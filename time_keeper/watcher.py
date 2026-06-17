"""File system watcher for detecting work activity.

A single process can watch many repos at once (see MultiWatcher). To stay
safe with SQLite, all database writes happen on the main loop thread:
watchdog's observer threads only append events to an in-memory buffer, and
the main loop flushes those buffers in batches on each tick.
"""
from __future__ import annotations

import fnmatch
import os
import signal
import threading
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler, FileSystemEvent
from watchdog.observers import Observer

from . import store
from .logrotate import get_logger

log = get_logger()


DEFAULT_IGNORE = [
    ".git/*", "__pycache__/*", "node_modules/*", "*.pyc",
    ".DS_Store", "*.swp", "*.swo", "*~",
    ".next/*", "dist/*", "build/*", "target/*", ".turbo/*",
    "coverage/*", ".pytest_cache/*", ".mypy_cache/*", ".ruff_cache/*",
    "*.min.js", "*.map", ".sass-cache/*",
]

# How often the main loop flushes buffered events and checks for idle repos.
TICK_SECONDS = 1


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


class RepoTracker:
    """Per-repo session state. Buffers events from the observer thread;
    all DB access happens via flush()/check_idle() on the main thread."""

    def __init__(self, repo_path: str, project_name: str, idle_timeout_min: int):
        self.repo_path = os.path.realpath(repo_path)
        self.project_name = project_name or os.path.basename(self.repo_path)
        self.idle_timeout_min = idle_timeout_min
        self.session_id: int | None = None
        self.last_activity_ts = 0.0
        self._lock = threading.Lock()
        self._buffer: list[tuple[str, str, str]] = []  # (ts_iso, event_type, rel_path)

    # --- observer thread ---
    def on_file_event(self, event):
        try:
            rel_path = os.path.relpath(
                os.path.realpath(event.src_path), self.repo_path
            )
        except ValueError:  # different drive on Windows; fall back to raw path
            rel_path = event.src_path
        ts = store.now_iso()
        with self._lock:
            self._buffer.append((ts, "file_" + event.event_type, rel_path))
            self.last_activity_ts = time.time()

    # --- main thread ---
    def flush(self, conn) -> None:
        with self._lock:
            if not self._buffer:
                return
            pending = self._buffer
            self._buffer = []

        if self.session_id is None:
            self.session_id = store.create_session(
                conn, self.repo_path, self.project_name
            )
            log.info(f"Session {self.session_id} auto-started ({self.project_name})")

        rows = [
            (self.session_id, ts, event_type, detail)
            for (ts, event_type, detail) in pending
        ]
        store.log_activities_batch(conn, rows)

    def check_idle(self, conn) -> None:
        if self.session_id is None:
            return
        if time.time() - self.last_activity_ts > self.idle_timeout_min * 60:
            store.stop_session(conn, self.session_id)
            log.info(
                f"Session {self.session_id} stopped "
                f"({self.project_name}, idle {self.idle_timeout_min}m)"
            )
            self.session_id = None

    def shutdown(self, conn) -> None:
        self.flush(conn)
        if self.session_id is not None:
            store.stop_session(conn, self.session_id)
            log.info(f"Session {self.session_id} stopped ({self.project_name})")
            self.session_id = None


class MultiWatcher:
    """Watch one or more repos in a single process."""

    def __init__(self, repos: list[dict], idle_timeout_min: int = 15):
        # repos: list of {"path": str, "project": str | None}
        self.idle_timeout_min = idle_timeout_min
        self.trackers = [
            RepoTracker(r["path"], r.get("project"), idle_timeout_min)
            for r in repos
        ]

    def run(self) -> None:
        conn = store.get_db()

        warning = store.check_db_size()
        if warning:
            log.warning(warning)

        names = ", ".join(t.project_name for t in self.trackers)
        log.info(
            f"Watching {len(self.trackers)} repo(s) "
            f"(idle timeout: {self.idle_timeout_min}m): {names}"
        )

        observer = Observer()
        for t in self.trackers:
            handler = ActivityHandler(t.repo_path, DEFAULT_IGNORE, t)
            observer.schedule(handler, t.repo_path, recursive=True)
        observer.start()

        running = True

        def handle_signal(signum, frame):
            nonlocal running
            running = False

        signal.signal(signal.SIGTERM, handle_signal)

        try:
            while running:
                time.sleep(TICK_SECONDS)
                for t in self.trackers:
                    t.flush(conn)
                    t.check_idle(conn)
        except KeyboardInterrupt:
            pass

        observer.stop()
        observer.join()

        for t in self.trackers:
            t.shutdown(conn)
        conn.close()
        log.info("Watcher stopped.")
