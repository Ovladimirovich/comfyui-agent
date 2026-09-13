"""
Tests for Knowledge Core S4 → Planner integration.

Full path: User intent → Planner → validated knowledge → PlanResult
"""

import pytest
from unittest.mock import MagicMock

from app.planner.plan import PlanContext, PlanResult
from app.planner.heuristic import HeuristicPlanner
from app.knowledge.core import KnowledgeCore
from app.knowledge.runtime_validator import RuntimeValidator, ValidationResult, RuntimeEvidence


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def heuristic_planner():
    return HeuristicPlanner()


@pytest.fixture
def knowledge_core(tmp_path):
    from app.assets.store import AssetStore
    store = AssetStore(root="tests/__tmp_kcs4_planner__")
    return KnowledgeCore(data_dir=str(tmp_path / "kc"))


# ------------------------------------------------------------------
# Tests: PlanContext with validated_nodes
# ------------------------------------------------------------------


class TestPlanContext:
    """Тесты PlanContext с validated_nodes."""

    def test_plan_context_with_validated_nodes(self):
        """PlanContext принимает validated_nodes."""
        context = PlanContext(
            capabilities=("image.generate",),
            validated_nodes={"Get Request Node": True, "KSampler": False}
        )
        assert context.validated_nodes == {"Get Request Node": True, "KSampler": False}
        assert "image.generate" in context.capabilities

    def test_plan_context_without_validated_nodes(self):
        """PlanContext без validated_nodes (backward compat)."""
        context = PlanContext(capabilities=("image.generate",))
        assert context.validated_nodes == {}


# ------------------------------------------------------------------
# Tests: HeuristicPlanner with validated nodes
# ------------------------------------------------------------------


class TestHeuristicPlannerWithValidation:
    """Тесты HeuristicPlanner с validated nodes."""

    def test_plan_with_validated_nodes_in_rationale(self, heuristic_planner):
        """Validated nodes добавляются в rationale."""
        context = PlanContext(
            capabilities=("image.generate",),
            validated_nodes={"Get Request Node": True}
        )
        result = heuristic_planner.plan("create an image", context)
        
        assert result.capability == "image.generate"
        assert "[validated_nodes: 1]" in result.rationale

    def test_plan_without_validated_nodes(self, heuristic_planner):
        """Plan без validated nodes (backward compat)."""
        context = PlanContext(capabilities=("image.generate",))
        result = heuristic_planner.plan("create an image", context)
        
        assert result.capability == "image.generate"
        assert "[validated_nodes:" not in result.rationale

    def test_plan_with_multiple_validated_nodes(self, heuristic_planner):
        """Plan с несколькими валидированными нодами."""
        context = PlanContext(
            capabilities=("image.generate",),
            validated_nodes={"NodeA": True, "NodeB": True, "NodeC": False}
        )
        result = heuristic_planner.plan("create an image", context)
        
        assert "[validated_nodes: 2]" in result.rationale

    def test_edit_hint_with_validated_nodes(self, heuristic_planner):
        """Edit hint с validated nodes."""
        context = PlanContext(
            active_asset_type="image",
            capabilities=("image.edit", "image.generate"),
            validated_nodes={"RestoreFace": True}
        )
        result = heuristic_planner.plan("улучши изображение", context)
        
        assert result.capability == "image.edit"
        assert "[validated_nodes: 1]" in result.rationale


# ------------------------------------------------------------------
# Tests: KnowledgeCore integration
# ------------------------------------------------------------------


class TestKnowledgeCoreIntegration:
    """Интеграция KnowledgeCore с Planner."""

    def test_get_validated_for_capability(self, knowledge_core):
        """KnowledgeCore возвращает validated nodes для capability."""
        # Добавляем валидированные ноды
        knowledge_core._validated_nodes = {
            "Get Request Node": True,
            "KSampler": True,
            "CheckpointLoaderSimple": False
        }
        
        # Mock workflow registry
        mock_wf = MagicMock()
        mock_wf.workflow = {
            "nodes": [
                {"type": "Get Request Node", "inputs": {}},
                {"type": "KSampler", "inputs": {}},
            ]
        }
        knowledge_core._workflow_registry = MagicMock()
        knowledge_core._workflow_registry.by_capability = MagicMock(return_value=[mock_wf])
        
        result = knowledge_core.get_validated_for_capability("image.generate")
        
        # Должны вернуться только ноды из workflow
        assert "Get Request Node" in result
        assert "KSampler" in result
        assert "CheckpointLoaderSimple" not in result  # Не в workflow

    def test_get_validated_empty_when_no_validation(self, knowledge_core):
        """Empty result когда нет валидации."""
        knowledge_core._validated_nodes = {}
        result = knowledge_core.get_validated_for_capability("image.generate")
        assert result == {}

    def test_agent_passes_validated_nodes_to_planner(self):
        """Agent передаёт validated nodes в Planner."""
        from app.agent import Agent
        from app.assets.store import AssetStore
        
        store = AssetStore(root="tests/__tmp_agent_planner__")
        agent = Agent(store)
        
        # Mock knowledge_core
        mock_kc = MagicMock()
        mock_kc.get_validated_for_capability = MagicMock(return_value={
            "Get Request Node": True,
            "KSampler": True
        })
        agent.knowledge_core = mock_kc
        
        # Mock planner - captures the context
        captured_context = []
        def mock_plan(request, context=None):
            captured_context.append(context)
            return PlanResult(capability="image.generate", params={"prompt": request})
        
        agent.planner = MagicMock()
        agent.planner.plan = mock_plan
        
        # Вызываем generate
        agent.generate("create an image")
        
        # Проверяем что context был передан с validated nodes
        assert len(captured_context) == 1
        assert captured_context[0].validated_nodes == {"Get Request Node": True, "KSampler": True}


# ------------------------------------------------------------------
# Tests: Full Path
# ------------------------------------------------------------------


class TestFullPath:
    """Тест полного пути: User → Planner → Knowledge → PlanResult."""

    def test_user_intent_to_plan_result(self, heuristic_planner, knowledge_core):
        """Полный путь: запрос → контекст с validated nodes → PlanResult."""
        # 1. User intent
        request = "create an image of a cat"
        
        # 2. Knowledge Core предоставляет validated nodes
        knowledge_core._validated_nodes = {
            "Get Request Node": True,  # Валидирована
            "KSampler": True,           # Валидирована
            "UnknownNode": False        # Не валидирована
        }
        
        # Mock workflow registry
        mock_wf = MagicMock()
        mock_wf.workflow = {
            "nodes": [
                {"type": "Get Request Node", "inputs": {}},
                {"type": "KSampler", "inputs": {}},
            ]
        }
        knowledge_core._workflow_registry = MagicMock()
        knowledge_core._workflow_registry.by_capability = MagicMock(return_value=[mock_wf])
        
        # 3. Build PlanContext с validated nodes
        context = PlanContext(
            capabilities=("image.generate",),
            validated_nodes=knowledge_core.get_validated_for_capability("image.generate")
        )
        
        # 4. Planner использует контекст
        result = heuristic_planner.plan(request, context)
        
        # 5. Проверка результата
        assert result.capability == "image.generate"
        assert result.rationale is not None
        assert "[validated_nodes: 2]" in result.rationale  # 2 валидированные ноды

    def test_backward_compatibility_without_knowledge(self, heuristic_planner):
        """Backward compatibility: Planner работает без Knowledge Core."""
        request = "generate a video"
        
        # PlanContext без validated_nodes
        context = PlanContext(
            capabilities=("video.generate",),
            validated_nodes={}
        )
        
        result = heuristic_planner.plan(request, context)
        
        assert result.capability == "video.generate"
        assert "video_keyword" in result.rationale
