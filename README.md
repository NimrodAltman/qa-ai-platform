# QA AI Platform

An extensible, config-driven platform for AI-powered QA agents. Two agents ship
today:

- **STD Generator** — reads a specification and produces structured test
  scenarios and SQL population queries, exported as an Excel workbook.
- **Spec Analyzer** — reviews a specification's *readiness* before testing
  begins: business rules, entities/fields, gaps and ambiguities, and concrete
  recommendations — exported as a Word report.

Both agents share the same extraction layer, the same Claude-API plumbing
(`llm.py`), and the same `BaseAgent` registry — adding a capability means
adding an agent, not rewiring the platform.

The design goal is a platform that adapts to **any organization and any QA
department**: agents are database-agnostic (table = entity, column = field), and
everything organization-specific — sheet layout, column names, language,
direction, domain conventions — lives in a **profile** (data, not code). Adding a
new organization is a new profile; adding a new capability is a new agent.

## How it works

```
specification (.docx / .xlsx / .pdf)
        │
        ▼
  extraction   →  structured text extracted from the source document
        │
        ▼
  agent (LLM)  →  returns a structured STD as JSON (scenarios + SQL)
        │
        ▼
  excel_writer →  the engine builds the workbook from a profile
```

The LLM produces a **data structure**; the engine builds the file. This keeps the
output deterministic and testable — extraction and the Excel writer are covered by
unit tests, and the agent is tested against a mocked LLM, so the whole suite runs
with **no API key and no cost**.

## Output format

The STD Generator produces a two-sheet workbook (RTL, right-aligned):

- **תסריטים** (scenarios): `מס' · ישות · אירוע · שדה · סכמה · תנאי/פעולה · תוצאה צפויה`
  plus manual columns the tester fills in (`תוצאת בדיקה · הערות · ת.הרצה · סבב`).
- **SQL**: `מס' · תיוג · מטרת השאילתה · טבלה ראשית · שאילתת SQL · הערות`.

## Quick start

```bash
pip install -r requirements.txt

# generate the fictional demo specification
python examples/make_demo_spec.py

# run the agent (requires ANTHROPIC_API_KEY)
export ANTHROPIC_API_KEY=sk-ant-...
python -m qa_agents.std_generator examples/demo_spec.docx 40012
# → writes output/STD_40012_scenarios_sql.xlsx
#   (--outputs scenarios|sql changes the suffix; pass a 4th arg for a custom path)
#   (--profile crm-hebrew|ecommerce-english picks the organization — default: crm-hebrew)
```

Use it as a library:

```python
from qa_agents.std_generator.pipeline import generate_std

generate_std("spec.docx", tag="40012", output_path="std.xlsx")
```

**Spec Analyzer** (second agent — Word output, no DB access needed):

```bash
python -m qa_agents.spec_analyzer examples/sample_spec.docx 40100
# → writes output/ANALYSIS_40100.docx
#   (omit the tag to analyze the whole spec instead of one task)
```

## Web UI

A local web interface (FastAPI) drives the full agent hub — Dashboard, Agent
Catalog, Run Agent, Output Center, Feedback Center, Health Dashboard, Agent
Management, User Management:

```bash
python -m uvicorn qa_agents.web.app:app --port 8000
# open http://localhost:8000
```

The first run seeds a default admin account — **username `admin`, password
`admin`** — change the password (or add a real user and delete the default
one) from User Management before exposing this beyond your own machine.

**Login required.** Every screen sits behind a session (a signed cookie —
see `SESSION_SECRET` in `.env.example`). Two roles: **admin** sees and
controls everything; **user** (QA User) can run agents, browse outputs, and
submit feedback, but not triage feedback, view Health Dashboard, or reach
Agent/User Management. **User Management** (admin-only) creates/deletes users
and sets roles. A user can optionally be restricted to specific agents (data
model only for now — `store.set_user_agent_access()` — a picker in the UI is
a natural next step); unrestricted is the default, matching today's behavior.

**Agent Catalog** lists every agent registered in `BaseAgent`'s registry —
name, description, accepted input formats, and output format — and jumps
straight to Run Agent with that agent pre-selected. Add a new agent and it
appears here automatically, no UI change needed. (Every agent currently
accepts the same input formats — Word/Excel/PDF — while output format is
per-agent; the Catalog shows both, clearly labeled, so they aren't confused.)

**Agent Management** lets you pick which Claude model an agent uses (or
"default", which falls back to the `QA_MODEL` env var) without touching
`.env` or code — useful for testing an agent on Haiku while keeping Opus as
the default for real runs.

**Organization profile** — STD Generator's Run Agent form has an "organization
profile" dropdown (`crm-hebrew` / `ecommerce-english`), populated from the same
`Profile` registry the CLI's `--profile` flag reads. Same agent, same engine,
same prompt-building code — only the profile's data (persona, language, sheet
layout) changes what comes out. See [Multi-organization support](#multi-organization-support).

**Run Agent** drives both agents: pick STD Generator (execution mode, output
type — scenarios / SQL / both) or Spec Analyzer (optional tag, defaults to the
whole spec), upload a document, and download the result. The API key is read
from a local `.env`; generation runs server-side.

Both agents also accept, optionally: **free-text guidance** (a more precise
instruction than the tag alone, e.g. "focus on the rejection scenarios only"),
and an **image** — a marked-up screenshot pointing at the relevant part of the
spec. With no tag given, an attached image tells the model to find the right
scope from the image itself instead of covering the whole document.

## Multi-organization support

STD Generator's `Profile` (`std_generator/profile.py`) is the seam that lets
the same agent and engine serve any organization: it carries the LLM persona
and language, how a run is framed (execution-mode / output-type phrasing),
and the Excel layout (sheet names, column headers, RTL) — all as plain data,
not code. Two profiles ship today:

- `crm-hebrew` — the original CRM/Hebrew setup (RTL, `תסריטים`/`SQL` sheets).
- `ecommerce-english` — a fictional e-commerce/web-app organization (LTR,
  English persona, `Scenarios`/`SQL` sheets) — added with **zero changes** to
  `agent.py`, `excel_writer.py`, or `pipeline.py`.

Adding a third organization is a new `Profile` value in `profile.py`; nothing
else in the codebase needs to change.

## Testing

```bash
pytest
```

The suite mocks the LLM, so it needs no API key and incurs no cost.

## Powered by

[Claude](https://www.anthropic.com/) (Anthropic API), default model `claude-opus-5`.
Set `QA_MODEL` in `.env` to use a different model (e.g. `claude-sonnet-5` or
`claude-haiku-4-5` for cheaper runs). The `anthropic` SDK is imported lazily, so
tests and CI run without it configured.

## Project structure

```
src/qa_agents/
├── models.py            # STD Generator's data contract (Scenario, SqlQuery, StdResult)
├── base.py              # BaseAgent + registry — the extension seam
├── llm.py               # shared Claude-API plumbing (model choice, streaming completer)
├── extraction.py        # .docx / .xlsx / .pdf → structured text
├── std_generator/
│   ├── profile.py       # org profile: persona/language/framing + Excel layout, as data
│   ├── prompt.py        # assembles a profile's text into system/user prompts
│   ├── agent.py         # StdGeneratorAgent (LLM → StdResult)
│   ├── excel_writer.py  # StdResult + profile → .xlsx
│   ├── pipeline.py      # extract → agent → excel
│   └── __main__.py      # CLI
├── spec_analyzer/
│   ├── models.py        # AnalysisResult (business rules, entities, gaps, recommendations)
│   ├── prompt.py        # readiness-analysis persona and rules
│   ├── agent.py          # SpecAnalyzerAgent (LLM → AnalysisResult)
│   ├── word_writer.py    # AnalysisResult → .docx (RTL)
│   ├── pipeline.py       # extract → agent → word report
│   └── __main__.py       # CLI
└── web/                 # FastAPI app + Agent Hub UI
    ├── app.py           # routes: generate, runs, feedback, quality-stats, auth
    ├── auth.py          # password hashing, session dependency, role checks
    ├── store.py         # SQLite-backed run/feedback/user persistence
    └── static/index.html
tests/                   # unit + end-to-end tests (mocked LLM)
examples/                # fully fictional demo specifications
```

## Roadmap

- ✅ Hub screens: Dashboard, Run Agent, Output Center, Feedback Center (with
  triage), Health Dashboard.
- ✅ A second agent on the same base — **Spec Analyzer** (process/specification
  readiness analysis, Word output).
- ✅ Wired Spec Analyzer into the web UI alongside STD Generator.
- ✅ Agent Catalog — a registry-driven screen listing every registered agent,
  with a one-click jump to Run Agent pre-selected.
- ✅ Run Agent's agent/profile pickers are dropdowns loaded from their registries
  (`/api/agents`, `/api/profiles`), so both scale past a couple of options.
- ✅ Multi-profile support — a second organization (`ecommerce-english`) proves a
  new org is a config file, not code. See [Multi-organization support](#multi-organization-support).
- ✅ Agent Management — per-agent Claude model override (or "default"), editable
  without touching `.env` or code.
- ✅ Authentication & roles — session login, admin vs. user, User Management
  screen, and a per-user agent-access data model (UI for it not yet built).
- ✅ Per-user data isolation — each user sees only their own runs/feedback;
  an admin still sees everyone's.
- ✅ Optional free-text guidance and image upload (a marked-up screenshot) on
  both agents, to focus generation/analysis on a specific part of the spec
  without a task tag.
- Extend multi-profile support (persona/language, not just Excel layout) to
  Spec Analyzer — currently STD Generator only.
- Per-user agent-access picker in User Management (the data model already
  supports it — see `store.set_user_agent_access()`).
