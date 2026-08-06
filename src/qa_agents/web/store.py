"""Persistent record of agent runs, backed by SQLite (stdlib, no dependency).

Every generation is recorded so the Output Center can list past runs and
re-download their outputs. The database lives under ``output/`` (gitignored).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

# Module-level so tests can point it at a temp file.
DB_PATH = Path("output/runs.db")


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
    return conn


def add_run(
    tag: str | None,
    task_number: str,
    output_type: str,
    path: str,
    status: str = "completed",
) -> int:
    """Record a completed run and return its id."""
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
