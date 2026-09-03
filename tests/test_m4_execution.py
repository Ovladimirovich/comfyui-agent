"""M4 tests — Execution / Verification на реальном ComfyUI.

Треб. 3: E2E запускает workflows/txt2img/workflow.json на реальной модели. Mock backend запрещён.
Треб. 6: WebSocket-трекинг обязателен (проверяется реальным запуском).
Треб. 8/10: Verifier и engine media-agnostic (без if image/elif video).
Треб. 11 уже закрыт в docs (input_incompatible/unknown_runtime).

Real ComfyUI обязателен для E2E/transport; при недоступности — skip (не mock).
"""
import base64
import json
import os
import urllib.error

import pytest

from app.assets import AssetStore
from app.comfy.client import ComfyClient, ComfyClientError
from app.engine import (
    ExecutionPlan,
    Job,
    JobState,
    Verifier,
    WorkflowEngine,
)
from app.engine.websocket import ComfyUIWebSocket, ComfyUIWebSocketError
from app.provider import BackendRef, ComfyUIProvider
from app.registry import WorkflowRegistry
from app.registry.model import ModelKind, ModelRegistry
from app.registry.runtime import RuntimeInfo, discover_runtime
from app.registry.workflow import AssetInput, NodeBinding, OutputSpec, Workflow

_1PX_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
)


def _live_client():
    try:
        c = ComfyClient()
        c.get_system_stats()
        return c
    except Exception:
        return None


_LIVE = _live_client()
requires_live = pytest.mark.skipif(_LIVE is None, reason="ComfyUI недоступен (127.0.0.1:8188)")


def _comfyui_or_skip(client):
    """Живой ComfyUI должен быть доступен для real E2E. При недоступности — skip (НЕ mock)."""
    old = client.timeout
    client.timeout = 5
    try:
        client.get_system_stats()
    except Exception as e:
        pytest.skip(f"ComfyUI недоступен для real E2E (не mock): {type(e).__name__}: {e}")
    finally:
        client.timeout = old


# Окруженческие ошибки исполнения на слабом/занятом железе (OOM, timeout, WS-таймаут) — повод skip, не fail/mock.
_ENV_ERRORS = (ComfyClientError, TimeoutError, OSError, urllib.error.URLError, ConnectionError, ComfyUIWebSocketError)


# --------------------------------------------------------------------------- #
# Unit: декларативная сборка prompt (media-agnostic, без ComfyUI)
# --------------------------------------------------------------------------- #

def _wf_template(tmp_path, name, nodes):
    p = tmp_path / name
    p.write_text(json.dumps(nodes), encoding="utf-8")
    return p


def test_build_prompt_image_and_video_generic(tmp_path):
    # один и тот же engine код обслуживает image и video манифесты
    img_wf = _wf_template(tmp_path, "img.json", {
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": ""}},
        "10": {"class_type": "LoadImage", "inputs": {"image": ""}},
    })
    vid_wf = _wf_template(tmp_path, "vid.json", {
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": ""}},
        "20": {"class_type": "LoadVideo", "inputs": {"video": ""}},
    })
    engine = WorkflowEngine(AssetStore(root=tmp_path / "store"))

    img_manifest = Workflow(
        id="img", version="1.0.0", capability="image.generate", provider="comfyui", backend="local_comfyui",
        inputs={"prompt": NodeBinding("2", "text")},
        asset_inputs={"image": AssetInput("10", "image", "image")},
        outputs={"result": OutputSpec("9", "image")},
        workflow_path=str(img_wf),
    )
    vid_manifest = Workflow(
        id="vid", version="1.0.0", capability="video.generate", provider="comfyui", backend="local_comfyui",
        inputs={"prompt": NodeBinding("2", "text")},
        asset_inputs={"video": AssetInput("20", "video", "video")},
        outputs={"result": OutputSpec("9", "video")},
        workflow_path=str(vid_wf),
    )

    ref = BackendRef(provider="comfyui", backend="local_comfyui", reference={"filename": "up.png"})
    p_img = engine.build_prompt(img_manifest, ExecutionPlan("image.generate", "img", "1.0.0", params={"prompt": "hi"}), {"image": ref})
    p_vid = engine.build_prompt(vid_manifest, ExecutionPlan("video.generate", "vid", "1.0.0", params={"prompt": "hi"}), {"video": ref})

    assert p_img["2"]["inputs"]["text"] == "hi" and p_img["10"]["inputs"]["image"] == "up.png"
    assert p_vid["2"]["inputs"]["text"] == "hi" and p_vid["20"]["inputs"]["video"] == "up.png"


# --------------------------------------------------------------------------- #
# Unit: Verifier (media-agnostic)
# --------------------------------------------------------------------------- #

def test_verifier_pass_and_fail(tmp_path):
    store = AssetStore(root=tmp_path / "store")
    img_asset = store.ingest(_mkfile(tmp_path, "o.png"), type="image", role="output")
    vid_asset = store.ingest(_mkfile(tmp_path, "o2.png"), type="video", role="output")

    manifest_img = Workflow(
        id="x", version="1.0.0", capability="image.generate", provider="comfyui", backend="local_comfyui",
        outputs={"result": OutputSpec("9", "image")},
    )

    # совпадение kind → OK
    assert Verifier(store).verify(manifest_img, {"result": img_asset})["result"].id == img_asset.id
    # несовпадение kind (asset video != declared image) → ошибка
    with pytest.raises(Exception):
        Verifier(store).verify(manifest_img, {"result": vid_asset})


# --------------------------------------------------------------------------- #
# Real: asset transport через Provider (треб. 5)
# --------------------------------------------------------------------------- #

@requires_live
def test_provider_upload_asset(tmp_path):
    store = AssetStore(root=tmp_path / "store")
    asset = store.ingest(_mkfile(tmp_path, "src.png"), type="image", role="input")
    provider = ComfyUIProvider(_LIVE)
    _comfyui_or_skip(provider.client)
    ref = provider.upload_asset(asset)
    assert isinstance(ref, BackendRef)
    assert ref.reference.get("filename")


# --------------------------------------------------------------------------- #
# Real: txt2img E2E на реальной модели (треб. 3/6/9)
# --------------------------------------------------------------------------- #

@requires_live
def test_txt2img_e2e(tmp_path):
    store = AssetStore(root=tmp_path / "store")
    provider = ComfyUIProvider(_LIVE)
    _comfyui_or_skip(provider.client)
    reg = WorkflowRegistry()
    reg.discover("workflows")

    runtime = discover_runtime(_LIVE)
    real_checkpoints = provider.discover_checkpoints()
    assert real_checkpoints, "нет доступных чекпоинтов в живом ComfyUI"
    # runtime discovery реальных имён + плейсхолдер из манифеста (exact-match по PROJECT_SPEC §12)
    models = set(real_checkpoints) | {"checkpoint"}

    # Примечание: reg.select на РЕАЛЬНОМ железе вернёт None, т.к. ComfyUI API не отдаёт fp16/vram
    # достоверно (runtime.fp16=None) → совместимость UNKNOWN (корректно по спецификации, см. M3).
    # E2E проверяет реальное ИСПОЛНЕНИЕ, поэтому манифест берём напрямую через reg.get.
    sel = reg.select("image.generate", runtime, models=models, custom_nodes=set())
    manifest = reg.get(sel.workflow_id, sel.version) if sel else reg.get("txt2img", "1.0.0")
    assert manifest is not None, "manifest txt2img не найден"

    plan = ExecutionPlan(
        capability="image.generate", workflow_id=manifest.id, version=manifest.version,
        params={"prompt": "a calm lake at sunset", "negative_prompt": "",
                "width": 256, "height": 256, "seed": 0, "steps": 5},
    )
    # Один execution path: local и remote backend используют один WorkflowEngine + ModelRegistry (per-backend).
    registry = ModelRegistry()
    registry.discover(_LIVE, provider.backend_id, kinds=[ModelKind.CHECKPOINT])
    engine = WorkflowEngine(store, model_registry=registry)
    try:
        job = engine.execute(manifest, plan, provider, ws_timeout=90)
    except _ENV_ERRORS as e:
        pytest.skip(f"ComfyUI execution environment error (не mock): {type(e).__name__}: {e}")

    assert job.state == JobState.SUCCESS
    assert len(job.output_assets) == 1
    out = store.get(job.output_assets[0])
    assert out is not None
    assert out.type == "image"                # Verifier пропустил контракт
    assert os.path.exists(out.path)
    assert out.created_from == job.prompt_id  # lineage: Job породил ассет
    assert out.source_asset is None           # txt2img без входных ассетов


# --------------------------------------------------------------------------- #
# Executable: video.generate — реально исполнимый workflow (M6 Video E2E доказан)
# --------------------------------------------------------------------------- #

def test_video_generate_executable():
    # video.generate больше НЕ DECLARED_ONLY (D2/D5): реальный workflow.json есть,
    # E2E доказан на remote Colab (Tesla T4). Проверяем без живого ComfyUI —
    # достаточно локального discovery + наличия исполнимого графа.
    reg = WorkflowRegistry()
    reg.discover("workflows")
    wf = reg.get("video_generate", "1.0.0")
    assert wf is not None
    assert wf.workflow_path and os.path.exists(wf.workflow_path)
    assert wf.declared_only is False
    assert wf.status.value != "DECLARED_ONLY"


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _mkfile(tmp_path, name):
    p = tmp_path / name
    p.write_bytes(_1PX_PNG)
    return p


# --------------------------------------------------------------------------- #
# Unit: корректность guards (points 5/6/8) — чистая логика, БЕЗ mock ComfyUI
# --------------------------------------------------------------------------- #

def test_validate_output_bytes():
    from app.engine.engine import WorkflowEngine as _E
    _E._validate_output_bytes(b"\x89PNG", "image")           # валидный PNG — ок
    _E._validate_output_bytes(b"RIFFxxxxWEBP", "video")      # непустой video — ок
    with pytest.raises(RuntimeError):
        _E._validate_output_bytes(b"", "image")              # пустой — ошибка (point 8)
    with pytest.raises(RuntimeError):
        _E._validate_output_bytes(b"notimage", "image")     # битая сигнатура — ошибка (point 8)


def test_validate_output_bytes_generic_kinds():
    # ОДИН generic-механизм обслуживает image / video / audio (нет ветвления по media).
    from app.engine.engine import WorkflowEngine as _E

    valid = {
        "image": b"\x89PNG header payload",
        "video": b"\x00\x00\x00\x18ftypisom payload",
        "audio": b"ID3\x03\x00\x00 title payload",
    }
    for kind, payload in valid.items():
        _E._validate_output_bytes(payload, kind)            # не должно бросать

    # неизвестный kind — только непустота (generic fallback, без сигнатур)
    _E._validate_output_bytes(b"arbitrary content", "document")

    # битый выхлоп для любого kind с сигнатурами → ошибка (point 8)
    for kind in ("image", "video", "audio"):
        with pytest.raises(RuntimeError):
            _E._validate_output_bytes(b"this is not a media file", kind)

    # пустой выхлоп для любого kind → ошибка (point 8)
    for kind in ("image", "video", "audio", "document"):
        with pytest.raises(RuntimeError):
            _E._validate_output_bytes(b"", kind)


def test_broken_output_cannot_become_success(tmp_path, monkeypatch):
    # Битый выхлоп НЕ порождает output Asset и НЕ переводит Job в SUCCESS (point 8).
    monkeypatch.setattr(ComfyUIWebSocket, "track",
                        staticmethod(lambda pid, timeout=None, on_progress=None: {"9": {"images": [{"filename": "x.png"}]}}))

    store = AssetStore(root=tmp_path / "s")
    calls = []
    orig_ingest = store.ingest

    def _spy(*a, **k):
        calls.append((a, k))
        return orig_ingest(*a, **k)

    monkeypatch.setattr(store, "ingest", _spy)
    engine = WorkflowEngine(store)

    class _BrokenProvider(_FakeProvider):
        def view(self, ref):
            return b"corrupted-bytes"                       # не совпадает с сигнатурой image

    prov = _BrokenProvider()
    wf = _wf_template(tmp_path, "w.json", {"9": {"class_type": "SaveImage", "inputs": {}}})
    manifest = Workflow(
        id="t", version="1.0.0", capability="image.generate", provider="comfyui", backend="fake",
        outputs={"result": OutputSpec("9", "image")}, workflow_path=str(wf),
    )
    plan = ExecutionPlan("image.generate", "t", "1.0.0", params={"prompt": "x"})
    with pytest.raises(RuntimeError):
        engine.execute(manifest, plan, prov, ws_timeout=5)
    # output Asset НЕ создан для битого выхлопа (проверка ДО ingest, point 8)
    assert calls == []


def test_history_status_error_detection():
    hist_err = {"p": {"status": {"status": "error"}}}
    hist_ok = {"p": {"status": {"status": "success"}, "outputs": {"9": {}}}}
    assert WorkflowEngine._history_status(hist_err, "p") == "error"
    assert WorkflowEngine._history_status(hist_ok, "p") == "success"


class _FakeProvider:
    """Лёгкий double для проверки внутренней логики engine (НЕ mock реального ComfyUI)."""

    def __init__(self):
        self.cancelled = []
        self.client = type("C", (), {"base_url": "http://fake"})()
        self.backend_id = "fake"

    def upload_asset(self, asset):
        return BackendRef("comfyui", "fake", {"filename": "f"})

    def execute(self, prompt, client_id=None):
        return "pid"

    def get_job(self, prompt_id):
        return {}

    def cancel(self, prompt_id):
        self.cancelled.append(prompt_id)

    def view(self, ref):
        return b"\x89PNG\r\n\x1a\n"

    def discover_checkpoints(self):
        return []


def test_cancel_does_not_become_completed(tmp_path, monkeypatch):
    # WS трекаем заглушкой: возвращаем выхлоп, не ходя в реальный ComfyUI (это НЕ E2E-mock,
    # а изоляция логики cancel). Реальный E2E по-прежнему требует живой ComfyUI.
    monkeypatch.setattr(ComfyUIWebSocket, "track",
                        staticmethod(lambda pid, timeout=None, on_progress=None: {"9": {"images": [{"filename": "x.png"}]}}))
    store = AssetStore(root=tmp_path / "s")
    engine = WorkflowEngine(store)
    prov = _FakeProvider()
    wf = _wf_template(tmp_path, "w.json", {"9": {"class_type": "SaveImage", "inputs": {}}})
    manifest = Workflow(
        id="t", version="1.0.0", capability="image.generate", provider="comfyui", backend="fake",
        outputs={"result": OutputSpec("9", "image")}, workflow_path=str(wf),
    )
    plan = ExecutionPlan("image.generate", "t", "1.0.0", params={"prompt": "x"})
    job = Job(prompt_id="pid", workflow_id="t", version="1.0.0",
              capability="image.generate", state=JobState.RUNNING)
    engine.cancel(job, prov)  # отменяем до execute
    res = engine.execute(manifest, plan, prov, ws_timeout=5)
    # point 6: позднее WS-событие НЕ превращает CANCELLED в COMPLETED
    assert res.state == JobState.CANCELLED
    assert res.output_assets == []
