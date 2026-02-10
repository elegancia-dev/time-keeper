"""Time Keeper CLI - track billable hours across repos."""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

import click

from . import store, reports
from .watcher import WatchTracker


def date_range_options(f):
    """Common date range options for report commands."""
    f = click.option("--since", help="Start date (YYYY-MM-DD)")(f)
    f = click.option("--until", help="End date (YYYY-MM-DD)")(f)
    f = click.option("--today", is_flag=True, help="Today only")(f)
    f = click.option("--week", is_flag=True, help="Past 7 days")(f)
    f = click.option("--project", help="Filter by project name")(f)
    return f


def resolve_dates(since, until, today, week):
    if today:
        since = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        until = since
    elif week:
        until = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    return since, until


@click.group()
def cli():
    """tk - Time Keeper: track billable hours across repos."""
    pass


@cli.command()
@click.option("--repo", default=".", help="Repository path (default: current directory)")
@click.option("--project", help="Project name (defaults to repo directory name)")
def start(repo, project):
    """Manually start a work session."""
    conn = store.get_db()
    active = store.get_active_session(conn, repo)
    if active:
        click.echo(f"Session {active['id']} already active for {active['project_name']}")
        conn.close()
        return

    repo_path = os.path.abspath(repo)
    session_id = store.create_session(conn, repo_path, project)
    project_name = project or os.path.basename(repo_path)
    click.echo(f"Session {session_id} started for {project_name}")
    conn.close()


@cli.command()
@click.option("--repo", default=None, help="Repository path (stops session for this repo)")
def stop(repo):
    """Stop the current work session."""
    conn = store.get_db()
    active = store.get_active_session(conn, repo)
    if not active:
        click.echo("No active session to stop")
        conn.close()
        return

    if store.stop_session(conn, active["id"]):
        hours = reports.session_duration_hours(active)
        click.echo(f"Session {active['id']} stopped ({active['project_name']}, {reports.format_hours(hours)})")
    else:
        click.echo("Failed to stop session")
    conn.close()


@cli.command()
def status():
    """Show current session status."""
    conn = store.get_db()
    active = store.get_active_session(conn)
    if not active:
        click.echo("No active session")
        conn.close()
        return

    hours = reports.session_duration_hours(active)
    click.echo(f"Active session: [{active['id']}] {active['project_name']}")
    click.echo(f"  Repo:    {active['repo_path']}")
    click.echo(f"  Started: {active['start_time'][:19]}")
    click.echo(f"  Elapsed: {reports.format_hours(hours)}")
    conn.close()


@cli.command()
@click.option("--repo", default=".", help="Repository path to watch (default: current directory)")
@click.option("--idle-timeout", type=int, default=15, help="Idle timeout in minutes (default: 15)")
@click.option("--project", help="Project name (defaults to repo directory name)")
def watch(repo, idle_timeout, project):
    """Start file watcher daemon — auto-tracks sessions based on file changes."""
    tracker = WatchTracker(repo, idle_timeout, project)
    tracker.run()


@cli.command()
@date_range_options
def summary(since, until, today, week, project):
    """Show summary report (hours per project)."""
    since, until = resolve_dates(since, until, today, week)
    conn = store.get_db()
    click.echo(reports.summary_report(conn, since, until, project))
    conn.close()


@cli.command()
@date_range_options
def detail(since, until, today, week, project):
    """Show detailed report with commits and Claude conversations."""
    since, until = resolve_dates(since, until, today, week)
    conn = store.get_db()
    click.echo(reports.detail_report(conn, since, until, project))
    conn.close()


@cli.command()
def dashboard():
    """Open the live terminal dashboard."""
    from .dashboard import run_dashboard
    run_dashboard()


@cli.command()
def projects():
    """List all tracked projects."""
    conn = store.get_db()
    projs = store.list_projects(conn)
    if not projs:
        click.echo("No projects tracked yet")
        conn.close()
        return

    for p in projs:
        active_str = f" ({p['active_count']} active)" if p["active_count"] else ""
        click.echo(f"  {p['project_name']:30s}  {p['session_count']} sessions{active_str}  {p['repo_path']}")
    conn.close()


if __name__ == "__main__":
    cli()
