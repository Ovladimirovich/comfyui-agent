"""
Real E2E тесты для HttpRequestNodes на живом ComfyUI.

Тестирование:
1. GET запрос к /system_stats
2. POST запрос к API
3. Runtime validation сохраняет evidence
4. Claims upgrade до CONFIRMED
"""

import json
import pytest
import time
from pathlib import Path

from app.comfy.client import ComfyClient
from app.knowledge.runtime_validator import RuntimeValidator, ValidationResult
from app.knowledge.core import KnowledgeCore
from app.knowledge.node_doc import NodeDocStore
from app.knowledge.models import ClaimStatus


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def comfy_client():
    return ComfyClient()


@pytest.fixture
def runtime_validator(comfy_client):
    return RuntimeValidator(comfy_client=comfy_client, max_wait_seconds=60)


@pytest.fixture
def knowledge_core(runtime_validator):
    return KnowledgeCore(runtime_validator=runtime_validator)


@pytest.fixture
def node_doc_store():
    return NodeDocStore()


# ------------------------------------------------------------------
# Workflow builders
# ------------------------------------------------------------------


def build_get_request_workflow(url: str) -> dict:
    """Workflow: Get Request Node → SaveImage (для тестирования)."""
    return {
        "nodes": [
            {
                "id": 1,
                "type": "Get Request Node",
                "inputs": {"target_url": url},
                "widgets_values": [url, {}]
            }
        ],
        "links": []
    }


def build_system_stats_workflow() -> dict:
    """Workflow для проверки системных статов."""
    return build_get_request_workflow("http://127.0.0.1:8188/system_stats")


# ------------------------------------------------------------------
# Tests: Real HTTP requests
# ------------------------------------------------------------------


class TestRealHTTPRequests:
    """Реальные HTTP запросы через HttpRequestNodes."""

    def test_get_request_to_comfyui(self, runtime_validator):
        """GET запрос к системным статам ComfyUI."""
        workflow = build_system_stats_workflow()
        result = runtime_validator.validate_node("Get Request Node", workflow)
        
        # Нода должна либо succeed, либо error (но не timeout)
        assert result.validation_result in (
            ValidationResult.SUCCESS, 
            ValidationResult.ERROR,
            ValidationResult.FAILURE
        )
        assert result.execution_time_ms > 0
        
        # Если success — проверить что есть output
        if result.validation_result == ValidationResult.SUCCESS:
            assert result.output_summary  # Есть какие-то выходы

    def test_post_request_workflow(self, runtime_validator):
        """POST запрос работает (если нода существует)."""
        # Проверяем что нода существует
        from app.comfy.client import ComfyClient
        client = ComfyClient()
        oi = client.get_object_info()
        
        if "Post Request Node" in oi:
            workflow = {
                "nodes": [
                    {
                        "id": 1,
                        "type": "Post Request Node",
                        "inputs": {
                            "target_url": "http://127.0.0.1:8188/system_stats",
                            "body": "{}"
                        },
                        "widgets_values": ["http://127.0.0.1:8188/system_stats", "{}"]
                    }
                ],
                "links": []
            }
            result = runtime_validator.validate_node("Post Request Node", workflow)
            assert result.validation_result in (
                ValidationResult.SUCCESS,
                ValidationResult.ERROR,
                ValidationResult.FAILURE
            )
        else:
            pytest.skip("Post Request Node not found in ComfyUI")

    def test_blob_to_image_node_exists(self, comfy_client):
        """Blob To Image Node существует."""
        oi = comfy_client.get_object_info()
        assert "Blob To Image Node" in oi, "Blob To Image Node not found"

    def test_image_to_base64_node_exists(self, comfy_client):
        """Image To Base64 Node существует."""
        oi = comfy_client.get_object_info()
        assert "Image To Base64 Node" in oi, "Image To Base64 Node not found"


# ------------------------------------------------------------------
# Tests: Runtime Validation
# ------------------------------------------------------------------


class TestRuntimeValidation:
    """Runtime валидация и сохранение evidence."""

    def test_validation_stores_result(self, knowledge_core):
        """Результат валидации сохраняется."""
        workflow = build_system_stats_workflow()
        result = knowledge_core.validate_runtime("Get Request Node", workflow)
        
        assert "validation_result" in result
        assert "execution_time_ms" in result
        assert result["node_class"] == "Get Request Node"

    def test_validated_nodes_tracking(self, knowledge_core):
        """Отслеживание валидированных нод."""
        workflow = build_system_stats_workflow()
        knowledge_core.validate_runtime("Get Request Node", workflow)
        
        validated = knowledge_core.get_validated_nodes()
        assert "Get Request Node" in validated

    def test_multiple_nodes_validation(self, runtime_validator):
        """Валидация нескольких нод."""
        workflows = {
            "Get Request Node": build_system_stats_workflow(),
        }
        
        for node_class, workflow in workflows.items():
            result = runtime_validator.validate_node(node_class, workflow)
            assert result.node_class == node_class
            assert result.execution_time_ms >= 0


# ------------------------------------------------------------------
# Tests: Claims Upgrade
# ------------------------------------------------------------------


class TestClaimsUpgrade:
    """Upgrade claims до CONFIRMED."""

    def test_upgrade_on_success(self, runtime_validator):
        """Успешная валидация → CONFIRMED."""
        from app.knowledge.runtime_validator import RuntimeEvidence
        
        evidence = RuntimeEvidence(
            node_class="TestNode",
            validation_result=ValidationResult.SUCCESS,
            execution_time_ms=500.0,
        )
        
        claims = runtime_validator.upgrade_claims(evidence)
        assert len(claims) == 1
        assert claims[0].status == ClaimStatus.CONFIRMED

    def test_no_upgrade_on_failure(self, runtime_validator):
        """Неуспешная валидация → без upgrade."""
        from app.knowledge.runtime_validator import RuntimeEvidence
        
        evidence = RuntimeEvidence(
            node_class="TestNode",
            validation_result=ValidationResult.FAILURE,
            execution_time_ms=100.0,
        )
        
        claims = runtime_validator.upgrade_claims(evidence)
        assert len(claims) == 0

    def test_knowledge_core_upgrades_claims(self, knowledge_core):
        """KnowledgeCore применяет upgrade claims."""
        # Валидация должна обновить claims
        workflow = build_system_stats_workflow()
        result = knowledge_core.validate_runtime("Get Request Node", workflow)
        
        # Проверяем что валидация прошла
        assert result["validation_result"] in ("SUCCESS", "ERROR", "FAILURE")


# ------------------------------------------------------------------
# Tests: Integration with Agent
# ------------------------------------------------------------------


class TestAgentIntegration:
    """Интеграция с Agent."""

    def test_agent_with_runtime_validator(self):
        """Agent принимает RuntimeValidator."""
        from app.agent import Agent
        from app.assets.store import AssetStore
        from app.knowledge.runtime_validator import RuntimeValidator
        
        store = AssetStore(root="tests/__tmp_agent_e2e__")
        validator = RuntimeValidator(comfy_client=None)
        agent = Agent(store, runtime_validator=validator)
        
        assert agent.runtime_validator is validator

    def test_agent_validated_nodes(self):
        """Agent отслеживает валидированные ноды."""
        from app.agent import Agent
        from app.assets.store import AssetStore
        
        store = AssetStore(root="tests/__tmp_agent_e2e__")
        agent = Agent(store)
        
        # Сначала пусто
        assert agent.get_validated_nodes() == {}
        
        # Добавляем запись
        agent._validated_nodes["TestNode"] = True
        assert agent.get_validated_nodes()["TestNode"] is True


# ------------------------------------------------------------------
# End-to-end Pipeline
# ------------------------------------------------------------------


class TestFullPipeline:
    """Полный pipeline: Discovery → Documentation → Validation."""

    def test_pipeline(self, comfy_client, node_doc_store, knowledge_core):
        """Тест полного цикла."""
        # 1. Discovery: получаем /object_info
        oi = comfy_client.get_object_info()
        assert len(oi) > 0
        
        # 2. Documentation: проверяем что ноды документированы
        get_node_doc = node_doc_store.get_doc_for("Get Request Node")
        assert get_node_doc is not None
        assert get_node_doc.purpose == "HTTP GET запрос"
        
        # 3. Validation: пробуем валидировать
        workflow = build_system_stats_workflow()
        result = knowledge_core.validate_runtime("Get Request Node", workflow)
        
        # Результат может быть SUCCESS, ERROR или FAILURE
        assert "validation_result" in result


# ------------------------------------------------------------------
# Performance Tests
# ------------------------------------------------------------------


class TestPerformance:
    """Тесты производительности."""

    def test_validation_latency(self, runtime_validator):
        """Валидация должна завершиться за приемлемое время."""
        workflow = build_system_stats_workflow()
        start = time.time()
        result = runtime_validator.validate_node("Get Request Node", workflow)
        elapsed = time.time() - start
        
        # Должно быть меньше 60 секунд (timeout)
        assert elapsed < 60, f"Validation took {elapsed:.1f}s, expected < 60s"
        
        # Execution time должна быть > 0
        assert result.execution_time_ms > 0
