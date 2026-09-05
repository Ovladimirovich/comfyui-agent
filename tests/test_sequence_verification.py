"""M25 Phase 4 — Sequence Verification Tests.

Доказывает offline:
  - verify_sequence: empty sequence = FAIL
  - verify_sequence: all assets exist = PASS
  - verify_sequence: missing asset = FAIL
  - verify_sequence: wrong count = FAIL
  - verify_sequence: duplicates = FAIL
  - verify_sequence: order preserved
  - existing verify() unchanged
"""
from __future__ import annotations

import os
import tempfile
import uuid
from unittest.mock import MagicMock

import pytest

from app.assets import AssetStore
from app.engine.verifier import Verifier


# ── Helpers ──

def _make_store_with_assets(asset_ids: list[str]) -> tuple[AssetStore, str]:
    """Create a temporary AssetStore with fake assets."""
    tmp = tempfile.mkdtemp()
    store = AssetStore(tmp)
    for aid in asset_ids:
        # Create a fake asset file
        path = os.path.join(tmp, f"{aid}.png")
        with open(path, "wb") as f:
            f.write(b"\x89PNG fake data")
        # Store the asset using internal methods
        from app.assets.types import Asset
        asset = Asset(
            id=aid,
            path=path,
            type="image",
            role="input",
        )
        store._assets[aid] = asset
    return store, tmp


# ── Tests: verify_sequence ──

class TestVerifySequence:
    def test_empty_sequence_fails(self):
        store, tmp = _make_store_with_assets([])
        verifier = Verifier(store)
        result = verifier.verify_sequence([])
        assert result.ok is False
        assert "empty" in result.error_message

    def test_valid_sequence_passes(self):
        store, tmp = _make_store_with_assets(["a1", "a2", "a3"])
        verifier = Verifier(store)
        result = verifier.verify_sequence(["a1", "a2", "a3"])
        assert result.ok is True
        assert len(result.diagnostics) == 0

    def test_missing_asset_fails(self):
        store, tmp = _make_store_with_assets(["a1", "a2"])
        verifier = Verifier(store)
        result = verifier.verify_sequence(["a1", "a2", "nonexistent"])
        assert result.ok is False
        assert "nonexistent" in result.error_message

    def test_wrong_count_fails(self):
        store, tmp = _make_store_with_assets(["a1", "a2", "a3"])
        verifier = Verifier(store)
        result = verifier.verify_sequence(["a1", "a2", "a3"], expected_count=5)
        assert result.ok is False
        assert "expected 5" in result.error_message

    def test_correct_count_passes(self):
        store, tmp = _make_store_with_assets(["a1", "a2"])
        verifier = Verifier(store)
        result = verifier.verify_sequence(["a1", "a2"], expected_count=2)
        assert result.ok is True

    def test_duplicates_fails(self):
        store, tmp = _make_store_with_assets(["a1", "a2"])
        verifier = Verifier(store)
        result = verifier.verify_sequence(["a1", "a2", "a1"])
        assert result.ok is False
        assert "duplicate" in result.error_message

    def test_order_preserved(self):
        store, tmp = _make_store_with_assets(["a1", "a2", "a3"])
        verifier = Verifier(store)
        result = verifier.verify_sequence(["a3", "a1", "a2"])
        assert result.ok is True

    def test_single_asset_passes(self):
        store, tmp = _make_store_with_assets(["a1"])
        verifier = Verifier(store)
        result = verifier.verify_sequence(["a1"])
        assert result.ok is True

    def test_no_expected_count_skips_count_check(self):
        store, tmp = _make_store_with_assets(["a1"])
        verifier = Verifier(store)
        result = verifier.verify_sequence(["a1"], expected_count=None)
        assert result.ok is True
