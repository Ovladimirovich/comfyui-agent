"""M12.1 — Tests for ComfyCLI Optional Infrastructure Adapter (Agent).

Тестирует:
- CLI отсутствие → graceful unavailable
- CLI найден → version
- command failure → structured error
- timeout → structured error
- validate workflow
- system info
- JSON parsing
- adapter не имеет доступа к execution core
- отсутствие CLI не влияет на существующие тесты
- shell=True не используется (AD-33)

Source of Truth: docs/PROJECT_SPEC.md, agent architecture.
"""
from __future__ import annotations

import os
import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest

# Добавляем корень проекта в path для импорта
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.infrastructure.comfy_cli_adapter import (
    ComfyCLIAdapter,
    ComfyCLIResult,
    _parse_json_output,
    _resolve_comfy_path,
    _run_comfy_command,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def adapter() -> ComfyCLIAdapter:
    """Создать adapter с автоопределением comfy-cli."""
    return ComfyCLIAdapter()


@pytest.fixture
def adapter_with_path() -> ComfyCLIAdapter:
    """Создать adapter с явным путём к comfy-cli."""
    path = _resolve_comfy_path()
    if path is None:
        pytest.skip("comfy-cli not found")
    return ComfyCLIAdapter(comfy_path=path)


@pytest.fixture
def unavailable_adapter() -> ComfyCLIAdapter:
    """Создать adapter с несуществующим путём."""
    return ComfyCLIAdapter(comfy_path="/nonexistent/comfy")


# ============================================================================
# Test: CLI отсутствие → graceful unavailable
# ============================================================================


class TestUnavailable:
    """Тест graceful degradation при отсутствии comfy-cli (R9, AD-34)."""

    def test_is_available_returns_false(self, unavailable_adapter: ComfyCLIAdapter) -> None:
        assert unavailable_adapter.is_available() is False

    def test_version_returns_none(self, unavailable_adapter: ComfyCLIAdapter) -> None:
        assert unavailable_adapter.version() is None

    def test_stop_port_returns_error(self, unavailable_adapter: ComfyCLIAdapter) -> None:
        result = unavailable_adapter.stop_port(8188)
        assert result.ok is False
        assert "not available" in result.error

    def test_validate_workflow_returns_error(self, unavailable_adapter: ComfyCLIAdapter) -> None:
        result = unavailable_adapter.validate_workflow("/nonexistent/workflow.json")
        assert result.ok is False
        assert "not available" in result.error

    def test_system_info_returns_error(self, unavailable_adapter: ComfyCLIAdapter) -> None:
        result = unavailable_adapter.system_info()
        assert result.ok is False
        assert "not available" in result.error

    def test_env_info_returns_error(self, unavailable_adapter: ComfyCLIAdapter) -> None:
        result = unavailable_adapter.env_info()
        assert result.ok is False
        assert "not available" in result.error

    def test_model_list_returns_error(self, unavailable_adapter: ComfyCLIAdapter) -> None:
        result = unavailable_adapter.model_list()
        assert result.ok is False
        assert "not available" in result.error

    def test_free_memory_returns_error(self, unavailable_adapter: ComfyCLIAdapter) -> None:
        result = unavailable_adapter.free_memory()
        assert result.ok is False
        assert "not available" in result.error


# ============================================================================
# Test: CLI найден → version
# ============================================================================


class TestAvailable:
    """Тест работы при наличии comfy-cli."""

    def test_is_available_returns_true(self, adapter_with_path: ComfyCLIAdapter) -> None:
        assert adapter_with_path.is_available() is True

    def test_version_returns_string(self, adapter_with_path: ComfyCLIAdapter) -> None:
        version = adapter_with_path.version()
        assert version is not None
        assert isinstance(version, str)
        parts = version.split(".")
        assert len(parts) >= 2


# ============================================================================
# Test: command failure → structured error
# ============================================================================


class TestCommandFailure:
    """Тест обработки ошибок команд."""

    def test_validate_nonexistent_workflow(self, adapter_with_path: ComfyCLIAdapter) -> None:
        result = adapter_with_path.validate_workflow("/nonexistent/workflow.json")
        assert result.ok is False
        assert result.error is not None

    def test_stop_port_on_nonexistent_port(self, adapter_with_path: ComfyCLIAdapter) -> None:
        result = adapter_with_path.stop_port(1)
        assert isinstance(result, ComfyCLIResult)


# ============================================================================
# Test: timeout → structured error (R8)
# ============================================================================


class TestTimeout:
    """Тест обработки timeout."""

    def test_timeout_returns_error(self) -> None:
        path = _resolve_comfy_path()
        if path is None:
            pytest.skip("comfy-cli not found")

        result = _run_comfy_command(path, ["env", "--json"], timeout=0.001)
        assert result.ok is False
        assert "timed out" in result.error


# ============================================================================
# Test: validate workflow (R10)
# ============================================================================


class TestValidateWorkflow:
    """Тест валидации workflow (R10: не обязательный execution gate)."""

    def test_validate_file_not_found(self, adapter_with_path: ComfyCLIAdapter) -> None:
        result = adapter_with_path.validate_workflow("/nonexistent/workflow.json")
        assert result.ok is False
        assert "not found" in result.error.lower()

    def test_validate_returns_result(self, adapter_with_path: ComfyCLIAdapter) -> None:
        workflow_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "workflows",
            "txt2img",
            "workflow.json",
        )

        if not os.path.isfile(workflow_path):
            pytest.skip("Test workflow not found")

        result = adapter_with_path.validate_workflow(workflow_path)
        assert isinstance(result, ComfyCLIResult)


# ============================================================================
# Test: system info
# ============================================================================


class TestSystemInfo:
    """Тест получения system info."""

    def test_system_info_returns_data(self, adapter_with_path: ComfyCLIAdapter) -> None:
        result = adapter_with_path.system_info()
        assert result.ok is True
        assert result.data is not None


# ============================================================================
# Test: env info
# ============================================================================


class TestEnvInfo:
    """Тест получения env info."""

    def test_env_info_returns_data(self, adapter_with_path: ComfyCLIAdapter) -> None:
        result = adapter_with_path.env_info()
        assert result.ok is True
        assert result.data is not None


# ============================================================================
# Test: model list
# ============================================================================


class TestModelList:
    """Тест получения списка моделей."""

    def test_model_list_returns_data(self, adapter_with_path: ComfyCLIAdapter) -> None:
        result = adapter_with_path.model_list()
        assert result.ok is True
        assert result.data is not None


# ============================================================================
# Test: free memory
# ============================================================================


class TestFreeMemory:
    """Тест выгрузки моделей."""

    def test_free_memory_returns_result(self, adapter_with_path: ComfyCLIAdapter) -> None:
        result = adapter_with_path.free_memory()
        assert isinstance(result, ComfyCLIResult)


# ============================================================================
# Test: JSON parsing
# ============================================================================


class TestJsonParsing:
    """Тест парсинга JSON output."""

    def test_parse_valid_envelope(self) -> None:
        json_str = '{"schema": "envelope/1", "ok": true, "data": {"version": "1.19.0"}}'
        result = _parse_json_output(json_str)
        assert result is not None
        assert result["ok"] is True
        assert result["data"]["version"] == "1.19.0"

    def test_parse_invalid_json(self) -> None:
        result = _parse_json_output("not json at all")
        assert result is None

    def test_parse_empty_string(self) -> None:
        result = _parse_json_output("")
        assert result is None

    def test_parse_none(self) -> None:
        result = _parse_json_output(None)
        assert result is None

    def test_parse_multiple_lines(self) -> None:
        json_str = 'warning line\n{"schema": "envelope/1", "ok": true, "data": {}}'
        result = _parse_json_output(json_str)
        assert result is not None
        assert result["ok"] is True

    def test_parse_non_envelope_json(self) -> None:
        json_str = '{"key": "value"}'
        result = _parse_json_output(json_str)
        assert result is not None
        assert result["key"] == "value"


# ============================================================================
# Test: adapter не имеет доступа к execution core (R1, R11)
# ============================================================================


class TestNoExecutionAccess:
    """Тест что adapter не имеет доступа к execution core (R1, R11)."""

    def test_adapter_does_not_import_comfy_client(self) -> None:
        """Adapter не импортирует ComfyClient (только строка 'from app...' в коде)."""
        import ast
        import app.infrastructure.comfy_cli_adapter as adapter_module

        with open(adapter_module.__file__, encoding="utf-8") as f:
            tree = ast.parse(f.read())

        imports = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom) and node.module:
                    imports.append(node.module)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)

        bad_prefixes = ("app.client", "app.engine", "app.provider", "app.comfy.client")
        for imp in imports:
            for prefix in bad_prefixes:
                assert not imp.startswith(prefix), f"Adapter imports from execution core: {imp}"

    def test_adapter_result_is_named_tuple(self) -> None:
        """ComfyCLIResult — это NamedTuple с правильными полями."""
        result = ComfyCLIResult(ok=True, data={"key": "value"}, error=None)
        assert result.ok is True
        assert result.data == {"key": "value"}
        assert result.error is None

    def test_adapter_error_result(self) -> None:
        """ComfyCLIResult с ошибкой."""
        result = ComfyCLIResult(ok=False, data=None, error="test error")
        assert result.ok is False
        assert result.data is None
        assert result.error == "test error"


# ============================================================================
# Test: отсутствие CLI не влияет на существующие тесты (AD-34, R9)
# ============================================================================


class TestCliAbsentDoesNotAffectExisting:
    """Тест что отсутствие CLI не влияет на существующие тесты (AD-34)."""

    def test_adapter_can_be_created_without_cli(self) -> None:
        """Adapter может быть создан даже без comfy-cli."""
        adapter = ComfyCLIAdapter(comfy_path="/nonexistent/comfy")
        assert adapter.is_available() is False

    def test_adapter_default_init_does_not_crash(self) -> None:
        """Adapter с автоопределением не падает при отсутствии CLI."""
        adapter = ComfyCLIAdapter()
        assert isinstance(adapter.is_available(), bool)


# ============================================================================
# Test: AD-33 — shell=True не используется
# ============================================================================


class TestNoShellTrue:
    """Тест соблюдения AD-33: shell=True никогда не используется."""

    def test_run_command_uses_shell_false(self) -> None:
        """_run_comfy_command использует shell=False."""
        path = _resolve_comfy_path()
        if path is None:
            pytest.skip("comfy-cli not found")

        with patch("app.infrastructure.comfy_cli_adapter.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout='{"schema": "envelope/1", "ok": true, "data": {"version": "1.0.0"}}',
                stderr="",
                returncode=0,
            )

            _run_comfy_command(path, ["--version", "--json"])

            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args
            assert call_kwargs.kwargs.get("shell") is False or call_kwargs[1].get("shell") is False

    def test_model_list_uses_shell_false(self) -> None:
        """model_list использует shell=False."""
        path = _resolve_comfy_path()
        if path is None:
            pytest.skip("comfy-cli not found")

        with patch("app.infrastructure.comfy_cli_adapter.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="Model list output",
                stderr="",
                returncode=0,
            )

            adapter = ComfyCLIAdapter(comfy_path=path)
            adapter.model_list()

            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args
            assert call_kwargs.kwargs.get("shell") is False or call_kwargs[1].get("shell") is False


# ============================================================================
# Test: _resolve_comfy_path
# ============================================================================


class TestResolveComfyPath:
    """Тест поиска пути к comfy-cli."""

    def test_resolve_returns_path_or_none(self) -> None:
        result = _resolve_comfy_path()
        assert result is None or isinstance(result, str)

    def test_resolve_returns_existing_file(self) -> None:
        result = _resolve_comfy_path()
        if result is not None:
            assert os.path.isfile(result)
