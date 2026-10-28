---
name: diagnose-lost-sessions
description: Work out why Konsole died and took Claude Code sessions with it (a silent close, a Konsole crash, or a KWin crash and what triggered it), then switch on the matching prevention. Use on "why does Konsole keep crashing", "get to the bottom of this", "it happened again".
---

# Diagnose lost sessions

Restore first (`restore-lost-sessions`), then diagnose. Three causes have been seen, each
with its own fix:

| What the logs show | Cause | Prevention |
| --- | --- | --- |
| No Konsole core dump at the loss time | The window was **closed**: a click on the X with close prompts suppressed | `guard-konsole-close` |
| Konsole SIGSEGV in `QWaylandShmBackingStore::recreateBackBufferIfNeeded`, after a KWin crash | KWin crashed earlier and left the window damaged; a later repaint killed it | find what crashed KWin (below); `compositor_guard.py install-watch` |
| `kwin_wayland` SIGSEGV | The compositor crashed. Konsole may die at once or minutes later | `compositor_guard.py culprits`, then fix or block the trigger |

```bash
C="${CLAUDE_PLUGIN_ROOT}/scripts/compositor_guard.py"
coredumpctl list --since -1d                                   # what crashed, when
coredumpctl info <pid> | grep -A30 "Stack trace of thread <pid>" # the crashing thread's stack
python3 "$C" check                                             # last KWin crash; Konsole windows started before it (at risk)
python3 "$C" culprits --window 10                              # Bash commands sessions ran just before the last KWin crash
python3 "$C" culprits --at "2026-10-28 16:36:14"               # ... or before a given time
```

## Steps

1. Get the loss time from `session_restore.py list` (sessions' last write).
2. `coredumpctl list --since -1d`. No `konsole` entry near the loss time → silent close;
   run `guard-konsole-close`. A `konsole` entry → read its stack; a `kwin_wayland` entry
   shortly before it → KWin was the cause.
3. For a KWin crash, run `culprits`. A Claude Code command within a second or so of the
   crash is the prime suspect. Also read the user journal for the same seconds
   (`journalctl --user --since ... --until ... -o short-precise`) for non-Claude triggers.
   Report timing as evidence, not proof, unless the stack matches the command.
4. If the trigger is a command pattern, add it to `BLOCKED` in `compositor_guard.py` (the
   PreToolUse hook) with a dated comment, and record the incident in `docs/incidents/`.
5. Make sure the KWin watch runs (`systemctl --user is-active kwin-crash-watch.service`),
   or `install-watch`. Run `check`; for every at-risk Konsole, tell the user to move its
   sessions to a new window before it dies on its own.

## Known triggers

- **Hand-sent `org.kde.kconfig.notify.ConfigChanged`** (2026-10-28). `dbus-send ... 'dict:string:string:...'`
  sends `a{ss}`; KConfigWatcher expects `a{saay}` and KWin 6.6.6 segfaults unpacking it.
  `kwriteconfig6 ... --notify` sends the right payload. Blocked by the hook.
- **Restarting KWin** (`kwin_wayland --replace`, `pkill kwin`, `kquitapp6 kwin`). Same
  aftermath as a crash. Blocked by the hook.
