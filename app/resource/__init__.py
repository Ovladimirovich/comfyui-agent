"""Execution Resource Layer (AD-42).

Cluster Gateway — выбор Execution Backend для уже сформированного ExecutionPlan.

Слои ответственности:
- Intelligence (что делать): Planner, Composer, CapabilityGraph, SemanticVerifier
- Execution (как выполнить): ExecutionChain, WorkflowEngine, Provider, Backend
- Resource (где выполнить): ClusterGateway — health, load, routing, reconcile
"""
from app.resource.gateway import ClusterGateway
from app.resource.models import (
    BackendHealth,
    BackendResource,
    BackendResourceState,
    RoutingDecision,
    ExecutionDispatchRecord,
    ReconcileState,
    RecoveryAction,
)

__all__ = [
    "ClusterGateway",
    "BackendHealth",
    "BackendResource",
    "BackendResourceState",
    "RoutingDecision",
    "ExecutionDispatchRecord",
    "ReconcileState",
    "RecoveryAction",
]
