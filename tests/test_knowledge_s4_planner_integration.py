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
# Tests: PlanContext (текущий контракт app/planner/plan.py)
# Поле validated_nodes НЕ входит в PlanContext: validated knowledge
# живёт в KnowledgeCore (get_validated_for_capability), NOT в planner-контексте.
# ------------------------------------------------------------------


class TestPlanContext:
    """Тесты PlanContext по текущему контракту (без validated_nodes)."""

    def test_plan_context_current_fields(self):
        """PlanContext принимает текущие поля контракта."""
        context = PlanContext(
            active_asset_type="image",
            capabilities=("image.generate",),
            active_workflow="txt2img@1.0.0",
            previous_prompt="a cat",
            explicit_asset_type="image",
        )
        assert context.active_asset_type == "image"
        assert "image.generate" in context.capabilities
        assert context.active_workflow == "txt2img@1.0.0"
        assert context.previous_prompt == "a cat"

    def test_plan_context_defaults(self):
        """PlanContext с дефолтами (backward compat)."""
        context = PlanContext(capabilities=("image.generate",))
        assert context.active_asset_type is None
        assert context.active_workflow is None
        assert context.previous_prompt is None
        assert context.explicit_asset_type is None

    def test_plan_context_has_no_validated_nodes_field(self):
        """Контракт: validated_nodes НЕ является полем PlanContext (S4 triage)."""
        context = PlanContext(capabilities=("image.generate",))
        assert not hasattr(context, "validated_nodes")


# ------------------------------------------------------------------
# Tests: HeuristicPlanner with validated nodes
# ------------------------------------------------------------------


class TestHeuristicPlannerWithContext:
    """HeuristicPlanner по текущему контракту: работает с PlanContext,
    НЕ использует validated_nodes (validated knowledge — concern KnowledgeCore)."""

    def test_plan_with_context(self, heuristic_planner):
        """Plan с текущим PlanContext."""
        context = PlanContext(capabilities=("image.generate",))
        result = heuristic_planner.plan("create an image", context)

        assert result.capability == "image.generate"
        assert "[validated_nodes:" not in result.rationale

    def test_plan_without_context(self, heuristic_planner):
        """Plan без context (backward compat)."""
        result = heuristic_planner.plan("create an image")

        assert result.capability == "image.generate"

    def test_edit_hint_with_context(self, heuristic_planner):
        """Edit hint через active_asset_type (текущий механизм M9.1)."""
        context = PlanContext(
            active_asset_type="image",
            capabilities=("image.edit", "image.generate"),
        )
        result = heuristic_planner.plan("улучши изображение", context)

        assert result.capability == "image.edit"

    def test_planner_does_not_annotate_validated_nodes(self, heuristic_planner):
        """Контракт: rationale не содержит validated_nodes-аннотаций."""
        context = PlanContext(capabilities=("image.generate",))
        result = heuristic_planner.plan("create an image", context)

        assert result.rationale is not None
        assert "validated_nodes" not in (result.rationale or "")


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

    def test_agent_generate_calls_planner_without_validated_context(self):
        """Текущий контракт: Agent.generate вызывает planner.plan(request) —
        validated nodes НЕ прокидываются в planner-контекст (S4 triage)."""
        from app.agent import Agent
        from app.assets.store import AssetStore

        store = AssetStore(root="tests/__tmp_agent_planner__")
        agent = Agent(store)

        # Mock planner - captures the call
        captured = []
        def mock_plan(request, context=None):
            captured.append((request, context))
            return PlanResult(capability="image.generate", params={"prompt": request})

        agent.planner = MagicMock()
        agent.planner.plan = mock_plan

        agent.generate("create an image")

        assert len(captured) == 1
        request, context = captured[0]
        assert "create an image" in request
        # Текущий контракт: generate() не строит PlanContext и не передаёт validated_nodes
        assert context is None


# ------------------------------------------------------------------
# Tests: Full Path
# ------------------------------------------------------------------


class TestFullPath:
    """Тест полного пути: User → Planner → Knowledge → PlanResult."""

    def test_user_intent_to_plan_result(self, heuristic_planner, knowledge_core):
        """Полный путь: query → KnowledgeCore (validated) → PlanContext (текущий)
        → PlanResult. Validated nodes остаются в KnowledgeCore, НЕ в контексте."""
        # 1. User intent
        request = "create an image of a cat"

        # 2. Knowledge Core предоставляет validated nodes (production API)
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

        # 3. Validated nodes читаются из KnowledgeCore (не из PlanContext)
        validated = knowledge_core.get_validated_for_capability("image.generate")
        assert validated == {"Get Request Node": True, "KSampler": True}

        # 4. Build PlanContext по текущему контракту (без validated_nodes)
        context = PlanContext(capabilities=("image.generate",))

        # 5. Planner использует контекст
        result = heuristic_planner.plan(request, context)

        # 6. Проверка результата
        assert result.capability == "image.generate"
        assert result.rationale is not None
        assert "validated_nodes" not in (result.rationale or "")

    def test_backward_compatibility_without_knowledge(self, heuristic_planner):
        """Backward compatibility: Planner работает без Knowledge Core."""
        request = "generate a video"

        # PlanContext по текущему контракту
        context = PlanContext(capabilities=("video.generate",))

        result = heuristic_planner.plan(request, context)

        assert result.capability == "video.generate"
        assert "video_keyword" in result.rationale
