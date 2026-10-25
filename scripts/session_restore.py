#!/usr/bin/env python3
"""session_restore — find Claude Code sessions lost to a terminal crash and reopen them.

Sessions are read from the transcript store (~/.claude/projects/<encoded-cwd>/<id>.jsonl).
Each one is resumed in the directory it was started in (the one its transcript is filed
under), with `claude --resume <id>`, and the pane keeps an interactive shell afterwards.

  session_restore.py list    [--crash | --minutes N | --last N | IDS...] [--all] [--json]
  session_restore.py restore [--crash | --minutes N | --last N | IDS...] [--layout split|tabs|windows]
                             [--orientation horizontal|vertical] [--command TEMPLATE] [--dry-run]

Selection (default: --crash):
  --crash       the sessions that closed together in the most recent burst: when a terminal
                dies, every Claude Code session in it writes its transcript on the way out,
                within a second or so of the others (window: --cluster-seconds, default 10)
  --minutes N   sessions with transcript activity in the last N minutes
  --last N      the N most recently active sessions, however old
  IDS           explicit session ids (or unique prefixes)
Sessions still running (live entries in ~/.claude/sessions/<pid>.json), and the session
invoking this script, are skipped unless --all is given.

Layouts (Konsole):
  split    one window, one tab, every session in its own split pane (default)
  tabs     one window, one tab per session
  windows  one window per session

Defaults can be set with env vars SESSION_RESTORE_LAYOUT, SESSION_RESTORE_ORIENTATION,
SESSION_RESTORE_CLUSTER_SECONDS and SESSION_RESTORE_COMMAND (template; {id} and {cwd} are replaced).
"""

import argparse
import glob
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

CONFIG = os.path.expanduser(os.environ.get("CLAUDE_CONFIG_DIR", "~/.claude"))
PROJECTS = CONFIG + "/projects"
SESSIONS = CONFIG + "/sessions"
TAIL_BYTES = 2 * 1024 * 1024
DEFAULT_COMMAND = "claude --resume {id}"


# ---------- discovery ----------

def _human_prompt(rec):
    """Text of a prompt the user typed, or None for tool results, meta and command records."""
    if rec.get("type") != "user" or rec.get("isMeta") or rec.get("isSidechain"):
        return None
    content = (rec.get("message") or {}).get("content")
    if isinstance(content, list):
        if any(b.get("type") == "tool_result" for b in content if isinstance(b, dict)):
            return None
        content = " ".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    if not isinstance(content, str):
        return None
    text = content.strip()
    if not text or text.startswith("<"):
        return None
    return text


def _parse_ts(ts):
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def _encode(cwd):
    """Claude Code's project-folder name for a directory: every non-alphanumeric becomes '-'."""
    return re.sub(r"[^A-Za-z0-9]", "-", cwd)


def read_session(path):
    """Id, launch directory, title and last typed prompt of one transcript.

    The directory is the one the transcript is filed under (its project folder), not the
    last `cwd` seen: a session that cd'd elsewhere can only be resumed from where it started.
    """
    sid = os.path.basename(path)[:-6]
    folder = os.path.basename(os.path.dirname(path))
    info = {"id": sid, "path": path, "mtime": os.path.getmtime(path),
            "cwd": None, "title": None, "last_prompt": None, "last_prompt_at": None}
    seen = []
    size = os.path.getsize(path)
    with open(path, "rb") as fh:
        head = [fh.readline() for _ in range(50)]
        if size > TAIL_BYTES:
            fh.seek(size - TAIL_BYTES)
            fh.readline()  # drop the partial first line
        else:
            fh.seek(0)
        lines = fh.read().decode("utf-8", "replace").splitlines()
    for line in reversed(lines):
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if rec.get("cwd") and rec["cwd"] not in seen:
            seen.append(rec["cwd"])
        if not info["title"]:
            info["title"] = rec.get("customTitle") or rec.get("aiTitle") or (rec.get("summary") if rec.get("type") == "summary" else None)
        if not info["last_prompt"]:
            text = _human_prompt(rec)
            if text:
                info["last_prompt"] = text
                info["last_prompt_at"] = _parse_ts(rec.get("timestamp", ""))
    for line in head:
        try:
            cwd = json.loads(line).get("cwd")
        except Exception:
            continue
        if cwd and cwd not in seen:
            seen.append(cwd)
    matching = [c for c in seen if _encode(c) == folder]
    info["cwd"] = matching[0] if matching else (seen[-1] if seen else None)
    return info


def running_session_ids():
    """Session ids of live Claude Code processes, from the ~/.claude/sessions/<pid>.json registry.

    An entry whose pid is gone is a leftover from a crash and does not count.
    """
    live = set()
    for f in glob.glob(SESSIONS + "/*.json"):
        try:
            with open(f) as fh:
                rec = json.load(fh)
        except Exception:
            continue
        if rec.get("sessionId") and os.path.exists(f"/proc/{rec.get('pid')}"):
            live.add(rec["sessionId"])
    return live


def all_sessions():
    paths = [p for p in glob.glob(PROJECTS + "/*/*.jsonl")]
    paths.sort(key=os.path.getmtime, reverse=True)
    return paths


def select(args):
    me = os.environ.get("CLAUDE_CODE_SESSION_ID")
    live = set() if args.all else running_session_ids()
    paths = all_sessions()
    if args.ids:
        chosen = []
        for want in args.ids:
            hits = [p for p in paths if os.path.basename(p).startswith(want)]
            if len(hits) != 1:
                sys.exit(f"session id {want!r}: {len(hits)} matches")
            chosen.append(read_session(hits[0]))
        return chosen
    out = []
    cutoff = None
    if args.minutes is not None:
        cutoff = time.time() - args.minutes * 60
    elif args.last is None:  # --crash
        cutoff = 0.0
    for p in paths:
        if cutoff is not None and os.path.getmtime(p) < cutoff:
            break
        sid = os.path.basename(p)[:-6]
        if not args.all and (sid == me or sid in live):
            continue
        if cutoff == 0.0:
            cutoff = os.path.getmtime(p) - args.cluster_seconds
        info = read_session(p)
        if not info["last_prompt"]:
            continue  # never had a typed prompt: headless or aborted, nothing to resume
        out.append(info)
        if args.last is not None and len(out) >= args.last:
            break
    return out


def _ago(ts):
    if not ts:
        return "?"
    m = int((time.time() - ts) / 60)
    return f"{m}m" if m < 120 else f"{m // 60}h{m % 60:02d}m"


def cmd_list(args):
    sessions = select(args)
    if args.json:
        print(json.dumps([{k: v for k, v in s.items() if k != "path"} | {"mtime_iso": datetime.fromtimestamp(s["mtime"], timezone.utc).isoformat()} for s in sessions], indent=2))
        return
    if not sessions:
        print("no matching sessions")
        return
    for n, s in enumerate(sessions, 1):
        cwd = (s["cwd"] or "?").replace(os.path.expanduser("~"), "~")
        prompt = (s["last_prompt"] or "").replace("\n", " ")[:90]
        print(f"{n:>2}. {s['id'][:8]}  active {_ago(s['mtime'])} ago  {cwd}")
        if s["title"]:
            print(f"      {s['title']}")
        print(f"      last prompt ({_ago(s['last_prompt_at'])} ago): {prompt}")


# ---------- Konsole ----------
#
# Konsole (observed on 25.12.3) disables runCommand/sendText over D-Bus by default
# ("Security sensitive DBus API is disabled in the settings"), so nothing here types into a
# running shell. Each pane is started with its own launcher script instead: a --layout JSON
# for splits (per-widget "WorkingDirectory" and "Command" keys), --tabs-from-file for tabs,
# -e for windows. A script path rather than a command line, because --tabs-from-file does not
# honour quotes in its `command:` field.

def _run_dir():
    root = os.path.join(tempfile.gettempdir(), "session-restore")
    os.makedirs(root, exist_ok=True)
    # Unique per run: two restores in the same second must not share (and overwrite) launchers.
    return tempfile.mkdtemp(prefix=time.strftime("%Y%m%d-%H%M%S-"), dir=root)  # left in place: Konsole reads these later


def launcher(run_dir, s, template):
    """Script that resumes one session in its directory, then leaves an interactive shell open."""
    shell = os.environ.get("SHELL") or "/bin/bash"
    cmd = template.format(id=s["id"], cwd=shlex.quote(s["cwd"]))
    path = os.path.join(run_dir, s["id"] + ".sh")
    with open(path, "w") as fh:
        fh.write("#!/bin/sh\n"
                 f"cd {shlex.quote(s['cwd'])} || exit 1\n"
                 f"{shlex.quote(shell)} -ic {shlex.quote(cmd)}\n"  # -i so aliases and functions resolve
                 f"exec {shlex.quote(shell)} -i\n")
    os.chmod(path, 0o755)
    return path


def launch(argv):
    proc = subprocess.Popen(["konsole", "--separate", *argv], stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, start_new_session=True)
    return proc.pid


def restore_split(sessions, template, orientation):
    run = _run_dir()
    layout = {"Orientation": orientation.capitalize(),
              "Widgets": [{"SessionRestoreId": 0, "WorkingDirectory": s["cwd"],
                           "Command": launcher(run, s, template)} for s in sessions]}
    path = os.path.join(run, "layout.json")
    with open(path, "w") as fh:
        json.dump(layout, fh, indent=1)
    return [launch(["--layout", path])], run


def restore_tabs(sessions, template):
    run = _run_dir()
    lines = []
    for s in sessions:
        title = (s["title"] or os.path.basename(s["cwd"])).replace(";;", ";")[:40]
        lines.append(f"title: {title};; workdir: {s['cwd']};; command: {launcher(run, s, template)}")
    path = os.path.join(run, "tabs.txt")
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    # --tabs-from-file still opens one default tab; giving it /bin/true (a per-launch
    # override, not saved to the profile) makes it exit cleanly and close.
    return [launch(["-p", "Command=/bin/true", "--tabs-from-file", path])], run


def restore_windows(sessions, template):
    run = _run_dir()
    return [launch(["--workdir", s["cwd"], "-e", launcher(run, s, template)]) for s in sessions], run


def cmd_restore(args):
    sessions = select(args)
    missing = [s for s in sessions if not s["cwd"] or not os.path.isdir(s["cwd"])]
    sessions = [s for s in sessions if s not in missing]
    plan = {"layout": args.layout, "orientation": args.orientation, "command": args.command,
            "sessions": [{"id": s["id"], "cwd": s["cwd"], "title": s["title"]} for s in sessions],
            "skipped_missing_cwd": [{"id": s["id"], "cwd": s["cwd"]} for s in missing]}
    if not sessions:
        print(json.dumps(plan | {"result": "nothing to restore"}, indent=2))
        return
    if args.dry_run:
        print(json.dumps(plan | {"result": "dry run"}, indent=2))
        return
    if not shutil.which("konsole"):
        sys.exit("konsole not found; only Konsole is supported so far")
    if args.layout == "split":
        pids, spec = restore_split(sessions, args.command, args.orientation)
    elif args.layout == "tabs":
        pids, spec = restore_tabs(sessions, args.command)
    else:
        pids, spec = restore_windows(sessions, args.command)
    print(json.dumps(plan | {"result": "launched", "konsole_pids": pids, "launchers": spec}, indent=2))


def main():
    env = os.environ.get
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("list", "restore"):
        p = sub.add_parser(name)
        p.add_argument("ids", nargs="*", help="explicit session ids or unique prefixes")
        how = p.add_mutually_exclusive_group()
        how.add_argument("--crash", action="store_true", help="sessions that closed together most recently (default)")
        how.add_argument("--minutes", type=float, help="sessions active in the last N minutes")
        how.add_argument("--last", type=int, help="the N most recently active sessions")
        p.add_argument("--cluster-seconds", type=float, default=float(env("SESSION_RESTORE_CLUSTER_SECONDS", "10")))
        p.add_argument("--all", action="store_true", help="include sessions that are still running")
        if name == "list":
            p.add_argument("--json", action="store_true")
        else:
            p.add_argument("--layout", choices=["split", "tabs", "windows"], default=env("SESSION_RESTORE_LAYOUT", "split"))
            p.add_argument("--orientation", choices=["horizontal", "vertical"], default=env("SESSION_RESTORE_ORIENTATION", "horizontal"),
                           help="split panes: horizontal = side by side, vertical = stacked")
            p.add_argument("--command", default=env("SESSION_RESTORE_COMMAND", DEFAULT_COMMAND))
            p.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    (cmd_list if args.cmd == "list" else cmd_restore)(args)


if __name__ == "__main__":
    main()
