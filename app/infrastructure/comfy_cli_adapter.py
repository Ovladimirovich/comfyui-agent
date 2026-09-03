"""M12.1 — ComfyCLI Optional Infrastructure Adapter (Agent).

Предоставляет доступ к comfy-cli командам для diagnostics, валидации
и управления процессами. Полностью опциональный — отсутствие comfy-cli
никогда не блокирует основной execution path (AD-34).

Архитектурные инварианты:
  AD-33: Никогда не использует shell=True
  AD-34: Отсутствие comfy-cli не блокирует Agent execution path

R1: ComfyClient + WorkflowEngine — основной execution path (не заменяется).
R2: ComfyCLIAdapter НЕ управляет запуском ComfyUI.
R3: comfy launch НЕ интегрируется в production execution path.
R6: CLI полностью optional.
R7: subprocess только shell=False.
R8: timeout + structured result.
R9: ошибка/отсутствие CLI не ломает Agent.
R10: validate_workflow не является обязательным execution gate.
R11: не изменять ComfyClient, WorkflowEngine, Provider, Asset, Registry.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from typing import Any, NamedTuple, Optional

logger = logging.getLogger(__name__)

# Известные пути к comfy.exe на Windows (если не на PATH)
_KNOWN_WINDOWS_PATHS = [
    os.path.expanduser(r"~\AppData\Roaming\Python\Python314\Scripts\comfy.exe"),
    os.path.expanduser(r"~\AppData\Roaming\Python\Python313\Scripts\comfy.exe"),
    os.path.expanduser(r"~\AppData\Roaming\Python\Python312\Scripts\comfy.exe"),
    os.path.expanduser(r"~\AppData\Roaming\Python\Python311\Scripts\comfy.exe"),
    os.path.expanduser(r"~\AppData\Roaming\Python\Python310\Scripts\comfy.exe"),
]

# Timeout по умолчанию для CLI-команд (секунды)
_DEFAULT_TIMEOUT = 30


class ComfyCLIResult(NamedTuple):
    """Структурированный результат CLI-команды."""

    ok: bool
    data: Optional[dict[str, Any]]
    error: Optional[str]


def _resolve_comfy_path() -> Optional[str]:
    """Найти путь к comfy-cli executable.

    Ищет в следующем порядке:
    1. PATH (shutil.which)
    2. Известные пути на Windows

    Возвращает путь или None если comfy-cli не найден.
    """
    found = shutil.which("comfy") or shutil.which("comfy.exe")
    if found:
        return found

    for path in _KNOWN_WINDOWS_PATHS:
        if os.path.isfile(path):
            return path

    return None


def _parse_json_output(stdout: str) -> Optional[dict[str, Any]]:
    """Парсить JSON output comfy-cli.

    Все команды comfy-cli с --json возвращают envelope:
    {"schema": "envelope/1", "ok": true/false, "data": {...}, "error": {...}}
    """
    if not stdout or not stdout.strip():
        return None

    lines = [line for line in stdout.strip().splitlines() if line.strip()]
    if not lines:
        return None

    for line in reversed(lines):
        try:
            parsed = json.loads(line)
            if isinstance(parsed, dict) and parsed.get("schema") == "envelope/1":
                return parsed
            return parsed
        except (json.JSONDecodeError, ValueError):
            continue

    return None


def _run_comfy_command(
    comfy_path: str,
    args: list[str],
    timeout: int = _DEFAULT_TIMEOUT,
    use_json_flag: bool = True,
) -> ComfyCLIResult:
    """Выполнить comfy-cli команду.

    Использует subprocess.run с shell=False (AD-33, R7).
    Все команды имеют timeout (R8).

    Args:
        comfy_path: путь к comfy.exe
        args: аргументы команды (без comfy.exe)
        timeout: таймаут в секундах
        use_json_flag: добавлять --json как глобальный флаг

    Returns:
        ComfyCLIResult с результатом или ошибкой
    """
    cmd = [comfy_path]
    if use_json_flag:
        cmd.append("--json")
    cmd.extend(args)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,  # AD-33: никогда не shell=True
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )

        stdout = result.stdout or ""
        stderr = result.stderr or ""

        parsed = _parse_json_output(stdout)

        if parsed is not None:
            ok = parsed.get("ok", False)
            data = parsed.get("data")
            error_obj = parsed.get("error")

            if error_obj and isinstance(error_obj, dict):
                error_msg = error_obj.get("message", str(error_obj))
            elif not ok:
                error_msg = f"Command failed: {parsed.get('command', 'unknown')}"
            else:
                error_msg = None

            return ComfyCLIResult(ok=ok, data=data, error=error_msg)

        if result.returncode == 0:
            return ComfyCLIResult(ok=True, data={"raw": stdout}, error=None)
        else:
            error_msg = stderr.strip() if stderr.strip() else f"Exit code: {result.returncode}"
            return ComfyCLIResult(ok=False, data=None, error=error_msg)

    except subprocess.TimeoutExpired:
        return ComfyCLIResult(
            ok=False,
            data=None,
            error=f"Command timed out after {timeout}s: {' '.join(args)}",
        )
    except FileNotFoundError:
        return ComfyCLIResult(
            ok=False,
            data=None,
            error=f"comfy-cli not found at: {comfy_path}",
        )
    except Exception as e:
        return ComfyCLIResult(
            ok=False,
            data=None,
            error=f"Unexpected error: {type(e).__name__}: {e}",
        )


class ComfyCLIAdapter:
    """Опциональный infrastructure adapter для comfy-cli.

    Предоставляет доступ к CLI-командам для diagnostics, валидации
    и управления процессами. Полностью опциональный — отсутствие
    comfy-cli никогда не блокирует основной execution path (AD-34, R9).

    Не заменяет ComfyClient + WorkflowEngine (R1).
    Не управляет запуском ComfyUI (R2, R3).
    """

    def __init__(self, comfy_path: Optional[str] = None) -> None:
        self._comfy_path = comfy_path or _resolve_comfy_path()

    def is_available(self) -> bool:
        """Проверить доступность comfy-cli."""
        return self._comfy_path is not None and os.path.isfile(self._comfy_path)

    def version(self) -> Optional[str]:
        """Получить версию comfy-cli."""
        if not self.is_available():
            return None

        result = _run_comfy_command(self._comfy_path, ["--version"])
        if result.ok and result.data:
            return result.data.get("version")
        return None

    def stop_port(self, port: int) -> ComfyCLIResult:
        """Остановить ComfyUI процесс на указанном порту."""
        if not self.is_available():
            return ComfyCLIResult(ok=False, data=None, error="comfy-cli not available")

        return _run_comfy_command(
            self._comfy_path,
            ["stop", "--port", str(port)],
            timeout=15,
        )

    def validate_workflow(self, path: str) -> ComfyCLIResult:
        """Валидировать workflow без отправки на выполнение (R10)."""
        if not self.is_available():
            return ComfyCLIResult(ok=False, data=None, error="comfy-cli not available")

        if not os.path.isfile(path):
            return ComfyCLIResult(ok=False, data=None, error=f"Workflow file not found: {path}")

        return _run_comfy_command(
            self._comfy_path,
            ["workflow", "validate", "--workflow", path],
            timeout=30,
        )

    def system_info(self) -> ComfyCLIResult:
        """Получить информацию о системе (GPU, RAM, ComfyUI version)."""
        if not self.is_available():
            return ComfyCLIResult(ok=False, data=None, error="comfy-cli not available")

        return _run_comfy_command(
            self._comfy_path,
            ["system-stats"],
            timeout=15,
        )

    def env_info(self) -> ComfyCLIResult:
        """Получить информацию об окружении (Python, workspace, server)."""
        if not self.is_available():
            return ComfyCLIResult(ok=False, data=None, error="comfy-cli not available")

        return _run_comfy_command(
            self._comfy_path,
            ["env"],
            timeout=15,
        )

    def model_list(self) -> ComfyCLIResult:
        """Получить список установленных моделей."""
        if not self.is_available():
            return ComfyCLIResult(ok=False, data=None, error="comfy-cli not available")

        try:
            result = subprocess.run(
                [self._comfy_path, "model", "list"],
                capture_output=True,
                timeout=15,
                shell=False,  # AD-33
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )

            stdout = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
            stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""

            if result.returncode == 0:
                return ComfyCLIResult(ok=True, data={"raw": stdout}, error=None)
            else:
                return ComfyCLIResult(
                    ok=False,
                    data=None,
                    error=stderr.strip() or f"Exit code: {result.returncode}",
                )
        except subprocess.TimeoutExpired:
            return ComfyCLIResult(ok=False, data=None, error="Command timed out after 15s")
        except FileNotFoundError:
            return ComfyCLIResult(ok=False, data=None, error=f"comfy-cli not found at: {self._comfy_path}")
        except Exception as e:
            return ComfyCLIResult(ok=False, data=None, error=f"Unexpected error: {type(e).__name__}: {e}")

    def free_memory(self) -> ComfyCLIResult:
        """Выгрузить модели из VRAM / освободить кэш executor."""
        if not self.is_available():
            return ComfyCLIResult(ok=False, data=None, error="comfy-cli not available")

        return _run_comfy_command(
            self._comfy_path,
            ["free"],
            timeout=15,
        )
