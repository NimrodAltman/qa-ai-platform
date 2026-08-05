"""STD Generator agent.

Turns extracted specification text into an ``StdResult`` (test scenarios + SQL)
by calling an LLM. The LLM call is injected as a ``completer`` so the agent can
be tested against a mock — no API key, no cost. The real completer uses the
Claude API and constrains the output to a JSON schema.
"""

from __future__ import annotations

import json
import os
from typing import Callable

from ..base import BaseAgent
from ..models import Scenario, SqlQuery, StdResult
from .profile import CRM_HEBREW, Profile
from .prompt import build_system_prompt, build_user_prompt

# A completer takes (system_prompt, user_prompt) and returns the model's raw
# JSON text. This is the seam that isolates the agent from the LLM SDK.
Completer = Callable[[str, str], str]

DEFAULT_MODEL = "claude-opus-5"


def _default_model() -> str:
    """The model to use — from the QA_MODEL env var, else Claude Opus 5."""
    return os.environ.get("QA_MODEL", DEFAULT_MODEL)

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

    def __init__(
        self,
        completer: Completer | None = None,
        model: str | None = None,
        profile: Profile = CRM_HEBREW,
    ) -> None:
        model = model or _default_model()
        self._completer = completer or _anthropic_completer(model)
        self.model = model
        self.profile = profile

    def run(
        self,
        spec_text: str,
        tag: str | None = None,
        scenarios: bool = True,
        sql: bool = True,
    ) -> StdResult:
        """Generate an STD from ``spec_text``.

        ``tag`` selects a specific task tag (``None`` = whole spec);
        ``scenarios`` / ``sql`` select which outputs to produce.
        """
        system = build_system_prompt(self.profile)
        user = build_user_prompt(spec_text, tag=tag, scenarios=scenarios, sql=sql)
        raw = self._completer(system, user)
        return parse_std(raw)


def parse_std(raw: str) -> StdResult:
    """Parse the model's JSON output into an ``StdResult``."""
    data = json.loads(raw)
    scenarios = [Scenario(**s) for s in data.get("scenarios", [])]
    sql_queries = [SqlQuery(**q) for q in data.get("sql_queries", [])]
    return StdResult(scenarios=scenarios, sql_queries=sql_queries)


def _anthropic_completer(model: str) -> Completer:
    """Build a completer backed by the Claude API (imported lazily)."""
    client = None

    def complete(system: str, user: str) -> str:
        nonlocal client
        if client is None:
            import anthropic

            client = anthropic.Anthropic()
        response = client.messages.create(
            model=model,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": STD_SCHEMA}},
        )
        return next(block.text for block in response.content if block.type == "text")

    return complete
