"""Tests for prompt construction — execution mode and output-type selection."""

from qa_agents.std_generator.profile import CRM_HEBREW, ECOMMERCE_ENGLISH
from qa_agents.std_generator.prompt import build_system_prompt, build_user_prompt


def test_system_prompt_demands_exhaustive_coverage():
    assert "כיסוי ממצה" in build_system_prompt(CRM_HEBREW)


def test_system_prompt_comes_from_the_given_profile():
    assert "senior QA engineer" in build_system_prompt(ECOMMERCE_ENGLISH)


def test_user_prompt_framing_comes_from_the_given_profile():
    prompt = build_user_prompt("spec text", tag="99", profile=ECOMMERCE_ENGLISH)
    assert "Task tag: 99" in prompt
    assert "--- Specification ---" in prompt


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
