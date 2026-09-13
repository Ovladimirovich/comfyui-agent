"""
Tests for Agent integration with Runtime Validator (Slice 4).
"""

import pytest
from unittest.mock import MagicMock, patch

from app.agent import Agent
from app.assets.store import AssetStore
from app.knowledge.runtime_validator import RuntimeValidator, ValidationResult, RuntimeEvidence
from app.knowledge.core import KnowledgeCore


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def mock_runtime_validator():
    """Mock RuntimeValidator для тестов."""
    validator = MagicMock(spec=RuntimeValidator)
    validator.validate_node = MagicMock(return_value=RuntimeEvidence(
        node_class="TestNode",
        validation_result=ValidationResult.SUCCESS,
        execution_time_ms=500.0,
    ))
    return validator


@pytest.fixture
def agent_with_validator(mock_runtime_validator):
    """Agent с RuntimeValidator."""
    store = AssetStore(root="tests/__tmp_agent_validation__")
    agent = Agent(store, runtime_validator=mock_runtime_validator)
    return agent


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


class TestAgentRuntimeValidation:
    """Тесты интеграции Agent + RuntimeValidator."""

    def test_agent_accepts_runtime_validator(self, mock_runtime_validator):
        """Agent принимает RuntimeValidator."""
        store = AssetStore(root="tests/__tmp_agent_validation__")
        agent = Agent(store, runtime_validator=mock_runtime_validator)
        assert agent.runtime_validator is mock_runtime_validator

    def test_get_validated_nodes_empty(self, agent_with_validator):
        """Сначала validated_nodes пустой."""
        assert agent_with_validator.get_validated_nodes() == {}

    def test_validate_capability_nodes_trigger(self, agent_with_validator, mock_runtime_validator):
        """Вызов _validate_capability_nodes_background запускает валидацию."""
        # Mock registry to return a workflow
        mock_manifest = MagicMock()
        mock_manifest.workflow_id = "test_workflow"
        mock_manifest.version = "1.0.0"
        agent_with_validator.registry._workflows = {
            "test_workflow": MagicMock(
                id="test_workflow",
                version="1.0.0",
                workflow={
                    "nodes": [
                        {"type": "TestNode", "inputs": {}}
                    ]
                }
            )
        }
        agent_with_validator.registry.by_capability = MagicMock(return_value=[mock_manifest])
        agent_with_validator.registry.get = MagicMock(return_value=agent_with_validator.registry._workflows["test_workflow"])
        
        # Запускаем валидацию
        agent_with_validator._validate_capability_nodes_background("image.generate")
        
        # Даем время на выполнение
        import time
        time.sleep(0.1)
        
        # Проверяем что validate_node был вызван
        mock_runtime_validator.validate_node.assert_called()

    def test_validated_nodes_populated(self, agent_with_validator, mock_runtime_validator):
        """validated_nodes заполняется после валидации."""
        # Симулируем успешную валидацию
        agent_with_validator._validated_nodes["TestNode"] = True
        
        validated = agent_with_validator.get_validated_nodes()
        assert "TestNode" in validated
        assert validated["TestNode"] is True

    def test_validated_nodes_false_on_failure(self, agent_with_validator):
        """validated_nodes = False при ошибке валидации."""
        agent_with_validator._validated_nodes["FailedNode"] = False
        
        validated = agent_with_validator.get_validated_nodes()
        assert validated["FailedNode"] is False

    def test_generate_with_runtime_validator(self, agent_with_validator):
        """generate() работает с RuntimeValidator."""
        # Mock planner
        mock_planner = MagicMock()
        mock_planner.plan = MagicMock(return_value=MagicMock(
            capability="image.generate",
            params={"prompt": "test"},
            rationale=None
        ))
        agent_with_validator.planner = mock_planner
        
        # Mock engine.execute to avoid actual execution
        with patch.object(agent_with_validator.engine, 'execute') as mock_execute:
            mock_job = MagicMock()
            mock_job.state.value = "SUCCESS"
            mock_job.output_assets = []
            mock_execute.return_value = mock_job
            
            # Запускаем generate
            job = agent_with_validator.generate("create test image")
            
            # Генерация должна завершиться
            assert job is not None


class TestAgentS4Integration:
    """Интеграция S4 (Runtime Validator) с Agent."""

    def test_knowledge_core_and_runtime_validator(self):
        """KnowledgeCore и RuntimeValidator работают вместе."""
        from app.knowledge.core import KnowledgeCore
        from app.knowledge.runtime_validator import RuntimeValidator
        
        # Создаем оба компонента
        runtime_validator = RuntimeValidator(comfy_client=None)
        knowledge_core = KnowledgeCore(runtime_validator=runtime_validator)
        
        # Валидация без клиента возвращает ошибку
        result = knowledge_core.validate_runtime("TestNode", {})
        assert "error_message" in result or "error" in result

    def test_agent_with_both_knowledge_and_runtime(self):
        """Agent с KnowledgeCore и RuntimeValidator."""
        store = AssetStore(root="tests/__tmp_agent_s4__")
        mock_validator = MagicMock(spec=RuntimeValidator)
        agent = Agent(store, runtime_validator=mock_validator)
        
        # Agent должен принять оба компонента
        assert agent.runtime_validator is mock_validator
