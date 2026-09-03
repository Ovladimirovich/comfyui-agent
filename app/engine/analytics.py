"""HistoryAnalytics — расширенная аналитика по ExecutionHistory.

Предоставляет агрегированные метрики для AdaptivePlanner:
- success_rate (per capability)
- avg_duration (per capability)
- preferred_params (per capability)
- error_patterns (per error_class)
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Optional

from app.engine.history import ExecutionHistory, ExecutionRecord


class HistoryAnalytics:
    """Расширенная аналитика по ExecutionHistory (M16).

    Используется AdaptivePlanner для определения "что работало раньше".
    """

    def __init__(self, history: ExecutionHistory) -> None:
        self.history = history

    def success_rate(self, capability: Optional[str] = None) -> float:
        """Доля успешных попыток (0.0–1.0)."""
        return self.history.success_rate(capability)

    def avg_duration(self, capability: Optional[str] = None) -> float:
        """Средняя длительность успешных попыток."""
        return self.history.avg_duration(capability)

    def preferred_params(self, capability: str) -> dict:
        """Наиболее успешные параметры для capability.

        Анализирует успешные попытки и возвращает параметры,
        которые чаще всего приводили к успеху.
        """
        successful = self.history.get_successful(capability)
        if not successful:
            return {}

        # Подсчитываем частоту параметров в успешных попытках
        param_counter: Counter = Counter()
        param_values: dict[str, Counter] = defaultdict(Counter)

        for record in successful:
            for key, value in record.params.items():
                param_counter[key] += 1
                if isinstance(value, (str, int, float, bool)):
                    param_values[key][value] += 1

        # Возвращаем наиболее частые значения для каждого параметра
        preferred = {}
        for key, count in param_counter.items():
            if count >= 2:  # минимум 2 успешные попытки с этим параметром
                values = param_values[key]
                if values:
                    preferred[key] = values.most_common(1)[0][0]

        return preferred

    def error_patterns(self, capability: Optional[str] = None) -> dict:
        """Паттерны ошибок по error_class.

        Возвращает {error_class: count} для capability.
        """
        failed = self.history.get_failed(capability)
        patterns: Counter = Counter()
        for record in failed:
            if record.error_class:
                patterns[record.error_class] += 1
        return dict(patterns)

    def workflow_success_rates(self, capability: str) -> dict:
        """Успешность по workflow для capability.

        Возвращает {workflow_id@version: success_rate}.
        """
        attempts = self.history.get_attempts(capability)
        if not attempts:
            return {}

        workflow_attempts: dict[str, list[ExecutionRecord]] = defaultdict(list)
        for record in attempts:
            key = f"{record.workflow_id}@{record.workflow_version}"
            workflow_attempts[key].append(record)

        rates = {}
        for wf_key, records in workflow_attempts.items():
            successful = sum(1 for r in records if r.state == "SUCCESS")
            rates[wf_key] = successful / len(records) if records else 0.0

        return rates

    def most_used_workflows(self, capability: str, top_n: int = 3) -> list[str]:
        """Наиболее используемые workflow для capability."""
        attempts = self.history.get_attempts(capability)
        if not attempts:
            return []

        wf_counter: Counter = Counter()
        for record in attempts:
            key = f"{record.workflow_id}@{record.workflow_version}"
            wf_counter[key] += 1

        return [wf for wf, _ in wf_counter.most_common(top_n)]

    def avg_attempts_before_success(self, capability: Optional[str] = None) -> float:
        """Среднее количество попыток до успеха.

        Группирует по capability и считает среднее.
        """
        attempts = self.history.get_attempts(capability)
        if not attempts:
            return 0.0

        # Группируем по capability
        by_capability: dict[str, list[ExecutionRecord]] = defaultdict(list)
        for record in attempts:
            by_capability[record.capability].append(record)

        total_attempts = 0
        total_successes = 0

        for cap, records in by_capability.items():
            # Сортируем по времени
            sorted_records = sorted(records, key=lambda r: r.timestamp)
            current_attempts = 0
            for record in sorted_records:
                current_attempts += 1
                if record.state == "SUCCESS":
                    total_attempts += current_attempts
                    total_successes += 1
                    current_attempts = 0

        if total_successes == 0:
            return 0.0
        return total_attempts / total_successes
