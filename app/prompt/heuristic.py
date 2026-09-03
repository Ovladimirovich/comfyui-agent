"""M11 — Heuristic Prompt Builder (Offline).

Офлайн-улучшитель промптов на основе шаблонов и детерминированных правил (AD-14, AD-30, AD-31, AD-32).
"""
from __future__ import annotations

import re
from typing import Optional

from app.prompt.builder import PromptContext, PromptResult
from app.prompt.templates import TEMPLATES


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
        
        # Детерминированный выбор варианта по индексу
        idx = context.suggestion_index % len(variants)
        template = variants[idx]
        
        enhanced = template.format(subject=original)
        
        # AD-32 check: original text preserved inside enhanced prompt
        original_preserved = original.lower() in enhanced.lower()

        return PromptResult(
            enhanced_prompt=enhanced,
            original_preserved=original_preserved,
            mode=context.mode,
            variant_index=context.suggestion_index,
            source="heuristic",
            rationale=f"Applied template index {idx} for category '{category}'",
            original_prompt=original,
        )

    def _detect_category(self, text: str) -> str:
        text_lower = text.lower()
        if re.search(r"\b(кот|кошка|кошечка|котенок|cat)\b", text_lower):
            return "cat"
        if re.search(r"\b(человек|девушка|парень|портрет|portrait|face)\b", text_lower):
            return "portrait"
        if re.search(r"\b(гора|лес|река|пейзаж|город|landscape|nature)\b", text_lower):
            return "landscape"
        return "default"
