#!/usr/bin/env python3
"""compositor_guard — stop Claude Code sessions from crashing KWin, and warn when KWin has crashed.

On Plasma Wayland a KWin crash doesn't close Konsole at once. KWin restarts, Konsole
reconnects, and its windows look fine. The windows are damaged, though: minutes later a
repaint (a click on a tab-bar or toolbar button) segfaults Konsole in
QWaylandShmBackingStore::recreateBackBufferIfNeeded, and every session in that window goes with it.

  compositor_guard.py hook                          Claude Code PreToolUse hook (Bash): blocks commands known to crash or kill KWin
  compositor_guard.py check   [--json]              last KWin crash, and the Konsole processes started before it (at risk)
  compositor_guard.py culprits [--at TIME] [--window S]  Bash commands Claude Code sessions ran just before a KWin crash
  compositor_guard.py watch                         follow the journal; desktop notification on every KWin crash
  compositor_guard.py install-watch                 systemd user service running `watch`
  compositor_guard.py uninstall-watch

Exit codes: hook 2 = blocked (reason on stderr); check 0 = no Konsole at risk, 1 = some at risk.
"""

import argparse
import datetime as dt
import glob
import json
import os
import re
import shutil
import subprocess
import sys

KWIN_EXE = "/usr/bin/kwin_wayland"
PROJECTS = os.path.expanduser("~/.claude/projects")
UNIT = "kwin-crash-watch"
INSTALL_PATH = os.path.expanduser("~/.local/bin/kwin-crash-watch")
UNIT_DIR = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "systemd", "user")

# A command word at the start of a shell segment (after ; & | ( or $( ).
_START = r"(?:^|[;&|(\n]\s*|\$\(\s*)(?:sudo\s+)?"
BLOCKED = [
    # 2026-10-28: `dbus-send --type=signal /kwinrc org.kde.kconfig.notify.ConfigChanged
    # 'dict:string:string:"NightColor","DayTemperature"'` sent a{ss}; KConfigWatcher expects
    # a{saay} and KWin 6.6.6 segfaulted in QDBusArgument::beginArray 0.24 s later.
    (re.compile(_START + r"(?:dbus-send|gdbus\s+emit|busctl\s+(?:--user\s+)?emit|qdbus6?)\b[^;&|\n]*kconfig\.notify"),
     "A hand-built org.kde.kconfig.notify.ConfigChanged signal with the wrong signature crashes "
     "KWin (and every app watching that config). Use `kwriteconfig6 --file <rc> --group <g> --key <k> "
     "<value> --notify`, which sends the correct a{saay} payload, or `qdbus6 org.kde.KWin /KWin reconfigure`."),
    (re.compile(_START + r"(?:kwin_wayland\b[^;&|\n]*--replace|kquitapp6?\s+kwin|(?:killall|pkill)\s+(?:-\S+\s+)*kwin"
                         r"|systemctl\s+--user\s+(?:restart|stop|kill)\s+plasma-kwin)"),
     "Restarting or killing KWin on Wayland leaves every open Konsole window damaged: it segfaults on a "
     "later repaint and takes its Claude Code sessions with it. Ask the user to do this themselves, "
     "after saving work, or use `qdbus6 org.kde.KWin /KWin reconfigure` to reload settings."),
]


def cmd_hook(_args):
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    if data.get("tool_name") != "Bash":
        return 0
    command = (data.get("tool_input") or {}).get("command") or ""
    for pattern, reason in BLOCKED:
        if pattern.search(command):
            print(f"Blocked by session-restore compositor_guard: {reason}", file=sys.stderr)
            return 2
    return 0


def kwin_crashes(limit=20):
    """[(datetime, pid, signal)] of KWin core dumps in the user journal, oldest first."""
    r = subprocess.run(["journalctl", "--user", f"COREDUMP_EXE={KWIN_EXE}", "-o", "json", "-n", str(limit),
                        "--no-pager"], capture_output=True, text=True)
    out = []
    for line in r.stdout.splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        t = dt.datetime.fromtimestamp(int(d["__REALTIME_TIMESTAMP"]) / 1e6).astimezone()
        out.append((t, d.get("COREDUMP_PID"), d.get("COREDUMP_SIGNAL_NAME")))
    return out


def konsole_processes():
    """[(pid, start datetime)] of running Konsole processes."""
    ticks = os.sysconf("SC_CLK_TCK")
    with open("/proc/stat") as fh:
        btime = next(int(l.split()[1]) for l in fh if l.startswith("btime"))
    out = []
    for pid in filter(str.isdigit, os.listdir("/proc")):
        try:
            with open(f"/proc/{pid}/comm") as fh:
                if fh.read().strip() != "konsole":
                    continue
            with open(f"/proc/{pid}/stat") as fh:
                start = int(fh.read().rsplit(")", 1)[1].split()[19])
        except OSError:
            continue
        out.append((int(pid), dt.datetime.fromtimestamp(btime + start / ticks).astimezone()))
    return sorted(out)


def cmd_check(args):
    crashes = kwin_crashes()
    last = crashes[-1][0] if crashes else None
    procs = konsole_processes()
    at_risk = [(p, s) for p, s in procs if last and s < last]
    if args.json:
        print(json.dumps({"last_kwin_crash": last.isoformat() if last else None,
                          "kwin_crashes": [c[0].isoformat() for c in crashes],
                          "konsole": [{"pid": p, "started": s.isoformat(), "at_risk": (p, s) in at_risk}
                                      for p, s in procs]}, indent=2))
    else:
        print(f"Last KWin crash: {last:%Y-%m-%d %H:%M:%S}" if last else "No KWin crash in the journal.")
        for p, s in procs:
            print(f"  konsole {p} started {s:%Y-%m-%d %H:%M:%S}" + ("  AT RISK (started before the crash)" if (p, s) in at_risk else ""))
        if at_risk:
            print("Open a new Konsole and move the sessions out of the at-risk windows: quit each Claude "
                  "session (Ctrl+D), close the window, then run session_restore.py restore --minutes 5.")
    return 1 if at_risk else 0


def bash_commands_between(start, end):
    """[(datetime, session id, cwd, command)] of Bash tool calls in Claude Code transcripts."""
    hits = []
    for path in glob.glob(os.path.join(PROJECTS, "*", "*.jsonl")):
        if os.path.getmtime(path) < start.timestamp():
            continue
        with open(path, errors="replace") as fh:
            for line in fh:
                if '"tool_use"' not in line:
                    continue
                try:
                    d = json.loads(line)
                    t = dt.datetime.fromisoformat(d["timestamp"].replace("Z", "+00:00"))
                except (ValueError, KeyError):
                    continue
                if not start <= t <= end:
                    continue
                for block in (d.get("message") or {}).get("content") or []:
                    if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") == "Bash":
                        hits.append((t.astimezone(), d.get("sessionId", os.path.basename(path)[:-6]), d.get("cwd"),
                                     block.get("input", {}).get("command", "")))
    return sorted(hits)


def cmd_culprits(args):
    if args.at:
        at = dt.datetime.fromisoformat(args.at)
        at = at if at.tzinfo else at.astimezone()
    else:
        crashes = kwin_crashes()
        if not crashes:
            sys.exit("No KWin crash in the journal; pass --at.")
        at = crashes[-1][0]
    # The core dump is logged ~2 s after the crash; look before it and a little after.
    hits = bash_commands_between(at - dt.timedelta(seconds=args.window), at + dt.timedelta(seconds=2))
    print(f"Bash commands from Claude Code sessions in the {args.window} s before {at:%Y-%m-%d %H:%M:%S}:")
    for t, sid, cwd, cmd in hits:
        flag = "  <- matches a blocked pattern" if any(p.search(cmd) for p, _ in BLOCKED) else ""
        print(f"\n{t:%H:%M:%S.%f}"[:-3] + f"  session {sid[:8]}  {cwd}{flag}\n  {cmd[:600]}")
    if not hits:
        print("  none")
    return 0


def notify(title, body):
    if shutil.which("notify-send"):
        subprocess.run(["notify-send", "-u", "critical", "-a", "KWin crash watch", title, body], check=False)


def cmd_watch(_args):
    proc = subprocess.Popen(["journalctl", "--user", "-f", "-n", "0", "-o", "json", f"COREDUMP_EXE={KWIN_EXE}"],
                            stdout=subprocess.PIPE, text=True)
    for line in proc.stdout:
        try:
            d = json.loads(line)
        except ValueError:
            continue
        t = dt.datetime.fromtimestamp(int(d["__REALTIME_TIMESTAMP"]) / 1e6)
        notify("KWin crashed: Konsole windows are at risk",
               f"KWin crashed at {t:%H:%M:%S}. Konsole windows opened before then can segfault on the next "
               "repaint and take their Claude sessions with them. Move the sessions to a new Konsole window now.")
        print(f"KWin crash at {t:%Y-%m-%d %H:%M:%S}", flush=True)
    return proc.wait()


def cmd_install_watch(_args):
    os.makedirs(os.path.dirname(INSTALL_PATH), exist_ok=True)
    shutil.copy2(os.path.abspath(__file__), INSTALL_PATH)
    os.chmod(INSTALL_PATH, 0o755)
    os.makedirs(UNIT_DIR, exist_ok=True)
    with open(os.path.join(UNIT_DIR, UNIT + ".service"), "w") as fh:
        fh.write("[Unit]\nDescription=Warn when KWin crashes (Konsole windows are then at risk)\n\n"
                 f"[Service]\nExecStart={INSTALL_PATH} watch\nRestart=always\nRestartSec=5\n\n"
                 "[Install]\nWantedBy=default.target\n")
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "enable", "--now", UNIT + ".service"], check=True)
    print(f"Installed {INSTALL_PATH} and {UNIT}.service.")
    return 0


def cmd_uninstall_watch(_args):
    subprocess.run(["systemctl", "--user", "disable", "--now", UNIT + ".service"], check=False)
    for f in (os.path.join(UNIT_DIR, UNIT + ".service"), INSTALL_PATH):
        if os.path.exists(f):
            os.remove(f)
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    print("Removed the watch.")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("hook").set_defaults(fn=cmd_hook)
    p = sub.add_parser("check"); p.add_argument("--json", action="store_true"); p.set_defaults(fn=cmd_check)
    p = sub.add_parser("culprits"); p.add_argument("--at"); p.add_argument("--window", type=int, default=10)
    p.set_defaults(fn=cmd_culprits)
    sub.add_parser("watch").set_defaults(fn=cmd_watch)
    sub.add_parser("install-watch").set_defaults(fn=cmd_install_watch)
    sub.add_parser("uninstall-watch").set_defaults(fn=cmd_uninstall_watch)
    args = ap.parse_args()
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
