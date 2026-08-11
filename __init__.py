"""Mirror persisted Hermes session titles into the current terminal window.

Hermes does not expose a native ``on_session_title_changed`` plugin hook. This
plugin therefore wraps the one persistence boundary shared by manual, derived,
and LLM-generated title writes. It writes both standard OSC 0 and OSC 2 title
sequences when stdout is a TTY, so gateway, cron, and background processes are
unaffected.
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Any, Callable


_ORIGINAL_SETTER_ATTR = "_terminal_session_title_original_setter"
_ORIGINAL_CLI_COMMAND_ATTR = "_terminal_session_title_original_process_command"
_ORIGINAL_CLI_RUN_ATTR = "_terminal_session_title_original_run"


def _safe_terminal_title(value: Any) -> str:
    """Return a single-line OSC-safe terminal title."""
    return " ".join(
        str(value or "Hermes").replace("\x1b", "").replace("\x07", "").split()
    ) or "Hermes"


def _run_tmux(*args: str) -> None:
    """Run a cosmetic tmux command without affecting Hermes behavior."""
    try:
        subprocess.run(
            ["tmux", *args],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=1,
        )
    except (OSError, subprocess.SubprocessError):
        return


def _rename_tmux_window(title: str) -> None:
    """Mirror a title to its tmux window and the outer terminal tab.

    ``TMUX_PANE`` selects the precise originating pane, avoiding accidental
    renames of the active window in a concurrently used tmux client. tmux
    normally owns the outer terminal title and defaults ``set-titles`` to off,
    which leaves terminals showing a session summary such as ``1219: 1 windows``
    even after the window is named. Enable title propagation and make it follow
    the active window name before explicitly naming the originating window.
    """
    pane = os.environ.get("TMUX_PANE")
    if not os.environ.get("TMUX") or not pane:
        return
    _run_tmux("set-option", "-t", pane, "set-titles", "on")
    _run_tmux("set-option", "-t", pane, "set-titles-string", "#W")
    _run_tmux("rename-window", "-t", pane, title)


def _write_terminal_title(title: Any) -> None:
    """Set the controlling terminal and active tmux-window titles.

    Prompt-toolkit can replace ``sys.stdout`` with a non-TTY proxy while Hermes
    runs. Writing directly to ``/dev/tty`` keeps OSC controls on the terminal
    that launched Hermes (including VS Code's integrated terminal) instead of
    silently discarding them through that proxy. When the process is inside
    tmux, its containing window is renamed too. Gateway/cron/background jobs
    have no controlling TTY and harmlessly fall through to a no-op.
    """
    safe_title = _safe_terminal_title(title)
    sequence = f"\x1b]0;{safe_title}\x07\x1b]2;{safe_title}\x07"
    wrote_to_terminal = False
    try:
        with open("/dev/tty", "w", encoding="utf-8", errors="ignore") as tty:
            if tty.isatty():
                tty.write(sequence)
                tty.flush()
                wrote_to_terminal = True
    except OSError:
        pass

    if not wrote_to_terminal:
        try:
            if not sys.stdout.isatty():
                return
            sys.stdout.write(sequence)
            sys.stdout.flush()
            wrote_to_terminal = True
        except Exception:
            # A terminal title is cosmetic; it must never affect persistence.
            return

    if wrote_to_terminal:
        _rename_tmux_window(safe_title)


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


def _install_cli_close_title_writer() -> None:
    """Leave the CLI terminal named for the session that just closed.

    ``HermesCLI.run`` owns interactive teardown for `/exit`, EOF, signals, and
    terminal-window closes. Its ``finally`` block flushes and closes the session,
    so a wrapper's own ``finally`` is a narrow, reliable place to publish the
    opaque session ID as a copyable ``hermes --resume`` target.
    """
    try:
        from cli import HermesCLI
    except Exception:
        return

    if getattr(HermesCLI, _ORIGINAL_CLI_RUN_ATTR, None) is not None:
        return

    original: Callable[..., Any] = HermesCLI.run

    def wrapped(self: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            return original(self, *args, **kwargs)
        finally:
            session_id = getattr(self, "session_id", None)
            agent = getattr(self, "agent", None)
            session_id = getattr(agent, "session_id", None) or session_id
            if session_id:
                _write_terminal_title(session_id)

    setattr(HermesCLI, _ORIGINAL_CLI_RUN_ATTR, original)
    HermesCLI.run = wrapped


def register(ctx: Any) -> None:
    """Install title writers before commands or persistence can run."""
    _install_title_writer()
    _install_pending_cli_title_writer()
    _install_cli_close_title_writer()
