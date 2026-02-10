#!/usr/bin/env python3
from __future__ import annotations

"""Active tracker daemon: watches a repo, auto-starts sessions, handles idle timeout.

Combines: file-watcher + session-timer + sqlite-store

Usage:
    python main.py /path/to/repo [--idle-timeout MINUTES] [--project NAME]
"""

import argparse
import importlib.util
import os
import signal
import time
from datetime import datetime, timezone
from pathlib import Path


def _load_module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


BASE = Path(__file__).resolve().parent.parent.parent / "apps"
store = _load_module("store", str(BASE / "sqlite-store" / "main.py"))
watcher = _load_module("watcher", str(BASE / "file-watcher" / "main.py"))


class ActiveTracker:
    def __init__(self, repo_path: str, idle_timeout_min: int = 15, project_name: str | None = None):
        self.repo_path = os.path.abspath(repo_path)
        self.idle_timeout_min = idle_timeout_min
        self.project_name = project_name or os.path.basename(self.repo_path)
        self.conn = store.get_db()
        self.session_id = None
        self.last_activity_ts = 0.0
        self.paused = False

    def _on_file_event(self, event):
        """Callback from file watcher."""
        now = time.time()
        self.last_activity_ts = now

        if self.session_id is None:
            # Auto-start session on first activity
            self.session_id = store.create_session(self.conn, self.repo_path, self.project_name)
            self.paused = False
            ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
            print(f"  [{ts}] Session {self.session_id} auto-started")

        if self.paused:
            # Resume from idle
            self.paused = False
            store.log_activity(self.conn, self.session_id, "session_resume", "Resumed from idle")
            ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
            print(f"  [{ts}] Session resumed from idle")

        # Log the file event (resolve symlinks for correct relpath)
        src = os.path.realpath(event.src_path)
        repo = os.path.realpath(self.repo_path)
        rel_path = os.path.relpath(src, repo)
        store.log_activity(
            self.conn, self.session_id, "file_" + event.event_type,
            rel_path,
        )

    def _check_idle(self):
        """Check if we should auto-pause due to idle."""
        if self.session_id is None or self.paused:
            return

        idle_seconds = time.time() - self.last_activity_ts
        if idle_seconds > self.idle_timeout_min * 60:
            self.paused = True
            store.log_activity(
                self.conn, self.session_id, "session_pause",
                f"Auto-paused after {self.idle_timeout_min}m idle",
            )
            ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
            print(f"  [{ts}] Session paused (idle for {self.idle_timeout_min}m)")

    def _shutdown(self, observer):
        """Clean shutdown: stop observer and session."""
        observer.stop()
        observer.join()

        if self.session_id:
            store.stop_session(self.conn, self.session_id)
            print(f"\n  Session {self.session_id} stopped")
        else:
            print("\n  No session was started (no file changes detected)")

        self.conn.close()

    def run(self):
        """Run the tracker until Ctrl+C or SIGTERM."""
        print(f"Active Tracker watching: {self.repo_path}")
        print(f"  Project: {self.project_name}")
        print(f"  Idle timeout: {self.idle_timeout_min} minutes")
        print(f"  Waiting for file changes to auto-start session...")
        print()

        observer = watcher.watch(self.repo_path, callback=self._on_file_event)
        running = True

        def handle_signal(signum, frame):
            nonlocal running
            running = False

        signal.signal(signal.SIGTERM, handle_signal)

        try:
            while running:
                time.sleep(1)
                self._check_idle()
        except KeyboardInterrupt:
            pass

        self._shutdown(observer)


def main():
    parser = argparse.ArgumentParser(description="Active tracker: auto-detect work sessions via file watching")
    parser.add_argument("repo", nargs="?", default=".", help="Repository path to watch (default: .)")
    parser.add_argument("--idle-timeout", type=int, default=15, help="Idle timeout in minutes (default: 15)")
    parser.add_argument("--project", help="Project name (defaults to repo dir name)")
    args = parser.parse_args()

    tracker = ActiveTracker(args.repo, args.idle_timeout, args.project)
    tracker.run()


if __name__ == "__main__":
    main()
