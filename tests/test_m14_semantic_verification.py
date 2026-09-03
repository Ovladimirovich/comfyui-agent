"""M14 Tests — Semantic Verification.

Тестирует:
- SemanticVerifier: initialization, MIME detection, prompt building, response parsing
- SemanticVerificationResult: dataclass, ok property
- Integration: Agent.generate() with semantic verification
"""
from __future__ import annotations

import base64
import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from app.engine.semantic_verifier import (
    SemanticVerificationResult,
    SemanticVerifier,
    SemanticVerifierError,
)


# --- SemanticVerificationResult tests ---

class TestSemanticVerificationResult:
    def test_ok_with_high_score(self):
        result = SemanticVerificationResult(score=0.8, matches_intent=True)
        assert result.ok is True

    def test_not_ok_with_low_score(self):
        result = SemanticVerificationResult(score=0.3, matches_intent=False)
        assert result.ok is False

    def test_not_ok_with_error(self):
        result = SemanticVerificationResult(score=0.8, matches_intent=True, error="some error")
        assert result.ok is False

    def test_ok_with_issues(self):
        result = SemanticVerificationResult(
            score=0.6, matches_intent=True, issues=["minor issue"]
        )
        assert result.ok is True  # score >= 0.5 and no error


# --- SemanticVerifier tests ---

class TestSemanticVerifier:
    def test_init_without_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            verifier = SemanticVerifier()
            assert verifier.api_key is None

    def test_init_with_api_key(self):
        verifier = SemanticVerifier(api_key="test-key")
        assert verifier.api_key == "test-key"

    def test_verify_without_api_key_returns_fallback(self):
        with patch.dict(os.environ, {}, clear=True):
            verifier = SemanticVerifier()
            result = verifier.verify(
                request="a cat",
                output_path="/nonexistent.png",
                capability="image.generate",
            )
            assert result.score == 0.5
            assert result.matches_intent is True
            assert "vision API not configured" in result.error

    def test_verify_with_nonexistent_file(self):
        verifier = SemanticVerifier(api_key="test-key")
        result = verifier.verify(
            request="a cat",
            output_path="/nonexistent/file.png",
            capability="image.generate",
        )
        assert result.score == 0.0
        assert result.matches_intent is False
        assert "file not found" in result.error

    def test_detect_mime_png(self):
        verifier = SemanticVerifier(api_key="test-key")
        assert verifier._detect_mime("test.png") == "image/png"

    def test_detect_mime_jpg(self):
        verifier = SemanticVerifier(api_key="test-key")
        assert verifier._detect_mime("test.jpg") == "image/jpeg"

    def test_detect_mime_mp4(self):
        verifier = SemanticVerifier(api_key="test-key")
        assert verifier._detect_mime("test.mp4") == "video/mp4"

    def test_detect_mime_unknown(self):
        verifier = SemanticVerifier(api_key="test-key")
        assert verifier._detect_mime("test.xyz") is None

    def test_build_system_prompt(self):
        verifier = SemanticVerifier(api_key="test-key")
        prompt = verifier._build_system_prompt("image.generate")
        assert "score" in prompt
        assert "matches_intent" in prompt
        assert "issues" in prompt

    def test_build_user_content(self):
        verifier = SemanticVerifier(api_key="test-key")
        content = verifier._build_user_content(
            request="a cat",
            file_data="base64data",
            mime="image/png",
            capability="image.generate",
        )
        assert len(content) == 2
        assert content[0]["type"] == "text"
        assert content[1]["type"] == "image_url"
        assert "base64data" in content[1]["image_url"]["url"]

    def test_build_user_content_with_previous(self):
        verifier = SemanticVerifier(api_key="test-key")
        content = verifier._build_user_content(
            request="a cat",
            file_data="base64data",
            mime="image/png",
            capability="image.generate",
            previous_output_path="/path/to/previous.png",
        )
        assert len(content) == 2
        assert "previous.png" in content[0]["text"]

    def test_parse_response_valid(self):
        verifier = SemanticVerifier(api_key="test-key")
        response = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "score": 0.85,
                        "matches_intent": True,
                        "issues": [],
                        "suggested_params": None,
                    })
                }
            }]
        }
        result = verifier._parse_response(response)
        assert result.score == 0.85
        assert result.matches_intent is True
        assert result.issues == []

    def test_parse_response_with_issues(self):
        verifier = SemanticVerifier(api_key="test-key")
        response = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "score": 0.4,
                        "matches_intent": False,
                        "issues": ["blurry", "wrong colors"],
                        "suggested_params": {"steps": 30},
                    })
                }
            }]
        }
        result = verifier._parse_response(response)
        assert result.score == 0.4
        assert result.matches_intent is False
        assert len(result.issues) == 2
        assert result.suggested_params == {"steps": 30}

    def test_parse_response_invalid_json(self):
        verifier = SemanticVerifier(api_key="test-key")
        response = {
            "choices": [{
                "message": {
                    "content": "not valid json"
                }
            }]
        }
        result = verifier._parse_response(response)
        assert result.score == 0.5
        assert "failed to parse" in result.error

    def test_parse_response_missing_fields(self):
        verifier = SemanticVerifier(api_key="test-key")
        response = {
            "choices": [{
                "message": {
                    "content": json.dumps({"score": 0.7})
                }
            }]
        }
        result = verifier._parse_response(response)
        assert result.score == 0.7
        # matches_intent defaults to True when score >= 0.5

    def test_score_clamped_to_range(self):
        verifier = SemanticVerifier(api_key="test-key")
        response = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "score": 1.5,
                        "matches_intent": True,
                    })
                }
            }]
        }
        result = verifier._parse_response(response)
        assert result.score == 1.0  # clamped

    def test_score_clamped_negative(self):
        verifier = SemanticVerifier(api_key="test-key")
        response = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "score": -0.5,
                        "matches_intent": False,
                    })
                }
            }]
        }
        result = verifier._parse_response(response)
        assert result.score == 0.0  # clamped


# --- Integration tests (mock vision API) ---

class TestSemanticVerifierIntegration:
    def test_verify_with_mock_api(self):
        """Тест с mock vision API (без реального вызова)."""
        mock_response = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "score": 0.9,
                        "matches_intent": True,
                        "issues": [],
                    })
                }
            }]
        }

        verifier = SemanticVerifier(api_key="test-key")

        # Создаём временный файл
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
            temp_path = f.name

        try:
            with patch.object(verifier, '_call_vision_api', return_value=mock_response):
                result = verifier.verify(
                    request="a cat",
                    output_path=temp_path,
                    capability="image.generate",
                )
                assert result.score == 0.9
                assert result.matches_intent is True
                assert result.ok is True
        finally:
            os.unlink(temp_path)

    def test_verify_handles_api_error(self):
        """Тест обработки ошибки vision API."""
        verifier = SemanticVerifier(api_key="test-key")

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
            temp_path = f.name

        try:
            with patch.object(
                verifier, '_call_vision_api',
                side_effect=RuntimeError("API error")
            ):
                result = verifier.verify(
                    request="a cat",
                    output_path=temp_path,
                    capability="image.generate",
                )
                assert result.score == 0.5  # fallback
                assert "vision API error" in result.error
        finally:
            os.unlink(temp_path)
