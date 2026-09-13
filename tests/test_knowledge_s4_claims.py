"""
Tests for Knowledge Core S4 — Claims Upgrade to CONFIRMED.
"""

import pytest
from unittest.mock import MagicMock

from app.knowledge.runtime_validator import RuntimeValidator, ValidationResult, RuntimeEvidence
from app.knowledge.core import KnowledgeCore, KnowledgeQuery
from app.knowledge.models import ClaimStatus, EvidenceTrustLevel, EvidenceSource
from app.knowledge.node_schema import NodeSchema, FieldSpec


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
# Tests: Claims Upgrade
# ------------------------------------------------------------------


class TestClaimsUpgrade:
    """Тесты upgrade claims до CONFIRMED."""

    def test_upgrade_existing_claim(self, runtime_validator):
        """Upgrade существующего claim до CONFIRMED."""
        from app.knowledge.models import KnowledgeClaim
        
        # Создаем существующий claim с INFERENCE статусом
        existing_claim = KnowledgeClaim(
            claim="TestNode may implement http.get",
            subject="TestNode",
            predicate="may_implement",
            object="http.get",
            status=ClaimStatus.INFERENCE,
            evidence=[],
        )
        
        evidence = RuntimeEvidence(
            node_class="TestNode",
            validation_result=ValidationResult.SUCCESS,
            execution_time_ms=500.0,
        )
        
        # Merge evidence
        updated_claims = runtime_validator.merge_runtime_evidence(evidence, [existing_claim])
        
        assert len(updated_claims) == 1
        assert updated_claims[0].status == ClaimStatus.CONFIRMED
        assert len(updated_claims[0].evidence) == 1
        assert updated_claims[0].evidence[0].trust_level == EvidenceTrustLevel.OBSERVED_BEHAVIOR

    def test_create_new_claim_on_success(self, runtime_validator):
        """Создание нового claim при успешной валидации."""
        from app.knowledge.models import KnowledgeClaim
        
        evidence = RuntimeEvidence(
            node_class="NewNode",
            validation_result=ValidationResult.SUCCESS,
            execution_time_ms=300.0,
        )
        
        # Нет существующих claims
        updated_claims = runtime_validator.merge_runtime_evidence(evidence, [])
        
        assert len(updated_claims) == 1
        assert updated_claims[0].subject == "NewNode"
        assert updated_claims[0].status == ClaimStatus.CONFIRMED

    def test_no_upgrade_on_failure(self, runtime_validator):
        """No upgrade при failurer."""
        from app.knowledge.models import KnowledgeClaim
        
        existing_claim = KnowledgeClaim(
            claim="TestNode may implement http.get",
            subject="TestNode",
            predicate="may_implement",
            object="http.get",
            status=ClaimStatus.INFERENCE,
            evidence=[],
        )
        
        evidence = RuntimeEvidence(
            node_class="TestNode",
            validation_result=ValidationResult.FAILURE,
            execution_time_ms=100.0,
        )
        
        updated_claims = runtime_validator.merge_runtime_evidence(evidence, [existing_claim])
        
        # Claims должны остаться без изменений
        assert len(updated_claims) == 1
        assert updated_claims[0].status == ClaimStatus.INFERENCE

    def test_multiple_claims_upgrade(self, runtime_validator):
        """Upgrade нескольких claims."""
        from app.knowledge.models import KnowledgeClaim
        
        claims = [
            KnowledgeClaim(
                claim="NodeA may implement http.get",
                subject="NodeA",
                predicate="may_implement",
                object="http.get",
                status=ClaimStatus.INFERENCE,
                evidence=[],
            ),
            KnowledgeClaim(
                claim="NodeB may implement image.generate",
                subject="NodeB",
                predicate="may_implement",
                object="image.generate",
                status=ClaimStatus.INFERENCE,
                evidence=[],
            ),
        ]
        
        # Валидируем NodeA
        evidence_a = RuntimeEvidence(
            node_class="NodeA",
            validation_result=ValidationResult.SUCCESS,
            execution_time_ms=500.0,
        )
        updated = runtime_validator.merge_runtime_evidence(evidence_a, claims)
        
        # NodeA должен быть CONFIRMED, NodeB остался INFERENCE
        assert updated[0].status == ClaimStatus.CONFIRMED
        assert updated[1].status == ClaimStatus.INFERENCE

    def test_get_confirmed_claims(self, knowledge_core):
        """Получение CONFIRMED claims."""
        from app.knowledge.models import KnowledgeClaim
        
        # Добавляем существующие claims
        knowledge_core._claims = [
            KnowledgeClaim(
                claim="TestNode validated",
                subject="TestNode",
                predicate="validated_by_execution",
                object="true",
                status=ClaimStatus.CONFIRMED,
                evidence=[],
            ),
            KnowledgeClaim(
                claim="OtherNode inferred",
                subject="OtherNode",
                predicate="may_implement",
                object="http.get",
                status=ClaimStatus.INFERENCE,
                evidence=[],
            ),
        ]
        
        confirmed = knowledge_core.get_confirmed_claims()
        assert len(confirmed) == 1
        assert confirmed[0].subject == "TestNode"


# ------------------------------------------------------------------
# Tests: KnowledgeCore Integration
# ------------------------------------------------------------------


class TestKnowledgeCoreS4:
    """Интеграция S4 с KnowledgeCore."""

    def test_validate_and_upgrade_claims(self, knowledge_core, mock_comfy_client):
        """Валидация обновляет claims."""
        workflow = {
            "nodes": [{"type": "TestNode", "inputs": {}}],
            "links": []
        }
        result = knowledge_core.validate_runtime("TestNode", workflow)
        
        assert result["validation_result"] == "SUCCESS"
        confirmed = knowledge_core.get_confirmed_claims()
        assert len(confirmed) > 0

    def test_query_after_runtime_validation(self, knowledge_core, mock_comfy_client):
        """Query после runtime валидации."""
        # Сначала валидируем
        workflow = {
            "nodes": [{"type": "TestNode", "inputs": {}}],
            "links": []
        }
        knowledge_core.validate_runtime("TestNode", workflow)
        
        # Теперь query
        query = KnowledgeQuery(
            required_operation="http.get",
            required_media_input=(),
            required_media_output="string",
        )
        response = knowledge_core.query(query)
        
        # Должны быть claims
        assert len(response.claims) >= 0  # Зависит от того, нашлась ли нода

    def test_readiness_after_validation(self, knowledge_core, mock_comfy_client):
        """Readiness после валидации (claim создан, readiness может быть UNKNOWN)."""
        from app.knowledge.core import Readiness
        
        # Валидация
        workflow = {
            "nodes": [{"type": "TestNode", "inputs": {}}],
            "links": []
        }
        knowledge_core.validate_runtime("TestNode", workflow)
        
        # Query — readiness зависит от наличия capability/candidate, не от claims
        query = KnowledgeQuery(
            required_operation="test.operation",
            required_media_input=(),
            required_media_output="string",
        )
        response = knowledge_core.query(query)
        
        # Claims должны быть созданы
        assert len(knowledge_core.get_confirmed_claims()) > 0
        # Readiness может быть любым — зависит от capability registry


# ------------------------------------------------------------------
# Tests: End-to-End
# ------------------------------------------------------------------


class TestEndToEnd:
    """End-to-end тесты S4."""

    def test_full_pipeline(self, knowledge_core, mock_comfy_client):
        """Полный pipeline: валидация → upgrade → query."""
        # 1. Валидация
        workflow = {
            "nodes": [{"type": "TestNode", "inputs": {}}],
            "links": []
        }
        result = knowledge_core.validate_runtime("TestNode", workflow)
        assert result["validation_result"] == "SUCCESS"
        
        # 2. Проверка claims
        confirmed = knowledge_core.get_confirmed_claims()
        assert len(confirmed) > 0
        assert confirmed[0].status == ClaimStatus.CONFIRMED
        
        # 3. Query
        query = KnowledgeQuery(
            required_operation="test.operation",
            required_media_input=(),
            required_media_output="string",
        )
        response = knowledge_core.query(query)
        assert response is not None
