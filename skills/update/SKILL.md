---
name: update
description: Update Session Restore to the latest release. Finds what changed since the installed version from CHANGELOG.md, updates the plugin, and applies anything the new version needs on this machine (for example reinstalling the close-guard watch). Use on "update session restore", "I shipped updates", "apply the latest".
---

# Update Session Restore

## Steps

1. **Installed version:** `claude plugin list` (the `session-restore` entry), or
   `ls ~/.claude/plugins/cache/*/session-restore/`.
2. **Fetch and update:**
   ```bash
   claude plugin marketplace update danielrosehill
   claude plugin update session-restore@danielrosehill
   P=$(ls -d ~/.claude/plugins/cache/*/session-restore/*/ | sort -V | tail -1)
   ```
   If the version didn't change, say it is already current and stop.
3. **What changed:** read `$P/CHANGELOG.md` and tell the user the entries newer than the
   old version, in a line or two each.
4. **Apply.** Do what those entries' **Apply** lines say. Every time, also:
   - if the close-guard watch is installed (`systemctl --user is-enabled konsole-close-guard.path`),
     rerun `python3 "$P/scripts/konsole_close_guard.py" install-watch`. That refreshes the
     copy in `~/.local/bin`, which doesn't follow plugin updates.
   - run `konsole_close_guard.py check`.
5. Report: old version, new version, the changes, and what was applied. New or changed
   skills load in new sessions.
