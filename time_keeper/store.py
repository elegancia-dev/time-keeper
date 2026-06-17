"""Central SQLite storage for time-keeper sessions and activity logs."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


DB_DIR = Path.home() / ".time-keeper"
DB_PATH = DB_DIR / "timekeeper.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_path TEXT NOT NULL,
    project_name TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT,
    status TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    detail TEXT,
    source TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);
"""


def _migrate(conn: sqlite3.Connection) -> None:
    """Run schema migrations for existing databases."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(activity_log)").fetchall()}
    if "source" not in cols:
        conn.execute("ALTER TABLE activity_log ADD COLUMN source TEXT")
        conn.commit()

    # Check if session_id is nullable — recreate table if NOT NULL constraint exists
    for row in conn.execute("PRAGMA table_info(activity_log)").fetchall():
        if row[1] == "session_id" and row[3] == 1:  # notnull == 1
            conn.executescript("""
                CREATE TABLE activity_log_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    detail TEXT,
                    source TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                );
                INSERT INTO activity_log_new (id, session_id, timestamp, event_type, detail, source)
                    SELECT id, session_id, timestamp, event_type, detail, source FROM activity_log;
                DROP TABLE activity_log;
                ALTER TABLE activity_log_new RENAME TO activity_log;
            """)
            break


def get_db(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # WAL lets readers (dashboard, menubar) and writers (watchers) coexist
    # without "database is locked"; NORMAL sync is durable under WAL and far
    # cheaper than the default FULL fsync-per-commit; busy_timeout backstops
    # the rare concurrent-writer collision across processes.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_session(
    conn: sqlite3.Connection, repo_path: str, project_name: str | None = None
) -> int:
    repo = os.path.abspath(repo_path)
    project = project_name or os.path.basename(repo)
    cur = conn.execute(
        "INSERT INTO sessions (repo_path, project_name, start_time, status) VALUES (?, ?, ?, 'active')",
        (repo, project, now_iso()),
    )
    conn.commit()
    session_id = cur.lastrowid
    log_activity(conn, session_id, "session_start", f"Started session for {project}")
    return session_id


def stop_session(conn: sqlite3.Connection, session_id: int) -> bool:
    row = conn.execute(
        "SELECT status FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()
    if not row or row["status"] != "active":
        return False
    conn.execute(
        "UPDATE sessions SET end_time = ?, status = 'stopped' WHERE id = ?",
        (now_iso(), session_id),
    )
    conn.commit()
    log_activity(conn, session_id, "session_stop", "Session stopped")
    return True


def get_active_session(
    conn: sqlite3.Connection, repo_path: str | None = None
) -> dict | None:
    if repo_path:
        repo = os.path.abspath(repo_path)
        row = conn.execute(
            "SELECT * FROM sessions WHERE status = 'active' AND repo_path = ? ORDER BY start_time DESC LIMIT 1",
            (repo,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM sessions WHERE status = 'active' ORDER BY start_time DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else None


def list_sessions(conn: sqlite3.Connection, status: str | None = None) -> list[dict]:
    if status:
        rows = conn.execute(
            "SELECT * FROM sessions WHERE status = ? ORDER BY start_time DESC",
            (status,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM sessions ORDER BY start_time DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_session(conn: sqlite3.Connection, session_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if not row:
        return None
    session = dict(row)
    activities = conn.execute(
        "SELECT * FROM activity_log WHERE session_id = ? ORDER BY timestamp",
        (session_id,),
    ).fetchall()
    session["activities"] = [dict(a) for a in activities]
    return session


def log_activity(
    conn: sqlite3.Connection,
    session_id: int,
    event_type: str,
    detail: str | None = None,
) -> int:
    cur = conn.execute(
        "INSERT INTO activity_log (session_id, timestamp, event_type, detail) VALUES (?, ?, ?, ?)",
        (session_id, now_iso(), event_type, detail),
    )
    conn.commit()
    return cur.lastrowid


def log_activities_batch(
    conn: sqlite3.Connection,
    rows: list[tuple[int, str, str, str | None]],
) -> int:
    """Insert many activity rows in a single transaction.

    Each row is (session_id, timestamp, event_type, detail). Returns the
    number of rows written. Used by the watcher to flush buffered file
    events without an fsync per event.
    """
    if not rows:
        return 0
    conn.executemany(
        "INSERT INTO activity_log (session_id, timestamp, event_type, detail) VALUES (?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    return len(rows)


def query_sessions(
    conn: sqlite3.Connection,
    since: str | None = None,
    until: str | None = None,
    project: str | None = None,
) -> list[dict]:
    conditions = []
    params = []
    if since:
        conditions.append("start_time >= ?")
        params.append(since)
    if until:
        conditions.append("start_time <= ?")
        params.append(until + "T23:59:59")
    if project:
        conditions.append("project_name = ?")
        params.append(project)
    where = " AND ".join(conditions) if conditions else "1=1"
    rows = conn.execute(
        f"SELECT * FROM sessions WHERE {where} ORDER BY start_time", params
    ).fetchall()
    return [dict(r) for r in rows]


def query_activities(conn: sqlite3.Connection, session_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM activity_log WHERE session_id = ? ORDER BY timestamp",
        (session_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def list_projects(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT project_name, repo_path, COUNT(*) as session_count,
               SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active_count
        FROM sessions GROUP BY project_name, repo_path ORDER BY project_name
    """
    ).fetchall()
    return [dict(r) for r in rows]


def db_size_mb(db_path: Path | None = None) -> float:
    path = db_path or DB_PATH
    if not path.exists():
        return 0.0
    return path.stat().st_size / (1024 * 1024)


def check_db_size(threshold_mb: float = 100, db_path: Path | None = None) -> str | None:
    size = db_size_mb(db_path)
    if size >= threshold_mb:
        return (
            f"WARNING: Database is {size:.1f} MB (threshold: {threshold_mb} MB).\n"
            f"Run 'tk db-export --before DATE' to export old data and free space."
        )
    return None


def export_and_clean(
    conn: sqlite3.Connection, before_date: str, db_path: Path | None = None
) -> str:
    """Export sessions and activity older than before_date to JSON, then delete them."""
    export_dir = DB_DIR / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)

    sessions = conn.execute(
        "SELECT * FROM sessions WHERE start_time < ?", (before_date,)
    ).fetchall()
    sessions = [dict(r) for r in sessions]

    session_ids = [s["id"] for s in sessions]
    if not session_ids:
        return "No sessions found before that date."

    placeholders = ",".join("?" * len(session_ids))
    activities = conn.execute(
        f"SELECT * FROM activity_log WHERE session_id IN ({placeholders})",
        session_ids,
    ).fetchall()
    activities = [dict(r) for r in activities]

    export_data = {
        "exported_at": now_iso(),
        "before_date": before_date,
        "sessions": sessions,
        "activity_log": activities,
    }

    today = datetime.now().strftime("%Y-%m-%d")
    export_path = export_dir / f"export-{today}.json"
    with open(export_path, "w") as f:
        json.dump(export_data, f, indent=2, default=str)

    conn.execute(
        f"DELETE FROM activity_log WHERE session_id IN ({placeholders})",
        session_ids,
    )
    conn.execute(
        f"DELETE FROM sessions WHERE id IN ({placeholders})",
        session_ids,
    )
    conn.commit()
    conn.execute("VACUUM")

    return (
        f"Exported {len(sessions)} sessions and {len(activities)} activity records "
        f"to {export_path}\nDatabase vacuumed."
    )


def log_standalone_activity(
    conn: sqlite3.Connection,
    event_type: str,
    detail: str | None = None,
    source: str | None = None,
    timestamp: str | None = None,
) -> int:
    """Insert an activity with session_id=NULL (not tied to a watcher session)."""
    cur = conn.execute(
        "INSERT INTO activity_log (session_id, timestamp, event_type, detail, source) VALUES (NULL, ?, ?, ?, ?)",
        (timestamp or now_iso(), event_type, detail, source),
    )
    conn.commit()
    return cur.lastrowid


def get_activities_by_source(
    conn: sqlite3.Connection,
    source: str,
    since: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Query activities filtered by source."""
    conditions = ["source = ?"]
    params: list = [source]
    if since:
        conditions.append("timestamp >= ?")
        params.append(since)
    where = " AND ".join(conditions)
    query = f"SELECT * FROM activity_log WHERE {where} ORDER BY timestamp DESC"
    if limit:
        query += f" LIMIT {int(limit)}"
    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def get_projects_list(conn: sqlite3.Connection) -> list[str]:
    """Distinct project names from both sessions and standalone activity logs."""
    rows = conn.execute("""
        SELECT DISTINCT project_name AS name FROM sessions
        UNION
        SELECT DISTINCT json_extract(detail, '$.project') AS name
            FROM activity_log WHERE source IS NOT NULL AND json_valid(detail) AND json_extract(detail, '$.project') IS NOT NULL
        ORDER BY name
    """).fetchall()
    return [r["name"] for r in rows if r["name"]]
