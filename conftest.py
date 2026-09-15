import os
import socket
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))

# test_m11_verification.py — это ручной verification-скрипт (запуск: python tests/test_m11_verification.py),
# НЕ pytest-тест: исполняет код верхнего уровня при import и требует живого registry/ComfyUI.
# Исключаем из pytest-сбора, чтобы collection не падал (HANDOFF 2026-09-14, pre-existing failure).
collect_ignore_glob = ["tests/test_m11_verification.py"]

# Тесты, требующие ЖИВОГО ComfyUI (127.0.0.1:8188). В CI (ubuntu, без ComfyUI)
# они обязаны корректно SKIP, а не падать с ConnectionRefused.
# Механизм: pytest_collection_modifyitems + live socket-проба.
# Если ComfyUI доступен — тесты исполняются как раньше (никакого поведения не меняем).

REAL_E2E_MODULES = (
    "test_http_external_e2e",
    "test_http_request_e2e",
    "test_http_request_real_e2e",
    "test_knowledge_s4_full_e2e",
    "test_knowledge_s4_real_e2e",
    "test_m18_e2e_real",
    "test_m19_e2e_real",
    "test_m21_real_e2e",
)

COMFYUI_URL = "http://127.0.0.1:8188"


def _comfyui_alive(host: str = "127.0.0.1", port: int = 8188, timeout: float = 1.0) -> bool:
    # AGENT_E2E_FORCE_OFFLINE=1 — принудительный offline-режим (эмуляция CI,
    # отладка skip-механизма без остановки локального ComfyUI).
    if os.environ.get("AGENT_E2E_FORCE_OFFLINE") == "1":
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def pytest_collection_modifyitems(config, items):
    if not any(item.module.__name__.rsplit(".", 1)[-1] in REAL_E2E_MODULES for item in items):
        return
    if _comfyui_alive():
        return
    skip_marker = pytest.mark.skip(
        reason=f"Real-E2E: ComfyUI недоступен на {COMFYUI_URL} "
               f"(запустите ComfyUI или прогоните локально; CI skip)"
    )
    for item in items:
        if item.module.__name__.rsplit(".", 1)[-1] in REAL_E2E_MODULES:
            item.add_marker(skip_marker)


# Force pytest tmpdir to a writable location (DSH sandbox may block default temp)
def pytest_configure(config):
    """Ensure tmp_path uses a writable directory."""
    # Use project-local tmp dir to avoid sandbox permission issues
    tmpdir = os.path.join(os.path.dirname(__file__), "__tmp_pytest")
    os.makedirs(tmpdir, exist_ok=True)
    config.option.tmp_path_factory = None  # disable default, we override via env
    os.environ["PYTEST_TMPDIR"] = tmpdir
