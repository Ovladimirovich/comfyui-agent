"""M11 — Tests for CompositePromptBuilder (fallback orchestration layer).

Тесты используют mock builders — НЕ требуют интернета или реального API.
"""
from __future__ import annotations
import sys

import json
import os
from dataclasses import dataclass
from typing import Literal, Optional
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass
class PromptContext:
    original_text: str
    mode: Literal["completion", "suggestion"] = "suggestion"
    capability: Optional[str] = None
    active_asset_type: Optional[str] = None
    previous_prompt: Optional[str] = None
    suggestion_index: int = 0
    style: Optional[str] = None
    parameters: Optional[dict] = None


@dataclass
class PromptResult:
    enhanced_prompt: str
    original_preserved: bool
    mode: Literal["completion", "suggestion"]
    variant_index: int
    source: Literal["heuristic", "llm", "heuristic_fallback"]
    rationale: Optional[str] = None


from app.prompt.composite import (  # noqa: E402
    CompositePromptBuilder,
    FALLBACK_REASON_LLM_NOT_CONFIGURED,
    FALLBACK_REASON_LLM_TIMEOUT,
    FALLBACK_REASON_LLM_API_ERROR,
    FALLBACK_REASON_LLM_INVALID_RESPONSE,
    FALLBACK_REASON_INTENT_VALIDATION_FAILED,
)
from app.prompt.heuristic import HeuristicPromptBuilder  # noqa: E402
from app.prompt.llm import LLMPromptBuilder, LLMPromptBuilderError  # noqa: E402


def _make_llm_success_result(text: str = "реалистичный кот") -> PromptResult:
    return PromptResult(
        enhanced_prompt=text,
        original_preserved=True,
        mode="suggestion",
        variant_index=0,
        source="llm",
        rationale="LLM enhanced",
    )


def _make_llm_error(error_msg: str) -> LLMPromptBuilderError:
    return LLMPromptBuilderError(error_msg)


def _make_heuristic_result(text: str = "детальный кот") -> PromptResult:
    return PromptResult(
        enhanced_prompt=text,
        original_preserved=True,
        mode="suggestion",
        variant_index=0,
        source="heuristic",
        rationale="template applied",
    )


def test_llm_success():
    """LLM вызван, heuristic НЕ вызван, source == 'llm'."""
    llm_builder = MagicMock()
    llm_builder.build.return_value = _make_llm_success_result()
    
    composite = CompositePromptBuilder(llm_builder=llm_builder)
    result = composite.build(PromptContext(original_text="кот"))
    
    assert result.source == "llm"
    assert result.enhanced_prompt == "реалистичный кот"
    assert result.original_preserved == True
    llm_builder.build.assert_called_once()
    print("✓ test_llm_success: LLM использован, heuristic пропущен")


def test_llm_timeout_falls_back():
    """LLM timeout → heuristic fallback, source == 'heuristic_fallback'."""
    llm_builder = MagicMock()
    llm_builder.build.side_effect = _make_llm_error("LLM timeout after 30s")
    
    composite = CompositePromptBuilder(
        llm_builder=llm_builder,
        heuristic_builder=HeuristicPromptBuilder(),
    )
    result = composite.build(PromptContext(original_text="кот на крыше"))
    
    assert result.source == "heuristic_fallback"
    assert "timeout" in str(result.rationale).lower()
    assert "кот" in result.enhanced_prompt.lower()
    print("✓ test_llm_timeout_falls_back: fallback при timeout")


def test_llm_api_error_falls_back():
    """LLM HTTP error → heuristic fallback."""
    llm_builder = MagicMock()
    llm_builder.build.side_effect = _make_llm_error("LLM HTTP 500: Internal Server Error")
    
    composite = CompositePromptBuilder(
        llm_builder=llm_builder,
        heuristic_builder=HeuristicPromptBuilder(),
    )
    result = composite.build(PromptContext(original_text="кот"))
    
    assert result.source == "heuristic_fallback"
    assert "api" in str(result.rationale).lower() or "500" in str(result.rationale)
    print("✓ test_llm_api_error_falls_back: fallback при API error")


def test_llm_not_configured():
    """Отсутствие LLM builder → сразу heuristic, source == 'heuristic_fallback'."""
    composite = CompositePromptBuilder(llm_builder=None)
    result = composite.build(PromptContext(original_text="кот"))
    
    assert result.source == "heuristic_fallback"
    assert "not_configured" in str(result.rationale).lower()
    assert "кот" in result.enhanced_prompt.lower()
    print("✓ test_llm_not_configured: fallback при отсутствии LLM")


def test_invalid_llm_response_falls_back():
    """LLM вернул невалидный результат → heuristic fallback."""
    llm_builder = MagicMock()
    # LLM возвращает результат с original_preserved=False
    bad_result = PromptResult(
        enhanced_prompt="собака на пляже",
        original_preserved=False,
        mode="suggestion",
        variant_index=0,
        source="llm",
        rationale="bad result",
    )
    llm_builder.build.return_value = bad_result
    
    composite = CompositePromptBuilder(
        llm_builder=llm_builder,
        heuristic_builder=HeuristicPromptBuilder(),
    )
    result = composite.build(PromptContext(original_text="кот"))
    
    assert result.source == "heuristic_fallback"
    assert "intent_validation" in str(result.rationale).lower()
    print("✓ test_invalid_llm_response_falls_back: fallback при fail validation")


def test_intent_validation_failure_falls_back():
    """AD-32: LLM result не прошёл intent check → heuristic fallback."""
    llm_builder = MagicMock()
    # LLM вернул результат, но исходный текст потерян
    bad_result = PromptResult(
        enhanced_prompt="красивый пейзаж гор",
        original_preserved=False,
        mode="suggestion",
        variant_index=0,
        source="llm",
        rationale="no subject preserved",
    )
    llm_builder.build.return_value = bad_result
    
    composite = CompositePromptBuilder(
        llm_builder=llm_builder,
        heuristic_builder=HeuristicPromptBuilder(),
    )
    result = composite.build(PromptContext(original_text="кот на крыше"))
    
    assert result.source == "heuristic_fallback"
    assert "intent_validation_failed" in str(result.rationale)
    print("✓ test_intent_validation_failure_falls_back: AD-32 соблюден")


def test_heuristic_result_is_returned():
    """Fallback выдаёт полноценный PromptResult, а не пустоту."""
    composite = CompositePromptBuilder(llm_builder=None)
    result = composite.build(PromptContext(original_text="кот на крыше ночью"))
    
    assert result.enhanced_prompt != "", "enhanced_prompt не должен быть пустым"
    assert result.original_preserved == True
    assert result.mode == "suggestion"
    assert result.variant_index == 0
    assert result.source == "heuristic_fallback"
    assert result.rationale is not None
    print("✓ test_heuristic_result_is_returned: fallback даёт полноценный результат")


def test_no_comfyui_access():
    """CompositePromptBuilder не зависит от ComfyUI (AD-30)."""
    # Composite должен работать без ComfyClient, AssetStore, Provider
    composite = CompositePromptBuilder(llm_builder=None)
    result = composite.build(PromptContext(original_text="кот"))
    
    assert result.source == "heuristic_fallback"
    assert result.enhanced_prompt != ""
    print("✓ test_no_comfyui_access: AD-30 соблюден")


def test_no_capability_selection():
    """CompositePromptBuilder не выбирает capability (AD-31)."""
    composite = CompositePromptBuilder(llm_builder=None)
    ctx = PromptContext(
        original_text="кот",
        capability="image.generate",
        active_asset_type="image",
    )
    result = composite.build(ctx)
    
    # Capability не должен влиять на результат
    assert isinstance(result.enhanced_prompt, str)
    assert "кот" in result.enhanced_prompt.lower()
    print("✓ test_no_capability_selection: AD-31 соблюден")


def test_single_llm_attempt():
    """Нет скрытого retry loop — LLM вызывается ровно один раз."""
    llm_builder = MagicMock()
    llm_builder.build.side_effect = _make_llm_error("LLM timeout")
    
    composite = CompositePromptBuilder(
        llm_builder=llm_builder,
        heuristic_builder=HeuristicPromptBuilder(),
    )
    result = composite.build(PromptContext(original_text="кот"))
    
    # LLM должен быть вызван ровно 1 раз
    assert llm_builder.build.call_count == 1, f"Ожидался 1 вызов, получено {llm_builder.build.call_count}"
    assert result.source == "heuristic_fallback"
    print("✓ test_single_llm_attempt: нет retry loop, single attempt")


def test_llm_error_classification():
    """Классификация ошибок LLM для диагностики."""
    # Timeout
    composite = CompositePromptBuilder(llm_builder=None)
    from app.prompt.composite import CompositePromptBuilder as CPB
    classifier = CPB(llm_builder=None)
    
    assert classifier._classify_llm_error(_make_llm_error("timeout")) == FALLBACK_REASON_LLM_TIMEOUT
    assert classifier._classify_llm_error(_make_llm_error("HTTP 500")) == FALLBACK_REASON_LLM_API_ERROR
    assert classifier._classify_llm_error(_make_llm_error("bad response")) == FALLBACK_REASON_LLM_INVALID_RESPONSE
    assert classifier._classify_llm_error(_make_llm_error("unknown error")) == FALLBACK_REASON_LLM_API_ERROR
    print("✓ test_llm_error_classification: ошибки классифицируются корректно")


def test_dependency_injection():
    """Dependency injection: builders передаются извне."""
    custom_llm = MagicMock()
    custom_llm.build.return_value = _make_llm_success_result("custom llm result")
    custom_heuristic = MagicMock()
    custom_heuristic.build.return_value = _make_heuristic_result("custom heuristic")
    
    composite = CompositePromptBuilder(llm_builder=custom_llm, heuristic_builder=custom_heuristic)
    result = composite.build(PromptContext(original_text="кот"))
    
    assert result.source == "llm"
    assert result.enhanced_prompt == "custom llm result"
    custom_llm.build.assert_called_once()
    custom_heuristic.build.assert_not_called()
    print("✓ test_dependency_injection: DI работает корректно")


if __name__ == "__main__":
    test_llm_success()
    test_llm_timeout_falls_back()
    test_llm_api_error_falls_back()
    test_llm_not_configured()
    test_invalid_llm_response_falls_back()
    test_intent_validation_failure_falls_back()
    test_heuristic_result_is_returned()
    test_no_comfyui_access()
    test_no_capability_selection()
    test_single_llm_attempt()
    test_llm_error_classification()
    test_dependency_injection()
    print("\n=== All M11.5 CompositePromptBuilder tests PASSED ===")
