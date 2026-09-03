"""Composition Result — результат работы Composer.

AD-41: Явный тип результата с success, chain, alternatives, failure_reason.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.engine.chain import SubTask


@dataclass
class CompositionResult:
    """Результат composition — успешный или нет."""
    
    success: bool
    chain: list[SubTask] = field(default_factory=list)
    alternatives: list[list[SubTask]] = field(default_factory=list)
    failure_reason: str | None = None
    suggestions: list[str] = field(default_factory=list)
    
    @property
    def has_alternatives(self) -> bool:
        return len(self.alternatives) > 0
    
    @classmethod
    def ok(cls, chain: list[SubTask], alternatives: list[list[SubTask]] | None = None) -> CompositionResult:
        return cls(
            success=True,
            chain=chain,
            alternatives=alternatives or [],
        )
    
    @classmethod
    def fail(cls, reason: str, suggestions: list[str] | None = None) -> CompositionResult:
        return cls(
            success=False,
            failure_reason=reason,
            suggestions=suggestions or [],
        )
