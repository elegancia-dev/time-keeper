#!/usr/bin/env python3
from __future__ import annotations

"""SQLite store for time-keeper sessions and activity logs.

Usage:
    python main.py create-session /path/to/repo [--project NAME]
    python main.py stop-session SESSION_ID
    python main.py list-sessions [--status STATUS]
    python main.py log-activity SESSION_ID EVENT_TYPE [DETAIL]
    python main.py show-session SESSION_ID
"""

import argparse
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


DB_DIR = Path.home() / ".time-keeper"
DB_PATH = DB_DIR / "timekeeper.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_path TEXT NOT NULL,
    project_name TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT,
    status TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    detail TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);
"""


def get_db(db_path: Path | None = None) -> sqlite3.Connection:
    """Open (and initialize if needed) the database."""
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_session(conn: sqlite3.Connection, repo_path: str, project_name: str | None = None) -> int:
    """Create a new active session. Returns the session id."""
    repo = os.path.abspath(repo_path)
    project = project_name or os.path.basename(repo)
    cur = conn.execute(
        "INSERT INTO sessions (repo_path, project_name, start_time, status) VALUES (?, ?, ?, 'active')",
        (repo, project, now_iso()),
    )
    conn.commit()
    session_id = cur.lastrowid
    log_activity(conn, session_id, "session_start", f"Started session for {project}")
    return session_id


def stop_session(conn: sqlite3.Connection, session_id: int) -> bool:
    """Stop an active session. Returns True if session was found and stopped."""
    row = conn.execute("SELECT status FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if not row:
        return False
    if row["status"] != "active":
        return False
    conn.execute(
        "UPDATE sessions SET end_time = ?, status = 'stopped' WHERE id = ?",
        (now_iso(), session_id),
    )
    conn.commit()
    log_activity(conn, session_id, "session_stop", "Session stopped")
    return True


def list_sessions(conn: sqlite3.Connection, status: str | None = None) -> list[dict]:
    """List sessions, optionally filtered by status."""
    if status:
        rows = conn.execute("SELECT * FROM sessions WHERE status = ? ORDER BY start_time DESC", (status,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM sessions ORDER BY start_time DESC").fetchall()
    return [dict(r) for r in rows]


def get_session(conn: sqlite3.Connection, session_id: int) -> dict | None:
    """Get a single session with its activity log."""
    row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if not row:
        return None
    session = dict(row)
    activities = conn.execute(
        "SELECT * FROM activity_log WHERE session_id = ? ORDER BY timestamp", (session_id,)
    ).fetchall()
    session["activities"] = [dict(a) for a in activities]
    return session


def log_activity(conn: sqlite3.Connection, session_id: int, event_type: str, detail: str | None = None) -> int:
    """Log an activity event for a session."""
    cur = conn.execute(
        "INSERT INTO activity_log (session_id, timestamp, event_type, detail) VALUES (?, ?, ?, ?)",
        (session_id, now_iso(), event_type, detail),
    )
    conn.commit()
    return cur.lastrowid


def format_session(s: dict) -> str:
    """Format a session dict for display."""
    end = s["end_time"] or "—"
    return f"[{s['id']}] {s['project_name']}  {s['status']}  {s['start_time']} → {end}  ({s['repo_path']})"


def main():
    parser = argparse.ArgumentParser(description="SQLite store for time-keeper")
    sub = parser.add_subparsers(dest="command")

    p_create = sub.add_parser("create-session", help="Create a new session")
    p_create.add_argument("repo_path", help="Path to the repo")
    p_create.add_argument("--project", help="Project name (defaults to repo dir name)")

    p_stop = sub.add_parser("stop-session", help="Stop an active session")
    p_stop.add_argument("session_id", type=int, help="Session ID to stop")

    p_list = sub.add_parser("list-sessions", help="List sessions")
    p_list.add_argument("--status", help="Filter by status (active/stopped)")

    p_show = sub.add_parser("show-session", help="Show session details")
    p_show.add_argument("session_id", type=int, help="Session ID")

    p_log = sub.add_parser("log-activity", help="Log an activity event")
    p_log.add_argument("session_id", type=int, help="Session ID")
    p_log.add_argument("event_type", help="Event type (e.g., file_modified, commit)")
    p_log.add_argument("detail", nargs="?", help="Event detail")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    conn = get_db()

    if args.command == "create-session":
        sid = create_session(conn, args.repo_path, args.project)
        print(f"Created session {sid}")

    elif args.command == "stop-session":
        if stop_session(conn, args.session_id):
            print(f"Stopped session {args.session_id}")
        else:
            print(f"Session {args.session_id} not found or not active")

    elif args.command == "list-sessions":
        sessions = list_sessions(conn, args.status)
        if not sessions:
            print("No sessions found")
        for s in sessions:
            print(format_session(s))

    elif args.command == "show-session":
        session = get_session(conn, args.session_id)
        if not session:
            print(f"Session {args.session_id} not found")
            return
        print(format_session(session))
        for a in session.get("activities", []):
            print(f"  {a['timestamp']} [{a['event_type']}] {a['detail'] or ''}")

    elif args.command == "log-activity":
        aid = log_activity(conn, args.session_id, args.event_type, args.detail)
        print(f"Logged activity {aid}")

    conn.close()


if __name__ == "__main__":
    main()
