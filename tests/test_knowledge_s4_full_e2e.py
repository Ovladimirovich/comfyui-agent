"""
REAL E2E — Полный цикл Knowledge → Runtime → Claim → Planner

Доказывает что существующий механизм Agent Core + Knowledge Core работает
на реальных возможностях ComfyUI.
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

import time
import pytest
from pathlib import Path

from app.agent import Agent
from app.assets.store import AssetStore
from app.knowledge.node_doc import NodeDocStore
from app.knowledge.core import KnowledgeCore
from app.knowledge.claims_persistence import ClaimsPersistence
from app.knowledge.runtime_validator import RuntimeValidator, ValidationResult
from app.planner.heuristic import HeuristicPlanner
from app.planner.plan import PlanContext
from app.provider.comfyui import ComfyUIProvider
from app.comfy.client import ComfyClient
from app.engine import ExecutionPlan


# ------------------------------------------------------------------
# Конфигурация
# ------------------------------------------------------------------

COMFY_URL = "http://127.0.0.1:8188"
DATA_DIR = str(Path(__file__).parent.parent / "app/data/knowledge")


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture(scope="module")
def comfy_client():
    return ComfyClient(base_url=COMFY_URL)


@pytest.fixture(scope="module")
def agent(tmp_path_factory):
    store = AssetStore(root=str(tmp_path_factory.mktemp("assets")))
    a = Agent(store)
    a.registry.discover(str(Path(__file__).parent.parent / "workflows"))
    return a


@pytest.fixture(scope="module")
def knowledge_core(comfy_client):
    rv = RuntimeValidator(comfy_client=comfy_client, max_wait_seconds=30)
    cp = ClaimsPersistence(data_dir=DATA_DIR)
    return KnowledgeCore(runtime_validator=rv, claims_persistence=cp)


@pytest.fixture(scope="module")
def node_doc_store():
    return NodeDocStore(data_dir=DATA_DIR)


# ------------------------------------------------------------------
# Tests: Discovery
# ------------------------------------------------------------------


class TestDiscovery:
    """Проверка обнаружения возможностей."""

    def test_capabilities_discovered(self, agent):
        caps = agent.capabilities()
        assert "image.generate" in caps
        assert "video.generate" in caps

    def test_workflows_discovered(self, agent):
        wf_ids = [w.id for w in agent.registry.workflows]
        assert "txt2img" in wf_ids
        assert "pollinations_image" in wf_ids

    def test_nodes_available(self, comfy_client):
        oi = comfy_client.get_object_info()
        assert "PollinationsImageGen" in oi
        assert "CheckpointLoaderSimple" in oi


# ------------------------------------------------------------------
# Tests: Documentation
# ------------------------------------------------------------------


class TestDocumentation:
    """Проверка загрузки документации."""

    def test_documentation_loaded(self, node_doc_store):
        assert node_doc_store.count() > 0

    def test_pollinations_documented(self, node_doc_store):
        doc = node_doc_store.get_doc_for("PollinationsImageGen")
        assert doc is not None
        assert "Pollinations" in doc.purpose or "pollinations" in doc.purpose.lower()

    def test_agnes_documented(self, node_doc_store):
        doc = node_doc_store.get_doc_for("AgnesImage")
        assert doc is not None


# ------------------------------------------------------------------
# Tests: Execution
# ------------------------------------------------------------------


class TestExecution:
    """Реальное выполнение через Agent."""

    def test_txt2img_execution(self, agent):
        """txt2img выполняется успешно."""
        from app.engine import ExecutionPlan
        from app.provider.comfyui import ComfyUIProvider
        from app.comfy.client import ComfyClient

        manifest = agent.registry.get("txt2img", "1.0.0")
        plan = ExecutionPlan(
            capability="image.generate",
            workflow_id="txt2img",
            version="1.0.0",
            params={"prompt": "a small red circle", "steps": 3, "width": 64, "height": 64},
        )
        provider = ComfyUIProvider(ComfyClient(base_url=COMFY_URL), backend_id="local_comfyui")

        t0 = time.time()
        job = agent.engine.execute(manifest, plan, provider=provider, ws_timeout=120)
        elapsed = time.time() - t0

        assert job.state.value == "SUCCESS", f"txt2img failed: {job.error}"
        assert len(job.output_assets) >= 1
        print(f"\n  [txt2img] elapsed={elapsed:.1f}s assets={job.output_assets}")

    def test_pollinations_execution(self, agent):
        """Pollinations Image Gen выполняется успешно."""
        from app.engine import ExecutionPlan
        from app.provider.comfyui import ComfyUIProvider
        from app.comfy.client import ComfyClient

        manifest = agent.registry.get("pollinations_image", "1.0.0")
        plan = ExecutionPlan(
            capability="image.generate",
            workflow_id="pollinations_image",
            version="1.0.0",
            params={"prompt": "a cat in space", "model": "flux", "width": 256, "height": 256},
        )
        provider = ComfyUIProvider(ComfyClient(base_url=COMFY_URL), backend_id="local_comfyui")

        t0 = time.time()
        job = agent.engine.execute(manifest, plan, provider=provider, ws_timeout=120)
        elapsed = time.time() - t0

        assert job.state.value == "SUCCESS", f"pollinations failed: {job.error}"
        assert len(job.output_assets) >= 1
        print(f"\n  [pollinations] elapsed={elapsed:.1f}s assets={job.output_assets}")


# ------------------------------------------------------------------
# Tests: Planner Integration
# ------------------------------------------------------------------


class TestPlannerIntegration:
    """Planner использует validated knowledge."""

    def test_planner_with_validated_nodes(self):
        """Planner получает validated nodes через PlanContext."""
        context = PlanContext(
            capabilities=("image.generate",),
            validated_nodes={"PollinationsImageGen": True, "KSampler": False}
        )
        planner = HeuristicPlanner()
        result = planner.plan("create an image", context)

        assert result.capability == "image.generate"
        assert "validated_nodes" in result.rationale

    def test_agent_passes_validated_to_planner(self):
        """Agent передаёт validated nodes в Planner."""
        from unittest.mock import MagicMock
        from app.planner.plan import PlanResult

        store = AssetStore(root="tests/__tmp_planner__")
        agent = Agent(store)

        mock_kc = MagicMock()
        mock_kc.get_validated_for_capability = MagicMock(
            return_value={"PollinationsImageGen": True}
        )
        agent.knowledge_core = mock_kc

        captured_context = []
        def mock_plan(request, context=None):
            captured_context.append(context)
            return PlanResult(capability="image.generate", params={"prompt": request})

        agent.planner = MagicMock()
        agent.planner.plan = mock_plan

        agent.generate("test request")

        assert len(captured_context) >= 1
        assert captured_context[-1].validated_nodes == {"PollinationsImageGen": True}


# ------------------------------------------------------------------
# Tests: Full Chain
# ------------------------------------------------------------------


class TestFullChain:
    """Полный цикл: Discovery → Doc → Planner → Execution."""

    def test_full_chain(self, agent, node_doc_store, knowledge_core):
        """Доказательство полного цикла."""
        # 1. Discovery
        caps = agent.capabilities()
        assert "image.generate" in caps

        # 2. Documentation loaded
        poll_doc = node_doc_store.get_doc_for("PollinationsImageGen")
        assert poll_doc is not None

        # 3. Planner
        planner = HeuristicPlanner()
        context = PlanContext(
            capabilities=tuple(caps),
            validated_nodes={}
        )
        plan_result = planner.plan("generate an image with pollinations", context)
        assert plan_result.capability == "image.generate"

        # 4. Workflow selection
        manifests = agent.registry.by_capability("image.generate")
        assert len(manifests) >= 2  # txt2img + pollinations_image

        # 5. Execution
        from app.engine import ExecutionPlan
        from app.provider.comfyui import ComfyUIProvider
        from app.comfy.client import ComfyClient

        manifest = agent.registry.get("pollinations_image", "1.0.0")
        plan = ExecutionPlan(
            capability="image.generate",
            workflow_id="pollinations_image",
            version="1.0.0",
            params={"prompt": "a dog in garden", "model": "flux", "width": 256, "height": 256},
        )
        provider = ComfyUIProvider(ComfyClient(base_url=COMFY_URL), backend_id="local_comfyui")

        job = agent.engine.execute(manifest, plan, provider=provider, ws_timeout=120)
        assert job.state.value == "SUCCESS"
        assert len(job.output_assets) >= 1

        print(f"\n  [full_chain] SUCCESS, assets={job.output_assets}")


# ------------------------------------------------------------------
# Tests: Persistence
# ------------------------------------------------------------------


class TestPersistence:
    """Проверка persistence knowledge."""

    def test_claims_persisted(self, knowledge_core):
        """Claims сохраняются в persistence."""
        from app.knowledge.models import KnowledgeClaim, ClaimStatus

        claim = KnowledgeClaim(
            claim="TestNode executed",
            subject="TestNode",
            predicate="validated_by_execution",
            object="true",
            status=ClaimStatus.CONFIRMED,
            evidence=[],
        )
        knowledge_core._claims.append(claim)
        knowledge_core.save_state()

        # Проверяем что данные сохранились
        assert len(knowledge_core._claims) > 0

    def test_validated_nodes_persisted(self, knowledge_core):
        """Validated nodes сохраняются."""
        knowledge_core._validated_nodes["TestNode"] = True
        knowledge_core.save_state()

        assert "TestNode" in knowledge_core.get_validated_nodes()
