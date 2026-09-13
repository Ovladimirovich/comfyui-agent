"""S1 integration tests — CostTier / Free-First Routing.

Покрытие:
  T1:  CostTier enum values
  T2:  BackendSpec default cost_tier (remote → UNKNOWN)
  T3:  BackendSpec local_comfyui → FREE
  T4:  BackendSpec remote → UNKNOWN
  T5:  Workflow default cost_tier → None
  T6:  Manifest JSON without cost_tier → None
  T7:  Manifest JSON with cost_tier → parsed
  T8:  _effective_cost_tier: workflow override > backend > UNKNOWN
  T9:  BackendCatalog.choose: FREE backend allowed
  T10: BackendCatalog.choose: TRIAL backend allowed
  T11: BackendCatalog.choose: PAID backend excluded (auto)
  T12: BackendCatalog.choose: UNKNOWN backend excluded (auto)
  T13: BackendCatalog.choose: allow_paid=True → PAID allowed
  T14: from_env local → cost_tier=FREE
  T15: from_env remote → cost_tier=UNKNOWN
  T16: COST_RANKING order
  T17: cost_tier string-to-enum conversion in BackendSpec
  T18: load_workflow with cost_tier in manifest JSON
  T19: load_workflow without cost_tier → None
  CRITICAL-1: remote backend UNKNOWN → excluded from auto-selection
  CRITICAL-2: explicitly declared FREE remote backend → allowed
"""
import json
import os
import pytest

from app.registry.cost import CostTier, COST_RANKING
from app.registry.backends import BackendCatalog, BackendSpec


# ------------------------------------------------------------------ #
# T1: CostTier enum
# ------------------------------------------------------------------ #


class TestCostTierEnum:
    def test_values(self):
        assert CostTier.FREE.value == "FREE"
        assert CostTier.TRIAL.value == "TRIAL"
        assert CostTier.PAID.value == "PAID"
        assert CostTier.UNKNOWN.value == "UNKNOWN"

    def test_str_enum(self):
        assert isinstance(CostTier.FREE, str)
        assert str(CostTier.FREE) == "CostTier.FREE"

    def test_from_string(self):
        assert CostTier("FREE") is CostTier.FREE
        assert CostTier("PAID") is CostTier.PAID

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            CostTier("INVALID")


# ------------------------------------------------------------------ #
# T2-T4, T17: BackendSpec cost_tier
# ------------------------------------------------------------------ #


class TestBackendSpecCostTier:
    def test_default_remote(self):
        """T2: remote backend default → UNKNOWN."""
        spec = BackendSpec("r", "http://r", kind="remote_comfyui")
        assert spec.cost_tier == CostTier.UNKNOWN

    def test_default_local(self):
        """T3: local backend default → FREE."""
        spec = BackendSpec("l", "http://l", kind="local_comfyui")
        assert spec.cost_tier == CostTier.FREE

    def test_default_cloud(self):
        """T4: cloud backend default → UNKNOWN."""
        spec = BackendSpec("c", "http://c", kind="cloud_comfyui")
        assert spec.cost_tier == CostTier.UNKNOWN

    def test_explicit_cost_tier(self):
        spec = BackendSpec("p", "http://p", cost_tier=CostTier.PAID)
        assert spec.cost_tier == CostTier.PAID

    def test_string_conversion(self):
        """T17: string cost_tier → enum conversion."""
        spec = BackendSpec("x", "http://x", cost_tier="FREE")
        assert spec.cost_tier == CostTier.FREE

    def test_invalid_string_defaults_unknown(self):
        """T17: invalid string → UNKNOWN."""
        spec = BackendSpec("x", "http://x", cost_tier="INVALID")
        assert spec.cost_tier == CostTier.UNKNOWN


# ------------------------------------------------------------------ #
# T5-T7, T18-T19: Workflow cost_tier
# ------------------------------------------------------------------ #


class TestWorkflowCostTier:
    def test_default_none(self):
        """T5: Workflow default cost_tier → None."""
        from app.registry.workflow import Workflow
        wf = Workflow(id="t", version="1.0", capability="c", provider="p", backend="b")
        assert wf.cost_tier is None


# ------------------------------------------------------------------ #
# T8: _effective_cost_tier
# ------------------------------------------------------------------ #


class TestEffectiveCostTier:
    def test_workflow_override(self):
        """T8: workflow cost_tier overrides backend."""
        from app.registry.workflow import Workflow
        from app.agent import Agent
        wf = Workflow(id="t", version="1.0", capability="c", provider="p", backend="b",
                      cost_tier=CostTier.FREE)
        backend = BackendSpec("b", "http://b", kind="remote_comfyui")  # UNKNOWN
        assert Agent._effective_cost_tier(wf, backend) == CostTier.FREE

    def test_workflow_none_inherits_backend(self):
        """T8: workflow None → inherits backend."""
        from app.registry.workflow import Workflow
        from app.agent import Agent
        wf = Workflow(id="t", version="1.0", capability="c", provider="p", backend="b")
        backend = BackendSpec("b", "http://b", kind="local_comfyui")  # FREE
        assert Agent._effective_cost_tier(wf, backend) == CostTier.FREE

    def test_no_backend_unknown(self):
        """T8: no backend → UNKNOWN."""
        from app.registry.workflow import Workflow
        from app.agent import Agent
        wf = Workflow(id="t", version="1.0", capability="c", provider="p", backend="b")
        assert Agent._effective_cost_tier(wf, None) == CostTier.UNKNOWN

    def test_backend_paid_workflow_paid(self):
        """T8: backend PAID + workflow PAID → PAID."""
        from app.registry.workflow import Workflow
        from app.agent import Agent
        wf = Workflow(id="t", version="1.0", capability="c", provider="p", backend="b",
                      cost_tier=CostTier.PAID)
        backend = BackendSpec("b", "http://b", cost_tier=CostTier.PAID)
        assert Agent._effective_cost_tier(wf, backend) == CostTier.PAID

    def test_backend_free_workflow_none(self):
        """T8: backend FREE + workflow None → FREE."""
        from app.registry.workflow import Workflow
        from app.agent import Agent
        wf = Workflow(id="t", version="1.0", capability="c", provider="p", backend="b")
        backend = BackendSpec("b", "http://b", kind="local_comfyui")
        assert Agent._effective_cost_tier(wf, backend) == CostTier.FREE


# ------------------------------------------------------------------ #
# T9-T13: BackendCatalog.choose cost_tier filter
# ------------------------------------------------------------------ #


class TestBackendCatalogChoose:
    def test_free_backend_allowed(self):
        """T9: FREE backend → allowed."""
        cat = BackendCatalog([
            BackendSpec("a", "http://a", kind="local_comfyui", priority=1),
        ])
        result = cat.choose("image.generate")
        assert result is not None
        assert result.backend_id == "a"

    def test_trial_backend_allowed(self):
        """T10: TRIAL backend → allowed."""
        cat = BackendCatalog([
            BackendSpec("t", "http://t", cost_tier=CostTier.TRIAL, priority=1),
        ])
        result = cat.choose("image.generate")
        assert result is not None
        assert result.backend_id == "t"

    def test_paid_backend_excluded(self):
        """T11: PAID backend → excluded from auto-selection."""
        cat = BackendCatalog([
            BackendSpec("p", "http://p", cost_tier=CostTier.PAID, priority=100),
        ])
        result = cat.choose("image.generate")
        assert result is None

    def test_unknown_backend_excluded(self):
        """T12: UNKNOWN backend → excluded from auto-selection."""
        cat = BackendCatalog([
            BackendSpec("u", "http://u", kind="remote_comfyui", priority=100),
        ])
        result = cat.choose("image.generate")
        assert result is None

    def test_allow_paid_includes_paid(self):
        """T13: allow_paid=True → PAID allowed."""
        cat = BackendCatalog([
            BackendSpec("p", "http://p", cost_tier=CostTier.PAID, priority=100),
        ])
        result = cat.choose("image.generate", allow_paid=True)
        assert result is not None
        assert result.backend_id == "p"

    def test_mixed_free_and_paid_selects_free(self):
        """Among FREE + PAID backends, FREE is chosen (PAID excluded)."""
        cat = BackendCatalog([
            BackendSpec("free", "http://free", kind="local_comfyui", priority=1),
            BackendSpec("paid", "http://paid", cost_tier=CostTier.PAID, priority=100),
        ])
        result = cat.choose("image.generate")
        assert result is not None
        assert result.backend_id == "free"

    def test_mixed_free_and_unknown_selects_free(self):
        """Among FREE + UNKNOWN backends, FREE is chosen (UNKNOWN excluded)."""
        cat = BackendCatalog([
            BackendSpec("free", "http://free", kind="local_comfyui", priority=1),
            BackendSpec("unk", "http://unk", kind="remote_comfyui", priority=100),
        ])
        result = cat.choose("image.generate")
        assert result is not None
        assert result.backend_id == "free"


# ------------------------------------------------------------------ #
# T14-T15: from_env
# ------------------------------------------------------------------ #


class TestFromEnvCostTier:
    def test_default_local_free(self):
        """T14: from_env default (no env) → local_comfyui → FREE."""
        old_remote = os.environ.get("COMFY_REMOTE_URL")
        old_backends = os.environ.get("COMFY_BACKENDS")
        old_url = os.environ.get("COMFY_URL")
        try:
            os.environ.pop("COMFY_REMOTE_URL", None)
            os.environ.pop("COMFY_BACKENDS", None)
            os.environ.pop("COMFY_URL", None)
            cat = BackendCatalog.from_env()
            assert len(cat.backends) == 1
            assert cat.backends[0].kind == "local_comfyui"
            assert cat.backends[0].cost_tier == CostTier.FREE
        finally:
            if old_remote is not None:
                os.environ["COMFY_REMOTE_URL"] = old_remote
            if old_backends is not None:
                os.environ["COMFY_BACKENDS"] = old_backends
            if old_url is not None:
                os.environ["COMFY_URL"] = old_url

    def test_remote_url_unknown(self):
        """T15: COMFY_REMOTE_URL → remote → UNKNOWN."""
        old = os.environ.get("COMFY_REMOTE_URL")
        try:
            os.environ["COMFY_REMOTE_URL"] = "http://remote:8188"
            cat = BackendCatalog.from_env()
            assert cat.backends[0].kind == "remote_comfyui"
            assert cat.backends[0].cost_tier == CostTier.UNKNOWN
        finally:
            if old is None:
                os.environ.pop("COMFY_REMOTE_URL", None)
            else:
                os.environ["COMFY_REMOTE_URL"] = old

    def test_comfy_backends_json_with_cost_tier(self):
        """COMFY_BACKENDS JSON with explicit cost_tier."""
        old = os.environ.get("COMFY_BACKENDS")
        old_remote = os.environ.get("COMFY_REMOTE_URL")
        try:
            os.environ.pop("COMFY_REMOTE_URL", None)
            os.environ["COMFY_BACKENDS"] = json.dumps([
                {"backend_id": "cloud", "base_url": "http://cloud", "kind": "cloud_comfyui",
                 "priority": 10, "cost_tier": "FREE"},
            ])
            cat = BackendCatalog.from_env()
            assert cat.backends[0].cost_tier == CostTier.FREE
        finally:
            if old is None:
                os.environ.pop("COMFY_BACKENDS", None)
            else:
                os.environ["COMFY_BACKENDS"] = old
            if old_remote is not None:
                os.environ["COMFY_REMOTE_URL"] = old_remote


# ------------------------------------------------------------------ #
# T16: COST_RANKING
# ------------------------------------------------------------------ #


class TestCostRanking:
    def test_ordering(self):
        """T16: FREE > TRIAL > UNKNOWN > PAID."""
        assert COST_RANKING[CostTier.FREE] > COST_RANKING[CostTier.TRIAL]
        assert COST_RANKING[CostTier.TRIAL] > COST_RANKING[CostTier.UNKNOWN]
        assert COST_RANKING[CostTier.UNKNOWN] > COST_RANKING[CostTier.PAID]


# ------------------------------------------------------------------ #
# T18-T19: load_workflow cost_tier parsing
# ------------------------------------------------------------------ #


class TestLoadWorkflowCostTier:
    def test_manifest_with_cost_tier(self, tmp_path):
        """T18: manifest JSON with cost_tier → parsed."""
        from app.registry.workflow import load_workflow
        manifest = {
            "id": "test", "version": "1.0.0", "capability": "image.generate",
            "provider": "comfyui", "cost_tier": "PAID",
        }
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))
        wf = load_workflow(manifest_path)
        assert wf.cost_tier == CostTier.PAID

    def test_manifest_without_cost_tier(self, tmp_path):
        """T19: manifest JSON without cost_tier → None."""
        from app.registry.workflow import load_workflow
        manifest = {
            "id": "test", "version": "1.0.0", "capability": "image.generate",
            "provider": "comfyui",
        }
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))
        wf = load_workflow(manifest_path)
        assert wf.cost_tier is None

    def test_manifest_invalid_cost_tier(self, tmp_path):
        """Invalid cost_tier value → None (ignored)."""
        from app.registry.workflow import load_workflow
        manifest = {
            "id": "test", "version": "1.0.0", "capability": "image.generate",
            "provider": "comfyui", "cost_tier": "INVALID",
        }
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))
        wf = load_workflow(manifest_path)
        assert wf.cost_tier is None


# ------------------------------------------------------------------ #
# CRITICAL TESTS (user-requested)
# ------------------------------------------------------------------ #


class TestCriticalScenarios:
    def test_critical_remote_unknown_excluded(self):
        """CRITICAL-1: remote backend UNKNOWN → capability exists, workflow exists,
        but auto-selection does NOT select it."""
        cat = BackendCatalog([
            BackendSpec("remote", "http://remote:8188", kind="remote_comfyui",
                        priority=100, capabilities={"image.generate"}),
        ])
        # Backend is UNKNOWN → excluded from auto-selection
        result = cat.choose("image.generate")
        assert result is None, "Remote UNKNOWN backend must be excluded from auto-selection"

    def test_critical_free_remote_allowed(self):
        """CRITICAL-2: explicitly declared FREE remote backend → allowed candidate."""
        cat = BackendCatalog([
            BackendSpec("remote_free", "http://remote:8188", kind="remote_comfyui",
                        priority=100, cost_tier=CostTier.FREE,
                        capabilities={"image.generate"}),
        ])
        result = cat.choose("image.generate")
        assert result is not None, "Explicitly FREE remote backend must be allowed"
        assert result.backend_id == "remote_free"
