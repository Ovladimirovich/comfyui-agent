"""BackendCatalog (inv 12) — offline-выбор ExecutionBackend для Agent."""
from __future__ import annotations

import os

from app.registry.backends import BackendCatalog, BackendSpec


def test_choose_highest_priority():
    cat = BackendCatalog([
        BackendSpec("a", "http://a", priority=1),
        BackendSpec("b", "http://b", priority=5),
    ])
    assert cat.choose("image.generate").backend_id == "b"


def test_choose_capability_filter():
    cat = BackendCatalog([
        BackendSpec("a", "http://a", priority=10, capabilities={"image.generate"}),
        BackendSpec("b", "http://b", priority=1, capabilities={"video.generate"}),
    ])
    assert cat.choose("video.generate").backend_id == "b"
    assert cat.choose("image.generate").backend_id == "a"


def test_choose_disabled_excluded():
    cat = BackendCatalog([
        BackendSpec("a", "http://a", priority=10, disabled=True),
        BackendSpec("b", "http://b", priority=1),
    ])
    assert cat.choose("image.generate").backend_id == "b"


def test_choose_none_when_no_eligible():
    cat = BackendCatalog([
        BackendSpec("a", "http://a", priority=10, capabilities={"image.generate"}),
    ])
    assert cat.choose("audio.generate") is None


def test_from_env_single():
    os.environ["COMFY_REMOTE_URL"] = "http://gpu:8188"
    try:
        cat = BackendCatalog.from_env()
        assert cat.backends[0].backend_id == "remote_comfyui"
        assert cat.backends[0].base_url == "http://gpu:8188"
    finally:
        del os.environ["COMFY_REMOTE_URL"]
