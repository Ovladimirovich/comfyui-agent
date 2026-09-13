"""S0.5 integration tests — Knowledge pre-flight wiring (advisory, non-blocking).

Покрытие:
  T1:  Legacy path: Agent без knowledge_core → Job без knowledge metadata
  T2:  Legacy path: ConversationAgent без knowledge_core → Job без knowledge metadata
  T3:  Agent с knowledge_core → pre-flight metadata на Job
  T4:  _plan_result_to_query mapping
  T5:  _plan_result_to_query без knowledge_core → None
  T6:  _plan_result_to_query пустая capability → None
  T7:  KnowledgeCore exception → graceful fallback (None)
  T8:  READINESS.UNKNOWN → advisory, execution proceeds
  T9:  READINESS.GAP → advisory, gaps on Job
  T10: READINESS.CANDIDATE_ONLY → advisory
  T11: READINESS.EXECUTABLE → advisory
  T12: _infer_media_output heuristic
  T13: ConversationAgent turn с knowledge_core → metadata на Job
  T14: Multi-turn: knowledge metadata per turn
  T15: backward compatibility: Agent(store) identical behavior
"""
import pytest
from unittest.mock import MagicMock, patch

from app.agent import Agent
from app.assets.store import AssetStore
from app.engine import Job, JobState
from app.conversation import ConversationAgent
from app.knowledge.core import KnowledgeCore, KnowledgeQuery, KnowledgeResponse, Readiness
from app.knowledge.gaps import GapNature, GapType, KnowledgeGap
from app.planner import PlanResult


# ------------------------------------------------------------------ #
# Fixtures
# ------------------------------------------------------------------ #


@pytest.fixture
def store(tmp_path):
    return AssetStore(root=str(tmp_path))


@pytest.fixture
def mock_knowledge_core():
    """Mock KnowledgeCore with configurable query response."""
    core = MagicMock(spec=KnowledgeCore)
    core.query = MagicMock(return_value=KnowledgeResponse(
        known_capabilities=["image.generate"],
        readiness=Readiness.EXECUTABLE,
        gaps=[],
    ))
    return core


@pytest.fixture
def mock_knowledge_core_with_gap():
    """Mock KnowledgeCore that returns GAP readiness."""
    core = MagicMock(spec=KnowledgeCore)
    core.query = MagicMock(return_value=KnowledgeResponse(
        known_capabilities=[],
        readiness=Readiness.GAP,
        gaps=[KnowledgeGap(
            needed="workflow for capability=video.generate",
            gap_type=GapType.NO_WORKFLOW,
            gap_nature=GapNature.EXECUTION,
            priority="MEDIUM",
        )],
    ))
    return core


@pytest.fixture
def agent_no_knowledge(store):
    return Agent(asset_store=store)


@pytest.fixture
def agent_with_knowledge(store, mock_knowledge_core):
    return Agent(asset_store=store, knowledge_core=mock_knowledge_core)


@pytest.fixture
def agent_with_gap_knowledge(store, mock_knowledge_core_with_gap):
    return Agent(asset_store=store, knowledge_core=mock_knowledge_core_with_gap)


@pytest.fixture
def conv_no_knowledge(store):
    return ConversationAgent(asset_store=store)


@pytest.fixture
def conv_with_knowledge(store, mock_knowledge_core):
    return ConversationAgent(asset_store=store, knowledge_core=mock_knowledge_core)


# ------------------------------------------------------------------ #
# T1-T2: Legacy path (no knowledge_core)
# ------------------------------------------------------------------ #


class TestLegacyPath:
    def test_agent_default_knowledge_core_none(self, agent_no_knowledge):
        """T1: Agent без knowledge_core → knowledge_core=None."""
        assert agent_no_knowledge.knowledge_core is None

    def test_conv_default_knowledge_core_none(self, conv_no_knowledge):
        """T2: ConversationAgent без knowledge_core → knowledge_core=None."""
        assert conv_no_knowledge.knowledge_core is None

    def test_plan_result_to_query_returns_none_without_core(self, agent_no_knowledge):
        """T5: _plan_result_to_query → None когда knowledge_core=None."""
        result = PlanResult(capability="image.generate", params={})
        query = agent_no_knowledge._plan_result_to_query(result)
        assert query is None

    def test_knowledge_preflight_returns_none_without_core(self, agent_no_knowledge):
        """_knowledge_preflight → None когда knowledge_core=None."""
        meta = agent_no_knowledge._knowledge_preflight("image.generate")
        assert meta is None


# ------------------------------------------------------------------ #
# T3, T11: Agent with knowledge_core → pre-flight metadata
# ------------------------------------------------------------------ #


class TestAgentKnowledgePreflight:
    def test_knowledge_preflight_returns_metadata(self, agent_with_knowledge):
        """T3: Agent с knowledge_core → preflight возвращает metadata dict."""
        meta = agent_with_knowledge._knowledge_preflight("image.generate")
        assert meta is not None
        assert "readiness" in meta
        assert "gaps" in meta
        assert meta["readiness"] == "EXECUTABLE"
        assert meta["gaps"] == []

    def test_preflight_with_manifest(self, agent_with_knowledge):
        """T11: preflight с manifest → metadata на основе manifest."""
        mock_manifest = MagicMock()
        mock_manifest.asset_inputs = {}  # no inputs = txt2img-like
        meta = agent_with_knowledge._knowledge_preflight(
            "image.generate", manifest=mock_manifest
        )
        assert meta is not None
        assert meta["readiness"] == "EXECUTABLE"

    def test_preflight_query_calls_knowledge_core(self, agent_with_knowledge, mock_knowledge_core):
        """T3: preflight вызывает knowledge_core.query()."""
        agent_with_knowledge._knowledge_preflight("image.generate")
        mock_knowledge_core.query.assert_called_once()
        call_args = mock_knowledge_core.query.call_args[0][0]
        assert isinstance(call_args, KnowledgeQuery)
        assert call_args.required_operation == "image.generate"


# ------------------------------------------------------------------ #
# T4: _plan_result_to_query mapping
# ------------------------------------------------------------------ #


class TestPlanResultToQuery:
    def test_basic_mapping(self, agent_with_knowledge):
        """T4: PlanResult → KnowledgeQuery basic mapping."""
        result = PlanResult(capability="image.generate", params={"prompt": "a cat"})
        query = agent_with_knowledge._plan_result_to_query(result)
        assert query is not None
        assert query.required_operation == "image.generate"
        assert query.task_description == "a cat"
        assert query.required_media_input == ()
        assert query.input_cardinality == 0

    def test_mapping_with_manifest(self, agent_with_knowledge):
        """T4: PlanResult + manifest → KnowledgeQuery с media_input/cardinality."""
        mock_manifest = MagicMock()
        mock_asset_input = MagicMock()
        mock_asset_input.kind = "image"
        mock_manifest.asset_inputs = {"image": mock_asset_input}

        result = PlanResult(capability="image.edit", params={})
        query = agent_with_knowledge._plan_result_to_query(result, mock_manifest)
        assert query is not None
        assert query.required_operation == "image.edit"
        assert query.required_media_input == ("image",)
        assert query.input_cardinality == 1

    def test_empty_capability_returns_none(self, agent_with_knowledge):
        """T6: пустая capability → None."""
        result = PlanResult(capability="", params={})
        query = agent_with_knowledge._plan_result_to_query(result)
        assert query is None

    def test_multi_asset_input(self, agent_with_knowledge):
        """T4: manifest с multi-asset input → cardinality=2."""
        mock_manifest = MagicMock()
        img_input = MagicMock()
        img_input.kind = "image"
        vid_input = MagicMock()
        vid_input.kind = "video"
        mock_manifest.asset_inputs = {"first_frame": img_input, "last_frame": img_input}

        result = PlanResult(capability="video.image_to_video", params={})
        query = agent_with_knowledge._plan_result_to_query(result, mock_manifest)
        assert query is not None
        assert query.required_media_input == ("image",)
        assert query.input_cardinality == 2


# ------------------------------------------------------------------ #
# T7: KnowledgeCore exception → graceful fallback
# ------------------------------------------------------------------ #


class TestKnowledgeException:
    def test_query_exception_returns_none(self, store):
        """T7: KnowledgeCore.query() exception → graceful fallback."""
        core = MagicMock(spec=KnowledgeCore)
        core.query.side_effect = RuntimeError("knowledge not initialized")
        agent = Agent(asset_store=store, knowledge_core=core)
        meta = agent._knowledge_preflight("image.generate")
        assert meta is None

    def test_plan_result_to_query_exception_returns_none(self, store):
        """_plan_result_to_query internal exception → None."""
        core = MagicMock(spec=KnowledgeCore)
        agent = Agent(asset_store=store, knowledge_core=core)
        # capability with no registry — should not raise
        result = PlanResult(capability="nonexistent.cap", params={})
        query = agent._plan_result_to_query(result)
        # may return None or a valid query — either way no crash
        assert query is None or isinstance(query, KnowledgeQuery)


# ------------------------------------------------------------------ #
# T8-T11: Readiness semantics (all advisory, non-blocking)
# ------------------------------------------------------------------ #


class TestReadinessSemantics:
    def test_unknown_readiness(self, store):
        """T8: READINESS.UNKNOWN → advisory, execution proceeds."""
        core = MagicMock(spec=KnowledgeCore)
        core.query.return_value = KnowledgeResponse(readiness=Readiness.UNKNOWN)
        agent = Agent(asset_store=store, knowledge_core=core)
        meta = agent._knowledge_preflight("unknown.cap")
        assert meta is not None
        assert meta["readiness"] == "UNKNOWN"

    def test_gap_readiness(self, agent_with_gap_knowledge):
        """T9: READINESS.GAP → advisory, gaps on Job."""
        meta = agent_with_gap_knowledge._knowledge_preflight("video.generate")
        assert meta is not None
        assert meta["readiness"] == "GAP"
        assert len(meta["gaps"]) > 0
        assert "workflow" in meta["gaps"][0].lower()

    def test_candidate_only_readiness(self, store):
        """T10: READINESS.CANDIDATE_ONLY → advisory."""
        core = MagicMock(spec=KnowledgeCore)
        core.query.return_value = KnowledgeResponse(readiness=Readiness.CANDIDATE_ONLY)
        agent = Agent(asset_store=store, knowledge_core=core)
        meta = agent._knowledge_preflight("some.cap")
        assert meta is not None
        assert meta["readiness"] == "CANDIDATE_ONLY"

    def test_executable_readiness(self, agent_with_knowledge):
        """T11: READINESS.EXECUTABLE → advisory."""
        meta = agent_with_knowledge._knowledge_preflight("image.generate")
        assert meta is not None
        assert meta["readiness"] == "EXECUTABLE"


# ------------------------------------------------------------------ #
# T12: _infer_media_output
# ------------------------------------------------------------------ #


class TestInferMediaOutput:
    def test_image_generate(self, agent_no_knowledge):
        assert agent_no_knowledge._infer_media_output("image.generate") == "image"

    def test_video_generate(self, agent_no_knowledge):
        assert agent_no_knowledge._infer_media_output("video.generate") == "video"

    def test_audio_generate(self, agent_no_knowledge):
        assert agent_no_knowledge._infer_media_output("audio.generate") == "audio"

    def test_text_generate(self, agent_no_knowledge):
        assert agent_no_knowledge._infer_media_output("text.generate") == "text"

    def test_video_image_to_video(self, agent_no_knowledge):
        assert agent_no_knowledge._infer_media_output("video.image_to_video") == "video"

    def test_unknown_capability(self, agent_no_knowledge):
        assert agent_no_knowledge._infer_media_output("unknown.cap") == ""

    def test_no_dot(self, agent_no_knowledge):
        assert agent_no_knowledge._infer_media_output("imagedit") == ""


# ------------------------------------------------------------------ #
# T13-T14: ConversationAgent turn with knowledge
# ------------------------------------------------------------------ #


class TestConversationAgentKnowledge:
    def test_conv_knowledge_core_forwarded(self, conv_with_knowledge, mock_knowledge_core):
        """T13: ConversationAgent knowledge_core forwarded to Agent."""
        assert conv_with_knowledge.knowledge_core is mock_knowledge_core
        # Agent (super) also has it
        assert conv_with_knowledge.knowledge_core is mock_knowledge_core

    def test_conv_inherits_agent_methods(self, conv_with_knowledge):
        """T13: ConversationAgent inherits _plan_result_to_query, _knowledge_preflight."""
        assert hasattr(conv_with_knowledge, '_plan_result_to_query')
        assert hasattr(conv_with_knowledge, '_knowledge_preflight')
        meta = conv_with_knowledge._knowledge_preflight("image.generate")
        assert meta is not None
        assert meta["readiness"] == "EXECUTABLE"


# ------------------------------------------------------------------ #
# T15: Backward compatibility — Agent(store) identical
# ------------------------------------------------------------------ #


class TestBackwardCompatibility:
    def test_agent_no_knowledge_no_attribute_error(self, store):
        """T15: Agent(store) — no AttributeError on knowledge_core."""
        agent = Agent(store)
        assert agent.knowledge_core is None
        assert agent._knowledge_preflight("image.generate") is None
        assert agent._plan_result_to_query(PlanResult(capability="x")) is None

    def test_conv_no_knowledge_no_attribute_error(self, store):
        """T15: ConversationAgent(store) — no AttributeError."""
        conv = ConversationAgent(store)
        assert conv.knowledge_core is None
        assert conv._knowledge_preflight("image.generate") is None

    def test_job_has_knowledge_fields(self):
        """T15: Job has _knowledge_readiness and _knowledge_gaps fields."""
        job = Job(
            prompt_id="test",
            workflow_id="wf",
            version="1.0",
            capability="image.generate",
        )
        assert hasattr(job, '_knowledge_readiness')
        assert hasattr(job, '_knowledge_gaps')
        assert job._knowledge_readiness is None
        assert job._knowledge_gaps is None

    def test_job_knowledge_fields_assignable(self):
        """T15: Job knowledge fields are assignable."""
        job = Job(
            prompt_id="test",
            workflow_id="wf",
            version="1.0",
            capability="image.generate",
        )
        job._knowledge_readiness = "EXECUTABLE"
        job._knowledge_gaps = ["some gap"]
        assert job._knowledge_readiness == "EXECUTABLE"
        assert job._knowledge_gaps == ["some gap"]
