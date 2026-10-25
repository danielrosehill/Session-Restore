---
name: restore-lost-sessions
description: Restore Claude Code sessions lost when the terminal or Konsole crashed or quit. Finds the sessions that died together and resumes each in its repo, in one split window.
---

# Restore lost sessions

When a terminal dies, every Claude Code session in it writes its transcript on the way
out, within about a second of the others. That burst identifies the sessions that were
open. Each is resumed in the directory it was started in.

```bash
SR="${CLAUDE_PLUGIN_ROOT}/scripts/session_restore.py"
python3 "$SR" list                  # default selection: the most recent crash burst
```

## Steps

1. Run `list`. Show the user the numbered result: repo, title, how long ago, last prompt.
   Sessions still running and this session itself are already left out.
2. If the burst looks wrong (one session, or not the ones the user meant), widen it:
   - `list --minutes 15`: everything active in the last 15 minutes
   - `list --cluster-seconds 60`: a looser burst
   - `list --last 5`: the five most recent, however old
3. Layout: use the user's stated preference. If none was stated, use the default, **one
   Konsole window, one tab, side-by-side split panes** (`--layout split --orientation
   horizontal`). Ask only if the user hasn't said and there are more than six sessions:
   offer `tabs` or `windows` then, because the panes get narrow.
4. Restore with the same selection flags used in `list`. Add explicit ids to drop
   or pick sessions:
   ```bash
   python3 "$SR" restore                               # crash burst, split panes
   python3 "$SR" restore --minutes 15 --layout tabs
   python3 "$SR" restore b23972c1 634a69af             # just these (id prefixes)
   ```
   Use `--dry-run` first if the selection is in doubt. It prints the plan as JSON.
5. Report which sessions were reopened, in which layout, and any `skipped_missing_cwd`.

## Options

| Flag / env | Default | Meaning |
| --- | --- | --- |
| `--layout` / `SESSION_RESTORE_LAYOUT` | `split` | `split`, `tabs` or `windows` |
| `--orientation` / `SESSION_RESTORE_ORIENTATION` | `horizontal` | split panes side by side (`horizontal`) or stacked (`vertical`) |
| `--command` / `SESSION_RESTORE_COMMAND` | `claude --resume {id}` | what each pane runs; `{id}`, `{cwd}` substituted, runs in an interactive shell so aliases work |
| `--cluster-seconds` / `SESSION_RESTORE_CLUSTER_SECONDS` | `10` | width of the crash burst |
| `--all` | off | include sessions that are still running |

## Testing

To test the mechanics without opening windows on the user's screen, run it inside a
headless sandbox (the `kde-agent-workspace` plugin's `use-sandbox` skill) with a
harmless command:

```bash
kagent.py sandbox start
kagent.py sandbox run -- python3 "$SR" restore --command 'echo {id}'
kagent.py --sandbox capture --screen Virtual-0 -o shot.png
kagent.py sandbox stop
```

The sandbox shares the user's files, so keep a real `claude --resume` out of it.
Otherwise the session would be resumed in two places.
