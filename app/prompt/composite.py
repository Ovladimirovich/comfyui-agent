"""M11 — Composite Prompt Builder (Orchestration/Fallback Layer).

CompositePromptBuilder — policy layer поверх HeuristicPromptBuilder и LLMPromptBuilder.
Предпочитает LLM, при недоступности/ошибке/fail validation использует heuristic fallback.
НЕ делает retry loops — single attempt LLM → failure → heuristic.

AD-30: не имеет доступа к FS/ComfyUI.
AD-31: не выбирает capability.
AD-32: сохраняет исходное намерение (validation через LLM builder).

Source of Truth: docs/PROJECT_SPEC.md, docs/20_PROMPT_BUILDER.md (M11.5).
"""
from __future__ import annotations

from typing import Optional

from app.prompt.builder import PromptBuilder, PromptContext, PromptResult
from app.prompt.heuristic import HeuristicPromptBuilder
from app.prompt.llm import LLMPromptBuilder, LLMPromptBuilderError


# Причины fallback (диагностика)
FALLBACK_REASON_LLM_NOT_CONFIGURED = "llm_not_configured"
FALLBACK_REASON_LLM_TIMEOUT = "llm_timeout"
FALLBACK_REASON_LLM_API_ERROR = "llm_api_error"
FALLBACK_REASON_LLM_INVALID_RESPONSE = "llm_invalid_response"
FALLBACK_REASON_INTENT_VALIDATION_FAILED = "intent_validation_failed"


class CompositePromptBuilderError(RuntimeError):
    """Ошибка CompositePromptBuilder (неожиданное состояние)."""


class CompositePromptBuilder:
    """Orchestration/fallback layer над HeuristicPromptBuilder и LLMPromptBuilder.

    Алгоритм:
    1. Если LLM не настроен → сразу heuristic.
    2. Попытка LLM (single attempt, без retry).
    3. Если LLM успешен И прошли intent validation → вернуть LLM result.
    4. Иначе → heuristic fallback с diagnostics.
    """

    def __init__(
        self,
        llm_builder: Optional[LLMPromptBuilder] = None,
        heuristic_builder: Optional[HeuristicPromptBuilder] = None,
    ) -> None:
        self.llm_builder = llm_builder
        self.heuristic_builder = heuristic_builder or HeuristicPromptBuilder()

    def build(self, context: PromptContext) -> PromptResult:
        # П1: Проверка LLM конфигурации
        if self.llm_builder is None:
            return self._build_heuristic(context, reason=FALLBACK_REASON_LLM_NOT_CONFIGURED)

        # П2: Попытка LLM (single attempt)
        try:
            llm_result = self.llm_builder.build(context)
        except LLMPromptBuilderError as e:
            reason = self._classify_llm_error(e)
            return self._build_heuristic(context, reason=reason)

        # П3: Intent validation (AD-32)
        if not llm_result.original_preserved:
            return self._build_heuristic(
                context, reason=FALLBACK_REASON_INTENT_VALIDATION_FAILED
            )

        # П4: LLM success
        return llm_result

    def _build_heuristic(
        self, context: PromptContext, reason: str
    ) -> PromptResult:
        heuristic_result = self.heuristic_builder.build(context)
        return PromptResult(
            enhanced_prompt=heuristic_result.enhanced_prompt,
            original_preserved=heuristic_result.original_preserved,
            mode=context.mode,
            variant_index=context.suggestion_index,
            source="heuristic_fallback",
            rationale=f"fallback: {reason}",
            original_prompt=context.original_text,
        )

    def _classify_llm_error(self, error: LLMPromptBuilderError) -> str:
        """Классификация ошибки LLM для диагностики fallback reason."""
        error_str = str(error).lower()
        if "timeout" in error_str:
            return FALLBACK_REASON_LLM_TIMEOUT
        if "http" in error_str or "unauthorized" in error_str or "forbidden" in error_str:
            return FALLBACK_REASON_LLM_API_ERROR
        if "bad response" in error_str or "empty response" in error_str:
            return FALLBACK_REASON_LLM_INVALID_RESPONSE
        return FALLBACK_REASON_LLM_API_ERROR
