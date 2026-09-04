"""Base agent contract and registry.

This is the extension seam for the platform: every QA agent subclasses
``BaseAgent`` and registers itself under a unique name. Adding a new agent
(SQL population, spec analysis, …) is a new subclass — no changes here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

_REGISTRY: dict[str, type["BaseAgent"]] = {}


class BaseAgent(ABC):
    """A QA agent that turns some input into a structured result.

    Subclasses set a class-level ``name`` and implement ``run``. ``display_name``,
    ``description`` and ``output_format`` are catalog metadata — plain data on
    the agent itself, so a catalog UI reflects whatever is actually registered
    instead of a hand-maintained list that can drift out of sync.
    """

    name: str
    display_name: str = ""
    description: str = ""
    output_format: str = ""

    @abstractmethod
    def run(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the agent and return its structured result."""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        agent_name = getattr(cls, "name", None)
        if agent_name is None:
            return  # intermediate base class, not a concrete agent
        if agent_name in _REGISTRY:
            raise ValueError(f"Agent name already registered: {agent_name!r}")
        _REGISTRY[agent_name] = cls


def get_agent(name: str) -> type[BaseAgent]:
    """Look up a registered agent class by name."""
    return _REGISTRY[name]


def available_agents() -> list[str]:
    """Names of all registered agents."""
    return sorted(_REGISTRY)


def list_agents() -> list[dict[str, str]]:
    """Catalog metadata for every registered agent, sorted by name."""
    return [
        {
            "name": cls.name,
            "display_name": cls.display_name,
            "description": cls.description,
            "output_format": cls.output_format,
        }
        for cls in (_REGISTRY[name] for name in sorted(_REGISTRY))
    ]
