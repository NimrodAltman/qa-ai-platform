"""STD Generator agent.

Turns extracted specification text into an ``StdResult`` (test scenarios + SQL)
by calling an LLM. The LLM call is injected as a ``completer`` so the agent can
be tested against a mock — no API key, no cost. The real completer uses the
Claude API and constrains the output to a JSON schema.
"""

from __future__ import annotations

import json

from ..base import BaseAgent
from ..llm import Completer, TRUNCATED_OUTPUT_MESSAGE, anthropic_completer, default_model
from ..models import Scenario, SqlQuery, StdResult
from .profile import CRM_HEBREW, Profile
from .prompt import build_system_prompt, build_user_prompt

_SCENARIO_PROPS = {
    "entity": {"type": "string"},
    "event": {"type": "string"},
    "target_field": {"type": "string"},
    "schema": {"type": "string"},
    "condition": {"type": "string"},
    "expected_result": {"type": "string"},
}
_SQL_PROPS = {
    "tag": {"type": "string"},
    "purpose": {"type": "string"},
    "main_table": {"type": "string"},
    "sql": {"type": "string"},
    "notes": {"type": "string"},
}
STD_SCHEMA = {
    "type": "object",
    "properties": {
        "scenarios": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": _SCENARIO_PROPS,
                "required": list(_SCENARIO_PROPS),
                "additionalProperties": False,
            },
        },
        "sql_queries": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": _SQL_PROPS,
                "required": list(_SQL_PROPS),
                "additionalProperties": False,
            },
        },
    },
    "required": ["scenarios", "sql_queries"],
    "additionalProperties": False,
}


class StdGeneratorAgent(BaseAgent):
    name = "std_generator"
    display_name = "STD Generator"
    description = "מפיק תסריטי בדיקה ושאילתות SQL מאפיון, לבדיקה שיטתית של תהליך."
    output_format = "Excel (.xlsx)"

    def __init__(
        self,
        completer: Completer | None = None,
        model: str | None = None,
        profile: Profile = CRM_HEBREW,
    ) -> None:
        model = model or default_model()
        self._completer = completer or anthropic_completer(model, STD_SCHEMA)
        self.model = model
        self.profile = profile

    def run(
        self,
        spec_text: str,
        tag: str | None = None,
        scenarios: bool = True,
        sql: bool = True,
        guidance: str = "",
    ) -> StdResult:
        """Generate an STD from ``spec_text``.

        ``tag`` selects a specific task tag (``None`` = whole spec);
        ``scenarios`` / ``sql`` select which outputs to produce; ``guidance``
        is optional free text from the user, e.g. a more precise instruction
        than the tag number alone.
        """
        system = build_system_prompt(self.profile)
        user = build_user_prompt(
            spec_text, tag=tag, scenarios=scenarios, sql=sql,
            profile=self.profile, guidance=guidance,
        )
        raw = self._completer(system, user)
        return parse_std(raw)


def parse_std(raw: str) -> StdResult:
    """Parse the model's JSON output into an ``StdResult``."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(TRUNCATED_OUTPUT_MESSAGE) from exc
    scenarios = [Scenario(**s) for s in data.get("scenarios", [])]
    sql_queries = [SqlQuery(**q) for q in data.get("sql_queries", [])]
    return StdResult(scenarios=scenarios, sql_queries=sql_queries)
