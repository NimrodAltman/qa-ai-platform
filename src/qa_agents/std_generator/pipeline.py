"""End-to-end pipeline: specification document → STD Excel workbook."""

from __future__ import annotations

from pathlib import Path

from ..extraction import extract
from .agent import StdGeneratorAgent
from .excel_writer import write_workbook


def generate_std(
    spec_path: str | Path,
    tag: str | None,
    output_path: str | Path,
    agent: StdGeneratorAgent | None = None,
    scenarios: bool = True,
    sql: bool = True,
) -> Path:
    """Extract a spec, generate the STD, and write the Excel workbook.

    ``tag`` selects a specific task tag (``None`` = whole spec);
    ``scenarios`` / ``sql`` select which outputs to produce.
    ``agent`` defaults to a live :class:`StdGeneratorAgent` (Claude API); pass a
    mock-backed agent in tests to avoid an API call.
    """
    agent = agent or StdGeneratorAgent()
    spec_text = extract(spec_path)
    result = agent.run(spec_text, tag=tag, scenarios=scenarios, sql=sql)
    return write_workbook(
        result,
        output_path,
        agent.profile,
        include_scenarios=scenarios,
        include_sql=sql,
    )
