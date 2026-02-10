"""Report generation for time-keeper."""
from __future__ import annotations

from datetime import datetime, timezone

from . import store, git, claude


def parse_iso(ts: str) -> datetime:
    ts = ts.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)


def session_duration_hours(session: dict) -> float:
    start = parse_iso(session["start_time"])
    end = parse_iso(session["end_time"]) if session["end_time"] else datetime.now(timezone.utc)
    return max(0, (end - start).total_seconds() / 3600)


def format_hours(hours: float) -> str:
    h = int(hours)
    m = int((hours - h) * 60)
    if h:
        return f"{h}h {m}m"
    return f"{m}m"


def summary_report(conn, since: str | None = None, until: str | None = None,
                   project: str | None = None) -> str:
    sessions = store.query_sessions(conn, since, until, project)
    if not sessions:
        return "No sessions found for the specified range.\n"

    projects = {}
    for s in sessions:
        name = s["project_name"]
        if name not in projects:
            projects[name] = {"sessions": [], "total_hours": 0.0}
        hours = session_duration_hours(s)
        projects[name]["sessions"].append(s)
        projects[name]["total_hours"] += hours

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


def detail_report(conn, since: str | None = None, until: str | None = None,
                  project: str | None = None) -> str:
    sessions = store.query_sessions(conn, since, until, project)
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

        # Activity log
        activities = store.query_activities(conn, s["id"])
        if activities:
            lines.append("**Activity:**")
            for a in activities:
                ts = a["timestamp"][:19]
                detail = a["detail"] or ""
                lines.append(f"  - `{ts}` [{a['event_type']}] {detail}")
            lines.append("")

        # Git commits
        repo = s["repo_path"]
        since_date = s["start_time"][:10]
        until_date = (s["end_time"] or s["start_time"])[:10]
        commits = git.git_log(repo, since=since_date, until=until_date + "T23:59:59")
        if commits:
            lines.append(f"**Git Commits ({len(commits)}):**")
            lines.append(git.format_markdown(repo, commits))

        # Claude conversations
        project_dirs = claude.find_project_dirs(repo)
        for pdir in project_dirs:
            claude_sessions = []
            for f in sorted(pdir.glob("*.jsonl")):
                parsed = claude.parse_session(f)
                if parsed.get("first_timestamp") and parsed.get("last_timestamp"):
                    start = s["start_time"][:19]
                    end = s["end_time"][:19] if s["end_time"] else datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
                    if parsed["last_timestamp"] >= start and parsed["first_timestamp"] <= end:
                        claude_sessions.append(parsed)

            if claude_sessions:
                lines.append(f"**Claude Conversations ({len(claude_sessions)}):**")
                for cs in claude_sessions:
                    lines.append(claude.format_session_summary(cs))
                lines.append("")

    lines.append(f"---\n**Grand Total: {format_hours(grand_total)}**\n")
    return "\n".join(lines)
