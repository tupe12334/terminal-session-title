"""Focused tests for terminal-session-title's cosmetic integrations."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch


_PLUGIN = Path(__file__).resolve().parents[1] / "__init__.py"
_SPEC = importlib.util.spec_from_file_location("terminal_session_title", _PLUGIN)
assert _SPEC and _SPEC.loader
plugin = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(plugin)


class TmuxWindowTitleTests(unittest.TestCase):
    def test_renames_the_window_containing_the_originating_pane(self) -> None:
        with patch.dict(
            os.environ, {"TMUX": "/tmp/tmux.sock,1,2", "TMUX_PANE": "%42"}, clear=False
        ), patch.object(plugin.subprocess, "run") as run:
            plugin._rename_tmux_window("Focused title")

        run.assert_called_once_with(
            ["tmux", "rename-window", "-t", "%42", "Focused title"],
            check=False,
            stdout=plugin.subprocess.DEVNULL,
            stderr=plugin.subprocess.DEVNULL,
            timeout=1,
        )

    def test_does_not_invoke_tmux_outside_a_tmux_pane(self) -> None:
        with patch.dict(os.environ, {}, clear=True), patch.object(
            plugin.subprocess, "run"
        ) as run:
            plugin._rename_tmux_window("Ignored")

        run.assert_not_called()

    def test_tmux_failures_are_cosmetic(self) -> None:
        with patch.dict(
            os.environ, {"TMUX": "/tmp/tmux.sock,1,2", "TMUX_PANE": "%42"}, clear=False
        ), patch.object(plugin.subprocess, "run", side_effect=OSError):
            plugin._rename_tmux_window("Still safe")


class TitleSanitizationTests(unittest.TestCase):
    def test_removes_escape_controls_and_flattens_whitespace(self) -> None:
        self.assertEqual(plugin._safe_terminal_title("  A\x1b title\x07\n here  "), "A title here")


if __name__ == "__main__":
    unittest.main()
