#!/usr/bin/env python3
from __future__ import annotations

"""Work summarizer: enrich sessions with git commits and Claude conversation summaries.

Combines: git-summarizer + claude-parser + sqlite-store

Usage:
    python main.py [--session SESSION_ID] [--since DATE] [--until DATE] [--today] [--week]
"""

import argparse
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _load_module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


BASE = Path(__file__).resolve().parent.parent.parent / "apps"
store = _load_module("store", str(BASE / "sqlite-store" / "main.py"))
git_sum = _load_module("git_sum", str(BASE / "git-summarizer" / "main.py"))
claude = _load_module("claude", str(BASE / "claude-parser" / "main.py"))


def summarize_session(conn, session: dict) -> dict:
    """Enrich a session with git and Claude summaries."""
    repo = session["repo_path"]
    start = session["start_time"][:19]
    end = session["end_time"][:19] if session["end_time"] else datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    # Git summary
    since_date = start[:10]
    until_date = end[:10]
    commits = git_sum.git_log(repo, since=since_date, until=until_date + "T23:59:59")
    git_summary = git_sum.format_markdown(repo, commits) if commits else None

    # Claude summary
    project_dirs = claude.find_project_dirs(repo)
    claude_summaries = []
    for pdir in project_dirs:
        for f in sorted(pdir.glob("*.jsonl")):
            parsed = claude.parse_session(f)
            # Filter by time overlap with session
            if parsed.get("first_timestamp") and parsed.get("last_timestamp"):
                if parsed["last_timestamp"] >= start and parsed["first_timestamp"] <= end:
                    claude_summaries.append(parsed)

    # Log enrichment as activity
    if commits:
        store.log_activity(conn, session["id"], "git_summary", f"{len(commits)} commits found")
    if claude_summaries:
        store.log_activity(conn, session["id"], "claude_summary", f"{len(claude_summaries)} conversations found")

    return {
        **session,
        "git_summary": git_summary,
        "git_commit_count": len(commits),
        "claude_summaries": claude_summaries,
    }


def format_enriched_session(s: dict) -> str:
    """Format an enriched session as markdown."""
    lines = [
        f"## [{s['id']}] {s['project_name']}",
        f"**Repo:** {s['repo_path']}",
        f"**Time:** {s['start_time'][:19]} → {(s['end_time'] or 'ongoing')[:19]}",
        "",
    ]

    if s.get("git_summary"):
        lines.append("### Git Commits")
        lines.append(s["git_summary"])
        lines.append("")

    if s.get("claude_summaries"):
        lines.append("### Claude Conversations")
        for cs in s["claude_summaries"]:
            lines.append(claude.format_session_summary(cs))
        lines.append("")

    if not s.get("git_summary") and not s.get("claude_summaries"):
        lines.append("*No git commits or Claude conversations found for this session.*")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Enrich sessions with git and Claude summaries")
    parser.add_argument("--session", type=int, help="Specific session ID to summarize")
    parser.add_argument("--since", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--until", help="End date (YYYY-MM-DD)")
    parser.add_argument("--today", action="store_true", help="Today only")
    parser.add_argument("--week", action="store_true", help="Past 7 days")
    args = parser.parse_args()

    conn = store.get_db()

    since = args.since
    until = args.until

    if args.today:
        since = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        until = since
    elif args.week:
        until = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

    if args.session:
        session = store.get_session(conn, args.session)
        if not session:
            print(f"Session {args.session} not found")
            return
        enriched = summarize_session(conn, session)
        print(format_enriched_session(enriched))
    else:
        sessions = store.list_sessions(conn)
        # Filter by date
        filtered = []
        for s in sessions:
            if since and s["start_time"][:10] < since:
                continue
            if until and s["start_time"][:10] > until:
                continue
            filtered.append(s)

        if not filtered:
            print("No sessions found for the specified range.")
            return

        print("# Work Summary")
        print()
        for s in filtered:
            enriched = summarize_session(conn, s)
            print(format_enriched_session(enriched))

    conn.close()


if __name__ == "__main__":
    main()
