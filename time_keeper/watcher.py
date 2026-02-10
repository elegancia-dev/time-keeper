"""File system watcher for detecting work activity."""
from __future__ import annotations

import fnmatch
import os
import signal
import time
from datetime import datetime, timezone
from pathlib import Path

from watchdog.events import FileSystemEventHandler, FileSystemEvent
from watchdog.observers import Observer

from . import store


DEFAULT_IGNORE = [
    ".git/*", "__pycache__/*", "node_modules/*", "*.pyc",
    ".DS_Store", "*.swp", "*.swo", "*~",
]


class ActivityHandler(FileSystemEventHandler):
    def __init__(self, repo_path: str, ignore_patterns: list[str], tracker):
        self.repo_path = os.path.realpath(repo_path)
        self.ignore_patterns = ignore_patterns
        self.tracker = tracker

    def _should_ignore(self, path: str) -> bool:
        for pattern in self.ignore_patterns:
            if fnmatch.fnmatch(Path(path).name, pattern):
                return True
            for part in Path(path).parts:
                if fnmatch.fnmatch(part, pattern.rstrip("/*")):
                    return True
        return False

    def on_any_event(self, event: FileSystemEvent):
        if event.is_directory:
            return
        if self._should_ignore(event.src_path):
            return
        self.tracker.on_file_event(event)


class WatchTracker:
    def __init__(self, repo_path: str, idle_timeout_min: int = 15, project_name: str | None = None):
        self.repo_path = os.path.abspath(repo_path)
        self.idle_timeout_min = idle_timeout_min
        self.project_name = project_name or os.path.basename(self.repo_path)
        self.conn = store.get_db()
        self.session_id = None
        self.last_activity_ts = 0.0
        self.paused = False

    def on_file_event(self, event):
        now = time.time()
        self.last_activity_ts = now

        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")

        if self.session_id is None:
            self.session_id = store.create_session(self.conn, self.repo_path, self.project_name)
            self.paused = False
            print(f"  [{ts}] Session {self.session_id} auto-started")

        if self.paused:
            self.paused = False
            store.log_activity(self.conn, self.session_id, "session_resume", "Resumed from idle")
            print(f"  [{ts}] Session resumed from idle")

        src = os.path.realpath(event.src_path)
        repo = os.path.realpath(self.repo_path)
        rel_path = os.path.relpath(src, repo)
        store.log_activity(self.conn, self.session_id, "file_" + event.event_type, rel_path)

    def check_idle(self):
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

    def run(self):
        print(f"Watching: {self.repo_path}")
        print(f"  Project: {self.project_name}")
        print(f"  Idle timeout: {self.idle_timeout_min} minutes")
        print(f"  Waiting for file changes...")
        print()

        handler = ActivityHandler(self.repo_path, DEFAULT_IGNORE, self)
        observer = Observer()
        observer.schedule(handler, self.repo_path, recursive=True)
        observer.start()

        running = True

        def handle_signal(signum, frame):
            nonlocal running
            running = False

        signal.signal(signal.SIGTERM, handle_signal)

        try:
            while running:
                time.sleep(1)
                self.check_idle()
        except KeyboardInterrupt:
            pass

        observer.stop()
        observer.join()

        if self.session_id:
            store.stop_session(self.conn, self.session_id)
            print(f"\n  Session {self.session_id} stopped")
        else:
            print("\n  No session was started (no file changes detected)")

        self.conn.close()
