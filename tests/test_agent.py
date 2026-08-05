"""Tests for the STD Generator agent, using a mocked LLM completer."""

import json

from qa_agents.base import get_agent
from qa_agents.models import StdResult
from qa_agents.std_generator.agent import StdGeneratorAgent, parse_std

_MODEL_JSON = json.dumps(
    {
        "scenarios": [
            {
                "entity": "פרטי (contact)",
                "event": "שליפת אוכלוסייה - חיובי",
                "target_field": 'שדה "סירוב דוחות" (new_mailreports)',
                "schema": "פרטי (contact)",
                "condition": "new_mailreports = 0 או NULL",
                "expected_result": "רשומה תיכלל באוכלוסייה",
            }
        ],
        "sql_queries": [
            {
                "tag": "12345",
                "purpose": "שליפת אוכלוסייה חיובית",
                "main_table": "contact",
                "sql": "SELECT * FROM contact WHERE statecode = 0",
                "notes": "",
            }
        ],
    },
    ensure_ascii=False,
)


def test_run_returns_std_result_and_passes_tag_and_spec():
    captured = {}

    def fake_completer(system: str, user: str) -> str:
        captured["system"] = system
        captured["user"] = user
        return _MODEL_JSON

    agent = StdGeneratorAgent(completer=fake_completer)
    result = agent.run("תוכן אפיון לדוגמה", tag="12345")

    assert isinstance(result, StdResult)
    assert len(result.scenarios) == 1
    assert result.scenarios[0].entity == "פרטי (contact)"
    assert result.sql_queries[0].sql.startswith("SELECT")
    # the prompt carried the tag and the spec text
    assert "12345" in captured["user"]
    assert "תוכן אפיון לדוגמה" in captured["user"]


def test_parse_std_defaults_notes_when_missing():
    raw = json.dumps(
        {
            "scenarios": [],
            "sql_queries": [
                {
                    "tag": "1",
                    "purpose": "p",
                    "main_table": "t",
                    "sql": "SELECT 1",
                }
            ],
        }
    )
    result = parse_std(raw)
    assert result.sql_queries[0].notes == ""


def test_agent_is_registered():
    assert get_agent("std_generator") is StdGeneratorAgent


def test_model_defaults_to_opus(monkeypatch):
    monkeypatch.delenv("QA_MODEL", raising=False)
    agent = StdGeneratorAgent(completer=lambda s, u: "{}")
    assert agent.model == "claude-opus-5"


def test_model_from_env(monkeypatch):
    monkeypatch.setenv("QA_MODEL", "claude-haiku-4-5")
    agent = StdGeneratorAgent(completer=lambda s, u: "{}")
    assert agent.model == "claude-haiku-4-5"
