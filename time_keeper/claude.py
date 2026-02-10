"""Parse Claude Code conversation history."""
from __future__ import annotations

import json
from pathlib import Path


CLAUDE_DIR = Path.home() / ".claude" / "projects"


def find_project_dirs(project_path: str | None = None) -> list[Path]:
    if not CLAUDE_DIR.exists():
        return []
    dirs = []
    for d in CLAUDE_DIR.iterdir():
        if not d.is_dir():
            continue
        if project_path:
            encoded = project_path.replace("/", "-")
            if encoded.lstrip("-") in d.name.lstrip("-"):
                dirs.append(d)
        else:
            dirs.append(d)
    return sorted(dirs)


def parse_session(filepath: Path) -> dict:
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

    timestamps = [e.get("timestamp") for e in entries if e.get("timestamp")]
    first_ts = min(timestamps) if timestamps else None
    last_ts = max(timestamps) if timestamps else None
    topic = user_messages[0][:200] if user_messages else "(no messages)"

    return {
        "session_id": filepath.stem,
        "first_timestamp": first_ts,
        "last_timestamp": last_ts,
        "topic": topic,
        "user_message_count": len(user_messages),
        "assistant_message_count": len(assistant_messages),
        "tools_used": sorted(tools_used),
    }


def format_session_summary(s: dict) -> str:
    lines = [
        f"- **{s['session_id'][:12]}...** ({s.get('first_timestamp', '?')[:19]})",
        f"  Topic: {s['topic'][:100]}",
        f"  Messages: {s['user_message_count']} user, {s['assistant_message_count']} assistant",
    ]
    if s["tools_used"]:
        lines.append(f"  Tools: {', '.join(s['tools_used'][:10])}")
    return "\n".join(lines)
