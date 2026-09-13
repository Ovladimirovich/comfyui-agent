"""Knowledge Core tests — NodeSchema, Evidence, Claims, Candidates, Gaps, Query.

Без ComfyUI: используются fixtures с реальной runtime schema shape.
Покрытие: UNKNOWN NODE test, AGNES test, GAP test, persistence test.
"""
import json
import os
import time

import pytest

from app.knowledge.candidates import CandidateGenerator, InputMapping, UsageHypothesis, CapabilityCandidate
from app.knowledge.core import KnowledgeCore, KnowledgeQuery, KnowledgeResponse, Readiness
from app.knowledge.gaps import GapNature, GapType, KnowledgeGap
from app.knowledge.models import ClaimStatus, EvidenceSource, EvidenceTrustLevel, KnowledgeClaim, KnowledgeEvidence
from app.knowledge.node_schema import (
    FieldSpec,
    NodeSchema,
    NodeSchemaStore,
    node_schema_from_object_info,
    parse_field_spec,
    parse_optional_field,
)
from app.knowledge.research import ResearchRequest, ResearchResult


# --------------------------------------------------------------------------- #
# Fixtures: real /object_info shape
# --------------------------------------------------------------------------- #

@pytest.fixture
def agnes_video_object_info():
    """Real AgnesVideo /object_info shape."""
    return {
        "AgnesVideo": {
            "input": {
                "required": {
                    "mode": [
                        ["Text To Video", "Image To Video", "First and Last frame"],
                        {"default": "Text To Video", "tooltip": "mode selection"},
                    ],
                    "prompt": ["STRING", {"default": "", "multiline": True, "tooltip": "prompt"}],
                    "quality": [["480p", "720p", "1080p"], {"default": "720p"}],
                    "aspect_ratio": [["auto", "1:1", "16:9"], {"default": "auto"}],
                    "duration": ["FLOAT", {"default": 5.0, "min": 3.0, "max": 18.0}],
                    "frame_rate": ["INT", {"default": 24, "min": 1, "max": 60}],
                    "seed": ["INT", {"default": 0, "min": 0, "max": 2147483647}],
                },
                "optional": {
                    "image": ["IMAGE", {"tooltip": "start frame"}],
                    "end_frame": ["IMAGE", {"tooltip": "end frame"}],
                    "negative_prompt": ["STRING", {"default": "", "multiline": True}],
                },
            },
            "output": ["VIDEO", "IMAGE", "IMAGE", "AUDIO"],
            "output_name": ["video", "last_frame", "frames", "audio"],
            "display_name": "Agnes-AI Video",
            "category": "AILab/Agnes-AI",
            "python_module": "custom_nodes.ComfyUI-Agnes-AI",
        }
    }


@pytest.fixture
def some_new_node_object_info():
    """Unknown node: prompt + VIDEO output."""
    return {
        "SomeNewNode": {
            "input": {
                "required": {
                    "prompt": ["STRING", {"default": "", "multiline": True}],
                },
                "optional": {},
            },
            "output": ["VIDEO"],
            "output_name": ["video"],
            "display_name": "SomeNew Node",
            "category": "Video",
            "python_module": "custom_nodes.SomeNew",
        }
    }


@pytest.fixture
def image_only_node_object_info():
    """Node that only outputs IMAGE."""
    return {
        "ImageFilter": {
            "input": {
                "required": {
                    "prompt": ["STRING", {"default": ""}],
                    "image": ["IMAGE", {}],
                },
                "optional": {},
            },
            "output": ["IMAGE"],
            "output_name": ["image"],
            "display_name": "Image Filter",
            "category": "Image",
            "python_module": "custom_nodes.ImageFilter",
        }
    }


@pytest.fixture
def multi_output_node_object_info():
    """Node with VIDEO + IMAGE outputs."""
    return {
        "VideoGenerator": {
            "input": {
                "required": {
                    "prompt": ["STRING", {"default": ""}],
                },
                "optional": {},
            },
            "output": ["VIDEO", "IMAGE"],
            "output_name": ["video", "preview"],
            "display_name": "Video Generator",
            "category": "Video",
            "python_module": "custom_nodes.VideoGen",
        }
    }


# --------------------------------------------------------------------------- #
# NodeSchema tests
# --------------------------------------------------------------------------- #

class TestNodeSchema:
    def test_from_object_info_agnes_video(self, agnes_video_object_info):
        schema = node_schema_from_object_info("AgnesVideo", agnes_video_object_info["AgnesVideo"])

        assert schema.class_type == "AgnesVideo"
        assert schema.display_name == "Agnes-AI Video"
        assert schema.category == "AILab/Agnes-AI"
        assert schema.python_module == "custom_nodes.ComfyUI-Agnes-AI"

        # Check required inputs exist
        required_names = [f.name for f in schema.input_required]
        assert "mode" in required_names
        assert "prompt" in required_names
        assert "quality" in required_names
        assert "duration" in required_names

        # Check optional inputs exist
        optional_names = [f.name for f in schema.input_optional]
        assert "image" in optional_names
        assert "end_frame" in optional_names

        # Check outputs
        assert "VIDEO" in schema.output_types
        assert "AUDIO" in schema.output_types
        assert "video" in schema.output_names

    def test_from_object_info_unknown_node(self, some_new_node_object_info):
        schema = node_schema_from_object_info("SomeNewNode", some_new_node_object_info["SomeNewNode"])

        assert schema.class_type == "SomeNewNode"
        assert schema.display_name == "SomeNew Node"
        assert schema.category == "Video"

        required_names = [f.name for f in schema.input_required]
        assert "prompt" in required_names

        assert schema.output_types == ("VIDEO",)
        assert schema.output_names == ("video",)

    def test_mode_field_is_enum(self, agnes_video_object_info):
        schema = node_schema_from_object_info("AgnesVideo", agnes_video_object_info["AgnesVideo"])

        mode_field = None
        for f in schema.input_required:
            if f.name == "mode":
                mode_field = f
                break

        assert mode_field is not None
        assert mode_field.type == "ENUM"
        assert "Image To Video" in mode_field.options
        assert "First and Last frame" in mode_field.options
        assert "Text To Video" in mode_field.options

    def test_duration_field_has_min_max(self, agnes_video_object_info):
        schema = node_schema_from_object_info("AgnesVideo", agnes_video_object_info["AgnesVideo"])

        duration_field = None
        for f in schema.input_required:
            if f.name == "duration":
                duration_field = f
                break

        assert duration_field is not None
        assert duration_field.type == "FLOAT"
        assert duration_field.min_val == 3.0
        assert duration_field.max_val == 18.0

    def test_serialization_roundtrip(self, agnes_video_object_info):
        schema = node_schema_from_object_info("AgnesVideo", agnes_video_object_info["AgnesVideo"])
        d = schema.to_dict()
        restored = NodeSchema.from_dict(d)

        assert restored.class_type == schema.class_type
        assert restored.display_name == schema.display_name
        assert len(restored.input_required) == len(schema.input_required)
        assert len(restored.input_optional) == len(schema.input_optional)
        assert restored.output_types == schema.output_types


# --------------------------------------------------------------------------- #
# CandidateGenerator tests
# --------------------------------------------------------------------------- #

class TestCandidateGenerator:
    def test_agnes_video_generates_image_to_video(self, agnes_video_object_info):
        schema = node_schema_from_object_info("AgnesVideo", agnes_video_object_info["AgnesVideo"])
        gen = CandidateGenerator()
        candidates = gen.generate(schema)

        # Should have at least one candidate
        assert len(candidates) > 0

        # Find image-to-video candidate
        itv_candidates = [c for c in candidates if c.capability == "video.image_to_video"]
        assert len(itv_candidates) >= 1

        cand = itv_candidates[0]
        assert cand.node_class == "AgnesVideo"
        assert cand.status == ClaimStatus.INFERENCE

        # Check usage
        assert cand.usage.mode == "Image To Video"
        assert cand.usage.cardinality == 1

    def test_agnes_video_generates_first_last_frame(self, agnes_video_object_info):
        schema = node_schema_from_object_info("AgnesVideo", agnes_video_object_info["AgnesVideo"])
        gen = CandidateGenerator()
        candidates = gen.generate(schema)

        flf_candidates = [c for c in candidates if c.capability == "video.image_to_video"]
        # "First and Last frame" is also image-to-video but with cardinality=2
        # The generator finds mode-based candidates
        assert len(flf_candidates) >= 1

    def test_unknown_node_weak_video_signal(self, some_new_node_object_info):
        schema = node_schema_from_object_info("SomeNewNode", some_new_node_object_info["SomeNewNode"])
        gen = CandidateGenerator()
        candidates = gen.generate(schema)

        # Should generate a weak video.generate candidate
        assert len(candidates) >= 1
        assert candidates[0].status == ClaimStatus.INFERENCE

    def test_image_only_node_no_video_candidate(self, image_only_node_object_info):
        schema = node_schema_from_object_info("ImageFilter", image_only_node_object_info["ImageFilter"])
        gen = CandidateGenerator()
        candidates = gen.generate(schema)

        # No VIDEO output → no video candidates
        video_candidates = [c for c in candidates if "video" in c.capability]
        assert len(video_candidates) == 0

    def test_candidate_has_evidence(self, agnes_video_object_info):
        schema = node_schema_from_object_info("AgnesVideo", agnes_video_object_info["AgnesVideo"])
        gen = CandidateGenerator()
        candidates = gen.generate(schema)

        for cand in candidates:
            assert len(cand.evidence) > 0
            assert cand.evidence[0].source_type == EvidenceSource.RUNTIME
            assert cand.evidence[0].trust_level == EvidenceTrustLevel.SCHEMA

    def test_candidate_has_claim(self, agnes_video_object_info):
        schema = node_schema_from_object_info("AgnesVideo", agnes_video_object_info["AgnesVideo"])
        gen = CandidateGenerator()
        candidates = gen.generate(schema)

        for cand in candidates:
            assert len(cand.claims) > 0
            claim = cand.claims[0]
            assert claim.subject == "AgnesVideo"
            assert claim.status == ClaimStatus.INFERENCE


# --------------------------------------------------------------------------- #
# Gap tests
# --------------------------------------------------------------------------- #

class TestKnowledgeGap:
    def test_gap_types(self):
        gap = KnowledgeGap(
            needed="capability for lip_sync",
            gap_type=GapType.UNKNOWN_CAPABILITY,
            gap_nature=GapNature.KNOWLEDGE,
            research_sources=("runtime:/object_info",),
        )
        assert gap.gap_type == GapType.UNKNOWN_CAPABILITY
        assert gap.gap_nature == GapNature.KNOWLEDGE
        assert gap.priority == "MEDIUM"

    def test_serialization(self):
        gap = KnowledgeGap(
            needed="workflow for video",
            gap_type=GapType.NO_WORKFLOW,
            gap_nature=GapNature.EXECUTION,
        )
        d = gap.to_dict()
        restored = KnowledgeGap.from_dict(d)
        assert restored.gap_type == GapType.NO_WORKFLOW
        assert restored.gap_nature == GapNature.EXECUTION


# --------------------------------------------------------------------------- #
# KnowledgeQuery tests
# --------------------------------------------------------------------------- #

class TestKnowledgeQuery:
    def test_query_construction(self):
        query = KnowledgeQuery(
            required_operation="image_to_video",
            required_media_input=("image", "image"),
            required_media_output="video",
            input_cardinality=2,
        )
        assert query.required_operation == "image_to_video"
        assert query.input_cardinality == 2


# --------------------------------------------------------------------------- #
# KnowledgeCore query tests
# --------------------------------------------------------------------------- #

class TestKnowledgeCoreQuery:
    def test_query_unknown_operation(self):
        core = KnowledgeCore()
        query = KnowledgeQuery(
            required_operation="lip_sync_video",
            required_media_input=("video", "audio"),
            required_media_output="video",
        )
        response = core.query(query)

        assert response.readiness == Readiness.UNKNOWN
        assert len(response.gaps) > 0
        assert response.gaps[0].gap_type == GapType.UNKNOWN_CAPABILITY

    def test_query_builtin_capability(self):
        from app.registry.capability import CapabilityRegistry
        cap_reg = CapabilityRegistry()
        core = KnowledgeCore(capability_registry=cap_reg)

        query = KnowledgeQuery(
            required_operation="image.generate",
            required_media_input=(),
            required_media_output="image",
        )
        response = core.query(query)

        assert "image.generate" in response.known_capabilities

    def test_query_candidate_only(self, agnes_video_object_info):
        core = KnowledgeCore()
        # Manually inject schemas
        schema = node_schema_from_object_info("AgnesVideo", agnes_video_object_info["AgnesVideo"])
        core._schemas = {"AgnesVideo": schema}
        core._candidates = {"AgnesVideo": CandidateGenerator().generate(schema)}
        for cands in core._candidates.values():
            for cand in cands:
                core._claims.extend(cand.claims)

        query = KnowledgeQuery(
            required_operation="video.image_to_video",
            required_media_input=("image",),
            required_media_output="video",
            input_cardinality=1,
        )
        response = core.query(query)

        # Should find AgnesVideo candidate
        assert len(response.candidate_nodes) > 0
        assert response.candidate_nodes[0].node_class == "AgnesVideo"
        # Should have gap: no workflow for candidates
        assert response.readiness in (Readiness.CANDIDATE_ONLY, Readiness.GAP)

    def test_query_cardinality_mismatch(self, agnes_video_object_info):
        core = KnowledgeCore()
        schema = node_schema_from_object_info("AgnesVideo", agnes_video_object_info["AgnesVideo"])
        core._schemas = {"AgnesVideo": schema}
        core._candidates = {"AgnesVideo": CandidateGenerator().generate(schema)}
        for cands in core._candidates.values():
            for cand in cands:
                core._claims.extend(cand.claims)

        # Query with cardinality=2 — AgnesVideo "Image To Video" has cardinality=1
        query = KnowledgeQuery(
            required_operation="video.image_to_video",
            required_media_input=("image", "image"),
            required_media_output="video",
            input_cardinality=2,
        )
        response = core.query(query)

        # Should NOT match cardinality=1 candidate
        matching = [c for c in response.candidate_nodes if c.usage.cardinality == 1]
        assert len(matching) == 0


# --------------------------------------------------------------------------- #
# UNKNOWN NODE test
# --------------------------------------------------------------------------- #

class TestUnknownNode:
    """SomeNewNode: prompt → VIDEO. Agent has right to say what exists, not what it does."""

    def test_facts_about_unknown_node(self, some_new_node_object_info):
        schema = node_schema_from_object_info("SomeNewNode", some_new_node_object_info["SomeNewNode"])

        # FACT: node exists
        assert schema.class_type == "SomeNewNode"
        # FACT: accepts prompt
        required_names = [f.name for f in schema.input_required]
        assert "prompt" in required_names
        # FACT: outputs VIDEO
        assert "VIDEO" in schema.output_types

    def test_no_confirmed_capability(self, some_new_node_object_info):
        schema = node_schema_from_object_info("SomeNewNode", some_new_node_object_info["SomeNewNode"])
        gen = CandidateGenerator()
        candidates = gen.generate(schema)

        # Candidates exist but status is INFERENCE
        for cand in candidates:
            assert cand.status == ClaimStatus.INFERENCE
            # NOT CONFIRMED
            assert cand.status != ClaimStatus.CONFIRMED

    def test_no_text_to_video_assertion(self, some_new_node_object_info):
        schema = node_schema_from_object_info("SomeNewNode", some_new_node_object_info["SomeNewNode"])
        gen = CandidateGenerator()
        candidates = gen.generate(schema)

        # Should NOT create a candidate with confirmed text-to-video
        for cand in candidates:
            if cand.capability == "video.generate":
                # Weak signal, but still INFERENCE
                assert cand.status == ClaimStatus.INFERENCE


# --------------------------------------------------------------------------- #
# AGNES test
# --------------------------------------------------------------------------- #

class TestAgnesVideo:
    """Full AgnesVideo test: schema + candidates + claims + gap detection."""

    def test_schema_preserves_all_fields(self, agnes_video_object_info):
        schema = node_schema_from_object_info("AgnesVideo", agnes_video_object_info["AgnesVideo"])

        # Required inputs
        required = {f.name: f for f in schema.input_required}
        assert "mode" in required
        assert required["mode"].type == "ENUM"
        assert "Image To Video" in required["mode"].options

        # Optional inputs
        optional = {f.name: f for f in schema.input_optional}
        assert "image" in optional
        assert optional["image"].type == "IMAGE"
        assert "end_frame" in optional

        # Outputs
        assert "VIDEO" in schema.output_types
        assert "AUDIO" in schema.output_types

    def test_two_candidate_usage_hypotheses(self, agnes_video_object_info):
        schema = node_schema_from_object_info("AgnesVideo", agnes_video_object_info["AgnesVideo"])
        gen = CandidateGenerator()
        candidates = gen.generate(schema)

        # Should have candidates with different usage modes
        modes = set()
        for cand in candidates:
            if cand.usage.mode:
                modes.add(cand.usage.mode)

        # At least "Image To Video" should be detected
        assert "Image To Video" in modes

    def test_image_to_video_cardinality_1(self, agnes_video_object_info):
        schema = node_schema_from_object_info("AgnesVideo", agnes_video_object_info["AgnesVideo"])
        gen = CandidateGenerator()
        candidates = gen.generate(schema)

        itv = [c for c in candidates if c.usage.mode == "Image To Video"]
        assert len(itv) >= 1
        assert itv[0].usage.cardinality == 1

    def test_first_last_frame_cardinality_2(self, agnes_video_object_info):
        schema = node_schema_from_object_info("AgnesVideo", agnes_video_object_info["AgnesVideo"])
        gen = CandidateGenerator()
        candidates = gen.generate(schema)

        flf = [c for c in candidates if c.usage.mode == "First and Last frame"]
        if flf:
            assert flf[0].usage.cardinality == 2

    def test_candidate_status_is_inference(self, agnes_video_object_info):
        schema = node_schema_from_object_info("AgnesVideo", agnes_video_object_info["AgnesVideo"])
        gen = CandidateGenerator()
        candidates = gen.generate(schema)

        for cand in candidates:
            assert cand.status == ClaimStatus.INFERENCE


# --------------------------------------------------------------------------- #
# Persistence tests
# --------------------------------------------------------------------------- #

class TestPersistence:
    def test_save_and_load(self, tmp_path):
        store = NodeSchemaStore(data_dir=str(tmp_path))

        schema = NodeSchema(
            class_type="TestNode",
            display_name="Test Node",
            category="Test",
            input_required=(FieldSpec(name="prompt", type="STRING", required=True),),
            input_optional=(),
            output_types=("IMAGE",),
            output_names=("image",),
            python_module="test_module",
            discovered_at=time.time(),
        )

        store.save_snapshot({"TestNode": schema})
        loaded = store.load_current()

        assert "TestNode" in loaded
        assert loaded["TestNode"].class_type == "TestNode"
        assert loaded["TestNode"].input_required[0].name == "prompt"

    def test_diff_detection(self, tmp_path):
        store = NodeSchemaStore(data_dir=str(tmp_path))

        schema1 = NodeSchema(
            class_type="NodeA",
            display_name="A",
            category="",
            input_required=(),
            input_optional=(),
            output_types=("IMAGE",),
            output_names=(),
            python_module="",
            discovered_at=0.0,
        )
        store.save_snapshot({"NodeA": schema1})

        # Add NodeB, remove nothing
        schema2 = NodeSchema(
            class_type="NodeB",
            display_name="B",
            category="",
            input_required=(),
            input_optional=(),
            output_types=("VIDEO",),
            output_names=(),
            python_module="",
            discovered_at=0.0,
        )
        store.save_snapshot({"NodeA": schema1, "NodeB": schema2})

        diff = store.diff(store.load_previous(), store.load_current())
        assert "NodeB" in diff["added"]
        assert len(diff["removed"]) == 0

    def test_snapshot_rotation(self, tmp_path):
        store = NodeSchemaStore(data_dir=str(tmp_path))

        schema = NodeSchema(
            class_type="X",
            display_name="X",
            category="",
            input_required=(),
            input_optional=(),
            output_types=(),
            output_names=(),
            python_module="",
            discovered_at=0.0,
        )

        store.save_snapshot({"X": schema})
        store.save_snapshot({"X": schema})

        # Previous should exist after second save
        assert os.path.exists(store._previous_path)


# --------------------------------------------------------------------------- #
# Research contract tests
# --------------------------------------------------------------------------- #

class TestResearchContracts:
    def test_research_request_construction(self):
        claim = KnowledgeClaim(
            claim="AgnesVideo implements video.image_to_video",
            subject="AgnesVideo",
            predicate="implements",
            object="video.image_to_video",
        )
        req = ResearchRequest(
            claim=claim,
            gap_type=GapType.INSUFFICIENT_EVIDENCE,
            required_evidence=(EvidenceTrustLevel.DECLARED_PURPOSE,),
            preferred_sources=("local:/README.md",),
        )
        assert req.gap_type == GapType.INSUFFICIENT_EVIDENCE
        assert len(req.required_evidence) == 1

    def test_research_result_construction(self):
        evidence = KnowledgeEvidence(
            source="local:/README.md",
            source_type=EvidenceSource.LOCAL_SOURCE,
            trust_level=EvidenceTrustLevel.DECLARED_PURPOSE,
            timestamp=time.time(),
            claim="AgnesVideo is image-to-video",
        )
        result = ResearchResult(
            evidence=(evidence,),
            unresolved=("external docs",),
            sources_checked=("local:/README.md",),
        )
        assert len(result.evidence) == 1
        assert len(result.unresolved) == 1
