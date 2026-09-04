"""Tests for the Spec Analyzer agent, using a mocked LLM completer."""

import json

import pytest

from qa_agents.base import get_agent
from qa_agents.spec_analyzer.agent import SpecAnalyzerAgent, parse_analysis
from qa_agents.spec_analyzer.models import AnalysisResult

_MODEL_JSON = json.dumps(
    {
        "business_rules": [
            "בקשה זכאית לאישור רק אם סטטוסה 1 (ממתין) והלקוח פעיל.",
        ],
        "entities": [
            {"name": "בקשת החזר (req_refund)", "fields": ["req_status", "req_amount"]},
        ],
        "gaps": [
            "לא מוגדר מה קורה כאשר req_amount שווה בדיוק לתקרת ההחזר.",
        ],
        "recommendations": [
            "יש להבהיר מול בעל האפיון את ההתנהגות בגבול התקרה המדויק.",
        ],
    },
    ensure_ascii=False,
)


def test_run_returns_analysis_result_and_passes_tag_and_spec():
    captured = {}

    def fake_completer(system: str, user: str) -> str:
        captured["system"] = system
        captured["user"] = user
        return _MODEL_JSON

    agent = SpecAnalyzerAgent(completer=fake_completer)
    result = agent.run("תוכן אפיון לדוגמה", tag="40100")

    assert isinstance(result, AnalysisResult)
    assert len(result.business_rules) == 1
    assert result.entities[0].name == "בקשת החזר (req_refund)"
    assert result.entities[0].fields == ["req_status", "req_amount"]
    assert len(result.gaps) == 1
    assert len(result.recommendations) == 1
    assert "40100" in captured["user"]
    assert "תוכן אפיון לדוגמה" in captured["user"]


def test_run_whole_spec_mode_has_no_tag_in_prompt():
    def fake_completer(system: str, user: str) -> str:
        assert "כלל האפיון" in user
        return _MODEL_JSON

    agent = SpecAnalyzerAgent(completer=fake_completer)
    agent.run("תוכן אפיון", tag=None)


def test_parse_analysis_defaults_empty_lists_when_missing():
    result = parse_analysis(json.dumps({"business_rules": [], "entities": [], "gaps": [], "recommendations": []}))
    assert result == AnalysisResult()


def test_parse_analysis_raises_clear_error_on_truncated_json():
    truncated = '{"business_rules": ["unterminated'
    with pytest.raises(ValueError, match="נחתך"):
        parse_analysis(truncated)


def test_agent_is_registered():
    assert get_agent("spec_analyzer") is SpecAnalyzerAgent


def test_model_defaults_to_opus(monkeypatch):
    monkeypatch.delenv("QA_MODEL", raising=False)
    agent = SpecAnalyzerAgent(completer=lambda s, u: "{}")
    assert agent.model == "claude-opus-5"


def test_model_from_env(monkeypatch):
    monkeypatch.setenv("QA_MODEL", "claude-haiku-4-5")
    agent = SpecAnalyzerAgent(completer=lambda s, u: "{}")
    assert agent.model == "claude-haiku-4-5"
