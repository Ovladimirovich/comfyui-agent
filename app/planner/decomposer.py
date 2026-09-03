"""TaskDecomposer — декомпозиция сложных запросов на подзадачи.

Разбивает сложные запросы (например, "сгенерируй кота и увеличь разрешение")
на последовательность простых capability вызовов.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SubTask:
    """Одна подзадача в цепочке."""
    capability: str
    params: dict = field(default_factory=dict)
    description: str = ""

    def __repr__(self) -> str:
        return f"SubTask({self.capability}, {self.params})"


class TaskDecomposer:
    """Декомпозитор сложных запросов (M18).

    Разбивает запросы с conjunctions ("и", "and") на последовательность subtasks.
    """

    # Conjunctions для разделения запросов
    CONJUNCTIONS = (
        " и ", " and ", ", ", " а также ", " потом ", " после этого ",
        " затем ", " then ", " afterwards ",
    )

    # Keywords для определения capability
    EDIT_HINTS = (
        "улучши", "улучшить", "сделай реалистивнее", "измени", "отредактируй",
        "enhance", "improve", "edit", "refine", "adjust",
    )
    UPScale_HINTS = (
        "увеличь", "увеличить", "масштаб", "разрешение",
        "upscale", "enlarge", "bigger", "higher resolution",
    )
    GENERATE_HINTS = (
        "сгенерируй", "создай", "нарисуй", "сделай",
        "generate", "create", "draw", "make",
    )

    def decompose(self, request: str) -> list[SubTask]:
        """Декомпозировать запрос на подзадачи.

        Возвращает список SubTask в порядке выполнения.
        Если запрос простой (одна capability) — возвращает один SubTask.
        """
        # Пытаемся разделить по conjunctions
        parts = self._split_by_conjunctions(request)

        if len(parts) <= 1:
            # Простой запрос — определяем capability
            capability, params = self._analyze_part(request)
            return [SubTask(
                capability=capability,
                params=params,
                description=request,
            )]

        # Мульти-части — определяем capability для каждой
        subtasks = []
        for part in parts:
            part = part.strip()
            if not part:
                continue
            capability, params = self._analyze_part(part)
            subtasks.append(SubTask(
                capability=capability,
                params=params,
                description=part,
            ))

        return subtasks if subtasks else [SubTask(
            capability="image.generate",
            params={"prompt": request},
            description=request,
        )]

    def _split_by_conjunctions(self, request: str) -> list[str]:
        """Разделить запрос по conjunctions."""
        request_lower = request.lower()
        for conj in self.CONJUNCTIONS:
            if conj in request_lower:
                parts = re.split(re.escape(conj), request, flags=re.IGNORECASE)
                return [p for p in parts if p.strip()]
        return [request]

    def _analyze_part(self, part: str) -> tuple[str, dict]:
        """Определить capability и params для части запроса."""
        part_lower = part.lower()

        # Проверяем upscale hints
        for hint in self.UPScale_HINTS:
            if hint in part_lower:
                params = self._extract_params(part)
                return "image.upscale", params

        # Проверяем edit hints
        for hint in self.EDIT_HINTS:
            if hint in part_lower:
                params = self._extract_params(part)
                return "image.edit", params

        # Проверяем generate hints
        for hint in self.GENERATE_HINTS:
            if hint in part_lower:
                params = self._extract_params(part)
                return "image.generate", params

        # Default: image.generate с полным текстом как prompt
        return "image.generate", {"prompt": part}

    def _extract_params(self, text: str) -> dict:
        """Извлечь параметры из текста."""
        params = {}

        # Извлекаем prompt (всё кроме ключевых слов размера)
        prompt = text
        # Убираем ключевые слова capability
        for hint in self.EDIT_HINTS + self.UPScale_HINTS + self.GENERATE_HINTS:
            prompt = re.sub(rf'\b{re.escape(hint)}\b', '', prompt, flags=re.IGNORECASE)
        prompt = re.sub(r'\s+', ' ', prompt).strip()
        if prompt:
            params["prompt"] = prompt

        # Извлекаем размер
        size_match = re.search(r'(\d{1,4})\s*[x×]\s*(\d{1,4})', text, re.IGNORECASE)
        if size_match:
            params["width"] = int(size_match.group(1))
            params["height"] = int(size_match.group(2))

        # Извлекаем steps
        steps_match = re.search(r'(\d{1,3})\s*steps?', text, re.IGNORECASE)
        if steps_match:
            params["steps"] = int(steps_match.group(1))

        return params
