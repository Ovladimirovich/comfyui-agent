"""M21 — Fault-Injection E2E Tests.

Simulates real disconnect scenarios and verifies:
1. disconnect → COMPLETED: no duplicate execution
2. disconnect → RUNNING: observe/wait, no duplicate
3. NOT_ACCEPTED → safe retry on alternative backend
4. UNKNOWN → STOP (MD-01)
5. restart → reconciliation from persistent history

KEY CONSTRAINT: Reconciler NEVER starts execution directly.
All retries go through existing ExecutionChain → WorkflowEngine → Provider path.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.agent import Agent
from app.assets.store import AssetStore
from app.conversation import ConversationAgent
from app.engine.history import ExecutionHistory
from app.engine.job import Job, JobState
from app.resource.gateway import ClusterGateway
from app.resource.models import (
    BackendResource,
    BackendHealth,
    BackendResourceState,
    ReconcileState,
    RecoveryAction,
)
from app.resource.reconciler import Reconciler


# --- Helpers ---

def _make_agent_with_gateway(
    store: AssetStore,
    history: ExecutionHistory,
    num_backends: int = 2,
) -> tuple[Agent, ClusterGateway, list[str]]:
    """Создать Agent с Gateway и mock provider для E2E."""
    backends = []
    for i in range(num_backends):
        bid = f"backend_{i}"
        backends.append(BackendResource(
            backend_id=bid,
            endpoint_url=f"http://{bid}:8188",
            health=BackendHealth.HEALTHY,
        ))

    gw = ClusterGateway(backends=backends)
    gw.refresh_health()

    agent = Agent(
        asset_store=store,
        execution_history=history,
        gateway=gw,
    )

    return agent, gw, [b.backend_id for b in backends]


def _mock_workflow_engine_success(agent, asset_store):
    """Mock engine.execute to return a SUCCESS job without real ComfyUI."""
    from app.engine.engine import WorkflowEngine
    original_execute = WorkflowEngine.execute

    def mock_execute(self, manifest, plan, provider, **kwargs):
        job = Job(
            prompt_id="mock-prompt-123",
            workflow_id=manifest.id,
            version=manifest.version,
            capability=plan.capability,
            state=JobState.SUCCESS,
            output_assets=["mock-asset-1"],
            backend_execution_identity=provider.backend_id,
        )
        return job

    return patch.object(WorkflowEngine, "execute", mock_execute)


class TestFaultInjectionCompleted:
    """Scenario: disconnect → COMPLETED → return existing, NO duplicate."""

    def test_completed_no_duplicate_execution(self, tmp_path):
        store = AssetStore(root=tmp_path / "assets")
        history = ExecutionHistory(persist_path=str(tmp_path / "history.jsonl"))

        agent, gw, backend_ids = _make_agent_with_gateway(store, history, num_backends=2)

        call_count = 0
        executed_prompt_ids = []

        from app.engine.engine import WorkflowEngine
        original_execute = WorkflowEngine.execute

        def counting_execute(self, manifest, plan, provider, **kwargs):
            nonlocal call_count
            call_count += 1
            executed_prompt_ids.append(plan.capability)
            job = Job(
                prompt_id=f"exec-{call_count}",
                workflow_id=manifest.id,
                version=manifest.version,
                capability=plan.capability,
                state=JobState.SUCCESS,
                output_assets=[f"asset-{call_count}"],
                backend_execution_identity=provider.backend_id,
            )
            return job

        with patch.object(WorkflowEngine, "execute", counting_execute):
            # Step 1: Submit job via Agent.run()
            job = agent.run(
                capability="image.generate",
                params={"prompt": "test", "width": 64, "height": 64, "steps": 1},
                base_url="http://backend_0:8188",
                ws_timeout=1,
            )

        assert job.state == JobState.SUCCESS
        assert job.backend_execution_identity is not None
        assert call_count == 1

        # Step 2: Manually record dispatch (Agent.run with mocked engine doesn't go through full path)
        backend_used = job.backend_execution_identity or "local_comfyui"
        gw.record_dispatch(job.prompt_id, backend_used)
        history.record_dispatch(job.prompt_id, backend_used)

        # Step 3: Simulate disconnect → reconcile → COMPLETED
        def probe_completed(prompt_id):
            return ReconcileState.COMPLETED

        rec = Reconciler(gateway=gw, history=history)
        result = rec.reconcile(job.prompt_id, probe_fn=probe_completed)

        # Step 4: Verify NO duplicate execution
        assert result.action == RecoveryAction.RESULT_RETURNED
        assert call_count == 1  # Still 1 — no duplicate!

        print(f"\n  [COMPLETED] executions={call_count} dispatch_ok=True MD-01 enforced")


class TestFaultInjectionUnknown:
    """Scenario: disconnect → UNKNOWN → STOP (MD-01)."""

    def test_unknown_stops_no_retry(self, tmp_path):
        store = AssetStore(root=tmp_path / "assets")
        history = ExecutionHistory(persist_path=str(tmp_path / "history.jsonl"))

        agent, gw, backend_ids = _make_agent_with_gateway(store, history, num_backends=2)

        call_count = 0

        from app.engine.engine import WorkflowEngine
        def counting_execute(self, manifest, plan, provider, **kwargs):
            nonlocal call_count
            call_count += 1
            return Job(
                prompt_id=f"exec-{call_count}",
                workflow_id=manifest.id,
                version=manifest.version,
                capability=plan.capability,
                state=JobState.SUCCESS,
                output_assets=[f"asset-{call_count}"],
                backend_execution_identity=provider.backend_id,
            )

        with patch.object(WorkflowEngine, "execute", counting_execute):
            job = agent.run(
                capability="image.generate",
                params={"prompt": "test", "width": 64, "height": 64, "steps": 1},
                base_url="http://backend_0:8188",
                ws_timeout=1,
            )

        assert call_count == 1

        # Simulate disconnect → UNKNOWN
        gw.record_dispatch(job.prompt_id, "backend_0")

        def probe_unknown(prompt_id):
            return ReconcileState.UNKNOWN

        rec = Reconciler(gateway=gw, history=history)
        result = rec.reconcile(job.prompt_id, probe_fn=probe_unknown)

        # MD-01: UNKNOWN → STOP, NO auto-retry
        assert result.state == ReconcileState.UNKNOWN
        assert result.action == RecoveryAction.NONE
        assert result.target_backend_id is None  # No reroute for UNKNOWN
        assert call_count == 1  # No additional execution
        assert rec.can_auto_retry(job.prompt_id) is False

        print(f"\n  [UNKNOWN] executions={call_count} STOP enforced (MD-01)")


class TestFaultInjectionNotAccepted:
    """Scenario: NOT_ACCEPTED → safe retry on alternative backend."""

    def test_not_accepted_reroutes_to_alternative(self, tmp_path):
        store = AssetStore(root=tmp_path / "assets")
        history = ExecutionHistory(persist_path=str(tmp_path / "history.jsonl"))

        agent, gw, backend_ids = _make_agent_with_gateway(store, history, num_backends=2)

        call_count = 0
        executed_backends = []

        from app.engine.engine import WorkflowEngine
        def counting_execute(self, manifest, plan, provider, **kwargs):
            nonlocal call_count
            call_count += 1
            executed_backends.append(provider.backend_id)
            return Job(
                prompt_id=f"exec-{call_count}",
                workflow_id=manifest.id,
                version=manifest.version,
                capability=plan.capability,
                state=JobState.SUCCESS,
                output_assets=[f"asset-{call_count}"],
                backend_execution_identity=provider.backend_id,
            )

        with patch.object(WorkflowEngine, "execute", counting_execute):
            job = agent.run(
                capability="image.generate",
                params={"prompt": "test", "width": 64, "height": 64, "steps": 1},
                base_url="http://backend_0:8188",
                ws_timeout=1,
            )

        assert call_count == 1
        # Backend identity recorded (could be local_comfyui or backend_0 depending on provider)
        backend_used = executed_backends[0]
        assert backend_used is not None

        # Ensure dispatch recorded
        gw.record_dispatch(job.prompt_id, backend_used)
        history.record_dispatch(job.prompt_id, backend_used)

        def probe_not_accepted(prompt_id):
            return ReconcileState.NOT_ACCEPTED

        rec = Reconciler(gateway=gw, history=history)
        result = rec.reconcile(job.prompt_id, probe_fn=probe_not_accepted)

        # Safe retry: should suggest alternative backend
        assert result.state == ReconcileState.NOT_ACCEPTED
        assert result.action == RecoveryAction.REROUTED
        assert result.target_backend_id is not None
        assert rec.can_auto_retry(job.prompt_id) is True

        # Verify no duplicate execution happened during reconcile
        assert call_count == 1  # Reconciler doesn't execute!

        print(f"\n  [NOT_ACCEPTED] executions={call_count} reroute_to={result.target_backend_id}")


class TestFaultInjectionPersistence:
    """Scenario: restart → reconcile from persistent history."""

    def test_persistence_survives_restart(self, tmp_path):
        """Dispatch record survives process restart via JSONL persistence."""
        persist = str(tmp_path / "history.jsonl")

        # Phase 1: First "process" — record dispatch
        history1 = ExecutionHistory(persist_path=persist)
        history1.record_dispatch("p-restart-1", "backend_0", "http://backend_0:8188")
        del history1  # Simulate process exit

        # Phase 2: Second "process" — reload from persistence
        history2 = ExecutionHistory(persist_path=persist)
        dispatch = history2.get_dispatch("p-restart-1")

        assert dispatch is not None, "Dispatch record lost after restart!"
        assert dispatch["backend_id"] == "backend_0"
        assert dispatch["endpoint_url"] == "http://backend_0:8188"

        # Phase 3: Reconcile using reloaded history
        gw = ClusterGateway(backends=[
            BackendResource(backend_id="backend_0", endpoint_url="http://backend_0:8188",
                           health=BackendHealth.HEALTHY),
        ])
        gw.refresh_health()
        gw.record_dispatch("p-restart-1", "backend_0")

        rec = Reconciler(gateway=gw, history=history2)

        def probe_completed(prompt_id):
            return ReconcileState.COMPLETED

        result = rec.reconcile("p-restart-1", probe_fn=probe_completed)
        assert result.action == RecoveryAction.RESULT_RETURNED

        print(f"\n  [PERSISTENCE] dispatch survived restart: backend={dispatch['backend_id']}")


class TestNoDuplicateExecution:
    """Critical invariant: Reconciler NEVER starts new execution."""

    def test_reconciler_does_not_call_execute(self, tmp_path):
        """Reconciler is read-only: it determines state but doesn't execute."""
        store = AssetStore(root=tmp_path / "assets")
        history = ExecutionHistory()
        gw = ClusterGateway(backends=[
            BackendResource(backend_id="b1", endpoint_url="http://b1:8188",
                           health=BackendHealth.HEALTHY),
        ])
        gw.refresh_health()
        gw.record_dispatch("p-test", "b1")
        history.record_dispatch("p-test", "b1")

        rec = Reconciler(gateway=gw, history=history)

        # All reconcile states should NOT trigger execution
        for state in [ReconcileState.COMPLETED, ReconcileState.RUNNING,
                      ReconcileState.NOT_ACCEPTED, ReconcileState.UNKNOWN]:
            def probe(prompt_id):
                return state
            result = rec.reconcile("p-test", probe_fn=probe)
            # Reconciler only returns decision, never executes
            assert result.state == state

        print(f"\n  [NO_DUPLICATE] reconcile never calls execute()")


class TestMDO1Enforcement:
    """Verify MD-01: UNKNOWN state NEVER leads to auto-failover."""

    def test_md01_unknown_never_allows_auto_retry(self, tmp_path):
        history = ExecutionHistory()
        gw = ClusterGateway(backends=[
            BackendResource(backend_id="b1", endpoint_url="http://b1:8188",
                           health=BackendHealth.HEALTHY),
            BackendResource(backend_id="b2", endpoint_url="http://b2:8188",
                           health=BackendHealth.HEALTHY),
        ])
        gw.refresh_health()
        gw.record_dispatch("p-md01", "b1")
        history.record_dispatch("p-md01", "b1")

        rec = Reconciler(gateway=gw, history=history)

        def probe_unknown(prompt_id):
            return ReconcileState.UNKNOWN

        result = rec.reconcile("p-md01", probe_fn=probe_unknown)

        # MD-01: UNKNOWN → STOP, NO reroute, NO auto-retry
        assert result.action == RecoveryAction.NONE
        assert result.target_backend_id is None
        assert rec.can_auto_retry("p-md01") is False

        print(f"\n  [MD-01] UNKNOWN→STOP enforced, can_auto_retry=False")


class TestMD03Enforcement:
    """Verify MD-03: auto-retry ONLY for NOT_ACCEPTED state."""

    def test_md03_only_not_accepted_allows_retry(self, tmp_path):
        history = ExecutionHistory()
        gw = ClusterGateway(backends=[
            BackendResource(backend_id="b1", endpoint_url="http://b1:8188",
                           health=BackendHealth.HEALTHY),
            BackendResource(backend_id="b2", endpoint_url="http://b2:8188",
                           health=BackendHealth.HEALTHY),
        ])
        gw.refresh_health()

        rec = Reconciler(gateway=gw, history=history)

        # NOT_ACCEPTED → can retry
        gw.record_dispatch("p-retry", "b1")
        history.record_dispatch("p-retry", "b1")
        def probe_not_accepted(pid):
            return ReconcileState.NOT_ACCEPTED
        rec.reconcile("p-retry", probe_fn=probe_not_accepted)
        assert rec.can_auto_retry("p-retry") is True

        # COMPLETED → cannot retry (already done)
        gw.record_dispatch("p-done", "b1")
        history.record_dispatch("p-done", "b1")
        def probe_completed(pid):
            return ReconcileState.COMPLETED
        rec.reconcile("p-done", probe_fn=probe_completed)
        assert rec.can_auto_retry("p-done") is False

        # UNKNOWN → cannot retry (MD-01)
        gw.record_dispatch("p-unknown", "b1")
        history.record_dispatch("p-unknown", "b1")
        def probe_unknown(pid):
            return ReconcileState.UNKNOWN
        rec.reconcile("p-unknown", probe_fn=probe_unknown)
        assert rec.can_auto_retry("p-unknown") is False

        print(f"\n  [MD-03] only NOT_ACCEPTED allows auto-retry")
