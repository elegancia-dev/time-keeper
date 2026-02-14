#!/usr/bin/env python3
from __future__ import annotations

"""File system watcher that prints timestamped change events.

Usage:
    python main.py /path/to/watch [--ignore PATTERN ...]
"""

import argparse
import fnmatch
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from watchdog.events import FileSystemEventHandler, FileSystemEvent
from watchdog.observers import Observer


DEFAULT_IGNORE = [
    ".git/*",
    "__pycache__/*",
    "node_modules/*",
    "*.pyc",
    ".DS_Store",
    "*.swp",
    "*.swo",
    "*~",
]


class EventPrinter(FileSystemEventHandler):
    """Prints timestamped file system events, filtering ignored patterns."""

    def __init__(self, ignore_patterns: list[str], callback=None):
        self.ignore_patterns = ignore_patterns
        self.callback = callback

    def _should_ignore(self, path: str) -> bool:
        for pattern in self.ignore_patterns:
            if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(Path(path).name, pattern):
                # Also check if any path component matches directory patterns
                parts = Path(path).parts
                for part in parts:
                    if fnmatch.fnmatch(part, pattern.rstrip("/*")):
                        return True
        return False

    def on_any_event(self, event: FileSystemEvent):
        if event.is_directory:
            return
        if self._should_ignore(event.src_path):
            return

        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        event_type = event.event_type.upper()
        print(f"{ts} {event_type} {event.src_path}", flush=True)

        if self.callback:
            self.callback(event)


def watch(path: str, ignore_patterns: list[str] | None = None, callback=None) -> Observer:
    """Start watching a directory. Returns the Observer (call .stop() to end)."""
    patterns = ignore_patterns if ignore_patterns is not None else DEFAULT_IGNORE
    handler = EventPrinter(patterns, callback=callback)
    observer = Observer()
    observer.schedule(handler, path, recursive=True)
    observer.start()
    return observer


def main():
    parser = argparse.ArgumentParser(description="Watch a directory for file changes")
    parser.add_argument("path", nargs="?", default=".", help="Directory to watch (default: .)")
    parser.add_argument("--ignore", nargs="*", default=None, help="Additional ignore patterns")
    args = parser.parse_args()

    watch_path = str(Path(args.path).resolve())
    ignore = list(DEFAULT_IGNORE)
    if args.ignore:
        ignore.extend(args.ignore)

    print(f"Watching {watch_path} for changes... (Ctrl+C to stop)")
    observer = watch(watch_path, ignore)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
    print("\nStopped watching.")


if __name__ == "__main__":
    main()
