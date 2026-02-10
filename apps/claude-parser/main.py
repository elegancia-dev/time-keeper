#!/usr/bin/env python3
from __future__ import annotations

"""Parse Claude Code conversation history and extract summaries.

Usage:
    python main.py [--project-dir PATH] [--since DATE] [--until DATE]
    python main.py --session SESSION_ID [--project-dir PATH]
    python main.py --list [--project-dir PATH]
"""

import argparse
import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


CLAUDE_DIR = Path.home() / ".claude" / "projects"


def find_project_dirs(project_path: str | None = None) -> list[Path]:
    """Find Claude project directories, optionally filtered by project path."""
    if not CLAUDE_DIR.exists():
        return []

    dirs = []
    for d in CLAUDE_DIR.iterdir():
        if not d.is_dir():
            continue
        if project_path:
            # Claude encodes paths with dashes: /Users/foo/bar -> -Users-foo-bar
            encoded = project_path.replace("/", "-")
            if encoded.lstrip("-") in d.name.lstrip("-"):
                dirs.append(d)
        else:
            dirs.append(d)
    return sorted(dirs)


def list_sessions(project_dir: Path) -> list[dict]:
    """List all conversation sessions in a project directory."""
    sessions = []
    for f in sorted(project_dir.glob("*.jsonl")):
        session_id = f.stem
        first_ts = None
        last_ts = None
        message_count = 0
        first_user_msg = None

        with open(f) as fh:
            for line in fh:
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                ts = entry.get("timestamp")
                if ts:
                    if not first_ts:
                        first_ts = ts
                    last_ts = ts

                if entry.get("type") == "user":
                    message_count += 1
                    if not first_user_msg:
                        msg = entry.get("message", {})
                        content = msg.get("content", "")
                        if isinstance(content, list):
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "text":
                                    first_user_msg = block["text"][:100]
                                    break
                        elif isinstance(content, str):
                            first_user_msg = content[:100]

        sessions.append({
            "session_id": session_id,
            "first_timestamp": first_ts,
            "last_timestamp": last_ts,
            "message_count": message_count,
            "topic": first_user_msg or "(empty)",
        })

    return sessions


def parse_session(filepath: Path) -> dict:
    """Parse a single session JSONL file and extract a summary."""
    entries = []
    with open(filepath) as f:
        for line in f:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    user_messages = []
    assistant_messages = []
    tools_used = set()
    files_touched = set()

    for entry in entries:
        msg = entry.get("message", {})
        role = msg.get("role")
        content = msg.get("content", "")

        if entry.get("type") == "user" and role == "user":
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        user_messages.append(block["text"])
            elif isinstance(content, str):
                user_messages.append(content)

        elif role == "assistant":
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            assistant_messages.append(block["text"])
                        elif block.get("type") == "tool_use":
                            tools_used.add(block.get("name", "unknown"))
                            inp = block.get("input", {})
                            # Extract file paths from common tool inputs
                            for key in ("file_path", "path", "command"):
                                val = inp.get(key, "")
                                if isinstance(val, str) and ("/" in val or "\\" in val):
                                    files_touched.add(val)

    timestamps = [e.get("timestamp") for e in entries if e.get("timestamp")]
    first_ts = min(timestamps) if timestamps else None
    last_ts = max(timestamps) if timestamps else None

    # Build topic from first user message
    topic = user_messages[0][:200] if user_messages else "(no messages)"

    return {
        "session_id": filepath.stem,
        "first_timestamp": first_ts,
        "last_timestamp": last_ts,
        "topic": topic,
        "user_message_count": len(user_messages),
        "assistant_message_count": len(assistant_messages),
        "tools_used": sorted(tools_used),
        "files_touched": sorted(files_touched)[:20],
    }


def format_session_summary(s: dict) -> str:
    """Format a parsed session as markdown."""
    lines = [
        f"### Session: {s['session_id'][:12]}...",
        f"**Time:** {s.get('first_timestamp', '?')} → {s.get('last_timestamp', '?')}",
        f"**Topic:** {s['topic']}",
        f"**Messages:** {s['user_message_count']} user, {s['assistant_message_count']} assistant",
    ]
    if s["tools_used"]:
        lines.append(f"**Tools:** {', '.join(s['tools_used'])}")
    if s["files_touched"]:
        lines.append("**Files touched:**")
        for f in s["files_touched"]:
            lines.append(f"  - {f}")
    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Parse Claude Code conversation history")
    parser.add_argument("--project-dir", help="Path to project (filters Claude sessions for that project)")
    parser.add_argument("--session", help="Specific session ID to parse")
    parser.add_argument("--list", action="store_true", help="List available sessions")
    parser.add_argument("--since", help="Filter sessions starting from this date (YYYY-MM-DD)")
    parser.add_argument("--until", help="Filter sessions until this date (YYYY-MM-DD)")
    args = parser.parse_args()

    project_dirs = find_project_dirs(args.project_dir)
    if not project_dirs:
        print("No Claude project directories found.")
        if args.project_dir:
            print(f"  Looked for project matching: {args.project_dir}")
        return

    for pdir in project_dirs:
        if args.list:
            sessions = list_sessions(pdir)
            if not sessions:
                continue
            print(f"# Sessions in {pdir.name}")
            print()
            for s in sessions:
                print(f"  {s['session_id'][:12]}  {s['first_timestamp'] or '?':25s}  msgs={s['message_count']:3d}  {s['topic']}")
            print()

        elif args.session:
            session_file = pdir / f"{args.session}.jsonl"
            if session_file.exists():
                summary = parse_session(session_file)
                print(format_session_summary(summary))
                return
        else:
            # Summarize all sessions
            print(f"# Claude Sessions: {pdir.name}")
            print()
            for f in sorted(pdir.glob("*.jsonl")):
                summary = parse_session(f)

                # Date filter
                if args.since and summary.get("first_timestamp"):
                    if summary["first_timestamp"] < args.since:
                        continue
                if args.until and summary.get("first_timestamp"):
                    if summary["first_timestamp"] > args.until:
                        continue

                print(format_session_summary(summary))

    if args.session:
        print(f"Session {args.session} not found")


if __name__ == "__main__":
    main()
