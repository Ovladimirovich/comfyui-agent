"""ClusterGateway — Execution Resource Layer (AD-42).

Выбирает Execution Backend для уже сформированного ExecutionPlan.
НЕ меняет ExecutionPlan, НЕ выбирает capability, НЕ создаёт workflow, НЕ обходит WorkflowEngine.

Строгие инварианты (MD-01..MD-05):
- MD-01: Failover НЕ автоматический при UNKNOWN execution state.
- MD-02: UNKNOWN health ≠ HEALTHY (не выбирать для routing).
- MD-03: Авто-retry на другой backend только если state достоверно "не выполнялся".
- MD-04: Gateway не имеет прямого доступа к ComfyUI HTTP (только через Provider).
- MD-05: Gateway не строит node-graph / не генерирует workflow.
"""

from __future__ import annotations

import time as _time
from typing import TYPE_CHECKING, Callable, Optional

from app.resource.models import (
    BackendHealth,
    BackendResource,
    BackendResourceState,
    ExecutionDispatchRecord,
    ReconcileState,
    RecoveryAction,
    RoutingDecision,
)

if TYPE_CHECKING:
    from app.engine.history import ExecutionHistory
    from app.registry.registry import WorkflowRegistry


class ClusterGateway:
    """Gateway выбора backend для execution.
    
    AD-42: Routing (auto) vs Failover (reconcile/inspect, NOT auto).
    """

    def __init__(
        self,
        backends: list[BackendResource] | None = None,
        health_check_fn: Callable[[BackendResource], Optional[BackendHealth]] | None = None,
        queue_depth_fn: Callable[[BackendResource], int] | None = None,
        history: Optional[ExecutionHistory] = None,
        registry: Optional[WorkflowRegistry] = None,
    ) -> None:
        self._backends: dict[str, BackendResource] = {}
        self._dispatch_records: dict[str, ExecutionDispatchRecord] = {}
        self._health_check_fn = health_check_fn
        self._queue_depth_fn = queue_depth_fn
        self._history = history
        self._registry = registry

        if backends:
            for b in backends:
                self._backends[b.backend_id] = b

    # --- resource management ---

    def register(self, resource: BackendResource) -> None:
        """Зарегистрировать backend в каталоге Gateway."""
        self._backends[resource.backend_id] = resource

    def unregister(self, backend_id: str) -> None:
        """Удалить backend из каталога."""
        self._backends.pop(backend_id, None)

    def get_backend(self, backend_id: str) -> BackendResource | None:
        return self._backends.get(backend_id)

    def list_backends(self) -> list[BackendResource]:
        return list(self._backends.values())

    # --- health / load / state ---

    def refresh_health(self) -> None:
        """Обновить health/load/state для всех backends."""
        for backend in self._backends.values():
            # Health
            if self._health_check_fn is not None:
                health = self._health_check_fn(backend)
                backend.health = health if health is not None else BackendHealth.UNKNOWN
            else:
                backend.health = BackendHealth.UNKNOWN

            # Queue depth
            if self._queue_depth_fn is not None:
                backend.queue_depth = self._queue_depth_fn(backend)
            else:
                backend.queue_depth = 0

            # Compute resource state
            backend.state = self._compute_resource_state(backend)

    @staticmethod
    def _compute_resource_state(resource: BackendResource) -> BackendResourceState:
        """Определить состояние ресурса.
        
        MD-02: UNKNOWN health ≠ HEALTHY → не выбирать для routing.
        """
        if resource.health == BackendHealth.UNKNOWN:
            return BackendResourceState.UNKNOWN
        if resource.health == BackendHealth.UNHEALTHY:
            return BackendResourceState.UNAVAILABLE
        if resource.health == BackendHealth.DEGRADED or resource.queue_depth > 3:
            return BackendResourceState.BUSY
        if resource.health == BackendHealth.HEALTHY:
            return BackendResourceState.AVAILABLE
        return BackendResourceState.UNKNOWN

    # --- routing (NEW job) ---

    def route(
        self,
        capability: str,
        available_models: set[str] | None = None,
    ) -> RoutingDecision:
        """Выбрать backend для NEW job.
        
        Routing — автоматический и безопасный (задача ещё не отправлена).
        Критерии: health → state → compatibility → load → priority.
        """
        # 1. Refresh health
        self.refresh_health()

        # 2. Filter— только selectable (AVAILABLE)
        candidates = [b for b in self._backends.values() if b.is_selectable]

        if not candidates:
            return RoutingDecision(
                backend_id="",
                rationale="No HEALTHY/AVAILABLE backends available (MD-02)",
                timestamp=_time.time(),
            )

        # 3. Filter by capability
        if capability:
            candidates = [
                b for b in candidates
                if not b.capabilities or capability in b.capabilities
            ]

        if not candidates:
            return RoutingDecision(
                backend_id="",
                rationale=f"No backend supports capability '{capability}'",
                timestamp=_time.time(),
            )

        # 4. Sort by: load (queue depth asc) → priority (desc)
        candidates.sort(key=lambda b: (b.queue_depth, -b.priority))

        selected = candidates[0]
        return RoutingDecision(
            backend_id=selected.backend_id,
            rationale=(
                f"Selected {selected.backend_id} "
                f"(state={selected.state.value}, "
                f"queue={selected.queue_depth}, "
                f"priority={selected.priority})"
            ),
            timestamp=_time.time(),
        )

    # --- dispatch tracking ---

    def record_dispatch(
        self,
        prompt_id: str,
        backend_id: str,
    ) -> None:
        """Записать факт диспетчеризации."""
        backend = self._backends.get(backend_id)
        record = ExecutionDispatchRecord(
            job_prompt_id=prompt_id,
            backend_id=backend_id,
            endpoint_url=backend.endpoint_url if backend else "",
            submitted_at=_time.time(),
        )
        self._dispatch_records[prompt_id] = record

        # Также записываем в ExecutionHistory
        if self._history is not None:
            # ExecutionHistory не хранит dispatch напрямую, но мы можем
            # дополнить существующие записи через backend_execution_identity
            pass

    def get_dispatch(self, prompt_id: str) -> ExecutionDispatchRecord | None:
        return self._dispatch_records.get(prompt_id)

    # --- reconcile (failover-safe) ---

    def reconcile(
        self,
        prompt_id: str,
        probe_fn: Callable[[str], ReconcileState] | None = None,
    ) -> ReconcileState:
        """Проверить реальное состояние задачи на backend.
        
        MD-01: Failover НЕ автоматический при UNKNOWN state.
        Возвращает ReconcileState — решение, что делать:
        - COMPLETED → вернуть результат (не дублировать)
        - NOT_ACCEPTED → безопасный retry
        - UNKNOWN → НЕ auto-failover (запросить пользователя)
        """
        record = self._dispatch_records.get(prompt_id)
        if record is None:
            return ReconcileState.UNKNOWN

        if probe_fn is not None:
            state = probe_fn(prompt_id)
            record.execution_state = state
            return state

        # Если probe_fn не задан — не можем установить состояние
        record.execution_state = ReconcileState.UNKNOWN
        return ReconcileState.UNKNOWN

    def can_auto_retry(self, prompt_id: str) -> bool:
        """Проверить, можно ли автоматически повторить на другом backend.
        
        MD-03: Только если state достоверно "не выполнялся".
        """
        record = self._dispatch_records.get(prompt_id)
        if record is None:
            return False
        return record.execution_state == ReconcileState.NOT_ACCEPTED