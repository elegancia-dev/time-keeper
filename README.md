# time-keeper

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)

A billable hour tracker for contractors working across multiple repositories. It auto-detects work sessions by watching file changes, logs time to a local SQLite database, and generates reports enriched with git commit history and Claude Code conversation summaries.

## Why time-keeper?

If you're a contractor juggling multiple repos, tracking billable hours is tedious. Most time trackers require you to remember to start and stop timers manually. time-keeper watches your file system instead — start `tk watch` when you sit down to work and it handles the rest. Sessions auto-start, auto-pause on idle, and auto-resume when you come back. At the end of the week, `tk summary --week` gives you a clean breakdown by project.

## Features

- **Auto-detection** — watches file changes and tracks sessions automatically
- **Idle handling** — pauses after inactivity, resumes when you return
- **Git enrichment** — reports include commit history for each session
- **Claude integration** — detailed reports pull in Claude Code conversation summaries
- **Live dashboard** — terminal UI with real-time session tracking
- **macOS menu bar** — start/stop sessions from the menu bar
- **Local-first** — all data in a single SQLite file, no network, no accounts, no telemetry
- **JSON inbox** — ingest time data from external sources (e.g., browser extensions)

## Quick Start

```bash
# Install (editable mode, from the repo root)
pip install -e .

# The `tk` binary installs to your Python user bin directory
# (e.g., ~/Library/Python/3.9/bin/tk). If it's not on your PATH, either
# add that directory to PATH or use the module directly:
python3 -m time_keeper.cli

# Start watching the current repo for file changes (auto-tracks sessions)
tk watch

# Or manually start/stop sessions
tk start
tk stop

# Check what's running
tk status

# See hours for the past week
tk summary --week
```

## CLI Reference

All commands are available via `tk <command>`.

### `tk start`

Manually start a work session.

```bash
tk start                          # Current directory, project name from dir
tk start --repo /path/to/repo     # Specific repo
tk start --project "client-api"   # Custom project name
```

### `tk stop`

Stop the current active session.

```bash
tk stop                           # Stop the most recent active session
tk stop --repo /path/to/repo      # Stop the session for a specific repo
```

### `tk status`

Show the currently active session with elapsed time.

```bash
tk status
# Active session: [3] client-api
#   Repo:    /Users/you/repos/client-api
#   Started: 2026-02-09T14:30:00
#   Elapsed: 1h 23m
```

### `tk watch`

Start a file watcher daemon that auto-starts and auto-pauses sessions based on file activity. This is the primary way to use time-keeper -- start it when you begin work and let it handle the rest.

```bash
tk watch                                  # Watch current directory, 15m idle timeout
tk watch --repo /path/to/repo             # Watch a specific repo
tk watch --idle-timeout 10                # Pause after 10 minutes of inactivity
tk watch --project "client-api"           # Custom project name
```

The watcher auto-starts a session on the first file change, pauses when idle, resumes when activity returns, and cleanly stops the session on Ctrl+C.

### `tk summary`

Show a summary report with hours grouped by project.

```bash
tk summary                        # All sessions
tk summary --today                # Today only
tk summary --week                 # Past 7 days
tk summary --since 2026-02-01     # From a specific date
tk summary --since 2026-02-01 --until 2026-02-07
tk summary --project "client-api" # Filter to one project
```

### `tk detail`

Show a detailed report with per-session breakdown, activity logs, git commits, and Claude conversations.

```bash
tk detail --today
tk detail --week
tk detail --project "client-api"
tk detail --since 2026-02-01 --until 2026-02-07
```

### `tk projects`

List all tracked projects with session counts.

```bash
tk projects
#   client-api                      12 sessions  /Users/you/repos/client-api
#   internal-tools                   4 sessions  /Users/you/repos/internal-tools
```

### `tk dashboard`

Open a live terminal dashboard with real-time session tracking. The dashboard refreshes every second and shows:

- **Active Sessions** — currently running sessions with live elapsed timers
- **Recent Sessions** — last 10 completed sessions
- **Projects** — all tracked projects with session counts
- **Activity Feed** — last 15 events (file changes, starts, stops, pauses)

Keyboard shortcuts inside the dashboard:

| Key | Action                                            |
| --- | ------------------------------------------------- |
| `q` | Quit the dashboard                                |
| `s` | Start a session for the current working directory |
| `x` | Stop the most recent active session               |

```bash
tk dashboard
```

## Architecture

```
time-keeper/
  examples/apps/     # Standalone single-purpose scripts (prototypes)
  examples/combos/   # Compositions of the standalone apps (prototypes)
  time_keeper/       # Final CLI tool (installed as `tk`)
```

The `time_keeper/` package is the installable Python package with a Click-based CLI. This is what `pip install -e .` installs as the `tk` command.

## Examples

The `examples/` directory contains the prototypes that time-keeper was built from:

- **`examples/apps/`** — Six standalone scripts that each do one thing (file watching, SQLite storage, git summarization, session timing, Claude conversation parsing, report generation). Each can be run independently with `python main.py --help`.
- **`examples/combos/`** — Two scripts that compose the standalone apps into higher-level workflows (active session tracking, work summarization).

These are useful as reference implementations and for understanding how the pieces fit together. See the README files in each subdirectory for usage details.

## Configuration

### Database Location

All data is stored in a single SQLite file:

```
~/.time-keeper/timekeeper.db
```

The directory is created automatically on first use.

### Idle Timeout

The default idle timeout is **15 minutes**. When no file changes are detected for this duration, the session is automatically paused. Activity resumes the session. Configure per-invocation:

```bash
tk watch --idle-timeout 10    # 10 minutes
tk watch --idle-timeout 30    # 30 minutes
```

### Ignore Patterns

The file watcher ignores these patterns by default:

- `.git/*`
- `__pycache__/*`
- `node_modules/*`
- `*.pyc`
- `.DS_Store`
- `*.swp`, `*.swo`, `*~`

### Claude Conversation Parsing

Claude conversations are read from `~/.claude/projects/`. The parser matches project directories by encoding the repo path (e.g., `/Users/you/repos/project` maps to a directory name containing `Users-you-repos-project`). No configuration is needed -- if Claude Code has been used in a repo, its conversations will be picked up automatically in detailed reports.

## Data

### Database Schema

**sessions**

| Column       | Type    | Description                               |
| ------------ | ------- | ----------------------------------------- |
| id           | INTEGER | Primary key, auto-increment               |
| repo_path    | TEXT    | Absolute path to the repository           |
| project_name | TEXT    | Project name (defaults to directory name) |
| start_time   | TEXT    | ISO 8601 UTC timestamp                    |
| end_time     | TEXT    | ISO 8601 UTC timestamp (NULL if active)   |
| status       | TEXT    | `active` or `stopped`                     |

**activity_log**

| Column     | Type    | Description                                                                                                                                             |
| ---------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| id         | INTEGER | Primary key, auto-increment                                                                                                                             |
| session_id | INTEGER | Foreign key to sessions.id                                                                                                                              |
| timestamp  | TEXT    | ISO 8601 UTC timestamp                                                                                                                                  |
| event_type | TEXT    | Event type (e.g., `session_start`, `session_stop`, `session_pause`, `session_resume`, `file_modified`, `file_created`, `git_summary`, `claude_summary`) |
| detail     | TEXT    | Optional detail (e.g., relative file path)                                                                                                              |

### Querying the Database Directly

```bash
sqlite3 ~/.time-keeper/timekeeper.db

-- Active sessions
SELECT * FROM sessions WHERE status = 'active';

-- Hours per project this week
SELECT project_name,
       SUM((julianday(COALESCE(end_time, datetime('now'))) - julianday(start_time)) * 24) as hours
FROM sessions
WHERE start_time >= date('now', '-7 days')
GROUP BY project_name;

-- Recent activity
SELECT * FROM activity_log ORDER BY timestamp DESC LIMIT 20;
```

## Privacy

time-keeper is local-first by design:

- All data stays in `~/.time-keeper/` on your machine
- No network requests, no telemetry, no external accounts
- SQLite database you can query, export, or delete at any time
- Git and Claude data are read on demand, never copied into the database

## Roadmap

See [docs/roadmap.md](docs/roadmap.md) for planned improvements and future directions.

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
