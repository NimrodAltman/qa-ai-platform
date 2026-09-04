"""Tests for Spec Analyzer prompt construction."""

from qa_agents.spec_analyzer.prompt import build_system_prompt, build_user_prompt


def test_system_prompt_scopes_to_analysis_only():
    system = build_system_prompt()
    assert "אינך מפיק תסריטי בדיקה" in system
    assert "אינך מפיק שאילתות SQL" in system


def test_specific_tag_mode():
    prompt = build_user_prompt("spec text", tag="40100")
    assert "40100" in prompt


def test_whole_spec_mode():
    prompt = build_user_prompt("spec text", tag=None)
    assert "כלל האפיון" in prompt
