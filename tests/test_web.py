"""Tests for the FastAPI web layer (generation mocked — no API call)."""

import pytest
from fastapi.testclient import TestClient

from qa_agents.models import StdResult
from qa_agents.spec_analyzer.models import AnalysisResult
from qa_agents.spec_analyzer.word_writer import write_report
from qa_agents.std_generator.excel_writer import write_workbook
from qa_agents.web import app as webapp
from qa_agents.web import store as webstore

client = TestClient(webapp.app)


@pytest.fixture(autouse=True)
def _isolate_db(tmp_path, monkeypatch):
    """Point the run store at a throwaway DB for every web test."""
    monkeypatch.setattr(webstore, "DB_PATH", tmp_path / "runs.db")


def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_index_is_served():
    res = client.get("/")
    assert res.status_code == 200
    assert "Run Agent" in res.text


def test_generate_returns_xlsx(tmp_path, monkeypatch):
    monkeypatch.setattr(
        webapp, "generate_std",
        lambda *a, **k: write_workbook(StdResult(), tmp_path / "o.xlsx"),
    )
    files = {"file": ("spec.docx", b"dummy", "application/octet-stream")}
    res = client.post("/api/generate", data={"tag": "40100"}, files=files)
    assert res.status_code == 200
    assert "spreadsheetml" in res.headers["content-type"]


def test_generate_maps_mode_and_output_type(tmp_path, monkeypatch):
    captured = {}

    def fake_generate(spec_path, tag, output_path, scenarios=True, sql=True):
        captured.update(tag=tag, output_path=str(output_path), scenarios=scenarios, sql=sql)
        return write_workbook(StdResult(), tmp_path / "o.xlsx")

    monkeypatch.setattr(webapp, "generate_std", fake_generate)
    files = {"file": ("spec.docx", b"dummy", "application/octet-stream")}
    res = client.post(
        "/api/generate",
        data={"mode": "whole", "task_number": "77", "output_type": "sql"},
        files=files,
    )
    assert res.status_code == 200
    assert captured["tag"] is None          # whole-spec mode
    assert captured["scenarios"] is False    # SQL only
    assert captured["sql"] is True
    assert "STD_77_sql" in captured["output_path"]  # unique path per run


def test_tag_mode_requires_tag():
    files = {"file": ("spec.docx", b"dummy", "application/octet-stream")}
    res = client.post(
        "/api/generate", data={"mode": "tag", "tag": "", "task_number": ""}, files=files
    )
    assert res.status_code == 400


def test_generate_rejects_unsupported_extension():
    files = {"file": ("spec.txt", b"dummy", "text/plain")}
    res = client.post("/api/generate", data={"tag": "999"}, files=files)
    assert res.status_code == 400


def test_agents_endpoint_lists_registered_agents():
    res = client.get("/api/agents")
    assert res.status_code == 200
    by_name = {a["name"]: a for a in res.json()}
    for name in ("std_generator", "spec_analyzer"):
        assert by_name[name]["display_name"]
        assert by_name[name]["description"]
        assert by_name[name]["output_format"]


def test_runs_endpoint_lists_a_generated_run(tmp_path, monkeypatch):
    monkeypatch.setattr(
        webapp, "generate_std",
        lambda *a, **k: write_workbook(StdResult(), tmp_path / "STD_x.xlsx"),
    )
    files = {"file": ("spec.docx", b"dummy", "application/octet-stream")}
    client.post("/api/generate", data={"tag": "40100", "output_type": "both"}, files=files)

    res = client.get("/api/runs")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["output_type"] == "both"
    assert data[0]["tag"] == "40100"


def test_download_missing_run_returns_404():
    res = client.get("/api/runs/999999/download")
    assert res.status_code == 404


def test_stats_endpoint():
    res = client.get("/api/stats")
    assert res.status_code == 200
    body = res.json()
    assert "total" in body
    assert set(body["by_type"]) == {"both", "scenarios", "sql"}


def test_feedback_categories_endpoint():
    res = client.get("/api/feedback/categories")
    assert res.status_code == 200
    cats = res.json()
    assert "Missing SQL" in cats
    assert "Other" in cats


def _make_run(tmp_path, monkeypatch) -> int:
    monkeypatch.setattr(
        webapp, "generate_std",
        lambda *a, **k: write_workbook(StdResult(), tmp_path / "o.xlsx"),
    )
    files = {"file": ("spec.docx", b"dummy", "application/octet-stream")}
    client.post("/api/generate", data={"tag": "40100"}, files=files)
    return client.get("/api/runs").json()[0]["id"]


def test_submit_and_list_feedback(tmp_path, monkeypatch):
    run_id = _make_run(tmp_path, monkeypatch)

    res = client.post(
        "/api/feedback",
        data={
            "run_id": run_id,
            "rating": "4",
            "categories": "Missing SQL,RTL Issue",
            "comment": "חסרים תסריטי קצה",
        },
    )
    assert res.status_code == 200

    items = client.get("/api/feedback").json()
    assert len(items) == 1
    assert items[0]["run_id"] == run_id
    assert items[0]["rating"] == 4
    assert items[0]["categories"] == ["Missing SQL", "RTL Issue"]
    # default triage fields
    assert items[0]["priority"] == "Medium"
    assert items[0]["status"] == "Open"


def test_submit_feedback_with_explicit_priority(tmp_path, monkeypatch):
    run_id = _make_run(tmp_path, monkeypatch)
    res = client.post("/api/feedback", data={"run_id": run_id, "priority": "High"})
    assert res.status_code == 200
    assert client.get("/api/feedback").json()[0]["priority"] == "High"


def test_submit_feedback_rejects_bad_priority(tmp_path, monkeypatch):
    run_id = _make_run(tmp_path, monkeypatch)
    res = client.post("/api/feedback", data={"run_id": run_id, "priority": "Urgent!!"})
    assert res.status_code == 400


def test_triage_updates_status_and_priority(tmp_path, monkeypatch):
    run_id = _make_run(tmp_path, monkeypatch)
    fid = client.post("/api/feedback", data={"run_id": run_id}).json()["id"]

    res = client.post(f"/api/feedback/{fid}", data={"status": "Resolved", "priority": "Low"})
    assert res.status_code == 200

    item = client.get("/api/feedback").json()[0]
    assert item["status"] == "Resolved"
    assert item["priority"] == "Low"


def test_triage_rejects_bad_status(tmp_path, monkeypatch):
    run_id = _make_run(tmp_path, monkeypatch)
    fid = client.post("/api/feedback", data={"run_id": run_id}).json()["id"]
    res = client.post(f"/api/feedback/{fid}", data={"status": "NotAStatus"})
    assert res.status_code == 400


def test_triage_missing_feedback_returns_404():
    res = client.post("/api/feedback/999999", data={"status": "Resolved"})
    assert res.status_code == 404


def test_quality_stats_shape():
    res = client.get("/api/quality-stats")
    assert res.status_code == 200
    body = res.json()
    for key in (
        "total_runs", "total_feedback", "open_feedback", "resolved_feedback",
        "avg_rating", "quality_score", "recent_ratings", "category_counts",
    ):
        assert key in body


def test_quality_stats_category_counts_include_action_text(tmp_path, monkeypatch):
    run_id = _make_run(tmp_path, monkeypatch)
    client.post("/api/feedback", data={"run_id": run_id, "categories": "Missing SQL"})

    body = client.get("/api/quality-stats").json()
    entry = next(e for e in body["category_counts"] if e["category"] == "Missing SQL")
    assert entry["count"] == 1
    assert entry["action"]  # non-empty suggested action text


def test_feedback_rejects_missing_run():
    res = client.post("/api/feedback", data={"run_id": 999999, "rating": "3"})
    assert res.status_code == 404


def test_feedback_rejects_bad_rating(tmp_path, monkeypatch):
    run_id = _make_run(tmp_path, monkeypatch)
    res = client.post("/api/feedback", data={"run_id": run_id, "rating": "9"})
    assert res.status_code == 400


def test_feedback_rejects_unknown_category(tmp_path, monkeypatch):
    run_id = _make_run(tmp_path, monkeypatch)
    res = client.post(
        "/api/feedback", data={"run_id": run_id, "categories": "Not A Real Category"}
    )
    assert res.status_code == 400


# ===== Spec Analyzer endpoint =====

def test_analyze_returns_docx(tmp_path, monkeypatch):
    monkeypatch.setattr(
        webapp, "generate_analysis",
        lambda *a, **k: write_report(AnalysisResult(), tmp_path / "o.docx"),
    )
    files = {"file": ("spec.docx", b"dummy", "application/octet-stream")}
    res = client.post("/api/analyze", data={"tag": "40100"}, files=files)
    assert res.status_code == 200
    assert "wordprocessingml" in res.headers["content-type"]


def test_analyze_defaults_to_whole_spec_when_tag_empty(tmp_path, monkeypatch):
    captured = {}

    def fake_analyze(spec_path, tag, output_path):
        captured["tag"] = tag
        return write_report(AnalysisResult(), tmp_path / "o.docx")

    monkeypatch.setattr(webapp, "generate_analysis", fake_analyze)
    files = {"file": ("spec.docx", b"dummy", "application/octet-stream")}
    res = client.post("/api/analyze", data={}, files=files)
    assert res.status_code == 200
    assert captured["tag"] is None


def test_analyze_rejects_unsupported_extension():
    files = {"file": ("spec.txt", b"dummy", "text/plain")}
    res = client.post("/api/analyze", data={}, files=files)
    assert res.status_code == 400


def test_analyze_run_appears_in_history_and_downloads_as_docx(tmp_path, monkeypatch):
    monkeypatch.setattr(
        webapp, "generate_analysis",
        lambda *a, **k: write_report(AnalysisResult(), tmp_path / "o.docx"),
    )
    files = {"file": ("spec.docx", b"dummy", "application/octet-stream")}
    client.post("/api/analyze", data={"tag": "40100"}, files=files)

    run = client.get("/api/runs").json()[0]
    assert run["output_type"] == "analysis"
    assert run["filename"].endswith(".docx")

    res = client.get(f"/api/runs/{run['id']}/download")
    assert res.status_code == 200
    assert "wordprocessingml" in res.headers["content-type"]
