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

ROLES = ["admin", "user"]


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
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_settings (
            agent_name   TEXT PRIMARY KEY,
            model        TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            username       TEXT NOT NULL UNIQUE,
            password_hash  TEXT NOT NULL,
            salt           TEXT NOT NULL,
            role           TEXT NOT NULL,
            created_at     TEXT NOT NULL
        )
        """
    )
    # A user with no rows here may run every agent; rows restrict them to a
    # specific set (schema in place now for a future per-agent-access screen).
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_agent_access (
            user_id      INTEGER NOT NULL REFERENCES users (id),
            agent_name   TEXT NOT NULL,
            PRIMARY KEY (user_id, agent_name)
        )
        """
    )
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


def get_agent_model(agent_name: str) -> str | None:
    """Return the configured model override for an agent, or None (use default)."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT model FROM agent_settings WHERE agent_name = ?", (agent_name,)
        ).fetchone()
        return row["model"] if row else None


def set_agent_model(agent_name: str, model: str | None) -> None:
    """Set (or clear, with ``None``) an agent's model override."""
    with _connect() as conn:
        conn.execute(
            "INSERT INTO agent_settings (agent_name, model) VALUES (?, ?)"
            " ON CONFLICT(agent_name) DO UPDATE SET model = excluded.model",
            (agent_name, model),
        )


def create_user(username: str, password_hash: str, salt: str, role: str) -> int:
    """Create a user and return its id. Raises sqlite3.IntegrityError if taken."""
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, salt, role, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (username, password_hash, salt, role, created_at),
        )
        return int(cur.lastrowid)


def get_user_by_username(username: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None


def get_user(user_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def list_users() -> list[dict]:
    """Return every user (without password fields), oldest first."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, username, role, created_at FROM users ORDER BY id"
        ).fetchall()
        return [dict(row) for row in rows]


def user_count() -> int:
    with _connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def set_user_role(user_id: int, role: str) -> bool:
    with _connect() as conn:
        cur = conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
        return cur.rowcount > 0


def delete_user(user_id: int) -> bool:
    with _connect() as conn:
        conn.execute("DELETE FROM user_agent_access WHERE user_id = ?", (user_id,))
        cur = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        return cur.rowcount > 0


def get_user_agent_access(user_id: int) -> list[str]:
    """Agent names this user is restricted to; an empty list means 'all agents'."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT agent_name FROM user_agent_access WHERE user_id = ?", (user_id,)
        ).fetchall()
        return [row["agent_name"] for row in rows]


def set_user_agent_access(user_id: int, agent_names: list[str]) -> None:
    """Replace this user's agent restriction list (empty = allow all)."""
    with _connect() as conn:
        conn.execute("DELETE FROM user_agent_access WHERE user_id = ?", (user_id,))
        conn.executemany(
            "INSERT INTO user_agent_access (user_id, agent_name) VALUES (?, ?)",
            [(user_id, name) for name in agent_names],
        )


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


def health_stats(recent_limit: int = 10) -> dict:
    """Aggregate quality metrics for the Health Dashboard.

    ``avg_rating`` / ``quality_score`` are ``None`` when no feedback has a
    rating yet. ``recent_ratings`` is oldest-first (for a left-to-right trend
    chart), capped at ``recent_limit``. ``category_counts`` is every category
    mentioned across all feedback, sorted by count descending.
    """
    with _connect() as conn:
        total_runs = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        total_feedback = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
        open_feedback = conn.execute(
            "SELECT COUNT(*) FROM feedback WHERE status = 'Open'"
        ).fetchone()[0]
        resolved_feedback = conn.execute(
            "SELECT COUNT(*) FROM feedback WHERE status = 'Resolved'"
        ).fetchone()[0]
        avg_rating = conn.execute(
            "SELECT AVG(rating) FROM feedback WHERE rating IS NOT NULL"
        ).fetchone()[0]
        recent_rows = conn.execute(
            "SELECT id, created_at, rating FROM feedback"
            " WHERE rating IS NOT NULL ORDER BY id DESC LIMIT ?",
            (recent_limit,),
        ).fetchall()
        category_rows = conn.execute("SELECT categories FROM feedback").fetchall()

    counts: dict[str, int] = {}
    for row in category_rows:
        for category in json.loads(row["categories"]):
            counts[category] = counts.get(category, 0) + 1
    category_counts = sorted(
        ({"category": c, "count": n} for c, n in counts.items()),
        key=lambda entry: (-entry["count"], entry["category"]),
    )

    return {
        "total_runs": total_runs,
        "total_feedback": total_feedback,
        "open_feedback": open_feedback,
        "resolved_feedback": resolved_feedback,
        "avg_rating": round(avg_rating, 2) if avg_rating is not None else None,
        "quality_score": round(avg_rating / 5 * 100) if avg_rating is not None else None,
        "recent_ratings": [
            {"id": r["id"], "created_at": r["created_at"], "rating": r["rating"]}
            for r in reversed(recent_rows)
        ],
        "category_counts": category_counts,
    }
