"""Tests for the SQLite run store."""

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
