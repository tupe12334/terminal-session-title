# terminal-session-title

A native [Hermes Agent](https://github.com/NousResearch/hermes-agent) plugin that mirrors session titles to the active terminal window/tab title.

It covers manual `/title` commands, including a title queued before the first message, plus Hermes-generated session titles. The plugin emits terminal title control sequences only when it has a controlling TTY, so gateway, cron, and background processes are unaffected.

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

## License

MIT. See [LICENSE](LICENSE).
