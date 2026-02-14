# Architecture

This document describes the internal architecture of time-keeper.

## Overview

time-keeper is a local-first billable hour tracker. It watches file changes in repositories, detects work sessions, stores time data in SQLite, and generates reports enriched with git history and Claude Code conversation summaries.

All data stays on the user's machine. There is no network communication, no telemetry, and no external accounts required.

## System Components

```
┌──────────────────────────────────────────────────────┐
│                   CLI (cli.py)                        │
│           Click-based command interface               │
├──────────┬───────────┬───────────┬───────────────────┤
│          │           │           │                    │
│  Watcher │  Reports  │ Dashboard │  Menu Bar          │
│          │           │           │  (macOS)           │
├──────────┴───────────┴───────────┴───────────────────┤
│                                                       │
│              Enrichment Layer                         │
│         git.py          claude.py                    │
│                                                       │
├───────────────────────────────────────────────────────┤
│                                                       │
│              Storage Layer (store.py)                 │
│              SQLite via ~/.time-keeper/               │
│                                                       │
└───────────────────────────────────────────────────────┘
```

## Core Abstractions

### Activity Event

A single observable action: a file modification, a session start/stop, a pause, or a resume. Stored as a row in `activity_log` with a timestamp, event type, and optional detail string.

### Work Session

A bounded period of work on a specific repository. Has a start time, optional end time, a status (`active` or `stopped`), and a project name derived from the directory. Sessions are the primary unit of time tracking.

### Repository Context

A repository path that anchors a session. Used to locate git history and Claude conversation data for enrichment.

### Enrichment Layer

Git commits and Claude conversations are not stored in the time-keeper database. They are fetched on demand when generating reports:

- **git.py** shells out to `git log` for commit history in a time range
- **claude.py** reads JSONL files from `~/.claude/projects/` and extracts conversation metadata

This keeps the database simple and avoids duplicating data that already exists elsewhere.

### Report Snapshot

A formatted output (terminal text or markdown) combining session data, activity logs, git commits, and Claude summaries. Reports are generated fresh each time, never cached.

## Module Responsibilities

| Module | Responsibility |
|--------|---------------|
| `cli.py` | Click command definitions, argument parsing, output formatting |
| `store.py` | SQLite connection, schema creation, all CRUD operations |
| `watcher.py` | File system monitoring (watchdog), idle detection, session lifecycle |
| `reports.py` | Report generation: summary, detail, recap, day context |
| `git.py` | Git log extraction and markdown formatting |
| `claude.py` | Claude conversation JSONL parsing and summarization |
| `ingest.py` | JSON inbox processing for external time sources |
| `dashboard.py` | Rich-based live terminal UI |
| `menubar.py` | macOS menu bar app (rumps) |

## Data Flow

1. **Session creation** — User runs `tk start` or the watcher detects file activity. `store.create_session()` inserts a row into `sessions` and logs a `session_start` event.

2. **Activity tracking** — The watcher logs `file_modified`/`file_created` events to `activity_log`. Each event resets the idle timer.

3. **Idle detection** — The watcher checks elapsed time since the last file event every second. If the idle timeout (default 15 minutes) is exceeded, the session is paused. New file activity resumes it.

4. **Session stop** — User hits Ctrl+C or runs `tk stop`. `store.stop_session()` sets `end_time` and status to `stopped`.

5. **Report generation** — `reports.py` queries sessions and activities from the database, then enriches each session with git commits (via `git.py`) and Claude conversations (via `claude.py`). Output is formatted as terminal text.

6. **External ingestion** — The Chrome extension or other tools write JSON files to `~/.time-keeper/inbox/`. `tk ingest` processes these into standalone activity log entries (no associated session).

## Layer Separation

The architecture separates three concerns:

- **Core engine** — Session lifecycle and activity tracking (`store.py`, `watcher.py`)
- **Enrichment** — External data sources pulled in on demand (`git.py`, `claude.py`)
- **Presentation** — CLI, dashboard, menu bar, reports (`cli.py`, `dashboard.py`, `menubar.py`, `reports.py`)

This separation means new enrichment sources or presentation layers can be added without modifying the core engine.

## Design Decisions

- **SQLite, not a service** — No daemon, no server, no ports. A single file database that works offline.
- **Text timestamps** — ISO 8601 strings stored as TEXT, not SQLite DATETIME. Simple to query, sort, and debug.
- **No ORM** — Direct SQL via Python's built-in `sqlite3` module. Minimal dependencies.
- **Subprocess for git** — Shells out to `git log` rather than using a Python git library. Avoids a heavy dependency and works with any git version.
- **Nullable session_id** — Activity log entries can exist without a session, supporting external data sources (inbox ingestion).
