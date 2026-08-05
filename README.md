# QA AI Platform

An extensible, config-driven platform for AI-powered QA agents. The first agent,
**STD Generator**, reads a specification document and produces structured test
scenarios (STD) and SQL population queries, exported as an Excel workbook.

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
# → writes output/STD_40012.xlsx  (pass a 4th argument for a custom path)
```

Use it as a library:

```python
from qa_agents.std_generator.pipeline import generate_std

generate_std("spec.docx", tag="40012", output_path="std.xlsx")
```

## Web UI

A local web interface (FastAPI) exposes the "Run Agent" screen — upload a spec,
pick options, and download the STD:

```bash
python -m uvicorn qa_agents.web.app:app --port 8000
# open http://localhost:8000
```

Options mirror the product mockups: execution mode (specific tag / whole spec),
output type (scenarios / SQL / both), and a task number for the file name. The
API key is read from a local `.env`; generation runs server-side.

## Testing

```bash
pytest
```

The suite mocks the LLM, so it needs no API key and incurs no cost.

## Powered by

[Claude](https://www.anthropic.com/) (Anthropic API), default model `claude-opus-5`.
The `anthropic` SDK is imported lazily, so tests and CI run without it configured.

## Project structure

```
src/qa_agents/
├── models.py            # shared data contract (Scenario, SqlQuery, StdResult)
├── base.py              # BaseAgent + registry — the extension seam
├── extraction.py        # .docx / .xlsx / .pdf → structured text
├── std_generator/
│   ├── profile.py       # output profile (sheet + column layout as data)
│   ├── prompt.py        # QA persona and domain rules
│   ├── agent.py         # StdGeneratorAgent (LLM → StdResult)
│   ├── excel_writer.py  # StdResult + profile → .xlsx
│   ├── pipeline.py      # extract → agent → excel
│   └── __main__.py      # CLI
└── web/                 # FastAPI app + Run Agent UI
    ├── app.py
    └── static/index.html
tests/                   # unit + end-to-end tests (mocked LLM)
examples/                # fully fictional demo specifications
```

## Roadmap

- Additional hub screens (run history, output center, feedback, health).
- Additional agents on the same base (SQL population, spec analysis).
- Multi-profile support so a new organization is a config file, not code.
```
