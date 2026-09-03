"""M1 integration test — реальный ComfyUI (127.0.0.1:8188), без mock.

Если ComfyUI не запущен, тесты завершаются понятным диагностическим skip,
а не превращают отсутствие backend в mock-success.
"""
import os

import pytest

from app.comfy.client import ComfyClient, ComfyClientError
from app.registry.runtime import RuntimeInfo, build_runtime_info, discover_runtime

BASE_URL = os.environ.get("COMFYUI_BASE_URL", "http://127.0.0.1:8188")


def _client() -> ComfyClient:
    return ComfyClient(base_url=BASE_URL)


def _stats_or_skip():
    client = _client()
    try:
        return client, client.get_system_stats()
    except ComfyClientError as e:
        pytest.skip(f"ComfyUI недоступен по {BASE_URL}: {e}")


def test_comfyui_reachable():
    client = _client()
    try:
        stats = client.get_system_stats()
    except ComfyClientError as e:
        pytest.skip(f"ComfyUI недоступен по {BASE_URL}: {e}")
    assert isinstance(stats, dict)


def test_system_stats():
    client, _ = _stats_or_skip()
    assert isinstance(client.get_system_stats(), dict)


def test_object_info():
    client, _ = _stats_or_skip()
    assert isinstance(client.get_object_info(), dict)


def test_queue():
    client, _ = _stats_or_skip()
    q = client.get_queue()
    assert "queue_running" in q and "queue_pending" in q


def test_history():
    client, _ = _stats_or_skip()
    assert isinstance(client.get_history(), dict)


def test_runtime_info_created():
    _, stats = _stats_or_skip()
    rt = build_runtime_info(stats)
    assert isinstance(rt, RuntimeInfo)
    if rt.accelerator is not None:
        assert isinstance(rt.accelerator, str) and len(rt.accelerator) > 0


def test_runtime_info_reflects_real():
    _, stats = _stats_or_skip()
    rt = build_runtime_info(stats)
    # Отражаем реальное состояние, а не предположения.
    if rt.vram_gb is not None:
        assert rt.vram_gb > 0
    # ComfyUI не отдаёт эти поля надёжно через API — UNKNOWN (None), не выдумываем.
    assert rt.fp16 is None
    assert rt.xformers is None
    assert rt.lowvram is None
    assert rt.comfyui_version is None


def test_discover_runtime():
    client, _ = _stats_or_skip()
    rt = discover_runtime(client)
    assert isinstance(rt, RuntimeInfo)
