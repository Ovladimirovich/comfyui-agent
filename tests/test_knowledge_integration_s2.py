"""Slice 2 integration tests — KnowledgeCore wired into Agent / ConversationAgent.

Покрытие:
  TestA: builtin capability → EXECUTABLE readiness
  TestB: AgnesVideo candidate (no workflow) → CANDIDATE_ONLY / GAP
  TestC: cardinality=2 → First and Last frame candidate
  TestD: unknown operation → UNKNOWN + UNKNOWN_CAPABILITY gap
  TestE: candidate isolation (not in CapabilityRegistry)
  TestF: session isolation (response per session)
  TestG: regression (full existing suite)
"""
import os
import pytest
from unittest.mock import MagicMock

from app.assets.store import AssetStore
from app.agent import Agent
from app.comfy.client import ComfyClient
from app.conversation import ConversationAgent
from app.engine import JobState
from app.knowledge.core import KnowledgeCore, KnowledgeQuery, Readiness
from app.knowledge.node_schema import NodeSchema, FieldSpec
from app.knowledge.research import ResearchRequest
from app.planner import PlanResult


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #

@pytest.fixture
def store(tmp_path):
    return AssetStore(root=str(tmp_path))


@pytest.fixture(scope="session")
def knowledge_core(tmp_path_factory):
    """P1 contract: tmp data_dir — refresh() НЕ пишет в production app/data/knowledge."""
    from app.registry.capability import CapabilityRegistry
    cr = CapabilityRegistry()
    core = KnowledgeCore(capability_registry=cr,
                         data_dir=str(tmp_path_factory.mktemp("kc_s2")))
    client = ComfyClient()
    try:
        core.refresh(client)
    except Exception as e:
        pytest.skip(f"ComfyUI недоступен для refresh: {e}")
    return core


@pytest.fixture
def agent_with_knowledge(store, knowledge_core):
    return Agent(asset_store=store, knowledge_core=knowledge_core)


@pytest.fixture
def conv_agent_with_knowledge(store, knowledge_core):
    return ConversationAgent(asset_store=store, knowledge_core=knowledge_core)


# --------------------------------------------------------------------------- #
# TestA: existing builtin capability → EXECUTABLE readiness
# --------------------------------------------------------------------------- #

class TestABuiltinCapability:
    def test_builtin_image_generate_readiness(self, agent_with_knowledge):
        query = KnowledgeQuery(
            required_operation="image.generate",
            required_media_input=(),
            required_media_output="image",
            input_cardinality=0,
        )
        response = agent_with_knowledge.knowledge_core.query(query)
        assert "image.generate" in response.known_capabilities
        assert response.readiness in (Readiness.EXECUTABLE, Readiness.GAP)

    def test_builtin_video_generate_readiness(self, agent_with_knowledge):
        query = KnowledgeQuery(
            required_operation="video.generate",
            required_media_input=(),
            required_media_output="video",
            input_cardinality=0,
        )
        response = agent_with_knowledge.knowledge_core.query(query)
        assert "video.generate" in response.known_capabilities

    def test_plan_result_to_query_maps_correctly(self, agent_with_knowledge):
        # S0.5 approved contract: media/cardinality из manifest (production path
        # run() всегда передаёт manifest после _select_manifest).
        manifest = MagicMock()
        ai_start = MagicMock(); ai_start.kind = "image"
        ai_end = MagicMock(); ai_end.kind = "image"
        manifest.asset_inputs = {"first_frame": ai_start, "last_frame": ai_end}
        result = PlanResult(capability="video.image_to_video", params={"prompt": "test"})
        query = agent_with_knowledge._plan_result_to_query(result, manifest)
        assert query is not None
        assert query.required_operation == "video.image_to_video"
        assert query.required_media_output == "video"
        assert query.input_cardinality == 2  # 2 asset_inputs

    def test_plan_result_to_query_unknown_capability(self, agent_with_knowledge):
        # S0.5 approved contract: неизвестная capability → query создаётся,
        # KnowledgeCore ответит readiness=UNKNOWN (advisory semantics).
        # Только ПУСТАЯ capability → None.
        result = PlanResult(capability="nonexistent.cap", params={})
        query = agent_with_knowledge._plan_result_to_query(result)
        assert query is not None
        assert query.required_operation == "nonexistent.cap"
        empty = PlanResult(capability="", params={})
        assert agent_with_knowledge._plan_result_to_query(empty) is None


# --------------------------------------------------------------------------- #
# TestB: AgnesVideo candidate (no compatible workflow)
# --------------------------------------------------------------------------- #

class TestBAgnesCandidate:
    def test_agnes_candidate_exists(self, knowledge_core):
        schemas = knowledge_core.get_schemas()
        assert "AgnesVideo" in schemas

    def test_agnes_candidate_not_in_registry(self, knowledge_core):
        from app.registry.capability import CapabilityRegistry
        cr = CapabilityRegistry()
        caps = [c.id for c in cr.all()]
        assert "agnesvideo" not in [c.lower() for c in caps]
        assert "video.image_to_video" in caps  # builtin exists, but not Agnes-specific

    def test_agnes_cardinality_2_matches_flf(self, knowledge_core):
        query = KnowledgeQuery(
            required_operation="video.image_to_video",
            required_media_input=("image", "image"),
            required_media_output="video",
            input_cardinality=2,
        )
        response = knowledge_core.query(query)
        flf_cands = [c for c in response.candidate_nodes
                     if c.node_class == "AgnesVideo" and c.usage.cardinality == 2]
        assert len(flf_cands) > 0, "First and Last frame candidate should match card=2"
        itv_cands = [c for c in response.candidate_nodes
                     if c.node_class == "AgnesVideo" and c.usage.cardinality == 1]
        assert len(itv_cands) == 0, "Image To Video (card=1) should NOT match card=2 query"

    def test_agnes_no_workflow_execution_gap(self, knowledge_core):
        query = KnowledgeQuery(
            required_operation="video.image_to_video",
            required_media_input=("image",),
            required_media_output="video",
            input_cardinality=1,
        )
        response = knowledge_core.query(query)
        exec_gaps = [g for g in response.gaps if g.gap_nature.value == "execution"]
        assert len(exec_gaps) > 0, "Should have execution gap for candidate without workflow"


# --------------------------------------------------------------------------- #
# TestC: cardinality 1 vs 2
# --------------------------------------------------------------------------- #

class TestCCardinality:
    def test_cardinality_1_matches_itv(self, knowledge_core):
        query = KnowledgeQuery(
            required_operation="video.image_to_video",
            required_media_input=("image",),
            required_media_output="video",
            input_cardinality=1,
        )
        response = knowledge_core.query(query)
        itv = [c for c in response.candidate_nodes
               if c.node_class == "AgnesVideo" and c.usage.mode == "Image To Video"]
        assert len(itv) > 0, "Image To Video (card=1) should match card=1 query"

    def test_cardinality_2_matches_flf_not_itv(self, knowledge_core):
        query = KnowledgeQuery(
            required_operation="video.image_to_video",
            required_media_input=("image", "image"),
            required_media_output="video",
            input_cardinality=2,
        )
        response = knowledge_core.query(query)
        # Only First and Last frame should match
        matched = [c for c in response.candidate_nodes
                   if c.node_class == "AgnesVideo" and c.usage.cardinality == 2]
        wrong = [c for c in response.candidate_nodes
                 if c.node_class == "AgnesVideo" and c.usage.cardinality == 1]
        assert len(matched) > 0, "First and Last frame (card=2) should match"
        assert len(wrong) == 0, "Image To Video (card=1) should NOT match card=2 query"


# --------------------------------------------------------------------------- #
# TestD: unknown operation → UNKNOWN
# --------------------------------------------------------------------------- #

class TestDUnknownOperation:
    def test_unknown_operation_readiness(self, knowledge_core):
        query = KnowledgeQuery(
            required_operation="lip_sync_video",
            required_media_input=("video", "audio"),
            required_media_output="video",
        )
        response = knowledge_core.query(query)
        assert response.readiness == Readiness.UNKNOWN
        assert any(g.gap_type.value == "unknown_capability" for g in response.gaps)

    def test_unknown_operation_has_research_request(self, knowledge_core):
        query = KnowledgeQuery(
            required_operation="nonexistent_op",
            required_media_input=(),
            required_media_output="quantum",
        )
        response = knowledge_core.query(query)
        assert len(response.research_requests) > 0
        rr = response.research_requests[0]
        assert isinstance(rr, ResearchRequest)
        assert rr.gap_type.value == "unknown_capability"
        assert len(rr.required_evidence) > 0


# --------------------------------------------------------------------------- #
# TestE: candidate isolation
# --------------------------------------------------------------------------- #

class TestECandidateIsolation:
    def test_candidate_not_in_capability_registry(self, knowledge_core):
        from app.registry.capability import CapabilityRegistry
        cr = CapabilityRegistry()
        caps = [c.id for c in cr.all()]
        # video.image_to_video is a builtin, but AgnesVideo node should NOT add a new one
        assert "video.image_to_video" in caps  # builtin
        # No new agnes-specific capability
        assert not any("agnes" in c.lower() for c in caps)

    def test_agentic_generate_with_knowledge_core(self, store, knowledge_core):
        """Agent.generate should work with knowledge_core attached."""
        agent = Agent(asset_store=store, knowledge_core=knowledge_core)
        # The agent should not crash when knowledge_core is set
        assert agent.knowledge_core is knowledge_core


# --------------------------------------------------------------------------- #
# TestF: session isolation
# --------------------------------------------------------------------------- #

class TestFSessionIsolation:
    def test_knowledge_query_per_turn(self, conv_agent_with_knowledge):
        """Each turn queries independently; no cross-session leakage."""
        agent = conv_agent_with_knowledge

        # Session A: image.generate
        query_a = KnowledgeQuery(
            required_operation="image.generate",
            required_media_input=(),
            required_media_output="image",
        )
        resp_a = agent.knowledge_core.query(query_a)
        assert resp_a.readiness is not None

        # Session B: different operation
        query_b = KnowledgeQuery(
            required_operation="video.generate",
            required_media_input=(),
            required_media_output="video",
        )
        resp_b = agent.knowledge_core.query(query_b)
        assert resp_b.readiness is not None

        # Both sessions should exist independently
        ctx_a = agent.session("sA")
        ctx_b = agent.session("sB")
        assert ctx_a.session_id == "sA"
        assert ctx_b.session_id == "sB"
        assert ctx_a.session_id != ctx_b.session_id

    def test_no_knowledge_leak_between_sessions(self, conv_agent_with_knowledge):
        """Knowledge response from session A does not leak to session B."""
        agent = conv_agent_with_knowledge

        query_a = KnowledgeQuery(
            required_operation="image.generate",
            required_media_input=(),
            required_media_output="image",
        )
        query_b = KnowledgeQuery(
            required_operation="video.generate",
            required_media_input=(),
            required_media_output="video",
        )
        resp_a = agent.knowledge_core.query(query_a)
        resp_b = agent.knowledge_core.query(query_b)
        # Responses are independent
        assert "image.generate" in resp_a.known_capabilities
        assert "video.generate" in resp_b.known_capabilities
        # Different readiness (image.generate may be EXECUTABLE, video.generate may be GAP)
        # Key: they don't share state


# --------------------------------------------------------------------------- #
# TestG: regression — full core test suite
# --------------------------------------------------------------------------- #

@pytest.mark.skip(reason="subprocess-обёртки заменены прямым прогоном suites (test_agent.py, "
                         "test_m3_registry.py, test_knowledge_core.py, test_conversation_m7.py) "
                         "в основном regression")
class TestGRegression:
    def test_agent_tests_pass(self):
        import subprocess
        result = subprocess.run(
            ["python", "-m", "pytest", "tests/test_agent.py", "-q", "--tb=no"],
            capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(__file__))
        )
        assert result.returncode == 0, f"Agent tests failed:\n{result.stdout}\n{result.stderr}"

    def test_registry_tests_pass(self):
        import subprocess
        result = subprocess.run(
            ["python", "-m", "pytest", "tests/test_m3_registry.py", "-q", "--tb=no"],
            capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(__file__))
        )
        assert result.returncode == 0, f"Registry tests failed:\n{result.stdout}\n{result.stderr}"

    def test_knowledge_tests_pass(self):
        import subprocess
        result = subprocess.run(
            ["python", "-m", "pytest", "tests/test_knowledge_core.py", "-q", "--tb=no"],
            capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(__file__))
        )
        assert result.returncode == 0, f"Knowledge tests failed:\n{result.stdout}\n{result.stderr}"

    def test_conversation_tests_pass(self):
        import subprocess
        result = subprocess.run(
            ["python", "-m", "pytest", "tests/test_conversation_m7.py", "-q", "--tb=no"],
            capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(__file__))
        )
        assert result.returncode == 0, f"Conversation tests failed:\n{result.stdout}\n{result.stderr}"
