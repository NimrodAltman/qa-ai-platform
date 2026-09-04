"""Tests for the SQLite run store."""

import sqlite3

import pytest

from qa_agents.web import store


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "runs.db")


def test_add_and_list_run():
    rid = store.add_run("40100", "40100", "both", "output/STD_40100_scenarios_sql.xlsx")
    runs = store.list_runs()
    assert len(runs) == 1
    assert runs[0]["id"] == rid
    assert runs[0]["output_type"] == "both"
    assert runs[0]["filename"] == "STD_40100_scenarios_sql.xlsx"
    assert runs[0]["status"] == "completed"


def test_get_run_and_missing():
    rid = store.add_run(None, "77", "sql", "output/STD_77_sql.xlsx")
    run = store.get_run(rid)
    assert run["task_number"] == "77"
    assert run["tag"] is None
    assert store.get_run(9999) is None


def test_agent_model_defaults_to_none():
    assert store.get_agent_model("std_generator") is None


def test_agent_model_set_and_clear():
    store.set_agent_model("std_generator", "claude-haiku-4-5")
    assert store.get_agent_model("std_generator") == "claude-haiku-4-5"

    store.set_agent_model("std_generator", "claude-sonnet-5")  # overwrite
    assert store.get_agent_model("std_generator") == "claude-sonnet-5"

    store.set_agent_model("std_generator", None)  # clear
    assert store.get_agent_model("std_generator") is None


def test_list_is_newest_first():
    store.add_run("1", "1", "both", "output/a.xlsx")
    second = store.add_run("2", "2", "sql", "output/b.xlsx")
    assert store.list_runs()[0]["id"] == second


def test_run_stats_counts_by_type():
    store.add_run("1", "1", "both", "output/a.xlsx")
    store.add_run("2", "2", "both", "output/b.xlsx")
    store.add_run("3", "3", "sql", "output/c.xlsx")
    stats = store.run_stats()
    assert stats["total"] == 3
    assert stats["by_type"] == {"both": 2, "scenarios": 0, "sql": 1}


def test_add_and_list_feedback():
    rid = store.add_run("1", "1", "both", "output/a.xlsx")
    fid = store.add_feedback(rid, 4, ["Missing SQL", "RTL Issue"], "חסרים תסריטי קצה")
    items = store.list_feedback()
    assert len(items) == 1
    assert items[0]["id"] == fid
    assert items[0]["run_id"] == rid
    assert items[0]["run_filename"] == "a.xlsx"
    assert items[0]["rating"] == 4
    assert items[0]["categories"] == ["Missing SQL", "RTL Issue"]
    assert items[0]["comment"] == "חסרים תסריטי קצה"
    # default triage fields
    assert items[0]["priority"] == "Medium"
    assert items[0]["status"] == "Open"


def test_add_feedback_with_explicit_priority():
    rid = store.add_run("1", "1", "both", "output/a.xlsx")
    fid = store.add_feedback(rid, 5, [], "", priority="High")
    assert store.get_feedback(fid)["priority"] == "High"


def test_update_feedback_status_and_priority():
    rid = store.add_run("1", "1", "both", "output/a.xlsx")
    fid = store.add_feedback(rid, 2, [], "בעיה")
    assert store.update_feedback(fid, status="Resolved", priority="Low") is True
    item = store.get_feedback(fid)
    assert item["status"] == "Resolved"
    assert item["priority"] == "Low"


def test_update_feedback_partial_leaves_other_field():
    rid = store.add_run("1", "1", "both", "output/a.xlsx")
    fid = store.add_feedback(rid, 2, [], "", priority="High")
    store.update_feedback(fid, status="Reviewed")  # priority not touched
    item = store.get_feedback(fid)
    assert item["status"] == "Reviewed"
    assert item["priority"] == "High"


def test_update_feedback_missing_returns_false():
    assert store.update_feedback(9999, status="Resolved") is False


def test_get_feedback_missing_returns_none():
    assert store.get_feedback(9999) is None


def test_health_stats_counts_and_score():
    rid = store.add_run("1", "1", "both", "output/a.xlsx")
    f1 = store.add_feedback(rid, 4, [], "")
    store.add_feedback(rid, 2, [], "")
    store.update_feedback(f1, status="Resolved")

    stats = store.health_stats()
    assert stats["total_runs"] == 1
    assert stats["total_feedback"] == 2
    assert stats["open_feedback"] == 1
    assert stats["resolved_feedback"] == 1
    assert stats["avg_rating"] == 3.0
    assert stats["quality_score"] == 60  # 3/5 * 100


def test_health_stats_no_ratings_yields_none():
    stats = store.health_stats()
    assert stats["avg_rating"] is None
    assert stats["quality_score"] is None


def test_health_stats_category_counts_sorted_descending():
    rid = store.add_run("1", "1", "both", "output/a.xlsx")
    store.add_feedback(rid, 3, ["Missing SQL", "RTL Issue"], "")
    store.add_feedback(rid, 3, ["Missing SQL"], "")
    store.add_feedback(rid, 3, ["Other"], "")

    counts = store.health_stats()["category_counts"]
    assert counts[0] == {"category": "Missing SQL", "count": 2}
    assert {"category": "RTL Issue", "count": 1} in counts
    assert {"category": "Other", "count": 1} in counts


def test_health_stats_recent_ratings_oldest_first_and_limited():
    rid = store.add_run("1", "1", "both", "output/a.xlsx")
    for rating in [1, 2, 3, 4, 5]:
        store.add_feedback(rid, rating, [], "")

    recent = store.health_stats(recent_limit=3)["recent_ratings"]
    assert [r["rating"] for r in recent] == [3, 4, 5]  # oldest-first among the last 3


def test_migrates_pre_existing_db_without_priority_status(tmp_path, monkeypatch):
    """A DB created before priority/status existed must still work (ALTER TABLE)."""
    db_path = tmp_path / "old.db"
    monkeypatch.setattr(store, "DB_PATH", db_path)
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, tag TEXT,
            task_number TEXT, output_type TEXT NOT NULL, filename TEXT NOT NULL,
            path TEXT NOT NULL, status TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER NOT NULL,
            created_at TEXT NOT NULL, rating INTEGER,
            categories TEXT NOT NULL, comment TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()

    rid = store.add_run("1", "1", "both", "output/a.xlsx")
    fid = store.add_feedback(rid, 3, [], "old-schema row")
    item = store.get_feedback(fid)
    assert item["priority"] == "Medium"
    assert item["status"] == "Open"


def test_feedback_is_newest_first():
    rid = store.add_run("1", "1", "both", "output/a.xlsx")
    store.add_feedback(rid, 3, [], "")
    second = store.add_feedback(rid, 5, [], "")
    assert store.list_feedback()[0]["id"] == second


# ===== users =====

def test_create_and_get_user():
    uid = store.create_user("alice", "hash", "salt", "user")
    user = store.get_user(uid)
    assert user["username"] == "alice"
    assert user["role"] == "user"
    assert store.get_user_by_username("alice")["id"] == uid
    assert store.get_user_by_username("nobody") is None


def test_duplicate_username_raises():
    store.create_user("bob", "hash", "salt", "user")
    with pytest.raises(sqlite3.IntegrityError):
        store.create_user("bob", "hash2", "salt2", "user")


def test_list_users_excludes_password_fields():
    store.create_user("carol", "supersecret-hash", "salt", "admin")
    users = store.list_users()
    assert len(users) == 1
    assert "password_hash" not in users[0]
    assert "salt" not in users[0]


def test_set_user_role():
    uid = store.create_user("dave", "hash", "salt", "user")
    assert store.set_user_role(uid, "admin") is True
    assert store.get_user(uid)["role"] == "admin"
    assert store.set_user_role(999999, "admin") is False


def test_delete_user_and_cascades_agent_access():
    uid = store.create_user("erin", "hash", "salt", "user")
    store.set_user_agent_access(uid, ["std_generator"])
    assert store.delete_user(uid) is True
    assert store.get_user(uid) is None
    assert store.get_user_agent_access(uid) == []
    assert store.delete_user(999999) is False


def test_agent_access_defaults_to_empty_meaning_all():
    uid = store.create_user("frank", "hash", "salt", "user")
    assert store.get_user_agent_access(uid) == []


def test_agent_access_set_and_replace():
    uid = store.create_user("gina", "hash", "salt", "user")
    store.set_user_agent_access(uid, ["std_generator", "spec_analyzer"])
    assert set(store.get_user_agent_access(uid)) == {"std_generator", "spec_analyzer"}

    store.set_user_agent_access(uid, ["spec_analyzer"])  # replaces, not appends
    assert store.get_user_agent_access(uid) == ["spec_analyzer"]

    store.set_user_agent_access(uid, [])  # clears back to "all"
    assert store.get_user_agent_access(uid) == []
