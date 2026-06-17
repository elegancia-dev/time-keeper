"""Watcher logging with monthly, gzip-compressed rotation.

The watcher owns its own log file (rather than relying on launchd's stdout
redirect, which can't rotate). On the first write of a new calendar month
the previous month's log is compressed into ``logs/archive/watch-YYYY-MM.log.gz``
and the live ``logs/watch.log`` is truncated in place, so a long-running
watcher never accumulates an unbounded log.
"""
from __future__ import annotations

import gzip
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path

LOG_DIR = Path.home() / ".time-keeper" / "logs"
LIVE_LOG = LOG_DIR / "watch.log"
ARCHIVE_DIR = LOG_DIR / "archive"


def _month_of(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m")


class MonthlyRotatingFileHandler(logging.FileHandler):
    """A FileHandler that rolls over (and gzips) at calendar-month boundaries."""

    def __init__(self, filename: Path, archive_dir: Path | None = None):
        self.base_path = Path(filename)
        self.archive_dir = Path(archive_dir) if archive_dir else self.base_path.parent / "archive"
        self.base_path.parent.mkdir(parents=True, exist_ok=True)
        self._period = self._existing_period()
        super().__init__(str(self.base_path), mode="a", encoding="utf-8")

    def _now_period(self) -> str:
        return datetime.now().strftime("%Y-%m")

    def _existing_period(self) -> str:
        """Month the current live log belongs to, by its creation time."""
        if self.base_path.exists() and self.base_path.stat().st_size > 0:
            st = self.base_path.stat()
            birth = getattr(st, "st_birthtime", st.st_mtime)
            return _month_of(birth)
        return self._now_period()

    def emit(self, record):
        try:
            if self._now_period() != self._period:
                self._rotate()
        except Exception:
            self.handleError(record)
        super().emit(record)

    def _rotate(self) -> None:
        self.acquire()
        try:
            if self.stream:
                self.stream.close()
                self.stream = None
            if self.base_path.exists() and self.base_path.stat().st_size > 0:
                self.archive_dir.mkdir(parents=True, exist_ok=True)
                archive = self.archive_dir / f"{self.base_path.stem}-{self._period}.log.gz"
                # Append in case this month was already partially archived.
                with open(self.base_path, "rb") as src, gzip.open(archive, "ab") as dst:
                    shutil.copyfileobj(src, dst)
                # Truncate in place so the live path/handle stays stable.
                open(self.base_path, "w").close()
            self._period = self._now_period()
            self.stream = self._open()
        finally:
            self.release()


_LOGGER: logging.Logger | None = None


def get_logger() -> logging.Logger:
    """Logger that writes to the console and to the rotating watch.log."""
    global _LOGGER
    if _LOGGER is not None:
        return _LOGGER

    logger = logging.getLogger("time_keeper.watch")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        fmt = logging.Formatter("[%(asctime)s] %(message)s", "%Y-%m-%d %H:%M:%S")
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(fmt)
        logger.addHandler(console)
        try:
            file_handler = MonthlyRotatingFileHandler(LIVE_LOG, ARCHIVE_DIR)
            file_handler.setFormatter(fmt)
            logger.addHandler(file_handler)
        except OSError:
            # If the log file can't be opened, keep console logging only.
            pass

    _LOGGER = logger
    return logger
