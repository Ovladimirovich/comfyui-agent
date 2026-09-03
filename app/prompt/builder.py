"""M11 — Prompt Builder Protocol and Contracts.

Source of Truth: docs/PROJECT_SPEC.md, docs/20_PROMPT_BUILDER.md.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional, Protocol, runtime_checkable


@dataclass
class PromptContext:
    """Декларативный контекст для PromptBuilder.

    Содержит ТОЛЬКО строки и идентификаторы — без bytes/paths/FS (AD-30).
    """

    original_text: str  # исходный текст пользователя
    mode: Literal["completion", "suggestion"] = "suggestion"  # режим работы
    capability: Optional[str] = None  # для context-aware (image.generate, image.edit, ...)
    active_asset_type: Optional[str] = None  # из ConversationContext
    previous_prompt: Optional[str] = None  # для итеративного улучшения
    suggestion_index: int = 0  # индекс варианта (для suggestion)
    style: Optional[str] = None  # желаемый стиль (photorealistic, cinematic, ...)
    parameters: Optional[dict] = None  # параметры генерации (width, height, ...)


@dataclass
class PromptResult:
    """Результат работы PromptBuilder (AD-32 original_preserved check)."""

    enhanced_prompt: str  # улучшенный промпт
    original_preserved: bool  # сохранено ли исходное намерение
    mode: Literal["completion", "suggestion"]
    variant_index: int  # индекс варианта
    source: Literal["heuristic", "llm", "heuristic_fallback"]  # источник
    rationale: Optional[str] = None  # объяснение (для отладки / причина fallback)
    original_prompt: Optional[str] = None  # исходный текст пользователя (M11.6)


@runtime_checkable
class PromptBuilder(Protocol):
    def build(self, context: PromptContext) -> PromptResult:
        ...
