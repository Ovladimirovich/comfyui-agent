"""M26.1 — Experience Analytics (AC1).

Read-only aggregation над ExperienceStore. Нет mutation исходных Experience objects,
нет новой persistence, нет нового subsystem.
"""
from __future__ import annotations

from app.engine.experience import (
    ChainExperience,
    ChainStepExperience,
    ExperienceAnalytics,
    ExperienceHint,
    ExperienceStore,
    TemporalStats,
)


def _make_chain(chain_id, temporal, video_params, capability="video.image_to_video"):
    steps = [
        ChainStepExperience(
            step_index=0, capability="image.generate", output_assets=["a1"],
            workflow_id="image_generate", workflow_version="1",
        ),
        ChainStepExperience(
            step_index=1, capability=capability, output_assets=["v1"],
            workflow_id="video_image_to_video", workflow_version="1",
        ),
    ]
    seq = {
        "video_params": video_params,
        "temporal_consistency": temporal,
        "image_to_video_transition": "success",
    }
    return ChainExperience(
        chain_id=chain_id, session_id="s1", steps=steps,
        overall_state="COMPLETED", completed_steps=2,
        temporal_consistency=temporal, sequence_experience=seq,
    )


def _store_with(chains, tmp_path):
    store = ExperienceStore(str(tmp_path / "experience"))
    for c in chains:
        store.record(c)
    return store


def test_load_all_returns_recorded_chains(tmp_path):
    store = _store_with([_make_chain("c1", 0.9, {"fps": 12}), _make_chain("c2", 0.6, {"fps": 8})], tmp_path)
    analytics = ExperienceAnalytics(store)
    all_exp = analytics.load_all()
    assert len(all_exp) == 2
    assert {e.chain_id for e in all_exp} == {"c1", "c2"}


def test_temporal_stats_aggregates_per_capability(tmp_path):
    store = _store_with([_make_chain("c1", 0.9, {"fps": 12}), _make_chain("c2", 0.6, {"fps": 8})], tmp_path)
    analytics = ExperienceAnalytics(store)
    stats = analytics.temporal_stats("video.image_to_video")
    assert isinstance(stats, TemporalStats)
    assert stats.sample_count == 2
    assert stats.avg_score == 0.75
    assert stats.available is True
    assert "video_image_to_video@1" in stats.per_workflow_avg


def test_temporal_stats_none_when_no_relevant_samples(tmp_path):
    # chain без temporal-опыта (image.generate только)
    chain = ChainExperience(
        chain_id="img1", session_id="s1",
        steps=[ChainStepExperience(step_index=0, capability="image.generate", output_assets=["a1"])],
    )
    store = _store_with([chain], tmp_path)
    analytics = ExperienceAnalytics(store)
    assert analytics.temporal_stats("video.image_to_video") is None
    # capability вообще отсутствует
    assert analytics.temporal_stats("audio.generate") is None


def test_preferred_params_picks_highest_temporal_no_magic_threshold(tmp_path):
    store = _store_with([_make_chain("c1", 0.9, {"fps": 12, "steps": 25}), _make_chain("c2", 0.6, {"fps": 8, "steps": 20})], tmp_path)
    analytics = ExperienceAnalytics(store)
    pref = analytics.preferred_params("video.image_to_video")
    # выбрана цепочка с наивысшим temporal (0.9) → её video_params
    assert pref == {"fps": 12, "steps": 25}


def test_preferred_params_insufficient_samples_returns_empty(tmp_path):
    # только 1 цепочка с temporal — ниже min_samples (2)
    store = _store_with([_make_chain("c1", 0.9, {"fps": 12})], tmp_path)
    analytics = ExperienceAnalytics(store)
    assert analytics.preferred_params("video.image_to_video") == {}


def test_preferred_params_for_capability_without_experience_is_empty(tmp_path):
    store = _store_with([_make_chain("c1", 0.9, {"fps": 12})], tmp_path)
    analytics = ExperienceAnalytics(store)
    # image.generate не имеет temporal-опыта в этой цепочке
    assert analytics.preferred_params("image.generate") == {}


def test_no_mutation_of_source_experience_objects(tmp_path):
    chain = _make_chain("c1", 0.9, {"fps": 12, "steps": 25})
    store = _store_with([chain], tmp_path)
    analytics = ExperienceAnalytics(store)
    # исходный объект не должен меняться при агрегации
    orig_temporal = chain.temporal_consistency
    orig_seq = dict(chain.sequence_experience)
    analytics.temporal_stats("video.image_to_video")
    analytics.preferred_params("video.image_to_video")
    assert chain.temporal_consistency == orig_temporal
    assert chain.sequence_experience == orig_seq
    # загруженные копии тоже не мутированы после preferred_params
    loaded = analytics.load_all()[0]
    assert loaded.temporal_consistency == 0.9
    assert loaded.sequence_experience == orig_seq


def test_experience_hint_is_plain_data():
    hint = ExperienceHint(capability="video.image_to_video", preferred_params={"fps": 12}, avg_temporal_consistency=0.9, sample_count=2)
    assert hint.capability == "video.image_to_video"
    assert hint.sample_count == 2
