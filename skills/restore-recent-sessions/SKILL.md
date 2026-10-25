---
name: restore-recent-sessions
description: Reopen the last N Claude Code sessions, or picked ones, each in its own repo, in one Konsole window of split panes, tabs or separate windows. Lists recent sessions to choose from.
---

# Restore recent sessions

For bringing back a working set on purpose (after a reboot, the next morning), not only
after a crash. For a crash, `restore-lost-sessions` finds the right set by itself.

```bash
SR="${CLAUDE_PLUGIN_ROOT}/scripts/session_restore.py"
python3 "$SR" list --last 10        # numbered: repo, title, last active, last prompt
```

1. List, then let the user pick by number, repo or title. "The last five" means
   `--last 5`.
2. Restore. The default layout is one window with side-by-side split panes:
   ```bash
   python3 "$SR" restore --last 5
   python3 "$SR" restore 16a5574a 2f6863cc 12117afb --layout tabs
   ```
3. Report what opened and anything skipped (`skipped_missing_cwd`: the repo was moved or
   deleted).

Each pane `cd`s to the directory the session was **started** in. A session that changed
directory midway can only be resumed from there, because Claude Code files the
transcript under the starting directory's project folder. Options and env defaults are
the same as `restore-lost-sessions`.
