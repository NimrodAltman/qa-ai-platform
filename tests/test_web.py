"""Tests for the FastAPI web layer (generation mocked — no API call)."""

import pytest
from fastapi.testclient import TestClient

from qa_agents.models import StdResult
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
