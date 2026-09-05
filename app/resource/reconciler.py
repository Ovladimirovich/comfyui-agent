"""Reconciler — состояние execution после потери связи (M21).

Определяет судьбу уже отправленной задачи при disconnect/timeout.
НЕ запускает execution. НЕ обходит WorkflowEngine.
Только читает Gateway + History + probe_fn для определения состояния.

MD-01: UNKNOWN execution state НЕ превращается автоматически в retry/failover.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Optional

from app.resource.models import ReconcileState, RecoveryAction

if TYPE_CHECKING:
    from app.resource.gateway import ClusterGateway
    from app.engine.history import ExecutionHistory


@dataclass
class ReconcileResult:
    """Результат reconciliation."""
    state: ReconcileState
    action: RecoveryAction
    rationale: str
    target_backend_id: str | None = None


class Reconciler:
    """Определяет состояние execution после потери связи.

    ВЛАДЕЛЕЦ state transitions: ТОЛЬКО чтение Gateway + History.
    НЕ запускает execution. НЕ обходит WorkflowEngine.
    """

    def __init__(
        self,
        gateway: "ClusterGateway",
        history: "ExecutionHistory",
    ) -> None:
        self.gateway = gateway
        self.history = history

    def reconcile(
        self,
        prompt_id: str,
        probe_fn: Callable[[str], ReconcileState] | None = None,
    ) -> ReconcileResult:
        """Определить состояние и решение для prompt_id.

        M21 State Machine:
            connection_lost
                ↓
            RECONCILE (probe_fn или Gateway)
                ↓
            ┌─────────────────────────────────────────────────┐
            │ UNKNOWN  → STOP (MD-01: мораторий на auto)      │
            │ COMPLETED → RESULT_RETURNED (не дублировать)   │
            │ RUNNING   → OBSERVE (ждать завершения)         │
            │ FAILED    → RECORD (+ retry?)                  │
            │ NOT_ACCEPTED → REROUTED (safe retry)           │
            └─────────────────────────────────────────────────┘
        """
        # 1. Проверяем dispatch record
        dispatch = self.history.get_dispatch(prompt_id)
        if dispatch is None:
            return ReconcileResult(
                state=ReconcileState.UNKNOWN,
                action=RecoveryAction.NONE,
                rationale="No dispatch record found (MD-01: cannot determine)",
            )

        backend_id = dispatch["backend_id"]

        # 2. Определяем состояние через probe_fn или Gateway
        state = self._determine_state(prompt_id, probe_fn)

        # 3. Принимаем решение по state machine
        return self._decide(state, backend_id, dispatch)

    def _determine_state(
        self,
        prompt_id: str,
        probe_fn: Callable[[str], ReconcileState] | None,
    ) -> ReconcileState:
        """Определить состояние через probe_fn или Gateway.reconcile().

        M21: если probe_fn задан — обновляем Gateway dispatch record,
        чтобы can_auto_retry и другие методы Gateway видели актуальное состояние.
        """
        if probe_fn is not None:
            state = probe_fn(prompt_id)
            # Обновляем Gateway dispatch record для консистентности
            gw_record = self.gateway.get_dispatch(prompt_id)
            if gw_record is not None:
                gw_record.execution_state = state
            return state

        # Fallback: используем Gateway.reconcile()
        return self.gateway.reconcile(prompt_id)

    def _decide(
        self,
        state: ReconcileState,
        backend_id: str,
        dispatch: dict,
    ) -> ReconcileResult:
        """State machine: состояние → решение."""
        if state == ReconcileState.COMPLETED:
            return ReconcileResult(
                state=state,
                action=RecoveryAction.RESULT_RETURNED,
                rationale=f"Task {backend_id} COMPLETED — return existing result (no duplicate)",
            )

        if state == ReconcileState.RUNNING:
            return ReconcileResult(
                state=state,
                action=RecoveryAction.NONE,
                rationale=f"Task {backend_id} RUNNING — observe/wait",
            )

        if state == ReconcileState.FAILED:
            # Проверям retry policy через Gateway
            prompt_id = dispatch.get("prompt_id") or dispatch.get("job_prompt_id")
            if prompt_id and self.gateway.can_auto_retry(prompt_id):
                return ReconcileResult(
                    state=state,
                    action=RecoveryAction.REROUTED,
                    rationale=f"Task {backend_id} FAILED but safe retry allowed",
                    target_backend_id=self._find_alternative(backend_id),
                )
            return ReconcileResult(
                state=state,
                action=RecoveryAction.NONE,
                rationale=f"Task {backend_id} FAILED, no safe retry",
            )

        if state == ReconcileState.NOT_ACCEPTED:
            return ReconcileResult(
                state=state,
                action=RecoveryAction.REROUTED,
                rationale=f"Task {backend_id} NOT_ACCEPTED — safe retry on alternative backend",
                target_backend_id=self._find_alternative(backend_id),
            )

        # UNKNOWN — MD-01: STOP, NO AUTO-FAILover
        return ReconcileResult(
            state=ReconcileState.UNKNOWN,
            action=RecoveryAction.NONE,
            rationale=f"Task state UNKNOWN for {backend_id} — STOP per MD-01",
        )

    def _find_alternative(self, current_backend_id: str) -> str | None:
        """Найти альтернативный backend для reroute."""
        backends = self.gateway.list_backends()
        for b in backends:
            if b.backend_id != current_backend_id and b.is_selectable:
                return b.backend_id
        return None

    def can_auto_retry(self, prompt_id: str) -> bool:
        """Проверить, можно ли автоматический retry (MD-03)."""
        return self.gateway.can_auto_retry(prompt_id)
