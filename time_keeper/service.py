"""macOS launchd integration: run `tk watch` automatically at login.

Generates a LaunchAgent plist that invokes the watcher via the current
Python interpreter (so it works regardless of PATH, which launchd keeps
minimal). KeepAlive is set to restart only on a crash — a clean exit
(e.g. no repos registered) will not spin in a relaunch loop.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .logrotate import LIVE_LOG, LOG_DIR

LABEL = "dev.elegancia.timekeeper"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
# The watcher writes its own rotating log (LIVE_LOG), so launchd's stdout is
# discarded; stderr captures only startup tracebacks, which are rare.
STDERR_LOG = LOG_DIR / "launchd.err"


def _plist_contents() -> str:
    python = sys.executable
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python}</string>
        <string>-m</string>
        <string>time_keeper.cli</string>
        <string>watch</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>StandardOutPath</key>
    <string>/dev/null</string>
    <key>StandardErrorPath</key>
    <string>{STDERR_LOG}</string>
    <key>WorkingDirectory</key>
    <string>{Path.home()}</string>
</dict>
</plist>
"""


def install() -> str:
    if sys.platform != "darwin":
        return "launchd is macOS-only. On Linux, run `tk watch` under systemd or tmux."
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.write_text(_plist_contents())
    # Reload if already loaded, so reinstall picks up changes.
    subprocess.run(["launchctl", "unload", str(PLIST_PATH)],
                   capture_output=True)
    result = subprocess.run(["launchctl", "load", "-w", str(PLIST_PATH)],
                            capture_output=True, text=True)
    if result.returncode != 0:
        return f"Wrote {PLIST_PATH}\nlaunchctl load failed: {result.stderr.strip()}"
    return (
        f"Installed and started.\n"
        f"  Plist: {PLIST_PATH}\n"
        f"  Logs:  {LIVE_LOG} (rotated monthly into {LOG_DIR / 'archive'})\n"
        f"The watcher now starts at login and tracks your registered repos.\n"
        f"Manage repos with `tk repos add/remove/list`."
    )


def uninstall() -> str:
    if sys.platform != "darwin":
        return "launchd is macOS-only; nothing to uninstall."
    if not PLIST_PATH.exists():
        return "Not installed (no plist found)."
    subprocess.run(["launchctl", "unload", "-w", str(PLIST_PATH)],
                   capture_output=True)
    PLIST_PATH.unlink()
    return f"Uninstalled. Removed {PLIST_PATH}"


def status() -> str:
    if sys.platform != "darwin":
        return "launchd is macOS-only."
    if not PLIST_PATH.exists():
        return "Not installed. Run `tk service install` to auto-start at login."
    result = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
    loaded = any(LABEL in line for line in result.stdout.splitlines())
    state = "loaded and running" if loaded else "installed but not loaded"
    return f"Service {state}.\n  Plist: {PLIST_PATH}\n  Logs:  {LIVE_LOG}"
