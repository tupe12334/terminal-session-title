"""Mirror persisted Hermes session titles into the current terminal window.

Hermes does not expose a native ``on_session_title_changed`` plugin hook. This
plugin therefore wraps the one persistence boundary shared by manual, derived,
and LLM-generated title writes. It writes both standard OSC 0 and OSC 2 title
sequences when stdout is a TTY, so gateway, cron, and background processes are
unaffected.
"""

from __future__ import annotations

import sys
from typing import Any, Callable


_ORIGINAL_SETTER_ATTR = "_terminal_session_title_original_setter"
_ORIGINAL_CLI_COMMAND_ATTR = "_terminal_session_title_original_process_command"


def _safe_terminal_title(value: Any) -> str:
    """Return a single-line OSC-safe terminal title."""
    return " ".join(
        str(value or "Hermes").replace("\x1b", "").replace("\x07", "").split()
    ) or "Hermes"


def _write_terminal_title(title: Any) -> None:
    """Set the controlling terminal's title without visible terminal text.

    Prompt-toolkit can replace ``sys.stdout`` with a non-TTY proxy while Hermes
    runs. Writing directly to ``/dev/tty`` keeps OSC controls on the terminal
    that launched Hermes (including VS Code's integrated terminal) instead of
    silently discarding them through that proxy. Gateway/cron jobs normally
    have no controlling TTY and harmlessly fall through to a no-op.
    """
    sequence = f"\x1b]0;{_safe_terminal_title(title)}\x07\x1b]2;{_safe_terminal_title(title)}\x07"
    try:
        with open("/dev/tty", "w", encoding="utf-8", errors="ignore") as tty:
            tty.write(sequence)
            tty.flush()
        return
    except OSError:
        pass

    try:
        if not sys.stdout.isatty():
            return
        sys.stdout.write(sequence)
        sys.stdout.flush()
    except Exception:
        # A terminal title is cosmetic; it must never affect title persistence.
        return


def _install_title_writer() -> None:
    """Patch the shared SessionDB title persistence boundary exactly once."""
    try:
        from hermes_state import SessionDB
    except Exception:
        return

    if getattr(SessionDB, _ORIGINAL_SETTER_ATTR, None) is not None:
        return

    original: Callable[..., bool] = SessionDB._set_session_title

    def wrapped(self: Any, session_id: str, title: str, *, source: str) -> bool:
        changed = original(self, session_id, title, source=source)
        if changed:
            _write_terminal_title(title)
        return changed

    setattr(SessionDB, _ORIGINAL_SETTER_ATTR, original)
    SessionDB._set_session_title = wrapped


def _install_pending_cli_title_writer() -> None:
    """Mirror ``/title`` immediately when CLI persistence is intentionally deferred.

    A brand-new CLI session has no database row. Hermes correctly queues a
    manual ``/title`` until the first user message creates that row, but the
    SessionDB wrapper cannot see a write that has not happened yet. Wrap the
    CLI command boundary and emit only when the command successfully populated
    ``_pending_title``; persisted titles remain handled by ``SessionDB`` above.
    """
    try:
        from cli import HermesCLI
    except Exception:
        return

    if getattr(HermesCLI, _ORIGINAL_CLI_COMMAND_ATTR, None) is not None:
        return

    original: Callable[..., bool] = HermesCLI.process_command

    def wrapped(self: Any, command: str) -> bool:
        result = original(self, command)
        parts = command.strip().split(maxsplit=1) if isinstance(command, str) else []
        if len(parts) == 2 and parts[0].lower() == "/title":
            pending = getattr(self, "_pending_title", None)
            if pending:
                _write_terminal_title(pending)
        return result

    setattr(HermesCLI, _ORIGINAL_CLI_COMMAND_ATTR, original)
    HermesCLI.process_command = wrapped


def register(ctx: Any) -> None:
    """Install title writers before commands or persistence can run."""
    _install_title_writer()
    _install_pending_cli_title_writer()
