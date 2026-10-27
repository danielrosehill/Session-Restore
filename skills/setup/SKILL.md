---
name: setup
description: First-time setup of Session Restore on this machine. Installs the plugin if needed, checks Konsole and Python, turns Konsole's close prompts back on and installs the watch that keeps them on. Use on "set up session restore", "install this", "I just downloaded it".
---

# Set up Session Restore

## Steps

1. **Requirements.** Check `command -v konsole python3 claude systemctl`. Konsole is
   required for restoring; without systemd user units, skip the watch in step 4.
2. **Plugin.** If `claude plugin list` doesn't show `session-restore`, install it:
   ```bash
   claude plugin marketplace add danielrosehill/Claude-Code-Plugins   # skip if `marketplace list` has it
   claude plugin install session-restore@danielrosehill
   ```
   Skills from a newly installed plugin load in new sessions. For the rest of this run,
   use the scripts from the installed copy:
   ```bash
   P=$(ls -d ~/.claude/plugins/cache/*/session-restore/*/ | sort -V | tail -1)
   ```
3. **Check the restore finds sessions:** `python3 "$P/scripts/session_restore.py" list --last 3`.
4. **Close guard:** follow the `guard-konsole-close` skill. Run `check`, then `fix`, then
   `install-watch`.
5. Report: the plugin version installed, whether the close prompts were suppressed and are
   now on, and that the watch is active (`systemctl --user is-active konsole-close-guard.path`).
   Tell the user to close and reopen any Konsole windows open before the fix.
