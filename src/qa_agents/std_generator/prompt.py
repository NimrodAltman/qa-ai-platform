"""Prompt construction for the STD Generator.

Every piece of natural-language text — persona, language, framing — comes from
the given :class:`Profile`. This module only assembles it; it carries no
domain or language content of its own, so a new profile needs no changes here.
"""

from __future__ import annotations

from .profile import CRM_HEBREW, Profile


def build_system_prompt(profile: Profile) -> str:
    """Return the system prompt for the given profile."""
    return profile.system_prompt


def build_user_prompt(
    spec_text: str,
    tag: str | None = None,
    scenarios: bool = True,
    sql: bool = True,
    profile: Profile = CRM_HEBREW,
) -> str:
    """Return the user prompt for the specification.

    ``tag`` selects a specific task tag; ``None`` means cover the whole spec.
    ``scenarios`` / ``sql`` select which outputs to produce.
    """
    scope = profile.tag_scope.format(tag=tag) if tag else profile.whole_scope

    if scenarios and sql:
        outputs = profile.outputs_both
    elif scenarios:
        outputs = profile.outputs_scenarios
    else:
        outputs = profile.outputs_sql

    return f"{scope}\n{outputs}\n\n{profile.spec_label}\n{spec_text}"
