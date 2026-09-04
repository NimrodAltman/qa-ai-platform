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
Catalog, Run Agent, Output Center, Feedback Center, Health Dashboard:

```bash
python -m uvicorn qa_agents.web.app:app --port 8000
# open http://localhost:8000
```

**Agent Catalog** lists every agent registered in `BaseAgent`'s registry (name,
description, output format) and jumps straight to Run Agent with that agent
pre-selected — add a new agent and it appears here automatically, no UI change
needed.

**Run Agent** drives both agents: pick STD Generator (execution mode, output
type — scenarios / SQL / both) or Spec Analyzer (optional tag, defaults to the
whole spec), upload a document, and download the result. The API key is read
from a local `.env`; generation runs server-side.

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
│   ├── profile.py       # output profile (sheet + column layout as data)
│   ├── prompt.py        # QA persona and domain rules
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
    ├── app.py           # routes: generate, runs, feedback, quality-stats
    ├── store.py         # SQLite-backed run/feedback persistence
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
- Agent Management screen (enable/disable agents, per-agent settings).
- Multi-profile support so a new organization is a config file, not code.
- Authentication / roles (deliberately deferred — single local user today).
