"""Data contract for the Spec Analyzer agent's output.

Distinct from ``qa_agents.models`` (the STD Generator's contract) — this agent
produces a readiness *analysis*, not test scenarios or SQL.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Entity:
    """One entity (table) and the fields (columns) mentioned for it."""

    name: str
    fields: list[str] = field(default_factory=list)


@dataclass
class AnalysisResult:
    business_rules: list[str] = field(default_factory=list)
    entities: list[Entity] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
