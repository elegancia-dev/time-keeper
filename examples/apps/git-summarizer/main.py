#!/usr/bin/env python3
from __future__ import annotations

"""Extract and summarize git commit history for a time range.

Usage:
    python main.py /path/to/repo [--since DATE] [--until DATE]
    python main.py /path/to/repo --today
    python main.py /path/to/repo --week
"""

import argparse
import subprocess
from collections import defaultdict
from datetime import datetime, timedelta, timezone


def git_log(repo_path: str, since: str | None = None, until: str | None = None) -> list[dict]:
    """Run git log and return parsed commits."""
    cmd = [
        "git", "-C", repo_path, "log",
        "--format=%H%n%an%n%aI%n%s%n---END---",
    ]
    if since:
        cmd.append(f"--since={since}")
    if until:
        cmd.append(f"--until={until}")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        if "not a git repository" in result.stderr:
            print(f"Error: {repo_path} is not a git repository")
            return []
        print(f"Git error: {result.stderr.strip()}")
        return []

    commits = []
    raw = result.stdout.strip()
    if not raw:
        return []

    entries = raw.split("---END---")
    for entry in entries:
        lines = entry.strip().split("\n")
        if len(lines) >= 4:
            commits.append({
                "hash": lines[0],
                "author": lines[1],
                "date": lines[2],
                "message": lines[3],
            })

    return commits


def group_by_day(commits: list[dict]) -> dict[str, list[dict]]:
    """Group commits by date (YYYY-MM-DD)."""
    groups = defaultdict(list)
    for c in commits:
        day = c["date"][:10]
        groups[day].append(c)
    return dict(sorted(groups.items()))


def format_markdown(repo_path: str, commits: list[dict]) -> str:
    """Format commits as a markdown summary."""
    if not commits:
        return f"# Git Summary: {repo_path}\n\nNo commits found for the specified range.\n"

    by_day = group_by_day(commits)
    lines = [f"# Git Summary: {repo_path}", ""]

    total = len(commits)
    days = len(by_day)
    lines.append(f"**{total} commits** across **{days} day(s)**")
    lines.append("")

    for day, day_commits in by_day.items():
        lines.append(f"## {day}")
        lines.append("")
        for c in day_commits:
            short_hash = c["hash"][:8]
            lines.append(f"- `{short_hash}` {c['message']} ({c['author']})")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Summarize git commit history")
    parser.add_argument("repo", nargs="?", default=".", help="Repository path (default: .)")
    parser.add_argument("--since", help="Start date (YYYY-MM-DD or git date spec)")
    parser.add_argument("--until", help="End date (YYYY-MM-DD or git date spec)")
    parser.add_argument("--today", action="store_true", help="Show today's commits")
    parser.add_argument("--week", action="store_true", help="Show this week's commits")
    args = parser.parse_args()

    since = args.since
    until = args.until

    if args.today:
        since = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    elif args.week:
        start = datetime.now(timezone.utc) - timedelta(days=7)
        since = start.strftime("%Y-%m-%d")

    commits = git_log(args.repo, since, until)
    print(format_markdown(args.repo, commits))


if __name__ == "__main__":
    main()
