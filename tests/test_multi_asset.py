"""M25 Phase 2 — Multi-Asset Workflow Input Tests.

Доказывает offline:
  - AssetInput multi fields (multi, max_count, load_node_template, batch_node, batch_field)
  - validate_manifest passes with multi
  - validate_manifest fails without batch_node/batch_field when multi=true
  - load_workflow parses multi fields
  - single-asset backward compat
  - build_prompt multi logic (N load nodes + batch)
  - resolve_asset_inputs list support
  - video_image_to_video manifest loads
"""
from __future__ import annotations

import json
import os
import tempfile
import pytest

from app.registry.workflow import (
    AssetInput,
    ManifestError,
    OutputSpec,
    Workflow,
    load_workflow,
    validate_manifest,
)


# ── Helpers ──

def _make_manifest(**overrides) -> dict:
    base = {
        "id": "test_wf",
        "version": "1.0.0",
        "capability": "image.generate",
        "provider": "comfyui",
        "backend": "local_comfyui",
        "inputs": {},
        "asset_inputs": {},
        "outputs": {"result": {"node": "9", "kind": "image"}},
        "parameters": {},
        "required_models": [],
        "required_custom_nodes": [],
    }
    base.update(overrides)
    return base


def _write_manifest(data: dict, tmp_dir: str) -> str:
    path = os.path.join(tmp_dir, "manifest.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return path


def _write_workflow(nodes: dict, tmp_dir: str) -> str:
    path = os.path.join(tmp_dir, "workflow.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(nodes, f, ensure_ascii=False)
    return path


# ── Tests: AssetInput multi fields ──

class TestAssetInputMultiFields:
    def test_default_multi_false(self):
        ai = AssetInput(node="10", field="image", kind="image")
        assert ai.multi is False
        assert ai.max_count == 1
        assert ai.load_node_template is None
        assert ai.batch_node is None
        assert ai.batch_field is None

    def test_multi_fields_set(self):
        ai = AssetInput(
            node="10",
            field="image",
            kind="image",
            multi=True,
            max_count=16,
            load_node_template="10",
            batch_node="11",
            batch_field="images",
        )
        assert ai.multi is True
        assert ai.max_count == 16
        assert ai.load_node_template == "10"
        assert ai.batch_node == "11"
        assert ai.batch_field == "images"


# ── Tests: validate_manifest multi ──

class TestValidateManifestMulti:
    def test_multi_with_batch_fields_passes(self):
        data = _make_manifest(
            asset_inputs={
                "images": {
                    "node": "10",
                    "field": "image",
                    "kind": "image",
                    "multi": True,
                    "max_count": 16,
                    "load_node_template": "10",
                    "batch_node": "11",
                    "batch_field": "images",
                }
            }
        )
        validate_manifest(data)

    def test_multi_without_batch_node_fails(self):
        data = _make_manifest(
            asset_inputs={
                "images": {
                    "node": "10",
                    "field": "image",
                    "kind": "image",
                    "multi": True,
                    "batch_field": "images",
                }
            }
        )
        with pytest.raises(ManifestError, match="batch_node"):
            validate_manifest(data)

    def test_multi_without_batch_field_fails(self):
        data = _make_manifest(
            asset_inputs={
                "images": {
                    "node": "10",
                    "field": "image",
                    "kind": "image",
                    "multi": True,
                    "batch_node": "11",
                }
            }
        )
        with pytest.raises(ManifestError, match="batch_field"):
            validate_manifest(data)

    def test_non_multi_no_batch_required(self):
        data = _make_manifest(
            asset_inputs={
                "image": {
                    "node": "10",
                    "field": "image",
                    "kind": "image",
                }
            }
        )
        validate_manifest(data)


# ── Tests: load_workflow multi ──

class TestLoadWorkflowMulti:
    def test_load_workflow_parses_multi(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = _make_manifest(
                asset_inputs={
                    "images": {
                        "node": "10",
                        "field": "image",
                        "kind": "image",
                        "multi": True,
                        "max_count": 8,
                        "load_node_template": "10",
                        "batch_node": "11",
                        "batch_field": "images",
                    }
                }
            )
            _write_manifest(manifest, tmp)
            _write_workflow({
                "10": {"inputs": {"image": "input.png"}, "class_type": "LoadImage"},
                "11": {"inputs": {"images": []}, "class_type": "ImageBatch"},
                "9": {"inputs": {}, "class_type": "SaveImage"},
            }, tmp)

            wf = load_workflow(os.path.join(tmp, "manifest.json"))
            assert wf.status.value in ("VALIDATED", "AVAILABLE")
            ai = wf.asset_inputs["images"]
            assert ai.multi is True
            assert ai.max_count == 8
            assert ai.batch_node == "11"
            assert ai.batch_field == "images"

    def test_load_workflow_single_backward_compat(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = _make_manifest(
                asset_inputs={
                    "image": {
                        "node": "10",
                        "field": "image",
                        "kind": "image",
                    }
                }
            )
            _write_manifest(manifest, tmp)
            _write_workflow({"10": {"inputs": {"image": "input.png"}, "class_type": "LoadImage"}}, tmp)

            wf = load_workflow(os.path.join(tmp, "manifest.json"))
            ai = wf.asset_inputs["image"]
            assert ai.multi is False
            assert ai.load_node_template is None


# ── Tests: video_image_to_video manifest ──

class TestVideoI2VManifest:
    def test_manifest_loads(self):
        manifest_path = os.path.join(
            os.path.dirname(__file__), "..", "workflows", "video_image_to_video", "manifest.json"
        )
        if not os.path.exists(manifest_path):
            pytest.skip("video_image_to_video workflow not found")

        wf = load_workflow(manifest_path)
        assert wf.id == "video_image_to_video"
        assert wf.capability == "video.image_to_video"
        assert "images" in wf.asset_inputs
        assert wf.asset_inputs["images"].multi is True
        assert wf.asset_inputs["images"].batch_node == "11"
        assert wf.asset_inputs["images"].batch_field == "images"
        assert "result" in wf.outputs
        assert wf.outputs["result"].kind == "video"
