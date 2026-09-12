"""M26.4 — Experience → Composer suggestions (AC4).

Experience → signal → suggestion (НЕ automatic prohibition / re-planning).
Существующий CompositionResult behaviour сохраняется.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from app.engine.experience import ExperienceHint
from app.planner.composer import Composer
from app.planner.composition_result import CompositionResult


def _composer():
    cap = MagicMock()
    cap.id = "video.image_to_video"
    cap.media_output = "video"
    cap.default_workflow = "video_generate@1"
    cap_reg = MagicMock()
    cap_reg.get.return_value = cap
    cap_reg.all.return_value = [cap]
    wf_reg = MagicMock()
    composer = Composer(cap_reg, wf_reg)
    # изолируем graph-поиск: одна trivial path
    composer._graph = MagicMock()
    composer._graph.find_paths.return_value = [["video.image_to_video"]]
    return composer


def test_suggestion_present_with_relevant_experience():
    composer = _composer()
    hint = ExperienceHint(
        capability="video.image_to_video",
        preferred_params={"fps": 12},
        avg_temporal_consistency=0.9,
        sample_count=3,
    )
    result = composer.compose(
        target_capability="video.image_to_video",
        params={},
        available_types=set(),
        experience_hint=hint,
    )
    assert isinstance(result, CompositionResult)
    assert len(result.suggestions) == 1
    assert "Experience (n=3)" in result.suggestions[0]
    assert "avg temporal consistency 0.90" in result.suggestions[0]
    assert "preferred params" in result.suggestions[0]


def test_no_suggestion_without_experience():
    composer = _composer()
    result = composer.compose(
        target_capability="video.image_to_video",
        params={},
        available_types=set(),
        experience_hint=None,
    )
    assert result.suggestions == []


def test_no_suggestion_when_sample_count_zero():
    composer = _composer()
    hint = ExperienceHint(capability="video.image_to_video", sample_count=0)
    result = composer.compose(
        target_capability="video.image_to_video",
        params={},
        available_types=set(),
        experience_hint=hint,
    )
    assert result.suggestions == []


def test_suggestion_does_not_alter_chain_or_alternatives():
    """Suggestion необязательна и не меняет capability availability / выбор цепочки."""
    composer = _composer()
    params = {"workflow": "video_generate@1"}
    # без hint
    base = composer.compose(
        target_capability="video.image_to_video",
        params=params,
        available_types=set(),
        experience_hint=None,
    )
    # с hint
    hint = ExperienceHint(capability="video.image_to_video", avg_temporal_consistency=0.8, sample_count=2)
    result = composer.compose(
        target_capability="video.image_to_video",
        params=params,
        available_types=set(),
        experience_hint=hint,
    )
    # chain и alternatives идентичны — suggestion НЕ altering selection
    assert result.chain == base.chain
    assert result.alternatives == base.alternatives
    assert result.success == base.success
    # отличается только suggestions
    assert len(result.suggestions) == 1
    assert len(base.suggestions) == 0
