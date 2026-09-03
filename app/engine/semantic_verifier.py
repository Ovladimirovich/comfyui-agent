"""M14 — Semantic Verifier: проверка output через vision model.

SemanticVerifier использует vision model (OpenRouter) для оценки
соответствия output запросу пользователя.

Usage:
    verifier = SemanticVerifier(api_key="...")
    result = verifier.verify(
        request="a cat sitting on a table",
        output_path="/path/to/image.png",
        capability="image.generate",
    )
    if result.score < 0.5:
        # output не соответствует запросу
"""
from __future__ import annotations

import base64
import json
import os
import urllib.request
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SemanticVerificationResult:
    """Результат semantic verification."""
    score: float  # 0.0–1.0 (качество/соответствие)
    matches_intent: bool  # True если output соответствует запросу
    issues: list[str] = field(default_factory=list)  # обнаруженные проблемы
    suggested_params: dict | None = None  # рекомендуемые параметры для retry
    raw_response: str | None = None  # сырой ответ vision model (для debug)
    error: str | None = None  # ошибка verification (если vision API недоступен)

    @property
    def ok(self) -> bool:
        """True если score >= 0.5 и нет критических issues."""
        return self.score >= 0.5 and self.error is None


class SemanticVerifierError(RuntimeError):
    """Ошибка semantic verification."""
    pass


class SemanticVerifier:
    """Vision-based verification через OpenRouter.

    Использует vision model для оценки:
    - Соответствует ли output запросу пользователя
    - Каково качество output
    - Есть ли проблемы (артефакты, неправильный контент, и т.д.)

    Fallback: если vision API недоступен → возвращает score=0.5 (neutral).
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "openai/gpt-4o-mini",
        base_url: str = "https://openrouter.ai/api/v1/chat/completions",
        timeout: int = 30,
    ) -> None:
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        self.model = model
        self.base_url = base_url
        self.timeout = timeout

    def verify(
        self,
        request: str,
        output_path: str,
        capability: str = "image.generate",
        previous_output_path: str | None = None,
    ) -> SemanticVerificationResult:
        """Проверить output через vision model.

        Args:
            request: исходный запрос пользователя
            output_path: путь к output файлу (image/video/audio)
            capability: capability (image.generate, image.edit, и т.д.)
            previous_output_path: путь к предыдущему output (для сравнения, опционально)

        Returns:
            SemanticVerificationResult с score, issues, suggested_params
        """
        if not self.api_key:
            return SemanticVerificationResult(
                score=0.5,
                matches_intent=True,
                error="vision API not configured (no OPENROUTER_API_KEY)",
            )

        if not os.path.exists(output_path):
            return SemanticVerificationResult(
                score=0.0,
                matches_intent=False,
                issues=["output file not found"],
                error=f"file not found: {output_path}",
            )

        # Определяем тип файла
        mime = self._detect_mime(output_path)
        if not mime:
            return SemanticVerificationResult(
                score=0.5,
                matches_intent=True,
                error=f"unsupported file type: {output_path}",
            )

        # Кодируем файл в base64
        try:
            with open(output_path, "rb") as f:
                file_data = base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            return SemanticVerificationResult(
                score=0.0,
                matches_intent=False,
                issues=[f"failed to read output file: {e}"],
                error=str(e),
            )

        # Строим prompt для vision model
        system_prompt = self._build_system_prompt(capability)
        user_content = self._build_user_content(
            request, file_data, mime, capability, previous_output_path
        )

        # Отправляем запрос
        try:
            response = self._call_vision_api(system_prompt, user_content)
            return self._parse_response(response)
        except Exception as e:
            return SemanticVerificationResult(
                score=0.5,
                matches_intent=True,
                error=f"vision API error: {e}",
            )

    def _detect_mime(self, path: str) -> str | None:
        """Определить MIME тип по расширению."""
        ext = os.path.splitext(path)[1].lower()
        mime_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".mp4": "video/mp4",
            ".webm": "video/webm",
            ".wav": "audio/wav",
            ".mp3": "audio/mpeg",
            ".ogg": "audio/ogg",
        }
        return mime_map.get(ext)

    def _build_system_prompt(self, capability: str) -> str:
        """Построить system prompt для vision model."""
        return (
            "Ты — AI-ассистент для проверки качества сгенерированных медиафайлов.\n"
            "Проанализируй output и оцени его по следующим критериям:\n"
            "1. Соответствие запросу (0.0–1.0): насколько output соответствует исходному запросу\n"
            "2. Качество (0.0–1.0): отсутствие артефактов, правильная композиция, детализация\n"
            "3. Проблемы: список обнаруженных проблем (если есть)\n"
            "4. Рекомендации: suggested parameters для улучшения (если возможно)\n\n"
            "Верни ТОЛЬКО JSON без markdown:\n"
            '{"score": 0.0-1.0, "matches_intent": true/false, '
            '"issues": ["problem1", ...], '
            '"suggested_params": {"param": "value"} or null}\n\n'
            "score >= 0.7 = хорошо, 0.5–0.7 = приемлемо, < 0.5 = плохо"
        )

    def _build_user_content(
        self,
        request: str,
        file_data: str,
        mime: str,
        capability: str,
        previous_output_path: str | None = None,
    ) -> list[dict]:
        """Построить user content с изображением."""
        content = []

        # Текстовый контекст
        text_parts = [
            f"Запрос пользователя: {request}",
            f"Capability: {capability}",
        ]
        if previous_output_path:
            text_parts.append(f"Предыдущий output: {os.path.basename(previous_output_path)}")
        content.append({"type": "text", "text": "\n".join(text_parts)})

        # Изображение
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:{mime};base64,{file_data}",
            },
        })

        return content

    def _call_vision_api(self, system_prompt: str, user_content: list[dict]) -> dict:
        """Вызвать vision model через OpenRouter."""
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "response_format": {"type": "json_object"},
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
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _parse_response(self, response: dict) -> SemanticVerificationResult:
        """Распарсить ответ vision model."""
        try:
            content = response["choices"][0]["message"]["content"]
            obj = json.loads(content)

            score = float(obj.get("score", 0.5))
            score = max(0.0, min(1.0, score))  # clamp 0.0–1.0

            matches_intent = bool(obj.get("matches_intent", score >= 0.5))
            issues = list(obj.get("issues", []))
            suggested_params = obj.get("suggested_params")

            return SemanticVerificationResult(
                score=score,
                matches_intent=matches_intent,
                issues=issues,
                suggested_params=suggested_params,
                raw_response=content,
            )
        except (KeyError, json.JSONDecodeError, TypeError) as e:
            return SemanticVerificationResult(
                score=0.5,
                matches_intent=True,
                error=f"failed to parse vision response: {e}",
                raw_response=str(response),
            )
