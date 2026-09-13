"""
Tests for Runtime Validator (Slice 4).
"""

import pytest
from unittest.mock import MagicMock, patch

from app.knowledge.runtime_validator import RuntimeValidator, ValidationResult, RuntimeEvidence
from app.knowledge.models import ClaimStatus, EvidenceTrustLevel, EvidenceSource
from app.knowledge.core import KnowledgeCore, KnowledgeQuery


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def mock_comfy_client():
    """Mock ComfyClient для тестов."""
    client = MagicMock()
    client.workflow_to_prompt = MagicMock(return_value={"1": {"class_type": "TestNode", "inputs": {}}})
    client.queue = MagicMock(return_value={"prompt_id": "test-123"})
    client.history = MagicMock(return_value={
        "test-123": {
            "status": {"status_str": "success"},
            "outputs": {"1": {"images": [{"filename": "test.png"}]}}
        }
    })
    return client


@pytest.fixture
def runtime_validator(mock_comfy_client):
    return RuntimeValidator(comfy_client=mock_comfy_client)


@pytest.fixture
def knowledge_core(runtime_validator):
    return KnowledgeCore(runtime_validator=runtime_validator)


# ------------------------------------------------------------------
# RuntimeEvidence
# ------------------------------------------------------------------


class TestRuntimeEvidence:
    def test_create_evidence(self):
        evidence = RuntimeEvidence(
            node_class="TestNode",
            validation_result=ValidationResult.SUCCESS,
            execution_time_ms=1234.5,
        )
        assert evidence.node_class == "TestNode"
        assert evidence.validation_result == ValidationResult.SUCCESS
        assert evidence.execution_time_ms == 1234.5

    def test_defaults(self):
        evidence = RuntimeEvidence(
            node_class="X",
            validation_result=ValidationResult.ERROR,
            execution_time_ms=0,
        )
        assert evidence.error_message == ""
        assert evidence.output_summary == ""


# ------------------------------------------------------------------
# RuntimeValidator
# ------------------------------------------------------------------


class TestRuntimeValidator:
    def test_no_client(self):
        validator = RuntimeValidator(comfy_client=None)
        evidence = validator.validate_node("TestNode", {})
        assert evidence.validation_result == ValidationResult.ERROR
        assert "No ComfyClient" in evidence.error_message

    def test_successful_validation(self, runtime_validator, mock_comfy_client):
        workflow = {"nodes": [{"type": "TestNode"}]}
        evidence = runtime_validator.validate_node("TestNode", workflow)
        assert evidence.validation_result == ValidationResult.SUCCESS
        assert evidence.execution_time_ms > 0
        mock_comfy_client.queue.assert_called_once()

    def test_timeout_validation(self, runtime_validator):
        # Mock history to never return result
        runtime_validator.comfy_client.history.return_value = {}
        runtime_validator.max_wait_seconds = 1  # Short timeout for test
        evidence = runtime_validator.validate_node("TestNode", {})
        assert evidence.validation_result == ValidationResult.TIMEOUT

    def test_error_validation(self, runtime_validator):
        runtime_validator.comfy_client.queue.side_effect = RuntimeError("Connection failed")
        evidence = runtime_validator.validate_node("TestNode", {})
        assert evidence.validation_result == ValidationResult.ERROR
        assert "Connection failed" in evidence.error_message

    def test_failure_validation(self, runtime_validator, mock_comfy_client):
        mock_comfy_client.history.return_value = {
            "test-123": {
                "status": {"status_str": "error", "messages": ["Node not found"]},
                "outputs": {}
            }
        }
        evidence = runtime_validator.validate_node("TestNode", {})
        assert evidence.validation_result == ValidationResult.FAILURE

    def test_upgrade_claims_success(self, runtime_validator):
        evidence = RuntimeEvidence(
            node_class="TestNode",
            validation_result=ValidationResult.SUCCESS,
            execution_time_ms=500.0,
        )
        claims = runtime_validator.upgrade_claims(evidence)
        assert len(claims) == 1
        assert claims[0].status == ClaimStatus.CONFIRMED
        assert claims[0].predicate == "validated_by_execution"

    def test_upgrade_claims_failure(self, runtime_validator):
        evidence = RuntimeEvidence(
            node_class="TestNode",
            validation_result=ValidationResult.FAILURE,
            execution_time_ms=100.0,
            error_message="Error occurred",
        )
        claims = runtime_validator.upgrade_claims(evidence)
        assert len(claims) == 0


# ------------------------------------------------------------------
# KnowledgeCore integration
# ------------------------------------------------------------------


class TestKnowledgeCoreSlice4:
    def test_validate_runtime_success(self, knowledge_core, mock_comfy_client):
        result = knowledge_core.validate_runtime("TestNode", {"nodes": []})
        assert result["validation_result"] == "SUCCESS"
        assert result["execution_time_ms"] > 0

    def test_validate_runtime_no_validator(self):
        core = KnowledgeCore()
        result = core.validate_runtime("TestNode", {})
        assert "error" in result
        assert "RuntimeValidator not configured" in result["error"]

    def test_get_validated_nodes(self, knowledge_core, mock_comfy_client):
        knowledge_core.validate_runtime("TestNode", {})
        validated = knowledge_core.get_validated_nodes()
        assert "TestNode" in validated
        assert validated["TestNode"] is True

    def test_validated_nodes_false_on_failure(self, knowledge_core):
        knowledge_core._runtime_validator = MagicMock()
        evidence = RuntimeEvidence(
            node_class="FailNode",
            validation_result=ValidationResult.FAILURE,
            execution_time_ms=100.0,
        )
        knowledge_core._runtime_validator.validate_node = MagicMock(return_value=evidence)
        knowledge_core.validate_runtime("FailNode", {})
        validated = knowledge_core.get_validated_nodes()
        assert validated["FailNode"] is False


# ------------------------------------------------------------------
# End-to-end with real ComfyUI (skip if not available)
# ------------------------------------------------------------------


class TestRuntimeValidatorE2E:
    @pytest.mark.skip(reason="Requires --real-comfyui flag (manual test)")
    def test_real_validation(self):
        """Реальная валидация на живом ComfyUI."""
        from app.comfy.client import ComfyClient
        from app.knowledge.runtime_validator import RuntimeValidator

        client = ComfyClient()
        validator = RuntimeValidator(comfy_client=client, max_wait_seconds=60)

        # Тест простой ноды (GetRequestNode если установлен)
        workflow = {
            "nodes": [
                {
                    "type": "Get Request Node",
                    "inputs": {
                        "target_url": "http://127.0.0.1:8188/system_stats"
                    }
                }
            ]
        }
        evidence = validator.validate_node("Get Request Node", workflow)
        # Результат зависит от наличия ноды в ComfyUI
        assert evidence.node_class == "Get Request Node"
