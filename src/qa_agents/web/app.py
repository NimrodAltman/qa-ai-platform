"""FastAPI application exposing the STD Generator over HTTP.

This is a thin wrapper: the UI uploads a specification and a task tag, the
server runs the existing ``generate_std`` pipeline, and returns the Excel file.
Run locally with:

    uvicorn qa_agents.web.app:app --reload

Requires ANTHROPIC_API_KEY (loaded from a local .env if present).
"""

from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from starlette.middleware.sessions import SessionMiddleware

from . import store
from .auth import (
    allowed_agent_names,
    ensure_default_admin,
    get_current_user,
    hash_password,
    require_admin,
    verify_password,
)
from ..base import get_agent, list_agents
from ..extraction import SUPPORTED
from ..llm import AVAILABLE_MODELS
from ..spec_analyzer.agent import SpecAnalyzerAgent
from ..spec_analyzer.pipeline import generate_analysis
from ..std_generator.agent import StdGeneratorAgent
from ..std_generator.pipeline import generate_std, output_suffix
from ..std_generator.profile import CRM_HEBREW, PROFILES

load_dotenv()  # pick up ANTHROPIC_API_KEY from a local .env for convenience
ensure_default_admin()  # first run only: seeds admin/admin if no users exist

app = FastAPI(title="QA AI Platform")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SESSION_SECRET", "dev-insecure-secret-change-me"),
)
_STATIC = Path(__file__).parent / "static"
_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

FEEDBACK_CATEGORIES = [
    "Missing Test Cases",
    "Missing SQL",
    "Wrong Business Logic",
    "Wrong Field Name",
    "Wrong Schema",
    "Formatting Issue",
    "RTL Issue",
    "Duplicate Scenario",
    "Wrong Expected Result",
    "Missing Negative Tests",
    "Missing Edge Cases",
    "Other",
]

# Suggested next step for whoever is improving the agent, shown next to each
# category's count on the Health Dashboard.
FEEDBACK_CATEGORY_ACTIONS = {
    "Missing Test Cases": "הרחב את כיסוי התסריטים בפרומפט",
    "Missing SQL": "חזק את חוקי ה-SQL בפרומפט",
    "Wrong Business Logic": "בדוק ועדכן את כללי הלוגיקה העסקית בפרומפט",
    "Wrong Field Name": "חזק את דרישת שם עברי + schema",
    "Wrong Schema": "שפר את דיוק החילוץ מהאפיון",
    "Formatting Issue": "בדוק את מנוע ה-Excel (עיצוב ויישור)",
    "RTL Issue": "בדוק את הגדרות ה-RTL בגיליון",
    "Duplicate Scenario": "הוסף הנחיה מפורשת למניעת כפילויות",
    "Wrong Expected Result": "בדוק דיוק בין התוצאה הצפויה לאפיון",
    "Missing Negative Tests": "חזק את דרישת הכיסוי השלילי",
    "Missing Edge Cases": "חזק את דרישת כיסוי הקצה",
    "Other": "עיין בהערה החופשית לפרטים",
}


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (_STATIC / "index.html").read_text(encoding="utf-8")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)) -> dict:
    user = store.get_user_by_username(username)
    if user is None or not verify_password(password, user["password_hash"], user["salt"]):
        raise HTTPException(status_code=401, detail="שם משתמש או סיסמה שגויים")
    request.session["user_id"] = user["id"]
    return {"username": user["username"], "role": user["role"]}


@app.post("/api/logout")
async def logout(request: Request) -> dict:
    request.session.clear()
    return {"ok": True}


@app.get("/api/me")
def me(user: dict = Depends(get_current_user)) -> dict:
    return {
        "id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "agent_access": store.get_user_agent_access(user["id"]),  # [] = every agent
    }


@app.post("/api/generate")
async def generate(
    file: UploadFile,
    user: dict = Depends(get_current_user),
    mode: str = Form("tag"),  # "tag" | "whole"
    tag: str = Form(""),
    task_number: str = Form(""),
    output_type: str = Form("both"),  # "both" | "scenarios" | "sql"
    profile: str = Form(CRM_HEBREW.name),
) -> FileResponse:
    allowed = allowed_agent_names(user)
    if allowed is not None and "std_generator" not in allowed:
        raise HTTPException(status_code=403, detail="אין הרשאה להריץ סוכן זה")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED:
        raise HTTPException(
            status_code=400,
            detail=f"סוג קובץ לא נתמך {suffix!r}. נתמכים: {', '.join(SUPPORTED)}",
        )
    if output_type not in ("both", "scenarios", "sql"):
        raise HTTPException(status_code=400, detail=f"output_type לא תקין: {output_type!r}")
    if profile not in PROFILES:
        raise HTTPException(status_code=400, detail=f"פרופיל לא תקין: {profile!r}")
    if mode == "tag" and not tag.strip():
        raise HTTPException(status_code=400, detail="במצב 'תיוג ספציפי' חובה להזין מספר תיוג")

    name_key = task_number.strip() or tag.strip()
    if not name_key:
        raise HTTPException(status_code=400, detail="חובה להזין מספר משימה או תיוג לשם הקובץ")

    scenarios = output_type in ("both", "scenarios")
    sql = output_type in ("both", "sql")
    agent_tag = tag.strip() if mode == "tag" else None
    out_suffix = output_suffix(scenarios, sql)
    display_name = f"STD_{name_key}_{out_suffix}.xlsx"
    # a unique path per run so repeated runs don't overwrite each other's output
    unique_path = f"output/STD_{name_key}_{out_suffix}_{uuid.uuid4().hex[:8]}.xlsx"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        spec_path = tmp.name

    try:
        chosen_profile = PROFILES[profile]
        agent = StdGeneratorAgent(
            model=store.get_agent_model("std_generator"), profile=chosen_profile
        )
        out = generate_std(
            spec_path, agent_tag, unique_path,
            agent=agent, scenarios=scenarios, sql=sql, profile=chosen_profile,
        )
    except Exception as exc:  # surface generation failures to the UI
        raise HTTPException(status_code=500, detail=f"ההפקה נכשלה: {exc}")

    store.add_run(
        tag.strip() or None, task_number.strip(), output_type, str(out), filename=display_name
    )
    return FileResponse(out, filename=display_name, media_type=_XLSX_MIME)


@app.post("/api/analyze")
async def analyze(
    file: UploadFile,
    user: dict = Depends(get_current_user),
    tag: str = Form(""),
    task_number: str = Form(""),
) -> FileResponse:
    """Run the Spec Analyzer agent. Empty ``tag`` analyzes the whole spec."""
    allowed = allowed_agent_names(user)
    if allowed is not None and "spec_analyzer" not in allowed:
        raise HTTPException(status_code=403, detail="אין הרשאה להריץ סוכן זה")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED:
        raise HTTPException(
            status_code=400,
            detail=f"סוג קובץ לא נתמך {suffix!r}. נתמכים: {', '.join(SUPPORTED)}",
        )

    name_key = task_number.strip() or tag.strip() or "full_spec"
    display_name = f"ANALYSIS_{name_key}.docx"
    # a unique path per run so repeated runs don't overwrite each other's output
    unique_path = f"output/ANALYSIS_{name_key}_{uuid.uuid4().hex[:8]}.docx"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        spec_path = tmp.name

    try:
        agent = SpecAnalyzerAgent(model=store.get_agent_model("spec_analyzer"))
        out = generate_analysis(spec_path, tag.strip() or None, unique_path, agent=agent)
    except Exception as exc:  # surface generation failures to the UI
        raise HTTPException(status_code=500, detail=f"הניתוח נכשל: {exc}")

    store.add_run(tag.strip() or None, task_number.strip(), "analysis", str(out), filename=display_name)
    return FileResponse(out, filename=display_name, media_type=_DOCX_MIME)


@app.get("/api/agents")
def agents(user: dict = Depends(get_current_user)) -> list[dict]:
    # every agent accepts the same input formats today (extraction.SUPPORTED);
    # exposed here so the Catalog doesn't have to hardcode it
    allowed = allowed_agent_names(user)
    result = list_agents()
    if allowed is not None:
        result = [a for a in result if a["name"] in allowed]
    return [{**a, "input_formats": list(SUPPORTED)} for a in result]


@app.get("/api/profiles")
def profiles(user: dict = Depends(get_current_user)) -> list[dict]:
    return [{"name": p.name, "display_name": p.display_name} for p in PROFILES.values()]


@app.get("/api/models")
def models(user: dict = Depends(get_current_user)) -> list[str]:
    return AVAILABLE_MODELS


@app.get("/api/agent-settings")
def agent_settings(admin: dict = Depends(require_admin)) -> list[dict]:
    """Per-agent config: current model override (None = use the global default)."""
    return [
        {
            "name": a["name"],
            "display_name": a["display_name"],
            "model": store.get_agent_model(a["name"]),
        }
        for a in list_agents()
    ]


@app.post("/api/agent-settings/{agent_name}")
async def update_agent_settings(
    agent_name: str, model: str = Form(""), admin: dict = Depends(require_admin)
) -> dict:
    """Set (or, with an empty ``model``, clear) an agent's model override."""
    try:
        get_agent(agent_name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"סוכן לא נמצא: {agent_name!r}")
    if model and model not in AVAILABLE_MODELS:
        raise HTTPException(status_code=400, detail=f"מודל לא תקין: {model!r}")
    store.set_agent_model(agent_name, model or None)
    return {"ok": True}


@app.get("/api/runs")
def runs(user: dict = Depends(get_current_user)) -> list[dict]:
    return store.list_runs()


@app.get("/api/stats")
def stats(user: dict = Depends(get_current_user)) -> dict:
    return store.run_stats()


_MIME_BY_SUFFIX = {".xlsx": _XLSX_MIME, ".docx": _DOCX_MIME}


@app.get("/api/runs/{run_id}/download")
def download_run(run_id: int, user: dict = Depends(get_current_user)) -> FileResponse:
    run = store.get_run(run_id)
    if run is None or not Path(run["path"]).is_file():
        raise HTTPException(status_code=404, detail="התוצר לא נמצא")
    suffix = Path(run["filename"]).suffix.lower()
    media_type = _MIME_BY_SUFFIX.get(suffix, "application/octet-stream")
    return FileResponse(run["path"], filename=run["filename"], media_type=media_type)


@app.get("/api/feedback/categories")
def feedback_categories(user: dict = Depends(get_current_user)) -> list[str]:
    return FEEDBACK_CATEGORIES


@app.post("/api/feedback")
async def submit_feedback(
    user: dict = Depends(get_current_user),
    run_id: int = Form(...),
    rating: str = Form(""),
    categories: str = Form(""),  # comma-separated category names
    comment: str = Form(""),
    priority: str = Form("Medium"),
) -> dict:
    if store.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="ההרצה לא נמצאה")

    rating_value = int(rating) if rating.strip() else None
    if rating_value is not None and not (1 <= rating_value <= 5):
        raise HTTPException(status_code=400, detail="הדירוג חייב להיות בין 1 ל-5")

    cats = [c.strip() for c in categories.split(",") if c.strip()]
    unknown = set(cats) - set(FEEDBACK_CATEGORIES)
    if unknown:
        raise HTTPException(status_code=400, detail=f"קטגוריות לא מוכרות: {', '.join(unknown)}")

    if priority not in store.PRIORITIES:
        raise HTTPException(status_code=400, detail=f"עדיפות לא תקינה: {priority!r}")

    fid = store.add_feedback(run_id, rating_value, cats, comment.strip(), priority=priority)
    return {"id": fid}


@app.get("/api/feedback")
def feedback(admin: dict = Depends(require_admin)) -> list[dict]:
    return store.list_feedback()


@app.post("/api/feedback/{feedback_id}")
async def triage_feedback(
    feedback_id: int,
    status: str = Form(""),
    priority: str = Form(""),
    admin: dict = Depends(require_admin),
) -> dict:
    """Admin triage: update a feedback item's status and/or priority."""
    if status and status not in store.STATUSES:
        raise HTTPException(status_code=400, detail=f"סטטוס לא תקין: {status!r}")
    if priority and priority not in store.PRIORITIES:
        raise HTTPException(status_code=400, detail=f"עדיפות לא תקינה: {priority!r}")

    updated = store.update_feedback(feedback_id, status=status or None, priority=priority or None)
    if not updated:
        raise HTTPException(status_code=404, detail="הפידבק לא נמצא")
    return {"ok": True}


@app.get("/api/quality-stats")
def quality_stats(admin: dict = Depends(require_admin)) -> dict:
    stats = store.health_stats()
    for entry in stats["category_counts"]:
        entry["action"] = FEEDBACK_CATEGORY_ACTIONS.get(entry["category"], "")
    return stats


@app.get("/api/users")
def users(admin: dict = Depends(require_admin)) -> list[dict]:
    return store.list_users()


@app.post("/api/users")
async def create_user_endpoint(
    admin: dict = Depends(require_admin),
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form("user"),
) -> dict:
    username = username.strip()
    if not username or not password:
        raise HTTPException(status_code=400, detail="שם משתמש וסיסמה הם שדות חובה")
    if role not in store.ROLES:
        raise HTTPException(status_code=400, detail=f"role לא תקין: {role!r}")
    if store.get_user_by_username(username) is not None:
        raise HTTPException(status_code=400, detail="שם המשתמש כבר תפוס")
    password_hash, salt = hash_password(password)
    uid = store.create_user(username, password_hash, salt, role)
    return {"id": uid}


@app.post("/api/users/{user_id}")
async def update_user_endpoint(
    user_id: int, role: str = Form(...), admin: dict = Depends(require_admin)
) -> dict:
    if role not in store.ROLES:
        raise HTTPException(status_code=400, detail=f"role לא תקין: {role!r}")
    target = store.get_user(user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="משתמש לא נמצא")
    if user_id == admin["id"] and role != "admin":
        raise HTTPException(status_code=400, detail="לא ניתן להסיר הרשאת אדמין מהמשתמש המחובר")
    if target["role"] == "admin" and role != "admin":
        remaining_admins = [u for u in store.list_users() if u["role"] == "admin"]
        if len(remaining_admins) <= 1:
            raise HTTPException(status_code=400, detail="לא ניתן להסיר את האדמין האחרון")
    store.set_user_role(user_id, role)
    return {"ok": True}


@app.delete("/api/users/{user_id}")
async def delete_user_endpoint(user_id: int, admin: dict = Depends(require_admin)) -> dict:
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="לא ניתן למחוק את המשתמש המחובר")
    target = store.get_user(user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="משתמש לא נמצא")
    if target["role"] == "admin":
        remaining_admins = [u for u in store.list_users() if u["role"] == "admin"]
        if len(remaining_admins) <= 1:
            raise HTTPException(status_code=400, detail="לא ניתן למחוק את האדמין האחרון")
    store.delete_user(user_id)
    return {"ok": True}
