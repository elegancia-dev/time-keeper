# Database Schema

time-keeper stores all data in a single SQLite file at `~/.time-keeper/timekeeper.db`. The directory is created automatically on first use.

## Tables

### sessions

Tracks bounded work periods on a repository.

```sql
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_path TEXT NOT NULL,
    project_name TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT,
    status TEXT NOT NULL DEFAULT 'active'
);
```

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | INTEGER | No | Auto-incrementing primary key |
| `repo_path` | TEXT | No | Absolute path to the repository |
| `project_name` | TEXT | No | Project name (defaults to directory name) |
| `start_time` | TEXT | No | ISO 8601 UTC timestamp |
| `end_time` | TEXT | Yes | ISO 8601 UTC timestamp, NULL while active |
| `status` | TEXT | No | `active` or `stopped` |

### activity_log

Event log for file changes, session lifecycle events, and external data.

```sql
CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    detail TEXT,
    source TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);
```

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | INTEGER | No | Auto-incrementing primary key |
| `session_id` | INTEGER | Yes | Foreign key to `sessions.id`, NULL for standalone entries |
| `timestamp` | TEXT | No | ISO 8601 UTC timestamp |
| `event_type` | TEXT | No | Event type identifier (see below) |
| `detail` | TEXT | Yes | Optional detail string (e.g., relative file path) |
| `source` | TEXT | Yes | Which app logged this entry (e.g., `chrome-extension`) |

## Event Types

| Event Type | Description |
|-----------|-------------|
| `session_start` | Session was started |
| `session_stop` | Session was stopped |
| `session_pause` | Session was paused due to idle timeout |
| `session_resume` | Session was resumed after pause |
| `file_modified` | A file was modified in the watched repo |
| `file_created` | A file was created in the watched repo |
| `git_summary` | Git commit summary was attached |
| `claude_summary` | Claude conversation summary was attached |

## Relationships

```
sessions (1) ──── (N) activity_log
    │                      │
    └── id ◄──── session_id┘
```

`activity_log.session_id` is a foreign key to `sessions.id`. It is nullable to support standalone activity entries from external sources (e.g., Chrome extension via inbox ingestion).

## Indexing

SQLite automatically creates indexes on:
- `sessions.id` (PRIMARY KEY)
- `activity_log.id` (PRIMARY KEY)

No additional indexes are currently defined. The most common query patterns filter on `sessions.status` and `sessions.start_time`. As data grows, adding indexes on these columns would improve performance:

```sql
-- Potential future indexes
CREATE INDEX idx_sessions_status ON sessions(status);
CREATE INDEX idx_sessions_start_time ON sessions(start_time);
CREATE INDEX idx_activity_session_id ON activity_log(session_id);
```

## Timestamps

All timestamps are stored as ISO 8601 UTC strings (TEXT type, not SQLite DATETIME). This makes them:
- Human-readable in direct SQL queries
- Sortable with standard string comparison
- Parseable in Python with `datetime.fromisoformat()`

## Session Detection Logic

Sessions are detected and managed through two mechanisms:

1. **Manual** — `tk start` creates a session, `tk stop` ends it.
2. **Automatic** — `tk watch` starts a file watcher. On the first file event, a session is created. If no file events occur for the idle timeout period (default 15 minutes), the session is paused. New file activity resumes it. Ctrl+C stops the session.

Session state transitions:

```
(no session) ──file event──▶ active
active ──idle timeout──▶ paused (session_pause event logged)
paused ──file event──▶ active (session_resume event logged)
active ──tk stop / Ctrl+C──▶ stopped
```

## Data Maintenance

Old sessions can be exported to JSON and removed from the database:

```bash
tk db-export --before 2026-01-01
```

This exports matching sessions and their activity log entries to a dated JSON file in `~/.time-keeper/`, deletes them from the database, and runs `VACUUM` to reclaim disk space.
