"""M26.2 — Experience → AdaptivePlanner (AC2 / AC3).

Integration point: AdaptivePlanner(experience_store=...). Experience влияет только на
ranking/preference (soft defaults), НЕ на prohibition. Нет изменения PlanContext / ExecutionRecord.
"""
from __future__ import annotations

from app.engine.experience import (
    ChainExperience,
    ChainStepExperience,
    ExperienceAnalytics,
    ExperienceStore,
)
from app.engine.history import ExecutionHistory, ExecutionRecord
from app.planner.adaptive import AdaptivePlanner
from app.planner.plan import PlanContext, PlanResult, Planner


class FakePlanner(Planner):
    """Детерминированный fallback: возвращает заданную capability + prompt (+ опц. params)."""

    def __init__(self, capability: str, extra_params: dict | None = None) -> None:
        self.capability = capability
        self.extra_params = extra_params or {}

    def plan(self, request: str, context: PlanContext | None = None) -> PlanResult:
        return PlanResult(capability=self.capability, params={"prompt": request, **self.extra_params})


def _history_with(capability, n=3):
    hist = ExecutionHistory()
    for i in range(n):
        hist.record(ExecutionRecord(
            prompt_id=f"p{i}", capability=capability, state="SUCCESS",
            params={"seed": i}, workflow_id="video_image_to_video", workflow_version="1",
        ))
    return hist


def _video_chain(chain_id, temporal, video_params):
    steps = [
        ChainStepExperience(step_index=0, capability="image.generate", output_assets=["a1"],
                            workflow_id="image_generate", workflow_version="1"),
        ChainStepExperience(step_index=1, capability="video.image_to_video", output_assets=["v1"],
                            workflow_id="video_image_to_video", workflow_version="1"),
    ]
    seq = {"video_params": video_params, "temporal_consistency": temporal,
           "image_to_video_transition": "success"}
    return ChainExperience(
        chain_id=chain_id, session_id="s1", steps=steps,
        overall_state="COMPLETED", completed_steps=2,
        temporal_consistency=temporal, sequence_experience=seq,
    )


def _exp_store(tmp_path, chains):
    store = ExperienceStore(str(tmp_path / "experience"))
    for c in chains:
        store.record(c)
    return store


def test_experience_available_changes_preference(tmp_path):
    """AC3: experience → observable preference в следующем plan()."""
    hist = _history_with("video.image_to_video", 3)
    # >=2 цепочек с temporal-опытом → experience-preference применяется
    store = _exp_store(tmp_path, [
        _video_chain("c1", 0.9, {"fps": 12, "steps": 25}),
        _video_chain("c2", 0.7, {"fps": 8, "steps": 20}),
    ])
    planner = AdaptivePlanner(history=hist, fallback=FakePlanner("video.image_to_video"), experience_store=store)
    result = planner.plan("make a video", context=PlanContext())
    # experience-preferred params присутствуют и не запрещают capability
    assert result.capability == "video.image_to_video"
    # выбрана цепочка с наивысшим temporal (0.9) → fps=12
    assert result.params.get("fps") == 12
    assert result.params.get("steps") == 25
    # explicit/исторические params не потеряны
    assert "prompt" in result.params


def test_experience_absent_falls_back(tmp_path):
    """AC2: experience_store=None → старое поведение без experience-влияния."""
    hist = _history_with("video.image_to_video", 3)
    planner = AdaptivePlanner(history=hist, fallback=FakePlanner("video.image_to_video"), experience_store=None)
    result = planner.plan("make a video", context=PlanContext())
    assert result.capability == "video.image_to_video"
    assert "fps" not in result.params  # нет experience-влияния
    assert "steps" not in result.params


def test_experience_insufficient_falls_back(tmp_path):
    """AC2: недостаточно samples → fallback (нейтрально, без влияния)."""
    hist = _history_with("video.image_to_video", 3)
    # только 1 цепочка с temporal → ниже min_samples(2) → preferred_params вернёт {}
    store = _exp_store(tmp_path, [_video_chain("c1", 0.9, {"fps": 12})])
    planner = AdaptivePlanner(history=hist, fallback=FakePlanner("video.image_to_video"), experience_store=store)
    result = planner.plan("make a video", context=PlanContext())
    assert "fps" not in result.params
    assert result.capability == "video.image_to_video"


def test_no_hard_prohibition_capability_remains_available(tmp_path):
    """Критическое правило: experience НЕ запрещает capability/workflow."""
    hist = _history_with("video.image_to_video", 3)
    store = _exp_store(tmp_path, [_video_chain("c1", 0.1, {"fps": 4})])  # низкий temporal
    planner = AdaptivePlanner(history=hist, fallback=FakePlanner("video.image_to_video"), experience_store=store)
    result = planner.plan("make a video", context=PlanContext())
    # capability доступен, план построен; никакого ban
    assert result.capability == "video.image_to_video"
    # при min_samples=2 single chain → нет experience-влияния (нейтрально), но не запрет
    assert "fps" not in result.params


def test_experience_preference_is_soft_default_not_override(tmp_path):
    """Experience params — defaults; explicit user params (base_result.params) побеждают."""
    hist = _history_with("video.image_to_video", 3)
    store = _exp_store(tmp_path, [
        _video_chain("c1", 0.9, {"fps": 12, "steps": 25}),
        _video_chain("c2", 0.7, {"fps": 8, "steps": 20}),
    ])
    # user явно задаёт fps=30 через fallback planner → должен победить experience-default
    planner = AdaptivePlanner(
        history=hist,
        fallback=FakePlanner("video.image_to_video", extra_params={"fps": 30}),
        experience_store=store,
    )
    result = planner.plan("make a video", context=PlanContext())
    assert result.capability == "video.image_to_video"
    # explicit fps=30 побеждает над experience-default fps=12
    assert result.params.get("fps") == 30
