"""Remote E2E (M5) — архитектурный proof-of-concept AD-29.

Сценарий (DoD, из установки M5):
    Agent host
        │ HTTP/WS
        ▼
    Provider (comfyui)
        │
        ▼
    ExecutionBackend (remote_comfyui)
        │
        ▼
    Remote ComfyUI
        │
        ▼
    Model (реальная модель на удалённой машине)
        │
        ▼
    Remote output
        │
        ▼
    Provider -> Verifier -> local AssetStore

Без mock: если COMFY_REMOTE_URL не задан или недоступен — тест ПРОПУСКАЕТСЯ (не подменяется фейком).
Локальный и удалённый ComfyUI проходят через ОДИН execution path (WorkflowEngine/Job/Asset).
video.generate остаётся DECLARED_ONLY (DEFERRED) — здесь не проверяется.
"""
from __future__ import annotations

import os

import pytest

from app.assets.store import AssetStore
from app.engine import ExecutionPlan, JobState, WorkflowEngine
from app.provider.comfyui import ComfyUIProvider
from app.registry.model import ModelKind, ModelRegistry
from app.registry.registry import WorkflowRegistry

COMFY_REMOTE_URL = os.environ.get("COMFY_REMOTE_URL")


@pytest.mark.skipif(
    not COMFY_REMOTE_URL,
    reason="COMFY_REMOTE_URL не задан — нет реального remote ComfyUI (без mock не проверяем).",
)
def test_remote_e2e_image_to_local_assetstore(tmp_path):
    """Реальный сквозной прогон: local Agent → Provider → remote ComfyUI → Model → output → local AssetStore."""
    from app.comfy.client import ComfyClient

    client = ComfyClient(base_url=COMFY_REMOTE_URL, timeout=60)
    # реальный backend должен быть доступен
    try:
        client.get_system_stats()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"remote ComfyUI недоступен: {e}")

    backend_id = "remote_comfyui"
    provider = ComfyUIProvider(client, backend_id=backend_id)

    # (2) Model Registry — per-backend discovery из РЕАЛЬНОГО ComfyUI (точные имена)
    registry = ModelRegistry()
    models = registry.discover(client, backend_id, kinds=[ModelKind.CHECKPOINT])
    assert models, "Model Registry не обнаружил ни одной checkpoint-модели на remote backend"
    # никаких глобальных предположений: имя точное, принадлежит конкретному backend
    assert all(m.backend_id == backend_id for m in models)

    # (3) Provider — граница; workflow выбран selection (здесь берём txt2img из registry)
    reg = WorkflowRegistry()
    reg.discover("workflows")
    manifest = reg.get("txt2img", "1.0.0")
    assert manifest is not None and manifest.status.value != "DECLARED_ONLY"

    store = AssetStore(root=tmp_path)
    # (1 execution path) локальный и удалённый backend — через один WorkflowEngine
    engine = WorkflowEngine(store, model_registry=registry)

    plan = ExecutionPlan(
        capability="image.generate", workflow_id=manifest.id, version=manifest.version,
        params={"prompt": "a cat on a windowsill", "negative_prompt": "",
                "width": 512, "height": 512, "seed": 0, "steps": 20},
    )

    job = engine.execute(manifest, plan, provider=provider, ws_timeout=120)
    assert job.prompt_id, "remote ComfyUI не вернул prompt_id"
    assert job.state == JobState.SUCCESS
    assert len(job.output_assets) == 1
    out = store.get(job.output_assets[0])
    assert out is not None
    assert out.type == "image"               # Verifier пропустил контракт
    assert os.path.exists(out.path)
    # output возвращается в ЛОКАЛЬНЫЙ AssetStore (agent host), не на remote ФС
    assert str(tmp_path) in out.path, "output должен лежать в локальном AssetStore, а не на remote ФС"
    # точное имя модели было забиндено (per-backend)
    assert registry.is_available(backend_id, registry.resolve(backend_id, "checkpoint"))
