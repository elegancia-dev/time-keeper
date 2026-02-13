"""Inbox ingestion for time-keeper.

Scans ~/.time-keeper/inbox/ for JSON files, validates them, and inserts
entries into the activity_log table.

Standard inbox format:
{
  "source": "some-app-name",
  "entries": [
    {
      "timestamp": "2026-02-10T07:30:00+00:00",
      "event_type": "work_log",
      "detail": {"task": "...", "project": "...", ...}
    }
  ]
}
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from . import store


INBOX_DIR = store.DB_DIR / "inbox"
PROCESSED_DIR = INBOX_DIR / "processed"


def validate_file(data: dict) -> list[str]:
    """Return a list of validation errors (empty if valid)."""
    errors = []
    if not isinstance(data, dict):
        return ["File must contain a JSON object"]
    if "source" not in data or not isinstance(data["source"], str):
        errors.append("Missing or invalid 'source' field (must be a string)")
    if "entries" not in data or not isinstance(data["entries"], list):
        errors.append("Missing or invalid 'entries' field (must be an array)")
        return errors
    for i, entry in enumerate(data["entries"]):
        if not isinstance(entry, dict):
            errors.append(f"entries[{i}]: must be an object")
            continue
        if "timestamp" not in entry:
            errors.append(f"entries[{i}]: missing 'timestamp'")
        if "event_type" not in entry:
            errors.append(f"entries[{i}]: missing 'event_type'")
    return errors


def ingest_file(conn: sqlite3.Connection, filepath: Path) -> tuple[int, list[str]]:
    """Ingest a single JSON file. Returns (count_inserted, errors)."""
    try:
        with open(filepath) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return 0, [f"Failed to read {filepath.name}: {e}"]

    errors = validate_file(data)
    if errors:
        return 0, errors

    source = data["source"]
    count = 0
    for entry in data["entries"]:
        detail = entry.get("detail")
        if isinstance(detail, dict):
            detail = json.dumps(detail)
        store.log_standalone_activity(
            conn,
            event_type=entry["event_type"],
            detail=detail,
            source=source,
            timestamp=entry.get("timestamp"),
        )
        count += 1

    return count, []


def ingest_all(conn: sqlite3.Connection) -> str:
    """Process all JSON files in the inbox directory."""
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    files = sorted(INBOX_DIR.glob("*.json"))
    if not files:
        return "No files found in inbox."

    total = 0
    results = []
    for filepath in files:
        count, errors = ingest_file(conn, filepath)
        if errors:
            results.append(f"  {filepath.name}: SKIPPED — {'; '.join(errors)}")
        else:
            filepath.rename(PROCESSED_DIR / filepath.name)
            results.append(f"  {filepath.name}: {count} entries ingested")
            total += count

    summary = f"Ingested {total} entries from {len(files)} file(s).\n"
    return summary + "\n".join(results)
