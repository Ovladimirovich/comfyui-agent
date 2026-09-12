"""M25.2 — Video Image-to-Video Workflow Contract Tests.

Доказывает offline:
  - manifest loads and is valid
  - manifest declares correct required_custom_nodes
  - workflow.json has >0 nodes
  - node graph is connected (no dangling refs)
  - capability is video.image_to_video
  - model_requirements checkpoint satisfied
  - AssetInput.multi fields correct
  - build_prompt works with multi assets (template expansion)
  - _build_multi_asset_input creates correct node IDs
  - sequential chain produces correct output kind=video
"""
from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import MagicMock

import pytest

from app.assets.store import AssetStore
from app.engine import ExecutionPlan
from app.engine.engine import WorkflowEngine
from app.registry.workflow import Workflow, load_workflow, validate_manifest
from app.provider.comfyui import ComfyUIProvider
from app.provider.backend_ref import BackendRef


# ── Helpers ──

_WORKFLOWS_DIR = os.path.join(os.path.dirname(__file__), "..", "workflows")


def _load_video_i2v() -> Workflow:
    manifest_path = os.path.join(_WORKFLOWS_DIR, "video_image_to_video", "manifest.json")
    return load_workflow(manifest_path)


def _make_fake_refs(n: int, tmp_dir: str) -> list[BackendRef]:
    """Create n fake BackendRef for image assets."""
    refs = []
    for i in range(n):
        path = os.path.join(tmp_dir, f"frame_{i}.png")
        with open(path, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 10)
        refs.append(BackendRef(
            provider="comfyui",
            backend="local_comfyui",
            reference={"filename": os.path.basename(path), "subfolder": "", "type": "input"},
        ))
    return refs


# ── Tests: manifest validation ──


class TestVideoI2VManifest:
    def test_manifest_loads(self):
        wf = _load_video_i2v()
        assert wf.id == "video_image_to_video"
        assert wf.version == "1.0.0"

    def test_capability_is_video_image_to_video(self):
        wf = _load_video_i2v()
        assert wf.capability == "video.image_to_video"

    def test_required_custom_nodes_declared(self):
        wf = _load_video_i2v()
        assert "CreateVideo" in wf.required_custom_nodes
        assert "SaveVideo" in wf.required_custom_nodes

    def test_model_requirements_checkpoint(self):
        wf = _load_video_i2v()
        mr = wf.model_requirements
        assert len(mr) == 1
        assert mr[0].kind == "checkpoint"

    def test_multi_asset_input_configured(self):
        wf = _load_video_i2v()
        ai = wf.asset_inputs["images"]
        assert ai.multi is True
        assert ai.max_count == 16
        assert ai.load_node_template is not None
        assert ai.batch_node is not None
        assert ai.batch_field == "images"

    def test_output_kind_video(self):
        wf = _load_video_i2v()
        assert wf.outputs["result"].kind == "video"

    def test_workflow_json_has_nodes(self):
        wf_path = os.path.join(_WORKFLOWS_DIR, "video_image_to_video", "workflow.json")
        with open(wf_path, encoding="utf-8") as f:
            wf = json.load(f)
        assert len(wf) > 0, "workflow.json must have >0 nodes"


# ── Tests: node graph connectivity ──


class TestVideoI2VGraphConnectivity:
    def test_all_edges_reference_existing_nodes(self):
        wf_path = os.path.join(_WORKFLOWS_DIR, "video_image_to_video", "workflow.json")
        with open(wf_path, encoding="utf-8") as f:
            graph = json.load(f)
        node_ids = set(graph.keys())
        for nid, node in graph.items():
            for val in node.get("inputs", {}).values():
                if isinstance(val, list) and len(val) >= 2:
                    ref_id = str(val[0])
                    assert ref_id in node_ids, f"Node {nid} references unknown node {ref_id}"

    def test_output_node_8_exists(self):
        wf_path = os.path.join(_WORKFLOWS_DIR, "video_image_to_video", "workflow.json")
        with open(wf_path, encoding="utf-8") as f:
            graph = json.load(f)
        assert "8" in graph, "Output node '8' (SaveVideo) must exist"
        assert graph["8"].get("class_type") == "SaveVideo"


# ── Tests: build_prompt multi ──


class TestBuildPromptMulti:
    def test_build_prompt_expands_load_nodes(self):
        wf = _load_video_i2v()
        engine = WorkflowEngine(asset_store=MagicMock())
        plan = ExecutionPlan(
            capability="video.image_to_video",
            workflow_id="video_image_to_video",
            version="1.0.0",
            params={"prompt": "smooth animation", "fps": 4, "steps": 20, "seed": 0},
        )
        tmp = tempfile.mkdtemp()
        refs = _make_fake_refs(3, tmp)
        asset_refs = {"images": refs}
        prompt = engine.build_prompt(wf, plan, asset_refs)

        # Template node "10" (LoadImage) should exist
        assert "10" in prompt
        # Expanded nodes should be created
        expanded = [k for k in prompt if k.startswith("10_m25_")]
        assert len(expanded) == 3, f"Expected 3 expanded load nodes, got {len(expanded)}"

        # Batch node "11" should have dotted keys
        batch_inputs = prompt["11"]["inputs"]["images"]
        assert "image0" in batch_inputs
        assert "image1" in batch_inputs
        assert "image2" in batch_inputs

    def test_build_prompt_single_asset_fallback(self):
        """Single asset (not multi) should use legacy path."""
        wf = _load_video_i2v()
        engine = WorkflowEngine(asset_store=MagicMock())
        plan = ExecutionPlan(
            capability="video.image_to_video",
            workflow_id="video_image_to_video",
            version="1.0.0",
            params={"prompt": "test", "fps": 4, "steps": 20, "seed": 0},
        )
        tmp = tempfile.mkdtemp()
        ref = _make_fake_refs(1, tmp)[0]
        # Pass as non-list (legacy single)
        asset_refs = {"images": ref}
        prompt = engine.build_prompt(wf, plan, asset_refs)
        # Should not expand — legacy path sets node "10".image directly
        assert "10" in prompt
        assert prompt["10"]["inputs"]["image"] == ref.reference["filename"]


# ── Tests: execution path integrity ──


class TestExecutionPathIntegrity:
    def test_capability_available_with_runtime(self):
        from app.agent import Agent
        from app.assets.store import AssetStore
        from app.registry.runtime import RuntimeInfo
        import shutil
        shutil.rmtree("__tmptest_videoi2v__", ignore_errors=True)
        agent = Agent(AssetStore(root="__tmptest_videoi2v__"))
        rt = RuntimeInfo(accelerator="directml", vram_gb=12.0, fp16=True, xformers=False, lowvram=True, comfyui_version="0.34.5")
        try:
            result = agent._select_manifest(
                "video.image_to_video",
                runtime=rt,
                models={"checkpoint"},
                custom_nodes={"CreateVideo", "SaveVideo"},
            )
            assert result is not None
            assert result.id == "video_image_to_video"
        finally:
            shutil.rmtree("__tmptest_videoi2v__", ignore_errors=True)

    def test_capability_unknown_without_custom_nodes(self):
        from app.agent import Agent
        from app.assets.store import AssetStore
        from app.registry.runtime import RuntimeInfo
        import shutil
        shutil.rmtree("__tmptest_videoi2v__", ignore_errors=True)
        agent = Agent(AssetStore(root="__tmptest_videoi2v__"))
        rt = RuntimeInfo(accelerator="directml", vram_gb=12.0, fp16=True, xformers=False, lowvram=True, comfyui_version="0.34.5")
        try:
            # Без custom nodes → workflow UNKNOWN → AgentError (AD-18 strict)
            with pytest.raises(Exception):  # noqa: B017 — AgentError ожидаем
                agent._select_manifest(
                    "video.image_to_video",
                    runtime=rt,
                    models={"checkpoint"},
                    custom_nodes=set(),  # no CreateVideo/SaveVideo
                )
        finally:
            shutil.rmtree("__tmptest_videoi2v__", ignore_errors=True)


# ── Tests: limits ──


class TestVideoI2VLimits:
    def test_max_sequence_length_in_limits(self):
        wf_path = os.path.join(_WORKFLOWS_DIR, "video_image_to_video", "manifest.json")
        with open(wf_path, encoding="utf-8") as f:
            m = json.load(f)
        assert m["limits"]["max_sequence_length"] == 16

    def test_max_upload_bytes_in_limits(self):
        wf_path = os.path.join(_WORKFLOWS_DIR, "video_image_to_video", "manifest.json")
        with open(wf_path, encoding="utf-8") as f:
            m = json.load(f)
        assert m["limits"]["max_upload_bytes"] == 209715200
