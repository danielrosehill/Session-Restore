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
| `diagnose-lost-sessions` | Find out why: a silent close, a Konsole crash, or a KWin crash and the command that caused it |
| `guard-konsole-close` | Prevention: turn Konsole's "close anyway?" prompt back on, test it, keep it on |
| `setup` | First install on this machine: plugin, checks, close guard |
| `update` | Update to the latest release, report what changed (`CHANGELOG.md`), apply it |
| `install-on-lan-host` | Install the plugin and close guard on other Linux machines over SSH |

The restore skills use one script, `scripts/session_restore.py`:

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

  Konsole is started without the variables a running Claude Code sets for its children
  (`CLAUDECODE`, `CLAUDE_CODE_CHILD_SESSION`, `CLAUDE_CODE_SESSION_ID`, ...). Restoring
  from inside a session otherwise passes them to every pane, and the resumed sessions
  start with "Transcript saving is off — inherited CLAUDE_CODE_CHILD_SESSION marker" (0.2.0
  had this bug; found 2026-10-25).

  Konsole 25.12 refuses `runCommand`/`sendText` over D-Bus ("Security sensitive DBus API
  is disabled in the settings"), so nothing is typed into a running shell.

## Prevention: Konsole closing without asking

The "crash" this plugin was built for was often not a crash. With nothing in the logs and
no core dump, the Konsole window had been closed: one click on the title-bar X, which
sits next to minimise. Konsole normally asks "There are N processes running in M tabs.
Close anyway?" before it does that. The question disappears for good once "Don't ask
again" is ticked. The answer lands in `~/.config/konsolerc`:

```ini
[Notification Messages]
CloseAllTabs=true      # window close with programs running: closes without asking
CloseAllEmptyTabs=true # window close with several tabs
CloseSingleTab=true    # tab close with a program running
```

`scripts/konsole_close_guard.py` finds and removes these keys:

```bash
python3 scripts/konsole_close_guard.py check          # exit 1 if prompts are suppressed
python3 scripts/konsole_close_guard.py fix            # back up konsolerc, remove the keys
python3 scripts/konsole_close_guard.py install-watch  # systemd user .path unit re-runs fix on every konsolerc change
python3 scripts/konsole_close_guard.py test           # throwaway window, closed over D-Bus; exit 0 = the prompt blocked it
```

Verified 2026-10-27 on Konsole 25.12.3. With `CloseAllTabs=true` set, `test` reported the
window closed silently. After `fix`, the close blocked on the dialog.

Things to know:

- **Konsole reads konsolerc once per process.** A fix applies to Konsole processes
  started after it. `check` lists older ones by pid. Close and reopen them.
- The dialog's default button is "Close Window", so Enter still closes.
- A tab started as `konsole -e claude` isn't protected. Konsole ignores a foreground
  process named like the tab's own program. Start a shell and run `claude` in it.
- `test` opens a window. Run it in a nested or headless session if you don't want it on
  screen.

## Prevention: KWin crashes

On Plasma Wayland a KWin crash doesn't close Konsole at once. KWin restarts, the windows
look fine, and then a later repaint (here 13 minutes on, at a click on a tab-bar button)
segfaults Konsole in `QWaylandShmBackingStore::recreateBackBufferIfNeeded`. Every session in
the window goes with it. Claude Code sessions that adjust KDE settings can crash KWin
themselves. On 2026-10-28 a hand-built `dbus-send ... org.kde.kconfig.notify.ConfigChanged
'dict:string:string:...'` sent `a{ss}` where KConfig expects `a{saay}`, and KWin 6.6.6
segfaulted 0.24 s later ([incident](docs/incidents/2026-10-28-kwin-crash-from-malformed-kconfig-signal.md)).

`scripts/compositor_guard.py`:

```bash
python3 scripts/compositor_guard.py check          # last KWin crash; Konsole windows started before it (at risk), exit 1 if any
python3 scripts/compositor_guard.py culprits       # Bash commands Claude Code sessions ran in the 10 s before the last KWin crash
python3 scripts/compositor_guard.py install-watch  # systemd user service: critical notification on every KWin crash
```

The plugin also registers `compositor_guard.py hook` as a PreToolUse hook on Bash. It
refuses hand-sent `kconfig.notify` signals (use `kwriteconfig6 ... --notify`) and KWin
restarts (`kwin_wayland --replace`, `pkill kwin`, `kquitapp6 kwin`), and tells the agent why.

After a KWin crash, move the sessions out of every at-risk window into a new one before it
dies on its own: quit each session, close the window, `session_restore.py restore --minutes 5`.

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

`konsole_close_guard.py fix` edits `~/.config/konsolerc` (a backup goes next to it as
`konsolerc.bak-<time>`) and touches `~/.local/state/konsole-close-guard/last-fix`.
`install-watch` adds `~/.local/bin/konsole-close-guard` and
`~/.config/systemd/user/konsole-close-guard.{path,service}`. `uninstall-watch` removes them.
`compositor_guard.py install-watch` adds `~/.local/bin/kwin-crash-watch` and
`~/.config/systemd/user/kwin-crash-watch.service`; its `uninstall-watch` removes them.

Launcher scripts and the layout or tabs file go in `/tmp/session-restore/<timestamp>-<random>/`.
They stay there, because Konsole reads them after the script returns. The restore changes nothing else.

## Installation

```bash
claude plugins install session-restore@danielrosehill
```

Then run the `setup` skill. `update` pulls later releases, and `install-on-lan-host` sets
up other machines over SSH.

## License

MIT
