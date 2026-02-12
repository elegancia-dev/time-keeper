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


def _extract_tool_file_paths(block: dict) -> list[str]:
    """Extract file paths from a tool_use block's input."""
    inp = block.get("input", {})
    paths = []
    for key in ("file_path", "path"):
        val = inp.get(key)
        if val and isinstance(val, str):
            paths.append(val)
    return paths


def parse_session(filepath: Path) -> dict:
    entries = []
    with open(filepath) as f:
        for line in f:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    user_messages = []
    user_requests = []
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
                            tool_name = block.get("name", "unknown")
                            tools_used.add(tool_name)
                            if tool_name in ("Edit", "Write", "Read", "NotebookEdit"):
                                for p in _extract_tool_file_paths(block):
                                    files_touched.add(p)

    # Filter user messages to real requests (skip tool interrupts and short confirmations)
    for msg in user_messages:
        text = msg.strip()
        if text.startswith("[Request interrupted"):
            continue
        if text.startswith("<task-notification>"):
            continue
        if len(text) <= 5:
            continue
        user_requests.append(text)

    timestamps = [e.get("timestamp") for e in entries if e.get("timestamp")]
    first_ts = min(timestamps) if timestamps else None
    last_ts = max(timestamps) if timestamps else None
    topic = user_requests[0][:200] if user_requests else "(no messages)"

    # Calculate duration
    duration_min = None
    if first_ts and last_ts:
        try:
            from .reports import parse_iso
            dt_first = parse_iso(first_ts)
            dt_last = parse_iso(last_ts)
            duration_min = max(0, (dt_last - dt_first).total_seconds() / 60)
        except Exception:
            pass

    return {
        "session_id": filepath.stem,
        "first_timestamp": first_ts,
        "last_timestamp": last_ts,
        "topic": topic,
        "user_requests": user_requests,
        "user_message_count": len(user_messages),
        "assistant_message_count": len(assistant_messages),
        "tools_used": sorted(tools_used),
        "files_touched": sorted(files_touched),
        "duration_min": duration_min,
    }


def format_session_summary(s: dict) -> str:
    duration = ""
    if s.get("duration_min") is not None:
        mins = int(s["duration_min"])
        if mins >= 60:
            duration = f" ({mins // 60}h {mins % 60}m)"
        else:
            duration = f" ({mins}m)"

    lines = [
        f"- **{s['session_id'][:12]}...** ({s.get('first_timestamp', '?')[:19]}){duration}",
    ]

    # Show user requests as work summary
    requests = s.get("user_requests", [])
    if requests:
        lines.append("  **Requests:**")
        for req in requests[:5]:
            # Trim to first line, max 120 chars
            first_line = req.split("\n")[0][:120]
            lines.append(f"    - {first_line}")
        if len(requests) > 5:
            lines.append(f"    - ...and {len(requests) - 5} more")

    # Show files changed
    files = s.get("files_touched", [])
    if files:
        lines.append(f"  **Files touched ({len(files)}):**")
        for fp in files[:10]:
            # Show just the filename or last 2 path components
            parts = fp.split("/")
            short = "/".join(parts[-2:]) if len(parts) > 1 else fp
            lines.append(f"    - `{short}`")
        if len(files) > 10:
            lines.append(f"    - ...and {len(files) - 10} more")

    lines.append(f"  Messages: {s['user_message_count']} user, {s['assistant_message_count']} assistant")
    if s["tools_used"]:
        lines.append(f"  Tools: {', '.join(s['tools_used'][:10])}")
    return "\n".join(lines)
