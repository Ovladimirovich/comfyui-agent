"""Real E2E — image.inpaint on local Comfy Desktop (127.0.0.1:8188).

Отдельный Real E2E suite (правило: НЕ в обычный regression). Требует живой
локальный ComfyUI. При недоступности — skip (НЕ mock). Критерий успеха:
workflow -> provider.execute -> WS/history -> Job SUCCESS -> Asset -> Verifier
-> существующий непустой валидный PNG, полученный от локального Comfy Desktop.
"""
from __future__ import annotations

import os
import tempfile

import pytest

from app.assets import AssetStore
from app.comfy.client import ComfyClient
from app.engine import ExecutionPlan, JobState, WorkflowEngine
from app.provider import ComfyUIProvider
from app.registry import WorkflowRegistry
from app.registry.model import ModelKind, ModelRegistry

from helpers import make_mask_png, make_png

BASE_URL = "http://127.0.0.1:8188"


def _live_provider():
    try:
        client = ComfyClient(base_url=BASE_URL, timeout=10)
        client.get_system_stats()
        provider = ComfyUIProvider(client, backend_id="local_comfyui")
        checkpoints = provider.discover_checkpoints()
        assert checkpoints, "нет чекпоинтов в локальном ComfyUI"
        return client, provider
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"локальный ComfyUI недоступен: {e}")


def test_inpaint_real_local_e2e(tmp_path):
    client, provider = _live_provider()

    store = AssetStore(root=tmp_path / "store")
    in_file = tmp_path / "in.png"
    in_file.write_bytes(make_png(64, 64))
    mask_file = tmp_path / "mask.png"
    mask_file.write_bytes(make_mask_png(64, 64))
    img_asset = store.ingest(in_file, type="image", role="input")
    mask_asset = store.ingest(mask_file, type="image", role="input")

    reg = WorkflowRegistry()
    reg.discover("workflows")
    wf = reg.get("image_inpaint", "1.0.0")
    assert wf is not None, "workflow image_inpaint не найден"
    assert wf.status.value != "DECLARED_ONLY"

    registry = ModelRegistry()
    registry.discover(client, provider.backend_id, kinds=[ModelKind.CHECKPOINT])

    engine = WorkflowEngine(store, model_registry=registry)
    plan = ExecutionPlan(
        capability="image.inpaint",
        workflow_id="image_inpaint",
        version="1.0.0",
        params={"prompt": "fill in the missing region naturally", "negative_prompt": "",
                "seed": 0, "steps": 5, "denoise": 0.95},
        asset_bindings={"image": img_asset.id, "mask": mask_asset.id},
    )
    job = engine.execute(wf, plan, provider=provider, ws_timeout=180)

    assert job.state == JobState.SUCCESS, job
    assert len(job.output_assets) == 1
    out = store.get(job.output_assets[0])
    assert out is not None
    assert out.type == "image"
    assert out.source_asset == img_asset.id
    assert out.created_from == job.prompt_id
    assert os.path.exists(out.path)
    assert os.path.getsize(out.path) > 0
    with open(out.path, "rb") as fh:
        head = fh.read(8)
    assert head.startswith(b"\x89PNG"), f"inpaint должен вернуть PNG: {head!r}"
