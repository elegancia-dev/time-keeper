#!/usr/bin/env python3
"""Chrome native messaging host for Work Logger → time-keeper SQLite bridge.

Chrome launches this as a subprocess. Communication uses Chrome's native messaging
protocol: 4-byte little-endian length prefix + JSON on stdin/stdout.
"""

import json
import struct
import sys
from pathlib import Path

# Add time_keeper package to path so we can import store
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from time_keeper import store

SETTINGS_PATH = Path.home() / ".time-keeper" / "work-logger-settings.json"

DEFAULT_SETTINGS = {
    "domains": [
        "instagram.com",
        "reddit.com",
        "twitter.com",
        "x.com",
        "facebook.com",
        "tiktok.com",
        "youtube.com",
    ],
    "cooldown_seconds": 30,
}


def read_message():
    """Read a native messaging message from stdin."""
    raw_length = sys.stdin.buffer.read(4)
    if len(raw_length) < 4:
        return None
    length = struct.unpack("<I", raw_length)[0]
    data = sys.stdin.buffer.read(length)
    return json.loads(data)


def send_message(obj):
    """Write a native messaging message to stdout."""
    encoded = json.dumps(obj).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("<I", len(encoded)))
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


def load_settings():
    if SETTINGS_PATH.exists():
        with open(SETTINGS_PATH) as f:
            return json.load(f)
    return dict(DEFAULT_SETTINGS)


def save_settings(settings):
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)


def handle_add_log(conn, msg):
    detail = json.dumps({
        "task": msg.get("task", ""),
        "project": msg.get("project"),
        "duration_estimate": msg.get("duration_estimate"),
        "triggered_by": msg.get("triggered_by"),
        "triggered_url": msg.get("triggered_url"),
    })
    row_id = store.log_standalone_activity(
        conn,
        event_type="work_log",
        detail=detail,
        source="work-logger-extension",
    )
    return {"ok": True, "id": row_id}


def handle_get_logs(conn, msg):
    limit = msg.get("limit")
    since = msg.get("since")
    rows = store.get_activities_by_source(
        conn, "work-logger-extension", since=since, limit=limit
    )
    logs = []
    for r in rows:
        entry = {"id": r["id"], "timestamp": r["timestamp"], "event_type": r["event_type"]}
        if r["detail"]:
            try:
                entry.update(json.loads(r["detail"]))
            except (json.JSONDecodeError, TypeError):
                entry["detail"] = r["detail"]
        logs.append(entry)
    return {"ok": True, "logs": logs}


def handle_get_projects(conn, _msg):
    projects = store.get_projects_list(conn)
    return {"ok": True, "projects": projects}


def handle_get_settings(_conn, _msg):
    settings = load_settings()
    return {"ok": True, "domains": settings["domains"], "cooldown_seconds": settings["cooldown_seconds"]}


def handle_save_settings(_conn, msg):
    settings = load_settings()
    if "domains" in msg:
        settings["domains"] = msg["domains"]
    if "cooldown_seconds" in msg:
        settings["cooldown_seconds"] = msg["cooldown_seconds"]
    save_settings(settings)
    return {"ok": True}


HANDLERS = {
    "add_log": handle_add_log,
    "get_logs": handle_get_logs,
    "get_projects": handle_get_projects,
    "get_settings": handle_get_settings,
    "save_settings": handle_save_settings,
}


def main():
    conn = store.get_db()
    try:
        while True:
            msg = read_message()
            if msg is None:
                break
            action = msg.get("action", "")
            handler = HANDLERS.get(action)
            if handler:
                try:
                    response = handler(conn, msg)
                except Exception as e:
                    response = {"ok": False, "error": str(e)}
            else:
                response = {"ok": False, "error": f"Unknown action: {action}"}
            send_message(response)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
