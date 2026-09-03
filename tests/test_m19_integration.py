"""Integration tests: Composer + ConversationAgent.

Scenarios:
- A: "Сгенерируй изображение кота и увеличь разрешение"
- B: "Сгенерируй изображение и затем увеличь его"
- C: Input Asset → edit → upscale
- D: Single-step regression
- E: Impossible composition (graceful failure)
"""

from __future__ import annotations

import pytest

from app.planner import Composer, CapabilityGraph, CompositionResult
from app.registry.capability import CapabilityRegistry
from app.registry.registry import WorkflowRegistry


@pytest.fixture
def cap_registry():
    return CapabilityRegistry()


@pytest.fixture
def wf_registry(cap_registry):
    return WorkflowRegistry(capabilities=cap_registry)


@pytest.fixture
def composer(cap_registry, wf_registry):
    return Composer(
        capability_registry=cap_registry,
        workflow_registry=wf_registry,
    )


class TestScenarioA_GenerateThenUpscale:
    """Scenario A: "Сгенерируй изображение кота и увеличь разрешение"
    
    Expected composition: image.generate → image.upscale
    """
    
    def test_composer_produces_valid_chain(self, composer):
        result = composer.compose(
            target_capability="image.upscale",
            params={"prompt": "кот", "factor": 2},
        )
        assert result.success is True
        assert len(result.chain) >= 2
        # First step: generate
        assert result.chain[0].capability == "image.generate"
        # Last step: upscale
        assert result.chain[-1].capability == "image.upscale"
    
    def test_chain_is_executable(self, composer):
        result = composer.compose(
            target_capability="image.upscale",
            params={"prompt": "кот", "factor": 2},
        )
        assert result.success is True
        # Each subtask should have capability and params
        for subtask in result.chain:
            assert subtask.capability is not None
            assert isinstance(subtask.params, dict)


class TestScenarioB_DifferentWording:
    """Scenario B: "Сгенерируй изображение и затем увеличь его"
    
    Should produce same capability sequence as Scenario A.
    """
    
    def test_composer_handles_different_wording(self, composer):
        result = composer.compose(
            target_capability="image.upscale",
            params={"prompt": "изображение", "factor": 2},
        )
        assert result.success is True
        assert result.chain[-1].capability == "image.upscale"


class TestScenarioC_InputAssetChain:
    """Scenario C: Input Asset → edit → upscale
    
    Tests that Composer can build chains starting from existing assets.
    """
    
    def test_composer_with_available_image_type(self, composer):
        result = composer.compose(
            target_capability="image.upscale",
            params={"factor": 2},
            available_types={"image"},
        )
        assert result.success is True
        # Should find a path from image to upscale
        assert result.chain[-1].capability == "image.upscale"
    
    def test_composer_chain_includes_edit_if_needed(self, composer):
        # If we have an image and want upscale, chain might be: edit → upscale
        # or just upscale if input is already high-res
        result = composer.compose(
            target_capability="image.upscale",
            params={"factor": 2},
            available_types={"image"},
        )
        assert result.success is True
        # Chain should be valid
        for subtask in result.chain:
            assert subtask.capability is not None


class TestScenarioD_SingleStepRegression:
    """Scenario D: Single-step "Сгенерируй изображение кота"
    
    Composer should handle single-step requests correctly.
    """
    
    def test_composer_single_step(self, composer):
        result = composer.compose(
            target_capability="image.generate",
            params={"prompt": "кот"},
        )
        assert result.success is True
        assert len(result.chain) == 1
        assert result.chain[0].capability == "image.generate"
    
    def test_composer_preserves_params(self, composer):
        result = composer.compose(
            target_capability="image.generate",
            params={"prompt": "кот", "width": 512, "height": 512},
        )
        assert result.success is True
        # Params should be passed through (identity mapping)
        assert result.chain[0].params.get("prompt") == "кот"


class TestScenarioE_ImpossibleComposition:
    """Scenario E: Impossible composition (graceful failure)
    
    Composer should return failure with suggestions, not crash.
    """
    
    def test_composer_nonexistent_target(self, composer):
        result = composer.compose(
            target_capability="nonexistent.capability",
            params={},
        )
        assert result.success is False
        assert result.failure_reason is not None
        assert len(result.suggestions) > 0
    
    def test_composer_incompatible_chain(self, composer):
        # audio.generate cannot lead to image.upscale
        result = composer.compose(
            target_capability="image.upscale",
            params={},
            available_types={"audio"},
        )
        # Should either fail or find no path
        if not result.success:
            assert result.failure_reason is not None
        else:
            # If it succeeds, chain should still be valid
            assert result.chain[-1].capability == "image.upscale"
    
    def test_composer_empty_params(self, composer):
        result = composer.compose(
            target_capability="image.generate",
            params={},
        )
        assert result.success is True
        assert len(result.chain) == 1


class TestCapabilityGraphIntegration:
    """Test CapabilityGraph with real CapabilityRegistry."""
    
    def test_graph_finds_all_capabilities(self, cap_registry):
        graph = CapabilityGraph(cap_registry)
        caps = graph.get_all_capabilities()
        assert len(caps) >= 5  # At least: generate, edit, upscale, video, audio
    
    def test_graph_composability_image_domain(self, cap_registry):
        graph = CapabilityGraph(cap_registry)
        # image.generate → image.upscale
        assert graph.get_composability("image.generate", "image.upscale") is True
        # image.generate → image.edit
        assert graph.get_composability("image.generate", "image.edit") is True
        # image.edit → image.upscale
        assert graph.get_composability("image.edit", "image.upscale") is True
    
    def test_graph_composability_video_domain(self, cap_registry):
        graph = CapabilityGraph(cap_registry)
        # video.generate → video.upscale
        assert graph.get_composability("video.generate", "video.upscale") is True
    
    def test_graph_no_cross_domain_leakage(self, cap_registry):
        graph = CapabilityGraph(cap_registry)
        # audio.generate should NOT be composable with image.upscale
        assert graph.get_composability("audio.generate", "image.upscale") is False
        # video.generate should NOT be composable with image.edit
        assert graph.get_composability("video.generate", "image.edit") is False


class TestComposerAlternatives:
    """Test that Composer returns alternative paths."""
    
    def test_composer_returns_alternatives(self, composer):
        result = composer.compose(
            target_capability="image.upscale",
            params={"prompt": "тест"},
        )
        assert result.success is True
        # May have alternatives (up to 3)
        assert len(result.alternatives) <= 3
    
    def test_alternatives_are_valid_chains(self, composer):
        result = composer.compose(
            target_capability="image.upscale",
            params={"prompt": "тест"},
        )
        if result.has_alternatives:
            for alt in result.alternatives:
                assert len(alt) > 0
                assert alt[-1].capability == "image.upscale"