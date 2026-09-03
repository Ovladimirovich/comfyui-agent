"""M11 — LLMPromptBuilder (Online, OpenAI-compatible API).

Онлайн-улучшитель промптов через OpenAI-compatible API (AD-14, AD-30, AD-31, AD-32).
Использует stdlib urllib.request — без новых зависимостей.
НЕ делает fallback на heuristic (M11.5 — CompositePromptBuilder).
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Optional

from app.prompt.builder import PromptContext, PromptResult


DEFAULT_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-4o-mini"
DEFAULT_TIMEOUT = 30

SYSTEM_PROMPT = (
    "Improve the user's image generation prompt without changing the user's original intent. "
    "Preserve the subject and requested elements. "
    "Add useful visual detail only when appropriate. "
    "Return only the improved prompt, without explanations, markdown or quotation marks."
)


class LLMPromptBuilderError(RuntimeError):
    """Ошибка LLM PromptBuilder (API error, timeout, bad response)."""


class LLMPromptBuilder:
    """Онлайн-улучшитель промптов через OpenAI-compatible API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self.api_key = api_key or os.environ.get("LLM_API_KEY")
        self.model = model or os.environ.get("LLM_MODEL", DEFAULT_MODEL)
        self.base_url = base_url or os.environ.get("LLM_BASE_URL", DEFAULT_BASE_URL)
        self.timeout = timeout or int(os.environ.get("LLM_TIMEOUT", str(DEFAULT_TIMEOUT)))

        if not self.api_key:
            raise LLMPromptBuilderError(
                "LLMPromptBuilder требует LLM_API_KEY (или конструкторского параметра)"
            )

    def build(self, context: PromptContext) -> PromptResult:
        original = (context.original_text or "").strip()
        if not original:
            return PromptResult(
                enhanced_prompt="",
                original_preserved=True,
                mode=context.mode,
                variant_index=context.suggestion_index,
                source="llm",
                rationale="Empty query input",
            )

        enhanced = self._call_llm(original)

        # AD-32: консервативная проверка — ключевые слова из оригинала присутствуют
        original_preserved = self._check_intent_preserved(original, enhanced)

        return PromptResult(
            enhanced_prompt=enhanced,
            original_preserved=original_preserved,
            mode=context.mode,
            variant_index=context.suggestion_index,
            source="llm",
            rationale=f"LLM enhanced prompt via {self.model}",
            original_prompt=original,
        )

    def _call_llm(self, text: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
        }
        req = urllib.request.Request(
            self.base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:400]
            raise LLMPromptBuilderError(f"LLM HTTP {e.code}: {body}") from e
        except urllib.error.URLError as e:
            raise LLMPromptBuilderError(f"LLM connection error: {e.reason}") from e
        except TimeoutError as e:
            raise LLMPromptBuilderError(f"LLM timeout after {self.timeout}s") from e

        try:
            content = data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as e:
            raise LLMPromptBuilderError(f"LLM bad response structure: {e}") from e

        if not content:
            raise LLMPromptBuilderError("LLM returned empty response")

        return content

    def _check_intent_preserved(self, original: str, enhanced: str) -> bool:
        """AD-32: консервативная проверка сохранения исходного намерения.

        Ключевые слова из original (длиной >= 3 символов) должны присутствовать в enhanced.
        Это не semantic validation, но минимальный guard против полной потери смысла.
        """
        if not original or not enhanced:
            return False

        original_words = set(re.findall(r"\b\w{3,}\b", original.lower()))
        if not original_words:
            # Если нет слов длиннее 3 символов — проверяем поwhole string
            return original.lower() in enhanced.lower()

        enhanced_lower = enhanced.lower()
        preserved_count = sum(1 for w in original_words if w in enhanced_lower)
        # Требем preservation хотя бы 50% ключевых слов
        return preserved_count >= max(1, len(original_words) // 2)
