"""M21 — Reconciliation & Recovery tests.

Tests for:
- ExecutionHistory.dispatch tracking
- Reconciler state machine
- Gateway integration with dispatch
- MD-01 enforcement (UNKNOWN → STOP)
- MD-03 enforcement (NOT_ACCEPTED → safe retry)
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from app.engine.history import ExecutionHistory, ExecutionRecord
from app.resource.gateway import ClusterGateway
from app.resource.models import (
    BackendResource,
    BackendHealth,
    BackendResourceState,
    ReconcileState,
    RecoveryAction,
)
from app.resource.reconciler import Reconciler, ReconcileResult


# --- ExecutionHistory dispatch tracking ---

class TestExecutionHistoryDispatch:
    """Test dispatch tracking in ExecutionHistory."""

    def test_record_and_get_dispatch(self):
        history = ExecutionHistory()
        history.record_dispatch("p1", "b1", "http://b1:8188")
        dispatch = history.get_dispatch("p1")
        assert dispatch is not None
        assert dispatch["backend_id"] == "b1"
        assert dispatch["endpoint_url"] == "http://b1:8188"

    def test_get_dispatch_missing(self):
        history = ExecutionHistory()
        assert history.get_dispatch("missing") is None

    def test_get_dispatches_by_backend(self):
        history = ExecutionHistory()
        history.record_dispatch("p1", "b1")
        history.record_dispatch("p2", "b1")
        history.record_dispatch("p3", "b2")
        dispatches = history.get_dispatches_by_backend("b1")
        assert len(dispatches) == 2
        assert all(d["backend_id"] == "b1" for d in dispatches)

    def test_dispatch_persistence(self, tmp_path):
        persist = str(tmp_path / "history.jsonl")
        history = ExecutionHistory(persist_path=persist)
        history.record_dispatch("p1", "b1")
        del history

        history2 = ExecutionHistory(persist_path=persist)
        dispatch = history2.get_dispatch("p1")
        assert dispatch is not None
        assert dispatch["backend_id"] == "b1"


# --- Reconciler state machine ---

class TestReconcilerStateMachine:
    """Test Reconciler state machine transitions."""

    def _make_reconciler(self):
        gw = ClusterGateway(backends=[
            BackendResource(backend_id="b1", endpoint_url="http://b1:8188",
                           health=BackendHealth.HEALTHY),
            BackendResource(backend_id="b2", endpoint_url="http://b2:8188",
                           health=BackendHealth.HEALTHY),
        ])
        # Обновляем state backends
        gw.refresh_health()
        hist = ExecutionHistory()
        hist.record_dispatch("p1", "b1")
        gw.record_dispatch("p1", "b1")  # M21: Gateway тоже должен знать о dispatch
        return Reconciler(gateway=gw, history=hist)

    def test_completed_returns_result(self):
        rec = self._make_reconciler()

        def probe(prompt_id):
            return ReconcileState.COMPLETED

        result = rec.reconcile("p1", probe_fn=probe)
        assert result.state == ReconcileState.COMPLETED
        assert result.action == RecoveryAction.RESULT_RETURNED
        assert "no duplicate" in result.rationale.lower() or "return" in result.rationale.lower()

    def test_running_returns_observe(self):
        rec = self._make_reconciler()

        def probe(prompt_id):
            return ReconcileState.RUNNING

        result = rec.reconcile("p1", probe_fn=probe)
        assert result.state == ReconcileState.RUNNING
        assert result.action == RecoveryAction.NONE
        assert "observe" in result.rationale.lower() or "wait" in result.rationale.lower()

    def test_failed_no_retry_without_can_auto_retry(self):
        rec = self._make_reconciler()

        def probe(prompt_id):
            return ReconcileState.FAILED

        result = rec.reconcile("p1", probe_fn=probe)
        assert result.state == ReconcileState.FAILED
        assert result.action == RecoveryAction.NONE

    def test_not_accepted_allows_reroute(self):
        rec = self._make_reconciler()

        def probe(prompt_id):
            return ReconcileState.NOT_ACCEPTED

        result = rec.reconcile("p1", probe_fn=probe)
        assert result.state == ReconcileState.NOT_ACCEPTED
        assert result.action == RecoveryAction.REROUTED
        assert result.target_backend_id == "b2"  # Alternative backend

    def test_unknown_stops_md01(self):
        """MD-01: UNKNOWN state → STOP, NO auto-failover."""
        rec = self._make_reconciler()

        def probe(prompt_id):
            return ReconcileState.UNKNOWN

        result = rec.reconcile("p1", probe_fn=probe)
        assert result.state == ReconcileState.UNKNOWN
        assert result.action == RecoveryAction.NONE
        assert "STOP" in result.rationale.upper() or "md-01" in result.rationale.lower()

    def test_no_dispatch_record_returns_unknown(self):
        rec = self._make_reconciler()
        # No dispatch recorded for "missing"
        result = rec.reconcile("missing", probe_fn=lambda x: ReconcileState.UNKNOWN)
        assert result.state == ReconcileState.UNKNOWN
        assert result.action == RecoveryAction.NONE

    def test_can_auto_retry_false_for_unknown(self):
        rec = self._make_reconciler()
        # Probe sets UNKNOWN
        def probe(prompt_id):
            return ReconcileState.UNKNOWN
        rec.reconcile("p1", probe_fn=probe)
        # After reconcile with UNKNOWN, can_auto_retry should be False
        assert rec.can_auto_retry("p1") is False

    def test_can_auto_retry_true_for_not_accepted(self):
        rec = self._make_reconciler()
        def probe(prompt_id):
            return ReconcileState.NOT_ACCEPTED
        rec.reconcile("p1", probe_fn=probe)
        assert rec.can_auto_retry("p1") is True


# --- Gateway integration ---

class TestGatewayDispatchIntegration:
    """Test Gateway dispatch tracking integration."""

    def test_record_dispatch_updates_internal(self):
        gw = ClusterGateway()
        gw.record_dispatch("p1", "b1")
        dispatch = gw.get_dispatch("p1")
        assert dispatch is not None
        assert dispatch.job_prompt_id == "p1"
        assert dispatch.backend_id == "b1"

    def test_reconcile_without_probe_returns_unknown(self):
        gw = ClusterGateway()
        gw.record_dispatch("p1", "b1")
        # No probe_fn, no history → UNKNOWN
        state = gw.reconcile("p1")
        assert state == ReconcileState.UNKNOWN

    def test_can_auto_retry_false_when_no_record(self):
        gw = ClusterGateway()
        assert gw.can_auto_retry("missing") is False


# --- End-to-end reconciliation flow ---

class TestReconciliationFlow:
    """Test complete reconciliation flow."""

    def test_full_flow_completed_no_duplicate(self, tmp_path):
        """COMPLETED after disconnect → return existing, NO duplicate execution."""
        history = ExecutionHistory(persist_path=str(tmp_path / "h.jsonl"))
        history.record_dispatch("p1", "b1", "http://b1:8188")

        gw = ClusterGateway(backends=[
            BackendResource(backend_id="b1", endpoint_url="http://b1:8188",
                           health=BackendHealth.HEALTHY),
        ])
        rec = Reconciler(gateway=gw, history=history)

        def probe(prompt_id):
            return ReconcileState.COMPLETED

        result = rec.reconcile("p1", probe_fn=probe)
        assert result.action == RecoveryAction.RESULT_RETURNED
        # Verify no new dispatch was created
        assert len(history._dispatch_records) == 1

    def test_full_flow_unknown_stops(self, tmp_path):
        """UNKNOWN after disconnect → STOP, NO retry."""
        history = ExecutionHistory(persist_path=str(tmp_path / "h.jsonl"))
        history.record_dispatch("p1", "b1")

        gw = ClusterGateway(backends=[
            BackendResource(backend_id="b1", endpoint_url="http://b1:8188",
                           health=BackendHealth.HEALTHY),
            BackendResource(backend_id="b2", endpoint_url="http://b2:8188",
                           health=BackendHealth.HEALTHY),
        ])
        rec = Reconciler(gateway=gw, history=history)

        def probe(prompt_id):
            return ReconcileState.UNKNOWN

        result = rec.reconcile("p1", probe_fn=probe)
        assert result.action == RecoveryAction.NONE
        assert result.state == ReconcileState.UNKNOWN
        # Should NOT have target_backend (no reroute for UNKNOWN)
        assert result.target_backend_id is None

    def test_full_flow_not_accepted_reroutes(self, tmp_path):
        """NOT_ACCEPTED → safe retry on alternative backend."""
        history = ExecutionHistory(persist_path=str(tmp_path / "h.jsonl"))
        history.record_dispatch("p1", "b1")

        gw = ClusterGateway(backends=[
            BackendResource(backend_id="b1", endpoint_url="http://b1:8188",
                           health=BackendHealth.HEALTHY),
            BackendResource(backend_id="b2", endpoint_url="http://b2:8188",
                           health=BackendHealth.HEALTHY),
        ])
        gw.refresh_health()
        gw.record_dispatch("p1", "b1")
        rec = Reconciler(gateway=gw, history=history)

        def probe(prompt_id):
            return ReconcileState.NOT_ACCEPTED

        result = rec.reconcile("p1", probe_fn=probe)
        assert result.action == RecoveryAction.REROUTED
        assert result.target_backend_id == "b2"
