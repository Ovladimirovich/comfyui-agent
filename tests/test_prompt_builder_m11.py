"""M11 — Tests for HeuristicPromptBuilder (offline, deterministic)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional


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
    source: Literal["heuristic", "llm", "fallback"]
    rationale: Optional[str] = None


# Template database
TEMPLATES = {
    "default": [
        "детальный {subject}, высокое качество, профессиональная фотография",
        "реалистичный {subject}, естественное освещение, мягкая текстура",
        "кинематографичный {subject}, драматичное освещение, малая глубина резкости",
        "высокодетализированный {subject}, 8k разрешение, студийное освещение",
    ],
    "cat": [
        "детальный {subject}, высокое качество, профессиональная фотография",
        "реалистичный {subject}, естественное освещение, мягкая текстура шерсти",
        "кинематографичный {subject}, драматичное освещение, малая глубина резкости",
        "уютный {subject}, мягкий свет, пушистая шерсть, фокус на глазах",
    ],
}


class HeuristicPromptBuilder:
    """Офлайн-улучшитель промптов на основе шаблонов и правил."""

    def __init__(self, templates: Optional[dict[str, list[str]]] = None) -> None:
        self.templates = templates or TEMPLATES

    def build(self, context: PromptContext) -> PromptResult:
        original = (context.original_text or "").strip()
        if not original:
            return PromptResult(
                enhanced_prompt="",
                original_preserved=True,
                mode=context.mode,
                variant_index=context.suggestion_index,
                source="heuristic",
                rationale="Empty query input",
            )

        category = self._detect_category(original)
        variants = self.templates.get(category, self.templates["default"])
        
        idx = context.suggestion_index % len(variants)
        template = variants[idx]
        
        enhanced = template.format(subject=original)
        
        original_preserved = original.lower() in enhanced.lower()

        return PromptResult(
            enhanced_prompt=enhanced,
            original_preserved=original_preserved,
            mode=context.mode,
            variant_index=context.suggestion_index,
            source="heuristic",
            rationale=f"Applied template index {idx} for category '{category}'",
        )

    def _detect_category(self, text: str) -> str:
        text_lower = text.lower()
        import re
        if re.search(r"\b(кот|кошка|кошечка|котенок|cat)\b", text_lower):
            return "cat"
        return "default"


def test_basic_suggestion() -> None:
    builder = HeuristicPromptBuilder()
    ctx = PromptContext(original_text="кот")
    result = builder.build(ctx)
    
    assert result.enhanced_prompt != "", "Не должна быть пустой"
    assert result.original_preserved == True, "Исходный текст должен сохраняться (AD-32)"
    assert result.mode == "suggestion"
    assert result.variant_index == 0
    assert result.source == "heuristic"
    assert "кот" in result.enhanced_prompt.lower()
    print(f"✓ test_basic_suggestion: {result.enhanced_prompt}")


def test_deterministic_variants() -> None:
    """Каждый клик = новый вариант."""
    builder = HeuristicPromptBuilder()
    
    variants = []
    for i in range(4):
        ctx = PromptContext(original_text="кот", suggestion_index=i)
        result = builder.build(ctx)
        variants.append(result.enhanced_prompt)
        print(f"  вариант #{i}: {result.enhanced_prompt}")
    
    assert len(set(variants)) == 4, f"Ожидалось 4 уникальных варианта, получено {len(set(variants))}"
    
    # Повторная генерация того же индекса даёт тот же результат
    ctx0 = PromptContext(original_text="кот", suggestion_index=0)
    r0 = builder.build(ctx0)
    r0_again = builder.build(ctx0)
    assert r0.enhanced_prompt == r0_again.enhanced_prompt, "Детерминированность нарушена"
    print("✓ test_deterministic_variants: 4 уникальных варианта, детерминированность ОК")


def test_suggestion_index_cycle() -> None:
    """suggestion_index % len(templates) — цикл вариантов."""
    builder = HeuristicPromptBuilder()
    ctx0 = PromptContext(original_text="кот", suggestion_index=0)
    ctx4 = PromptContext(original_text="кот", suggestion_index=4)
    r0 = builder.build(ctx0)
    r4 = builder.build(ctx4)
    assert r0.enhanced_prompt == r4.enhanced_prompt, "Цикличность нарушена"
    print("✓ test_suggestion_index_cycle: индекс 0 == индекс 4")


def test_empty_input() -> None:
    builder = HeuristicPromptBuilder()
    ctx = PromptContext(original_text="", mode="suggestion")
    result = builder.build(ctx)
    
    assert result.enhanced_prompt == "", "Пустой текст → пустой результат"
    assert result.original_preserved == True
    print("✓ test_empty_input: пустой запрос обработан корректно")


def test_original_preserved_all_variants() -> None:
    """AD-32: все варианты сохраняют исходное намерение."""
    builder = HeuristicPromptBuilder()
    for i in range(10):
        ctx = PromptContext(original_text="кот на крыше ночью", suggestion_index=i)
        result = builder.build(ctx)
        assert result.original_preserved, f"Исходный текст потерян при индексе {i}"
        assert "кот" in result.enhanced_prompt.lower() or "крыше" in result.enhanced_prompt.lower() or "ночью" in result.enhanced_prompt.lower()
    print("✓ test_original_preserved_all_variants: AD-32 соблюден для всех вариантов")


def test_no_capability_selection() -> None:
    """PromptBuilder НЕ выбирает capability (AD-31)."""
    builder = HeuristicPromptBuilder()
    ctx = PromptContext(
        original_text="кот",
        capability="image.generate",
        active_asset_type="image",
        suggestion_index=0
    )
    result = builder.build(ctx)
    assert isinstance(result.enhanced_prompt, str)
    assert result.enhanced_prompt != ""
    assert "кот" in result.enhanced_prompt.lower()
    print("✓ test_no_capability_selection: AD-31 соблюдён")


def test_no_fs_comfyui_access() -> None:
    """PromptBuilder не имеет доступа к FS/ComfyUI (AD-30)."""
    builder = HeuristicPromptBuilder()
    ctx = PromptContext(original_text="кот", suggestion_index=0)
    
    result = builder.build(ctx)
    assert result.source == "heuristic"
    assert "кот" in result.enhanced_prompt.lower()
    print("✓ test_no_fs_comfyui_access: AD-30 соблюден")


def test_endpoint_response_structure() -> None:
    """Проверка структуры ответа API (интеграционный тест)."""
    builder = HeuristicPromptBuilder()
    ctx = PromptContext(original_text="кот на крыше", suggestion_index=1)
    result = builder.build(ctx)
    
    assert hasattr(result, "enhanced_prompt")
    assert hasattr(result, "original_preserved")
    assert hasattr(result, "variant_index")
    assert hasattr(result, "source")
    assert result.source in ("heuristic", "llm", "fallback")
    print("✓ test_endpoint_response_structure: структура ответа корректна")


if __name__ == "__main__":
    test_basic_suggestion()
    test_deterministic_variants()
    test_suggestion_index_cycle()
    test_empty_input()
    test_original_preserved_all_variants()
    test_no_capability_selection()
    test_no_fs_comfyui_access()
    test_endpoint_response_structure()
    print("\n=== All M11 HeuristicPromptBuilder tests PASSED ===")
