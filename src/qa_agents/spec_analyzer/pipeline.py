"""End-to-end pipeline: specification document → analysis Word report."""

from __future__ import annotations

from pathlib import Path

from ..extraction import extract
from .agent import SpecAnalyzerAgent
from .word_writer import write_report


def default_output_name(key: str) -> str:
    """Build the default output path for a given tag/whole-spec key."""
    return f"output/ANALYSIS_{key}.docx"


def generate_analysis(
    spec_path: str | Path,
    tag: str | None,
    output_path: str | Path,
    agent: SpecAnalyzerAgent | None = None,
) -> Path:
    """Extract a spec, analyze it, and write the Word report.

    ``tag`` focuses the analysis on one task tag (``None`` = whole spec).
    ``agent`` defaults to a live :class:`SpecAnalyzerAgent` (Claude API); pass a
    mock-backed agent in tests to avoid an API call.
    """
    agent = agent or SpecAnalyzerAgent()
    spec_text = extract(spec_path)
    result = agent.run(spec_text, tag=tag)
    return write_report(result, output_path, tag=tag)
