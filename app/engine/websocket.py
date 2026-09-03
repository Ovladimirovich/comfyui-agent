"""ComfyUI WebSocket tracker (M4).

Источник истины: docs/08_EXECUTION_MODEL.md, FR-009 (Job lifecycle + WebSocket).
Обязательный трекинг через WebSocket (queue/executing/progress/executed),
а не только polling /history (треб. 6). Использует библиотеку `websocket-client`.

Сигналы ComfyUI:
  executing(node=None)   — граф завершён
  executed(node, output) — выхлоп узла (images/gifs/…)
  progress(value,max)    — прогресс выполнения узла
  execution_error        — ошибка исполнения
"""
from __future__ import annotations

import json
from typing import Callable, Optional

import websocket

from app.comfy.client import ComfyClientError


class ComfyUIWebSocketError(RuntimeError):
    pass


class ComfyUIWebSocket:
    def __init__(self, base_url: str, client_id: str) -> None:
        # http://host:port → ws://…   ;   https://host:port → wss://…  (AD-29: remote-first)
        scheme = "wss" if base_url.startswith("https") else "ws"
        host = base_url.split("//", 1)[-1].rstrip("/")
        self.ws_url = f"{scheme}://{host}/ws?client_id={client_id}"

    def track(
        self,
        prompt_id: str,
        timeout: int = 300,
        on_progress: Optional[Callable[[float, float], None]] = None,
    ) -> dict:
        """Слушать события prompt_id до завершения.

        Args:
            on_progress: callback(value, max) — вызывается при progress-событии.
                         value/max — абсолютные значения (0..max), percentage = value/max*100.

        Возвращает {node_id: output_dict} для всех executed-узлов.
        """
        ws = None
        try:
            ws = websocket.create_connection(self.ws_url, timeout=timeout, http_proxy_host=None)
            ws.send(json.dumps({"prompt_id": prompt_id}))
            executed: dict = {}
            while True:
                raw = ws.recv()
                if not raw:
                    continue
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                mtype = msg.get("type")
                data = msg.get("data", {}) or {}
                if data.get("prompt_id") not in (None, prompt_id):
                    continue
                if mtype == "executing":
                    # ComfyUI шлёт executing с node=None при завершении графа
                    if data.get("node") is None:
                        break
                elif mtype == "progress":
                    value = data.get("value", 0)
                    max_val = data.get("max", 1)
                    if on_progress is not None and max_val > 0:
                        on_progress(float(value), float(max_val))
                elif mtype == "executed":
                    node = data.get("node")
                    if node is not None:
                        executed[str(node)] = data.get("output", {})
                elif mtype == "execution_error":
                    raise ComfyUIWebSocketError(
                        f"ComfyUI execution_error для {prompt_id}: {data.get('message')}"
                    )
            return executed
        except (websocket.WebSocketException, OSError) as e:
            # WS разорван/таймаут/недоступен (в т.ч. при длинной remote-генерации через
            # tunnel, или ComfyUI не поднят локально) — Job не теряется: вызывающая
            # сторона восстановит выхлоп через /history (AD-29 inv 5/6).
            raise ComfyUIWebSocketError(f"WebSocket разорван для {prompt_id}: {e}") from e
        finally:
            if ws is not None:
                try:
                    ws.close()
                except Exception:
                    pass
