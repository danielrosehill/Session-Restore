# Session Restore

![License: MIT](https://img.shields.io/badge/license-MIT-green)

Your terminal crashed and took five Claude Code sessions with it. This plugin works out
which sessions were open, then reopens all of them, each in its own repo, in **one
Konsole window with side-by-side split panes**. Tabs or separate windows also work.

It was built around one way of working: every session scoped to a repo, several sessions
open side by side in Konsole on KDE Plasma. It may not suit other setups.

## Skills

| Skill | What it does |
| --- | --- |
| `restore-lost-sessions` | After a crash: find the sessions that died together and resume them all |
| `restore-recent-sessions` | Reopen the last N sessions, or picked ones, on purpose |
| `choose-sessions-to-restore` | A menu: tick sessions with space (crash losses marked), then pick one Konsole split (default) or a Konsole each |

Both use one script, `scripts/session_restore.py`:

```bash
python3 scripts/session_restore.py list                     # the most recent crash burst
python3 scripts/session_restore.py list --minutes 15        # or: active in the last 15 min
python3 scripts/session_restore.py restore                  # reopen them, split panes
python3 scripts/session_restore.py restore --last 5 --layout tabs
python3 scripts/session_restore.py restore 16a5574a 2f6863cc --dry-run
python3 scripts/session_restore.py list --last 12 --json     # menu data: repo, title, in_crash, ...
```

## How it works

- **Finding sessions.** Transcripts live in `~/.claude/projects/<folder>/<session-id>.jsonl`.
  The script reads each one's tail for its title (`ai-title` / `custom-title` records),
  its last typed prompt and its directory.
- **Spotting a crash.** When a terminal dies, each Claude Code session in it writes to
  its transcript on exit. In the crash this was built from, five sessions' files were
  last modified within 0.3 s of each other. The default selection (`--crash`) takes the
  newest such burst (10 s window, `--cluster-seconds`). Idle sessions are included too,
  because they also write on exit.
- **Skipping live ones.** Running sessions are listed in `~/.claude/sessions/<pid>.json`
  (`sessionId`, `pid`). An entry counts only if its pid is still alive.
- **The right directory.** `claude --resume <id>` finds a session only from the
  directory the transcript is filed under. A session can `cd` elsewhere midway, so the
  script uses the recorded `cwd` that maps to the transcript's folder name. That
  mapping is every non-alphanumeric character turned into `-`.
- **Opening Konsole.** Each session gets a small launcher script: `cd` to the repo, run
  `claude --resume <id>` in an interactive shell (so aliases work), then stay in a shell.
  - `split`: `konsole --separate --layout file.json`. The layout JSON takes per-pane
    `WorkingDirectory` and `Command` keys.
  - `tabs`: `konsole --separate --tabs-from-file`. The tabs file doesn't honour quotes in
    `command:`, which is why every layout uses launcher scripts rather than command
    lines. It also opens one extra default tab. `-p Command=/bin/true` makes that tab
    exit cleanly, and the override isn't saved to your profile.
  - `windows`: one `konsole --separate --workdir DIR -e launcher` per session.

  Konsole 25.12 refuses `runCommand`/`sendText` over D-Bus ("Security sensitive DBus API
  is disabled in the settings"), so nothing is typed into a running shell.

## Requirements

- Linux, KDE Konsole (verified on Konsole 25.12.3, Plasma 6.6.6 Wayland, 2026-10-25)
- Python 3.9+, standard library only
- Claude Code (verified on 2.1.310)

## Configuration

Set defaults through environment variables: `SESSION_RESTORE_LAYOUT` (`split` | `tabs` |
`windows`), `SESSION_RESTORE_ORIENTATION` (`horizontal` side by side | `vertical`
stacked), `SESSION_RESTORE_CLUSTER_SECONDS`, and `SESSION_RESTORE_COMMAND`, for example
`claude --resume {id} --permission-mode acceptEdits`.

## Files it writes

Launcher scripts and the layout or tabs file go in `/tmp/session-restore/<timestamp>-<random>/`.
They stay there, because Konsole reads them after the script returns. Nothing else is
changed.

## Installation

```bash
claude plugins install session-restore@danielrosehill
```

## License

MIT
