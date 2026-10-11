"""Guards for the stored-XSS fix: escaping in the UI, security headers.

The UI builds rows with string concatenation into innerHTML, and an admin
sees rows created by other users (their tags, file names, feedback
comments, usernames). Anything user-supplied must go through esc() first.
The escaping check is a source-level guard rather than a browser test —
there is no JS test runner in this project — so it asserts that each known
user-supplied field is only ever interpolated inside esc(...).
"""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from qa_agents.web import app as webapp
from qa_agents.web import auth as webauth
from qa_agents.web import store as webstore

INDEX_HTML = Path(webapp.__file__).parent / "static" / "index.html"

# Values that reach the browser from the database / another user.
USER_SUPPLIED_FIELDS = [
    "r.tag",
    "r.filename",
    "r.task_number",
    "f.comment",
    "f.run_filename",
    "f.categories.join(', ')",
    "u.username",
    "a.display_name",
    "a.description",
    "a.output_format",
    "a.name",
    "p.display_name",
    "c.category",
    "c.action",
]

client = TestClient(webapp.app)


@pytest.fixture(autouse=True)
def _isolate_db(tmp_path, monkeypatch):
    monkeypatch.setattr(webstore, "DB_PATH", tmp_path / "runs.db")
    password = webauth.ensure_default_admin()
    client.post("/api/login", data={"username": "admin", "password": password})
    yield
    client.post("/api/logout")


def test_escape_helper_exists():
    assert "function esc(" in INDEX_HTML.read_text(encoding="utf-8")


@pytest.mark.parametrize("field", USER_SUPPLIED_FIELDS)
def test_user_supplied_field_is_always_escaped(field):
    html = INDEX_HTML.read_text(encoding="utf-8")
    unescaped = []
    for match in re.finditer(re.escape(field), html):
        line_start = html.rfind("\n", 0, match.start()) + 1
        line_text = html[line_start:html.find("\n", match.start())]
        if "'<" not in line_text:
            continue  # not building markup on this line (e.g. a lookup table)
        before = html[max(0, match.start() - 60):match.start()]
        # the value must be inside an esc( call with nothing closing it first
        opened = before.rfind("esc(")
        if opened == -1 or ")" in before[opened + 4:]:
            unescaped.append(html[:match.start()].count("\n") + 1)
    assert not unescaped, f"{field} interpolated without esc() on line(s) {unescaped}"


def test_error_messages_reaching_innerhtml_are_escaped():
    """Server error details echo user input (e.g. an invalid profile name)."""
    for line in INDEX_HTML.read_text(encoding="utf-8").splitlines():
        if "innerHTML" in line and "err.message" in line:
            assert "esc(err.message)" in line, line.strip()


def test_security_headers_present_on_the_page():
    res = client.get("/")
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["x-frame-options"] == "DENY"
    assert res.headers["referrer-policy"] == "no-referrer"
    csp = res.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in csp
    assert "connect-src 'self'" in csp
    assert "default-src 'self'" in csp


def test_security_headers_present_on_api_responses():
    assert "content-security-policy" in client.get("/api/health").headers


def test_a_payload_stored_in_a_tag_comes_back_verbatim_for_the_ui_to_escape():
    """The API is JSON, so it stores and returns the payload as data; the
    escaping that makes it safe happens in the UI, checked above."""
    payload = "<img src=x onerror=alert(1)>"
    webstore.add_run(payload, "1", "both", "output/x.xlsx", filename="x.xlsx", user_id=1)
    tags = [r["tag"] for r in client.get("/api/runs").json()]
    assert payload in tags
