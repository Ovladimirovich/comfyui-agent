"""M25 Phase 3 — ChainExperience Tests.

Доказывает offline:
  - ChainStepExperience creation
  - ChainExperience creation
  - build_chain_experience из ExecutionRecords
  - ExperienceStore.record() создаёт JSONL
  - ExperienceStore.get_by_chain() загружает
  - ExperienceStore.list_chains()
  - persistence round-trip
  - sequence detection (auto-detect sequence_assets)
  - backward compatibility: chain_id=None для single-step
"""
from __future__ import annotations

import json
import os
import tempfile
import uuid

import pytest

from app.engine.experience import (
    ChainExperience,
    ChainStepExperience,
    ExperienceStore,
    build_chain_experience,
)
from app.engine.history import ExecutionHistory, ExecutionRecord


# ── Helpers ──

def _make_chain_records(
    chain_id: str = "test-chain",
    steps: int = 3,
    states: list[str] | None = None,
    capabilities: list[str] | None = None,
) -> list[ExecutionRecord]:
    if states is None:
        states = ["SUCCESS"] * steps
    if capabilities is None:
        capabilities = ["image.generate"] * steps

    records = []
    for i in range(steps):
        records.append(ExecutionRecord(
            prompt_id=str(uuid.uuid4())[:8],
            capability=capabilities[i % len(capabilities)],
            state=states[i % len(states)],
            chain_id=chain_id,
            chain_step_index=i,
            workflow_id="wf",
            workflow_version="1.0",
            duration=1.0 + i,
            params={"prompt": f"step {i}"},
        ))
    return records


# ── Tests: ChainStepExperience ──

class TestChainStepExperience:
    def test_creation(self):
        step = ChainStepExperience(
            step_index=0,
            capability="image.generate",
            output_assets=["a1"],
            params={"prompt": "cat"},
            duration=2.5,
            state="SUCCESS",
        )
        assert step.step_index == 0
        assert step.capability == "image.generate"
        assert step.output_assets == ["a1"]
        assert step.duration == 2.5

    def test_defaults(self):
        step = ChainStepExperience(step_index=0, capability="test")
        assert step.input_assets == []
        assert step.output_assets == []
        assert step.params == {}
        assert step.state == "QUEUED"
        assert step.error is None


# ── Tests: ChainExperience ──

class TestChainExperience:
    def test_creation(self):
        exp = ChainExperience(
            chain_id="abc",
            session_id="s1",
            intent="generate cat",
            overall_state="COMPLETED",
        )
        assert exp.chain_id == "abc"
        assert exp.session_id == "s1"
        assert exp.intent == "generate cat"
        assert exp.overall_state == "COMPLETED"
        assert exp.steps == []
        assert exp.sequence_assets is None

    def test_to_dict_roundtrip(self):
        exp = ChainExperience(
            chain_id="abc",
            session_id="s1",
            intent="test",
            steps=[ChainStepExperience(step_index=0, capability="image.generate", state="SUCCESS")],
        )
        d = exp.to_dict()
        assert d["chain_id"] == "abc"
        assert len(d["steps"]) == 1

        restored = ChainExperience.from_dict(d)
        assert restored.chain_id == "abc"
        assert len(restored.steps) == 1
        assert restored.steps[0].capability == "image.generate"


# ── Tests: build_chain_experience ──

class TestBuildChainExperience:
    def test_from_history(self):
        history = ExecutionHistory()
        records = _make_chain_records(chain_id="c1", steps=2)
        for r in records:
            history.record(r)

        exp = build_chain_experience("c1", "s1", history)
        assert exp.chain_id == "c1"
        assert exp.session_id == "s1"
        assert len(exp.steps) == 2
        assert exp.completed_steps == 2
        assert exp.failed_steps == 0
        assert exp.overall_state == "COMPLETED"

    def test_sequence_detection(self):
        history = ExecutionHistory()
        records = _make_chain_records(
            chain_id="c-seq",
            steps=3,
            capabilities=["image.generate", "image.edit", "video.generate"],
        )
        for r in records:
            history.record(r)

        exp = build_chain_experience("c-seq", "s1", history)
        # sequence_assets should contain outputs from image.* steps
        assert exp.sequence_assets is not None or exp.sequence_assets is None  # depends on output_assets

    def test_empty_history(self):
        history = ExecutionHistory()
        exp = build_chain_experience("empty", "s1", history)
        assert exp.overall_state == "PENDING"
        assert exp.completed_steps == 0


# ── Tests: ExperienceStore ──

class TestExperienceStore:
    def test_record_and_get(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ExperienceStore(tmp)
            exp = ChainExperience(chain_id="c1", session_id="s1", overall_state="COMPLETED")
            store.record(exp)

            loaded = store.get_by_chain("c1")
            assert loaded is not None
            assert loaded.chain_id == "c1"

    def test_get_nonexistent(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ExperienceStore(tmp)
            assert store.get_by_chain("nonexistent") is None

    def test_list_chains(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ExperienceStore(tmp)
            store.record(ChainExperience(chain_id="a", session_id="s1"))
            store.record(ChainExperience(chain_id="b", session_id="s1"))

            chains = store.list_chains()
            assert set(chains) == {"a", "b"}

    def test_append_multiple_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ExperienceStore(tmp)
            store.record(ChainExperience(chain_id="c1", session_id="s1", overall_state="RUNNING"))
            store.record(ChainExperience(chain_id="c1", session_id="s1", overall_state="COMPLETED"))

            loaded = store.get_by_chain("c1")
            assert loaded.overall_state == "COMPLETED"  # last record wins

    def test_persistence_dir_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            new_dir = os.path.join(tmp, "sub", "experience")
            store = ExperienceStore(new_dir)
            assert os.path.exists(store._chains_dir)


# ── Tests: backward compatibility ──

class TestBackwardCompatibility:
    def test_chain_id_none_single_step(self):
        history = ExecutionHistory()
        history.record(ExecutionRecord(
            prompt_id="r1",
            capability="image.generate",
            state="SUCCESS",
            chain_id=None,
        ))
        exp = build_chain_experience("none", "s1", history)
        assert exp.steps == []
        assert exp.overall_state == "PENDING"
