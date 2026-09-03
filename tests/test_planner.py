"""LLM-планировщик (главная задача) — Natural-language → capability + params."""
from __future__ import annotations

import os

from app.planner import HeuristicPlanner, LLMPlanner


def test_heuristic_audio():
    r = HeuristicPlanner().plan("сделай lo-fi трек про дождь")
    assert r.capability == "audio.generate"
    assert "prompt" in r.params


def test_heuristic_video():
    r = HeuristicPlanner().plan("сгенерируй видео с бегущим котом")
    assert r.capability == "video.generate"


def test_heuristic_image_default():
    r = HeuristicPlanner().plan("нарисуй замок на скале")
    assert r.capability == "image.generate"


def test_llm_planner_requires_key():
    os.environ.pop("OPENROUTER_API_KEY", None)
    try:
        LLMPlanner()
        assert False, "ожидалась ошибка без OPENROUTER_API_KEY"
    except RuntimeError:
        pass
