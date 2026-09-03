"""M3 tests — Capability + Workflow Registry.

Покрытие (M3-task §16): manifest discovery, manifest validation (±),
capability lookup, versioning, runtime/model/custom-node/input compatibility,
DECLARED_ONLY, candidate selection, determinism + media-agnostic contract.

Без mock: используются реальные RuntimeInfo/Asset и файловая система (tmp_path).
Никакой отправки в ComfyUI /prompt (M3-task §17).
"""
import json

import pytest

from app.assets import Asset
from app.registry import (
    AssetInput,
    UnavailableReason,
    UnknownReason,
    Workflow,
    WorkflowStatus,
    evaluate_compatibility,
    load_workflow,
    validate_manifest,
)
from app.registry.capability import CapabilityRegistry
from app.registry.registry import WorkflowRegistry
from app.registry.runtime import RuntimeInfo
from app.registry.semver import compare_version, parse_version


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _write(tmp_path, name, manifest, workflow=None):
    d = tmp_path / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    if workflow is not None:
        (d / "workflow.json").write_text(json.dumps(workflow), encoding="utf-8")
    return d


TXT2IMG_MANIFEST = {
    "id": "txt2img", "version": "1.0.0", "capability": "image.generate",
    "provider": "comfyui", "backend": "local_comfyui",
    "inputs": {"prompt": {"node": "2", "field": "text"}},
    "asset_inputs": {},
    "outputs": {"result": {"node": "9", "kind": "image"}},
    "parameters": {}, "required_models": ["checkpoint"], "required_custom_nodes": [],
    "min_comfyui_version": "0.0.0",
    "requirements": {"accelerator": "any", "xformers": False, "min_vram_gb": 4, "fp16": True},
}
TXT2IMG_WF = {
    "2": {"class_type": "CLIPTextEncode", "inputs": {"text": ""}},
    "9": {"class_type": "SaveImage", "inputs": {"images": ["6", 0]}},
}

IMG2IMG_MANIFEST = {
    "id": "img2img", "version": "1.0.0", "capability": "image.edit",
    "provider": "comfyui", "backend": "local_comfyui",
    "inputs": {"prompt": {"node": "6", "field": "text"}},
    "asset_inputs": {"image": {"node": "10", "field": "image", "kind": "image"}},
    "outputs": {"result": {"node": "9", "kind": "image"}},
    "parameters": {}, "required_models": ["checkpoint"], "required_custom_nodes": [],
    "min_comfyui_version": "0.0.0",
    "requirements": {"accelerator": "any", "xformers": False, "min_vram_gb": 4, "fp16": True},
}
IMG2IMG_WF = {
    "10": {"class_type": "LoadImage", "inputs": {"image": "", "upload": "image"}},
    "6": {"class_type": "CLIPTextEncode", "inputs": {"text": ""}},
    "9": {"class_type": "SaveImage", "inputs": {"images": ["6", 0]}},
}

RT_OK = RuntimeInfo(accelerator="directml", vram_gb=12, fp16=True, xformers=False,
                   lowvram=True, comfyui_version="0.10.9")


# --------------------------------------------------------------------------- #
# 1. Manifest discovery
# --------------------------------------------------------------------------- #

def test_manifest_discovery(tmp_path):
    _write(tmp_path, "txt2img", TXT2IMG_MANIFEST, TXT2IMG_WF)
    _write(tmp_path, "img2img", IMG2IMG_MANIFEST, IMG2IMG_WF)
    reg = WorkflowRegistry()
    found = reg.discover(tmp_path)
    assert {w.id for w in found} == {"txt2img", "img2img"}
    assert all(w.status == WorkflowStatus.VALIDATED for w in found)


# --------------------------------------------------------------------------- #
# 2. Manifest validation (positive / negative)
# --------------------------------------------------------------------------- #

def test_manifest_validation_positive():
    caps = CapabilityRegistry()
    validate_manifest(TXT2IMG_MANIFEST, caps)  # не бросает


@pytest.mark.parametrize("bad", [
    {"id": "x", "capability": "image.generate", "provider": "comfyui"},  # нет version
    {"id": "x", "version": "1.0", "capability": "image.generate", "provider": "comfyui"},  # плохой semver
    {"id": "x", "version": "1.0.0", "capability": "nope.cap", "provider": "comfyui"},  # нет capability
    {"id": "x", "version": "1.0.0", "capability": "image.generate", "provider": "comfyui",
     "inputs": {"p": {"node": "2"}}},  # inputs без field
    {"id": "x", "version": "1.0.0", "capability": "image.generate", "provider": "comfyui",
     "asset_inputs": {"i": {"node": "2", "field": "f"}}},  # asset_inputs без kind
    {"id": "x", "version": "1.0.0", "capability": "image.generate", "provider": "comfyui",
     "outputs": {"o": {"node": "2"}}},  # outputs без kind
    {"id": "x", "version": "1.0.0", "capability": "image.generate", "provider": "comfyui",
     "required_models": "checkpoint"},  # не список
])
def test_manifest_validation_negative(bad):
    caps = CapabilityRegistry()
    with pytest.raises(Exception):
        validate_manifest(bad, caps)


def test_manifest_invalid_workflow_structure(tmp_path):
    # manifest ссылается на node 99, которого нет в workflow.json
    m = dict(TXT2IMG_MANIFEST)
    m["inputs"] = {"prompt": {"node": "99", "field": "text"}}
    _write(tmp_path, "bad", m, TXT2IMG_WF)
    wf = load_workflow(tmp_path / "bad" / "manifest.json", CapabilityRegistry())
    assert wf.status == WorkflowStatus.UNAVAILABLE
    assert UnavailableReason.INVALID_WORKFLOW in wf.reasons


# --------------------------------------------------------------------------- #
# 3. Capability lookup
# --------------------------------------------------------------------------- #

def test_capability_lookup(tmp_path):
    _write(tmp_path, "txt2img", TXT2IMG_MANIFEST, TXT2IMG_WF)
    reg = WorkflowRegistry()
    reg.discover(tmp_path)
    assert reg.by_capability("image.generate")[0].id == "txt2img"
    assert reg.by_capability("video.generate") == []


# --------------------------------------------------------------------------- #
# 4. Versioning + latest
# --------------------------------------------------------------------------- #

def test_versioning_latest(tmp_path):
    for v in ("1.0.0", "1.1.0", "2.0.0"):
        m = dict(TXT2IMG_MANIFEST, version=v)
        _write(tmp_path, f"txt2img_{v}", m, TXT2IMG_WF)
    reg = WorkflowRegistry()
    reg.discover(tmp_path)
    assert reg.latest("txt2img") == "2.0.0"
    # select возвращает КОНКРЕТНУЮ версию, не 'latest'
    sel = reg.select("image.generate", RT_OK, models={"checkpoint"}, custom_nodes=set())
    assert sel.version == "2.0.0"


def test_semver_compare():
    assert compare_version("0.10.9", "0.9.99") > 0
    assert compare_version("1.2.0", "1.10.0") < 0
    assert parse_version("1.0.0")


# --------------------------------------------------------------------------- #
# 5. Runtime compatibility (compatible / incompatible / unknown)
# --------------------------------------------------------------------------- #

def test_runtime_compatible():
    wf = _wf("image.generate", required_models=[], custom_nodes=[],
             requirements={"accelerator": "any", "min_vram_gb": 4})
    st, reasons = evaluate_compatibility(wf, RT_OK, models=set(), custom_nodes=set())
    assert st == WorkflowStatus.AVAILABLE


def test_runtime_incompatible_vram():
    rt = RuntimeInfo(accelerator="directml", vram_gb=2, fp16=True, xformers=False,
                     lowvram=True, comfyui_version="0.10.9")
    wf = _wf("image.generate", required_models=[], custom_nodes=[],
             requirements={"min_vram_gb": 4})
    st, reasons = evaluate_compatibility(wf, rt, models=set(), custom_nodes=set())
    assert st == WorkflowStatus.UNAVAILABLE
    assert UnavailableReason.INSUFFICIENT_VRAM in reasons


def test_runtime_unknown_version():
    rt = RuntimeInfo(accelerator="directml", vram_gb=12, fp16=True, xformers=False,
                     lowvram=True, comfyui_version=None)  # версия неизвестна
    wf = _wf("image.generate", required_models=[], custom_nodes=[],
             requirements={}, min_comfyui_version="0.20.0")
    st, reasons = evaluate_compatibility(wf, rt, models=set(), custom_nodes=set())
    assert st == WorkflowStatus.UNKNOWN
    assert UnknownReason.UNKNOWN_VERSION in reasons  # UNKNOWN != AVAILABLE


# --------------------------------------------------------------------------- #
# 6. Model compatibility
# --------------------------------------------------------------------------- #

def test_model_present_missing():
    wf = _wf("image.generate", required_models=["checkpoint"], custom_nodes=[])
    ok, _ = evaluate_compatibility(wf, RT_OK, models={"checkpoint"}, custom_nodes=set())
    miss, reasons = evaluate_compatibility(wf, RT_OK, models=set(), custom_nodes=set())
    none, reasons2 = evaluate_compatibility(wf, RT_OK, models=None, custom_nodes=set())
    assert ok == WorkflowStatus.AVAILABLE
    assert miss == WorkflowStatus.UNAVAILABLE and UnavailableReason.MISSING_MODEL in reasons
    assert none == WorkflowStatus.UNAVAILABLE and UnavailableReason.MISSING_MODEL in reasons2


# --------------------------------------------------------------------------- #
# 7. Custom node compatibility
# --------------------------------------------------------------------------- #

def test_custom_node_present_missing():
    wf = _wf("video.generate", required_models=[], custom_nodes=["ComfyUI-Wan"])
    ok, _ = evaluate_compatibility(wf, RT_OK, models=set(), custom_nodes={"ComfyUI-Wan"})
    miss, reasons = evaluate_compatibility(wf, RT_OK, models=set(), custom_nodes=set())
    assert ok == WorkflowStatus.AVAILABLE
    assert miss == WorkflowStatus.UNAVAILABLE and UnavailableReason.MISSING_CUSTOM_NODE in reasons


# --------------------------------------------------------------------------- #
# 8. Input compatibility (контракт, не обработка медиа)
# --------------------------------------------------------------------------- #

def test_input_compatibility():
    wf = _wf("image.edit", required_models=[], custom_nodes=[],
             asset_inputs={"image": ("10", "image", "image")})
    img = Asset(id="a", type="image", path="/x")
    vid = Asset(id="b", type="video", path="/y")
    ok, _ = evaluate_compatibility(wf, RT_OK, models=set(), custom_nodes=set(), assets=[img])
    bad, reasons = evaluate_compatibility(wf, RT_OK, models=set(), custom_nodes=set(), assets=[vid])
    assert ok == WorkflowStatus.AVAILABLE
    assert bad == WorkflowStatus.UNAVAILABLE and UnavailableReason.INPUT_INCOMPATIBLE in reasons


def test_input_compatibility_kind_generic():
    # доказательство media-agnostic: kind 'video' требует Asset(type='video')
    wf = _wf("video.image_to_video", required_models=[], custom_nodes=[],
             asset_inputs={"src": ("1", "image", "video")})
    img = Asset(id="a", type="image", path="/x")
    vid = Asset(id="b", type="video", path="/y")
    assert evaluate_compatibility(wf, RT_OK, assets=[img])[0] == WorkflowStatus.UNAVAILABLE
    assert evaluate_compatibility(wf, RT_OK, assets=[vid])[0] == WorkflowStatus.AVAILABLE


# --------------------------------------------------------------------------- #
# 9. DECLARED_ONLY не становится AVAILABLE
# --------------------------------------------------------------------------- #

def test_declared_only_not_available(tmp_path):
    m = dict(TXT2IMG_MANIFEST, id="video_generate", capability="video.generate",
             declared_only=True, version="0.0.0-declared")
    _write(tmp_path, "video_generate", m)  # без workflow.json
    reg = WorkflowRegistry()
    reg.discover(tmp_path)
    wf = reg.by_capability("video.generate")[0]
    assert wf.status == WorkflowStatus.DECLARED_ONLY
    res = reg.candidates("video.generate", RT_OK, models={"checkpoint"}, custom_nodes=set())
    assert res.available == []  # не AVAILABLE


# --------------------------------------------------------------------------- #
# 10. Candidate selection
# --------------------------------------------------------------------------- #

def test_candidate_selection_only_from_available(tmp_path):
    _write(tmp_path, "txt2img", TXT2IMG_MANIFEST, TXT2IMG_WF)
    reg = WorkflowRegistry()
    reg.discover(tmp_path)
    # models пуст -> txt2img UNAVAILABLE -> кандидатов нет
    assert reg.select("image.generate", RT_OK, models=set(), custom_nodes=set()) is None
    # models заданы -> AVAILABLE -> выбран конкретный
    sel = reg.select("image.generate", RT_OK, models={"checkpoint"}, custom_nodes=set())
    assert sel is not None and sel.workflow_id == "txt2img"
    # override на недоступный -> None
    assert reg.select("image.generate", RT_OK, models=set(), override="txt2img@1.0.0") is None


# --------------------------------------------------------------------------- #
# 11. Determinism
# --------------------------------------------------------------------------- #

def test_determinism(tmp_path):
    _write(tmp_path, "txt2img", TXT2IMG_MANIFEST, TXT2IMG_WF)
    reg = WorkflowRegistry()
    reg.discover(tmp_path)
    a = reg.select("image.generate", RT_OK, models={"checkpoint"}, custom_nodes=set())
    b = reg.select("image.generate", RT_OK, models={"checkpoint"}, custom_nodes=set())
    assert a == b


# --------------------------------------------------------------------------- #
# Media-agnostic architecture contract
# --------------------------------------------------------------------------- #

def test_media_agnostic_contract(tmp_path):
    # image/video/audio регистрируются ЕДИНЫМ механизмом (asset_inputs/outputs/kind)
    for cap, kind in [("image.generate", "image"), ("video.generate", "video"),
                      ("audio.generate", "audio")]:
        m = {"id": f"dec_{cap}", "version": "0.0.0-declared", "declared_only": True,
             "capability": cap, "provider": "comfyui", "backend": "local_comfyui",
             "outputs": {"result": {"node": "0", "kind": kind}},
             "required_models": [], "required_custom_nodes": [],
             "min_comfyui_version": "0.0.0",
             "requirements": {"accelerator": "any", "min_vram_gb": 4}}
        _write(tmp_path, cap, m)
    reg = WorkflowRegistry()
    reg.discover(tmp_path)
    # ни один declared_only не попадает в AVAILABLE; единый путь evaluate
    for cap in ("image.generate", "video.generate", "audio.generate"):
        res = reg.candidates(cap, RT_OK)
        assert list(res.report.keys()) == [f"dec_{cap}"]
        assert all(s == WorkflowStatus.DECLARED_ONLY for _, s, _ in res.report.values())


# --------------------------------------------------------------------------- #
# Реальный workflow проекта (section 14): manifest против фактического графа
# --------------------------------------------------------------------------- #

def test_real_project_workflows():
    reg = WorkflowRegistry()
    reg.discover("workflows")  # реальный каталог агента
    txt = reg.get("txt2img", "1.0.0")
    assert txt is not None
    assert txt.status == WorkflowStatus.VALIDATED  # manifest + workflow.json валидны
    assert txt.workflow_path is not None
    # M6: video_generate реализован и валиден (реальный граф на Colab проходит E2E) -> VALIDATED.
    # M7: audio_generate реализован (SoniloTextToMusic + SaveAudio) -> VALIDATED (E2E заблокирован
    #     только ключом Sonilo, см. HANDOFF; код пайплайна доказан).
    assert reg.get("video_generate").status == WorkflowStatus.VALIDATED
    assert reg.get("audio_generate").status == WorkflowStatus.VALIDATED


# --------------------------------------------------------------------------- #
# fixture builder
# --------------------------------------------------------------------------- #

def _wf(capability, required_models=None, custom_nodes=None, asset_inputs=None,
        requirements=None, min_comfyui_version="0.0.0"):
    return Workflow(
        id="fixture", version="1.0.0", capability=capability, provider="comfyui",
        backend="local_comfyui",
        asset_inputs={k: AssetInput(n, f, k) for k, (n, f, k) in (asset_inputs or {}).items()},
        required_models=required_models or [],
        required_custom_nodes=custom_nodes or [],
        min_comfyui_version=min_comfyui_version,
        requirements=requirements or {},
    )
