"""Tests for Composer (Intent → Capability Planning).

AD-41 implementation tests.
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


class TestCapabilityGraph:
    def test_graph_builds_from_registry(self, cap_registry):
        graph = CapabilityGraph(cap_registry)
        caps = graph.get_all_capabilities()
        assert "image.generate" in caps
        assert "image.upscale" in caps
    
    def test_composability_image_to_upscale(self, cap_registry):
        graph = CapabilityGraph(cap_registry)
        assert graph.get_composability("image.generate", "image.upscale") is True
    
    def test_composability_image_to_edit(self, cap_registry):
        graph = CapabilityGraph(cap_registry)
        assert graph.get_composability("image.generate", "image.edit") is True
    
    def test_no_composability_audio_to_image(self, cap_registry):
        graph = CapabilityGraph(cap_registry)
        # audio.generate output is "audio", which is not in image.generate input
        assert graph.get_composability("audio.generate", "image.generate") is False
    
    def test_find_paths_generate_to_upscale(self, cap_registry):
        graph = CapabilityGraph(cap_registry)
        paths = graph.find_paths("image.upscale", available_types=set())
        assert len(paths) > 0
        # Should find image.generate -> image.upscale
        assert any("image.generate" in p for p in paths)
    
    def test_find_paths_standalone_capability(self, cap_registry):
        graph = CapabilityGraph(cap_registry)
        # audio.generate has no input requirements, so it's a standalone path
        paths = graph.find_paths("audio.generate", available_types=set())
        assert len(paths) == 1
        assert paths[0] == ["audio.generate"]
    
    def test_max_length_limit(self, cap_registry):
        graph = CapabilityGraph(cap_registry)
        paths = graph.find_paths("image.upscale", max_length=1)
        # With max_length=1, only direct capabilities are found
        for p in paths:
            assert len(p) <= 1


class TestComposer:
    def test_compose_simple_chain(self, composer):
        result = composer.compose(
            target_capability="image.upscale",
            params={"prompt": "test", "factor": 2},
        )
        assert result.success is True
        assert len(result.chain) > 0
        # Last step should be upscale
        assert result.chain[-1].capability == "image.upscale"
    
    def test_compose_nonexistent_capability(self, composer):
        result = composer.compose(
            target_capability="nonexistent.capability",
            params={},
        )
        assert result.success is False
        assert result.failure_reason is not None
    
    def test_compose_returns_alternatives(self, composer):
        result = composer.compose(
            target_capability="image.upscale",
            params={"prompt": "test"},
        )
        if result.success:
            # May have alternatives
            assert isinstance(result.alternatives, list)
    
    def test_compose_chain_respects_max_length(self, cap_registry, wf_registry):
        composer = Composer(
            capability_registry=cap_registry,
            workflow_registry=wf_registry,
            max_chain_length=2,
        )
        result = composer.compose(
            target_capability="image.upscale",
            params={},
        )
        if result.success:
            assert len(result.chain) <= 2


class TestCompositionResult:
    def test_ok_result(self):
        result = CompositionResult.ok(chain=[])
        assert result.success is True
        assert result.chain == []
    
    def test_fail_result(self):
        result = CompositionResult.fail("test error")
        assert result.success is False
        assert result.failure_reason == "test error"
    
    def test_has_alternatives(self):
        result = CompositionResult.ok(chain=[], alternatives=[[], []])
        assert result.has_alternatives is True
    
    def test_no_alternatives(self):
        result = CompositionResult.ok(chain=[])
        assert result.has_alternatives is False