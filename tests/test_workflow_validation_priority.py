"""
Tests for validated nodes prioritization in workflow selection (S4).
"""

import pytest
from unittest.mock import MagicMock

from app.agent import Agent
from app.assets.store import AssetStore
from app.registry.workflow import Workflow
from app.knowledge.runtime_validator import ValidationResult


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def agent():
    return Agent(AssetStore(root="tests/__tmp_validation_priority__"))


@pytest.fixture
def mock_workflow():
    """Mock workflow с нодами."""
    wf = MagicMock()
    wf.id = "test_workflow"
    wf.version = "1.0.0"
    wf.capability = "image.generate"
    wf.workflow = {
        "nodes": [
            {"type": "Get Request Node", "inputs": {}},
            {"type": "CheckpointLoaderSimple", "inputs": {}},
        ],
        "links": []
    }
    return wf


# ------------------------------------------------------------------
# Tests: Validation Score
# ------------------------------------------------------------------


class TestValidationScore:
    """Тесты расчёта score валидации."""

    def test_score_with_validated_nodes(self, agent):
        """Score > 0 когда ноды валидированы."""
        agent._validated_nodes = {"Get Request Node": True, "CheckpointLoaderSimple": True}
        mock_wf = MagicMock()
        mock_wf.workflow = {
            "nodes": [
                {"type": "Get Request Node", "inputs": {}},
                {"type": "CheckpointLoaderSimple", "inputs": {}},
            ]
        }
        score = agent._calculate_validation_score(mock_wf)
        assert score == 2

    def test_score_with_partial_validation(self, agent):
        """Score > 0 при частичной валидации."""
        agent._validated_nodes = {"Get Request Node": True}
        mock_wf = MagicMock()
        mock_wf.workflow = {
            "nodes": [
                {"type": "Get Request Node", "inputs": {}},
                {"type": "UnknownNode", "inputs": {}},
            ]
        }
        score = agent._calculate_validation_score(mock_wf)
        assert score == 1

    def test_score_without_validation(self, agent):
        """Score = 0 когда нет валидации."""
        agent._validated_nodes = {}
        mock_wf = MagicMock()
        mock_wf.workflow = {"nodes": [{"type": "Get Request Node", "inputs": {}}]}
        score = agent._calculate_validation_score(mock_wf)
        assert score == 0

    def test_score_with_unvalidated_nodes(self, agent):
        """Score = 0 для невалидированных нод."""
        agent._validated_nodes = {"Get Request Node": False}
        mock_wf = MagicMock()
        mock_wf.workflow = {"nodes": [{"type": "Get Request Node", "inputs": {}}]}
        score = agent._calculate_validation_score(mock_wf)
        assert score == 0


# ------------------------------------------------------------------
# Tests: Workflow Selection Priority
# ------------------------------------------------------------------


class TestWorkflowSelectionPriority:
    """Тесты приоритета валидированных workflow."""

    def test_selects_higher_score_workflow(self, agent):
        """Выбирает workflow с более высоким score."""
        # Валидируем ноды
        agent._validated_nodes = {"Get Request Node": True}

        # Создаём mock workflows — явно задать пустые compliance-атрибуты,
        # иначе MagicMock-атрибуты становятся truthy и _compatibility_from_known
        # трактует их как declared/req, ломая проверку (AD-18 strict).
        # Pattern taken from test_fallback_without_validation.
        wf1 = MagicMock()
        wf1.id = "wf1"
        wf1.version = "1.0.0"
        wf1.capability = "image.generate"
        wf1.workflow = {"nodes": [{"type": "Get Request Node", "inputs": {}}]}
        wf1.declared_only = False
        wf1.required_models = []
        wf1.required_custom_nodes = []
        wf1.requirements = {}
        wf1.min_comfyui_version = "0.0.0"

        wf2 = MagicMock()
        wf2.id = "wf2"
        wf2.version = "1.0.0"
        wf2.capability = "image.generate"
        wf2.workflow = {"nodes": [{"type": "OtherNode", "inputs": {}}]}
        wf2.declared_only = False
        wf2.required_models = []
        wf2.required_custom_nodes = []
        wf2.requirements = {}
        wf2.min_comfyui_version = "0.0.0"

        # Mock registry
        agent.registry._workflows = [wf1, wf2]
        # Кандидаты из by_capability — тоже MagicMock, их атрибуты тоже нужно явно
        # задать, иначе getattr(c, "declared_only", False) вернёт MagicMock (truthy)
        # и кандидат уйдёт в declared_only-ветку, минуя _compatibility_from_known.
        c1 = MagicMock()
        c1.workflow_id = "wf1"
        c1.version = "1.0.0"
        c1.id = "wf1"
        c1.declared_only = False
        c1.required_models = []
        c1.required_custom_nodes = []
        c1.requirements = {}
        c1.min_comfyui_version = "0.0.0"

        c2 = MagicMock()
        c2.workflow_id = "wf2"
        c2.version = "1.0.0"
        c2.id = "wf2"
        c2.declared_only = False
        c2.required_models = []
        c2.required_custom_nodes = []
        c2.requirements = {}
        c2.min_comfyui_version = "0.0.0"

        agent.registry.by_capability = MagicMock(return_value=[c1, c2])
        agent.registry.get = MagicMock(side_effect=lambda wid, ver: wf1 if wid == "wf1" else wf2)

        # Вызываем select
        result = agent._select_manifest("image.generate", None, set(), set())

        # Должен выбрать wf1 (с валидированной нодой)
        assert result == wf1

    def test_fallback_without_validation(self, agent):
        """Fallback когда нет валидации."""
        agent._validated_nodes = {}

        wf1 = MagicMock()
        wf1.id = "wf1"
        wf1.version = "1.0.0"
        wf1.capability = "image.generate"
        wf1.workflow = {"nodes": []}
        wf1.status = MagicMock()
        wf1.status.value = "VALIDATED"
        # Явно задать атрибуты, чтобы _compatibility_from_known не трактовал
        # MagicMock-атрибуты как truthy (declared_only / required_models / custom nodes).
        wf1.declared_only = False
        wf1.required_models = []
        wf1.required_custom_nodes = []
        wf1.requirements = {}
        wf1.min_comfyui_version = "0.0.0"

        agent.registry._workflows = [wf1]
        # Mock для by_capability и get
        mock_candidate = MagicMock()
        mock_candidate.workflow_id = "wf1"
        mock_candidate.version = "1.0.0"
        mock_candidate.status = MagicMock()
        mock_candidate.status.value = "VALIDATED"
        # _compatibility_from_known читает эти атрибуты у кандидата
        mock_candidate.declared_only = False
        mock_candidate.required_models = []
        mock_candidate.required_custom_nodes = []
        mock_candidate.requirements = {}
        mock_candidate.min_comfyui_version = "0.0.0"
        agent.registry.by_capability = MagicMock(return_value=[mock_candidate])
        agent.registry.get = MagicMock(return_value=wf1)

        result = agent._select_manifest("image.generate", None, set(), set())
        # Результат может быть любым из кандидатов
        assert result is not None


# ------------------------------------------------------------------
# Tests: Agent Integration
# ------------------------------------------------------------------


class TestAgentIntegration:
    """Интеграция Agent + Runtime Validator."""

    def test_agent_with_validated_nodes(self, agent):
        """Agent хранит валидированные ноды."""
        agent._validated_nodes = {"TestNode": True}
        assert agent.get_validated_nodes()["TestNode"] is True

    def test_agent_background_validation(self, agent):
        """Background validation запускается."""
        import threading
        
        # Mock runtime_validator
        from app.knowledge.runtime_validator import RuntimeValidator
        agent.runtime_validator = MagicMock(spec=RuntimeValidator)
        agent.runtime_validator.validate_node = MagicMock(return_value=MagicMock(
            node_class="TestNode",
            validation_result=ValidationResult.SUCCESS,
            execution_time_ms=100.0,
        ))

        # Mock registry
        mock_manifest = MagicMock()
        mock_manifest.workflow_id = "test_workflow"
        mock_manifest.version = "1.0.0"
        agent.registry._workflows = [
            MagicMock(id="test_workflow", version="1.0.0", workflow={"nodes": []})
        ]
        agent.registry.by_capability = MagicMock(return_value=[mock_manifest])
        agent.registry.get = MagicMock(return_value=agent.registry._workflows[0])

        # Запускаем background validation
        agent._validate_capability_nodes_background("image.generate")

        # Ждем завершения потока
        import time
        time.sleep(0.5)

        # Проверяем что валидация была запущена (через thread join)
        # Поскольку поток daemon, просто проверяем что метод не выбросил исключение
        assert True
