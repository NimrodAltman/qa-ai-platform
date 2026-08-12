"""Persistent record of agent runs, backed by SQLite (stdlib, no dependency).

Every generation is recorded so the Output Center can list past runs and
re-download their outputs. The database lives under ``output/`` (gitignored).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

# Module-level so tests can point it at a temp file.
DB_PATH = Path("output/runs.db")

# Admin triage fields on a feedback item.
PRIORITIES = ["Low", "Medium", "High"]
STATUSES = ["Open", "Reviewed", "Resolved"]


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    """Add ``column`` to ``table`` if an older on-disk DB doesn't have it yet."""
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at   TEXT NOT NULL,
            tag          TEXT,
            task_number  TEXT,
            output_type  TEXT NOT NULL,
            filename     TEXT NOT NULL,
            path         TEXT NOT NULL,
            status       TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS feedback (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id       INTEGER NOT NULL REFERENCES runs (id),
            created_at   TEXT NOT NULL,
            rating       INTEGER,
            categories   TEXT NOT NULL,
            comment      TEXT NOT NULL,
            priority     TEXT NOT NULL DEFAULT 'Medium',
            status       TEXT NOT NULL DEFAULT 'Open'
        )
        """
    )
    # Migrate DBs created before priority/status existed.
    _ensure_column(conn, "feedback", "priority", "priority TEXT NOT NULL DEFAULT 'Medium'")
    _ensure_column(conn, "feedback", "status", "status TEXT NOT NULL DEFAULT 'Open'")
    return conn


def add_run(
    tag: str | None,
    task_number: str,
    output_type: str,
    path: str,
    filename: str | None = None,
    status: str = "completed",
) -> int:
    """Record a completed run and return its id.

    ``path`` is the (unique) file on disk; ``filename`` is the friendly name
    shown and used when downloading (defaults to the path's basename).
    """
    if filename is None:
        filename = Path(path).name
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO runs (created_at, tag, task_number, output_type, filename, path, status)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (created_at, tag, task_number, output_type, filename, path, status),
        )
        return int(cur.lastrowid)


def list_runs() -> list[dict]:
    """Return all runs, newest first."""
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM runs ORDER BY id DESC").fetchall()
        return [dict(row) for row in rows]


def get_run(run_id: int) -> dict | None:
    """Return a single run by id, or None."""
    with _connect() as conn:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return dict(row) if row else None


def add_feedback(
    run_id: int,
    rating: int | None,
    categories: list[str],
    comment: str,
    priority: str = "Medium",
) -> int:
    """Record feedback for a run and return its id. Starts with status 'Open'."""
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO feedback (run_id, created_at, rating, categories, comment, priority)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                run_id,
                created_at,
                rating,
                json.dumps(categories, ensure_ascii=False),
                comment,
                priority,
            ),
        )
        return int(cur.lastrowid)


def update_feedback(
    feedback_id: int, status: str | None = None, priority: str | None = None
) -> bool:
    """Update a feedback item's triage fields. Returns False if it doesn't exist."""
    fields, values = [], []
    if status is not None:
        fields.append("status = ?")
        values.append(status)
    if priority is not None:
        fields.append("priority = ?")
        values.append(priority)
    if not fields:
        return get_feedback(feedback_id) is not None
    values.append(feedback_id)
    with _connect() as conn:
        cur = conn.execute(f"UPDATE feedback SET {', '.join(fields)} WHERE id = ?", values)
        return cur.rowcount > 0


def get_feedback(feedback_id: int) -> dict | None:
    """Return a single feedback item by id, or None."""
    with _connect() as conn:
        row = conn.execute("SELECT * FROM feedback WHERE id = ?", (feedback_id,)).fetchone()
    if row is None:
        return None
    item = dict(row)
    item["categories"] = json.loads(item["categories"])
    return item


def list_feedback() -> list[dict]:
    """Return all feedback with its run's file name, newest first."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT feedback.*, runs.filename AS run_filename
            FROM feedback JOIN runs ON runs.id = feedback.run_id
            ORDER BY feedback.id DESC
            """
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["categories"] = json.loads(item["categories"])
        result.append(item)
    return result


def run_stats() -> dict:
    """Return aggregate counts for the dashboard."""
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        rows = conn.execute(
            "SELECT output_type, COUNT(*) AS c FROM runs GROUP BY output_type"
        ).fetchall()
    by_type = {"both": 0, "scenarios": 0, "sql": 0}
    for row in rows:
        by_type[row["output_type"]] = row["c"]
    return {"total": total, "by_type": by_type}
