"""PHASE 2.3 — text.generate hardening (workflow + routing + build prompt).

Покрывает баги, найденные на реальном локальном E2E (ComfyUI 0.34.5):
  1. OpenAICompatibleChat (COMFY_AUTOGROW_V3) в API принимает ТОЛЬКО dotted-ключи
     "prompts.text_1", НЕ вложенный dict "prompts": {"text_1": ...}
     (comfy_api._io.build_nested_inputs разворачивает dotted values).
  2. api_key ноды ДОЛЖЕН быть непустым (нода падает "No API key",
     даже для локального llama-server, который ключ не проверяет).
  3. SaveText.format — валидное значение 'txt' (не 'text').
"""
from __future__ import annotations

import json
import os
import pytest

from app.assets.store import AssetStore
from app.engine import ExecutionPlan
from app.engine.engine import WorkflowEngine
from app.planner.heuristic import HeuristicPlanner
from app.registry.workflow import load_workflow, WorkflowStatus


STRETCH = os.path.join(os.path.dirname(__file__), "..", "workflows", "text_generate")
MANIFEST = os.path.join(STRETCH, "manifest.json")
WORKFLOW = os.path.join(STRETCH, "workflow.json")


def _wf():
    return load_workflow(MANIFEST)


class TestManifest:
    def test_loads_and_validates(self):
        wf = _wf()
        assert wf.id == "text_generate"
        assert wf.capability == "text.generate"
        assert wf.status.value in ("VALIDATED", "AVAILABLE")

    def test_workflow_json_present(self):
        wf = _wf()
        assert wf.workflow_path
        with open(wf.workflow_path, encoding="utf-8") as fh:
            data = json.load(fh)
        assert data["1"]["class_type"] == "OpenAICompatibleChat"
        assert data["2"]["class_type"] == "SaveText"

    def test_savetext_format_is_txt(self):
        with open(WORKFLOW, encoding="utf-8") as fh:
            data = json.load(fh)
        _format = data["2"]["inputs"]["format"]
        assert _format == "txt", f"SaveText.format должен быть 'txt', получено {_format!r}"

    def test_api_key_nonempty(self):
        with open(WORKFLOW, encoding="utf-8") as fh:
            data = json.load(fh)
        key = data["1"]["inputs"]["api_key"]
        assert key, "api_key должен быть непустым (нода падает 'No API key' без него)"

    def test_prompt_static_dotted(self):
        with open(WORKFLOW, encoding="utf-8") as fh:
            data = json.load(fh)
        inputs = data["1"]["inputs"]
        # Autogrow v3: dotted-ключ "prompts.text_1", а НЕ вложенный dict "prompts"
        assert "prompts.text_1" in inputs
        assert "prompts" not in inputs or not isinstance(inputs["prompts"], dict)


class TestRouting:
    def test_text_keyword_routes_to_text_generate(self):
        planner = HeuristicPlanner()
        res = planner.plan("please chat with AI about the weather",
                           PlanCtx(capabilities={"text.generate"}))
        assert res.capability == "text.generate"

    def test_write_keyword_routes_to_text_generate(self):
        planner = HeuristicPlanner()
        res = planner.plan("write a haiku", PlanCtx(capabilities={"text.generate"}))
        assert res.capability == "text.generate"


class TestBuildPrompt:
    def test_build_prompt_dotted_and_parms(self, tmp_path):
        wf = _wf()
        store = AssetStore(root=tmp_path / "store")
        engine = WorkflowEngine(store)
        plan = ExecutionPlan(
            "text.generate", wf.id, wf.version,
            params={
                "prompt": "Say hello",
                "model": "default",
                "base_url": "http://127.0.0.1:20130/v1",
            },
        )
        prompt = engine.build_prompt(wf, plan, {})
        n1 = prompt["1"]["inputs"]
        # Autogrow dotted key
        assert n1["prompts.text_1"] == "Say hello"
        assert "prompts" not in n1
        assert n1["api_key"] == "local"
        assert n1["model"] == "default"
        assert prompt["2"]["inputs"]["format"] == "txt"


import app.planner.plan as _plan_mod


def PlanCtx(*, capabilities):
    return _plan_mod.PlanContext(capabilities=tuple(capabilities))