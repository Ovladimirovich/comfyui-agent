"""
S6 — Self-Test mapping: gate, single entry, transport, no threads.

Покрывает acceptance S6 (§16) и NG-инварианты:
  1. Единственный явный user-initiated entry: Agent.run_self_test(...).
  2. Gate: детерминированный отказ, повтор refusing-ноды = тот же отказ (кэш)
     без повторной оценки и БЕЗ исполнения.
  3. Отказы: needs_knowledge / unknown_node / forbidden / requires_confirmation /
     not_standalone / cost_not_free / no_workflow_source / needs_input_asset /
     no_comfy_client.
  4. Роль ноды из registry-модели (query.classify_role).
  5. BLOCK: отказ ничего не записывает (validated/claims не появляются).
  6. Транспорт: RuntimeValidator работает с реальным ComfyClient API
     (queue_prompt/get_history) и legacy (queue/history fallback).
  7. NG: ни одного потока в S6-коде; deprecated shim без thread и с 2 аргументами.
"""

import pytest
from unittest.mock import MagicMock

from app.agent import Agent
from app.assets.store import AssetStore
from app.knowledge.core import KnowledgeCore
from app.knowledge.node_schema import FieldSpec, NodeSchema
from app.knowledge.runtime_validator import (
    RuntimeValidator,
    ValidationResult,
    RuntimeEvidence,
)
from app.registry.backends import BackendCatalog, BackendSpec
from app.registry.cost import CostTier


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #


def _field(name, type_, required=True, default=None):
    return FieldSpec(name=name, type=type_, required=required, default=default)


def _schema(class_type, module="nodes", category="testing",
            required=(), optional=(), outputs=("IMAGE",)):
    return NodeSchema(
        class_type=class_type, display_name=class_type, category=category,
        input_required=tuple(required), input_optional=tuple(optional),
        output_types=tuple(outputs), output_names=tuple(outputs),
        python_module=module, discovered_at=0.0, source="test",
    )


class FakeComfyUI:
    """Реальный контракт ComfyClient: queue_prompt/get_history."""

    def __init__(self, status="success"):
        self.calls = {"queue_prompt": [], "get_history": []}
        self.status = status

    def queue_prompt(self, prompt, client_id=None, extra_data=None):
        self.calls["queue_prompt"].append(prompt)
        return {"prompt_id": "p1"}

    def get_history(self, prompt_id=None):
        self.calls["get_history"].append(prompt_id)
        if self.status == "error":
            return {"p1": {"status": {"status_str": "error",
                                      "messages": ["boom"]}, "outputs": {}}}
        return {"p1": {"status": {"status_str": "success"}, "outputs": {}}}


def _core_with_schema(tmp_path, schema, client=None) -> tuple[KnowledgeCore, FakeComfyUI]:
    client = client or FakeComfyUI()
    core = KnowledgeCore(
        data_dir=str(tmp_path / "kc"),
        runtime_validator=RuntimeValidator(comfy_client=client),
    )
    core._schemas[schema.class_type] = schema
    return core, client


def _agent(core, backend_id="local_comfyui", store_root="tests/__tmp_selftest__"):
    backends = BackendCatalog([
        BackendSpec(backend_id="local_comfyui", base_url="http://127.0.0.1:8188",
                    kind="local_comfyui"),
    ])
    store = AssetStore(root=store_root)
    return Agent(store, knowledge_core=core, backends=backends), backends


# Позитивные сценарии (gate passes)
S_HEAD = _schema(
    "ExampleImageGen", module="nodes", category="only for testing",
    required=(_field("prompt", "STRING", default="hello"),),
    outputs=("IMAGE",),
)
# FORBIDDEN: keyword "shell"
S_FORBIDDEN = _schema(
    "ShellNode", module="custom_nodes.shell_runner", category="testing",
    required=(_field("prompt", "STRING"),), outputs=("IMAGE",),
)
# REQUIRES_CONFIRMATION (network keyword "api") и head-роль (для точного совпадения)
S_NETWORK = _schema(
    "APIGenNode", module="comfy_api_nodes.nodes_api_client", category="testing",
    required=(_field("prompt", "STRING"),), outputs=("IMAGE",),
)
# not_standalone: loader (GRAPH outputs)
S_LOADER = _schema(
    "FakeCheckpointLoader", module="nodes", category="testing",
    required=(_field("ckpt_name", "STRING"),),
    outputs=("MODEL", "CLIP", "VAE"),
)
# no_workflow_source: head без prompt (нет кандидата/шаблона)
S_EMPTY_HEAD = _schema(
    "EmptyHeadNode", module="nodes", category="testing",
    optional=(_field("seed", "INT", required=False, default=0),),
    outputs=("IMAGE",),
)
# needs_input_asset: processor c required IMAGE (S6 минимальный scope)
S_PROCESSOR = _schema(
    "UpscaleNode", module="nodes", category="testing",
    required=(_field("image", "IMAGE"), _field("prompt", "STRING", default="x")),
    outputs=("IMAGE",),
)
# Не head и не процессор: fragment + no source
S_TEXT_GEN = _schema(
    "TextGenNode", module="nodes", category="testing",
    required=(_field("prompt", "STRING"),), outputs=("STRING",),
)


# ------------------------------------------------------------------ #
# S6 tests
# ------------------------------------------------------------------ #


class TestSelfTestSingleEntry:
    """Acceptance §16.1: один явный user-initiated entry point."""

    def test_run_self_test_is_the_only_public_entry(self):
        assert callable(getattr(Agent, "run_self_test", None))
        assert "S6" in Agent.run_self_test.__doc__

    def test_ng_no_threads_in_s6_source(self):
        import app.agent as agent_module
        src = agent_module.__file__
        text = open(src, encoding="utf-8").read()
        assert "import threading" not in text
        assert "threading.Thread" not in text


class TestSelfTestGateRefusals:
    """Acceptance §16.2-16.4: детерминированные отказы и повтор без исполнения."""

    def test_needs_knowledge(self, tmp_path):
        # Без knowledge_core — сразу отказ (AD-47: UNKNOWN → отказ).
        store = AssetStore(root="tests/__tmp_selftest__")
        agent = Agent(store, backends=BackendCatalog([
            BackendSpec(backend_id="local_comfyui", base_url="http://127.0.0.1:8188",
                        kind="local_comfyui"),
        ]))
        result = agent.run_self_test("ExampleImageGen", "local_comfyui")
        assert result["status"] == "refused"
        assert "needs_knowledge" in result["refusal_reasons"]

    def test_unknown_node(self, tmp_path):
        core, _ = _core_with_schema(tmp_path, S_HEAD)
        agent, _ = _agent(core)
        result = agent.run_self_test("DoesNotExistNode", "local_comfyui")
        assert result["status"] == "refused"
        assert result["refusal_reasons"] == ["unknown_node"]

    def test_forbidden_refusal(self, tmp_path):
        core, client = _core_with_schema(tmp_path, S_FORBIDDEN)
        agent, _ = _agent(core)
        result = agent.run_self_test("ShellNode", "local_comfyui")
        assert result["status"] == "refused"
        assert result["refusal_reasons"] == ["forbidden"]
        # Исполнения не было (гейт-отказ до транспорта).
        assert client.calls["queue_prompt"] == []
        assert client.calls["get_history"] == []

    def test_requires_confirmation_refusal(self, tmp_path):
        core, _ = _core_with_schema(tmp_path, S_NETWORK)
        agent, _ = _agent(core)
        result = agent.run_self_test("APIGenNode", "local_comfyui")
        assert result["status"] == "refused"
        assert result["refusal_reasons"] == ["requires_confirmation"]

    def test_not_standalone_refusal(self, tmp_path):
        # Роль из registry-модели: loader не может быть standalone self-тестирован.
        core, _ = _core_with_schema(tmp_path, S_LOADER)
        agent, _ = _agent(core)
        result = agent.run_self_test("FakeCheckpointLoader", "local_comfyui")
        assert result["status"] == "refused"
        assert "not_standalone" in result["refusal_reasons"]

    def test_cost_not_free_refusal(self, tmp_path):
        core, _ = _core_with_schema(tmp_path, S_HEAD)
        paid = BackendCatalog([
            BackendSpec(backend_id="cloud_pro", base_url="https://comfy.example",
                        kind="cloud_comfyui", cost_tier=CostTier.PAID),
        ])
        store = AssetStore(root="tests/__tmp_selftest__")
        agent = Agent(store, knowledge_core=core, backends=paid)
        result = agent.run_self_test("ExampleImageGen", "cloud_pro")
        assert result["status"] == "refused"
        assert "cost_not_free" in result["refusal_reasons"]

    def test_unknown_backend_cost_not_free(self, tmp_path):
        core, _ = _core_with_schema(tmp_path, S_HEAD)
        agent, _ = _agent(core)
        result = agent.run_self_test("ExampleImageGen", "no_such_backend")
        assert result["status"] == "refused"
        assert "cost_not_free" in result["refusal_reasons"]

    def test_no_comfy_client_refusal(self, tmp_path):
        # Валидатор есть, но без клиента и безуказанного endpoint/provider.
        core = KnowledgeCore(data_dir=str(tmp_path / "kc"))
        core._schemas[S_HEAD.class_type] = S_HEAD
        agent, _ = _agent(core)
        result = agent.run_self_test("ExampleImageGen", "local_comfyui")
        assert result["status"] == "refused"
        assert result["refusal_reasons"] == ["no_comfy_client"]

    def test_no_workflow_source_refusal(self, tmp_path):
        # Head без prompt: нет кандидата/шаблона и нет registry-графа.
        core, _ = _core_with_schema(tmp_path, S_EMPTY_HEAD)
        agent, _ = _agent(core)
        result = agent.run_self_test("EmptyHeadNode", "local_comfyui")
        assert result["status"] == "refused"
        assert result["refusal_reasons"] == ["no_workflow_source"]

    def test_needs_input_asset_refusal(self, tmp_path):
        # Processor с required IMAGE — S6 минимальный scope (A6).
        core, client = _core_with_schema(tmp_path, S_PROCESSOR)
        agent, _ = _agent(core)
        result = agent.run_self_test("UpscaleNode", "local_comfyui")
        assert result["status"] == "refused"
        assert result["refusal_reasons"] == ["needs_input_asset"]
        assert client.calls["queue_prompt"] == []

    def test_refusal_is_cached_and_repeat_is_empty(self, tmp_path):
        """Повтор refusing-ноды → тот же отказ, без повторной оценки/исполнения."""
        core, client = _core_with_schema(tmp_path, S_PROCESSOR)
        agent, _ = _agent(core)
        first = agent.run_self_test("UpscaleNode", "local_comfyui")
        second = agent.run_self_test("UpscaleNode", "local_comfyui")
        assert first["status"] == "refused"
        assert first["refusal_reasons"] == second["refusal_reasons"] == ["needs_input_asset"]
        # Исполнения не было вообще (гейт-отказ из кэша).
        assert client.calls["queue_prompt"] == []
        assert client.calls["get_history"] == []
        assert agent._selftest_refusals["UpscaleNode"] == ["needs_input_asset"]

    def test_refusal_blocks_writes(self, tmp_path):
        """Блокировка (незапись): отказ не создаёт validated/confirmed состояния."""
        core, client = _core_with_schema(tmp_path, S_PROCESSOR)
        agent, _ = _agent(core)
        result = agent.run_self_test("UpscaleNode", "local_comfyui")
        assert result["status"] == "refused"
        assert core.get_validated_nodes() == {}
        assert core.get_confirmed_claims() == []
        assert agent.get_validated_nodes() == {}
        assert client.calls["queue_prompt"] == []


class TestSelfTestSuccessPath:
    """Acceptance §16.6/16.7: gate pass → реальный validate_runtime (2 аргумента),
    CONFIRMED claim, один production-путь."""

    def test_success_synthesized_and_confirmed(self, tmp_path):
        core, client = _core_with_schema(tmp_path, S_HEAD)
        agent, _ = _agent(core)
        result = agent.run_self_test("ExampleImageGen", "local_comfyui")

        assert result["status"] == "success"
        assert result["refusal_reasons"] == []
        assert result["node_class"] == "ExampleImageGen"
        assert result["backend_id"] == "local_comfyui"
        assert result["workflow_source"] == "synthesized"
        assert result["validation_result"] == "SUCCESS"
        assert result["claim_status"] == "CONFIRMED"

        # Transport прошёл через реальный ComfyClient API (queue_prompt/get_history).
        assert len(client.calls["queue_prompt"]) == 1
        assert client.calls["get_history"] == ["p1"]

        # Core записал validated + CONFIRMED claim (persistence-факт).
        assert core.get_validated_nodes().get("ExampleImageGen") is True
        assert any(getattr(c, "subject", None) == "ExampleImageGen"
                   for c in core.get_confirmed_claims())

    def test_validate_node_called_with_two_args(self, tmp_path):
        """A7: validate_node вызывается с (node_class, workflow) — 2 аргумента."""
        core = KnowledgeCore(data_dir=str(tmp_path / "kc"))
        core._schemas[S_HEAD.class_type] = S_HEAD
        spy_validator = MagicMock()
        spy_validator.validate_node = MagicMock(
            return_value=RuntimeEvidence(
                node_class="ExampleImageGen",
                validation_result=ValidationResult.SUCCESS,
                execution_time_ms=1.0,
            )
        )
        core._runtime_validator = spy_validator
        agent, _ = _agent(core)
        result = agent.run_self_test("ExampleImageGen", "local_comfyui")
        assert result["status"] == "success"
        call_args = spy_validator.validate_node.call_args
        assert call_args is not None
        args, kwargs = call_args
        assert len(args) == 2
        assert args[0] == "ExampleImageGen"
        assert isinstance(args[1], dict)

    def test_failure_path_reports_failure_without_claim(self, tmp_path):
        core, client = _core_with_schema(tmp_path, S_HEAD, client=FakeComfyUI(status="error"))
        agent, _ = _agent(core)
        result = agent.run_self_test("ExampleImageGen", "local_comfyui")
        assert result["status"] == "failure"
        assert result["validation_result"] == "FAILURE"
        assert result["claim_status"] is None
        # FAILURE — не upgrade claims, но validated=False фиксируется как факт.
        assert core.get_validated_nodes().get("ExampleImageGen") is False


class TestSelfTestValidationScore:
    """S6 §7: источник validated нод для score — core-derived, legacy fallback."""

    def _workflow_obj(self, node_types):
        return MagicMock(workflow={"nodes": [{"type": t} for t in node_types]})

    def test_score_from_knowledge_core(self, tmp_path):
        core = KnowledgeCore(data_dir=str(tmp_path / "kc"))
        core._validated_nodes = {"X": True, "Y": False}
        agent, _ = _agent(core)
        score = agent._calculate_validation_score(self._workflow_obj(["X", "Y", "Z"]))
        assert score == 1  # только реально выполненные (True)

    def test_score_legacy_fallback_without_core(self, tmp_path):
        agent = Agent(asset_store=AssetStore(root="tests/__tmp_selftest__"))
        agent._validated_nodes = {"X": True}
        score = agent._calculate_validation_score(self._workflow_obj(["X", "Y"]))
        assert score == 1

    def test_score_zero_when_not_validated(self, tmp_path):
        core = KnowledgeCore(data_dir=str(tmp_path / "kc"))
        core._validated_nodes = {"X": True}
        agent, _ = _agent(core)
        score = agent._calculate_validation_score(self._workflow_obj(["not_x"]))
        assert score == 0


class TestSelfTestLegacyShim:
    """S6 §8: deprecated synchronous shim — 2 аргумента, без потоков."""

    def _agent_with_shim_validator(self, tmp_path):
        validator = MagicMock()
        validator.validate_node = MagicMock(return_value=RuntimeEvidence(
            node_class="TestNode",
            validation_result=ValidationResult.SUCCESS,
            execution_time_ms=1.0,
        ))
        store = AssetStore(root="tests/__tmp_selftest__")
        agent = Agent(store, runtime_validator=validator)
        mock_manifest = MagicMock()
        mock_manifest.workflow_id = "test_workflow"
        mock_manifest.version = "1.0.0"
        agent.registry._workflows = {
            "test_workflow": MagicMock(
                id="test_workflow", version="1.0.0",
                workflow={"nodes": [{"type": "TestNode", "inputs": {}}]},
            )
        }
        agent.registry.by_capability = MagicMock(return_value=[mock_manifest])
        agent.registry.get = MagicMock(return_value=agent.registry._workflows["test_workflow"])
        return agent, validator

    def test_shim_passes_two_args_and_is_synchronous(self, tmp_path):
        agent, validator = self._agent_with_shim_validator(tmp_path)
        agent._validate_capability_nodes_background("image.generate")
        # Синхронно: кэш заполнен сразу после вызова.
        assert agent.get_validated_nodes().get("TestNode") is True
        args, kwargs = validator.validate_node.call_args
        assert len(args) == 2
        assert args[0] == "TestNode"
        assert isinstance(args[1], dict)


class TestSelfTestTransport:
    """S6 §16.6 транспорт: real ComfyClient API + legacy fallback."""

    def test_real_client_api_success(self):
        client = FakeComfyUI(status="success")
        validator = RuntimeValidator(comfy_client=client)
        evidence = validator.validate_node("SaveImage", {"1": {"class_type": "SaveImage"}})
        assert evidence.validation_result == ValidationResult.SUCCESS
        assert client.calls["queue_prompt"] and client.calls["get_history"]

    def test_real_client_api_failure(self):
        client = FakeComfyUI(status="error")
        validator = RuntimeValidator(comfy_client=client)
        evidence = validator.validate_node("SaveImage", {"1": {"class_type": "SaveImage"}})
        assert evidence.validation_result == ValidationResult.FAILURE

    def test_legacy_queue_history_fallback(self):
        class LegacyClient:
            def __init__(self):
                self.out = {"p1": {"status": {"status_str": "success"}, "outputs": {}}}

            def queue(self, prompt):
                return {"prompt_id": "p1"}

            def history(self, prompt_id):
                return self.out

        validator = RuntimeValidator(comfy_client=LegacyClient())
        evidence = validator.validate_node("Node", {"1": {"class_type": "Node"}})
        assert evidence.validation_result == ValidationResult.SUCCESS

    def test_no_transport_methods_returns_error(self):
        class BareClient:
            pass

        validator = RuntimeValidator(comfy_client=BareClient())
        evidence = validator.validate_node("Node", {"1": {"class_type": "Node"}})
        assert evidence.validation_result == ValidationResult.ERROR
        assert "queue_prompt" in evidence.error_message or "queue" in evidence.error_message