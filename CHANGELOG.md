# Changelog

Each entry says what changed and, under **Apply**, anything an existing install has to do
after updating. The `update` skill reads this file.

## 0.4.0 (2026-10-28)

- `scripts/compositor_guard.py` and a PreToolUse hook (`hooks/hooks.json`). The hook blocks
  Bash commands that crash or restart KWin: hand-sent `org.kde.kconfig.notify` signals and
  `kwin_wayland --replace` / `pkill kwin`. A KWin crash leaves Konsole windows damaged, and
  they segfault minutes later (`docs/incidents/2026-10-28-kwin-crash-from-malformed-kconfig-signal.md`).
- `compositor_guard.py check` lists Konsole windows at risk after a KWin crash. `culprits`
  finds the session commands run just before one. `install-watch` adds a desktop warning on every KWin crash.
- Skill `diagnose-lost-sessions`.
- **Apply:** run `python3 "$P/scripts/compositor_guard.py" install-watch`. The hook is active
  in sessions started after the update.

## 0.3.1 (2026-10-27)

- `install-on-lan-host`: how to recover when a host's settings hold an old marketplace entry.
- **Apply:** nothing.

## 0.3.0 (2026-10-27)

- `scripts/konsole_close_guard.py` and skill `guard-konsole-close`. They find Konsole close
  prompts suppressed in konsolerc, turn them back on, and test the result. A systemd user
  path unit keeps them on.
- Skills `setup`, `update` and `install-on-lan-host`.
- **Apply:** run the `guard-konsole-close` steps (`check`, `fix`, `install-watch`), then
  close and reopen Konsole windows that were open before the fix.

## 0.2.1 (2026-10-25)

- Konsole is started without Claude Code's session markers, so resumed sessions save their
  transcripts again.
- **Apply:** nothing.

## 0.2.0 (2026-10-25)

- Skill `choose-sessions-to-restore`. `list --json` adds repo, in_crash and ages.
- **Apply:** nothing.

## 0.1.0

- First release: `restore-lost-sessions`, `restore-recent-sessions`.
