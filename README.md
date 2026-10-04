# terminal-session-title

A native [Hermes Agent](https://github.com/NousResearch/hermes-agent) plugin that mirrors session titles to the active terminal tab and, when running inside tmux, its containing tmux window.

It covers manual `/title` commands, including a title queued before the first message, plus Hermes-generated session titles. When an interactive CLI chat closes, it changes both titles to the exact session ID (for example, `20260811_204918_98afaf`) so the tab/window is an immediate `hermes --resume` target. The plugin emits terminal title control sequences and invokes tmux only when it has a controlling TTY, so gateway, cron, and background processes are unaffected.

## tmux

Inside tmux, the plugin uses the originating `$TMUX_PANE` to rename only its containing window. It also enables tmux terminal-title propagation and sets it to the active window name, so the outer terminal tab shows the Hermes title instead of tmux's default session summary (for example, `1219: 1 windows (attached)`). Explicitly naming a tmux window disables tmux automatic window renaming for that window, so Hermes titles persist rather than being overwritten by the running process name.

## Install

```sh
hermes plugins install tupe12334/terminal-session-title --enable
```

Restart Hermes after installation so the plugin can register.

## VS Code integrated terminal

To mirror the title into VS Code terminal tabs, enable this User setting and open a new integrated terminal:

```jsonc
"terminal.integrated.tabs.allowAgentCliTitle": true
```

## Compatibility

This plugin wraps Hermes' internal `SessionDB._set_session_title` persistence boundary because Hermes currently has no public session-title-change plugin hook. Re-run its focused checks after upgrading Hermes; replace the wrapper with an official hook if one becomes available.

## Development

A native Hermes plugin is a directory containing `plugin.yaml` and an `__init__.py` with `register(ctx)`. The manifest name and directory name are both `terminal-session-title`.

Run the standard-library test suite:

```sh
python3 -m unittest discover -s tests -v
```

## License

MIT. See [LICENSE](LICENSE).
