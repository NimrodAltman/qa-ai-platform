"""Tests for prompt construction — execution mode and output-type selection."""

from qa_agents.std_generator.profile import CRM_HEBREW
from qa_agents.std_generator.prompt import build_system_prompt, build_user_prompt


def test_system_prompt_demands_exhaustive_coverage():
    assert "כיסוי ממצה" in build_system_prompt(CRM_HEBREW)


def test_specific_tag_mode():
    prompt = build_user_prompt("spec text", tag="40100")
    assert "40100" in prompt


def test_whole_spec_mode():
    prompt = build_user_prompt("spec text", tag=None)
    assert "כלל האפיון" in prompt


def test_scenarios_only():
    prompt = build_user_prompt("spec text", tag="1", scenarios=True, sql=False)
    assert "תסריטי בדיקה בלבד" in prompt


def test_sql_only():
    prompt = build_user_prompt("spec text", tag="1", scenarios=False, sql=True)
    assert "SQL בלבד" in prompt
