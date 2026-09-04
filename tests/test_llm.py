"""Tests for the shared Claude-API plumbing used by every agent."""

from qa_agents.llm import default_model


def test_default_model_falls_back_to_opus(monkeypatch):
    monkeypatch.delenv("QA_MODEL", raising=False)
    assert default_model() == "claude-opus-5"


def test_default_model_reads_env_var(monkeypatch):
    monkeypatch.setenv("QA_MODEL", "claude-haiku-4-5")
    assert default_model() == "claude-haiku-4-5"
