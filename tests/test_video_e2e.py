"""Video E2E (M6) — реальный video.generate на remote Colab через тот же execution path.

Сценарий (установка M6):
    Capability (video.generate)
        → WorkflowRegistry (discover, обычный Workflow, не DECLARED_ONLY)
        → ExecutionPlan
        → Provider (comfyui, remote_comfyui)
        → Colab ComfyUI (Tesla T4)
        → Job
        → Verifier (kind=video)
        → local AssetStore (Windows)

Без mock: требует COMFY_REMOTE_URL (Colab с VideoHelperSuite: CreateVideo/SaveVideo).
Никаких VideoEngine/VideoProvider/VideoJob — тот же WorkflowEngine/Job/Verifier/Asset, что у image.
"""
from __future__ import annotations

import os

import pytest

from app.assets.store import AssetStore
from app.comfy.client import ComfyClient
from app.engine import ExecutionPlan, JobState, WorkflowEngine
from app.provider.comfyui import ComfyUIProvider
from app.registry.model import ModelKind, ModelRegistry
from app.registry.registry import WorkflowRegistry
from app.registry.runtime import RuntimeInfo, discover_runtime

COMFY_REMOTE_URL = os.environ.get("COMFY_REMOTE_URL")


@pytest.mark.skipif(
    not COMFY_REMOTE_URL,
    reason="COMFY_REMOTE_URL не задан — нет remote ComfyUI с видео-нодами (без mock не проверяем).",
)
def test_video_e2e_remote(tmp_path):
    client = ComfyClient(base_url=COMFY_REMOTE_URL, timeout=90)
    try:
        client.get_system_stats()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"remote ComfyUI недоступен: {e}")

    backend_id = "remote_comfyui"
    provider = ComfyUIProvider(client, backend_id=backend_id)

    # Model Registry — per-backend discovery из реального ComfyUI
    registry = ModelRegistry()
    registry.discover(client, backend_id, kinds=[ModelKind.CHECKPOINT])

    # Workflow Registry — должен увидеть video_generate как ОБЫЧНЫЙ Workflow (не DECLARED_ONLY)
    reg = WorkflowRegistry()
    reg.discover("workflows")
    video_wfs = reg.by_capability("video.generate")
    assert video_wfs, "capability video.generate не обнаружен в registry"
    vw = reg.get("video_generate", "1.0.0")
    assert vw is not None, "video_generate 1.0.0 не найден"
    assert vw.status.value != "DECLARED_ONLY", "video_generate не должен быть DECLARED_ONLY после M6"
    assert vw.status.value in ("VALIDATED", "AVAILABLE")
    # required_models / required_custom_nodes заданы и проверяемы
    assert "checkpoint" in vw.required_models
    # M6 (final): граф собирает MP4 узлами CreateVideo + SaveVideo (VideoHelperSuite).
    # SaveVideo на Colab был сломан серверным багом DYNAMICCOMBO_V3 (execute() missing 'format');
    # исправлено на стороне окружения Colab: io.DynamicCombo.Input("format") -> io.Combo.Input
    # в /content/ComfyUI/comfy_extras/nodes_video.py (поле format стало plain COMBO). Ядро не менялось.
    assert "CreateVideo" in vw.required_custom_nodes and "SaveVideo" in vw.required_custom_nodes

    # runtime compatibility (честно, без глобальных допущений)
    runtime: RuntimeInfo = discover_runtime(client)
    models = set(registry.models_for(backend_id)) | {"checkpoint"}
    custom_nodes = set(vw.required_custom_nodes)
    sel = reg.select("video.generate", runtime, models=models, custom_nodes=custom_nodes)
    manifest = reg.get(sel.workflow_id, sel.version) if sel else vw

    store = AssetStore(root=tmp_path)
    engine = WorkflowEngine(store, model_registry=registry)
    plan = ExecutionPlan(
        capability="video.generate", workflow_id=manifest.id, version=manifest.version,
        params={
            "prompt": "a cat playing on a sunny windowsill, cinematic",
            "negative_prompt": "",
            "width": 512, "height": 512, "seed": 0, "steps": 20,
            "fps": 4, "frames": 4,
        },
    )

    job = engine.execute(manifest, plan, provider=provider, ws_timeout=240)
    assert job.prompt_id, "remote ComfyUI не вернул prompt_id"
    assert job.state == JobState.SUCCESS
    assert len(job.output_assets) == 1

    out = store.get(job.output_assets[0])
    assert out is not None
    assert out.type == "video"                 # Verifier пропустил контракт kind=video
    assert os.path.exists(out.path)
    assert str(tmp_path) in out.path           # output — в локальном Windows AssetStore, не на remote ФС
    # lineage (M2): Job породил ассет; t2v без входных ассетов
    assert out.created_from == job.prompt_id
    assert out.source_asset is None

    # MP4-контейнер: реальный файл, а не WEBM/PNG. MP4 начинается с бокса 'ftyp'.
    with open(out.path, "rb") as fh:
        head = fh.read(32)
    assert b"ftyp" in head, "video.generate должен вернуть реальный MP4 (ftyp-бокс), получено: %r" % head[:12]
