#!/usr/bin/env python3
from __future__ import annotations

"""Session timer with start/stop/status and idle timeout.

Usage:
    python main.py start [--repo PATH] [--idle-timeout MINUTES]
    python main.py stop
    python main.py status
    python main.py touch   # Record activity (resets idle timer)
"""

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path


STATE_DIR = Path.home() / ".time-keeper"
STATE_FILE = STATE_DIR / "session-timer-state.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def now_ts() -> float:
    return time.time()


def load_state() -> dict | None:
    if not STATE_FILE.exists():
        return None
    with open(STATE_FILE) as f:
        return json.load(f)


def save_state(state: dict):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def clear_state():
    if STATE_FILE.exists():
        STATE_FILE.unlink()


def format_duration(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def start_session(repo: str, idle_timeout_min: int):
    state = load_state()
    if state and state.get("status") == "active":
        print(f"Session already active for {state['repo']} (started {state['start_time']})")
        return

    state = {
        "repo": os.path.abspath(repo),
        "start_time": now_iso(),
        "start_ts": now_ts(),
        "last_activity_ts": now_ts(),
        "idle_timeout_min": idle_timeout_min,
        "status": "active",
        "paused_duration": 0.0,
        "pause_start_ts": None,
    }
    save_state(state)
    print(f"Session started for {state['repo']}")
    print(f"  Idle timeout: {idle_timeout_min} minutes")


def stop_session():
    state = load_state()
    if not state or state["status"] == "stopped":
        print("No active session")
        return

    elapsed = _elapsed(state)
    state["status"] = "stopped"
    state["end_time"] = now_iso()
    save_state(state)
    clear_state()

    print(f"Session stopped for {state['repo']}")
    print(f"  Duration: {format_duration(elapsed)}")


def _elapsed(state: dict) -> float:
    """Calculate active (non-paused) elapsed time."""
    if state["status"] == "stopped":
        return 0.0

    total = now_ts() - state["start_ts"]
    paused = state.get("paused_duration", 0.0)

    if state.get("pause_start_ts"):
        paused += now_ts() - state["pause_start_ts"]

    return max(0, total - paused)


def check_idle(state: dict) -> dict:
    """Check if session should be paused due to idle. Returns updated state."""
    if state["status"] != "active":
        return state

    idle_seconds = now_ts() - state["last_activity_ts"]
    timeout_seconds = state["idle_timeout_min"] * 60

    if state.get("pause_start_ts") is None and idle_seconds > timeout_seconds:
        # Auto-pause
        state["pause_start_ts"] = state["last_activity_ts"] + timeout_seconds
        state["status"] = "paused"
        save_state(state)

    return state


def touch_activity():
    """Record activity - resets idle timer and resumes if paused."""
    state = load_state()
    if not state:
        print("No session to update")
        return

    if state.get("pause_start_ts"):
        # Resume from pause
        state["paused_duration"] = state.get("paused_duration", 0.0) + (now_ts() - state["pause_start_ts"])
        state["pause_start_ts"] = None
        state["status"] = "active"

    state["last_activity_ts"] = now_ts()
    save_state(state)


def show_status():
    state = load_state()
    if not state:
        print("No active session")
        return

    state = check_idle(state)
    elapsed = _elapsed(state)
    idle_seconds = now_ts() - state["last_activity_ts"]

    print(f"Repo:     {state['repo']}")
    print(f"Status:   {state['status']}")
    print(f"Started:  {state['start_time']}")
    print(f"Elapsed:  {format_duration(elapsed)}")
    print(f"Idle:     {format_duration(idle_seconds)}")
    if state["status"] == "paused":
        print(f"  (paused — idle timeout of {state['idle_timeout_min']}m exceeded)")


def main():
    parser = argparse.ArgumentParser(description="Session timer with idle timeout")
    sub = parser.add_subparsers(dest="command")

    p_start = sub.add_parser("start", help="Start a new session")
    p_start.add_argument("--repo", default=".", help="Repository path (default: .)")
    p_start.add_argument("--idle-timeout", type=int, default=15, help="Idle timeout in minutes (default: 15)")

    sub.add_parser("stop", help="Stop the current session")
    sub.add_parser("status", help="Show current session status")
    sub.add_parser("touch", help="Record activity (resets idle timer)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == "start":
        start_session(args.repo, args.idle_timeout)
    elif args.command == "stop":
        stop_session()
    elif args.command == "status":
        show_status()
    elif args.command == "touch":
        touch_activity()


if __name__ == "__main__":
    main()
