"""Data Model для Cluster Gateway (AD-42).

Слой Resource — решает "ГДЕ выполнить уже сформированный ExecutionPlan".
Не меняет ExecutionPlan, не выбирает capability, не создаёт workflow, не обходит WorkflowEngine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class BackendHealth(str, Enum):
    """Уровни здоровья backend (MD-02: UNKNOWN ≠ HEALTHY)."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


class BackendResourceState(str, Enum):
    """Текущее состояние backend как ресурса."""

    # Объединение health + load
    AVAILABLE = "AVAILABLE"      # HEALTHY и может принять задачу
    BUSY = "BUSY"                # HEALTHY/DEGRADED, но queue depth высокий
    UNAVAILABLE = "UNAVAILABLE"  # UNHEALTHY
    UNKNOWN = "UNKNOWN"          # не удалось определить (не выбирать для routing)


class ReconcileState(str, Enum):
    """Состояние выполнения после reconcile (failover-safe)."""

    UNKNOWN = "UNKNOWN"           # не удалось определить (НЕ для auto-failover, MD-01)
    COMPLETED = "COMPLETED"       # задача выполнена (вернуть результат, НЕ дублировать, MD-03)
    NOT_ACCEPTED = "NOT_ACCEPTED" # задача не была принята (безопасный retry)
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    FAILED = "FAILED"


class RecoveryAction(str, Enum):
    """Действие после reconcile (что сделал Gateway)."""

    NONE = "NONE"
    RESULT_RETURNED = "RESULT_RETURNED"  # state=COMPLETED -> вернуть результат
    REROUTED = "REROUTED"                # state=NOT_ACCEPTED -> безопасный reroute
    USER_ASKED = "USER_ASKED"            # state=UNKNOWN -> запросить пользователя (НЕ auto)


@dataclass
class BackendResource:
    """Ресурс — конкретный Execution Backend для Gateway.

    Расширяет существующий BackendSpec (registry/backends.py) информацией о
    health/load, которую Gateway собирает/кэширует.
    """

    backend_id: str                  # стабильный identity
    endpoint_url: str
    kind: str = "remote_comfyui"     # local_comfyui / remote_comfyui / cloud_comfyui
    priority: int = 0
    capabilities: set[str] = field(default_factory=set)  # пусто = все
    health: BackendHealth = BackendHealth.UNKNOWN
    queue_depth: int = 0
    state: BackendResourceState = BackendResourceState.UNKNOWN
    description: str = ""

    @property
    def is_selectable(self) -> bool:
        """Только HEALTHY/DEGRADED backend может быть выбран для NEW job (MD-02).
        
        UNKNOWN и UNHEALTHY исключаются.
        BUSY — всё ещё selectable (но ниже по приоритету при routing).
        """
        return self.state in (BackendResourceState.AVAILABLE, BackendResourceState.BUSY)


@dataclass
class RoutingDecision:
    """Решение Gateway о маршрутизации NEW job."""

    backend_id: str
    rationale: str
    timestamp: float = 0.0


@dataclass
class ExecutionDispatchRecord:
    """Запись о диспетчеризации задачи на конкретный backend.

    Записывается в ExecutionHistory (Gateway только дополняет его записями).
    """

    job_prompt_id: str
    backend_id: str
    endpoint_url: str
    submitted_at: float = 0.0
    execution_state: ReconcileState = ReconcileState.UNKNOWN
    recovery_action: RecoveryAction = RecoveryAction.NONE