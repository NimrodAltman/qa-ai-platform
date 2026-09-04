"""FastAPI application exposing the STD Generator over HTTP.

This is a thin wrapper: the UI uploads a specification and a task tag, the
server runs the existing ``generate_std`` pipeline, and returns the Excel file.
Run locally with:

    uvicorn qa_agents.web.app:app --reload

Requires ANTHROPIC_API_KEY (loaded from a local .env if present).
"""

from __future__ import annotations

import shutil
import tempfile
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from . import store
from ..extraction import SUPPORTED
from ..spec_analyzer.pipeline import generate_analysis
from ..std_generator.pipeline import generate_std, output_suffix

load_dotenv()  # pick up ANTHROPIC_API_KEY from a local .env for convenience

app = FastAPI(title="QA AI Platform")
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


@app.post("/api/generate")
async def generate(
    file: UploadFile,
    mode: str = Form("tag"),  # "tag" | "whole"
    tag: str = Form(""),
    task_number: str = Form(""),
    output_type: str = Form("both"),  # "both" | "scenarios" | "sql"
) -> FileResponse:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED:
        raise HTTPException(
            status_code=400,
            detail=f"סוג קובץ לא נתמך {suffix!r}. נתמכים: {', '.join(SUPPORTED)}",
        )
    if output_type not in ("both", "scenarios", "sql"):
        raise HTTPException(status_code=400, detail=f"output_type לא תקין: {output_type!r}")
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
        out = generate_std(spec_path, agent_tag, unique_path, scenarios=scenarios, sql=sql)
    except Exception as exc:  # surface generation failures to the UI
        raise HTTPException(status_code=500, detail=f"ההפקה נכשלה: {exc}")

    store.add_run(
        tag.strip() or None, task_number.strip(), output_type, str(out), filename=display_name
    )
    return FileResponse(out, filename=display_name, media_type=_XLSX_MIME)


@app.post("/api/analyze")
async def analyze(
    file: UploadFile,
    tag: str = Form(""),
    task_number: str = Form(""),
) -> FileResponse:
    """Run the Spec Analyzer agent. Empty ``tag`` analyzes the whole spec."""
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
        out = generate_analysis(spec_path, tag.strip() or None, unique_path)
    except Exception as exc:  # surface generation failures to the UI
        raise HTTPException(status_code=500, detail=f"הניתוח נכשל: {exc}")

    store.add_run(tag.strip() or None, task_number.strip(), "analysis", str(out), filename=display_name)
    return FileResponse(out, filename=display_name, media_type=_DOCX_MIME)


@app.get("/api/runs")
def runs() -> list[dict]:
    return store.list_runs()


@app.get("/api/stats")
def stats() -> dict:
    return store.run_stats()


_MIME_BY_SUFFIX = {".xlsx": _XLSX_MIME, ".docx": _DOCX_MIME}


@app.get("/api/runs/{run_id}/download")
def download_run(run_id: int) -> FileResponse:
    run = store.get_run(run_id)
    if run is None or not Path(run["path"]).is_file():
        raise HTTPException(status_code=404, detail="התוצר לא נמצא")
    suffix = Path(run["filename"]).suffix.lower()
    media_type = _MIME_BY_SUFFIX.get(suffix, "application/octet-stream")
    return FileResponse(run["path"], filename=run["filename"], media_type=media_type)


@app.get("/api/feedback/categories")
def feedback_categories() -> list[str]:
    return FEEDBACK_CATEGORIES


@app.post("/api/feedback")
async def submit_feedback(
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
def feedback() -> list[dict]:
    return store.list_feedback()


@app.post("/api/feedback/{feedback_id}")
async def triage_feedback(
    feedback_id: int,
    status: str = Form(""),
    priority: str = Form(""),
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
def quality_stats() -> dict:
    stats = store.health_stats()
    for entry in stats["category_counts"]:
        entry["action"] = FEEDBACK_CATEGORY_ACTIONS.get(entry["category"], "")
    return stats
