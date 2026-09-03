"""Tests for Cluster Gateway (AD-42) — Execution Resource Layer.

Covered invariants:
- MD-01: Failover НЕ автоматический при UNKNOWN execution state.
- MD-02: UNKNOWN health ≠ HEALTHY (не выбирать для routing).
- MD-03: Авто-retry на другой backend только если state достоверно "не выполнялся".
- MD-04: Gateway не имеет прямого доступа к ComfyUI HTTP.
- MD-05: Gateway не строит node-graph / не генерирует workflow.
"""

from __future__ import annotations

import pytest

from app.resource import (
    BackendHealth,
    BackendResource,
    BackendResourceState,
    ClusterGateway,
    ReconcileState,
    RoutingDecision,
)


@pytest.fixture
def health_probe_healthy():
    def _probe(resource: BackendResource) -> BackendHealth:
        return BackendHealth.HEALTHY
    return _probe


@pytest.fixture
def health_probe_unknown():
    def _probe(resource: BackendResource) -> BackendHealth:
        return BackendHealth.UNKNOWN
    return _probe


@pytest.fixture
def queue_zero():
    def _queue(resource: BackendResource) -> int:
        return 0
    return _queue


class TestBackendResourceState:
    def test_unknown_health_means_unknown_state(self):
        # MD-02
        r = BackendResource(
            backend_id="b1",
            endpoint_url="http://x",
            health=BackendHealth.UNKNOWN,
        )
        assert ClusterGateway._compute_resource_state(r) == BackendResourceState.UNKNOWN
        assert r.is_selectable is False

    def test_healthy_zero_queue_means_available(self):
        r = BackendResource(
            backend_id="b1",
            endpoint_url="http://x",
            health=BackendHealth.HEALTHY,
            queue_depth=0,
        )
        state = ClusterGateway._compute_resource_state(r)
        assert state == BackendResourceState.AVAILABLE
        # is_selectable опирается на state (который ставится при refresh_health)
        r.state = state
        assert r.is_selectable is True

    def test_unhealthy_means_unavailable(self):
        r = BackendResource(
            backend_id="b1",
            endpoint_url="http://x",
            health=BackendHealth.UNHEALTHY,
        )
        assert ClusterGateway._compute_resource_state(r) == BackendResourceState.UNAVAILABLE
        assert r.is_selectable is False

    def test_degraded_means_busy(self):
        r = BackendResource(
            backend_id="b1",
            endpoint_url="http://x",
            health=BackendHealth.DEGRADED,
        )
        state = ClusterGateway._compute_resource_state(r)
        assert state == BackendResourceState.BUSY
        # BUSY — всё ещё selectable (но ниже по приоритету); ставим state
        r.state = state
        assert r.is_selectable is True  # busy is still selectable but lower priority


class TestRouting:
    def test_no_backends_returns_empty(self):
        gateway = ClusterGateway()
        decision = gateway.route("image.generate")
        assert decision.backend_id == ""

    def test_routes_to_only_healthy_backend(self, health_probe_healthy, queue_zero):
        b1 = BackendResource(backend_id="local", endpoint_url="http://localhost:8188")
        gateway = ClusterGateway(
            backends=[b1],
            health_check_fn=health_probe_healthy,
            queue_depth_fn=queue_zero,
        )
        decision = gateway.route("image.generate")
        assert decision.backend_id == "local"

    def test_unknown_health_backend_not_selected(self, health_probe_unknown, queue_zero):
        # MD-02: UNKNOWN health не выбирается
        b1 = BackendResource(backend_id="unknown-backend", endpoint_url="http://x")
        gateway = ClusterGateway(
            backends=[b1],
            health_check_fn=health_probe_unknown,
            queue_depth_fn=queue_zero,
        )
        decision = gateway.route("image.generate")
        assert decision.backend_id == ""

    def test_routes_by_capability(self, health_probe_healthy, queue_zero):
        b_image = BackendResource(
            backend_id="gpu-image", endpoint_url="http://img",
            capabilities={"image.generate", "image.upscale"},
        )
        b_video = BackendResource(
            backend_id="gpu-video", endpoint_url="http://vid",
            capabilities={"video.generate"},
        )
        gateway = ClusterGateway(
            backends=[b_image, b_video],
            health_check_fn=health_probe_healthy,
            queue_depth_fn=queue_zero,
        )
        decision = gateway.route("video.generate")
        assert decision.backend_id == "gpu-video"

    def test_routing_prefers_low_queue(self, health_probe_healthy):
        def _queue(resource):
            return {"busy": 10, "free": 0}[resource.backend_id]

        b_busy = BackendResource(backend_id="busy", endpoint_url="http://busy")
        b_free = BackendResource(backend_id="free", endpoint_url="http://free")
        gateway = ClusterGateway(
            backends=[b_busy, b_free],
            health_check_fn=health_probe_healthy,
            queue_depth_fn=_queue,
        )
        decision = gateway.route("image.generate")
        assert decision.backend_id == "free"


class TestDispatchAndReconcile:
    def test_record_dispatch(self):
        gateway = ClusterGateway()
        gateway.record_dispatch(prompt_id="p1", backend_id="b1")
        record = gateway.get_dispatch("p1")
        assert record is not None
        assert record.job_prompt_id == "p1"
        assert record.backend_id == "b1"

    def test_reconcile_without_probe_returns_unknown(self):
        """MD-01: без probe_fn не можем установить состояние → UNKNOWN"""
        gateway = ClusterGateway()
        gateway.record_dispatch(prompt_id="p1", backend_id="b1")
        state = gateway.reconcile("p1")
        assert state == ReconcileState.UNKNOWN

    def test_can_auto_retry_false_for_unknown(self):
        """MD-03: UNKNOWN → нельзя автоматически retry"""
        gateway = ClusterGateway()
        gateway.record_dispatch(prompt_id="p1", backend_id="b1")
        assert gateway.can_auto_retry("p1") is False

    def test_can_auto_retry_true_for_not_accepted(self):
        """MD-03: NOT_ACCEPTED → безопасный auto-retry"""
        gateway = ClusterGateway()
        gateway.record_dispatch(prompt_id="p1", backend_id="b1")

        def _probe(_prompt_id):
            return ReconcileState.NOT_ACCEPTED

        state = gateway.reconcile("p1", probe_fn=_probe)
        assert state == ReconcileState.NOT_ACCEPTED
        assert gateway.can_auto_retry("p1") is True

    def test_reconcile_completed_does_not_allow_duplicate(self):
        """MD-03/AD-42: COMPLETED → вернуть результат, не дублировать"""
        gateway = ClusterGateway()
        gateway.record_dispatch(prompt_id="p1", backend_id="b1")

        def _probe(_prompt_id):
            return ReconcileState.COMPLETED

        state = gateway.reconcile("p1", probe_fn=_probe)
        assert state == ReconcileState.COMPLETED
        assert gateway.can_auto_retry("p1") is False  # НЕ дублировать


class TestGatewayConstraints:
    """МD-04/МD-05: Gateway не имеет доступа к ComfyUI, не строит graph."""

    def _gateway_sources(self):
        import pathlib

        root = pathlib.Path(__file__).parent.parent
        galaxy = root / "app/resource/gateway.py"
        models = root / "app/resource/models.py"
        return galaxy.read_text(encoding="utf-8") + models.read_text(encoding="utf-8")

    def test_gateway_module_does_not_import_comfy_client(self):
        # Проверяем только import-строки (docstring может упоминать имя как текст)
        import re

        combined = self._gateway_sources()
        # Ищем `from ... import ... comfy ...` или `import ...comfy...`
        import_lines = [ln for ln in combined.splitlines() if ln.strip().startswith(("import ", "from "))]
        joined = "\n".join(import_lines)
        assert "comfy" not in joined.lower()

    def test_gateway_module_does_not_import_workflow_engine(self):
        import re

        combined = self._gateway_sources()
        import_lines = [ln for ln in combined.splitlines() if ln.strip().startswith(("import ", "from "))]
        joined = "\n".join(import_lines)
        assert "workflowengine" not in joined.lower()
        assert "engine.engine" not in joined.lower()
        assert "comfy.client" not in joined.lower()
