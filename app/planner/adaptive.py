"""AdaptivePlanner — контекстно-осведомлённый планировщик, учится на предыдущих результатах.

Использует ExecutionHistory + UserPreferences для оптимизации параметров.
Fallback на HeuristicPlanner при недостаточной истории.

AD-36: порог ≥ 3 считается по конкретной capability, не глобально.
AD-36: cross-capability contamination исключён — preferred_params фильтруются по capability.
"""
from __future__ import annotations

from typing import Optional

from app.engine.analytics import HistoryAnalytics
from app.engine.history import ExecutionHistory
from app.planner import HeuristicPlanner, PlanContext, PlanResult, Planner
from app.planner.preferences import UserPreferences


# Минимальное количество успешных попыток для конкретной capability
# перед включением adaptive planning
MIN_SUCCESSFUL_PER_CAPABILITY = 3


class AdaptivePlanner:
    """Контекстно-осведомлённый планировщик с обучением на истории (M16, AD-36).

    Использует HeuristicPlanner для определения capability,
    затем корректирует параметры на основе UserPreferences.

    AD-36: порог ≥ 3 считается по конкретной capability (не глобально).
    AD-36: cross-capability contamination исключён — preferred_params
    фильтруются по capability и context (active_workflow).

    User explicit overrides > learned preferences.
    """

    def __init__(
        self,
        history: ExecutionHistory,
        fallback: Optional[Planner] = None,
    ) -> None:
        self.history = history
        self.analytics = HistoryAnalytics(history)
        self.preferences = UserPreferences(self.analytics)
        self.fallback = fallback or HeuristicPlanner()

    def _has_enough_history(self, capability: str) -> bool:
        """Проверить, достаточно ли успешных попыток для конкретной capability.

        AD-36: порог считается по конкретной capability, не глобально.
        """
        return len(self.history.get_successful(capability)) >= MIN_SUCCESSFUL_PER_CAPABILITY

    def _context_aware_preferred_params(
        self,
        capability: str,
        context: Optional[PlanContext],
    ) -> dict:
        """Получить preferred params с учётом context.

        AD-36: фильтрует history по:
        1. capability (image.generate ≠ image.upscale)
        2. active_workflow (если задан в context)
        """
        # Получаем успешные попытки для этой capability
        successful = self.history.get_successful(capability)

        # Фильтруем по context.active_workflow (если задан)
        if context is not None and context.active_workflow is not None:
            successful = [
                r for r in successful
                if f"{r.workflow_id}@{r.workflow_version}" == context.active_workflow
            ]

        # Агрегируем preferred params (изолированно по capability + context)
        if not successful:
            return {}

        from collections import Counter, defaultdict

        param_counter: Counter = Counter()
        param_values: dict[str, Counter] = defaultdict(Counter)

        for record in successful:
            for key, value in record.params.items():
                param_counter[key] += 1
                if isinstance(value, (str, int, float, bool)):
                    param_values[key][value] += 1

        preferred = {}
        for key, count in param_counter.items():
            if count >= 2:
                values = param_values[key]
                if values:
                    preferred[key] = values.most_common(1)[0][0]

        return preferred

    def plan(self, request: str, context: Optional[PlanContext] = None) -> PlanResult:
        """Планирование с учётом истории и контекста.

        1) Fallback planner определяет capability + базовые params
        2) Если история < 3 для capability — возвращаем fallback result
        3) Если история >= 3 — корректирует params через context-aware preferences
        4) User explicit params (из request) > learned preferences
        """
        # 1) Базовое планирование (capability + params)
        base_result = self.fallback.plan(request, context)

        # 2) Порог по конкретной capability (AD-36)
        if not self._has_enough_history(base_result.capability):
            return base_result

        # 3) Context-aware preferred params (AD-36)
        preferred = self._context_aware_preferred_params(
            base_result.capability, context
        )
        if not preferred:
            return base_result

        # 4) Мержим: preferred params как дефолты, explicit из request перезаписывают
        merged_params = {**preferred, **base_result.params}

        # 5) Не перезаписываем explicit prompt из request
        if "prompt" in base_result.params:
            merged_params["prompt"] = base_result.params["prompt"]

        success_count = len(self.history.get_successful(base_result.capability))
        return PlanResult(
            capability=base_result.capability,
            params=merged_params,
            rationale=(
                f"adaptive: preferred params from {success_count} "
                f"successful {base_result.capability} records"
            ),
        )
