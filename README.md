# time-keeper

A billable hour tracker for contractors working across multiple repositories. It auto-detects work sessions by watching file changes, logs time to a local SQLite database, and generates reports enriched with git commit history and Claude Code conversation summaries.

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

| Key | Action |
|-----|--------|
| `q` | Quit the dashboard |
| `s` | Start a session for the current working directory |
| `x` | Stop the most recent active session |

```bash
tk dashboard
```

## Architecture

time-keeper is built as a three-phase monorepo:

```
time-keeper/
  apps/           # Phase 1: Independent single-purpose scripts
  combos/         # Phase 2: Compositions of Phase 1 apps
  time_keeper/    # Phase 3: Final CLI tool (installed as `tk`)
```

**Phase 1 -- Independent Apps** (`apps/`): Six standalone scripts that each do one thing. They have no dependencies on each other and can be used individually with `python main.py`.

**Phase 2 -- Combos** (`combos/`): Two scripts that compose Phase 1 apps together using `importlib` to load them directly. They wire up callbacks and data flow between apps.

**Phase 3 -- Final Tool** (`time_keeper/`): The installable Python package that refactors everything into a clean module structure with a Click-based CLI. This is what `pip install -e .` installs as the `tk` command.

## Phase 1 Apps

Each app is a standalone script in `apps/`. Run any of them with `python main.py --help` for usage.

### file-watcher

Watches a directory for file system changes and prints timestamped events. Filters out noise like `.git/`, `__pycache__/`, `node_modules/`, swap files, and `.DS_Store`.

```bash
cd apps/file-watcher
python main.py                             # Watch current directory
python main.py /path/to/repo               # Watch a specific path
python main.py . --ignore "*.log" "dist/*" # Add custom ignore patterns
```

Output:

```
Watching /Users/you/repos/project for changes... (Ctrl+C to stop)
2026-02-09T14:30:12 MODIFIED /Users/you/repos/project/src/main.py
2026-02-09T14:30:15 CREATED /Users/you/repos/project/src/utils.py
```

Default ignore patterns: `.git/*`, `__pycache__/*`, `node_modules/*`, `*.pyc`, `.DS_Store`, `*.swp`, `*.swo`, `*~`

### sqlite-store

CRUD interface for sessions and activity logs in the SQLite database.

```bash
cd apps/sqlite-store
python main.py create-session /path/to/repo                # Auto-names project from dir
python main.py create-session /path/to/repo --project "x"  # Custom project name
python main.py stop-session 1                              # Stop session by ID
python main.py list-sessions                               # List all sessions
python main.py list-sessions --status active               # Filter by status
python main.py show-session 1                              # Show session with activity log
python main.py log-activity 1 file_modified "src/main.py"  # Log an event
```

### git-summarizer

Extracts and formats git commit history for a repository and time range. Output is markdown.

```bash
cd apps/git-summarizer
python main.py                             # All commits in current repo
python main.py /path/to/repo               # Specific repo
python main.py . --today                   # Today's commits
python main.py . --week                    # Past 7 days
python main.py . --since 2026-02-01       # From a date
python main.py . --since 2026-02-01 --until 2026-02-07
```

### session-timer

A lightweight session timer with idle timeout, pause, and resume. Stores state in a JSON file (no database dependency).

```bash
cd apps/session-timer
python main.py start                        # Start timing (current directory)
python main.py start --repo /path/to/repo   # Start for a specific repo
python main.py start --idle-timeout 10      # Custom idle timeout (default: 15 min)
python main.py status                       # Show elapsed time and idle state
python main.py touch                        # Record activity (resets idle timer, resumes if paused)
python main.py stop                         # Stop and show total duration
```

State is stored at `~/.time-keeper/session-timer-state.json`. The timer auto-pauses when the idle timeout is exceeded (checked on `status`). Use `touch` to signal activity and resume a paused session.

### claude-parser

Parses Claude Code conversation history from `~/.claude/projects/` and extracts summaries including topics, message counts, tools used, and files touched.

```bash
cd apps/claude-parser
python main.py                                          # Summarize all sessions across all projects
python main.py --project-dir /path/to/repo              # Filter to sessions for a specific project
python main.py --list                                   # List sessions (compact format)
python main.py --list --project-dir /path/to/repo       # List sessions for a project
python main.py --session SESSION_ID                     # Parse a specific session by ID
python main.py --since 2026-02-01                       # Filter by date range
python main.py --since 2026-02-01 --until 2026-02-07
```

### report-generator

Generates summary and detailed reports from the time-keeper database. Requires that sessions already exist in the database (created by sqlite-store or the `tk` CLI).

```bash
cd apps/report-generator
python main.py summary                    # Summary grouped by project
python main.py summary --today            # Today only
python main.py summary --week             # Past 7 days
python main.py summary --project "x"      # Filter by project
python main.py detail                     # Detailed per-session breakdown
python main.py detail --week              # Detailed report for the past week
python main.py detail --since 2026-02-01 --until 2026-02-07
```

## Phase 2 Combos

Combos compose Phase 1 apps into higher-level workflows.

### active-tracker

Combines **file-watcher** + **session-timer** + **sqlite-store**. Watches a repo for file changes, auto-starts a database session on first activity, auto-pauses on idle, resumes on new activity, and stops cleanly on Ctrl+C.

```bash
cd combos/active-tracker
python main.py                              # Watch current directory
python main.py /path/to/repo                # Watch a specific repo
python main.py . --idle-timeout 10          # Custom idle timeout (default: 15 min)
python main.py . --project "client-api"     # Custom project name
```

This is the direct precursor to `tk watch`.

### work-summarizer

Combines **git-summarizer** + **claude-parser** + **sqlite-store**. Takes existing sessions from the database and enriches them with git commit history and Claude conversation summaries.

```bash
cd combos/work-summarizer
python main.py                              # Summarize all sessions
python main.py --session 3                  # Summarize a specific session
python main.py --today                      # Today's sessions
python main.py --week                       # Past 7 days
python main.py --since 2026-02-01 --until 2026-02-07
```

This is the precursor to `tk detail`.

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

The standalone file-watcher app supports adding custom patterns with `--ignore`. The `tk watch` command uses the built-in defaults.

### Claude Conversation Parsing

Claude conversations are read from `~/.claude/projects/`. The parser matches project directories by encoding the repo path (e.g., `/Users/you/repos/project` maps to a directory name containing `Users-you-repos-project`). No configuration is needed -- if Claude Code has been used in a repo, its conversations will be picked up automatically in detailed reports.

## Data

### Database Schema

**sessions**

| Column       | Type    | Description                              |
|--------------|---------|------------------------------------------|
| id           | INTEGER | Primary key, auto-increment              |
| repo_path    | TEXT    | Absolute path to the repository          |
| project_name | TEXT    | Project name (defaults to directory name) |
| start_time   | TEXT    | ISO 8601 UTC timestamp                   |
| end_time     | TEXT    | ISO 8601 UTC timestamp (NULL if active)  |
| status       | TEXT    | `active` or `stopped`                    |

**activity_log**

| Column     | Type    | Description                                    |
|------------|---------|------------------------------------------------|
| id         | INTEGER | Primary key, auto-increment                    |
| session_id | INTEGER | Foreign key to sessions.id                     |
| timestamp  | TEXT    | ISO 8601 UTC timestamp                         |
| event_type | TEXT    | Event type (e.g., `session_start`, `session_stop`, `session_pause`, `session_resume`, `file_modified`, `file_created`, `git_summary`, `claude_summary`) |
| detail     | TEXT    | Optional detail (e.g., relative file path)     |

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
