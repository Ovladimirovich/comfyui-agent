"""WorkflowEngine (M4) — декларативная сборка prompt и оркестрация execution.

Источник истины: docs/08_EXECUTION_MODEL.md, docs/16_TEST_STRATEGY.md (M4),
треб. 4 (engine декларативен, без if image/elif video), треб. 5 (asset transport
вне engine — через Provider), треб. 9 (lineage через M2).

WorkflowEngine:
  build_prompt(manifest, plan, asset_refs) — чистая сборка executable prompt из workflow.json
      по manifest.inputs / asset_inputs / parameters. НЕТ ветвления по media-типу.
  execute(manifest, plan, provider)         — upload → bind models (runtime discovery) →
      POST /prompt → WS track → fetch outputs → AssetStore.ingest (lineage) → Verifier.
"""
from __future__ import annotations

import copy
import json
import os
import tempfile
import threading
import uuid

from app.assets import AssetStore
from app.engine.job import Job, JobState
from app.engine.verifier import Verifier
from app.engine.websocket import ComfyUIWebSocket, ComfyUIWebSocketError
from app.provider.backend_ref import BackendRef
from app.registry.model import ModelRegistry
from app.registry.workflow import Workflow

# Media-agnostic сигнатуры выхлопа (data-driven, без ветвления по media).
# Ключ — kind из манифеста; значение — допустимые magic-сигнатуры.
# Для kind без записи проверяется только непустота (generic fallback).
_OUTPUT_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    "image": (b"\x89PNG", b"\xff\xd8\xff", b"GIF8", b"BM", b"RIFF"),
    "video": (b"ftyp", b"RIFF", b"\x00\x00\x00\x18", b"\x1a\x45\xdf\xa3"),
    "audio": (b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2", b"OggS", b"fLaC", b"RIFF", b"ftyp", b"\x1a\x45\xdf\xa3"),
}


def _iter_nodes(prompt: dict):
    if isinstance(prompt, dict) and "nodes" in prompt and isinstance(prompt["nodes"], list):
        for n in prompt["nodes"]:
            yield n
    else:
        for n in prompt.values():
            if isinstance(n, dict) and ("class_type" in n or "inputs" in n):
                yield n


def _set_field(prompt, node, field, value) -> None:
    """Установить поле node.inputs[field] в prompt (api- или graph-формат)."""
    if isinstance(prompt, dict) and "nodes" in prompt and isinstance(prompt["nodes"], list):
        for n in prompt["nodes"]:
            if str(n.get("id")) == str(node):
                n.setdefault("inputs", {})[field] = value
                return
    node_obj = prompt.get(str(node)) or prompt.get(node)
    if node_obj is not None:
        node_obj.setdefault("inputs", {})[field] = value


def _first_file_list(node_output: dict) -> list:
    """Media-agnostic извлечение списка файлов из выхлопа узла.

    Не ветвится по media: берёт первый список dict с ключом 'filename'.
    """
    if not isinstance(node_output, dict):
        return []
    for val in node_output.values():
        if isinstance(val, list) and val and isinstance(val[0], dict) and "filename" in val[0]:
            return val
    return []


class WorkflowEngine:
    def __init__(self, asset_store: AssetStore, model_registry: ModelRegistry | None = None) -> None:
        self.store = asset_store
        self.model_registry = model_registry
        self._cancelled: set[str] = set()  # prompt_id отменённых заданий (point 6)

    # --- декларативная сборка prompt (без IO, без ветвления по media) -------

    def build_prompt(self, manifest: Workflow, plan, asset_refs: dict) -> dict:
        if not manifest.workflow_path:
            raise ValueError(f"workflow {manifest.id} не имеет исполнимого workflow.json")
        with open(manifest.workflow_path, "r", encoding="utf-8") as fh:
            template = json.load(fh)
        prompt = copy.deepcopy(template)

        # логич. параметры
        for name, bind in manifest.inputs.items():
            if name in plan.params:
                _set_field(prompt, bind.node, bind.field, plan.params[name])

        # входные ассеты (через Provider/Backend boundary, уже загружены)
        for role, bind in manifest.asset_inputs.items():
            ref = asset_refs.get(role)
            if ref is None:
                continue
            if bind.multi and isinstance(ref, list):
                # M25: multi-asset — создаём N load nodes + batch connection
                self._build_multi_asset_input(prompt, bind, ref)
            else:
                # single-asset — существующее поведение
                single_ref = ref[0] if isinstance(ref, list) else ref
                _set_field(prompt, bind.node, bind.field, single_ref.reference["filename"])

        return prompt

    # --- runtime model binding (per-backend, точное имя модели) -----------

    def _build_multi_asset_input(self, prompt: dict, bind, refs: list) -> None:
        """Собрать multi-asset input: N load nodes → batch node.

        Для BatchImagesNode (COMFY_AUTOGROW_V3) используется формат:
          {"image0": [node_id, 0], "image1": [node_id, 0], ...}
        Для старых ImageBatch — список ссылок:
          {"images": [[node_id, 0], ...]}
        """
        # Находим template node для копирования
        template_node_id = str(bind.load_node_template) if bind.load_node_template else str(bind.node)
        template_node = prompt.get(template_node_id)
        if template_node is None:
            raise ValueError(f"load_node_template '{template_node_id}' не найден в prompt")

        # Для каждого ref создаём отдельный load node
        load_node_ids = []
        for i, ref in enumerate(refs):
            node_id = f"{template_node_id}_m25_{i}"
            new_node = copy.deepcopy(template_node)
            new_node.setdefault("inputs", {})["image"] = ref.reference["filename"]
            prompt[node_id] = new_node
            load_node_ids.append(node_id)

        # Подключаем все load nodes к batch node
        batch_node_id = str(bind.batch_node) if bind.batch_node else None
        if batch_node_id is not None:
            batch_node = prompt.get(batch_node_id)
            if batch_node is not None:
                inputs = batch_node.setdefault("inputs", {})
                # Проверяем тип batch node по его class_type
                class_type = batch_node.get("class_type", "")
                if class_type == "BatchImagesNode":
                    # COMFY_AUTOGROW_V3: images.image0, images.image1, ...
                    images_inputs = inputs.setdefault("images", {})
                    if not isinstance(images_inputs, dict):
                        images_inputs = {}
                    for i, nid in enumerate(load_node_ids):
                        images_inputs[f"image{i}"] = [nid, 0]
                    inputs["images"] = images_inputs
                else:
                    # Старый формат: images = [[node, idx], ...]
                    inputs[bind.batch_field] = [
                        [nid, 0] for nid in load_node_ids
                    ]

    def _bind_models(self, prompt: dict, provider) -> None:
        if self.model_registry is not None:
            # Точное имя модели берём из per-backend каталога (Model Registry, AD-29).
            chosen = self.model_registry.resolve(provider.backend_id, "checkpoint")
        else:
            # Fallback без реестра: runtime discovery у конкретного backend (НЕ глобальное предположение).
            checkpoints = provider.discover_checkpoints()
            chosen = checkpoints[0] if checkpoints else None
        if not chosen:
            return
        for node in _iter_nodes(prompt):
            inp = node.get("inputs", {})
            if isinstance(inp, dict) and "ckpt_name" in inp:
                inp["ckpt_name"] = chosen

    @staticmethod
    def _history_outputs(hist: dict, prompt_id: str) -> dict:
        """Извлечь {node_id: output} из ComfyUI /history (fallback при недоставке WS-событий)."""
        entry = (hist or {}).get(prompt_id, {})
        outputs = entry.get("outputs", {}) if isinstance(entry, dict) else {}
        return {str(k): v for k, v in outputs.items() if isinstance(v, dict)}

    # --- оркестрация execution ---------------------------------------------

    @staticmethod
    def _history_status(hist: dict, prompt_id: str):
        """Статус выполнения из ComfyUI /history (point 5: не маскируем ошибку)."""
        entry = (hist or {}).get(prompt_id, {})
        if not isinstance(entry, dict):
            return None
        st = entry.get("status")
        if isinstance(st, dict):
            return st.get("status_str") or st.get("status")
        return st

    @staticmethod
    def _history_error_message(hist: dict, prompt_id: str) -> str:
        """Извлечь сообщение ошибки из ComfyUI /history (execution_error)."""
        entry = (hist or {}).get(prompt_id, {})
        if not isinstance(entry, dict):
            return "нет данных"
        status = entry.get("status", {})
        messages = status.get("messages", []) if isinstance(status, dict) else []
        for msg_type, msg_data in messages:
            if msg_type == "execution_error" and isinstance(msg_data, dict):
                node = msg_data.get("node_id", "?")
                exc_msg = msg_data.get("exception_message", "неизвестная ошибка")
                return f"node {node}: {exc_msg}"
        return "status=error (без detailed message)"

    @staticmethod
    def _validate_output_bytes(data: bytes, kind: str) -> None:
        """Минимальная валидация выхлопа ДО создания Asset (point 8).

        Media-agnostic: тип результата определяется контрактом (kind из манифеста),
        а не хардкодом по media-типу. Для известных kind проверяются magic-сигнатуры
        из таблицы `_OUTPUT_SIGNATURES`; для остальных — только непустота.
        Битый/пустой выхлоп НЕ порождает output Asset (наличие записи в /history
        само по себе не является успехом). Нет ветвления if image/elif video/elif audio.
        """
        if not data:
            raise RuntimeError(f"output {kind}: пустой файл из backend")
        sigs = _OUTPUT_SIGNATURES.get(kind)
        if sigs:
            head = data[:256]
            if not any(s in head for s in sigs):
                raise RuntimeError(f"output {kind}: несовпадение сигнатуры")

    def execute(self, manifest: Workflow, plan, provider, ws_timeout: int | None = None,
                on_progress=None,
                gateway=None,  # M21: optional ClusterGateway for dispatch tracking
                history=None,  # M21: optional ExecutionHistory for dispatch persistence
    ) -> Job:
        """Запустить execution. on_progress(value, max) — callback для WS progress events.

        M21: gateway历史记录 backend_execution_identity + dispatch tracking.
        """
        # 1. транспорт входных ассетов через Provider boundary
        asset_refs: dict = {}
        source_asset_ids: list = []
        for role, asset_id in plan.asset_bindings.items():
            # M25: поддержка list[str] для multi-asset roles
            if isinstance(asset_id, list):
                refs = []
                for aid in asset_id:
                    asset = self.store.get(aid)
                    if asset is None:
                        raise ValueError(f"asset {aid} не найден для binding '{role}'")
                    refs.append(provider.upload_asset(asset))
                    source_asset_ids.append(aid)
                asset_refs[role] = refs
            else:
                asset = self.store.get(asset_id)
                if asset is None:
                    raise ValueError(f"asset {asset_id} не найден для binding '{role}'")
                asset_refs[role] = provider.upload_asset(asset)
                source_asset_ids.append(asset_id)

        # 2. сборка prompt
        prompt = self.build_prompt(manifest, plan, asset_refs)

        # 3. привязка моделей (runtime discovery)
        self._bind_models(prompt, provider)

        # 4. запуск (один Job = один POST /prompt); client_id связывает WS-события (треб. 6)
        client_id = str(uuid.uuid4())
        prompt_id = provider.execute(prompt, client_id=client_id)
        job = Job(
            prompt_id=prompt_id,
            workflow_id=plan.workflow_id,
            version=plan.version,
            capability=plan.capability,
            state=JobState.RUNNING,
            backend_execution_identity=provider.backend_id,  # M21: set backend identity
        )

        # M21: Record dispatch to Gateway if provided
        if gateway is not None:
            gateway.record_dispatch(prompt_id, provider.backend_id)
        if history is not None:
            history.record_dispatch(prompt_id, provider.backend_id, provider.client.base_url)

        # 5. трекинг через WebSocket (обязателен, треб. 6)
        lock = threading.Lock()

        def _on_progress(value: float, max_val: float) -> None:
            if max_val > 0:
                with lock:
                    job.progress = value / max_val
            if on_progress is not None:
                on_progress(value, max_val)

        ws = ComfyUIWebSocket(provider.client.base_url, client_id=client_id)
        try:
            executed = ws.track(prompt_id, timeout=ws_timeout, on_progress=_on_progress) if ws_timeout is not None else ws.track(prompt_id, on_progress=_on_progress)
        except ComfyUIWebSocketError:
            # WS разорван/таймаут — Job не считается потерянным (AD-29 inv 5/6):
            # восстанавливаем выхлоп через /history (reconnect-safe).
            executed = {}

        # Fallback: если WebSocket не дал выхлоп (таймаут, DirectML не шлёт exec events),
        # ждём завершения execution через polling /history.
        # DirectML: execution может занимать >60s, WS timeout=15s истекает ДО завершения.
        if not executed:
            import time as _time
            poll_deadline = _time.monotonic() + 300  # max 5 min ожидания
            poll_interval = 2.0
            while _time.monotonic() < poll_deadline:
                hist = provider.get_job(prompt_id)
                status_str = self._history_status(hist, prompt_id)
                if status_str == "error":
                    err_msg = self._history_error_message(hist, prompt_id)
                    raise RuntimeError(
                        f"ComfyUI завершил {prompt_id} с ошибкой: {err_msg}"
                    )
                executed = self._history_outputs(hist, prompt_id)
                if executed:
                    break
                _time.sleep(poll_interval)

        # Корреляция (point 7): client_id/prompt_id/job изолированы в рамках этого execute().
        # Отмена (point 6): если задание уже отменено — НЕ создаём ассеты и НЕ переводим в
        # SUCCESS. Позднее WS/history-событие не должно перезаписать CANCELLED в COMPLETED.
        if job.prompt_id in self._cancelled:
            job.state = JobState.CANCELLED
            return job

        # 6. выхлоп → Asset с lineage (только ПОСЛЕ успешной проверки контракта, point 8)
        created = {}
        try:
            for name, spec in manifest.outputs.items():
                node_out = executed.get(str(spec.node)) or executed.get(spec.node)
                if not node_out:
                    raise RuntimeError(f"нет выхлопа для output '{name}' (node {spec.node})")
                files = _first_file_list(node_out)
                if not files:
                    raise RuntimeError(f"output '{name}': нет файлов в {node_out}")
                ref = files[0]
                data = provider.view(
                    BackendRef(provider="comfyui", backend=provider.backend_id, reference=ref)
                )
                # валидация ДО создания ассета: битый/пустой выхлоп не порождает output Asset
                self._validate_output_bytes(data, spec.kind)
                tmp = tempfile.NamedTemporaryFile(
                    delete=False, suffix=f".{spec.kind}", prefix=f"{plan.workflow_id}_"
                )
                tmp.write(data)
                tmp.close()
                try:
                    source = source_asset_ids[0] if source_asset_ids else None
                    asset = self.store.ingest(
                        tmp.name,
                        type=spec.kind,
                        role="output",
                        created_from=job.prompt_id,
                        source_asset=source,
                    )
                finally:
                    if os.path.exists(tmp.name):
                        os.remove(tmp.name)
                created[name] = asset

            # 7. верификация контракта outputs (без ветвления по media)
            Verifier(self.store).verify(manifest, created)
        except Exception:
            # при провале верификации output-ассеты не считаются успешными (point 8)
            job.state = JobState.FAILED
            raise

        job.output_assets = [a.id for a in created.values()]
        job.state = JobState.SUCCESS
        return job

    def cancel(self, job, provider) -> None:
        """Отменить задание (point 6).

        Помечает prompt_id как отменённый и прерывает backend (best-effort). execute()
        после трекинга проверяет self._cancelled и возвращает job без создания ассетов,
        поэтому CANCELLED никогда не превращается в COMPLETED поздним событием.
        """
        self._cancelled.add(job.prompt_id)
        job.state = JobState.CANCELLED
        try:
            provider.cancel(job.prompt_id)
        except Exception:
            pass
