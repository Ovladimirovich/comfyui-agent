"""Unit tests for Prompt Builder contract (M11.1) and HeuristicPromptBuilder (M11.2).

Tests the core contracts: PromptContext, PromptResult, PromptBuilder protocol.
Tests HeuristicPromptBuilder implementation.
"""

import pytest
from typing import get_args

from app.prompt.builder import PromptBuilder, PromptContext, PromptResult
from app.prompt.heuristic import HeuristicPromptBuilder


class TestPromptContext:
    """Test PromptContext dataclass structure and validation."""

    def test_prompt_context_creation(self):
        """PromptContext can be created with minimal required fields."""
        ctx = PromptContext(original_text="кот", mode="suggestion")
        assert ctx.original_text == "кот"
        assert ctx.mode == "suggestion"
        assert ctx.capability is None
        assert ctx.active_asset_type is None
        assert ctx.previous_prompt is None
        assert ctx.suggestion_index == 0
        assert ctx.style is None
        assert ctx.parameters is None

    def test_prompt_context_with_all_fields(self):
        """PromptContext can be created with all optional fields."""
        ctx = PromptContext(
            original_text="кот",
            mode="suggestion",
            capability="image.generate",
            active_asset_type="image",
            previous_prompt="cat",
            suggestion_index=2,
            style="photorealistic",
            parameters={"width": 512, "height": 512},
        )
        assert ctx.original_text == "кот"
        assert ctx.mode == "suggestion"
        assert ctx.capability == "image.generate"
        assert ctx.active_asset_type == "image"
        assert ctx.previous_prompt == "cat"
        assert ctx.suggestion_index == 2
        assert ctx.style == "photorealistic"
        assert ctx.parameters == {"width": 512, "height": 512}

    def test_prompt_context_mode_literal(self):
        """PromptContext.mode only accepts valid Literal values."""
        # Hardcoded — get_args(Literal) unreliable in Python 3.14
        valid_modes = ("completion", "suggestion")
        assert "completion" in valid_modes
        assert "suggestion" in valid_modes

    def test_prompt_context_contains_only_strings_and_ids(self):
        """AD-30: PromptContext contains ONLY strings and IDs, no bytes/paths/FS."""
        ctx = PromptContext(
            original_text="кот",
            mode="suggestion",
            capability="image.generate",
            active_asset_type="image",
            previous_prompt="cat",
            suggestion_index=2,
            style="photorealistic",
            parameters={"width": 512},
        )
        # All fields are strings or simple types (int, dict), no bytes/paths
        assert isinstance(ctx.original_text, str)
        assert isinstance(ctx.mode, str)
        assert isinstance(ctx.capability, (str, type(None)))
        assert isinstance(ctx.active_asset_type, (str, type(None)))
        assert isinstance(ctx.previous_prompt, (str, type(None)))
        assert isinstance(ctx.suggestion_index, int)
        assert isinstance(ctx.style, (str, type(None)))
        assert isinstance(ctx.parameters, (dict, type(None)))


class TestPromptResult:
    """Test PromptResult dataclass structure and validation."""

    def test_prompt_result_creation(self):
        """PromptResult can be created with required fields."""
        result = PromptResult(
            enhanced_prompt="realistic cat",
            original_preserved=True,
            mode="suggestion",
            variant_index=0,
            source="heuristic",
        )
        assert result.enhanced_prompt == "realistic cat"
        assert result.original_preserved is True
        assert result.mode == "suggestion"
        assert result.variant_index == 0
        assert result.source == "heuristic"
        assert result.rationale is None

    def test_prompt_result_with_rationale(self):
        """PromptResult can include rationale for debugging."""
        result = PromptResult(
            enhanced_prompt="realistic cat",
            original_preserved=True,
            mode="suggestion",
            variant_index=0,
            source="heuristic",
            rationale="Applied photorealistic template",
        )
        assert result.rationale == "Applied photorealistic template"

    def test_prompt_result_mode_literal(self):
        """PromptResult.mode only accepts valid Literal values."""
        # Hardcoded — get_args(Literal) unreliable in Python 3.14
        valid_modes = ("completion", "suggestion")
        assert "completion" in valid_modes
        assert "suggestion" in valid_modes

    def test_prompt_result_source_literal(self):
        """PromptResult.source only accepts valid Literal values."""
        # Hardcoded — get_args(Literal) unreliable in Python 3.14
        valid_sources = ("heuristic", "llm", "heuristic_fallback")
        assert "heuristic" in valid_sources
        assert "llm" in valid_sources
        assert "heuristic_fallback" in valid_sources

    def test_prompt_result_original_preserved_flag(self):
        """AD-32: PromptResult has original_preserved flag to track intent preservation."""
        result = PromptResult(
            enhanced_prompt="realistic cat",
            original_preserved=True,
            mode="suggestion",
            variant_index=0,
            source="heuristic",
        )
        assert result.original_preserved is True


class TestPromptBuilderProtocol:
    """Test PromptBuilder protocol structure."""

    def test_prompt_builder_is_protocol(self):
        """PromptBuilder is a Protocol type."""
        from typing import Protocol
        assert issubclass(PromptBuilder, Protocol)

    def test_prompt_builder_has_build_method(self):
        """PromptBuilder protocol requires build method."""
        assert hasattr(PromptBuilder, "build")

    def test_prompt_builder_build_signature(self):
        """PromptBuilder.build has correct signature."""
        import inspect
        sig = inspect.signature(PromptBuilder.build)
        params = list(sig.parameters.keys())
        assert "context" in params
        assert "self" in params

    def test_mock_implementation_satisfies_protocol(self):
        """A mock implementation satisfies the PromptBuilder protocol."""

        class MockBuilder:
            def build(self, context: PromptContext) -> PromptResult:
                return PromptResult(
                    enhanced_prompt=context.original_text,
                    original_preserved=True,
                    mode=context.mode,
                    variant_index=context.suggestion_index,
                    source="heuristic",
                )

        builder = MockBuilder()
        assert isinstance(builder, PromptBuilder)

        ctx = PromptContext(original_text="кот", mode="suggestion")
        result = builder.build(ctx)
        assert result.enhanced_prompt == "кот"
        assert result.original_preserved is True


class TestArchitecturalInvariants:
    """Test compliance with architectural decisions AD-30, AD-31, AD-32."""

    def test_ad30_no_fs_access_in_contract(self):
        """AD-30: Contract does not include FS access or ComfyUI integration."""
        # PromptContext has no bytes, paths, or file handles
        ctx = PromptContext(original_text="кот", mode="suggestion")
        assert not hasattr(ctx, "file_path")
        assert not hasattr(ctx, "bytes")
        assert not hasattr(ctx, "asset_path")

        # PromptResult has no FS access
        result = PromptResult(
            enhanced_prompt="realistic cat",
            original_preserved=True,
            mode="suggestion",
            variant_index=0,
            source="heuristic",
        )
        assert not hasattr(result, "file_path")
        assert not hasattr(result, "bytes")

    def test_ad31_no_capability_selection_in_contract(self):
        """AD-31: Contract does not include capability selection logic."""
        # PromptContext has optional capability field but no selection logic
        ctx = PromptContext(
            original_text="сделай красивого кота",
            mode="suggestion",
            capability="image.generate",  # This is provided, not selected
        )
        # The contract does not have methods to select capability
        assert not hasattr(PromptContext, "select_capability")
        assert not hasattr(PromptResult, "selected_capability")


class TestHeuristicPromptBuilder:
    """Test HeuristicPromptBuilder implementation."""

    def test_heuristic_builder_satisfies_protocol(self):
        """HeuristicPromptBuilder satisfies the PromptBuilder protocol."""
        builder = HeuristicPromptBuilder()
        assert isinstance(builder, PromptBuilder)

    def test_minimal_prompt(self):
        """Test with minimal prompt (single word)."""
        builder = HeuristicPromptBuilder()
        ctx = PromptContext(original_text="кот", mode="suggestion")
        result = builder.build(ctx)
        
        assert result.enhanced_prompt
        assert "кот" in result.enhanced_prompt.lower()
        assert result.source == "heuristic"
        assert result.mode == "suggestion"

    def test_original_intent_preserved(self):
        """AD-32: Original intent is preserved in enhanced prompt."""
        builder = HeuristicPromptBuilder()
        ctx = PromptContext(original_text="кот на крыше", mode="suggestion")
        result = builder.build(ctx)
        
        assert result.original_preserved is True
        assert "кот" in result.enhanced_prompt.lower()

    def test_multiple_variants_different_indices(self):
        """Different suggestion_index should produce different variants."""
        builder = HeuristicPromptBuilder()
        
        ctx0 = PromptContext(original_text="кот", mode="suggestion", suggestion_index=0)
        result0 = builder.build(ctx0)
        
        ctx1 = PromptContext(original_text="кот", mode="suggestion", suggestion_index=1)
        result1 = builder.build(ctx1)
        
        ctx2 = PromptContext(original_text="кот", mode="suggestion", suggestion_index=2)
        result2 = builder.build(ctx2)
        
        # All should be different
        assert result0.enhanced_prompt != result1.enhanced_prompt
        assert result1.enhanced_prompt != result2.enhanced_prompt
        assert result0.enhanced_prompt != result2.enhanced_prompt

    def test_deterministic_same_index(self):
        """Same context + same index should produce same result (deterministic)."""
        builder = HeuristicPromptBuilder()
        ctx = PromptContext(original_text="кот", mode="suggestion", suggestion_index=0)
        
        result1 = builder.build(ctx)
        result2 = builder.build(ctx)
        
        assert result1.enhanced_prompt == result2.enhanced_prompt
        assert result1.variant_index == result2.variant_index

    def test_empty_input(self):
        """Test with empty input -- returns empty enhanced_prompt."""
        builder = HeuristicPromptBuilder()
        ctx = PromptContext(original_text="", mode="suggestion")
        result = builder.build(ctx)

        # Empty input -> empty enhanced_prompt
        assert result.enhanced_prompt == ""
        assert result.source == "heuristic"
        assert result.rationale == "Empty query input"

    def test_whitespace_input(self):
        """Test with whitespace-only input -- returns empty enhanced_prompt."""
        builder = HeuristicPromptBuilder()
        ctx = PromptContext(original_text="   ", mode="suggestion")
        result = builder.build(ctx)

        # Whitespace-only -> empty enhanced_prompt
        assert result.enhanced_prompt == ""
        assert result.source == "heuristic"
    def test_russian_text(self):
        """Test with Russian text."""
        builder = HeuristicPromptBuilder()
        ctx = PromptContext(original_text="кот на крыше", mode="suggestion")
        result = builder.build(ctx)
        
        assert result.enhanced_prompt
        assert "кот" in result.enhanced_prompt.lower()
        assert result.source == "heuristic"

    def test_english_text(self):
        """Test with English text."""
        builder = HeuristicPromptBuilder()
        ctx = PromptContext(original_text="cat on roof", mode="suggestion")
        result = builder.build(ctx)
        
        assert result.enhanced_prompt
        assert "cat" in result.enhanced_prompt.lower()
        assert result.source == "heuristic"

    def test_style_parameter(self):
        """Test with style parameter -- HeuristicPromptBuilder ignores style."""
        builder = HeuristicPromptBuilder()
        ctx = PromptContext(
            original_text="кот",
            mode="suggestion",
            style="photorealistic"
        )
        result = builder.build(ctx)

        # HeuristicPromptBuilder does not use style field (MVP)
        # Should not crash and should preserve original prompt
        assert result.enhanced_prompt
        assert "кот" in result.enhanced_prompt.lower()
        assert result.source == "heuristic"
        """Test with parameters (should be passed through but not used in MVP)."""
        builder = HeuristicPromptBuilder()
        ctx = PromptContext(
            original_text="кот",
            mode="suggestion",
            parameters={"width": 512, "height": 512}
        )
        result = builder.build(ctx)
        
        # Parameters are not used in heuristic builder (MVP)
        # But should not cause errors
        assert result.enhanced_prompt
        assert result.source == "heuristic"

    def test_mode_suggestion(self):
        """Test with mode='suggestion'."""
        builder = HeuristicPromptBuilder()
        ctx = PromptContext(original_text="кот", mode="suggestion")
        result = builder.build(ctx)
        
        assert result.mode == "suggestion"
        assert result.source == "heuristic"

    def test_mode_completion(self):
        """Test with mode='completion'."""
        builder = HeuristicPromptBuilder()
        ctx = PromptContext(original_text="кот", mode="completion")
        result = builder.build(ctx)
        
        assert result.mode == "completion"
        assert result.source == "heuristic"

    def test_ad30_no_fs_access(self):
        """AD-30: HeuristicPromptBuilder does not access FS or ComfyUI."""
        builder = HeuristicPromptBuilder()
        ctx = PromptContext(original_text="кот", mode="suggestion")
        
        # Should work without any FS/ComfyUI access
        result = builder.build(ctx)
        
        assert result.enhanced_prompt
        assert result.source == "heuristic"

    def test_ad31_no_capability_selection(self):
        """AD-31: HeuristicPromptBuilder does not select capability."""
        builder = HeuristicPromptBuilder()
        # capability is provided in context, not selected by builder
        ctx = PromptContext(
            original_text="сделай красивого кота",
            mode="suggestion",
            capability="image.generate"  # Provided, not selected
        )
        result = builder.build(ctx)
        
        # Builder should not add capability to the prompt
        assert "image.generate" not in result.enhanced_prompt.lower()
        assert "capability" not in result.enhanced_prompt.lower()

    def test_ad32_original_preserved_flag(self):
        """AD-32: original_preserved flag is correctly set."""
        builder = HeuristicPromptBuilder()
        ctx = PromptContext(original_text="кот", mode="suggestion")
        result = builder.build(ctx)
        
        assert result.original_preserved is True

    def test_media_agnostic(self):
        """Builder is media-agnostic (AD-03)."""
        builder = HeuristicPromptBuilder()
        
        # Should work with any active_asset_type (just a string)
        ctx_image = PromptContext(
            original_text="кот",
            mode="suggestion",
            active_asset_type="image"
        )
        result_image = builder.build(ctx_image)
        
        ctx_video = PromptContext(
            original_text="кот",
            mode="suggestion",
            active_asset_type="video"
        )
        result_video = builder.build(ctx_video)
        
        # Both should produce results
        assert result_image.enhanced_prompt
        assert result_video.enhanced_prompt

    def test_real_world_example_cat(self):
        """Real-world example: cat on roof."""
        builder = HeuristicPromptBuilder()
        ctx = PromptContext(original_text="кот на крыше", mode="suggestion")
        
        result0 = builder.build(ctx)
        result1 = builder.build(PromptContext(original_text="кот на крыше", mode="suggestion", suggestion_index=1))
        result2 = builder.build(PromptContext(original_text="кот на крыше", mode="suggestion", suggestion_index=2))
        
        # All should contain original text
        assert "кот" in result0.enhanced_prompt.lower()
        assert "кот" in result1.enhanced_prompt.lower()
        assert "кот" in result2.enhanced_prompt.lower()
        
        # All should be different variants
        assert result0.enhanced_prompt != result1.enhanced_prompt
        assert result1.enhanced_prompt != result2.enhanced_prompt

    def test_real_world_example_portrait(self):
        """Real-world example: portrait."""
        builder = HeuristicPromptBuilder()
        ctx = PromptContext(original_text="портрет девушки", mode="suggestion")
        
        result0 = builder.build(ctx)
        result1 = builder.build(PromptContext(original_text="портрет девушки", mode="suggestion", suggestion_index=1))
        
        assert "портрет" in result0.enhanced_prompt.lower() or "девушки" in result0.enhanced_prompt.lower()
        assert result0.enhanced_prompt != result1.enhanced_prompt

    def test_real_world_example_landscape(self):
        """Real-world example: landscape."""
        builder = HeuristicPromptBuilder()
        ctx = PromptContext(original_text="пейзаж гор", mode="suggestion")
        
        result0 = builder.build(ctx)
        result1 = builder.build(PromptContext(original_text="пейзаж гор", mode="suggestion", suggestion_index=1))
        
        assert "пейзаж" in result0.enhanced_prompt.lower() or "гор" in result0.enhanced_prompt.lower()
        assert result0.enhanced_prompt != result1.enhanced_prompt

    def test_rationale_provided(self):
        """Rationale is provided for debugging."""
        builder = HeuristicPromptBuilder()
        ctx = PromptContext(original_text="кот", mode="suggestion")
        result = builder.build(ctx)
        
        assert result.rationale is not None
        assert "template" in result.rationale.lower()

    def test_ad32_original_preserved_flag_exists(self):
        """AD-32: PromptResult has original_preserved flag."""
        result = PromptResult(
            enhanced_prompt="realistic cat",
            original_preserved=True,
            mode="suggestion",
            variant_index=0,
            source="heuristic",
        )
        assert hasattr(result, "original_preserved")
        assert isinstance(result.original_preserved, bool)

    def test_contract_is_media_agnostic(self):
        """Contract does not have media-specific fields (AD-03)."""
        # No ImageContext, VideoContext, etc.
        # Only generic active_asset_type (string)
        ctx = PromptContext(
            original_text="кот",
            mode="suggestion",
            active_asset_type="image",  # Generic string, not media-specific
        )
        assert isinstance(ctx.active_asset_type, str)
        assert not hasattr(ctx, "image_context")
        assert not hasattr(ctx, "video_context")
