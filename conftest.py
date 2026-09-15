import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

# test_m11_verification.py — это ручной verification-скрипт (запуск: python tests/test_m11_verification.py),
# НЕ pytest-тест: исполняет код верхнего уровня при import и требует живого registry/ComfyUI.
# Исключаем из pytest-сбора, чтобы collection не падал (HANDOFF 2026-09-14, pre-existing failure).
collect_ignore_glob = ["tests/test_m11_verification.py"]

# Force pytest tmpdir to a writable location (DSH sandbox may block default temp)
import pytest

def pytest_configure(config):
    """Ensure tmp_path uses a writable directory."""
    # Use project-local tmp dir to avoid sandbox permission issues
    tmpdir = os.path.join(os.path.dirname(__file__), "__tmp_pytest")
    os.makedirs(tmpdir, exist_ok=True)
    config.option.tmp_path_factory = None  # disable default, we override via env
    os.environ["PYTEST_TMPDIR"] = tmpdir
