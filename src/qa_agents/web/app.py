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
from ..std_generator.pipeline import generate_std, output_suffix

load_dotenv()  # pick up ANTHROPIC_API_KEY from a local .env for convenience

app = FastAPI(title="QA AI Platform")
_STATIC = Path(__file__).parent / "static"
_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


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


@app.get("/api/runs")
def runs() -> list[dict]:
    return store.list_runs()


@app.get("/api/stats")
def stats() -> dict:
    return store.run_stats()


@app.get("/api/runs/{run_id}/download")
def download_run(run_id: int) -> FileResponse:
    run = store.get_run(run_id)
    if run is None or not Path(run["path"]).is_file():
        raise HTTPException(status_code=404, detail="התוצר לא נמצא")
    return FileResponse(run["path"], filename=run["filename"], media_type=_XLSX_MIME)
