"""AD-48: wiring KnowledgeCore + RuntimeValidator в production-агент (build_server)
и read-only эндпоинтов /api/nodes, /api/knowledge, /api/self-test.

Решение A (post-AD-48 reproducibility fix): тест полностью самодостаточен.
  - Синтетический набор NodeSchema создаётся штатным NodeSchemaStore.save_snapshot()
    во временный каталог; KnowledgeCore строится оттуда (data_dir=tmp).
  - Не зависит от runtime snapshot app/data/knowledge (в git отсутствует) и от
    числа реальных нод (>100 убрано в пользу контрактных проверок синтетики).
  - Production wiring сохранён: build_server(knowledge_data_dir=tmp) проходит через
    настоящий composition root; production/runtime path с data_dir=None
    проверяется отдельно (НЕ получает синтетику).

Mock НЕ используется для execution chain (TEST_PROTOCOL), но живой ComfyUI здесь
НЕ трогается: все кейсы детерминированные и офлайн (snapshot-данные + refusal-пути
консервативного gate, AD-47). Истина — PROJECT_SPEC §21 + AGENT_UI_ARCHITECTURE.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.assets.store import AssetStore
from app.conversation import ConversationAgent
from app.knowledge.core import KnowledgeCore
from app.knowledge.node_schema import FieldSpec, NodeSchema, NodeSchemaStore
from app.ui import ComfyUIServer, _build_knowledge_core, _make_handler, build_server


# ---------------------------------------------------------------------------
# Синтетический seed (Solution A): минимальный, самодостаточный набор схем.
# Состав выбран так, чтобы покрыть контракты API:
#   - SaveImage — find_node / explain_node / search 'save' / nodes_by_io(IMAGE);
#   - LoadImage — IMAGE+MASK источник;
#   - KSampler — fragment без candidates;
#   - SyntheticText2ImageNode — prompt+IMAGE → image.generate candidate;
#   - SyntheticEchoNode — text+STRING → text.generate candidate, custom-пакет.
# Имена Synthetic* выбраны так, чтобы НЕ пересекаться с runtime snapshot
# (проверка default path в test_default_data_dir_expects_runtime_not_synthetic).
# ---------------------------------------------------------------------------
def _seeded_schemas() -> dict[str, NodeSchema]:
    def fs(name: str, ftype: str, required: bool = True, options=()):
        return FieldSpec(name=name, type=ftype, required=required, options=tuple(options))

    t = 1700000000.0
    return {
        "SaveImage": NodeSchema(
            class_type="SaveImage",
            display_name="Save Image",
            category="image",
            input_required=(fs("images", "IMAGE"),),
            input_optional=(),
            output_types=("IMAGE",),
            output_names=("images",),
            python_module="nodes",
            discovered_at=t,
        ),
        "LoadImage": NodeSchema(
            class_type="LoadImage",
            display_name="Load Image",
            category="image",
            input_required=(),
            input_optional=(fs("image", "STRING", required=False),),
            output_types=("IMAGE", "MASK"),
            output_names=("IMAGE", "MASK"),
            python_module="nodes",
            discovered_at=t,
        ),
        "KSampler": NodeSchema(
            class_type="KSampler",
            display_name="KSampler",
            category="sampling",
            input_required=(
                fs("model", "MODEL"),
                fs("positive", "CONDITIONING"),
                fs("negative", "CONDITIONING"),
                fs("latent_image", "LATENT"),
            ),
            input_optional=(),
            output_types=("LATENT",),
            output_names=("LATENT",),
            python_module="nodes",
            discovered_at=t,
        ),
        "SyntheticText2ImageNode": NodeSchema(
            class_type="SyntheticText2ImageNode",
            display_name="Synthetic Text2Image",
            category="synthetic",
            input_required=(fs("prompt", "STRING"),),
            input_optional=(),
            output_types=("IMAGE",),
            output_names=("image",),
            python_module="custom_nodes.SDGUI_synthetic",
            discovered_at=t,
        ),
        "SyntheticEchoNode": NodeSchema(
            class_type="SyntheticEchoNode",
            display_name="Synthetic Echo",
            category="synthetic",
            input_required=(fs("text", "STRING"),),
            input_optional=(),
            output_types=("STRING",),
            output_names=("text",),
            python_module="custom_nodes.SDGUI_synthetic",
            discovered_at=t,
        ),
    }


def _seed_core(tmp_path) -> tuple[KnowledgeCore, dict[str, NodeSchema]]:
    """Seeds синтетический snapshot во временный каталог и строит KnowledgeCore.

    Возвращает (core, seeded_schemas) — полностью детерминированный набор.
    """
    schemas = _seeded_schemas()
    NodeSchemaStore(data_dir=str(tmp_path)).save_snapshot(schemas)
    core = KnowledgeCore(data_dir=str(tmp_path))
    return core, schemas


# ---------------------------------------------------------------------------
# Helpers (аналог test_ui_section21.py)
# ---------------------------------------------------------------------------
def _make_server(store: AssetStore, agent_knowledge_core=None, factory_knowledge_core=None):
    """Сервер с детерминированным wiring: knowledge_core передаётся и в агента,
    и в ComfyUIServer (AD-48: factory.knowledge_core или fallback на agent)."""
    agent = ConversationAgent(store, knowledge_core=agent_knowledge_core)
    core = factory_knowledge_core if factory_knowledge_core is not None else agent_knowledge_core
    factory = ComfyUIServer(store, agent=agent, knowledge_core=core)
    handler = _make_handler(factory)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd, factory


def _get(url: str, timeout: float = 20.0):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}
    except Exception:
        return 0, {}


def _post(url: str, obj, timeout: float = 20.0):
    body = obj if isinstance(obj, (bytes,)) else json.dumps(obj).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}


# ============================================================================
# 1. Wiring: build_server (production composition root, AD-48)
# ============================================================================
def test_build_server_wires_knowledge_core(tmp_path):
    schemas = _seed_core(tmp_path)[1]
    store = AssetStore(root=str(tmp_path / "assets"))
    httpd, factory = build_server(store=store, port=0, knowledge_data_dir=str(tmp_path))
    try:
        core = factory.knowledge_core
        assert core is not None, "knowledge_core не построен (fail-open, AD-45)"
        assert factory.agent.knowledge_core is core, "agent и factory используют разные core"
        validator = getattr(core, "_runtime_validator", None)
        assert validator is not None, "RuntimeValidator не подключён к KnowledgeCore"
        assert validator.comfy_client is not None, "валидатор без transport (ComfyClient)"
        got = set(core.get_schemas())
        assert set(schemas).issubset(got), "wiring-ядро не содержит синтетический seed"
    finally:
        httpd.server_close()


def test_build_knowledge_core_receives_backend_transport(tmp_path):
    from app.registry.backends import BackendCatalog, BackendSpec

    _seed_core(tmp_path)
    catalog = BackendCatalog([BackendSpec(
        backend_id="local_comfyui",
        base_url="http://127.0.0.1:8188",
        kind="local_comfyui",
        priority=0,
    )])
    core = _build_knowledge_core(backends=catalog, data_dir=str(tmp_path))
    assert core is not None
    validator = core._runtime_validator
    assert validator is not None
    assert validator.comfy_client is not None
    assert validator.comfy_client.base_url == "http://127.0.0.1:8188"


def test_default_data_dir_expects_runtime_not_synthetic(tmp_path):
    """Runtime path (data_dir=None) читает реальный snapshot и НЕ получает
    синтетические данные автоматически (production behaviour, AD-48)."""
    from app.registry.backends import BackendCatalog, BackendSpec

    schemas = _seed_core(tmp_path)[1]
    synthetic_only = {k for k in schemas if k.startswith("Synthetic")}
    assert synthetic_only, "синтетический seed должен содержать Synthetic*-class_types"

    catalog = BackendCatalog([BackendSpec(
        backend_id="local_comfyui",
        base_url="http://127.0.0.1:8188",
        kind="local_comfyui",
        priority=0,
    )])
    core = _build_knowledge_core(backends=catalog)  # data_dir=None → runtime snapshot
    assert core is not None
    got = set(core.get_schemas())
    assert not synthetic_only.intersection(got), (
        "default path (data_dir=None) получил синтетические данные — "
        "production НЕ должен читать тестовый seed"
    )


# ============================================================================
# 2. GET /api/nodes (read-only, S3)
# ============================================================================
def test_api_nodes_stats(tmp_path):
    core, schemas = _seed_core(tmp_path)
    store = AssetStore(root=str(tmp_path / "assets"))
    httpd, factory = _make_server(store, agent_knowledge_core=core)
    try:
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        code, data = _get(f"{base}/api/nodes")
        assert code == 200, f"expected 200, got {code}: {data}"
        assert data.get("configured") is True
        assert data["stats"]["schemas"] == len(schemas)
        assert isinstance(data["stats"]["candidates"], int)
        assert isinstance(data["stats"]["validated_nodes"], int)
    finally:
        httpd.shutdown()


def test_api_nodes_by_class_type(tmp_path):
    core, _ = _seed_core(tmp_path)
    store = AssetStore(root=str(tmp_path / "assets"))
    httpd, factory = _make_server(store, agent_knowledge_core=core)
    try:
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        code, data = _get(f"{base}/api/nodes?node=SaveImage")
        assert code == 200, f"expected 200, got {code}: {data}"
        assert data["node"]["class_type"] == "SaveImage"
        assert isinstance(data["node"]["outputs"], list)
    finally:
        httpd.shutdown()


def test_api_nodes_unknown_class_type_404(tmp_path):
    core, _ = _seed_core(tmp_path)
    store = AssetStore(root=str(tmp_path / "assets"))
    httpd, factory = _make_server(store, agent_knowledge_core=core)
    try:
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        code, data = _get(f"{base}/api/nodes?node=No.Such.Node")
        assert code == 404, f"expected 404, got {code}: {data}"
        assert "not found" in data.get("error", "").lower()
    finally:
        httpd.shutdown()


def test_api_nodes_search_q(tmp_path):
    core, _ = _seed_core(tmp_path)
    store = AssetStore(root=str(tmp_path / "assets"))
    httpd, factory = _make_server(store, agent_knowledge_core=core)
    try:
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        code, data = _get(f"{base}/api/nodes?q=save")
        assert code == 200, f"expected 200, got {code}: {data}"
        assert data["count"] > 0, "поиск 'save' не нашёл нод"
        for node in data["nodes"]:
            assert node["class_type"]
            assert "display_name" in node
            assert "category" in node
            assert isinstance(node["output_types"], list)
    finally:
        httpd.shutdown()


def test_api_nodes_by_output(tmp_path):
    core, _ = _seed_core(tmp_path)
    store = AssetStore(root=str(tmp_path / "assets"))
    httpd, factory = _make_server(store, agent_knowledge_core=core)
    try:
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        code, data = _get(f"{base}/api/nodes?output=IMAGE")
        assert code == 200, f"expected 200, got {code}: {data}"
        assert data["count"] > 0, "nodes_by_io(IMAGE) пуст (синтетика должна содержать IMAGE-ноды)"
        for node in data["nodes"]:
            assert "IMAGE" in node["output_types"], f"{node['class_type']} без IMAGE-выхода"
    finally:
        httpd.shutdown()


def test_api_nodes_package_404(tmp_path):
    core, _ = _seed_core(tmp_path)
    store = AssetStore(root=str(tmp_path / "assets"))
    httpd, factory = _make_server(store, agent_knowledge_core=core)
    try:
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        code, data = _get(f"{base}/api/nodes?package=No.Such.Package")
        assert code == 404, f"expected 404, got {code}: {data}"
        assert "not found" in data.get("error", "").lower()
    finally:
        httpd.shutdown()


def test_api_nodes_not_configured_503(tmp_path):
    store = AssetStore(root=str(tmp_path / "assets"))
    httpd, factory = _make_server(store)  # knowledge_core=None (fail-open, AD-45)
    try:
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        code, data = _get(f"{base}/api/nodes")
        assert code == 503, f"expected 503, got {code}: {data}"
        assert "knowledge not configured" in data.get("error", "")
    finally:
        httpd.shutdown()


# ============================================================================
# 3. GET /api/knowledge (read-only, S3: explain_node / gap_report)
# ============================================================================
def test_api_knowledge_explain_node(tmp_path):
    core, _ = _seed_core(tmp_path)
    store = AssetStore(root=str(tmp_path / "assets"))
    httpd, factory = _make_server(store, agent_knowledge_core=core)
    try:
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        code, data = _get(f"{base}/api/knowledge?node=SaveImage")
        assert code == 200, f"expected 200, got {code}: {data}"
        assert data["node"]["facts"]["class_type"] == "SaveImage"
    finally:
        httpd.shutdown()


def test_api_knowledge_gap_report(tmp_path):
    core, _ = _seed_core(tmp_path)
    store = AssetStore(root=str(tmp_path / "assets"))
    httpd, factory = _make_server(store, agent_knowledge_core=core)
    try:
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        code, data = _get(f"{base}/api/knowledge?gap=1")
        assert code == 200, f"expected 200, got {code}: {data}"
        assert "gaps" in data and isinstance(data["count"], int)
    finally:
        httpd.shutdown()


def test_api_knowledge_stats(tmp_path):
    core, schemas = _seed_core(tmp_path)
    store = AssetStore(root=str(tmp_path / "assets"))
    httpd, factory = _make_server(store, agent_knowledge_core=core)
    try:
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        code, data = _get(f"{base}/api/knowledge")
        assert code == 200, f"expected 200, got {code}: {data}"
        assert data["stats"]["schemas"] == len(schemas)
        assert "claims" in data["stats"]
    finally:
        httpd.shutdown()


# ============================================================================
# 4. POST /api/self-test (S6, консервативный gate — только отказы, без живого ComfyUI)
# ============================================================================
def test_api_self_test_requires_node_class(tmp_path):
    store = AssetStore(root=str(tmp_path / "assets"))
    httpd, factory = _make_server(store)
    try:
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        code, data = _post(f"{base}/api/self-test", {})
        assert code == 400, f"expected 400, got {code}: {data}"
        assert "node_class required" in data.get("error", "")
        code2, data2 = _post(f"{base}/api/self-test", "not-json")
        assert code2 == 400, f"expected 400 for bad json, got {code2}: {data2}"
    finally:
        httpd.shutdown()


def test_api_self_test_refused_needs_knowledge(tmp_path):
    store = AssetStore(root=str(tmp_path / "assets"))
    httpd, factory = _make_server(store)  # без knowledge_core
    try:
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        code, data = _post(f"{base}/api/self-test", {"node_class": "SaveImage"})
        assert code == 200, f"отказ возвращается с 200, got {code}: {data}"
        assert data.get("status") == "refused"
        assert "needs_knowledge" in data.get("refusal_reasons", [])
    finally:
        httpd.shutdown()


def test_api_self_test_refused_unknown_node(tmp_path):
    core, _ = _seed_core(tmp_path)
    store = AssetStore(root=str(tmp_path / "assets"))
    httpd, factory = _make_server(store, agent_knowledge_core=core)
    try:
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        code, data = _post(f"{base}/api/self-test", {"node_class": "No.Such.Node"})
        assert code == 200, f"отказ возвращается с 200, got {code}: {data}"
        assert data.get("status") == "refused"
        assert "unknown_node" in data.get("refusal_reasons", [])
    finally:
        httpd.shutdown()


# ============================================================================
# 5. Запуск (pytest: python -m pytest tests/test_knowledge_wiring_ui.py;
#             standalone: python tests/test_knowledge_wiring_ui.py)
# ============================================================================
if __name__ == "__main__":
    import tempfile

    tests = [
        test_build_server_wires_knowledge_core,
        test_build_knowledge_core_receives_backend_transport,
        test_default_data_dir_expects_runtime_not_synthetic,
        test_api_nodes_stats,
        test_api_nodes_by_class_type,
        test_api_nodes_unknown_class_type_404,
        test_api_nodes_search_q,
        test_api_nodes_by_output,
        test_api_nodes_package_404,
        test_api_nodes_not_configured_503,
        test_api_knowledge_explain_node,
        test_api_knowledge_gap_report,
        test_api_knowledge_stats,
        test_api_self_test_requires_node_class,
        test_api_self_test_refused_needs_knowledge,
        test_api_self_test_refused_unknown_node,
    ]
    passed = 0
    failed = 0
    for test in tests:
        with tempfile.TemporaryDirectory() as tmp:
            try:
                test(pathlib.Path(tmp))
                passed += 1
                print(f"PASS {test.__name__}")
            except Exception as e:
                failed += 1
                print(f"FAIL: {test.__name__}: {e}")
    print(f"\nKnowledge Wiring UI Tests: {passed} passed, {failed} failed")
    if failed:
        sys.exit(1)
    print("ALL KNOWLEDGE WIRING UI TESTS PASSED")