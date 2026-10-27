---
name: install-on-lan-host
description: Install Session Restore and the Konsole close guard on other Linux machines on the network over SSH, one or several. Use on "put this on my desktop", "install on the other laptop", "set it up on <host>".
---

# Install on other machines over SSH

The user names the machines, as SSH aliases or `user@host`. Do each one in turn, and
report per host. Nothing here needs root.

## Steps (per host `H`)

1. **Reach it:** `ssh -o BatchMode=yes -o ConnectTimeout=5 H true`. If that fails, report
   the host as unreachable and move on. Run remote commands through a login shell
   (`ssh H 'bash -lc "…"'`) so `~/.local/bin/claude` is on the PATH.
2. **Requirements:** `command -v claude konsole python3 systemctl` on H. Without
   `claude`, stop for that host and say so. Installing Claude Code is the user's call.
3. **Plugin:**
   ```bash
   ssh H 'bash -lc "claude plugin marketplace list | grep -q danielrosehill/Claude-Code-Plugins || claude plugin marketplace add danielrosehill/Claude-Code-Plugins;
                    claude plugin marketplace update danielrosehill;
                    claude plugin install session-restore@danielrosehill || claude plugin update session-restore@danielrosehill"'
   ```
   If `marketplace add` fails with "its source doesn't match its extraKnownMarketplaces
   entry", then H's `~/.claude/settings.json` has an old `extraKnownMarketplaces.danielrosehill`
   entry. Seen 2026-10-27: a `directory` source at a path that no longer existed, so the
   marketplace never updated and `install` said "not found in marketplace". Back up
   settings.json, set the entry's source to
   `{"source": "github", "repo": "danielrosehill/Claude-Code-Plugins"}`, then rerun step 3.
4. **Close guard:** run the installed copy on H:
   ```bash
   ssh H 'P=$(ls -d ~/.claude/plugins/cache/*/session-restore/*/ | sort -V | tail -1);
          python3 "$P/scripts/konsole_close_guard.py" check;
          python3 "$P/scripts/konsole_close_guard.py" fix;
          XDG_RUNTIME_DIR=/run/user/$(id -u) python3 "$P/scripts/konsole_close_guard.py" install-watch;
          python3 "$P/scripts/konsole_close_guard.py" check --json'
   ```
   `XDG_RUNTIME_DIR` lets `systemctl --user` reach the user's systemd over SSH. If the user
   isn't logged in on H, install-watch fails on `systemctl`. Report that, and the `fix`
   still stands.
5. **Don't run `test` over SSH.** It opens a window on that machine's screen, in front of
   whoever is using it.
6. Report per host: plugin version, whether prompts were suppressed and are now on, the
   watch state, and the pids from `check` of Konsole windows that need reopening there.
