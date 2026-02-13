"""Report generation for time-keeper."""
from __future__ import annotations

import json
import os
import re
from collections import defaultdict
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


def parse_duration_estimate(raw: str) -> float:
    """Parse duration strings like '30m', '1h', '2h+', '1.5h', '90m' into hours."""
    if not raw:
        return 0.0
    raw = raw.strip().rstrip("+")
    m = re.match(r"^(\d+(?:\.\d+)?)\s*h$", raw, re.IGNORECASE)
    if m:
        return float(m.group(1))
    m = re.match(r"^(\d+)\s*m$", raw, re.IGNORECASE)
    if m:
        return int(m.group(1)) / 60.0
    return 0.0


def day_summary(conn, since_dt: datetime) -> dict[str, dict[str, float]]:
    """Return {date_str: {project: hours}} for sessions and standalone work_log entries since since_dt."""
    since_iso = since_dt.strftime("%Y-%m-%dT%H:%M:%S")
    result: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

    # 1. Sessions
    sessions = conn.execute(
        "SELECT * FROM sessions WHERE start_time >= ? OR (status = 'active' AND start_time < ?)",
        (since_iso, since_iso),
    ).fetchall()
    for row in sessions:
        s = dict(row)
        start = parse_iso(s["start_time"])
        # Clamp start to since_dt
        effective_start = max(start, since_dt)
        end = parse_iso(s["end_time"]) if s["end_time"] else datetime.now(timezone.utc)
        hours = max(0, (end - effective_start).total_seconds() / 3600)
        date_str = effective_start.strftime("%Y-%m-%d")
        result[date_str][s["project_name"]] += hours

    # 2. Standalone work_log entries
    work_logs = conn.execute(
        "SELECT * FROM activity_log WHERE session_id IS NULL AND event_type = 'work_log' AND timestamp >= ?",
        (since_iso,),
    ).fetchall()
    for row in work_logs:
        a = dict(row)
        date_str = a["timestamp"][:10]
        detail = a["detail"] or ""
        try:
            data = json.loads(detail)
        except (json.JSONDecodeError, TypeError):
            continue
        project = data.get("project") or "unknown"
        hours = parse_duration_estimate(data.get("duration_estimate", ""))
        if hours > 0:
            result[date_str][project] += hours

    return dict(result)


def format_day_summary(data: dict[str, dict[str, float]], period_label: str) -> str:
    """Format day_summary data as readable text for terminal display."""
    if not data:
        return f"No data for {period_label}.\n"
    lines = [f"  Time Summary — {period_label}", ""]
    grand_total = 0.0
    for date_str in sorted(data.keys(), reverse=True):
        projects = data[date_str]
        lines.append(f"  {date_str}")
        for proj, hrs in sorted(projects.items(), key=lambda x: -x[1]):
            grand_total += hrs
            lines.append(f"    {proj:30s} {format_hours(hrs)}")
        lines.append("")
    lines.append(f"  Total: {format_hours(grand_total)}")
    lines.append("")
    return "\n".join(lines)


def _extract_topic(raw_topic: str) -> str:
    """Extract a clean topic from a Claude conversation's first message.

    If it starts with 'Implement the following plan:' followed by a markdown
    heading, extract just that heading as the topic.
    """
    # Match plan-style prompts: extract the first # heading
    m = re.search(r"#\s+(.+)", raw_topic)
    if m:
        return m.group(1).strip()
    # Otherwise use first line, trimmed
    first_line = raw_topic.split("\n")[0].strip()
    return first_line[:120] if first_line else "(no topic)"


def _is_tmp_file(filename: str) -> bool:
    """Return True for temp/swap/backup files that should be filtered out."""
    return bool(re.search(r"\.tmp\.\d+\.\d+$", filename)) or filename.endswith("~")


def gather_day_context(conn, since_dt: datetime, until_dt: datetime | None = None) -> str:
    """Collect all raw data for a date range and return structured text for prompting."""
    since_iso = since_dt.strftime("%Y-%m-%dT%H:%M:%S")
    until_dt = until_dt or datetime.now(timezone.utc)
    until_iso = until_dt.strftime("%Y-%m-%dT%H:%M:%S")

    sections: list[str] = []

    # --- Sessions (grouped by date) ---
    sessions = store.query_sessions(conn, since_dt.strftime("%Y-%m-%d"), until_dt.strftime("%Y-%m-%d"))
    if sessions:
        by_date: dict[str, list] = defaultdict(list)
        for s in sessions:
            date_str = s["start_time"][:10]
            by_date[date_str].append(s)

        lines = ["## Sessions"]
        for date_str in sorted(by_date.keys()):
            lines.append(f"\n### {date_str}")
            for s in by_date[date_str]:
                hours = session_duration_hours(s)
                start_short = s["start_time"][11:16] if len(s["start_time"]) > 16 else ""
                end_short = ""
                if s["end_time"] and len(s["end_time"]) > 16:
                    end_short = s["end_time"][11:16]
                elif not s["end_time"]:
                    end_short = "ongoing"
                time_range = f"({start_short}\u2013{end_short})" if start_short else ""
                lines.append(f"- {s['project_name']}: {format_hours(hours)} {time_range}")
        sections.append("\n".join(lines))

    # --- Git Commits ---
    repo_paths = list({s["repo_path"] for s in sessions}) if sessions else []
    commit_lines = ["## Git Commits"]
    has_commits = False
    for repo in repo_paths:
        commits = git.git_log(repo, since=since_iso[:10], until=until_iso[:10] + "T23:59:59")
        if commits:
            has_commits = True
            project_name = os.path.basename(repo)
            commit_lines.append(f"{project_name}:")
            for c in commits:
                commit_lines.append(f"  - {c['hash'][:8]} {c['message']}")
    if has_commits:
        sections.append("\n".join(commit_lines))

    # --- File Changes (filter out tmp files) ---
    activities = conn.execute(
        "SELECT * FROM activity_log WHERE timestamp >= ? AND timestamp <= ?",
        (since_iso, until_iso),
    ).fetchall()
    file_changes: dict[str, set[str]] = defaultdict(set)
    for row in activities:
        a = dict(row)
        if a["event_type"] in ("file_modified", "file_created", "file_deleted"):
            detail = a["detail"] or ""
            try:
                data = json.loads(detail)
                path = data.get("path", detail)
            except (json.JSONDecodeError, TypeError):
                path = detail
            filename = os.path.basename(path) if path else ""
            if not filename or _is_tmp_file(filename):
                continue
            project = "unknown"
            if a["session_id"]:
                sess_row = conn.execute(
                    "SELECT project_name FROM sessions WHERE id = ?", (a["session_id"],)
                ).fetchone()
                if sess_row:
                    project = sess_row["project_name"]
            file_changes[project].add(filename)
    if file_changes:
        lines = ["## File Changes"]
        for proj, files in sorted(file_changes.items()):
            sorted_files = sorted(files)
            file_list = ", ".join(sorted_files[:15])
            extra = f" +{len(files) - 15} more" if len(files) > 15 else ""
            lines.append(f"{proj}: {file_list}{extra} ({len(files)} files)")
        sections.append("\n".join(lines))

    # --- Work Log (Chrome Extension) ---
    work_logs = conn.execute(
        "SELECT * FROM activity_log WHERE session_id IS NULL AND event_type = 'work_log' AND timestamp >= ? AND timestamp <= ?",
        (since_iso, until_iso),
    ).fetchall()
    if work_logs:
        lines = ["## Work Log (Chrome Extension)"]
        for row in work_logs:
            a = dict(row)
            detail = a["detail"] or ""
            try:
                data = json.loads(detail)
            except (json.JSONDecodeError, TypeError):
                continue
            task = data.get("task", data.get("description", ""))
            project = data.get("project", "")
            duration = data.get("duration_estimate", "")
            parts = []
            if project:
                parts.append(project)
            if duration:
                parts.append(f"~{duration}")
            suffix = f" ({', '.join(parts)})" if parts else ""
            if task:
                lines.append(f'- "{task}"{suffix}')
        if len(lines) > 1:
            sections.append("\n".join(lines))

    # --- Claude Conversations (deduplicated by session_id) ---
    claude_lines = ["## Claude Conversations"]
    seen_sessions: set[str] = set()
    has_claude = False
    for repo in repo_paths:
        project_name = os.path.basename(repo)
        project_dirs = claude.find_project_dirs(repo)
        for pdir in project_dirs:
            for f in sorted(pdir.glob("*.jsonl")):
                session_id = f.stem
                if session_id in seen_sessions:
                    continue
                try:
                    parsed = claude.parse_session(f)
                except Exception:
                    continue
                if not parsed.get("first_timestamp") or not parsed.get("last_timestamp"):
                    continue
                if parsed["last_timestamp"] < since_iso or parsed["first_timestamp"] > until_iso:
                    continue
                seen_sessions.add(session_id)
                has_claude = True
                duration = ""
                if parsed.get("duration_min") is not None:
                    mins = int(parsed["duration_min"])
                    duration = f", {format_hours(mins / 60)}" if mins > 0 else ""
                files = parsed.get("files_touched", [])
                file_str = ""
                if files:
                    short_files = [os.path.basename(p) for p in files[:5]]
                    file_str = f", touched {', '.join(short_files)}"
                topic = _extract_topic(parsed["topic"])
                claude_lines.append(f'- {project_name}: "{topic}" ({parsed["first_timestamp"][:16]}{duration}{file_str})')
    if has_claude:
        sections.append("\n".join(claude_lines))

    if not sections:
        return "No activity data found for this period."

    return "\n\n".join(sections)


def format_recap(conn, since_dt: datetime, period_label: str) -> str:
    """Hours summary + full context, ready to copy-paste into an AI chat."""
    until_dt = datetime.now(timezone.utc)

    # Part 1: hours per day per project
    data = day_summary(conn, since_dt)
    hours_text = format_day_summary(data, period_label)

    # Part 2: detailed context
    context = gather_day_context(conn, since_dt, until_dt)

    separator = "-" * 50
    return f"{hours_text}\n{separator}\n\n{context}"
