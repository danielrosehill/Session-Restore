#!/usr/bin/env python3
"""konsole_close_guard — keep Konsole asking before it closes a window or tab with programs running.

Konsole asks "There are N processes running in M tabs. Close anyway?" before a window close
kills them. Tick "Don't ask again" once (or have it set by an old config) and the answer is
saved in ~/.config/konsolerc, [Notification Messages]. From then on a stray click on the
title-bar X closes every tab, and every Claude Code session in it, without a prompt.

  konsole_close_guard.py check   [--json]        report suppressed prompts, and Konsole processes older than the last fix
  konsole_close_guard.py fix     [--quiet]       back up konsolerc and remove the suppressing keys
  konsole_close_guard.py test                    open a throwaway Konsole and check a close is refused
  konsole_close_guard.py install-watch           systemd user path unit: re-run `fix` whenever konsolerc changes
  konsole_close_guard.py uninstall-watch

Exit codes: check 0 = prompts on, 1 = suppressed; test 0 = prompt shown, 1 = closed silently.

Konsole reads konsolerc once per process (KSharedConfig) and never rereads it. A fix applies
only to Konsole processes started after it; `check` lists the ones started before.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

KONSOLERC = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "konsolerc")
GROUP = "Notification Messages"
# dontAskAgain keys of Konsole's close dialogs (Konsole 25.12, MainWindow::queryClose and
# ViewManager). Any stored value suppresses the dialog: "true"/"yes" auto-answers the
# primary button (close), "false"/"no" the secondary one.
KEYS = {
    "CloseAllTabs": "closing a window with programs running",
    "CloseAllEmptyTabs": "closing a window with several tabs open",
    "CloseSingleTab": "closing a tab with a program running",
}
STAMP = os.path.join(os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"),
                     "konsole-close-guard", "last-fix")  # when `fix` last changed konsolerc
UNIT = "konsole-close-guard"
INSTALL_PATH = os.path.expanduser("~/.local/bin/konsole-close-guard")
UNIT_DIR = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "systemd", "user")


def read_lines():
    try:
        with open(KONSOLERC) as fh:
            return fh.read().splitlines(keepends=True)
    except FileNotFoundError:
        return []


def suppressed(lines):
    """{key: value} for the close-dialog keys set in [Notification Messages]."""
    found, group = {}, None
    for line in lines:
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            group = s[1:-1]
        elif group == GROUP and "=" in s:
            k, v = s.split("=", 1)
            if k.strip() in KEYS:
                found[k.strip()] = v.strip()
    return found


def konsole_processes():
    """Running Konsole processes with their start time (epoch seconds)."""
    with open("/proc/stat") as fh:
        btime = next(int(l.split()[1]) for l in fh if l.startswith("btime"))
    hz = os.sysconf("SC_CLK_TCK")
    procs = []
    for pid in filter(str.isdigit, os.listdir("/proc")):
        try:
            with open(f"/proc/{pid}/comm") as fh:
                if fh.read().strip() != "konsole":
                    continue
            with open(f"/proc/{pid}/stat") as fh:
                fields = fh.read().rsplit(")", 1)[1].split()
            procs.append({"pid": int(pid), "started": btime + int(fields[19]) / hz})
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
    return procs


def cmd_check(args):
    keys = suppressed(read_lines())
    # Konsole rewrites konsolerc itself (window geometry), so its mtime says nothing; compare
    # against the last time `fix` changed it.
    fixed = os.path.getmtime(STAMP) if os.path.exists(STAMP) else None
    stale = [p for p in konsole_processes() if fixed and p["started"] < fixed]
    report = {
        "konsolerc": KONSOLERC,
        "prompts_on": not keys,
        "suppressed": {k: {"value": v, "dialog": KEYS[k]} for k, v in keys.items()},
        "last_fix": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(fixed)) if fixed else None,
        "konsole_started_before_last_fix": [
            {"pid": p["pid"], "started": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(p["started"]))}
            for p in stale],
    }
    if args.json:
        print(json.dumps(report, indent=1))
    else:
        if keys:
            print("Close prompts are OFF. Konsole will close without asking when:")
            for k, v in keys.items():
                print(f"  - {KEYS[k]}   ({k}={v})")
            print(f"Run `{os.path.basename(sys.argv[0])} fix` to turn them back on.")
        else:
            print("Close prompts are on.")
        if stale:
            print(f"{len(stale)} Konsole process(es) started before the last fix "
                  f"({report['last_fix']}) and still hold the old setting: "
                  + ", ".join(str(p["pid"]) for p in stale)
                  + ". Restart them to be sure.")
    return 1 if keys else 0


def cmd_fix(args):
    lines = read_lines()
    keys = suppressed(lines)
    if not keys:
        if not args.quiet:
            print("Close prompts are already on; nothing changed.")
        return 0
    backup = f"{KONSOLERC}.bak-{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.copy2(KONSOLERC, backup)
    out, group = [], None
    for line in lines:
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            group = s[1:-1]
        elif group == GROUP and "=" in s and s.split("=", 1)[0].strip() in KEYS:
            continue
        out.append(line)
    tmp = KONSOLERC + ".guard-tmp"
    with open(tmp, "w") as fh:
        fh.writelines(out)
    os.replace(tmp, KONSOLERC)
    os.makedirs(os.path.dirname(STAMP), exist_ok=True)
    open(STAMP, "w").close()
    msg = (f"Turned Konsole close prompts back on (removed {', '.join(keys)}; backup {backup}). "
           "Konsole windows already open keep the old setting until restarted.")
    print(msg)
    if args.quiet and shutil.which("notify-send"):
        subprocess.run(["notify-send", "-a", "Konsole close guard", "Konsole close prompts restored", msg],
                       check=False)
    return 0


def cmd_test(_args):
    """Throwaway `konsole --separate` window with a foreground job; ask it to close over D-Bus.
    The dialog blocks the call, so a timeout means the prompt works."""
    for tool in ("konsole", "qdbus6"):
        if not shutil.which(tool):
            sys.exit(f"{tool} not found")
    # `set -m` puts sleep in its own process group. Without it Konsole sees bash (the
    # session's own program) in the foreground, ignores it and closes silently: a false result.
    proc = subprocess.Popen(["konsole", "--separate", "--nofork", "-e", "bash", "-c", "set -m; sleep 900; true"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        service = f"org.kde.konsole-{proc.pid}"
        for _ in range(30):
            time.sleep(0.5)
            r = subprocess.run(["qdbus6", service], capture_output=True, text=True)
            if "/konsole/MainWindow_1" in r.stdout:
                break
        else:
            sys.exit("test window did not appear on D-Bus")
        time.sleep(1)
        try:
            subprocess.run(["qdbus6", service, "/konsole/MainWindow_1", "org.qtproject.Qt.QWidget.close"],
                           capture_output=True, timeout=5)
            print("FAIL: the window closed without a prompt.")
            return 1
        except subprocess.TimeoutExpired:
            print("OK: Konsole asked before closing (the close call blocked on the dialog).")
            return 0
    finally:
        proc.kill()


def cmd_install_watch(_args):
    os.makedirs(os.path.dirname(INSTALL_PATH), exist_ok=True)
    shutil.copy2(os.path.abspath(__file__), INSTALL_PATH)
    os.chmod(INSTALL_PATH, 0o755)
    os.makedirs(UNIT_DIR, exist_ok=True)
    with open(os.path.join(UNIT_DIR, UNIT + ".path"), "w") as fh:
        fh.write("[Unit]\nDescription=Watch konsolerc for suppressed close prompts\n\n"
                 f"[Path]\nPathChanged={KONSOLERC}\nUnit={UNIT}.service\n\n"
                 "[Install]\nWantedBy=default.target\n")
    with open(os.path.join(UNIT_DIR, UNIT + ".service"), "w") as fh:
        fh.write("[Unit]\nDescription=Turn Konsole close prompts back on\n\n"
                 f"[Service]\nType=oneshot\nExecStart={INSTALL_PATH} fix --quiet\n")
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "enable", "--now", UNIT + ".path"], check=True)
    subprocess.run([INSTALL_PATH, "fix", "--quiet"], check=False)
    print(f"Installed {INSTALL_PATH} and {UNIT}.path: konsolerc is checked on every change.")
    return 0


def cmd_uninstall_watch(_args):
    subprocess.run(["systemctl", "--user", "disable", "--now", UNIT + ".path"], check=False)
    for f in (os.path.join(UNIT_DIR, UNIT + ".path"), os.path.join(UNIT_DIR, UNIT + ".service"), INSTALL_PATH):
        if os.path.exists(f):
            os.remove(f)
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    print("Removed the watch.")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("check"); p.add_argument("--json", action="store_true"); p.set_defaults(fn=cmd_check)
    p = sub.add_parser("fix"); p.add_argument("--quiet", action="store_true"); p.set_defaults(fn=cmd_fix)
    sub.add_parser("test").set_defaults(fn=cmd_test)
    sub.add_parser("install-watch").set_defaults(fn=cmd_install_watch)
    sub.add_parser("uninstall-watch").set_defaults(fn=cmd_uninstall_watch)
    args = ap.parse_args()
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
