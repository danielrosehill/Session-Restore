# 2026-10-28: KWin crash from a hand-sent ConfigChanged signal, Konsole died 13 minutes later

Host: a laptop, Ubuntu (kernel 7.0.0-38), Plasma 6.6.6 Wayland (kwin 4:6.6.6-0ubuntu0.1),
Konsole 25.12.3, Qt 6.10.2, AMD Lucienne GPU. Two Claude Code sessions lost; restored with
`session_restore.py restore`.

## Timeline (IST)

- 16:36:12.742: Claude Code session `186d17ad` (adjusting night colour) ran
  `dbus-send --session --type=signal /kwinrc org.kde.kconfig.notify.ConfigChanged 'dict:string:string:"NightColor","DayTemperature"'`.
- 16:36:12.979: `kwin_wayland` (pid 6594) KCrash, SIGSEGV. Stack: `QDBusMetaType::demarshall`
  → KF6ConfigCore → `QDBusArgument::beginArray` → libdbus. kded6 crashed at 16:36:16 too.
- KWin restarted; Konsole pid 18255 survived and looked normal.
- 16:49:48: Konsole 18255 SIGSEGV on a tool-button mouse press → expose → `QWaylandShmBackingStore::beginPaint`
  → `recreateBackBufferIfNeeded` → `QImage::sizeInBytes`. Process had a 3.6 GB memory peak.

## Cause

Confirmed: KConfigWatcher's payload is `a{saay}` (captured with `dbus-monitor` while running
`kwriteconfig6 --file srtestrc --group G --key K 1 --notify`: dict entry string → array of
byte arrays). `dict:string:string` sends `a{ss}`. KWin's stack is in exactly that unpacking.
Inferred from timing (0.24 s) and the stack: that signal crashed KWin. Not reproduced, since
reproducing would crash the live desktop.

Inferred: the Konsole crash is the known Qt Wayland aftermath of a compositor restart (stale
shm buffer state in windows that outlived the old compositor). Not reproduced.

## Ruled out

- Hebrish dictation pasted 69 chars at 16:36:11.588, 1.4 s before. Its Linux paste path
  (`/usr/lib/hebrish/hebrish/inserter_linux.py`: wl-copy/xclip + uinput chord) sends no
  KConfig signals and the stack is in KConfig D-Bus handling, not input or clipboard.
- Suppressed close prompts (the 2026-10-27 cause): there is a Konsole core dump this time.

## Prevention (0.4.0)

`scripts/compositor_guard.py` + `hooks/hooks.json`: PreToolUse hook blocks hand-sent
`kconfig.notify` signals and KWin restarts. `install-watch` adds `kwin-crash-watch.service`,
a critical desktop notification on any KWin crash so at-risk Konsole windows can be emptied first.
