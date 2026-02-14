#!/usr/bin/env python3
from __future__ import annotations

"""Generate summary and detailed reports from time-keeper data.

Usage:
    python main.py summary [--since DATE] [--until DATE] [--today] [--week]
    python main.py detail [--since DATE] [--until DATE] [--today] [--week]
    python main.py summary --project NAME
"""

import argparse
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


DB_PATH = Path.home() / ".time-keeper" / "timekeeper.db"


def get_db() -> sqlite3.Connection:
    if not DB_PATH.exists():
        print(f"No database found at {DB_PATH}")
        print("Run sqlite-store to create sessions first.")
        raise SystemExit(1)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def parse_iso(ts: str) -> datetime:
    """Parse an ISO timestamp string."""
    # Handle various ISO formats
    ts = ts.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)


def session_duration_hours(session: dict) -> float:
    """Calculate session duration in hours."""
    start = parse_iso(session["start_time"])
    if session["end_time"]:
        end = parse_iso(session["end_time"])
    else:
        end = datetime.now(timezone.utc)
    delta = (end - start).total_seconds()
    return max(0, delta / 3600)


def format_hours(hours: float) -> str:
    h = int(hours)
    m = int((hours - h) * 60)
    if h:
        return f"{h}h {m}m"
    return f"{m}m"


def query_sessions(conn: sqlite3.Connection, since: str | None = None,
                   until: str | None = None, project: str | None = None) -> list[dict]:
    """Query sessions with optional filters."""
    conditions = []
    params = []

    if since:
        conditions.append("start_time >= ?")
        params.append(since)
    if until:
        conditions.append("start_time <= ?")
        params.append(until + "T23:59:59")
    if project:
        conditions.append("project_name = ?")
        params.append(project)

    where = " AND ".join(conditions) if conditions else "1=1"
    sql = f"SELECT * FROM sessions WHERE {where} ORDER BY start_time"
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def query_activities(conn: sqlite3.Connection, session_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM activity_log WHERE session_id = ? ORDER BY timestamp",
        (session_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def summary_report(sessions: list[dict]) -> str:
    """Generate a summary report grouped by project."""
    if not sessions:
        return "No sessions found for the specified range.\n"

    # Group by project
    projects = {}
    for s in sessions:
        name = s["project_name"]
        if name not in projects:
            projects[name] = {"sessions": [], "total_hours": 0.0}
        hours = session_duration_hours(s)
        projects[name]["sessions"].append(s)
        projects[name]["total_hours"] += hours

    # Date range
    all_starts = [s["start_time"][:10] for s in sessions]
    date_range = f"{min(all_starts)} – {max(all_starts)}"

    lines = ["# Time Summary", f"**Period:** {date_range}", ""]

    grand_total = 0.0
    for name, data in sorted(projects.items()):
        hours = data["total_hours"]
        grand_total += hours
        count = len(data["sessions"])
        lines.append(f"- **{name}** — {format_hours(hours)} ({count} session{'s' if count != 1 else ''})")

    lines.append("")
    lines.append(f"**Total: {format_hours(grand_total)}**")
    lines.append("")
    return "\n".join(lines)


def detail_report(conn: sqlite3.Connection, sessions: list[dict]) -> str:
    """Generate a detailed report with per-session breakdown."""
    if not sessions:
        return "No sessions found for the specified range.\n"

    lines = ["# Detailed Time Report", ""]

    grand_total = 0.0
    for s in sessions:
        hours = session_duration_hours(s)
        grand_total += hours
        end_display = s["end_time"][:19] if s["end_time"] else "ongoing"

        lines.append(f"## [{s['id']}] {s['project_name']}")
        lines.append(f"**Status:** {s['status']}  |  **Duration:** {format_hours(hours)}")
        lines.append(f"**Start:** {s['start_time'][:19]}  →  **End:** {end_display}")
        lines.append(f"**Repo:** {s['repo_path']}")
        lines.append("")

        activities = query_activities(conn, s["id"])
        if activities:
            lines.append("**Activity log:**")
            for a in activities:
                ts = a["timestamp"][:19]
                detail = a["detail"] or ""
                lines.append(f"  - `{ts}` [{a['event_type']}] {detail}")
            lines.append("")

    lines.append(f"---\n**Grand Total: {format_hours(grand_total)}**\n")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate time-keeper reports")
    sub = parser.add_subparsers(dest="command")

    for name in ("summary", "detail"):
        p = sub.add_parser(name, help=f"Generate {name} report")
        p.add_argument("--since", help="Start date (YYYY-MM-DD)")
        p.add_argument("--until", help="End date (YYYY-MM-DD)")
        p.add_argument("--today", action="store_true", help="Today only")
        p.add_argument("--week", action="store_true", help="Past 7 days")
        p.add_argument("--project", help="Filter by project name")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    since = args.since
    until = args.until

    if args.today:
        since = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        until = since
    elif args.week:
        until = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

    conn = get_db()
    sessions = query_sessions(conn, since, until, args.project)

    if args.command == "summary":
        print(summary_report(sessions))
    elif args.command == "detail":
        print(detail_report(conn, sessions))

    conn.close()


if __name__ == "__main__":
    main()
