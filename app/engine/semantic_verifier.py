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

# M25.3: порог оценки temporal consistency (симметрично semantic threshold 0.5).
# Результат ниже порога трактуется как провал verification (failure path).
TEMPORAL_CONSISTENCY_THRESHOLD = 0.5


@dataclass
class SemanticVerificationResult:
    """Результат semantic verification."""
    score: float  # 0.0–1.0 (качество/соответствие)
    matches_intent: bool  # True если output соответствует запросу
    issues: list[str] = field(default_factory=list)  # обнаруженные проблемы
    suggested_params: dict | None = None  # рекомендуемые параметры для retry
    raw_response: str | None = None  # сырой ответ vision model (для debug)
    error: str | None = None  # ошибка verification (если vision API недоступен)
    # M25.3: temporal-specific fields
    temporal_score: float | None = None  # 0.0–1.0 (continuity между кадрами)
    temporal_issues: list[str] = field(default_factory=list)  # проблемы temporal consistency

    @property
    def ok(self) -> bool:
        """True если score >= 0.5 и нет критических issues."""
        return self.score >= 0.5 and self.error is None

    @ok.setter
    def ok(self, value: bool) -> None:
        # property writable for test mocking; no-op for normal use
        pass


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

    def verify_temporal_consistency(
        self,
        sequence_assets: list[str],
        request: str = "",
        capability: str = "video.image_to_video",
    ) -> SemanticVerificationResult:
        """Проверить temporal consistency последовательности image assets.

        M25.3: Анализирует визуальную continuity между consecutive кадрами
        через vision model. Возвращает temporal_score 0.0–1.0.

        Архитектурные инварианты:
        - НЕ создаёт Asset — только read-only анализ
        - НЕ влияет на canonical ingest (происходит после verification)
        - Fallback: при отсутствии API ключа → temporal_score=None (neutral)
        """
        if not sequence_assets:
            return SemanticVerificationResult(
                score=0.0,
                matches_intent=False,
                temporal_score=0.0,
                temporal_issues=["empty sequence"],
                issues=["empty sequence"],
            )

        if len(sequence_assets) < 2:
            return SemanticVerificationResult(
                score=0.5,
                matches_intent=True,
                temporal_score=None,
                temporal_issues=["single asset — temporal check N/A"],
            )

        if not self.api_key:
            return SemanticVerificationResult(
                score=0.5,
                matches_intent=True,
                temporal_score=None,
                error="vision API not configured (no OPENROUTER_API_KEY)",
            )

        # Проверка существования файлов
        missing = [p for p in sequence_assets if not os.path.exists(p)]
        if missing:
            return SemanticVerificationResult(
                score=0.0,
                matches_intent=False,
                temporal_score=0.0,
                temporal_issues=[f"missing asset: {os.path.basename(m)}" for m in missing],
                issues=[f"missing asset: {os.path.basename(m)}" for m in missing],
            )

        # Sample frame pairs (first, middle, last) для efficiency
        indices = self._sample_indices(len(sequence_assets), max_samples=5)
        pairs = [(indices[i], indices[i + 1]) for i in range(len(indices) - 1)]

        if not pairs:
            return SemanticVerificationResult(
                score=0.5,
                matches_intent=True,
                temporal_score=None,
                temporal_issues=["insufficient frames for comparison"],
            )

        frame_scores = []
        temporal_issues = []

        for i, j in pairs:
            pair_result = self._compare_frame_pair(
                sequence_assets[indices[i]],
                sequence_assets[indices[j]],
                request,
                capability,
            )
            frame_scores.append(pair_result.score)
            if pair_result.temporal_issues:
                temporal_issues.extend(pair_result.temporal_issues)

        if not frame_scores:
            return SemanticVerificationResult(
                score=0.5,
                matches_intent=True,
                temporal_score=None,
            )

        temporal_score = sum(frame_scores) / len(frame_scores)
        temporal_score = max(0.0, min(1.0, temporal_score))

        return SemanticVerificationResult(
            score=temporal_score,
            matches_intent=temporal_score >= 0.5,
            temporal_score=temporal_score,
            temporal_issues=temporal_issues if temporal_issues else None,
            issues=temporal_issues if temporal_issues else None,
        )

    def _sample_indices(self, total: int, max_samples: int = 5) -> list[int]:
        """Выбрать индексы для sample: first, middle(s), last."""
        if total <= 2:
            return list(range(total))
        indices = [0]  # first
        step = max(1, (total - 2) // (max_samples - 2))
        for i in range(1, total - 1):
            if i % step == 0:
                indices.append(i)
                if len(indices) >= max_samples - 1:
                    break
        indices.append(total - 1)  # last
        return indices[:max_samples]

    def _compare_frame_pair(
        self,
        frame_a_path: str,
        frame_b_path: str,
        request: str,
        capability: str,
    ) -> SemanticVerificationResult:
        """Сравнить два consecutive frame для temporal continuity."""
        if not self.api_key:
            return SemanticVerificationResult(
                score=0.5,
                matches_intent=True,
                temporal_score=0.5,
            )

        try:
            with open(frame_a_path, "rb") as f:
                data_a = base64.b64encode(f.read()).decode("utf-8")
            with open(frame_b_path, "rb") as f:
                data_b = base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            return SemanticVerificationResult(
                score=0.0,
                matches_intent=False,
                temporal_score=0.0,
                temporal_issues=[f"failed to read frame pair: {e}"],
            )

        prompt = (
            "Ты проверяешь temporal consistency между двумя consecutive кадрами видео.\n"
            "Оцени визуальную continuity: насколько плавно кадр B переходит из кадра A.\n"
            "Критерии: отсутствие резких скачков, сохранение объектов, плавность движения.\n\n"
            "Верни ТОЛЬКО JSON:\n"
            '{"score": 0.0-1.0, "temporal_issues": ["issue1, ..."] or null}\n\n'
            "score >= 0.7 = good continuity, 0.5–0.7 = acceptable, < 0.5 = poor"
        )

        user_content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{data_a}"}},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{data_b}"}},
        ]

        try:
            response = self._call_vision_api(prompt, user_content)
            content = response["choices"][0]["message"]["content"]
            obj = json.loads(content)
            score = max(0.0, min(1.0, float(obj.get("score", 0.5))))
            issues = obj.get("temporal_issues") or []
            return SemanticVerificationResult(
                score=score,
                matches_intent=score >= 0.5,
                temporal_score=score,
                temporal_issues=issues if issues else None,
            )
        except Exception as e:
            return SemanticVerificationResult(
                score=0.5,
                matches_intent=True,
                temporal_score=0.5,
                temporal_issues=[f"vision API error: {e}"],
            )
