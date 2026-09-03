"""Audio E2E (M7) — реальный audio.generate на remote Colab через тот же execution path.

Сценарий (установка M7):
    Capability (audio.generate)
        → WorkflowRegistry (discover, обычный Workflow, не DECLARED_ONLY)
        → ExecutionPlan
        → Provider (comfyui, remote_comfyui)
        → Colab ComfyUI (Tesla T4)
        → Job
        → Verifier (kind=audio)
        → local AssetStore (Windows)

Без mock: требует COMFY_REMOTE_URL (Colab с SoniloTextToMusic + SaveAudio).
Никаких AudioEngine/AudioProvider/AudioJob — тот же WorkflowEngine/Job/Verifier/Asset, что у image/video.
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
    reason="COMFY_REMOTE_URL не задан — нет remote ComfyUI с audio-нодами (без mock не проверяем).",
)
def test_audio_e2e_remote(tmp_path):
    client = ComfyClient(base_url=COMFY_REMOTE_URL, timeout=90)
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
    audio_wfs = reg.by_capability("audio.generate")
    assert audio_wfs, "capability audio.generate не обнаружен в registry"
    aw = reg.get("audio_generate", "1.0.0")
    assert aw is not None, "audio_generate 1.0.0 не найден"
    assert aw.status.value != "DECLARED_ONLY", "audio_generate не должен быть DECLARED_ONLY после M7"
    assert aw.status.value in ("VALIDATED", "AVAILABLE")
    # M7: граф собирает аудио узлами SoniloTextToMusic + SaveAudio (тот же media-agnostic engine).
    assert "SoniloTextToMusic" in aw.required_custom_nodes and "SaveAudio" in aw.required_custom_nodes

    runtime: RuntimeInfo = discover_runtime(client)
    models = set(registry.models_for(backend_id)) | {"checkpoint"}
    custom_nodes = set(aw.required_custom_nodes)
    sel = reg.select("audio.generate", runtime, models=models, custom_nodes=custom_nodes)
    manifest = reg.get(sel.workflow_id, sel.version) if sel else aw

    store = AssetStore(root=tmp_path)
    engine = WorkflowEngine(store, model_registry=registry)
    plan = ExecutionPlan(
        capability="audio.generate", workflow_id=manifest.id, version=manifest.version,
        params={
            "prompt": "a calm lo-fi beat with gentle piano",
            "duration": 8.0,
            "seed": 0,
        },
    )

    job = engine.execute(manifest, plan, provider=provider, ws_timeout=240)
    assert job.prompt_id, "remote ComfyUI не вернул prompt_id"
    assert job.state == JobState.SUCCESS
    assert len(job.output_assets) == 1

    out = store.get(job.output_assets[0])
    assert out is not None
    assert out.type == "audio"                 # Verifier пропустил контракт kind=audio
    assert os.path.exists(out.path)
    assert str(tmp_path) in out.path           # output — в локальном Windows AssetStore, не на remote ФС
    assert out.created_from == job.prompt_id
    assert out.source_asset is None

    # WAV-контейнер: реальный аудио-файл (SoniloTextToMusic + SaveAudio пишут .wav).
    with open(out.path, "rb") as fh:
        head = fh.read(12)
    assert head[:4] == b"RIFF" and head[8:12] == b"WAVE", "audio.generate должен вернуть реальный WAV, получено: %r" % head
