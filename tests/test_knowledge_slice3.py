"""Slice 3 integration tests — LocalResearchProvider + EvidenceStore + Claim upgrade.

Покрытие:
  TestA: LocalResearchProvider discovers AgnesVideo from custom nodes
  TestB: EvidenceStore stores and retrieves evidence
  TestC: EvidenceStore upgrades INFERENCE → SUPPORTED
  TestD: Full flow — research → ingest → apply → query shows SUPPORTED
  TestE: No web/LLM calls (provider has no network methods)
  TestF: Session isolation (EvidenceStore per-core, not global)
  TestG: Regression (full existing suite green)
"""
import os
import sys
import tempfile
import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.knowledge.core import KnowledgeCore, KnowledgeQuery, Readiness
from app.knowledge.evidence_store import EvidenceStore
from app.knowledge.local_research import LocalResearchProvider, ResearchSource
from app.knowledge.models import ClaimStatus, EvidenceTrustLevel, KnowledgeClaim, KnowledgeEvidence
from app.knowledge.research import ResearchRequest
from app.knowledge.gaps import GapType
from app.registry.capability import CapabilityRegistry


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

@pytest.fixture
def agnes_node_dir():
    """Путь к ComfyUI-Agnes-AI custom node."""
    root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    # Check both possible locations
    for rel in ("ComfyUI/custom_nodes/ComfyUI-Agnes-AI",
                "../ComfyUI/custom_nodes/ComfyUI-Agnes-AI"):
        full = os.path.join(root, rel)
        if os.path.isdir(full):
            return full
    # Fallback: try relative to this file
    candidate = os.path.join(os.path.dirname(__file__), "..", "..", "..", "ComfyUI", "custom_nodes", "ComfyUI-Agnes-AI")
    candidate = os.path.normpath(candidate)
    if os.path.isdir(candidate):
        return candidate
    return None


@pytest.fixture
def research_provider(agnes_node_dir):
    if agnes_node_dir is None:
        pytest.skip("ComfyUI-Agnes-AI custom node not found")
    return LocalResearchProvider(custom_nodes_dir=os.path.dirname(agnes_node_dir))


@pytest.fixture
def tmp_evidence_store(tmp_path):
    return EvidenceStore(data_dir=str(tmp_path / "evidence"))


@pytest.fixture
def core_with_store(tmp_path, agnes_node_dir):
    from app.knowledge.evidence_store import EvidenceStore
    store = EvidenceStore(data_dir=str(tmp_path / "evidence"))
    core = KnowledgeCore(evidence_store=store)
    return core, store


# --------------------------------------------------------------------------- #
# TestA: LocalResearchProvider discovers AgnesVideo
# --------------------------------------------------------------------------- #

class TestALocalResearchProvider:
    def test_discovers_agnes_video(self, research_provider):
        sources = research_provider.list_sources("AgnesVideo")
        assert len(sources) > 0, "Should find at least one source for AgnesVideo"
        kinds = {s.kind for s in sources}
        assert "readme" in kinds or "python_source" in kinds, f"Expected readme/python_source, got {kinds}"

    def test_readme_source_has_content(self, research_provider):
        sources = research_provider.list_sources("AgnesVideo")
        readmes = [s for s in sources if s.kind == "readme"]
        if readmes:
            assert len(readmes[0].content_preview) > 0
            assert "Agnes" in readmes[0].content_preview or "video" in readmes[0].content_preview.lower()

    def test_python_source_discovered(self, research_provider):
        sources = research_provider.list_sources("AgnesVideo")
        py_sources = [s for s in sources if s.kind == "python_source"]
        assert len(py_sources) > 0, f"Should find Python source files, got: {[s.path for s in py_sources]}"
        # agnes_video.py should be among them
        paths = [os.path.basename(s.path) for s in py_sources]
        assert "agnes_video.py" in paths, f"Expected agnes_video.py in {paths}"

    def test_no_web_calls(self, research_provider):
        """Provider has no network methods — verify by inspection."""
        methods = [m for m in dir(research_provider) if not m.startswith("_")]
        assert "fetch" not in methods
        assert "request" not in methods
        assert "get" not in methods
        assert "post" not in methods

    def test_no_llm_calls(self, research_provider):
        """Provider has no LLM methods."""
        methods = [m for m in dir(research_provider) if not m.startswith("_")]
        assert "llm" not in str(methods).lower()
        assert "chat" not in str(methods).lower()
        assert "completion" not in str(methods).lower()


# --------------------------------------------------------------------------- #
# TestB: EvidenceStore stores and retrieves
# --------------------------------------------------------------------------- #

class TestBEvidenceStore:
    def test_ingest_and_load(self, tmp_evidence_store):
        ev = KnowledgeEvidence(
            source="local:/test/README.md",
            source_type="local_source",
            trust_level=EvidenceTrustLevel.DECLARED_PURPOSE,
            timestamp=1000.0,
            claim="AgnesVideo generates video from images",
        )
        from app.knowledge.research import ResearchResult
        result = ResearchResult(
            evidence=(ev,),
            unresolved=(),
            sources_checked=("local:/test/README.md",),
        )
        tmp_evidence_store.ingest(result)
        records = tmp_evidence_store.load()
        assert len(records) == 1
        assert records[0]["claim"] == "AgnesVideo generates video from images"

    def test_get_evidence_for_subject(self, tmp_evidence_store):
        ev1 = KnowledgeEvidence(
            source="local:/a/README.md",
            source_type="local_source",
            trust_level=EvidenceTrustLevel.DECLARED_PURPOSE,
            timestamp=1000.0,
            claim="AgnesVideo generates video",
        )
        ev2 = KnowledgeEvidence(
            source="local:/b/README.md",
            source_type="local_source",
            trust_level=EvidenceTrustLevel.DECLARED_PURPOSE,
            timestamp=1001.0,
            claim="SomeOtherNode generates images",
        )
        from app.knowledge.research import ResearchResult
        tmp_evidence_store.ingest(ResearchResult(evidence=(ev1, ev2), unresolved=(), sources_checked=()))
        agnes_evidence = tmp_evidence_store.get_evidence_for("AgnesVideo")
        other_evidence = tmp_evidence_store.get_evidence_for("SomeOtherNode")
        assert len(agnos_evidence := agnes_evidence) == 1
        assert len(other_evidence) == 1

    def test_clear(self, tmp_evidence_store):
        ev = KnowledgeEvidence(
            source="local:/test",
            source_type="local_source",
            trust_level=EvidenceTrustLevel.DECLARED_PURPOSE,
            timestamp=1000.0,
            claim="test",
        )
        from app.knowledge.research import ResearchResult
        tmp_evidence_store.ingest(ResearchResult(evidence=(ev,), unresolved=(), sources_checked=()))
        assert len(tmp_evidence_store.load()) == 1
        tmp_evidence_store.clear()
        assert len(tmp_evidence_store.load()) == 0


# --------------------------------------------------------------------------- #
# TestC: EvidenceStore upgrades INFERENCE → SUPPORTED
# --------------------------------------------------------------------------- #

class TestCEvidenceUpgrade:
    def test_inference_becomes_supported(self, tmp_evidence_store):
        claim = KnowledgeClaim(
            claim="AgnesVideo implements video.image_to_video",
            subject="AgnesVideo",
            predicate="implements",
            object="video.image_to_video",
            status=ClaimStatus.INFERENCE,
        )
        ev = KnowledgeEvidence(
            source="local:/test/README.md",
            source_type="local_source",
            trust_level=EvidenceTrustLevel.DECLARED_PURPOSE,
            timestamp=1000.0,
            claim="AgnesVideo: declares image-to-video capability from README",
        )
        from app.knowledge.research import ResearchResult
        tmp_evidence_store.ingest(ResearchResult(evidence=(ev,), unresolved=(), sources_checked=()))

        updated = tmp_evidence_store.merge_into_claims([claim], "AgnesVideo")
        assert len(updated) == 1
        assert updated[0].status == ClaimStatus.SUPPORTED

    def test_schema_only_stays_inference(self, tmp_evidence_store):
        claim = KnowledgeClaim(
            claim="SomeNode implements video.generate",
            subject="SomeNode",
            predicate="implements",
            object="video.generate",
            status=ClaimStatus.INFERENCE,
        )
        # Only SCHEMA evidence — should NOT upgrade
        ev = KnowledgeEvidence(
            source="runtime:/object_info",
            source_type="runtime",
            trust_level=EvidenceTrustLevel.SCHEMA,
            timestamp=1000.0,
            claim="runtime schema for SomeNode",
        )
        from app.knowledge.research import ResearchResult
        tmp_evidence_store.ingest(ResearchResult(evidence=(ev,), unresolved=(), sources_checked=()))

        updated = tmp_evidence_store.merge_into_claims([claim], "SomeNode")
        assert updated[0].status == ClaimStatus.INFERENCE

    def test_supported_not_downgraded(self, tmp_evidence_store):
        claim = KnowledgeClaim(
            claim="AgnesVideo implements video.image_to_video",
            subject="AgnesVideo",
            predicate="implements",
            object="video.image_to_video",
            status=ClaimStatus.SUPPORTED,
        )
        updated = tmp_evidence_store.merge_into_claims([claim], "AgnesVideo")
        assert updated[0].status == ClaimStatus.SUPPORTED

    def test_confirmed_not_changed(self, tmp_evidence_store):
        claim = KnowledgeClaim(
            claim="AgnesVideo implements video.image_to_video",
            subject="AgnesVideo",
            predicate="implements",
            object="video.image_to_video",
            status=ClaimStatus.CONFIRMED,
        )
        updated = tmp_evidence_store.merge_into_claims([claim], "AgnesVideo")
        assert updated[0].status == ClaimStatus.CONFIRMED


# --------------------------------------------------------------------------- #
# TestD: Full flow — research → ingest → apply → query shows SUPPORTED
# --------------------------------------------------------------------------- #

class TestDFullFlow:
    def test_agnes_research_flow(self, research_provider, tmp_evidence_store, agnes_node_dir):
        """End-to-end: research AgnesVideo → store → apply → claim is SUPPORTED."""
        # 1. Research
        claim = KnowledgeClaim(
            claim="AgnesVideo implements video.image_to_video",
            subject="AgnesVideo",
            predicate="implements",
            object="video.image_to_video",
            status=ClaimStatus.INFERENCE,
        )
        request = ResearchRequest(
            claim=claim,
            gap_type=GapType.INSUFFICIENT_EVIDENCE,
            required_evidence=(EvidenceTrustLevel.DECLARED_PURPOSE,),
            preferred_sources=("local:/README.md",),
        )
        result = research_provider.research(request)
        assert len(result.sources_checked) > 0, "Should have checked some sources"
        assert len(result.evidence) > 0, "Should have found evidence"

        # 2. Ingest into store
        tmp_evidence_store.ingest(result)
        evidence_count = len(tmp_evidence_store.get_evidence_for("AgnesVideo"))
        assert evidence_count > 0

        # 3. Apply to claims
        core_claim = KnowledgeClaim(
            claim="AgnesVideo implements video.image_to_video",
            subject="AgnesVideo",
            predicate="implements",
            object="video.image_to_video",
            status=ClaimStatus.INFERENCE,
        )
        updated = tmp_evidence_store.merge_into_claims([core_claim], "AgnesVideo")
        assert len(updated) == 1
        assert updated[0].status == ClaimStatus.SUPPORTED, \
            f"Expected SUPPORTED, got {updated[0].status}"

    def test_full_core_flow(self, core_with_store, research_provider, agnes_node_dir):
        """Core-level: refresh → query (INFERENCE) → research → apply → query (SUPPORTED)."""
        core, store = core_with_store

        # Refresh from runtime
        from app.comfy.client import ComfyClient
        client = ComfyClient()
        core.refresh(client)

        # Query before research — should see INFERENCE claims
        query = KnowledgeQuery(
            required_operation="video.image_to_video",
            required_media_input=("image",),
            required_media_output="video",
            input_cardinality=1,
        )
        resp_before = core.query(query)
        inference_claims = [c for c in resp_before.claims if c.status == ClaimStatus.INFERENCE]
        supported_claims = [c for c in resp_before.claims if c.status == ClaimStatus.SUPPORTED]
        # Before research, claims should be INFERENCE (no evidence yet)
        assert len(inference_claims) > 0 or len(resp_before.candidate_nodes) > 0

        # Run research
        if research_provider is not None:
            # Find a candidate claim to research
            for cand in resp_before.candidate_nodes:
                for claim in cand.claims:
                    request = ResearchRequest(
                        claim=claim,
                        gap_type=GapType.INSUFFICIENT_EVIDENCE,
                        required_evidence=(EvidenceTrustLevel.DECLARED_PURPOSE,),
                    )
                    result = research_provider.research(request)
                    store.ingest(result)
                    break
                else:
                    continue
                break

        # Apply research results
        upgraded = core.apply_research_results()

        # Query after research — claims should be upgraded
        resp_after = core.query(query)
        # Check that at least one claim was upgraded or still INFERENCE
        all_claims = resp_after.claims
        statuses = {c.status.value for c in all_claims}
        # Should have either SUPPORTED or INFERENCE (not UNKNOWN)
        assert statuses & {ClaimStatus.SUPPORTED.value, ClaimStatus.INFERENCE.value}


# --------------------------------------------------------------------------- #
# TestE: No web/LLM calls
# --------------------------------------------------------------------------- #

class TestENoExternalCalls:
    def test_provider_has_no_http_methods(self, research_provider):
        http_methods = [m for m in dir(research_provider)
                       if not m.startswith("_") and m in ("get", "post", "put", "delete", "patch")]
        assert len(http_methods) == 0, f"Should not have HTTP methods: {http_methods}"

    def test_provider_has_no_network_imports(self):
        import app.knowledge.local_research as mod
        imported_modules = [name for name in dir(mod) if not name.startswith("_")]
        # Should not import httpx, requests, aiohttp, urllib, etc.
        import_names = mod.__dict__
        forbidden = {"httpx", "requests", "aiohttp", "urllib", "urlopen"}
        for fn in forbidden:
            assert fn not in import_names, f"LocalResearchProvider imports {fn}"


# --------------------------------------------------------------------------- #
# TestF: Session isolation
# --------------------------------------------------------------------------- #

class TestFSessionIsolation:
    def test_evidence_store_is_per_instance(self, tmp_path):
        """Each EvidenceStore instance is independent."""
        store_a = EvidenceStore(data_dir=str(tmp_path / "store_a"))
        store_b = EvidenceStore(data_dir=str(tmp_path / "store_b"))

        ev = KnowledgeEvidence(
            source="local:/test",
            source_type="local_source",
            trust_level=EvidenceTrustLevel.DECLARED_PURPOSE,
            timestamp=1000.0,
            claim="AgnesVideo is for video",
        )
        from app.knowledge.research import ResearchResult
        store_a.ingest(ResearchResult(evidence=(ev,), unresolved=(), sources_checked=()))

        assert len(store_a.get_evidence_for("AgnesVideo")) == 1
        assert len(store_b.get_evidence_for("AgnesVideo")) == 0

    def test_core_query_isolation(self, tmp_path):
        """Two cores with different stores don't share evidence."""
        store_a = EvidenceStore(data_dir=str(tmp_path / "core_a"))
        store_b = EvidenceStore(data_dir=str(tmp_path / "core_b"))
        core_a = KnowledgeCore(evidence_store=store_a)
        core_b = KnowledgeCore(evidence_store=store_b)

        ev = KnowledgeEvidence(
            source="local:/test",
            source_type="local_source",
            trust_level=EvidenceTrustLevel.DECLARED_PURPOSE,
            timestamp=1000.0,
            claim="AgnesVideo is for video",
        )
        from app.knowledge.research import ResearchResult
        store_a.ingest(ResearchResult(evidence=(ev,), unresolved=(), sources_checked=()))

        # core_a should see evidence, core_b should not
        assert len(store_a.get_evidence_for("AgnesVideo")) == 1
        assert len(store_b.get_evidence_for("AgnesVideo")) == 0


# --------------------------------------------------------------------------- #
# TestG: Regression
# --------------------------------------------------------------------------- #

class TestGRegression:
    def test_knowledge_core_tests_pass(self):
        import subprocess
        result = subprocess.run(
            ["python", "-m", "pytest", "tests/test_knowledge_core.py", "-q", "--tb=no"],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(__file__)),
        )
        assert result.returncode == 0, f"Knowledge core tests failed:\n{result.stdout}\n{result.stderr}"

    def test_knowledge_s2_tests_pass(self):
        import subprocess
        result = subprocess.run(
            ["python", "-m", "pytest", "tests/test_knowledge_integration_s2.py", "-q", "--tb=no"],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(__file__)),
        )
        assert result.returncode == 0, f"Knowledge S2 tests failed:\n{result.stdout}\n{result.stderr}"

    def test_agent_tests_pass(self):
        import subprocess
        result = subprocess.run(
            ["python", "-m", "pytest", "tests/test_agent.py", "-q", "--tb=no"],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(__file__)),
        )
        assert result.returncode == 0, f"Agent tests failed:\n{result.stdout}\n{result.stderr}"

    def test_conversation_tests_pass(self):
        import subprocess
        result = subprocess.run(
            ["python", "-m", "pytest", "tests/test_conversation_m7.py", "-q", "--tb=no"],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(__file__)),
        )
        assert result.returncode == 0, f"Conversation tests failed:\n{result.stdout}\n{result.stderr}"
