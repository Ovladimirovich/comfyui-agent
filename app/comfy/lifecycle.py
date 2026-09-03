"""M12 — ComfyUI Lifecycle Manager (infrastructure adapter).

Минимальный адаптер для управления жизненным циклом ComfyUI процесса.
Строго infrastructure: НЕ трогает ComfyClient, WorkflowEngine, Provider.

Ответственность:
  - check() — проверка доступности через HTTP health check
  - start() — запуск ComfyUI из известного пути (опционально)
  - stop()  — остановка ComfyUI (опционально)

НЕ ответственность:
  - execution path (ComfyClient + WorkflowEngine)
  - workflow selection
  - prompt enhancement
  - asset management
"""
from __future__ import annotations

import os
import subprocess
import time
from typing import Optional


class ComfyUILifecycleError(RuntimeError):
    """Ошибка управления жизненным циклом ComfyUI."""


class ComfyUIProcessManager:
    """Минимальный менеджер жизненного цикла ComfyUI.

    Используется для:
    - проверки доступности ComfyUI перед началом работы
    - запуска ComfyUI из известного пути (если не запущен)
    - остановки ComfyUI (для тестов/очистки)

    НЕ вмешивается в execution path (ComfyClient + WorkflowEngine).
    """

    def __init__(
        self,
        comfyui_path: Optional[str] = None,
        python_executable: Optional[str] = None,
        port: int = 8188,
        timeout: float = 30.0,
    ) -> None:
        self.comfyui_path = comfyui_path or os.environ.get(
            "COMFYUI_PATH", r"C:\cd\ComfyUI_AMD\ComfyUI"
        )
        self.python_executable = python_executable or os.environ.get(
            "PYTHON_EXECUTABLE", "python"
        )
        self.port = port
        self.timeout = timeout
        self._process: Optional[subprocess.Popen] = None

    def check(self) -> bool:
        """Проверить доступность ComfyUI через HTTP health check.

        Возвращает True если ComfyUI доступен по localhost:port.
        """
        import urllib.request
        import urllib.error

        url = f"http://127.0.0.1:{self.port}/system_stats"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except (urllib.error.URLError, urllib.error.HTTPError, OSError):
            return False

    def wait_for_ready(self, timeout: Optional[float] = None) -> bool:
        """Подождать пока ComfyUI станет доступным.

        Returns:
            True если ComfyUI стал доступен, False по таймауту.
        """
        timeout = timeout or self.timeout
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.check():
                return True
            time.sleep(0.5)
        return False

    def start(self) -> bool:
        """Запустить ComfyUI процесс (если не запущен).

        Возвращает True если процесс успешно запущен и стал доступен.
        """
        if self.check():
            return True  # уже запущен

        if not os.path.isdir(self.comfyui_path):
            raise ComfyUILifecycleError(
                f"ComfyUI path not found: {self.comfyui_path}"
            )

        script = os.path.join(self.comfyui_path, "main.py")
        if not os.path.isfile(script):
            raise ComfyUILifecycleError(
                f"main.py not found in {self.comfyui_path}"
            )

        try:
            self._process = subprocess.Popen(
                [self.python_executable, script, "--port", str(self.port)],
                cwd=self.comfyui_path,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as e:
            raise ComfyUILifecycleError(f"Failed to start ComfyUI: {e}") from e

        return self.wait_for_ready()

    def stop(self) -> bool:
        """Остановить ComfyUI процесс (если управляется этим менеджером).

        Возвращает True если процесс был остановлен.
        """
        if self._process is None:
            return False

        try:
            self._process.terminate()
            self._process.wait(timeout=10)
            return True
        except Exception:
            try:
                self._process.kill()
            except Exception:
                pass
            return False

    @property
    def is_running(self) -> bool:
        """Проверить запущен ли процесс под управлением менеджера."""
        if self._process is None:
            return False
        return self._process.poll() is None
