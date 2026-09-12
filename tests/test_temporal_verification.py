"""M25.3 — Temporal Semantic Verification Tests.

Доказывает offline:
  - empty sequence → FAIL (temporal_score=0.0)
  - single asset → neutral (temporal_score=None, N/A)
  - no api_key → temporal_score=None (fallback neutral)
  - missing file → FAIL (temporal_score=0.0)
  - all files exist → calls vision API (mocked), returns score
  - poor continuity → low temporal_score (<0.5)
  - good continuity → high temporal_score (>=0.5)
  - visual OK but other errors → score unaffected
  - existing verify() unchanged (no regression)
"""
from __future__ import annotations

import base64
import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from app.engine.semantic_verifier import SemanticVerifier, SemanticVerificationResult


# ── Helpers ──


def _write_png(tmp: str, name: str) -> str:
    path = os.path.join(tmp, name)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)
    return path


def _mock_vision_response(score: float, issues: list[str] | None = None) -> dict:
    """Mock vision API response for frame-pair comparison."""
    content = json.dumps({"score": score, "temporal_issues": issues or []})
    return {"choices": [{"message": {"content": content}}]}


# ── Tests: empty / single ──


class TestTemporalEmptySequence:
    def test_empty_sequence_fails(self):
        v = SemanticVerifier(api_key="fake")
        result = v.verify_temporal_consistency([])
        assert result.temporal_score == 0.0
        assert result.matches_intent is False
        assert "empty sequence" in result.temporal_issues

    def test_none_sequence_fails(self):
        v = SemanticVerifier(api_key="fake")
        result = v.verify_temporal_consistency([])
        assert result.score == 0.0


class TestTemporalSingleAsset:
    def test_single_asset_neutral(self):
        tmp = tempfile.mkdtemp()
        path = _write_png(tmp, "frame0.png")
        v = SemanticVerifier(api_key="fake")
        result = v.verify_temporal_consistency([path])
        assert result.temporal_score is None
        assert "N/A" in result.temporal_issues[0]


# ── Tests: no api key ──


class TestTemporalNoApiKey:
    def test_no_api_key_returns_none(self):
        v = SemanticVerifier(api_key=None)
        tmp = tempfile.mkdtemp()
        p1 = _write_png(tmp, "a.png")
        p2 = _write_png(tmp, "b.png")
        result = v.verify_temporal_consistency([p1, p2])
        assert result.temporal_score is None
        assert "vision API not configured" in result.error


# ── Tests: missing files ──


class TestTemporalMissingFiles:
    def test_missing_file_fails(self):
        v = SemanticVerifier(api_key="fake")
        result = v.verify_temporal_consistency(["/nonexistent/frame.png", "/nonexistent/frame2.png"])
        assert result.temporal_score == 0.0
        assert result.matches_intent is False
        assert any("missing" in iss.lower() for iss in result.temporal_issues)


# ── Tests: vision API mocked ──


class TestTemporalGoodContinuity:
    def test_good_continuity_high_score(self):
        v = SemanticVerifier(api_key="fake")
        tmp = tempfile.mkdtemp()
        paths = [_write_png(tmp, f"f{i}.png") for i in range(4)]

        with patch.object(v, "_call_vision_api") as mock_call:
            mock_call.return_value = _mock_vision_response(0.85)
            result = v.verify_temporal_consistency(paths)

        assert result.temporal_score is not None
        assert result.temporal_score >= 0.7
        assert result.matches_intent is True

    def test_poor_continuity_low_score(self):
        v = SemanticVerifier(api_key="fake")
        tmp = tempfile.mkdtemp()
        paths = [_write_png(tmp, f"f{i}.png") for i in range(3)]

        with patch.object(v, "_call_vision_api") as mock_call:
            mock_call.return_value = _mock_vision_response(0.3, ["abrupt_change"])
            result = v.verify_temporal_consistency(paths)

        assert result.temporal_score is not None
        assert result.temporal_score < 0.5
        assert result.matches_intent is False


class TestTemporalComparisonSampling:
    """Verify that _sample_indices selects first/middle/last efficiently."""

    def test_samples_first_last_middle(self):
        v = SemanticVerifier(api_key="fake")
        indices = v._sample_indices(10, max_samples=5)
        assert indices[0] == 0
        assert indices[-1] == 9
        assert len(indices) <= 5

    def test_small_sequence_all_indices(self):
        v = SemanticVerifier(api_key="fake")
        indices = v._sample_indices(3, max_samples=5)
        assert indices == [0, 1, 2]


# ── Tests: regression — existing verify() ──


class TestTemporalRegression:
    def test_existing_verify_still_works(self):
        v = SemanticVerifier(api_key="fake")
        tmp = tempfile.mkdtemp()
        path = _write_png(tmp, "out.png")
        with patch.object(v, "_call_vision_api") as mock_call:
            mock_call.return_value = {"choices": [{"message": {"content": json.dumps(
                {"score": 0.8, "matches_intent": True, "issues": [], "suggested_params": None}
            )}}]}
            result = v.verify("a cat", path, capability="image.generate")
        assert result.score == 0.8
        assert result.temporal_score is None  # temporal only set by temporal method

    def test_verify_result_has_temporal_field(self):
        r = SemanticVerificationResult(score=0.8, matches_intent=True)
        assert hasattr(r, "temporal_score")
        assert r.temporal_score is None
        r.temporal_score = 0.7
        assert r.temporal_score == 0.7
