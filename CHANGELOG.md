# Changelog

Each entry says what changed and, under **Apply**, anything an existing install has to do
after updating. The `update` skill reads this file.

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
