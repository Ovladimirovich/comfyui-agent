"""M25 — B1/B2 Integration Tests (production path).

Доказывает, что:
       B1: SemanticVerifier.verify_temporal_consistency() реально вызывается из
       production path (_execute_chain) на последовательности image-кадров,
       и что низкий temporal_score НЕ превращает успешное задание в FAILED
       (advisory signal only — post-hoc quality gate принадлежит downstream
       Video Editor, AD-44 SUPERSEDED / M26.3 REDEFINED).
  B2: SequenceExperience + build_sequence_experience() существуют, строятся
      из ChainExperience (computed view, единый JSONL — без второй persistence)
      и реально используются в production experience flow.

Offline: реальный ComfyUI НЕ нужен — шаг исполнения (_execute_chain_step)
заменяется fake, возвращающим SUCCESS-Job с реальными image-ассетами в store.
Оркестрация (_execute_chain → sequence verification → experience) идёт НАТИВНО.
"""
from __future__ import annotations

import os
import tempfile
from unittest.mock import patch

import pytest

from app.assets.store import AssetStore
from app.conversation import ConversationAgent
from app.engine import JobState
from app.engine.chain import ChainContext
from app.engine.experience import (
    ChainExperience,
    ChainStepExperience,
    ExperienceStore,
    SequenceExperience,
    build_chain_experience,
    build_sequence_experience,
)
from app.engine.history import ExecutionHistory
from app.engine.job import Job
from app.engine.semantic_verifier import (
    SemanticVerificationResult,
    TEMPORAL_CONSISTENCY_THRESHOLD,
)
from app.planner.decomposer import SubTask


_1PX_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0dIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0aIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\x0d\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class FakeSemanticVerifier:
    """Контролируемый SemanticVerifier: запоминает вызов verify_temporal_consistency."""

    def __init__(self, temporal_score: float = 0.9) -> None:
        self.temporal_score = temporal_score
        self.calls: list[tuple] = []

    def verify_temporal_consistency(self, sequence_assets, request="", capability="video.image_to_video"):
        self.calls.append((list(sequence_assets), request, capability))
        return SemanticVerificationResult(
            score=self.temporal_score,
            matches_intent=self.temporal_score >= 0.5,
            temporal_score=self.temporal_score,
            temporal_issues=[] if self.temporal_score >= 0.5 else ["poor continuity"],
        )


def _ingest_images(store: AssetStore, n: int, base: str) -> list[str]:
    ids = []
    for i in range(n):
        p = os.path.join(base, f"img{i}.png")
        with open(p, "wb") as f:
            f.write(_1PX_PNG)
        asset = store.ingest(p, type="image", role="output")
        ids.append(asset.id)
    return ids


def _make_step_executor(asset_ids: list[str]):
    state = {"calls": 0}

    def _exec(subtask=None, **_kw):
        idx = state["calls"]
        state["calls"] += 1
        aid = asset_ids[idx % len(asset_ids)]
        return Job(
            prompt_id=f"p{idx}",
            workflow_id="txt2img",
            version="1.0.0",
            capability=(subtask.capability if subtask else "image.generate"),
            state=JobState.SUCCESS,
            output_assets=[aid],
        )

    return _exec


def _build_agent_with_chain(tmp_path, image_ids, temporal_score, n_steps=2):
    store = AssetStore(root=tmp_path)
    agent = ConversationAgent(store)
    agent.semantic_verifier = FakeSemanticVerifier(temporal_score=temporal_score)
    exp_dir = os.path.join(tmp_path, "exp")
    agent.experience_store = ExperienceStore(exp_dir)

    subtasks = [SubTask(capability="image.generate", params={"prompt": f"step {i}"}) for i in range(n_steps)]
    executor = _make_step_executor(image_ids)

    with patch.object(agent, "_execute_chain_step", side_effect=executor):
        returned_job = agent._execute_chain("s1", subtasks)

    return agent, store, returned_job


# ───────────────────────── B1: production temporal verification ─────────────────────────


class TestB1TemporalVerificationProductionPath:
    def test_temporal_verification_called_on_image_sequence(self, tmp_path):
        image_ids = _ingest_images(AssetStore(root=tmp_path), 2, str(tmp_path))
        agent, store, returned = _build_agent_with_chain(tmp_path, image_ids, temporal_score=0.9)

        # Production path реально вызвал verify_temporal_consistency
        assert len(agent.semantic_verifier.calls) == 1
        called_assets, request, capability = agent.semantic_verifier.calls[0]
        assert called_assets == [store.get(i).path for i in image_ids]
        # Последовательность из >=2 image → verification прошла, шаг SUCCESS
        assert returned.state == JobState.SUCCESS

    def test_temporal_verification_low_score_is_advisory_only(self, tmp_path):
        image_ids = _ingest_images(AssetStore(root=tmp_path), 3, str(tmp_path))
        agent, store, returned = _build_agent_with_chain(tmp_path, image_ids, temporal_score=0.2)

        assert len(agent.semantic_verifier.calls) == 1
        # M25.3: низкий temporal_score — advisory signal, НЕ failure gate.
        # Успешно выполненное задание НЕ превращается в FAILED (AD-44 SUPERSEDED).
        assert returned.state == JobState.SUCCESS
        # Advisory signal записан в experience (animation_quality="poor" при <0.5).
        exp = agent.experience_store.get_by_chain(returned.chain_id)
        assert exp is not None
        assert exp.temporal_consistency == 0.2
        assert exp.animation_quality == "poor"

    def test_no_temporal_verification_for_single_image(self, tmp_path):
        image_ids = _ingest_images(AssetStore(root=tmp_path), 1, str(tmp_path))
        agent, store, returned = _build_agent_with_chain(tmp_path, image_ids, temporal_score=0.9, n_steps=1)

        # <2 image кадров → temporal verification НЕ вызывается (безопасно для non-temporal)
        assert agent.semantic_verifier.calls == []
        assert returned.state == JobState.SUCCESS

    def test_temporal_threshold_boundary(self, tmp_path):
        # Ровно на пороге (0.5) — НЕ failure (строго < порога)
        image_ids = _ingest_images(AssetStore(root=tmp_path), 2, str(tmp_path))
        agent, store, returned = _build_agent_with_chain(tmp_path, image_ids, temporal_score=TEMPORAL_CONSISTENCY_THRESHOLD)
        assert returned.state == JobState.SUCCESS
        # на пороге (0.5) verification ВЫЗЫВАЕТСЯ, но failure path НЕ срабатывает
        assert len(agent.semantic_verifier.calls) == 1


# ───────────────────────── B2: SequenceExperience ─────────────────────────


class TestB2SequenceExperienceConstruction:
    def test_construction_and_roundtrip(self):
        se = SequenceExperience(
            sequence_id="c1",
            image_assets=["a", "b", "c"],
            video_asset="v",
            image_params=[{"prompt": "1"}],
            video_params={"steps": 16},
            temporal_consistency=0.8,
            image_to_video_transition="success",
        )
        assert se.sequence_id == "c1"
        assert se.image_assets == ["a", "b", "c"]
        assert se.temporal_consistency == 0.8

        d = se.to_dict()
        restored = SequenceExperience.from_dict(d)
        assert restored.image_assets == ["a", "b", "c"]
        assert restored.video_asset == "v"
        assert restored.temporal_consistency == 0.8

    def test_defaults(self):
        se = SequenceExperience(sequence_id="x")
        assert se.image_assets == []
        assert se.temporal_consistency is None
        assert se.image_to_video_transition is None


class TestB2BuildSequenceExperience:
    def _chain_exp(self, capabilities, temporal=None):
        steps = [
            ChainStepExperience(
                step_index=i,
                capability=capabilities[i],
                output_assets=[f"asset{i}"],
                params={"prompt": f"s{i}"},
                state="SUCCESS",
            )
            for i in range(len(capabilities))
        ]
        return ChainExperience(
            chain_id="c-seq",
            session_id="s1",
            steps=steps,
            sequence_assets=["asset0", "asset1"],
            temporal_consistency=temporal,
        )

    def test_valid_sequence_success(self):
        exp = self._chain_exp(["image.generate", "image.edit", "video.image_to_video"], temporal=0.8)
        se = build_sequence_experience(exp)
        assert se.sequence_id == "c-seq"
        assert se.image_assets == ["asset0", "asset1"]
        assert se.video_asset == "asset2"
        assert se.image_to_video_transition == "success"

    def test_poor_transition(self):
        exp = self._chain_exp(["image.generate", "video.image_to_video"], temporal=0.3)
        se = build_sequence_experience(exp)
        assert se.image_to_video_transition == "poor"
        assert se.video_asset == "asset1"

    def test_none_temporal_no_transition(self):
        exp = self._chain_exp(["image.generate", "video.image_to_video"], temporal=None)
        se = build_sequence_experience(exp)
        assert se.temporal_consistency is None
        assert se.image_to_video_transition is None

    def test_fallback_from_temporal_result(self):
        exp = self._chain_exp(["image.generate", "video.image_to_video"], temporal=None)
        result = SemanticVerificationResult(score=0.9, matches_intent=True, temporal_score=0.9)
        se = build_sequence_experience(exp, result)
        assert se.temporal_consistency == 0.9
        assert se.image_to_video_transition == "success"


class TestB2SequenceExperienceInProduction:
    def test_sequence_experience_recorded_in_chain_experience(self, tmp_path):
        image_ids = _ingest_images(AssetStore(root=tmp_path), 2, str(tmp_path))
        agent, store, returned = _build_agent_with_chain(tmp_path, image_ids, temporal_score=0.85)

        # experience_store реально записан через production path
        exp_store = agent.experience_store
        loaded = exp_store.get_by_chain(_chain_id_for(returned))
        assert loaded is not None
        # SequenceExperience встроен как computed view внутри ChainExperience
        # (единый JSONL, без второй persistence-модели)
        assert loaded.sequence_experience is not None
        assert loaded.sequence_experience["sequence_id"] == loaded.chain_id
        assert loaded.sequence_experience["temporal_consistency"] == 0.85
        assert loaded.sequence_experience["image_to_video_transition"] == "success"
        assert loaded.temporal_consistency == 0.85
        assert loaded.animation_quality == "success"

    def test_sequence_experience_poor_in_production(self, tmp_path):
        image_ids = _ingest_images(AssetStore(root=tmp_path), 2, str(tmp_path))
        agent, store, returned = _build_agent_with_chain(tmp_path, image_ids, temporal_score=0.2)
        loaded = agent.experience_store.get_by_chain(_chain_id_for(returned))
        assert loaded is not None
        assert loaded.sequence_experience["temporal_consistency"] == 0.2
        assert loaded.sequence_experience["image_to_video_transition"] == "poor"
        assert loaded.animation_quality == "poor"


def _chain_id_for(returned: Job) -> str:
    """chain_id проставляется ExecutionChain на Job последнего шага."""
    assert returned.chain_id is not None
    return returned.chain_id
