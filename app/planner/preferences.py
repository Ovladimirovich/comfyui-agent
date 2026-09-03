"""UserPreferences — агрегированные предпочтения пользователя из ExecutionHistory.

Используется AdaptivePlanner для определения "что работало раньше" для данного пользователя.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Optional

from app.engine.analytics import HistoryAnalytics


class UserPreferences:
    """Агрегированные предпочтения пользователя (M16).

    Источник: ExecutionHistory (успешные попытки).
    Не自治ное обучение (NG3) — только агрегация статистики.
    """

    def __init__(self, analytics: HistoryAnalytics) -> None:
        self.analytics = analytics

    def preferred_params(self, capability: str) -> dict:
        """Наиболее успешные параметры для capability.

        Возвращает параметры, которые чаще всего приводили к успеху.
        """
        return self.analytics.preferred_params(capability)

    def preferred_workflow(self, capability: str) -> Optional[str]:
        """Наиболее успешный workflow для capability."""
        rates = self.analytics.workflow_success_rates(capability)
        if not rates:
            return None
        # Выбираем workflow с наивысшим success rate (минимум 2 попытки)
        best_wf = None
        best_rate = 0.0
        for wf_key, rate in rates.items():
            if rate > best_rate and rate >= 0.5:  # минимум 50% успеха
                best_rate = rate
                best_wf = wf_key
        return best_wf

    def should_use_upscale(self, capability: str) -> bool:
        """Нуж ли upscale для capability (на основе истории).

        Если在过去 успешно использовался image.upscale — рекомендуем.
        """
        if capability != "image.generate":
            return False
        upscale_rate = self.analytics.success_rate("image.upscale")
        return upscale_rate > 0.3  # если >30% upscale были успешными

    def recommended_resolution(self, capability: str) -> Optional[tuple[int, int]]:
        """Рекомендуемое разрешение на основе истории."""
        params = self.analytics.preferred_params(capability)
        if not params:
            return None
        width = params.get("width")
        height = params.get("height")
        if width and height:
            try:
                return (int(width), int(height))
            except (ValueError, TypeError):
                return None
        return None

    def error_prone_params(self, capability: str) -> list[str]:
        """Параметры, которые часто приводят к ошибкам."""
        patterns = self.analytics.error_patterns(capability)
        if not patterns:
            return []
        # Возвращаем error_class с количеством > 2
        return [ec for ec, count in patterns.items() if count > 2]
