"""Tests for Extended Discovery (Steps 1-3 + §H.4 mapping gap).

Проверяют:
  - ComfyClient.discover_custom_node_packages() парсит /object_info корректно.
  - DiscoveryFacts frozen, merge, authority flags.
  - Agent._discover_facts() собирает факты с graceful degradation.
  - AD-18 сохраняется: при runtime=None + has_runtime_reqs → UNKNOWN.
  - §H.4: check_custom_node_requirement поддерживает node class name И package name.
"""
from __future__ import annotations

import pytest

from app.agent import Agent
from app.assets.store import AssetStore
from app.comfy.client import ComfyClient
from app.registry.discovery import DiscoveryFacts
from app.registry.runtime import RuntimeInfo
from app.registry.workflow import UnavailableReason, WorkflowStatus


# --------------------------------------------------------------------------- #
# ComfyClient.discover_custom_node_packages
# --------------------------------------------------------------------------- #


class _FakeClientWithObjectInfo:
    """Клиент с заданным /object_info для тестирования парсинга."""

    def __init__(self, object_info: dict):
        self._object_info = object_info

    def get_object_info(self) -> dict:
        return self._object_info


def test_discover_custom_node_packages_empty():
    """Пустой object_info → пустой dict."""
    client = _FakeClientWithObjectInfo({})
    result = ComfyClient.discover_custom_node_packages(client)
    assert result == {}


def test_discover_custom_node_packages_filters_builtins():
    """Built-in nodes (nodes.*, comfy_extras.*) не попадают в результат."""
    object_info = {
        "KSampler": {"python_module": "nodes"},
        "CheckpointLoaderSimple": {"python_module": "nodes"},
        "SaveAudio": {"python_module": "comfy_extras.nodes_audio"},
        "VAEDecode": {"python_module": "comfy_extras.nodes_video"},
    }
    client = _FakeClientWithObjectInfo(object_info)
    result = ComfyClient.discover_custom_node_packages(client)
    assert result == {}


def test_discover_custom_node_packages_extracts_custom():
    """custom_nodes.* и comfy_api_nodes.* извлекаются как package -> {node_class}."""
    object_info = {
        "PollinationsImageGen": {"python_module": "custom_nodes.pollinations-byop"},
        "SoniloTextToMusic": {"python_module": "comfy_api_nodes.nodes_sonilo"},
        "OpenAICompatibleChat": {"python_module": "custom_nodes.comfyui-openai-compatible"},
        "KSampler": {"python_module": "nodes"},
    }
    client = _FakeClientWithObjectInfo(object_info)
    result = ComfyClient.discover_custom_node_packages(client)
    assert result == {
        "pollinations-byop": {"PollinationsImageGen"},
        "nodes_sonilo": {"SoniloTextToMusic"},
        "comfyui-openai-compatible": {"OpenAICompatibleChat"},
    }


def test_discover_custom_node_packages_ignores_invalid_module():
    """Nodes без python_module или с невалидным format пропускаются."""
    object_info = {
        "GoodNode": {"python_module": "custom_nodes.my-pkg"},
        "NoModule": {},
        "BadModule": {"python_module": ""},
        "StringModule": {"python_module": 123},
    }
    client = _FakeClientWithObjectInfo(object_info)
    result = ComfyClient.discover_custom_node_packages(client)
    assert result == {"my-pkg": {"GoodNode"}}


def test_discover_custom_node_packages_handles_exception():
    """Если get_object_info бросает — exception propagates наружу.

    Graceful degradation реализуется на уровне Agent._discover_facts(),
    который ловит исключение и пробует NodeSchemaStore cache.
    """
    client = _FakeClientWithObjectInfo(None)

    def raise_exc():
        raise RuntimeError("connection refused")

    client.get_object_info = raise_exc
    with pytest.raises(RuntimeError, match="connection refused"):
        ComfyClient.discover_custom_node_packages(client)


# --------------------------------------------------------------------------- #
# DiscoveryFacts
# --------------------------------------------------------------------------- #


def test_discovery_facts_frozen():
    """DiscoveryFacts должен быть frozen — нельзя мутировать после создания."""
    facts = DiscoveryFacts(
        runtime=None, models=set(), custom_nodes={},
        runtime_available=False, models_available=False, custom_nodes_available=False,
    )
    with pytest.raises(AttributeError):
        facts.runtime = RuntimeInfo()  # type: ignore


def test_discovery_facts_authority_flags():
    """Флаги authority корректно отражают доступность источников."""
    rt = RuntimeInfo(accelerator="directml", vram_gb=12.0)
    facts = DiscoveryFacts(
        runtime=rt, models={"checkpoint"}, custom_nodes={"pkg": {"NodeA"}},
        runtime_available=True, models_available=True, custom_nodes_available=True,
    )
    assert facts.has_runtime is True
    assert facts.has_models is True
    assert facts.has_custom_nodes is True

    empty = DiscoveryFacts()
    assert empty.has_runtime is False
    assert empty.has_models is False
    assert empty.has_custom_nodes is False


def test_discovery_facts_merge():
    """Merge берёт non-empty значения из right поверх left."""
    left = DiscoveryFacts(
        runtime=None, models={"a"}, custom_nodes={},
        runtime_available=False, models_available=True, custom_nodes_available=False,
    )
    right = DiscoveryFacts(
        runtime=RuntimeInfo(accelerator="cpu"), models=set(),
        custom_nodes={"x": {"NodeX"}}, runtime_available=True,
        models_available=False, custom_nodes_available=True,
    )
    merged = left.merge(right)
    assert merged.runtime is not None
    assert merged.models == {"a"}  # left не пустой → остаётся
    assert merged.custom_nodes == {"x": {"NodeX"}}  # right не пустой → берётся
    assert merged.runtime_available is True
    assert merged.models_available is True
    assert merged.custom_nodes_available is True


# --------------------------------------------------------------------------- #
# Agent._discover_facts
# --------------------------------------------------------------------------- #


class _SpyClient:
    """Клиент-шпион: отслеживает вызовы методов discovery."""

    def __init__(
        self,
        system_stats=None,
        object_info=None,
        checkpoints=None,
        raise_on=None,
    ):
        self._system_stats = system_stats
        self._object_info = object_info or {}
        self._checkpoints = checkpoints or []
        self.raise_on = raise_on or set()
        self.calls = {"system_stats": 0, "object_info": 0, "checkpoints": 0}

    def get_system_stats(self):
        self.calls["system_stats"] += 1
        if "system_stats" in self.raise_on:
            raise RuntimeError("stats failed")
        return self._system_stats or {}

    def get_object_info(self):
        self.calls["object_info"] += 1
        if "object_info" in self.raise_on:
            raise RuntimeError("object_info failed")
        return self._object_info

    def discover_checkpoints(self):
        self.calls["checkpoints"] += 1
        if "checkpoints" in self.raise_on:
            raise RuntimeError("checkpoints failed")
        return self._checkpoints

    def discover_custom_node_packages(self):
        return ComfyClient.discover_custom_node_packages(self)


def test_discover_facts_full_success():
    """Все источники доступны → все флаги True, данные заполнены."""
    client = _SpyClient(
        system_stats={"devices": [{"type": "directml", "vram_total": 12 * 1024**3}]},
        object_info={
            "PollinationsImageGen": {"python_module": "custom_nodes.pollinations-byop"},
        },
        checkpoints=["model.safetensors"],
    )
    agent = Agent(AssetStore(root="__tmptest_disc_full__"))
    facts = agent._discover_facts(client, "local_comfyui")
    assert facts.runtime is not None
    assert facts.runtime_available is True
    assert facts.models == {"model.safetensors"}
    assert facts.models_available is True
    assert facts.custom_nodes == {"pollinations-byop": {"PollinationsImageGen"}}
    assert facts.custom_nodes_available is True


def test_discover_facts_runtime_fallback():
    """Runtime недоступен — models и custom_nodes всё равно собираются."""
    client = _SpyClient(
        system_stats=None,
        object_info={
            "MyNode": {"python_module": "custom_nodes.my-pkg"},
        },
        checkpoints=["ckpt"],
        raise_on={"system_stats"},
    )
    agent = Agent(AssetStore(root="__tmptest_disc_rt_fail__"))
    facts = agent._discover_facts(client, "local_comfyui")
    assert facts.runtime is None
    assert facts.runtime_available is False
    assert facts.models == {"ckpt"}
    assert facts.custom_nodes == {"my-pkg": {"MyNode"}}


def test_discover_facts_all_sources_fail():
    """Все live источники недоступны — кэш моделей и custom nodes загружается."""
    client = _SpyClient(raise_on={"system_stats", "object_info", "checkpoints"})
    agent = Agent(AssetStore(root="__tmptest_disc_all_fail__"))
    facts = agent._discover_facts(client, "local_comfyui")
    assert facts.runtime is None
    assert not facts.runtime_available
    # Cache моделей загружен из NodeSchemaStore
    assert facts.models  # non-empty from cache
    # Но availability остаётся False — AD-18: cache ≠ live
    assert not facts.models_available
    # Custom nodes тоже из cache
    assert facts.custom_nodes  # non-empty from cache
    assert not facts.custom_nodes_available


def test_discover_facts_no_model_registry_fallback():
    """Agent без ModelRegistry использует client.discover_checkpoints()."""
    client = _SpyClient(checkpoints=["foo.safetensors"])
    agent = Agent(AssetStore(root="__tmptest_disc_no_reg__"))
    assert agent.model_registry is None
    facts = agent._discover_facts(client, "local_comfyui")
    assert facts.models == {"foo.safetensors"}
    assert facts.models_available is True


def test_discover_facts_custom_nodes_filtering():
    """Built-in модули не попадают в custom_nodes."""
    client = _SpyClient(
        object_info={
            "KSampler": {"python_module": "nodes"},
            "VAEDecode": {"python_module": "comfy_extras.nodes_video"},
            "MyCustom": {"python_module": "custom_nodes.my-node"},
        },
    )
    agent = Agent(AssetStore(root="__tmptest_disc_filter__"))
    facts = agent._discover_facts(client, "local_comfyui")
    assert facts.custom_nodes == {"my-node": {"MyCustom"}}
    assert "nodes" not in facts.custom_nodes
    assert "comfy_extras.nodes_video" not in facts.custom_nodes


# --------------------------------------------------------------------------- #
# AD-18 preservation: _discover_facts не ломает UNKNOWN semantics
# --------------------------------------------------------------------------- #


def test_ad18_preserved_with_facts_runtime_none():
    """runtime=None + workflow с runtime-dependent reqs → UNKNOWN (AD-18)."""
    from app.registry.workflow import Workflow, OutputSpec
    from app.agent import Agent, AgentError
    from app.assets.store import AssetStore
    import json, pathlib

    tmp = pathlib.Path(__file__).parent / "__tmptest_ad18_facts__"
    tmp.mkdir(exist_ok=True, parents=True)

    # Создаём workflow с runtime-dependent требованиями
    manifest = {
        "id": "test_wf",
        "version": "1.0.0",
        "capability": "image.generate",
        "provider": "comfyui",
        "backend": "local_comfyui",
        "inputs": {},
        "asset_inputs": {},
        "outputs": {"result": {"node": "9", "kind": "image"}},
        "parameters": {},
        "required_models": [],
        "required_custom_nodes": [],
        "min_comfyui_version": "0.0.0",
        "requirements": {"min_vram_gb": 4, "fp16": True},
    }
    wf_json = {"9": {"class_type": "SaveImage", "inputs": {"images": ["6", 0]}}}
    d = tmp / "test_wf"
    d.mkdir(parents=True, exist_ok=True)
    (d / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (d / "workflow.json").write_text(json.dumps(wf_json), encoding="utf-8")

    agent = Agent(AssetStore(root=str(tmp / "store")), workflows_dir=str(tmp))
    # runtime=None, models есть, custom_nodes пуст
    facts = DiscoveryFacts(
        runtime=None,
        models={"checkpoint"},
        custom_nodes=set(),
        runtime_available=False,
        models_available=True,
        custom_nodes_available=False,
    )
    with pytest.raises(AgentError):
        agent._select_manifest(
            "image.generate", facts.runtime, facts.models, facts.custom_nodes
        )


def test_ad18_available_when_no_runtime_reqs_and_facts_present():
    """Workflow БЕЗ runtime-dependent требований + models/custom_nodes known → AVAILABLE."""
    from app.registry.workflow import Workflow, OutputSpec
    from app.agent import Agent
    from app.assets.store import AssetStore
    import json, pathlib

    tmp = pathlib.Path(__file__).parent / "__tmptest_avail_facts__"
    tmp.mkdir(exist_ok=True, parents=True)

    manifest = {
        "id": "simple_wf",
        "version": "1.0.0",
        "capability": "image.generate",
        "provider": "comfyui",
        "backend": "local_comfyui",
        "inputs": {},
        "asset_inputs": {},
        "outputs": {"result": {"node": "9", "kind": "image"}},
        "parameters": {},
        "required_models": [],
        "required_custom_nodes": [],
        "min_comfyui_version": "0.0.0",
        "requirements": {"accelerator": "any"},  # нет runtime-dependent
    }
    wf_json = {"9": {"class_type": "SaveImage", "inputs": {"images": ["6", 0]}}}
    d = tmp / "simple_wf"
    d.mkdir(parents=True, exist_ok=True)
    (d / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (d / "workflow.json").write_text(json.dumps(wf_json), encoding="utf-8")

    agent = Agent(AssetStore(root=str(tmp / "store")), workflows_dir=str(tmp))
    facts = DiscoveryFacts(
        runtime=None,
        models=set(),
        custom_nodes=set(),
        runtime_available=False,
        models_available=False,
        custom_nodes_available=False,
    )
    result = agent._select_manifest(
        "image.generate", facts.runtime, facts.models, facts.custom_nodes
    )
    assert result is not None
    assert result.id == "simple_wf"
    assert result.status == WorkflowStatus.AVAILABLE


# --------------------------------------------------------------------------- #
# §H.4 mapping gap: check_custom_node_requirement
# --------------------------------------------------------------------------- #


def test_requirement_by_node_class_found():
    """Требование по node class name → AVAILABLE (точное совпадение в value-set)."""
    from app.registry.discovery import check_custom_node_requirement
    inventory = {"pollinations-byop": {"PollinationsImageGen", "PollinationsTextGen"}}
    assert check_custom_node_requirement("PollinationsImageGen", inventory) is True
    assert check_custom_node_requirement("PollinationsTextGen", inventory) is True
    # Node из другого пакета
    assert check_custom_node_requirement("KSampler", inventory) is False


def test_requirement_by_package_found():
    """Требование по package name → AVAILABLE (точное совпадение по ключу)."""
    from app.registry.discovery import check_custom_node_requirement
    inventory = {"pollinations-byop": {"PollinationsImageGen"}}
    assert check_custom_node_requirement("pollinations-byop", inventory) is True
    # Частичное совпадение — НЕ должно работать (no fuzzy)
    assert check_custom_node_requirement("pollinations", inventory) is False
    assert check_custom_node_requirement("byop", inventory) is False


def test_unknown_node_class_missing():
    """Неизвестный node class → MISSING_CUSTOM_NODE."""
    from app.registry.discovery import check_custom_node_requirement
    inventory = {"pkg": {"KnownNode"}}
    assert check_custom_node_requirement("UnknownNode", inventory) is False


def test_unknown_package_missing():
    """Неизвестный package name → MISSING_CUSTOM_NODE."""
    from app.registry.discovery import check_custom_node_requirement
    inventory = {"known-pkg": {"SomeNode"}}
    assert check_custom_node_requirement("unknown-pkg", inventory) is False


def test_empty_inventory_returns_false():
    """Пустой inventory → False (downstream ставит UNAVAILABLE/UNKNOWN)."""
    from app.registry.discovery import check_custom_node_requirement
    assert check_custom_node_requirement("anything", {}) is False
    assert check_custom_node_requirement("anything", None) is False  # type: ignore


def test_hybrid_mixed_requirements():
    """Workflow с mixed requirements (node class + package) — оба формата работают."""
    from app.registry.discovery import check_custom_node_requirement
    inventory = {
        "nodes_sonilo": {"SoniloTextToMusic", "SoniloVideoToMusic"},
        "pollinations-byop": {"PollinationsImageGen"},
    }
    # Node class name из одного пакета
    assert check_custom_node_requirement("SoniloTextToMusic", inventory) is True
    # Package name другого пакета
    assert check_custom_node_requirement("pollinations-byop", inventory) is True
    # Node class из того же пакета, но другой нодой
    assert check_custom_node_requirement("SoniloVideoToMusic", inventory) is True


# --------------------------------------------------------------------------- #
# Step 7: NodeSchemaStore offline fallback
# --------------------------------------------------------------------------- #


def test_step7_live_success_ignores_cache():
    """A. Live discovery success → live inventory используется, cache игнорируется."""
    client = _SpyClient(
        object_info={
            "MyNode": {"python_module": "custom_nodes.my-pkg"},
        },
    )
    agent = Agent(AssetStore(root="__tmptest_s7_live__"))
    facts = agent._discover_facts(client, "local_comfyui")
    assert facts.custom_nodes == {"my-pkg": {"MyNode"}}
    assert facts.custom_nodes_available is True  # live source


def test_step7_live_success_empty_does_not_substitute_cache():
    """B. Live success + empty → empty сохранён, cache НЕ подставляется."""
    client = _SpyClient(object_info={})
    agent = Agent(AssetStore(root="__tmptest_s7_empty__"))
    facts = agent._discover_facts(client, "local_comfyui")
    assert facts.custom_nodes == {}
    assert facts.custom_nodes_available is True  # live returned empty, not failed


def test_step7_live_failure_uses_cache():
    """C. Live failure + cache hit → cached inventory, availability=False."""
    client = _SpyClient(raise_on={"object_info"})
    agent = Agent(AssetStore(root="__tmptest_s7_cache__"))
    facts = agent._discover_facts(client, "local_comfyui")
    assert facts.custom_nodes_available is False  # cache ≠ live
    assert facts.custom_nodes  # non-empty from NodeSchemaStore cache


def test_step7_live_failure_no_cache():
    """D. Live failure + missing cache → empty, availability=False."""
    # Создаём Agent с несуществующим data_dir (нет кэша)
    import tempfile, pathlib
    tmp = pathlib.Path(tempfile.mkdtemp())
    client = _SpyClient(raise_on={"object_info"})
    agent = Agent(AssetStore(root=str(tmp / "store")))
    # Monkeypatch node_schema store path to point to empty dir
    from app.knowledge.node_schema import NodeSchemaStore
    original_init = NodeSchemaStore.__init__

    def fake_init(self, data_dir=None):
        original_init(self, str(tmp / "no_cache"))

    NodeSchemaStore.__init__ = fake_init
    try:
        facts = agent._discover_facts(client, "local_comfyui")
        assert facts.custom_nodes == {}
        assert not facts.custom_nodes_available
    finally:
        NodeSchemaStore.__init__ = original_init


def test_step7_package_match_via_cache():
    """E. Exact package match через cache."""
    client = _SpyClient(raise_on={"object_info"})
    agent = Agent(AssetStore(root="__tmptest_s7_pkg__"))
    facts = agent._discover_facts(client, "local_comfyui")
    from app.registry.discovery import check_custom_node_requirement
    # pollinations-byop есть в реальном кэше
    assert check_custom_node_requirement("pollinations-byop", facts.custom_nodes) is True


def test_step7_node_class_match_via_cache():
    """F. Exact node-class match через cache."""
    client = _SpyClient(raise_on={"object_info"})
    agent = Agent(AssetStore(root="__tmptest_s7_cls__"))
    facts = agent._discover_facts(client, "local_comfyui")
    from app.registry.discovery import check_custom_node_requirement
    # PollinationsImageGen есть в реальном кэше
    assert check_custom_node_requirement("PollinationsImageGen", facts.custom_nodes) is True


def test_step7_no_fuzzy_matching():
    """G. Нет fuzzy matching — похожие, но не идентичные имена → False."""
    client = _SpyClient(raise_on={"object_info"})
    agent = Agent(AssetStore(root="__tmptest_s7_fuzzy__"))
    facts = agent._discover_facts(client, "local_comfyui")
    from app.registry.discovery import check_custom_node_requirement
    # Частичные совпадения не должны работать
    assert check_custom_node_requirement("pollinations", facts.custom_nodes) is False
    assert check_custom_node_requirement("byop", facts.custom_nodes) is False
    assert check_custom_node_requirement("PollinationsImage", facts.custom_nodes) is False


def test_step7_cache_cannot_elevate_availability():
    """H. Cache НЕ может повысить custom_nodes_available до True (AD-18 regression)."""
    client = _SpyClient(raise_on={"object_info"})
    agent = Agent(AssetStore(root="__tmptest_s7_avail__"))
    facts = agent._discover_facts(client, "local_comfyui")
    assert facts.custom_nodes_available is False
    assert facts.custom_nodes  # данные есть, но источник недоступен


# --------------------------------------------------------------------------- #
# Model cache fallback (Step 7 extension)
# --------------------------------------------------------------------------- #


def test_step7_model_live_success_ignores_cache():
    """A. Live model discovery success → live result, cache игнорируется."""
    client = _SpyClient(checkpoints=["live_model.safetensors"])
    agent = Agent(AssetStore(root="__tmptest_m_live__"))
    facts = agent._discover_facts(client, "local_comfyui")
    assert facts.models == {"live_model.safetensors"}
    assert facts.models_available is True


def test_step7_model_live_empty_does_not_use_cache():
    """B. Live success + empty — если live вернул [], кэш подставляется (knowledge gap).

    Пустой live-результат = knowledge gap (не 'точно нет моделей'), поэтому кэш
    заполняет пробел. models_available остаётся False — cache ≠ live.
    """
    client = _SpyClient(checkpoints=[])
    agent = Agent(AssetStore(root="__tmptest_m_empty__"))
    facts = agent._discover_facts(client, "local_comfyui")
    # Cache заполняет knowledge gap от пустого live
    assert facts.models  # non-empty from NodeSchemaStore cache
    # availability остаётся False — cache ≠ live (AD-18)
    assert not facts.models_available


def test_step7_model_live_failure_uses_cache():
    """C. Live failure + cache hit → cached models, models_available=False."""
    client = _SpyClient(raise_on={"checkpoints"})
    agent = Agent(AssetStore(root="__tmptest_m_cache__"))
    facts = agent._discover_facts(client, "local_comfyui")
    assert facts.models_available is False
    assert facts.models  # non-empty from NodeSchemaStore cache


def test_step7_model_live_failure_no_cache():
    """D. Live failure + empty cache → models={}, models_available=False."""
    import tempfile, pathlib
    tmp = pathlib.Path(tempfile.mkdtemp())
    client = _SpyClient(raise_on={"checkpoints"})
    agent = Agent(AssetStore(root=str(tmp / "store")))
    # Monkeypatch NodeSchemaStore to use empty dir
    from app.knowledge.node_schema import NodeSchemaStore
    orig = NodeSchemaStore.__init__
    NodeSchemaStore.__init__ = lambda self, data_dir=None: orig(self, str(tmp / "no_cache"))
    try:
        facts = agent._discover_facts(client, "local_comfyui")
        assert facts.models == set()
        assert not facts.models_available
    finally:
        NodeSchemaStore.__init__ = orig


def test_step7_cache_cannot_elevate_model_availability():
    """E. Cache НЕ может поднять models_available до True (AD-18 regression)."""
    client = _SpyClient(raise_on={"checkpoints"})
    agent = Agent(AssetStore(root="__tmptest_m_avail__"))
    facts = agent._discover_facts(client, "local_comfyui")
    assert facts.models_available is False
    assert facts.models  # but data is present


def test_step7_existing_required_models_semantics():
    """F. Legacy required_models=["checkpoint"] мигрируется в kind requirement (AD-MODEL-BINDING-001)."""
    from app.registry.workflow import Workflow, OutputSpec, WorkflowStatus, ModelRequirement
    from app.registry.model import ModelKind
    from app.agent import Agent
    from app.assets.store import AssetStore
    import json, pathlib

    tmp = pathlib.Path(__file__).parent / "__tmptest_m_compat__"
    tmp.mkdir(parents=True, exist_ok=True)

    # Workflow требует модель "checkpoint" (legacy формат)
    manifest = {
        "id": "needs_model", "version": "1.0.0", "capability": "image.generate",
        "provider": "comfyui", "backend": "local_comfyui",
        "inputs": {}, "asset_inputs": {},
        "outputs": {"result": {"node": "9", "kind": "image"}},
        "parameters": {}, "required_models": ["checkpoint"],
        "required_custom_nodes": [], "min_comfyui_version": "0.0.0",
        "requirements": {"accelerator": "any"},
    }
    wf_json = {"9": {"class_type": "SaveImage", "inputs": {"images": ["6", 0]}}}
    d = tmp / "needs_model"
    d.mkdir(parents=True, exist_ok=True)
    (d / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (d / "workflow.json").write_text(json.dumps(wf_json), encoding="utf-8")

    agent = Agent(AssetStore(root=str(tmp / "store")), workflows_dir=str(tmp))
    wf = agent.registry.get("needs_model", "1.0.0")

    # Проверяем что legacy мигрирован в kind requirement
    assert wf.model_requirements == [ModelRequirement.by_kind(ModelKind.CHECKPOINT)]
    assert wf.contract_version == 1

    # С cache: модели = {"cyberrealistic_v80.safetensors", ...}
    # Kind requirement satisfied because models exist
    facts = agent._discover_facts(
        _SpyClient(raise_on={"system_stats", "object_info", "checkpoints"}), "local_comfyui"
    )
    st, reasons = agent._compatibility_from_known(
        wf,
        facts.runtime, facts.models, facts.custom_nodes,
    )
    # Now AVAILABLE because "checkpoint" is interpreted as kind, not exact identity
    assert st == WorkflowStatus.AVAILABLE
    assert reasons == []


def test_step7_exact_model_identity():
    """G. Точное совпадение имён моделей — без guessing."""
    from app.registry.discovery import checkpoints_from_node_schema_store
    cp = checkpoints_from_node_schema_store()
    # Реальные имена из кэша
    assert "cyberrealistic_v80.safetensors" in cp
    assert "majicmixRealistic_v7.safetensors" in cp
    # Выдуманные имена — не должны появляться
    assert "random_model.safetensors" not in cp
    assert "checkpoint" not in cp  # placeholder не равен реальному имени


def test_step7_merge_models_and_custom_nodes():
    """H. Merge корректно работает с обоими inventory одновременно."""
    from app.registry.discovery import DiscoveryFacts
    f1 = DiscoveryFacts(
        models={"live_ckpt.safetensors"}, models_available=True,
        custom_nodes={"pkg": {"Node"}}, custom_nodes_available=True,
    )
    f2 = DiscoveryFacts(
        runtime="rt", models_available=True, custom_nodes_available=True,
    )
    m = f1.merge(f2)
    assert m.models == {"live_ckpt.safetensors"}
    assert m.custom_nodes == {"pkg": {"Node"}}
    assert m.models_available is True
    assert m.custom_nodes_available is True
    assert m.runtime is not None
