"""Shared Claude-API plumbing used by every agent.

Every agent needs the same three things: which model to use, a completer that
calls the API with a JSON-schema-constrained structured output, and graceful
handling of a truncated response. Centralizing this means a fix here (e.g. the
streaming/truncation handling) applies to every agent, not just one.
"""

from __future__ import annotations

import os
from typing import Callable

DEFAULT_MODEL = "claude-opus-5"

# A completer takes (system_prompt, user_prompt) and returns the model's raw
# JSON text. This is the seam that isolates an agent from the LLM SDK.
Completer = Callable[[str, str], str]

TRUNCATED_OUTPUT_MESSAGE = (
    "הפלט מהסוכן נחתך כי היה ארוך מדי. נסה לצמצם את ההיקף — למשל התמקד "
    "בתיוג ספציפי במקום כלל האפיון, או פצל לבקשות קטנות יותר."
)


def default_model() -> str:
    """The model to use — from the QA_MODEL env var, else Claude Opus 5."""
    return os.environ.get("QA_MODEL", DEFAULT_MODEL)


def anthropic_completer(model: str, schema: dict, max_tokens: int = 32000) -> Completer:
    """Build a completer backed by the Claude API (imported lazily).

    Streams — non-streaming requests above ~16K output tokens risk an SDK
    timeout guard, and exhaustive agent prompts can exceed that — and
    constrains the response to ``schema`` via structured outputs.
    """
    client = None

    def complete(system: str, user: str) -> str:
        nonlocal client
        if client is None:
            import anthropic

            client = anthropic.Anthropic()
        with client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        ) as stream:
            response = stream.get_final_message()
        if response.stop_reason == "max_tokens":
            raise RuntimeError(TRUNCATED_OUTPUT_MESSAGE)
        return next(block.text for block in response.content if block.type == "text")

    return complete
