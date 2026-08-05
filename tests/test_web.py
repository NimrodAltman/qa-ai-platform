"""Tests for the FastAPI web layer (generation mocked — no API call)."""

from fastapi.testclient import TestClient

from qa_agents.models import StdResult
from qa_agents.std_generator.excel_writer import write_workbook
from qa_agents.web import app as webapp

client = TestClient(webapp.app)


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
    assert captured["output_path"].endswith("STD_77.xlsx")


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
