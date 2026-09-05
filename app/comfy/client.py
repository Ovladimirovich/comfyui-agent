"""HTTP-клиент ComfyUI.

Минимальный фундамент M1: только взаимодействие с реальным ComfyUI через stdlib.
Не содержит логики WorkflowEngine / Provider / JobManager / Agent (это последующие milestones).
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

# Локальный дефолт, но не архитектурное предположение о localhost (AD-29).
# Реальный endpoint берётся из COMFY_URL либо передаётся явно в base_url.
DEFAULT_BASE_URL = os.environ.get("COMFY_URL", "http://127.0.0.1:8188")
DEFAULT_TIMEOUT = 30

# Имя переменной окружения с ComfyUI-platform API-ключом для cloud API-нод
# (comfy_api_nodes: SoniloTextToMusic и др.). Ключ передаётся в ComfyUI через
# extra_data["api_key_comfy_org"] промпта: server-side НЕ инжектит его для внешних
# HTTP-клиентов, поэтому агент шлёт ключ самим промптом (транспорт, не ядро engine).
COMFY_API_KEY_ENV = "COMFY_API_KEY_COMFY_ORG"


def _comfy_api_extra_data() -> dict | None:
    """extra_data с API-ключом для cloud API-нод, если задан; иначе None.

    Не влияет на обычные (не API) промпты — ComfyUI игнорирует неиспользуемый ключ.
    """
    key = os.environ.get(COMFY_API_KEY_ENV)
    if not key:
        return None
    return {"api_key_comfy_org": key.strip()}


class ComfyClientError(RuntimeError):
    """Ошибка взаимодействия с ComfyUI (HTTP или недоступность)."""

    def __init__(self, message: str, status: int | None = None, body: str | None = None):
        super().__init__(message)
        self.status = status
        self.body = body


class ComfyClient:
    """Синхронный HTTP-клиент ComfyUI (stdlib, без тяжёлых зависимостей)."""

    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout: int = DEFAULT_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        # Явно отключаем системный прокси для localhost (Hiddify и др. блокируют 127.0.0.1).
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def _request(self, method: str, path: str, json_body=None, raw: bool = False):
        url = f"{self.base_url}{path}"
        data = None
        headers = {"Accept": "application/json"}
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with self._opener.open(req, timeout=self.timeout) as resp:
                if raw:
                    return resp.read()
                # Для больших ответов (например /object_info ~1.6MB через туннель)
                # читаем чанками чтобы избежать IncompleteRead
                content_length = resp.headers.get("Content-Length")
                if content_length and int(content_length) > 500000:
                    chunks = []
                    while True:
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        chunks.append(chunk)
                    return json.loads(b"".join(chunks).decode("utf-8"))
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace") if e.fp else None
            raise ComfyClientError(f"ComfyUI HTTP {e.code} at {path}", status=e.code, body=body) from e
        except urllib.error.URLError as e:
            raise ComfyClientError(f"ComfyUI недоступен по {url}: {e.reason}") from e

    def get_system_stats(self) -> dict:
        return self._request("GET", "/system_stats")

    def get_object_info(self) -> dict:
        return self._request("GET", "/object_info")

    def get_queue(self) -> dict:
        return self._request("GET", "/queue")

    def get_history(self, prompt_id: str | None = None) -> dict:
        path = f"/history/{prompt_id}" if prompt_id else "/history"
        return self._request("GET", path)

    def view(self, filename: str, subfolder: str = "", type: str = "output") -> bytes:
        params = "filename={}&subfolder={}&type={}".format(
            urllib.parse.quote(filename),
            urllib.parse.quote(subfolder),
            urllib.parse.quote(type),
        )
        return self._request("GET", f"/view?{params}", raw=True)

    def interrupt(self) -> dict:
        return self._request("POST", "/interrupt", json_body={})

    def queue_prompt(self, prompt: dict, client_id: str | None = None, extra_data: dict | None = None) -> dict:
        body = {"prompt": prompt}
        if client_id:
            body["client_id"] = client_id
        # Cloud API-ноды (Sonilo и др.) требуют api_key_comfy_org в extra_data промпта.
        if extra_data is None:
            extra_data = _comfy_api_extra_data()
        if extra_data:
            body["extra_data"] = extra_data
        return self._request("POST", "/prompt", json_body=body)

    # --- upload (asset transport boundary) ---------------------------------

    def upload_image(self, file_path: str, subfolder: str = "", type_: str = "input") -> dict:
        """Загрузить файл в ComfyUI (POST /upload/image, multipart).

        Возвращает {name, subfolder, type}. Используется Provider для транспорта ассета
        в backend. Не является Model Registry (просто HTTP-загрузка).
        """
        import mimetypes
        import os
        import uuid

        boundary = uuid.uuid4().hex
        filename = os.path.basename(file_path)
        mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        with open(file_path, "rb") as fh:
            data = fh.read()
        parts = []
        parts.append(f"--{boundary}".encode())
        parts.append(f'Content-Disposition: form-data; name="image"; filename="{filename}"'.encode())
        parts.append(f"Content-Type: {mime}".encode())
        parts.append(b"")
        parts.append(data)
        for name, val in (("subfolder", subfolder), ("type", type_)):
            if val:
                parts.append(f"--{boundary}".encode())
                parts.append(f'Content-Disposition: form-data; name="{name}"'.encode())
                parts.append(b"")
                parts.append(val.encode())
        parts.append(f"--{boundary}--".encode())
        parts.append(b"")
        body = b"\r\n".join(parts)
        url = f"{self.base_url}/upload/image"
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "Accept": "application/json"},
            method="POST",
        )
        try:
            with self._opener.open(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace") if e.fp else None
            raise ComfyClientError(f"ComfyUI upload HTTP {e.code}", status=e.code, body=body) from e
        except urllib.error.URLError as e:
            raise ComfyClientError(f"ComfyUI недоступен при загрузке: {e.reason}") from e

    # --- runtime model discovery (НЕ Model Registry) -----------------------

    @staticmethod
    def _extract_options(spec) -> list:
        """Извлечь список имён опций из поля ввода node (оба формата ComfyUI)."""
        if spec is None:
            return []
        if isinstance(spec, list):
            # старый формат: [ [options...], {meta} ]
            if spec and isinstance(spec[0], list):
                return [str(x) for x in spec[0]]
            return []
        if isinstance(spec, dict):
            opts = spec.get("options")
            if isinstance(opts, list):
                return [str(x) for x in opts]
        return []

    def list_model_options(self, node_type: str, input_name: str) -> list:
        """Runtime discovery допустимых имён моделей из /object_info (по точному имени)."""
        info = self.get_object_info()
        node = info.get(node_type, {})
        inp = node.get("input", {})
        if isinstance(inp, dict):
            required = inp.get("required", {})
            optional = inp.get("optional", {})
            spec = required.get(input_name) or optional.get(input_name)
            return self._extract_options(spec)
        if isinstance(inp, list):
            # старый формат: список [name, typeinfo]
            for entry in inp:
                if isinstance(entry, list) and entry and entry[0] == input_name:
                    return self._extract_options(entry[1])
        return []

    def discover_checkpoints(self) -> list:
        """Список доступных чекпоинтов (runtime discovery). Без хранения/индексации."""
        return self.list_model_options("CheckpointLoaderSimple", "ckpt_name")
