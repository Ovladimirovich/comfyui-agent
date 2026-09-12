"""HeuristicPlanner — keyword-based capability selection (M8/M9.1).

Offline, deterministic. Context-aware: active_asset_type + edit/upscale hints
bias capability selection (AD-31: planner selects capability, NOT PromptBuilder).
S9: explicit image attach текущего turn → image.edit (AD-23 приоритет explicit).
Extracts size/step params from request text.
"""
from __future__ import annotations

import re
from typing import Optional

from app.planner.plan import PlanContext, PlanResult, Planner


# Edit hints: when active_asset_type == "image" → image.edit
EDIT_HINTS = (
    "улучши", "улучшить", "сделай реалистивнее", "измени", "отредактируй",
    "enhance", "improve", "edit", "refine", "adjust", "make realistic",
    "better quality", "more detailed",
)

# Upscale hints: → image.upscale
UPSCALE_HINTS = (
    "увеличь", "увеличить", "масштаб", "разрешение", "крупнее", "масштабируй",
    "выше разрешение", "высоком разрешении",
    "upscale", "enlarge", "bigger", "higher resolution",
)

# Generate defaults
GENERATE_HINTS = (
    "сгенерируй", "создай", "нарисуй", "сделай",
    "generate", "create", "draw", "make",
)

# Media keywords
AUDIO_KEYWORDS = ("трек", "музыка", "звук", "аудио", "lo-fi", "beat", "sound")
VIDEO_KEYWORDS = ("видео", "ролик", "animate", "video", "animation")

# Text keywords → text.generate (workflow: workflows/text_generate)
TEXT_KEYWORDS = (
    "напиши", "сочини", "текст", "эссе", "поговори",
    "chat", "write", "text", "essay", "haiku",
)


class HeuristicPlanner(Planner):
    """Keyword-based planner with context-aware edit/upscale routing."""

    def plan(self, request: str, context: Optional[PlanContext] = None) -> PlanResult:
        req = (request or "").strip()
        req_lower = req.lower()
        ctx = context or PlanContext()

        # Extract explicit params from request text (size, steps)
        params = self._extract_params(req)

        # 1. Edit hint + active image → image.edit
        if ctx.active_asset_type == "image":
            for hint in EDIT_HINTS:
                if hint in req_lower:
                    if "image.edit" in ctx.capabilities:
                        return PlanResult(
                            capability="image.edit",
                            params={**params, "prompt": req},
                            rationale=f"edit_hint: '{hint}' + active image",
                        )

        # 2. Upscale hint + active image → image.upscale
        if ctx.active_asset_type == "image":
            for hint in UPSCALE_HINTS:
                if hint in req_lower:
                    if "image.upscale" in ctx.capabilities:
                        return PlanResult(
                            capability="image.upscale",
                            params={**params, "prompt": req},
                            rationale=f"upscale_hint: '{hint}' + active image",
                        )

        # 3. Media-type keywords
        for kw in AUDIO_KEYWORDS:
            if kw in req_lower:
                return PlanResult(
                    capability="audio.generate",
                    params={**params, "prompt": req},
                    rationale=f"audio_keyword: '{kw}'",
                )
        for kw in VIDEO_KEYWORDS:
            if kw in req_lower:
                return PlanResult(
                    capability="video.generate",
                    params={**params, "prompt": req},
                    rationale=f"video_keyword: '{kw}'",
                )

        # 4. Text keywords → text.generate
        for kw in TEXT_KEYWORDS:
            if kw in req_lower:
                return PlanResult(
                    capability="text.generate",
                    params={**params, "prompt": req},
                    rationale=f"text_keyword: '{kw}'",
                )

        # 5. S9: explicit image attach текущего turn → image.edit.
        # Медиа/text-ключевые слова имеют приоритет (вложение не затеняет
        # явный intent «сделай трек»/«напиши текст»). Если image.edit недоступен —
        # fallback на image.generate (не резолвим несуществующую capability).
        if ctx.explicit_asset_type == "image" and "image.edit" in ctx.capabilities:
            return PlanResult(
                capability="image.edit",
                params={**params, "prompt": req},
                rationale="explicit_image_attach",
            )

        # 6. Default: image.generate
        return PlanResult(
            capability="image.generate",
            params={**params, "prompt": req},
            rationale="default",
        )

    @staticmethod
    def _extract_params(text: str) -> dict:
        """Извлечь size/step параметры из текста запроса."""
        params: dict = {}
        # Размер: NxN или N x N
        size_match = re.search(r'(\d{1,4})\s*[x×X]\s*(\d{1,4})', text)
        if size_match:
            params["width"] = int(size_match.group(1))
            params["height"] = int(size_match.group(2))
        # Steps
        steps_match = re.search(r'(\d{1,3})\s*steps?', text, re.IGNORECASE)
        if steps_match:
            params["steps"] = int(steps_match.group(1))
        return params
