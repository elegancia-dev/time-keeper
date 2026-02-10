"""Git commit extraction and summarization."""
from __future__ import annotations

import subprocess
from collections import defaultdict


def git_log(repo_path: str, since: str | None = None, until: str | None = None) -> list[dict]:
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
        return []

    commits = []
    raw = result.stdout.strip()
    if not raw:
        return []

    for entry in raw.split("---END---"):
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
    groups = defaultdict(list)
    for c in commits:
        groups[c["date"][:10]].append(c)
    return dict(sorted(groups.items()))


def format_markdown(repo_path: str, commits: list[dict]) -> str:
    if not commits:
        return ""

    by_day = group_by_day(commits)
    lines = []
    for day, day_commits in by_day.items():
        lines.append(f"**{day}:**")
        for c in day_commits:
            lines.append(f"  - `{c['hash'][:8]}` {c['message']}")
        lines.append("")
    return "\n".join(lines)
