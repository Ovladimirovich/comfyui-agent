"""M6.5 — Image Input / img2img (image.edit).

Закрывает функциональный gap `img2img / image.edit`, чтобы M7 Conversation Context можно было
доказать реальным chain-сценарием (Asset -> image input -> workflow -> новый Asset -> lineage).

Контракты (без изменения архитектуры):
    Asset / AssetStore / asset_inputs / WorkflowRegistry / Capability / ExecutionPlan /
    WorkflowEngine / Provider / BackendRef / Job / Verifier / lineage.

Никаких ImageEngine / ImageAsset / media-ветвления в execution core.
Без mock: E2E требует живой ComfyUI (COMFY_REMOTE_URL), иначе skip.
"""
from __future__ import annotations

import base64
import os

import pytest

from app.assets import AssetStore
from app.engine import ExecutionPlan, JobState, WorkflowEngine
from app.engine.websocket import ComfyUIWebSocket
from app.provider import BackendRef, ComfyUIProvider
from app.registry import WorkflowRegistry
from app.registry.compatibility import evaluate_compatibility
from app.registry.model import ModelKind, ModelRegistry
from app.registry.runtime import RuntimeInfo, discover_runtime
from app.registry.workflow import UnavailableReason, WorkflowStatus

_1PX_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
)

COMFY_REMOTE_URL = os.environ.get("COMFY_REMOTE_URL")


def _make_test_png(width: int = 64, height: int = 64) -> bytes:
    """Генерирует минимальный solid-color PNG. 64x64 безопасен для VAEEncode."""
    import struct, zlib
    def _chunk(ctype: bytes, data: bytes) -> bytes:
        c = ctype + data
        crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + c + crc
    header = b"\x89PNG\r\n\x1a\n"
    ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    raw = b"".join(b"\x00" + b"\x80\x80\x80" * width for _ in range(height))
    idat = _chunk(b"IDAT", zlib.compress(raw))
    return header + ihdr + idat + _chunk(b"IEND", b"")

SMALL_PNG = _make_test_png(64, 64)


# --------------------------------------------------------------------------- #
# 1) manifest декларативно описывает asset_inputs
# --------------------------------------------------------------------------- #

def test_img2img_manifest_declares_asset_inputs():
    reg = WorkflowRegistry()
    reg.discover("workflows")
    wf = reg.get("img2img", "1.0.0")
    assert wf is not None, "workflow img2img не найден"
    assert wf.status.value != "DECLARED_ONLY", "img2img должен быть исполнимым (не DECLARED_ONLY)"
    assert wf.status.value in ("VALIDATED", "AVAILABLE")

    # декларативная связь Asset -> ComfyUI input через manifest
    assert "image" in wf.asset_inputs, "asset_inputs.image отсутствует в манифесте"
    ain = wf.asset_inputs["image"]
    assert ain.kind == "image"
    assert ain.node and ain.field
    # capability согласован с AD-23 (media_input=("image",))
    assert wf.capability == "image.edit"
    # граф реально содержит узел LoadImage по декларированному node
    assert wf.workflow_path and os.path.exists(wf.workflow_path)


# --------------------------------------------------------------------------- #
# 2)/3) image Asset совместим; video Asset НЕ совместим (AD-23, без обработки медиа)
# --------------------------------------------------------------------------- #

def test_img2img_input_compatibility(tmp_path):
    reg = WorkflowRegistry()
    reg.discover("workflows")
    wf = reg.get("img2img", "1.0.0")

    store = AssetStore(root=tmp_path)
    img_file = tmp_path / "in.png"
    img_file.write_bytes(_1PX_PNG)
    vid_file = tmp_path / "in.mp4"
    vid_file.write_bytes(b"ftypmp4box")  # video-сигнатура, неважно для compat

    img_asset = store.ingest(img_file, type="image", role="input")
    vid_asset = store.ingest(vid_file, type="video", role="input")

    # runtime с известными значениями, чтобы не уйти в UNKNOWN (проверяем только input contract)
    runtime = RuntimeInfo(
        accelerator="cpu", vram_gb=24.0, fp16=True,
        xformers=False, lowvram=False, comfyui_version="0.0.0",
    )
    models = {"checkpoint"}
    custom_nodes = set(wf.required_custom_nodes)

    status_img, reasons_img = evaluate_compatibility(
        wf, runtime, models=models, custom_nodes=custom_nodes, assets=[img_asset])
    assert status_img == WorkflowStatus.AVAILABLE, reasons_img

    status_vid, reasons_vid = evaluate_compatibility(
        wf, runtime, models=models, custom_nodes=custom_nodes, assets=[vid_asset])
    assert status_vid == WorkflowStatus.UNAVAILABLE
    assert UnavailableReason.INPUT_INCOMPATIBLE in reasons_vid


# --------------------------------------------------------------------------- #
# 4) asset binding формируется декларативно (через manifest, не хардкод в engine)
# --------------------------------------------------------------------------- #

def test_img2img_binding_declarative(tmp_path):
    reg = WorkflowRegistry()
    reg.discover("workflows")
    wf = reg.get("img2img", "1.0.0")
    engine = WorkflowEngine(AssetStore(root=tmp_path / "store"))

    ref = BackendRef("comfyui", "local_comfyui", {"filename": "in.png"})
    plan = ExecutionPlan("image.edit", "img2img", "1.0.0", params={"prompt": "x"})
    prompt = engine.build_prompt(wf, plan, {"image": ref})

    # привязка взята из manifest.asset_inputs, а не из константы engine
    bind = wf.asset_inputs["image"]
    assert prompt[str(bind.node)]["inputs"][bind.field] == "in.png"
    assert prompt["10"]["inputs"]["image"] == "in.png"


# --------------------------------------------------------------------------- #
# 5) lineage сохраняется (input Asset A -> img2img Job -> output Asset B)
# --------------------------------------------------------------------------- #

def test_img2img_lineage_offline(tmp_path, monkeypatch):
    # изоляция логики lineage: WS-трек заглушён, реальный ComfyUI не нужен.
    monkeypatch.setattr(
        ComfyUIWebSocket, "track",
        staticmethod(lambda pid, timeout=None, on_progress=None: {"9": {"images": [{"filename": "x.png"}]}}),
    )

    store = AssetStore(root=tmp_path / "store")
    in_file = tmp_path / "in.png"
    in_file.write_bytes(_1PX_PNG)
    input_asset = store.ingest(in_file, type="image", role="input")

    reg = WorkflowRegistry()
    reg.discover("workflows")
    wf = reg.get("img2img", "1.0.0")
    engine = WorkflowEngine(store)

    plan = ExecutionPlan(
        capability="image.edit", workflow_id="img2img", version="1.0.0",
        params={"prompt": "make it blue", "negative_prompt": "", "seed": 0, "steps": 20, "denoise": 0.6},
        asset_bindings={"image": input_asset.id},
    )
    job = engine.execute(wf, plan, _FakeProvider(), ws_timeout=5)

    assert job.state == JobState.SUCCESS
    assert len(job.output_assets) == 1
    out = store.get(job.output_assets[0])
    assert out is not None
    assert out.type == "image"
    # lineage: B.source_asset == A
    assert out.source_asset == input_asset.id
    assert out.created_from == job.prompt_id
    assert store.lineage(out.id) == [out, input_asset]


# --------------------------------------------------------------------------- #
# 6) реальный img2img E2E (требует живой ComfyUI; без backend — skip, не fake)
# --------------------------------------------------------------------------- #

@pytest.mark.skipif(
    not COMFY_REMOTE_URL,
    reason="COMFY_REMOTE_URL не задан — нет remote ComfyUI с LoadImage/VAEEncode (без mock не проверяем).",
)
def test_img2img_e2e_remote(tmp_path):
    from app.comfy.client import ComfyClient

    client = ComfyClient(base_url=COMFY_REMOTE_URL, timeout=120)
    try:
        client.get_system_stats()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"remote ComfyUI недоступен: {e}")

    backend_id = "remote_comfyui"
    provider = ComfyUIProvider(client, backend_id=backend_id)

    registry = ModelRegistry()
    registry.discover(client, backend_id, kinds=[ModelKind.CHECKPOINT])

    reg = WorkflowRegistry()
    reg.discover("workflows")
    wf = reg.get("img2img", "1.0.0")
    assert wf is not None
    assert wf.status.value != "DECLARED_ONLY"
    assert wf.status.value in ("VALIDATED", "AVAILABLE")
    assert "checkpoint" in wf.required_models

    runtime: RuntimeInfo = discover_runtime(client)
    models = set(registry.models_for(backend_id)) | {"checkpoint"}
    custom_nodes = set(wf.required_custom_nodes)
    sel = reg.select("image.edit", runtime, models=models, custom_nodes=custom_nodes)
    manifest = reg.get(sel.workflow_id, sel.version) if sel else wf

    store = AssetStore(root=tmp_path)
    in_file = tmp_path / "in.png"
    in_file.write_bytes(SMALL_PNG)  # 64x64, safe for VAEEncode
    input_asset = store.ingest(in_file, type="image", role="input")

    engine = WorkflowEngine(store, model_registry=registry)
    plan = ExecutionPlan(
        capability="image.edit", workflow_id=manifest.id, version=manifest.version,
        params={
            "prompt": "turn the subject into a watercolor painting",
            "negative_prompt": "",
            "seed": 0, "steps": 20, "denoise": 0.6,
        },
        asset_bindings={"image": input_asset.id},
    )
    job = engine.execute(manifest, plan, provider=provider, ws_timeout=240)
    assert job.prompt_id, "remote ComfyUI не вернул prompt_id"
    assert job.state == JobState.SUCCESS
    assert len(job.output_assets) == 1

    out = store.get(job.output_assets[0])
    assert out is not None
    assert out.type == "image"                 # Verifier пропустил контракт kind=image
    assert os.path.exists(out.path)
    assert out.source_asset == input_asset.id  # lineage сохранён на реальном E2E
    assert out.created_from == job.prompt_id

    with open(out.path, "rb") as fh:
        head = fh.read(8)
    assert head.startswith(b"\x89PNG"), "img2img должен вернуть реальный PNG, получено: %r" % head


class _FakeProvider:
    """Лёгкий double для проверки внутренней логики engine (НЕ mock реального ComfyUI)."""

    def __init__(self):
        self.client = type("C", (), {"base_url": "http://fake"})()
        self.backend_id = "fake"

    def upload_asset(self, asset):
        return BackendRef("comfyui", "fake", {"filename": "f"})

    def execute(self, prompt, client_id=None):
        return "pid"

    def get_job(self, prompt_id):
        return {}

    def cancel(self, prompt_id):
        pass

    def view(self, ref):
        return b"\x89PNG\r\n\x1a\n"

    def discover_checkpoints(self):
        return []
