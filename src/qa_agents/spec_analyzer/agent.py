"""Spec Analyzer agent.

Turns extracted specification text into an ``AnalysisResult`` — business rules,
entities/fields, gaps, and recommendations — by calling an LLM. Mirrors the
STD Generator agent's shape: an injectable ``completer`` for testing, and a
real completer that uses the Claude API with a JSON-schema-constrained output.
"""

from __future__ import annotations

import json

from ..base import BaseAgent
from ..llm import Completer, TRUNCATED_OUTPUT_MESSAGE, anthropic_completer, default_model
from .models import AnalysisResult, Entity
from .prompt import build_system_prompt, build_user_prompt

_ENTITY_PROPS = {
    "name": {"type": "string"},
    "fields": {"type": "array", "items": {"type": "string"}},
}
ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "business_rules": {"type": "array", "items": {"type": "string"}},
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": _ENTITY_PROPS,
                "required": list(_ENTITY_PROPS),
                "additionalProperties": False,
            },
        },
        "gaps": {"type": "array", "items": {"type": "string"}},
        "recommendations": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["business_rules", "entities", "gaps", "recommendations"],
    "additionalProperties": False,
}


class SpecAnalyzerAgent(BaseAgent):
    name = "spec_analyzer"
    display_name = "Spec Analyzer"
    description = "בודק מוכנות אפיון לפני תחילת בדיקות: חוקים עסקיים, ישויות ושדות, פערים והמלצות."
    output_format = "Word (.docx)"

    def __init__(self, completer: Completer | None = None, model: str | None = None) -> None:
        model = model or default_model()
        self._completer = completer or anthropic_completer(model, ANALYSIS_SCHEMA)
        self.model = model

    def run(
        self,
        spec_text: str,
        tag: str | None = None,
        guidance: str = "",
        images: list[dict] | None = None,
    ) -> AnalysisResult:
        """Analyze ``spec_text``. ``tag`` focuses on one task tag (None = whole spec).

        ``guidance`` is optional free text from the user; ``images`` are Claude
        content blocks (see ``llm.image_content_block``), e.g. a marked-up
        screenshot pointing at the part of the spec to analyze.
        """
        system = build_system_prompt()
        text = build_user_prompt(
            spec_text, tag=tag, guidance=guidance, images_attached=bool(images)
        )
        user = [*images, {"type": "text", "text": text}] if images else text
        raw = self._completer(system, user)
        return parse_analysis(raw)


def parse_analysis(raw: str) -> AnalysisResult:
    """Parse the model's JSON output into an ``AnalysisResult``."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(TRUNCATED_OUTPUT_MESSAGE) from exc
    entities = [Entity(**e) for e in data.get("entities", [])]
    return AnalysisResult(
        business_rules=data.get("business_rules", []),
        entities=entities,
        gaps=data.get("gaps", []),
        recommendations=data.get("recommendations", []),
    )
