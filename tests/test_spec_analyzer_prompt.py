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


def test_guidance_included_when_given():
    prompt = build_user_prompt("spec text", tag="1", guidance="התמקד רק בממשק החיצוני")
    assert "התמקד רק בממשק החיצוני" in prompt
    assert "הנחיה נוספת מהמשתמש" in prompt


def test_guidance_omitted_when_blank():
    prompt = build_user_prompt("spec text", tag="1", guidance="   ")
    assert "הנחיה נוספת מהמשתמש" not in prompt


def test_image_scope_used_when_no_tag_and_image_attached():
    prompt = build_user_prompt("spec text", tag=None, images_attached=True)
    assert "מצורפת תמונה" in prompt
    assert "מיקוד: ניתוח כלל האפיון" not in prompt


def test_tag_takes_priority_over_image_scope():
    prompt = build_user_prompt("spec text", tag="40100", images_attached=True)
    assert "40100" in prompt
    assert "מצורפת תמונה" not in prompt
