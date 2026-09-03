"""image.upscale workflow — увеличение разрешения изображения.

Закрывает gap: capability `image.upscale` зарегистрирована, но workflow не существовал.
Workflow: LoadImage → ImageScale (lanczos) → SaveImage. Без custom nodes, без checkpoint.

Контракты (SAFE CHANGE): тот же WorkflowEngine/Job/Verifier/Asset. Media-agnostic.
Без mock: real-E2E требует живой ComfyUI (COMFY_REMOTE_URL), иначе skip.
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
from app.registry.runtime import RuntimeInfo
from app.registry.workflow import UnavailableReason, WorkflowStatus

_1PX_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
)

COMFY_REMOTE_URL = os.environ.get("COMFY_REMOTE_URL")


# --------------------------------------------------------------------------- #
# 1) manifest декларативно описывает asset_inputs
# --------------------------------------------------------------------------- #

def test_upscale_manifest_declares_asset_inputs():
    reg = WorkflowRegistry()
    reg.discover("workflows")
    wf = reg.get("upscale", "1.0.0")
    assert wf is not None, "workflow upscale не найден"
    assert wf.status.value != "DECLARED_ONLY", "upscale должен быть исполнимым"
    assert wf.status.value in ("VALIDATED", "AVAILABLE")

    assert "image" in wf.asset_inputs, "asset_inputs.image отсутствует"
    ain = wf.asset_inputs["image"]
    assert ain.kind == "image"
    assert ain.node and ain.field
    assert wf.capability == "image.upscale"
    assert wf.workflow_path and os.path.exists(wf.workflow_path)


# --------------------------------------------------------------------------- #
# 2)/3) image Asset совместим; video Asset НЕ совместим (AD-23)
# --------------------------------------------------------------------------- #

def test_upscale_input_compatibility(tmp_path):
    reg = WorkflowRegistry()
    reg.discover("workflows")
    wf = reg.get("upscale", "1.0.0")

    store = AssetStore(root=tmp_path)
    img_file = tmp_path / "in.png"
    img_file.write_bytes(_1PX_PNG)
    vid_file = tmp_path / "in.mp4"
    vid_file.write_bytes(b"ftypmp4box")

    img_asset = store.ingest(img_file, type="image", role="input")
    vid_asset = store.ingest(vid_file, type="video", role="input")

    runtime = RuntimeInfo(
        accelerator="cpu", vram_gb=24.0, fp16=True,
        xformers=False, lowvram=False, comfyui_version="0.0.0",
    )
    models = set()
    custom_nodes = set(wf.required_custom_nodes)

    status_img, reasons_img = evaluate_compatibility(
        wf, runtime, models=models, custom_nodes=custom_nodes, assets=[img_asset])
    assert status_img == WorkflowStatus.AVAILABLE, reasons_img

    status_vid, reasons_vid = evaluate_compatibility(
        wf, runtime, models=models, custom_nodes=custom_nodes, assets=[vid_asset])
    assert status_vid == WorkflowStatus.UNAVAILABLE
    assert UnavailableReason.INPUT_INCOMPATIBLE in reasons_vid


# --------------------------------------------------------------------------- #
# 4) asset binding формируется декларативно (через manifest)
# --------------------------------------------------------------------------- #

def test_upscale_binding_declarative(tmp_path):
    reg = WorkflowRegistry()
    reg.discover("workflows")
    wf = reg.get("upscale", "1.0.0")
    engine = WorkflowEngine(AssetStore(root=tmp_path / "store"))

    ref = BackendRef("comfyui", "local_comfyui", {"filename": "in.png"})
    plan = ExecutionPlan("image.upscale", "upscale", "1.0.0", params={"width": 2048, "height": 2048})
    prompt = engine.build_prompt(wf, plan, {"image": ref})

    bind = wf.asset_inputs["image"]
    assert prompt[str(bind.node)]["inputs"][bind.field] == "in.png"
    assert prompt["10"]["inputs"]["image"] == "in.png"
    # ImageScale получил width/height из params
    assert prompt["20"]["inputs"]["width"] == 2048
    assert prompt["20"]["inputs"]["height"] == 2048


# --------------------------------------------------------------------------- #
# 5) lineage: input Asset A → upscale Job → output Asset B
# --------------------------------------------------------------------------- #

def test_upscale_lineage_offline(tmp_path, monkeypatch):
    monkeypatch.setattr(
        ComfyUIWebSocket, "track",
        staticmethod(lambda pid, timeout=None, on_progress=None: {"30": {"images": [{"filename": "up.png"}]}}),
    )

    store = AssetStore(root=tmp_path / "store")
    in_file = tmp_path / "in.png"
    in_file.write_bytes(_1PX_PNG)
    input_asset = store.ingest(in_file, type="image", role="input")

    reg = WorkflowRegistry()
    reg.discover("workflows")
    wf = reg.get("upscale", "1.0.0")
    engine = WorkflowEngine(store)

    plan = ExecutionPlan(
        capability="image.upscale", workflow_id="upscale", version="1.0.0",
        params={"width": 2048, "height": 2048},
        asset_bindings={"image": input_asset.id},
    )
    job = engine.execute(wf, plan, _FakeProvider(), ws_timeout=5)

    assert job.state == JobState.SUCCESS
    assert len(job.output_assets) == 1
    out = store.get(job.output_assets[0])
    assert out is not None
    assert out.type == "image"
    assert out.source_asset == input_asset.id
    assert out.created_from == job.prompt_id
    assert store.lineage(out.id) == [out, input_asset]


# --------------------------------------------------------------------------- #
# 6) no required_models — checkpoint НЕ нужен
# --------------------------------------------------------------------------- #

def test_upscale_no_checkpoint_required():
    reg = WorkflowRegistry()
    reg.discover("workflows")
    wf = reg.get("upscale", "1.0.0")
    assert wf.required_models == [], "upscale не должен требовать checkpoint"


# --------------------------------------------------------------------------- #
# 7) реальный upscale E2E (требует живой ComfyUI; без backend — skip)
# --------------------------------------------------------------------------- #

@pytest.mark.skipif(
    not COMFY_REMOTE_URL,
    reason="COMFY_REMOTE_URL не задан — нет remote ComfyUI с ImageScale (без mock не проверяем).",
)
def test_upscale_e2e_remote(tmp_path):
    from app.comfy.client import ComfyClient

    client = ComfyClient(base_url=COMFY_REMOTE_URL, timeout=120)
    try:
        client.get_system_stats()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"remote ComfyUI недоступен: {e}")

    backend_id = "remote_comfyui"
    provider = ComfyUIProvider(client, backend_id=backend_id)

    reg = WorkflowRegistry()
    reg.discover("workflows")
    wf = reg.get("upscale", "1.0.0")
    assert wf is not None
    assert wf.status.value in ("VALIDATED", "AVAILABLE")

    store = AssetStore(root=tmp_path)
    in_file = tmp_path / "in.png"
    in_file.write_bytes(_1PX_PNG)
    input_asset = store.ingest(in_file, type="image", role="input")

    engine = WorkflowEngine(store)
    plan = ExecutionPlan(
        capability="image.upscale", workflow_id="upscale", version="1.0.0",
        params={"width": 2048, "height": 2048},
        asset_bindings={"image": input_asset.id},
    )
    job = engine.execute(wf, plan, provider=provider, ws_timeout=240)
    assert job.state == JobState.SUCCESS
    assert len(job.output_assets) == 1
    out = store.get(job.output_assets[0])
    assert out is not None
    assert out.type == "image"
    assert out.source_asset == input_asset.id
    with open(out.path, "rb") as fh:
        head = fh.read(8)
    assert head.startswith(b"\x89PNG"), "upscale должен вернуть PNG"


class _FakeProvider:
    """Лёгкий double для offline проверки lineage и build_prompt."""

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
