"""Tests for the profile registry — the seam that lets a new organization be
a config file instead of new code."""

from qa_agents.std_generator.profile import CRM_HEBREW, ECOMMERCE_ENGLISH, PROFILES


def test_profiles_registry_contains_both_profiles():
    assert set(PROFILES) == {"crm-hebrew", "ecommerce-english"}
    assert PROFILES["crm-hebrew"] is CRM_HEBREW
    assert PROFILES["ecommerce-english"] is ECOMMERCE_ENGLISH


def test_profiles_differ_in_language_and_layout():
    assert CRM_HEBREW.rtl is True
    assert ECOMMERCE_ENGLISH.rtl is False
    assert CRM_HEBREW.scenarios.title != ECOMMERCE_ENGLISH.scenarios.title
    assert CRM_HEBREW.system_prompt != ECOMMERCE_ENGLISH.system_prompt
