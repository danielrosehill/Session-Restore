---
name: guard-konsole-close
description: Stop Konsole closing a window or tab full of Claude Code sessions without asking. Checks konsolerc for suppressed close prompts, turns them back on, tests it, and can watch for them coming back. Use on "terminal closed without asking", "Konsole keeps closing", "lost all my sessions again".
---

# Guard Konsole against silent closes

Konsole asks before a window close kills running programs, unless "Don't ask again" was
ticked once. That answer is saved in `~/.config/konsolerc`, `[Notification Messages]`
(`CloseAllTabs`, `CloseAllEmptyTabs`, `CloseSingleTab`). From then on a stray click on the
title-bar X closes every tab without a prompt. No crash shows up in the logs, because
nothing crashed.

```bash
G="${CLAUDE_PLUGIN_ROOT}/scripts/konsole_close_guard.py"
python3 "$G" check            # exit 1 = prompts suppressed; also lists Konsole processes older than the last fix
python3 "$G" fix              # back up konsolerc, remove the keys
python3 "$G" install-watch    # systemd user path unit: re-run fix whenever konsolerc changes
python3 "$G" test             # throwaway Konsole window; exit 0 = the close was refused by the prompt
```

## Steps

1. Run `check`. If the prompts are already on and no watch is installed, offer `install-watch`.
2. Run `fix`, then `install-watch`. The watch catches the next "Don't ask again" tick and
   sends a desktop notification when it undoes one.
3. Tell the user: **Konsole windows already open keep the old setting** until they are
   closed (Konsole reads konsolerc once per process). `check` lists them by pid.
4. Verify with `test`. It opens a short-lived window, so run it in a headless session if
   one is available (for example the `kde-agent-workspace` plugin's sandbox:
   `kagent.py sandbox run -- python3 "$G" test`). Otherwise tell the user a window will
   flash up. As of 2026-10-27 the `kde-agent-workspace` sandbox makes `xdg-desktop-portal-kde`
   and `ksecretd` crash-loop on the host for about 30 s, which shows up as crash
   notifications. Warn the user first.

## Limits

- The close dialog's default button is "Close Window", so Enter in the dialog still closes.
- Konsole skips the check for a foreground process with the same name as the tab's own
  program. A tab started as `konsole -e claude` is not protected. Start a shell and run
  `claude` from it (Session Restore's launchers already do this).
