"""Plan model — PlanContext, PlanResult, Planner protocol (M8/M9.1).

Источник: tests/test_planner.py, tests/test_planner_context.py, app/agent.py,
app/conversation.py, app/planner/adaptive.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol


@dataclass
class PlanContext:
    """Контекст для планировщика (декларативный, без FS/media bytes)."""

    active_asset_type: Optional[str] = None
    capabilities: tuple[str, ...] = ()
    active_workflow: Optional[str] = None
    previous_prompt: Optional[str] = None


@dataclass
class PlanResult:
    """Результат планирования."""

    capability: str
    params: dict = field(default_factory=dict)
    rationale: Optional[str] = None


class Planner(Protocol):
    """Протокол планировщика: request → capability + params."""

    def plan(self, request: str, context: Optional[PlanContext] = None) -> PlanResult:
        ...
