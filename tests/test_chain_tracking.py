"""M25 Phase 1 — Chain Identity Tests.

Доказывает offline:
  - chain_id stamped on Job and ExecutionRecord
  - ExecutionHistory.get_by_chain groups records correctly
  - get_chain_summary aggregates correctly
  - backward compatibility: single-step jobs have chain_id=None
  - chain_id in ConversationContext messages
"""
from __future__ import annotations

import uuid

import pytest

from app.engine.chain import ChainContext, ChainState, ExecutionChain
from app.engine.history import ExecutionHistory, ExecutionRecord
from app.engine.job import Job, JobState
from app.planner.decomposer import SubTask


# ── Helpers ──

def _make_subtask(capability: str = "image.generate") -> SubTask:
    return SubTask(
        capability=capability,
        description="test",
        params={"prompt": "a cat"},
    )


def _make_execute_fn(results: list[str] | None = None):
    """Returns a callable that produces fake Jobs."""
    counter = [0]
    if results is None:
        results = ["SUCCESS"]

    def _fn(subtask: SubTask) -> Job:
        idx = counter[0]
        counter[0] += 1
        state = JobState.SUCCESS if results[min(idx, len(results) - 1)] == "SUCCESS" else JobState.FAILED
        return Job(
            prompt_id=str(uuid.uuid4())[:8],
            workflow_id="test_wf",
            version="1.0",
            capability=subtask.capability,
            state=state,
        )
    return _fn


# ── Tests: chain_id on Job ──

class TestChainIdOnJob:
    def test_chain_id_field_exists(self):
        job = Job(
            prompt_id="test",
            workflow_id="wf",
            version="1",
            capability="image.generate",
            state=JobState.SUCCESS,
        )
        assert hasattr(job, "chain_id")
        assert job.chain_id is None

    def test_chain_id_can_be_set(self):
        job = Job(
            prompt_id="test",
            workflow_id="wf",
            version="1",
            capability="image.generate",
            state=JobState.SUCCESS,
        )
        job.chain_id = "abc123"
        assert job.chain_id == "abc123"


# ── Tests: chain_id on ExecutionRecord ──

class TestChainIdOnExecutionRecord:
    def test_chain_id_field_exists(self):
        rec = ExecutionRecord(
            prompt_id="test",
            capability="image.generate",
            state="SUCCESS",
        )
        assert hasattr(rec, "chain_id")
        assert rec.chain_id is None

    def test_chain_id_from_job(self):
        job = Job(
            prompt_id="test",
            workflow_id="wf",
            version="1",
            capability="image.generate",
            state=JobState.SUCCESS,
        )
        job.chain_id = "chain-xyz"
        rec = ExecutionRecord.from_job(job)
        assert rec.chain_id == "chain-xyz"

    def test_chain_id_none_for_default_job(self):
        job = Job(
            prompt_id="test",
            workflow_id="wf",
            version="1",
            capability="image.generate",
            state=JobState.SUCCESS,
        )
        rec = ExecutionRecord.from_job(job)
        assert rec.chain_id is None


# ── Tests: ExecutionHistory.get_by_chain ──

class TestGetByChain:
    def test_grouping_by_chain_id(self):
        history = ExecutionHistory()
        rec1 = ExecutionRecord(prompt_id="r1", capability="image.generate", state="SUCCESS", chain_id="chain-A", chain_step_index=0)
        rec2 = ExecutionRecord(prompt_id="r2", capability="image.edit", state="SUCCESS", chain_id="chain-A", chain_step_index=1)
        rec3 = ExecutionRecord(prompt_id="r3", capability="image.generate", state="SUCCESS", chain_id="chain-B", chain_step_index=0)
        history.record(rec1)
        history.record(rec2)
        history.record(rec3)

        chain_a = history.get_by_chain("chain-A")
        assert len(chain_a) == 2
        assert all(r.chain_id == "chain-A" for r in chain_a)

    def test_ordering_by_step_index(self):
        history = ExecutionHistory()
        rec2 = ExecutionRecord(prompt_id="r2", capability="image.edit", state="SUCCESS", chain_id="c1", chain_step_index=1, timestamp=100.0)
        rec0 = ExecutionRecord(prompt_id="r0", capability="image.generate", state="SUCCESS", chain_id="c1", chain_step_index=0, timestamp=50.0)
        rec1 = ExecutionRecord(prompt_id="r1", capability="image.generate", state="SUCCESS", chain_id="c1", chain_step_index=0, timestamp=75.0)
        history.record(rec2)
        history.record(rec0)
        history.record(rec1)

        chain = history.get_by_chain("c1")
        assert len(chain) == 3
        assert chain[0].prompt_id == "r0"
        assert chain[1].prompt_id == "r1"
        assert chain[2].prompt_id == "r2"

    def test_empty_chain(self):
        history = ExecutionHistory()
        assert history.get_by_chain("nonexistent") == []

    def test_chain_id_none_not_grouped(self):
        history = ExecutionHistory()
        rec = ExecutionRecord(prompt_id="r1", capability="image.generate", state="SUCCESS", chain_id=None)
        history.record(rec)
        assert history.get_by_chain("any") == []


# ── Tests: ExecutionHistory.get_chain_summary ──

class TestGetChainSummary:
    def test_summary_basic(self):
        history = ExecutionHistory()
        history.record(ExecutionRecord(prompt_id="r1", capability="image.generate", state="SUCCESS", chain_id="c1", chain_step_index=0, workflow_id="wf", workflow_version="1.0", duration=1.5))
        history.record(ExecutionRecord(prompt_id="r2", capability="video.generate", state="SUCCESS", chain_id="c1", chain_step_index=1, workflow_id="wf2", workflow_version="2.0", duration=3.0))

        summary = history.get_chain_summary("c1")
        assert summary["chain_id"] == "c1"
        assert summary["total_steps"] == 2
        assert summary["completed_steps"] == 2
        assert summary["failed_steps"] == 0
        assert summary["total_duration"] == pytest.approx(4.5)
        assert "image.generate" in summary["capabilities"]
        assert "video.generate" in summary["capabilities"]

    def test_summary_with_failures(self):
        history = ExecutionHistory()
        history.record(ExecutionRecord(prompt_id="r1", capability="image.generate", state="SUCCESS", chain_id="c2", chain_step_index=0))
        history.record(ExecutionRecord(prompt_id="r2", capability="video.generate", state="FAILED", chain_id="c2", chain_step_index=1))

        summary = history.get_chain_summary("c2")
        assert summary["completed_steps"] == 1
        assert summary["failed_steps"] == 1

    def test_summary_empty_chain(self):
        history = ExecutionHistory()
        summary = history.get_chain_summary("empty")
        assert summary["total_steps"] == 0
        assert summary["chain_id"] == "empty"


# ── Tests: ExecutionChain chain_id stamping ──

class TestExecutionChainChainId:
    def test_chain_id_stamped_on_jobs(self):
        history = ExecutionHistory()
        chain = ExecutionChain(
            execute_fn=_make_execute_fn(["SUCCESS", "SUCCESS"]),
            history=history,
        )
        result = chain.execute([_make_subtask(), _make_subtask()])

        records = history.get_by_chain(result.steps[0].job.chain_id)
        assert len(records) == 2
        assert all(r.chain_id == records[0].chain_id for r in records)

    def test_chain_id_consistent_across_steps(self):
        history = ExecutionHistory()
        chain = ExecutionChain(
            execute_fn=_make_execute_fn(["SUCCESS", "SUCCESS", "SUCCESS"]),
            history=history,
        )
        result = chain.execute([_make_subtask(), _make_subtask(), _make_subtask()])

        chain_ids = [step.job.chain_id for step in result.steps if step.job]
        assert len(set(chain_ids)) == 1  # all same
        assert chain_ids[0] is not None

    def test_explicit_chain_id(self):
        history = ExecutionHistory()
        chain = ExecutionChain(
            execute_fn=_make_execute_fn(["SUCCESS"]),
            history=history,
        )
        result = chain.execute([_make_subtask()], chain_id="my-custom-id")

        assert result.steps[0].job.chain_id == "my-custom-id"
        records = history.get_by_chain("my-custom-id")
        assert len(records) == 1

    def test_different_chains_different_ids(self):
        h = ExecutionHistory()
        c1 = ExecutionChain(execute_fn=_make_execute_fn(["SUCCESS"]), history=h)
        c2 = ExecutionChain(execute_fn=_make_execute_fn(["SUCCESS"]), history=h)

        r1 = c1.execute([_make_subtask()])
        r2 = c2.execute([_make_subtask()])

        assert r1.steps[0].job.chain_id != r2.steps[0].job.chain_id


# ── Tests: ChainContext chain_id ──

class TestChainContextChainId:
    def test_chain_context_has_chain_id(self):
        ctx = ChainContext(session_id="s1", chain_id="c-abc")
        assert ctx.chain_id == "c-abc"

    def test_chain_context_chain_id_optional(self):
        ctx = ChainContext(session_id="s1")
        assert ctx.chain_id is None


# ── Tests: backward compatibility ──

class TestBackwardCompatibility:
    def test_single_step_job_chain_id_none(self):
        job = Job(
            prompt_id="test",
            workflow_id="wf",
            version="1",
            capability="image.generate",
            state=JobState.SUCCESS,
        )
        assert job.chain_id is None
        rec = ExecutionRecord.from_job(job)
        assert rec.chain_id is None

    def test_history_get_by_chain_handles_none(self):
        history = ExecutionHistory()
        history.record(ExecutionRecord(
            prompt_id="r1",
            capability="image.generate",
            state="SUCCESS",
            chain_id=None,
        ))
        assert history.get_by_chain("any") == []
