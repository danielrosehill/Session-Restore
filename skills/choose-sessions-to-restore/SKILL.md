---
name: choose-sessions-to-restore
description: Menu to pick which Claude Code sessions to restore (space to toggle), then how to open them, one Konsole split (default) or a Konsole each. Use on "restore sessions", "which sessions".
---

# Choose sessions to restore

The user picks from a menu instead of typing ids: first which sessions, then how to open
them. Both questions go in **one** `AskUserQuestion` call so they come up back to back.

```bash
SR="${CLAUDE_PLUGIN_ROOT}/scripts/session_restore.py"
python3 "$SR" list --last 12 --json
```

Each entry has `id`, `repo` (where it was last working), `title`, `active_ago`,
`last_prompt`, `prompt_ago` and `in_crash` (closed in the most recent crash burst).
Sessions still running and this session are already left out.

## 1. Build the menu

Order: `in_crash` sessions first (newest first), then the rest by recency. Up to 12.

`AskUserQuestion` allows 2–4 options per question and 4 questions per call. Spread
the sessions over **up to three multi-select questions**, then add the layout question as
the last one:

- Split sessions into groups of at most 4, and never leave a group of 1: 5 → 3 + 2,
  9 → 4 + 3 + 2. With a single session, skip the menu and ask only the layout.
- Each session question: `multiSelect: true`, `header` like `Sessions 1-4` (≤ 12 chars),
  `question` like "Which sessions should I restore? (space to toggle)". The first group's
  question adds "Lost in the crash are marked." when any are.
- Option `label`: `<repo>: <2–3 words of title>`. Make every label unique.
- Option `description`: `<title>. Active <active_ago> ago[, lost in the crash]. Last: "<last_prompt, ~70 chars>"`.
  Put "lost in the crash" there. The tool can't preselect, so the description is how the
  suggestion shows.

Layout question (single-select, `header: "Open as"`):

| Label | Description | Maps to |
| --- | --- | --- |
| `One Konsole, split (Recommended)` | All sessions side by side in one window | `--layout split` |
| `One Konsole each` | A separate Konsole window per session | `--layout windows` |

Keep a label → id table in your head. The answers come back as labels.

## 2. Act on the answers

- Gather the ticked sessions across all session questions. None ticked: say so and stop.
- "Other" text such as "all", "the crash ones" or "all but Inbox" maps onto the same list.
  A tabs request maps to `--layout tabs`.
- If there were more than 12 candidates and the user asked for more, list again with
  `--last 24` and run a second menu.
- Restore:
  ```bash
  python3 "$SR" restore <id> <id> ... --layout split     # or windows / tabs
  ```
- Report what opened (repo + title per session) and any `skipped_missing_cwd`.

## Notes

- This opens real windows on the user's screen and resumes the sessions. That's the
  point, so don't run it in the sandbox. For a test of the mechanics, see
  `restore-lost-sessions` → Testing.
- More than six sessions in one split gets narrow. If the user picks seven or more with
  `split`, mention `tabs` in one line, but do what they chose.
