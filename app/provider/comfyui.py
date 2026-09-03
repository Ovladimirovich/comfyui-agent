"""ComfyUI Provider — Provider/Execution Backend boundary (M4, AD-29).

Источник истины: docs/07_PROVIDER_MODEL.md, docs/02_ARCHITECTURE.md (Provider ≠ Backend),
PROJECT_SPEC §27 (AD-29: ExecutionBackend может быть local_comfyui / remote_comfyui / cloud_comfyui).

Provider (comfyui) — логический поставщик capability; backend_id — конкретное место исполнения.
Различия local/remote живут ниже этого boundary (transport layer), не в логике Provider.
Provider отвечает за взаимодействие с backend:
  upload_asset(asset) → BackendRef   — транспорт ассета в backend
  execute(prompt)     → prompt_id     — запуск графа (один Job)
  get_job(prompt_id)  → история       — статус/выхлоп
  cancel(prompt_id)                    — interrupt
  discover_checkpoints()               — runtime model discovery (/object_info), НЕ Model Registry
  view(ref)          → bytes          — скачивание выходного файла

Provider НЕ выбирает workflow (AD-22) и НЕ является Model Registry (M5). Он лишь предоставляет
backend и runtime model discovery. Связывание capability + выбранный workflow + backend выполняет
Agent/Selection (M3); WorkflowEngine строит prompt и оркестрирует execution. Model Registry — отдельный
компонент (app/registry/model.py), используемый engine/Agent для per-backend точных имён моделей.
"""
from __future__ import annotations

from app.comfy.client import ComfyClient
from app.provider.backend_ref import BackendRef


class ComfyUIProvider:
    def __init__(self, client: ComfyClient, backend_id: str = "local_comfyui") -> None:
        self.client = client
        self.backend_id = backend_id

    # --- asset transport (Provider boundary) ------------------------------

    def upload_asset(self, asset) -> BackendRef:
        """Загрузить Asset в backend и вернуть BackendRef."""
        resp = self.client.upload_image(asset.path)
        ref = {
            "filename": resp.get("name"),
            "subfolder": resp.get("subfolder", ""),
            "type": resp.get("type", "input"),
        }
        return BackendRef(provider="comfyui", backend=self.backend_id, reference=ref)

    # --- execution ---------------------------------------------------------

    def execute(self, prompt: dict, client_id: str | None = None) -> str:
        """Отправить prompt в ComfyUI. Возвращает prompt_id (один Job).

        client_id передаётся в /prompt, чтобы ComfyUI маршрутизировал WebSocket-события
        (executing/progress/executed) именно в этот WS-клиент (треб. 6).
        """
        result = self.client.queue_prompt(prompt, client_id=client_id)
        prompt_id = result.get("prompt_id")
        if not prompt_id:
            raise RuntimeError(f"ComfyUI не вернул prompt_id: {result}")
        return prompt_id

    def get_job(self, prompt_id: str) -> dict:
        return self.client.get_history(prompt_id)

    def cancel(self, prompt_id: str) -> None:
        self.client.interrupt()

    # --- outputs / model discovery ---------------------------------------

    def view(self, ref: BackendRef) -> bytes:
        r = ref.reference
        return self.client.view(r.get("filename", ""), r.get("subfolder", ""), r.get("type", "output"))

    def discover_checkpoints(self) -> list:
        return self.client.discover_checkpoints()
