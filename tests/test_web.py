"""Tests for the FastAPI web layer (generation mocked — no API call)."""

import pytest
from fastapi.testclient import TestClient

from qa_agents.models import StdResult
from qa_agents.spec_analyzer.models import AnalysisResult
from qa_agents.spec_analyzer.word_writer import write_report
from qa_agents.std_generator.excel_writer import write_workbook
from qa_agents.web import app as webapp
from qa_agents.web import auth as webauth
from qa_agents.web import store as webstore

client = TestClient(webapp.app)


@pytest.fixture(autouse=True)
def _isolate_db(tmp_path, monkeypatch):
    """Point the run store at a throwaway DB, seeded + logged in as admin,
    for every web test (most endpoints require a session)."""
    monkeypatch.setattr(webstore, "DB_PATH", tmp_path / "runs.db")
    webauth.ensure_default_admin()
    client.post("/api/login", data={"username": "admin", "password": "admin"})
    yield
    client.post("/api/logout")


def _login_as(username: str, password: str) -> None:
    res = client.post("/api/login", data={"username": username, "password": password})
    assert res.status_code == 200, res.text


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

    def fake_generate(spec_path, tag, output_path, agent=None, scenarios=True, sql=True, profile=None):
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


def test_agent_settings_defaults_to_null_model():
    res = client.get("/api/agent-settings")
    assert res.status_code == 200
    by_name = {a["name"]: a for a in res.json()}
    assert by_name["std_generator"]["model"] is None


def test_agent_settings_update_and_clear():
    res = client.post("/api/agent-settings/std_generator", data={"model": "claude-haiku-4-5"})
    assert res.status_code == 200

    by_name = {a["name"]: a for a in client.get("/api/agent-settings").json()}
    assert by_name["std_generator"]["model"] == "claude-haiku-4-5"

    res = client.post("/api/agent-settings/std_generator", data={"model": ""})
    assert res.status_code == 200
    by_name = {a["name"]: a for a in client.get("/api/agent-settings").json()}
    assert by_name["std_generator"]["model"] is None


def test_agent_settings_rejects_unknown_agent():
    res = client.post("/api/agent-settings/not-a-real-agent", data={"model": "claude-opus-5"})
    assert res.status_code == 404


def test_agent_settings_rejects_unknown_model():
    res = client.post("/api/agent-settings/std_generator", data={"model": "gpt-5"})
    assert res.status_code == 400


def test_generate_uses_configured_model(tmp_path, monkeypatch):
    captured = {}

    def fake_generate(spec_path, tag, output_path, agent=None, scenarios=True, sql=True, profile=None):
        captured["model"] = agent.model
        return write_workbook(StdResult(), tmp_path / "o.xlsx")

    monkeypatch.setattr(webapp, "generate_std", fake_generate)
    client.post("/api/agent-settings/std_generator", data={"model": "claude-haiku-4-5"})

    files = {"file": ("spec.docx", b"dummy", "application/octet-stream")}
    res = client.post("/api/generate", data={"tag": "40100"}, files=files)

    assert res.status_code == 200
    assert captured["model"] == "claude-haiku-4-5"


def test_profiles_endpoint_lists_both_profiles():
    res = client.get("/api/profiles")
    assert res.status_code == 200
    names = {p["name"] for p in res.json()}
    assert names == {"crm-hebrew", "ecommerce-english"}


def test_generate_rejects_unknown_profile():
    files = {"file": ("spec.docx", b"dummy", "application/octet-stream")}
    res = client.post(
        "/api/generate", data={"tag": "40100", "profile": "not-a-real-profile"}, files=files
    )
    assert res.status_code == 400


def test_generate_passes_selected_profile_through(tmp_path, monkeypatch):
    captured = {}

    def fake_generate(spec_path, tag, output_path, agent=None, scenarios=True, sql=True, profile=None):
        captured["profile"] = profile.name
        return write_workbook(StdResult(), tmp_path / "o.xlsx")

    monkeypatch.setattr(webapp, "generate_std", fake_generate)
    files = {"file": ("spec.docx", b"dummy", "application/octet-stream")}
    res = client.post(
        "/api/generate",
        data={"tag": "40100", "profile": "ecommerce-english"},
        files=files,
    )
    assert res.status_code == 200
    assert captured["profile"] == "ecommerce-english"


def test_agents_endpoint_lists_registered_agents():
    res = client.get("/api/agents")
    assert res.status_code == 200
    by_name = {a["name"]: a for a in res.json()}
    for name in ("std_generator", "spec_analyzer"):
        assert by_name[name]["display_name"]
        assert by_name[name]["description"]
        assert by_name[name]["output_format"]
        # both agents accept the same input formats (extraction.SUPPORTED)
        assert set(by_name[name]["input_formats"]) == {".docx", ".xlsx", ".pdf"}


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

    def fake_analyze(spec_path, tag, output_path, agent=None):
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


# ===== Auth =====

def _create_user(username: str, password: str, role: str = "user") -> int:
    res = client.post("/api/users", data={"username": username, "password": password, "role": role})
    assert res.status_code == 200, res.text
    return res.json()["id"]


def test_index_and_health_are_public():
    client.post("/api/logout")
    assert client.get("/").status_code == 200
    assert client.get("/api/health").status_code == 200


def test_me_requires_login():
    client.post("/api/logout")
    assert client.get("/api/me").status_code == 401


def test_login_wrong_password_rejected():
    res = client.post("/api/login", data={"username": "admin", "password": "wrong"})
    assert res.status_code == 401


def test_login_unknown_username_rejected():
    res = client.post("/api/login", data={"username": "nobody", "password": "x"})
    assert res.status_code == 401


def test_login_success_reflected_in_me():
    res = client.get("/api/me")
    assert res.status_code == 200
    body = res.json()
    assert body["username"] == "admin"
    assert body["role"] == "admin"
    assert body["agent_access"] == []


def test_logout_clears_session():
    client.post("/api/logout")
    assert client.get("/api/me").status_code == 401
    _login_as("admin", "admin")  # restore for fixture teardown


def test_non_admin_can_list_feedback_scoped_to_their_own():
    _create_user("regular1", "pw")
    _login_as("regular1", "pw")
    res = client.get("/api/feedback")
    assert res.status_code == 200
    assert res.json() == []  # hasn't submitted any feedback yet


def test_non_admin_cannot_access_agent_settings():
    _create_user("regular2", "pw")
    _login_as("regular2", "pw")
    assert client.get("/api/agent-settings").status_code == 403


def test_non_admin_cannot_access_quality_stats():
    _create_user("regular3", "pw")
    _login_as("regular3", "pw")
    assert client.get("/api/quality-stats").status_code == 403


def test_non_admin_cannot_manage_users():
    _create_user("regular4", "pw")
    _login_as("regular4", "pw")
    assert client.get("/api/users").status_code == 403


def test_regular_user_can_run_agents_by_default(tmp_path, monkeypatch):
    monkeypatch.setattr(
        webapp, "generate_std",
        lambda *a, **k: write_workbook(StdResult(), tmp_path / "o.xlsx"),
    )
    _create_user("regular5", "pw")
    _login_as("regular5", "pw")
    files = {"file": ("spec.docx", b"dummy", "application/octet-stream")}
    res = client.post("/api/generate", data={"tag": "40100"}, files=files)
    assert res.status_code == 200


def test_agent_access_restricts_generate_and_analyze(tmp_path, monkeypatch):
    uid = _create_user("restricted1", "pw")
    webstore.set_user_agent_access(uid, ["spec_analyzer"])
    monkeypatch.setattr(
        webapp, "generate_analysis",
        lambda *a, **k: write_report(AnalysisResult(), tmp_path / "o.docx"),
    )
    _login_as("restricted1", "pw")

    files = {"file": ("spec.docx", b"dummy", "application/octet-stream")}
    res = client.post("/api/generate", data={"tag": "40100"}, files=files)
    assert res.status_code == 403

    res = client.post("/api/analyze", data={"tag": "40100"}, files=files)
    assert res.status_code == 200


def test_agents_endpoint_filtered_by_access():
    uid = _create_user("restricted2", "pw")
    webstore.set_user_agent_access(uid, ["spec_analyzer"])
    _login_as("restricted2", "pw")
    names = {a["name"] for a in client.get("/api/agents").json()}
    assert names == {"spec_analyzer"}


def test_create_user_rejects_duplicate_username():
    _create_user("dupe", "pw")
    res = client.post("/api/users", data={"username": "dupe", "password": "pw2", "role": "user"})
    assert res.status_code == 400


def test_create_user_rejects_invalid_role():
    res = client.post("/api/users", data={"username": "badrole", "password": "pw", "role": "superadmin"})
    assert res.status_code == 400


def test_update_user_role():
    uid = _create_user("promote-me", "pw")
    res = client.post(f"/api/users/{uid}", data={"role": "admin"})
    assert res.status_code == 200
    assert next(u for u in client.get("/api/users").json() if u["id"] == uid)["role"] == "admin"


def test_cannot_demote_self():
    me = client.get("/api/me").json()
    res = client.post(f"/api/users/{me['id']}", data={"role": "user"})
    assert res.status_code == 400


def test_cannot_delete_self():
    me = client.get("/api/me").json()
    res = client.delete(f"/api/users/{me['id']}")
    assert res.status_code == 400


def test_cannot_delete_last_admin():
    # the only admin is the current user, already covered by test_cannot_delete_self;
    # this covers deleting the last admin via a DIFFERENT admin session
    uid = _create_user("second-admin", "pw", role="admin")
    _login_as("second-admin", "pw")
    admins = [u for u in client.get("/api/users").json() if u["role"] == "admin"]
    for a in admins:
        if a["username"] != "second-admin":
            res = client.delete(f"/api/users/{a['id']}")
            assert res.status_code == 200
    # now second-admin is the only admin left (the original "admin" was deleted above) —
    # demoting the last admin is blocked
    res = client.post(f"/api/users/{uid}", data={"role": "user"})
    assert res.status_code == 400


def test_delete_user():
    uid = _create_user("to-delete", "pw")
    res = client.delete(f"/api/users/{uid}")
    assert res.status_code == 200
    assert all(u["id"] != uid for u in client.get("/api/users").json())


# ===== Per-user data isolation (item 3) =====

def test_non_admin_sees_only_own_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(
        webapp, "generate_std",
        lambda *a, **k: write_workbook(StdResult(), tmp_path / "o.xlsx"),
    )
    admin_run_id = _make_run(tmp_path, monkeypatch)  # created while logged in as admin

    _create_user("owner1", "pw")
    _login_as("owner1", "pw")
    own_run_id = _make_run(tmp_path, monkeypatch)  # created while logged in as owner1

    visible_ids = {r["id"] for r in client.get("/api/runs").json()}
    assert visible_ids == {own_run_id}
    assert admin_run_id not in visible_ids


def test_admin_sees_every_users_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(
        webapp, "generate_std",
        lambda *a, **k: write_workbook(StdResult(), tmp_path / "o.xlsx"),
    )
    admin_run_id = _make_run(tmp_path, monkeypatch)

    _create_user("owner2", "pw")
    _login_as("owner2", "pw")
    own_run_id = _make_run(tmp_path, monkeypatch)

    _login_as("admin", "admin")
    visible_ids = {r["id"] for r in client.get("/api/runs").json()}
    assert {admin_run_id, own_run_id} <= visible_ids


def test_non_admin_cannot_download_others_run(tmp_path, monkeypatch):
    monkeypatch.setattr(
        webapp, "generate_std",
        lambda *a, **k: write_workbook(StdResult(), tmp_path / "o.xlsx"),
    )
    admin_run_id = _make_run(tmp_path, monkeypatch)

    _create_user("owner3", "pw")
    _login_as("owner3", "pw")
    res = client.get(f"/api/runs/{admin_run_id}/download")
    assert res.status_code == 404


def test_admin_can_download_any_users_run(tmp_path, monkeypatch):
    monkeypatch.setattr(
        webapp, "generate_std",
        lambda *a, **k: write_workbook(StdResult(), tmp_path / "o.xlsx"),
    )
    _create_user("owner4", "pw")
    _login_as("owner4", "pw")
    own_run_id = _make_run(tmp_path, monkeypatch)

    _login_as("admin", "admin")
    res = client.get(f"/api/runs/{own_run_id}/download")
    assert res.status_code == 200


def test_non_admin_stats_scoped_to_own_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(
        webapp, "generate_std",
        lambda *a, **k: write_workbook(StdResult(), tmp_path / "o.xlsx"),
    )
    _make_run(tmp_path, monkeypatch)  # admin's run

    _create_user("owner5", "pw")
    _login_as("owner5", "pw")
    assert client.get("/api/stats").json()["total"] == 0
    _make_run(tmp_path, monkeypatch)
    assert client.get("/api/stats").json()["total"] == 1


def test_non_admin_cannot_submit_feedback_on_others_run(tmp_path, monkeypatch):
    monkeypatch.setattr(
        webapp, "generate_std",
        lambda *a, **k: write_workbook(StdResult(), tmp_path / "o.xlsx"),
    )
    admin_run_id = _make_run(tmp_path, monkeypatch)

    _create_user("owner6", "pw")
    _login_as("owner6", "pw")
    res = client.post("/api/feedback", data={"run_id": admin_run_id, "rating": "5"})
    assert res.status_code == 404


def test_feedback_list_scoped_to_submitter_admin_sees_all(tmp_path, monkeypatch):
    monkeypatch.setattr(
        webapp, "generate_std",
        lambda *a, **k: write_workbook(StdResult(), tmp_path / "o.xlsx"),
    )
    _create_user("owner7", "pw")
    _login_as("owner7", "pw")
    own_run_id = _make_run(tmp_path, monkeypatch)
    fid = client.post("/api/feedback", data={"run_id": own_run_id, "rating": "4"}).json()["id"]

    assert {f["id"] for f in client.get("/api/feedback").json()} == {fid}

    _login_as("admin", "admin")
    assert fid in {f["id"] for f in client.get("/api/feedback").json()}
