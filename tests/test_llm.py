"""Tests for the shared Claude-API plumbing used by every agent."""

import base64

from qa_agents.llm import default_model, image_content_block


def test_default_model_falls_back_to_opus(monkeypatch):
    monkeypatch.delenv("QA_MODEL", raising=False)
    assert default_model() == "claude-opus-5"


def test_default_model_reads_env_var(monkeypatch):
    monkeypatch.setenv("QA_MODEL", "claude-haiku-4-5")
    assert default_model() == "claude-haiku-4-5"


def test_image_content_block_base64_encodes_and_shapes_correctly():
    block = image_content_block(b"raw-bytes", "image/png")
    assert block == {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/png",
            "data": base64.b64encode(b"raw-bytes").decode(),
        },
    }
