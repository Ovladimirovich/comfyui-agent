"""S2 integration tests — Template-Based Workflow Synthesis.

Покрытие:
  T1:  Template matching: text→image candidate → text_to_image template
  T2:  Template matching: image→image candidate → image_to_image template
  T3:  Template matching: text→audio candidate → text_to_audio template
  T4:  Template matching: text→video candidate → text_to_video template
  T5:  Template matching: unknown pattern → None
  T6:  Synthesis: PollinationsImageGen (text→image) → valid manifest + workflow
  T7:  Synthesis: AgnesVideo Text To Video → valid manifest + workflow
  T8:  Synthesis preserves output mapping
  T9:  Synthesis preserves required_custom_nodes
  T10: Synthesis preserves model requirements when MODEL input present
  T11: Safety: built-in node → ALLOWED
  T12: Safety: custom node → REQUIRES_CONFIRMATION
  T13: Safety: shell keyword → FORBIDDEN
  T14: Synthesized manifest has provenance metadata
  T15: Safety = FORBIDDEN → synthesis returns FORBIDDEN status
  T16: Knowledge readiness remains advisory (CANDIDATE_ONLY, not auto-EXECUTABLE)
  T17: Existing workflows remain unaffected (regression)
  T18: Template catalog has at least 3 templates
"""
import pytest
from unittest.mock import MagicMock

from app.knowledge.candidates import CapabilityCandidate, UsageHypothesis
from app.knowledge.core import KnowledgeCore, KnowledgeQuery, Readiness
from app.knowledge.gaps import GapType, KnowledgeGap
from app.knowledge.models import ClaimStatus, KnowledgeClaim, KnowledgeEvidence, EvidenceSource, EvidenceTrustLevel
from app.knowledge.node_schema import FieldSpec, NodeSchema
from app.synthesis.template import SafetyClass, WorkflowTemplate, WorkflowSynthesisResult
from app.synthesis.catalog import TEMPLATE_CATALOG, TEXT_TO_IMAGE, IMAGE_TO_IMAGE, TEXT_TO_AUDIO, TEXT_TO_VIDEO
from app.synthesis.selector import select_template, _score_template
from app.synthesis.builder import synthesize_workflow
from app.synthesis.safety import classify_safety


# ------------------------------------------------------------------ #
# Fixtures
# ------------------------------------------------------------------ #


def _make_schema(
    class_type: str,
    output_types: tuple[str, ...],
    required_inputs: tuple[FieldSpec, ...] = (),
    optional_inputs: tuple[FieldSpec, ...] = (),
    category: str = "test",
    python_module: str = "custom_nodes.test",
) -> NodeSchema:
    return NodeSchema(
        class_type=class_type,
        display_name=class_type,
        category=category,
        input_required=required_inputs,
        input_optional=optional_inputs,
        output_types=output_types,
        output_names=tuple(),
        python_module=python_module,
        discovered_at=0.0,
    )


def _make_candidate(
    node_class: str,
    capability: str,
) -> CapabilityCandidate:
    return CapabilityCandidate(
        node_class=node_class,
        capability=capability,
        status=ClaimStatus.INFERENCE,
        usage=UsageHypothesis(description="test"),
    )


# Pre-built schemas
POLLINATIONS_SCHEMA = _make_schema(
    "PollinationsImageGen",
    ("IMAGE", "STRING"),
    required_inputs=(
        FieldSpec("prompt", "STRING", True, default="a cat"),
        FieldSpec("model", "ENUM", True, default="flux", options=("flux", "gptimage")),
        FieldSpec("width", "INT", True, default=1024),
        FieldSpec("height", "INT", True, default=1024),
        FieldSpec("seed", "INT", True, default=42),
    ),
    python_module="custom_nodes.pollinations-byop",
    category="Pollinations/Image",
)

AGNES_SCHEMA = _make_schema(
    "AgnesVideo",
    ("VIDEO", "IMAGE", "IMAGE", "AUDIO"),
    required_inputs=(
        FieldSpec("mode", "ENUM", True, default="Text To Video",
                  options=("Text To Video", "Image To Video", "First and Last frame")),
        FieldSpec("prompt", "STRING", True, default=""),
        FieldSpec("quality", "ENUM", True, default="720p", options=("480p", "720p", "1080p")),
        FieldSpec("duration", "FLOAT", True, default=5.0),
        FieldSpec("frame_rate", "INT", True, default=24),
        FieldSpec("seed", "INT", True, default=0),
    ),
    optional_inputs=(
        FieldSpec("image", "IMAGE", False),
        FieldSpec("end_frame", "IMAGE", False),
    ),
    python_module="custom_nodes.ComfyUI-Agnes-AI",
    category="AILab/Agnes-AI",
)

IMAGE_SCALE_SCHEMA = _make_schema(
    "ImageScale",
    ("IMAGE",),
    required_inputs=(
        FieldSpec("image", "IMAGE", True),
        FieldSpec("upscale_method", "ENUM", True, options=("lanczos", "bilinear")),
        FieldSpec("width", "INT", True, default=512),
        FieldSpec("height", "INT", True, default=512),
    ),
    python_module="nodes",
    category="image/upscaling",
)

BUILTIN_SCHEMA = _make_schema(
    "BuiltinNode",
    ("IMAGE",),
    required_inputs=(FieldSpec("prompt", "STRING", True, default="test"),),
    python_module="nodes",
    category="image",
)


# ------------------------------------------------------------------ #
# T1-T5: Template matching
# ------------------------------------------------------------------ #


class TestTemplateSelection:
    def test_text_to_image_match(self):
        """T1: PollinationsImageGen → text_to_image template."""
        cand = _make_candidate("PollinationsImageGen", "image.generate")
        tmpl = select_template(cand, POLLINATIONS_SCHEMA)
        assert tmpl is not None
        assert tmpl.template_id == "s2_text_to_image"

    def test_image_to_image_match(self):
        """T2: ImageScale → image_to_image template."""
        cand = _make_candidate("ImageScale", "image.edit")
        tmpl = select_template(cand, IMAGE_SCALE_SCHEMA)
        assert tmpl is not None
        assert tmpl.template_id == "s2_image_to_image"

    def test_text_to_audio_match(self):
        """T3: text→audio candidate matches text_to_audio."""
        schema = _make_schema(
            "MyAudioGen", ("AUDIO",),
            required_inputs=(FieldSpec("prompt", "STRING", True, default="beat"),),
            python_module="custom_nodes.test",
        )
        cand = _make_candidate("MyAudioGen", "audio.generate")
        tmpl = select_template(cand, schema)
        assert tmpl is not None
        assert tmpl.template_id == "s2_text_to_audio"

    def test_text_to_video_match(self):
        """T4: AgnesVideo Text To Video → text_to_video template."""
        cand = _make_candidate("AgnesVideo", "video.generate")
        tmpl = select_template(cand, AGNES_SCHEMA)
        assert tmpl is not None
        assert tmpl.template_id == "s2_text_to_video"

    def test_no_match_unknown_pattern(self):
        """T5: Unknown pattern → None."""
        schema = _make_schema("WeirdNode", ("LATENT", "STRING"),
                              required_inputs=(FieldSpec("x", "LATENT", True),))
        cand = _make_candidate("WeirdNode", "unknown.cap")
        tmpl = select_template(cand, schema)
        assert tmpl is None


# ------------------------------------------------------------------ #
# T6-T10: Synthesis
# ------------------------------------------------------------------ #


class TestSynthesis:
    def test_pollinations_synthesis(self):
        """T6: PollinationsImageGen → valid manifest + workflow."""
        cand = _make_candidate("PollinationsImageGen", "image.generate")
        tmpl = select_template(cand, POLLINATIONS_SCHEMA)
        assert tmpl is not None
        result = synthesize_workflow(cand, POLLINATIONS_SCHEMA, tmpl)

        assert isinstance(result, WorkflowSynthesisResult)
        assert result.capability == "image.generate"
        assert result.template_id == "s2_text_to_image"
        assert "s2_PollinationsImageGen_s2_text_to_image" == result.manifest["id"]
        assert result.manifest["source"] == "synthesized"
        assert result.manifest["outputs"]["result"]["kind"] == "image"
        # Workflow has generator + save nodes
        assert len(result.workflow) == 2
        assert result.workflow["1"]["class_type"] == "PollinationsImageGen"
        assert result.workflow["2"]["class_type"] == "SaveImage"
        # Connection: generator[0] → save.images
        assert result.workflow["2"]["inputs"]["images"] == ["1", 0]

    def test_agnes_video_synthesis(self):
        """T7: AgnesVideo Text To Video → valid manifest + workflow."""
        cand = _make_candidate("AgnesVideo", "video.generate")
        tmpl = select_template(cand, AGNES_SCHEMA)
        assert tmpl is not None
        result = synthesize_workflow(cand, AGNES_SCHEMA, tmpl)

        assert result.capability == "video.generate"
        assert result.template_id == "s2_text_to_video"
        # Workflow has generator + CreateVideo + SaveVideo = 3 nodes
        assert len(result.workflow) == 3
        assert result.workflow["1"]["class_type"] == "AgnesVideo"
        assert result.workflow["2"]["class_type"] == "CreateVideo"
        assert result.workflow["3"]["class_type"] == "SaveVideo"

    def test_output_mapping_preserved(self):
        """T8: Synthesis preserves output mapping."""
        cand = _make_candidate("PollinationsImageGen", "image.generate")
        tmpl = select_template(cand, POLLINATIONS_SCHEMA)
        result = synthesize_workflow(cand, POLLINATIONS_SCHEMA, tmpl)
        assert result.manifest["outputs"]["result"]["kind"] == "image"
        assert result.manifest["outputs"]["result"]["node"] == "2"  # save node

    def test_required_custom_nodes_preserved(self):
        """T9: Synthesis preserves required_custom_nodes."""
        cand = _make_candidate("AgnesVideo", "video.generate")
        tmpl = select_template(cand, AGNES_SCHEMA)
        result = synthesize_workflow(cand, AGNES_SCHEMA, tmpl)
        assert "AgnesVideo" in result.manifest["required_custom_nodes"]
        assert "CreateVideo" in result.manifest["required_custom_nodes"]
        assert "SaveVideo" in result.manifest["required_custom_nodes"]

    def test_model_requirements_when_model_input(self):
        """T10: Synthesis adds model requirements when MODEL input detected."""
        schema = _make_schema("ModelNode", ("IMAGE",),
                              required_inputs=(FieldSpec("model", "MODEL", True),
                                               FieldSpec("prompt", "STRING", True, default="test")),
                              python_module="nodes")
        cand = _make_candidate("ModelNode", "image.generate")
        tmpl = TEXT_TO_IMAGE  # will match (IMAGE output, no IMAGE input, has prompt)
        result = synthesize_workflow(cand, schema, tmpl)
        assert "checkpoint" in result.manifest["required_models"]
        assert result.manifest.get("contract_version") == 2


# ------------------------------------------------------------------ #
# T11-T13: Safety classification
# ------------------------------------------------------------------ #


class TestSafety:
    def test_builtin_allowed(self):
        """T11: Built-in node → ALLOWED."""
        assert classify_safety("nodes", "image", "ImageScale") == SafetyClass.ALLOWED

    def test_custom_requires_confirmation(self):
        """T12: Custom node → REQUIRES_CONFIRMATION."""
        assert classify_safety("custom_nodes.pollinations-byop", "Pollinations/Image",
                               "PollinationsImageGen") == SafetyClass.REQUIRES_CONFIRMATION

    def test_shell_forbidden(self):
        """T13: Shell keyword → FORBIDDEN."""
        assert classify_safety("custom_nodes.shell_exec", "system", "RunCommand") == SafetyClass.FORBIDDEN

    def test_api_requires_confirmation(self):
        """Custom node with 'api' keyword → REQUIRES_CONFIRMATION."""
        assert classify_safety("custom_nodes.my_api_client", "api", "CallAPI") == SafetyClass.REQUIRES_CONFIRMATION

    def test_comfy_extras_allowed(self):
        """comfy_extras module → ALLOWED."""
        assert classify_safety("comfy_extras.nodes_video", "video", "CreateVideo") == SafetyClass.ALLOWED


# ------------------------------------------------------------------ #
# T14-T15: Provenance + FORBIDDEN rejection
# ------------------------------------------------------------------ #


class TestProvenanceAndRejection:
    def test_provenance_metadata(self):
        """T14: Synthesized manifest has provenance metadata."""
        cand = _make_candidate("PollinationsImageGen", "image.generate")
        tmpl = select_template(cand, POLLINATIONS_SCHEMA)
        result = synthesize_workflow(cand, POLLINATIONS_SCHEMA, tmpl,
                                     SafetyClass.REQUIRES_CONFIRMATION)
        assert result.manifest["source"] == "synthesized"
        assert result.manifest["synthesized_from"]["candidate"] == "PollinationsImageGen"
        assert result.manifest["synthesized_from"]["template"] == "s2_text_to_image"
        assert result.manifest["safety_class"] == "REQUIRES_CONFIRMATION"

    def test_forbidden_returns_forbidden_status(self):
        """T15: Safety = FORBIDDEN → synthesis result has FORBIDDEN safety."""
        cand = _make_candidate("EvilNode", "image.generate")
        schema = _make_schema("EvilNode", ("IMAGE",),
                              required_inputs=(FieldSpec("prompt", "STRING", True, default="test"),),
                              python_module="custom_nodes.shell_exec")
        tmpl = select_template(cand, schema)
        assert tmpl is not None
        result = synthesize_workflow(cand, schema, tmpl, SafetyClass.FORBIDDEN)
        assert result.safety == SafetyClass.FORBIDDEN
        assert result.manifest["safety_class"] == "FORBIDDEN"


# ------------------------------------------------------------------ #
# T16: Knowledge readiness remains advisory
# ------------------------------------------------------------------ #


class TestAdvisoryBehavior:
    def test_readiness_remains_advisory(self):
        """T16: KnowledgeCore.synthesize_candidates returns data, does NOT change readiness."""
        # Use a fresh KnowledgeCore with no persistent store
        import tempfile
        core = KnowledgeCore(data_dir=tempfile.mkdtemp())
        core._schemas.clear()
        core._candidates.clear()
        core._claims.clear()
        # Inject only our test data
        core._schemas["TestNode"] = _make_schema(
            "TestNode", ("IMAGE",),
            required_inputs=(FieldSpec("prompt", "STRING", True, default="test"),),
        )
        core._candidates["TestNode"] = [_make_candidate("TestNode", "image.generate")]
        core._claims = [KnowledgeClaim(
            claim="TestNode implements image.generate",
            subject="TestNode", predicate="implements", object="image.generate",
            status=ClaimStatus.INFERENCE,
        )]

        query = KnowledgeQuery(
            required_operation="image.generate",
            required_media_input=(),
            required_media_output="image",
        )
        # Query should show CANDIDATE_ONLY (no builtin workflow)
        response = core.query(query)
        gap_types = {g.gap_type for g in response.gaps}
        assert GapType.CANDIDATE_NO_WORKFLOW in gap_types

        # Synthesize
        results = core.synthesize_candidates(query)
        assert len(results) == 1
        assert results[0]["status"] == "SYNTHESIZED"

        # Readiness should NOT change to EXECUTABLE
        # (synthesized workflow is NOT auto-registered)
        response2 = core.query(query)
        assert response2.readiness != Readiness.EXECUTABLE


# ------------------------------------------------------------------ #
# T17-T18: Regression + catalog
# ------------------------------------------------------------------ #


class TestRegressionAndCatalog:
    def test_existing_workflows_unaffected(self):
        """T17: Template catalog doesn't affect existing workflow loading."""
        from app.registry.registry import WorkflowRegistry
        reg = WorkflowRegistry()
        reg.discover("workflows")
        # All existing workflows should still load
        assert len(reg.workflows) >= 9

    def test_catalog_has_minimum_templates(self):
        """T18: Template catalog has at least 3 templates."""
        assert len(TEMPLATE_CATALOG) >= 3
        ids = {t.template_id for t in TEMPLATE_CATALOG}
        assert "s2_text_to_image" in ids
        assert "s2_image_to_image" in ids
        assert "s2_text_to_video" in ids
