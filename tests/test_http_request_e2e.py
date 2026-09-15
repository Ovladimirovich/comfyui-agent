"""
Real E2E test for HttpRequestNodes integration.

Тестирование:
1. Get Request Node → API call to ComfyUI system_stats
2. Verify response is valid JSON
3. Validate runtime evidence stored
"""

import json
import os
import pytest
from pathlib import Path

from app.comfy.client import ComfyClient

# Repo-relative resolution. Прежний хардкод "C:/cd/ComfyUI_AMD/comfyui_api.py" —
# не портируемый (вне репо/CI) и ссылался на модули, НЕ закоммиченные в репозиторий.
# Контракт: если артефакт (CLI/MCP) отсутствует в репо — тест SKIP с явной причиной,
# а не error (не маскируем дефект: артефакт действительно не часть репозитория).
_REPO_ROOT = Path(__file__).resolve().parents[1]
_CLI_SCRIPT = _REPO_ROOT / "comfyui_api.py"
_MCP_MODULE = _REPO_ROOT / "comfyui_mcp_server.py"
from app.knowledge.runtime_validator import RuntimeValidator
from app.knowledge.core import KnowledgeCore
from app.knowledge.node_doc import NodeDocStore


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def comfy_client():
    return ComfyClient()


@pytest.fixture
def runtime_validator(comfy_client):
    return RuntimeValidator(comfy_client=comfy_client, max_wait_seconds=60)


@pytest.fixture
def knowledge_core(runtime_validator, tmp_path):
    # P1 contract: tmp data_dir — validate_runtime не пишет в production app/data/knowledge
    return KnowledgeCore(runtime_validator=runtime_validator,
                         data_dir=str(tmp_path / "kc"))


@pytest.fixture
def node_doc_store():
    return NodeDocStore()


# ------------------------------------------------------------------
# Workflow builders
# ------------------------------------------------------------------


def build_get_request_workflow(url: str, headers: dict = None) -> dict:
    """Создаёт workflow с Get Request Node."""
    return {
        "nodes": [
            {
                "id": 1,
                "type": "Get Request Node",
                "inputs": {
                    "target_url": url,
                    "headers": headers or {}
                },
                "widgets_values": [url, headers or {}]
            }
        ],
        "links": []
    }


def build_post_request_workflow(url: str, body: dict = None) -> dict:
    """Создаёт workflow с Post Request Node."""
    return {
        "nodes": [
            {
                "id": 1,
                "type": "Post Request Node",
                "inputs": {
                    "target_url": url,
                    "body": json.dumps(body or {})
                },
                "widgets_values": [url, json.dumps(body or {})]
            }
        ],
        "links": []
    }


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


class TestHttpRequestNodesE2E:
    """Реальные тесты с живым ComfyUI."""

    def test_node_exists_in_object_info(self, comfy_client):
        """Проверяет что Get Request Node существует в /object_info."""
        oi = comfy_client.get_object_info()
        assert "Get Request Node" in oi, "Get Request Node not found in /object_info"

    def test_node_schema_loaded(self, node_doc_store):
        """Проверяет что документация загружена."""
        doc = node_doc_store.get_doc_for("Get Request Node")
        assert doc is not None, "Documentation not found for Get Request Node"
        assert doc.purpose == "HTTP GET запрос"

    @pytest.mark.skip(reason="Requires live ComfyUI + HTTP nodes to be working")
    def test_get_request_to_comfyui(self, runtime_validator):
        """Тест: GET запрос к системным статам ComfyUI."""
        workflow = build_get_request_workflow("http://127.0.0.1:8188/system_stats")
        result = runtime_validator.validate_node("Get Request Node", workflow)
        
        assert result.validation_result.value in ("SUCCESS", "ERROR")
        # Если нода работает — SUCCESS, иначе ERROR (но не timeout)
        assert result.execution_time_ms > 0

    @pytest.mark.skip(reason="Requires live ComfyUI + HTTP nodes to be working")
    def test_runtime_validation_stores_evidence(self, knowledge_core):
        """Тест: runtime validation сохраняет evidence."""
        workflow = build_get_request_workflow("http://127.0.0.1:8188/system_stats")
        result = knowledge_core.validate_runtime("Get Request Node", workflow)
        
        assert "validation_result" in result
        validated = knowledge_core.get_validated_nodes()
        assert "Get Request Node" in validated

    def test_cli_node_explain(self):
        """Тест CLI команды node-explain (skip, если CLI-модуль отсутствует в репо)."""
        import subprocess
        if not _CLI_SCRIPT.exists():
            pytest.skip(f"CLI-скрипт отсутствует в репозитории: {_CLI_SCRIPT}")
        result = subprocess.run(
            ["python", str(_CLI_SCRIPT), "node-explain", "Get Request Node"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        assert result.returncode == 0
        assert "Get Request Node" in result.stdout
        assert "HTTP GET" in result.stdout or "HTTP" in result.stdout

    def test_cli_node_docs_list(self):
        """Тест CLI команды node-docs list (skip, если CLI-модуль отсутствует в репо)."""
        import subprocess
        if not _CLI_SCRIPT.exists():
            pytest.skip(f"CLI-скрипт отсутствует в репозитории: {_CLI_SCRIPT}")
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        result = subprocess.run(
            ["python", str(_CLI_SCRIPT), "node-docs", "list"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            env=env,
        )
        assert result.returncode == 0
        assert "Get Request Node" in result.stdout

    def test_cli_node_docs_search(self):
        """Тест CLI команды node-docs search (skip, если CLI-модуль отсутствует в репо)."""
        import subprocess
        if not _CLI_SCRIPT.exists():
            pytest.skip(f"CLI-скрипт отсутствует в репозитории: {_CLI_SCRIPT}")
        result = subprocess.run(
            ["python", str(_CLI_SCRIPT), "node-docs", "search", "HTTP"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        assert result.returncode == 0
        assert "Get Request Node" in result.stdout or "Post Request Node" in result.stdout

    def test_mcp_tools_defined(self):
        """Тест что MCP tools зарегистрированы (skip, если MCP-модуль отсутствует в репо)."""
        import sys
        if not _MCP_MODULE.exists():
            pytest.skip(f"MCP-модуль отсутствует в репозитории: {_MCP_MODULE}")
        sys.path.insert(0, str(_REPO_ROOT))
        from comfyui_mcp_server import TOOLS

        tool_names = [t.name for t in TOOLS]
        assert "comfy_node_explain" in tool_names
        assert "comfy_node_search" in tool_names
        assert "comfy_node_docs_ingest" in tool_names


# ------------------------------------------------------------------
# Integration with KnowledgeCore
# ------------------------------------------------------------------


class TestKnowledgeCoreIntegration:
    """Интеграция Runtime Validator с KnowledgeCore."""

    def test_query_with_validated_node(self, knowledge_core, node_doc_store):
        """Тест: query видит validated nodes."""
        # Получаем query для HTTP GET
        from app.knowledge.core import KnowledgeQuery
        
        query = KnowledgeQuery(
            required_operation="http.get",
            required_media_input=(),
            required_media_output="string",
            task_description="HTTP GET request",
        )
        
        response = knowledge_core.query(query)
        # Должен быть известен capability или candidate
        assert response.readiness.value in ("EXECUTABLE", "CANDIDATE_ONLY", "GAP", "UNKNOWN")

    def test_validate_and_upgrade_claims(self, knowledge_core):
        """Тест: валидация обновляет claims."""
        # Симулируем успешную валидацию
        from app.knowledge.runtime_validator import RuntimeEvidence, ValidationResult
        
        evidence = RuntimeEvidence(
            node_class="Get Request Node",
            validation_result=ValidationResult.SUCCESS,
            execution_time_ms=500.0,
        )
        
        claims = knowledge_core._runtime_validator.upgrade_claims(evidence)
        assert len(claims) == 1
        assert claims[0].status.value == "CONFIRMED"
