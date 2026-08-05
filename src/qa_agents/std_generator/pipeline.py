"""End-to-end pipeline: specification document → STD Excel workbook."""

from __future__ import annotations

from pathlib import Path

from ..extraction import extract
from .agent import StdGeneratorAgent
from .excel_writer import write_workbook


def generate_std(
    spec_path: str | Path,
    tag: str,
    output_path: str | Path,
    agent: StdGeneratorAgent | None = None,
) -> Path:
    """Extract a spec, generate the STD, and write the Excel workbook.

    ``agent`` defaults to a live :class:`StdGeneratorAgent` (Claude API); pass a
    mock-backed agent in tests to avoid an API call.
    """
    agent = agent or StdGeneratorAgent()
    spec_text = extract(spec_path)
    result = agent.run(spec_text, tag)
    return write_workbook(result, output_path, agent.profile)
