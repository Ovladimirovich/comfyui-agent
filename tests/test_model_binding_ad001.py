"""AD-MODEL-BINDING-001: Model Requirement Semantics tests.

Проверяет:
- ModelRequirement контракт (kind vs identity)
- Compatibility правильно обрабатывает оба типа
- Selection детерминирован
- Legacy migration работает
- ExecutionPlan содержит resolved model bindings
- Provider/Backend не выполняют скрытый semantic selection
"""
from __future__ import annotations

import pytest

from app.agent import _resolve_model_requirements
from app.assets.store import AssetStore
from app.engine.plan import ExecutionPlan
from app.registry.model import ModelKind, ModelRegistry
from app.registry.workflow import ModelRequirement, Workflow, OutputSpec, WorkflowStatus


class TestModelRequirementContract:
    """Тесты контракта ModelRequirement."""

    def test_kind_requirement_creation(self):
        req = ModelRequirement.by_kind(ModelKind.CHECKPOINT)
        assert req.kind == ModelKind.CHECKPOINT
        assert req.identity is None

    def test_identity_requirement_creation(self):
        req = ModelRequirement.by_identity('foo.safetensors')
        assert req.kind is None
        assert req.identity == 'foo.safetensors'

    def test_cannot_create_with_both(self):
        with pytest.raises(ValueError, match='одновременно'):
            ModelRequirement(kind=ModelKind.CHECKPOINT, identity='foo.safetensors')

    def test_cannot_create_with_neither(self):
        with pytest.raises(ValueError, match='либо kind, либо identity'):
            ModelRequirement()

    def test_to_dict_kind(self):
        req = ModelRequirement.by_kind(ModelKind.CHECKPOINT)
        assert req.to_dict() == {'kind': 'checkpoint'}

    def test_to_dict_identity(self):
        req = ModelRequirement.by_identity('foo.safetensors')
        assert req.to_dict() == {'identity': 'foo.safetensors'}

    def test_from_dict_kind(self):
        req = ModelRequirement.from_dict({'kind': 'checkpoint'})
        assert req.kind == ModelKind.CHECKPOINT
        assert req.identity is None

    def test_from_dict_identity(self):
        req = ModelRequirement.from_dict({'identity': 'foo.safetensors'})
        assert req.kind is None
        assert req.identity == 'foo.safetensors'

    def test_from_dict_both_raises(self):
        with pytest.raises(ValueError, match='одновременно'):
            ModelRequirement.from_dict({'kind': 'checkpoint', 'identity': 'foo.safetensors'})

    def test_from_dict_neither_raises(self):
        with pytest.raises(ValueError, match='либо'):
            ModelRequirement.from_dict({})


class TestModelRequirementResolution:
    """Тесты разрешения model requirements в concrete identities."""

    def test_kind_resolution_with_registry(self):
        mr = ModelRegistry()
        mr._catalog['local'] = {
            'a.safetensors': type('MI', (), {'name': 'a.safetensors', 'backend_id': 'local', 'kind': ModelKind.CHECKPOINT})(),
            'b.safetensors': type('MI', (), {'name': 'b.safetensors', 'backend_id': 'local', 'kind': ModelKind.CHECKPOINT})(),
        }
        reqs = [ModelRequirement.by_kind(ModelKind.CHECKPOINT)]
        bindings = _resolve_model_requirements(reqs, {'a.safetensors', 'b.safetensors'}, mr, 'local')
        # Deterministic: should pick first by name sort when registry.resolve returns first
        assert 'checkpoint' in bindings
        assert bindings['checkpoint'] in ('a.safetensors', 'b.safetensors')

    def test_kind_resolution_with_user_preference(self):
        mr = ModelRegistry()
        mr._catalog['local'] = {
            'a.safetensors': type('MI', (), {'name': 'a.safetensors', 'backend_id': 'local', 'kind': ModelKind.CHECKPOINT})(),
            'b.safetensors': type('MI', (), {'name': 'b.safetensors', 'backend_id': 'local', 'kind': ModelKind.CHECKPOINT})(),
        }
        reqs = [ModelRequirement.by_kind(ModelKind.CHECKPOINT)]
        bindings = _resolve_model_requirements(reqs, {'a.safetensors', 'b.safetensors'}, mr, 'local', user_preference='b.safetensors')
        assert bindings['checkpoint'] == 'b.safetensors'

    def test_identity_resolution(self):
        reqs = [ModelRequirement.by_identity('foo.safetensors')]
        bindings = _resolve_model_requirements(reqs, {'foo.safetensors', 'bar.safetensors'})
        assert bindings['foo.safetensors'] == 'foo.safetensors'

    def test_deterministic_without_registry(self):
        """Without ModelRegistry, selection should be deterministic (sorted)."""
        reqs = [ModelRequirement.by_kind(ModelKind.CHECKPOINT)]
        bindings = _resolve_model_requirements(reqs, {'c.safetensors', 'a.safetensors', 'b.safetensors'})
        # Should pick 'a.safetensors' (first alphabetically)
        assert bindings['checkpoint'] == 'a.safetensors'

    def test_deterministic_different_insertion_order(self):
        """Same candidates in different insertion order -> same result."""
        reqs = [ModelRequirement.by_kind(ModelKind.CHECKPOINT)]
        bindings1 = _resolve_model_requirements(reqs, {'a', 'b', 'c'})
        bindings2 = _resolve_model_requirements(reqs, {'c', 'a', 'b'})
        bindings3 = _resolve_model_requirements(reqs, {'b', 'c', 'a'})
        assert bindings1 == bindings2 == bindings3


class TestCompatibilityWithTypedRequirements:
    """Тесты compatibility с новым typed contract."""

    def test_exact_identity_satisfied(self):
        wf = Workflow(
            id='test', version='1.0.0', capability='image.generate',
            provider='comfyui', backend='local_comfyui',
            outputs={'result': OutputSpec('9', 'image')},
            model_requirements=[ModelRequirement.by_identity('foo.safetensors')],
            required_custom_nodes=[],
            requirements={},
        )
        from app.registry.compatibility import evaluate_compatibility
        from app.registry.runtime import RuntimeInfo
        rt = RuntimeInfo(accelerator='cuda', vram_gb=12.0, fp16=True)
        status, reasons = evaluate_compatibility(wf, rt, models={'foo.safetensors', 'bar.safetensors'})
        assert status == WorkflowStatus.AVAILABLE
        assert reasons == []

    def test_exact_identity_missing(self):
        wf = Workflow(
            id='test', version='1.0.0', capability='image.generate',
            provider='comfyui', backend='local_comfyui',
            outputs={'result': OutputSpec('9', 'image')},
            model_requirements=[ModelRequirement.by_identity('foo.safetensors')],
            required_custom_nodes=[],
            requirements={},
        )
        from app.registry.compatibility import evaluate_compatibility
        from app.registry.runtime import RuntimeInfo
        rt = RuntimeInfo(accelerator='cuda', vram_gb=12.0, fp16=True)
        status, reasons = evaluate_compatibility(wf, rt, models={'bar.safetensors'})
        assert status == WorkflowStatus.UNAVAILABLE
        assert any('missing_model' in str(r).lower() for r in reasons)

    def test_kind_requirement_satisfied(self):
        wf = Workflow(
            id='test', version='1.0.0', capability='image.generate',
            provider='comfyui', backend='local_comfyui',
            outputs={'result': OutputSpec('9', 'image')},
            model_requirements=[ModelRequirement.by_kind(ModelKind.CHECKPOINT)],
            required_custom_nodes=[],
            requirements={},
        )
        from app.registry.compatibility import evaluate_compatibility
        from app.registry.runtime import RuntimeInfo
        rt = RuntimeInfo(accelerator='cuda', vram_gb=12.0, fp16=True)
        status, reasons = evaluate_compatibility(wf, rt, models={'a.safetensors', 'b.safetensors'})
        assert status == WorkflowStatus.AVAILABLE

    def test_kind_requirement_no_models(self):
        wf = Workflow(
            id='test', version='1.0.0', capability='image.generate',
            provider='comfyui', backend='local_comfyui',
            outputs={'result': OutputSpec('9', 'image')},
            model_requirements=[ModelRequirement.by_kind(ModelKind.CHECKPOINT)],
            required_custom_nodes=[],
            requirements={},
        )
        from app.registry.compatibility import evaluate_compatibility
        from app.registry.runtime import RuntimeInfo
        rt = RuntimeInfo(accelerator='cuda', vram_gb=12.0, fp16=True)
        status, reasons = evaluate_compatibility(wf, rt, models=set())
        assert status == WorkflowStatus.UNAVAILABLE


class TestLegacyMigration:
    """Тесты миграции legacy required_models."""

    def test_legacy_checkpoint_migrated_to_kind(self):
        from app.registry.workflow import load_workflow
        import json, tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            manifest = {
                'id': 'test',
                'version': '1.0.0',
                'capability': 'image.generate',
                'provider': 'comfyui',
                'backend': 'local_comfyui',
                'inputs': {},
                'asset_inputs': {},
                'outputs': {'result': {'node': '9', 'kind': 'image'}},
                'parameters': {},
                'required_models': ['checkpoint'],
                'required_custom_nodes': [],
            }
            path = os.path.join(tmp, 'manifest.json')
            with open(path, 'w') as f:
                json.dump(manifest, f)
            wf = load_workflow(path)
            assert wf.model_requirements == [ModelRequirement.by_kind(ModelKind.CHECKPOINT)]
            assert wf.contract_version == 1

    def test_legacy_exact_model_migrated_to_identity(self):
        from app.registry.workflow import load_workflow
        import json, tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            manifest = {
                'id': 'test',
                'version': '1.0.0',
                'capability': 'image.generate',
                'provider': 'comfyui',
                'backend': 'local_comfyui',
                'inputs': {},
                'asset_inputs': {},
                'outputs': {'result': {'node': '9', 'kind': 'image'}},
                'parameters': {},
                'required_models': ['my_model.safetensors'],
                'required_custom_nodes': [],
            }
            path = os.path.join(tmp, 'manifest.json')
            with open(path, 'w') as f:
                json.dump(manifest, f)
            wf = load_workflow(path)
            assert wf.model_requirements == [ModelRequirement.by_identity('my_model.safetensors')]
            assert wf.contract_version == 1


class TestExecutionPlanModelBindings:
    """Тесты что ExecutionPlan содержит resolved model bindings."""

    def test_plan_has_model_bindings(self):
        plan = ExecutionPlan(
            capability='image.generate',
            workflow_id='txt2img',
            version='1.0.0',
            model_bindings={'checkpoint': 'cyberrealistic_v80.safetensors'},
        )
        assert plan.model_bindings == {'checkpoint': 'cyberrealistic_v80.safetensors'}

    def test_plan_empty_model_bindings_by_default(self):
        plan = ExecutionPlan(
            capability='image.generate',
            workflow_id='txt2img',
            version='1.0.0',
        )
        assert plan.model_bindings == {}
