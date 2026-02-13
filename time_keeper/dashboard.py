"""Terminal dashboard for time-keeper — live view of sessions and projects."""
from __future__ import annotations

import time
from datetime import datetime, timezone

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import store


def parse_iso(ts: str) -> datetime:
    ts = ts.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)


def duration_str(start_time: str, end_time: str | None) -> str:
    start = parse_iso(start_time)
    end = parse_iso(end_time) if end_time else datetime.now(timezone.utc)
    seconds = max(0, (end - start).total_seconds())
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    return f"{m}m {s:02d}s"


def make_active_panel(conn) -> Panel:
    """Build the active sessions panel."""
    active = store.list_sessions(conn, status="active")

    if not active:
        content = Text("No active sessions", style="dim italic")
        return Panel(content, title="Active Sessions", border_style="green")

    table = Table(show_header=True, header_style="bold cyan", expand=True,
                  show_lines=False, pad_edge=False)
    table.add_column("ID", style="bold", width=4)
    table.add_column("Project", style="bold green")
    table.add_column("Elapsed", style="yellow", justify="right")
    table.add_column("Repo", style="dim")

    for s in active:
        elapsed = duration_str(s["start_time"], None)
        repo_short = s["repo_path"].replace(str(store.DB_DIR.parent), "~")
        # Try to shorten home dir
        import os
        home = os.path.expanduser("~")
        repo_display = s["repo_path"].replace(home, "~")
        table.add_row(str(s["id"]), s["project_name"], elapsed, repo_display)

    return Panel(table, title=f"Active Sessions ({len(active)})", border_style="green")


def make_recent_panel(conn, limit: int = 10) -> Panel:
    """Build the recent stopped sessions panel."""
    stopped = store.list_sessions(conn, status="stopped")[:limit]

    if not stopped:
        content = Text("No completed sessions yet", style="dim italic")
        return Panel(content, title="Recent Sessions", border_style="blue")

    table = Table(show_header=True, header_style="bold cyan", expand=True,
                  show_lines=False, pad_edge=False)
    table.add_column("ID", width=4)
    table.add_column("Project")
    table.add_column("Duration", justify="right")
    table.add_column("Date", style="dim")

    for s in stopped:
        dur = duration_str(s["start_time"], s["end_time"])
        date = s["start_time"][:10]
        table.add_row(str(s["id"]), s["project_name"], dur, date)

    return Panel(table, title=f"Recent Sessions (last {limit})", border_style="blue")


def make_projects_panel(conn) -> Panel:
    """Build the projects summary panel."""
    projects = store.list_projects(conn)

    if not projects:
        content = Text("No projects tracked yet", style="dim italic")
        return Panel(content, title="Projects", border_style="magenta")

    table = Table(show_header=True, header_style="bold cyan", expand=True,
                  show_lines=False, pad_edge=False)
    table.add_column("Project", style="bold")
    table.add_column("Sessions", justify="right")
    table.add_column("Active", justify="right")

    for p in projects:
        active_str = str(p["active_count"]) if p["active_count"] else "-"
        active_style = "bold green" if p["active_count"] else "dim"
        table.add_row(
            p["project_name"],
            str(p["session_count"]),
            Text(active_str, style=active_style),
        )

    return Panel(table, title="Projects", border_style="magenta")


def make_activity_panel(conn, limit: int = 15) -> Panel:
    """Build the recent activity log panel."""
    rows = conn.execute(
        """SELECT a.timestamp, a.event_type, a.detail, s.project_name
           FROM activity_log a
           LEFT JOIN sessions s ON a.session_id = s.id
           ORDER BY a.timestamp DESC LIMIT ?""",
        (limit,),
    ).fetchall()

    if not rows:
        content = Text("No activity logged yet", style="dim italic")
        return Panel(content, title="Activity Feed", border_style="yellow")

    table = Table(show_header=True, header_style="bold cyan", expand=True,
                  show_lines=False, pad_edge=False)
    table.add_column("Time", width=8, style="dim", no_wrap=True)
    table.add_column("Event", no_wrap=True)
    table.add_column("Detail", style="dim", ratio=1)

    event_styles = {
        "session_start": "bold green",
        "session_stop": "bold red",
        "session_pause": "yellow",
        "session_resume": "green",
        "file_created": "cyan",
        "file_modified": "blue",
        "work_log": "bold magenta",
    }

    for r in rows:
        ts = r["timestamp"][11:19] if len(r["timestamp"]) > 19 else r["timestamp"][-8:]
        event = r["event_type"]
        style = event_styles.get(event, "")
        project_name = r["project_name"]
        detail_raw = r["detail"] or ""
        # For standalone entries (no session), extract project from JSON detail
        if not project_name and detail_raw:
            try:
                import json
                data = json.loads(detail_raw)
                project_name = data.get("project") or data.get("task", "")[:30] or "standalone"
                # Use task as detail for work_log entries
                detail_raw = data.get("task", detail_raw)
            except (json.JSONDecodeError, TypeError):
                project_name = "standalone"
        detail = detail_raw[:50]
        detail_text = f"{project_name}: {detail}" if detail else (project_name or "—")
        table.add_row(ts, Text(event, style=style), detail_text)

    return Panel(table, title=f"Activity Feed (last {limit})", border_style="yellow")


def make_header() -> Panel:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    header = Text()
    header.append("  time-keeper", style="bold white")
    header.append("  |  ", style="dim")
    header.append(now, style="cyan")
    header.append("  |  ", style="dim")
    header.append("q", style="bold")
    header.append("=quit  ", style="dim")
    header.append("s", style="bold")
    header.append("=start  ", style="dim")
    header.append("x", style="bold")
    header.append("=stop  ", style="dim")
    header.append("r", style="bold")
    header.append("=refresh", style="dim")
    return Panel(header, style="on grey11", height=3)


def make_dashboard(conn) -> Layout:
    """Build the full dashboard layout."""
    layout = Layout()

    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
    )

    layout["body"].split_row(
        Layout(name="left"),
        Layout(name="right"),
    )

    layout["left"].split_column(
        Layout(name="active", ratio=2),
        Layout(name="projects", ratio=1),
    )

    layout["right"].split_column(
        Layout(name="recent", ratio=1),
        Layout(name="activity", ratio=2),
    )

    layout["header"].update(make_header())
    layout["active"].update(make_active_panel(conn))
    layout["projects"].update(make_projects_panel(conn))
    layout["recent"].update(make_recent_panel(conn))
    layout["activity"].update(make_activity_panel(conn))

    return layout


def run_dashboard():
    """Run the live dashboard."""
    import os
    import select
    import sys
    import termios
    import tty

    conn = store.get_db()
    console = Console()

    # Set terminal to raw mode for key detection
    old_settings = termios.tcgetattr(sys.stdin)

    try:
        tty.setcbreak(sys.stdin.fileno())

        with Live(make_dashboard(conn), console=console, refresh_per_second=1, screen=True) as live:
            while True:
                # Check for keypress (non-blocking)
                if select.select([sys.stdin], [], [], 0.5)[0]:
                    key = sys.stdin.read(1)

                    if key in ("q", "Q", "\x03"):  # q or Ctrl+C
                        break

                    elif key in ("s", "S"):
                        # Start a session for CWD
                        cwd = os.getcwd()
                        active = store.get_active_session(conn, cwd)
                        if not active:
                            store.create_session(conn, cwd)

                    elif key in ("x", "X"):
                        # Stop the most recent active session
                        active = store.get_active_session(conn)
                        if active:
                            store.stop_session(conn, active["id"])

                # Refresh display
                live.update(make_dashboard(conn))

    except KeyboardInterrupt:
        pass
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        conn.close()
