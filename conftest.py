import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

# Force pytest tmpdir to a writable location (DSH sandbox may block default temp)
import pytest

def pytest_configure(config):
    """Ensure tmp_path uses a writable directory."""
    # Use project-local tmp dir to avoid sandbox permission issues
    tmpdir = os.path.join(os.path.dirname(__file__), "__tmp_pytest")
    os.makedirs(tmpdir, exist_ok=True)
    config.option.tmp_path_factory = None  # disable default, we override via env
    os.environ["PYTEST_TMPDIR"] = tmpdir
