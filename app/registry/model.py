"""Model Registry (M5) — каталог моделей конкретного ExecutionBackend.

Источник истины: PROJECT_SPEC §27 (AD-29), docs/14_RUNTIME_COMPATIBILITY.md (M3).

Ключевые принципы (установка M5):
- Модели принадлежат конкретному ExecutionBackend; нет глобальных предположений «модель есть».
- Discovery — только из реального ComfyUI (через ComfyClient).
- Имя модели — точное (как возвращает ComfyUI), без плейсхолдеров.
- availability / compatibility считаются per-backend.
- Model Registry — отдельный компонент; Provider НЕ является Model Registry и НЕ выбирает workflow.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ModelKind(str, Enum):
    """Вид модели в ComfyUI."""

    CHECKPOINT = "checkpoint"
    LORA = "lora"
    VAE = "vae"
    CONTROLNET = "controlnet"
    EMBEDDING = "embedding"
    UNKNOWN = "unknown"


@dataclass
class ModelInfo:
    """Точная модель, обнаруженная на конкретном backend."""

    name: str
    backend_id: str
    kind: ModelKind = ModelKind.CHECKPOINT
    extra: dict = field(default_factory=dict)

    @property
    def identity(self) -> str:
        """Backend-local identity модели (никогда не глобальный)."""
        return f"{self.backend_id}::{self.kind.value}::{self.name}"


class ModelRegistry:
    """Per-backend каталог моделей (точные имена из реального ComfyUI)."""

    def __init__(self) -> None:
        # backend_id -> name -> ModelInfo
        self._catalog: dict[str, dict[str, ModelInfo]] = {}

    # --- discovery (только из реального ComfyUI) ----------------------------

    def discover(self, client, backend_id: str, kinds=None) -> list[ModelInfo]:
        """Обнаружить модели на конкретном backend через ComfyClient.

        kinds ограничивает набор (по умолчанию — checkpoint, основная генерирующая модель).
        """
        kinds = kinds or [ModelKind.CHECKPOINT]
        models: list[ModelInfo] = []

        for kind in kinds:
            if kind == ModelKind.CHECKPOINT:
                names = client.discover_checkpoints()
            else:
                names = self._discover_by_kind(client, kind)
            for n in names:
                models.append(ModelInfo(name=n, backend_id=backend_id, kind=kind))

        # перезаписываем каталог backend-а (последняя discovery — истина для этого backend)
        self._catalog[backend_id] = {m.name: m for m in models}
        return models

    @staticmethod
    def _discover_by_kind(client, kind: ModelKind) -> list[str]:
        """Discovery не-checkpoint моделей по /object_info (точные имена).

        ComfyClient не имеет специализированного метода для каждого вида —
        читаем список допустимых значений из /object_info соответствующего узла.
        Возвращает [] если вид не распознан (без глобальных предположений).
        """
        try:
            info = client.get_object_info()
        except Exception:
            return []
        node_class = {
            ModelKind.LORA: "LoraLoader",
            ModelKind.VAE: "VAELoader",
            ModelKind.CONTROLNET: "ControlNetLoader",
            ModelKind.EMBEDDING: "EmbeddingLoader",
        }.get(kind)
        if not node_class or node_class not in info:
            return []
        inputs = (info[node_class].get("input", {}) or {})
        required = inputs.get("required", {}) if isinstance(inputs, dict) else {}
        for field_name, spec in required.items():
            if isinstance(spec, list) and len(spec) >= 1 and isinstance(spec[0], list):
                return [str(x) for x in spec[0]]
        return []

    # --- per-backend queries ------------------------------------------------

    def models_for(self, backend_id: str) -> list[str]:
        return list(self._catalog.get(backend_id, {}).keys())

    def infos_for(self, backend_id: str) -> list[ModelInfo]:
        return list(self._catalog.get(backend_id, {}).values())

    def is_available(self, backend_id: str, name: str) -> bool:
        """Точная проверка availability на конкретном backend (без глобальных допущений)."""
        return name in self._catalog.get(backend_id, {})

    def get(self, backend_id: str, name: str) -> Optional[ModelInfo]:
        return self._catalog.get(backend_id, {}).get(name)

    def resolve(self, backend_id: str, requirement: str, kind: ModelKind = ModelKind.CHECKPOINT) -> Optional[str]:
        """Разрешить требование в точное имя модели на backend.

        - requirement — точное имя: возвращаем, если доступно на backend.
        - requirement — вид модели ("checkpoint"): возвращаем первую доступную этого вида.
        Возвращает None, если на данном backend модель недоступна (НЕ маскируем отсутствие).
        """
        cat = self._catalog.get(backend_id, {})
        if requirement in cat:
            return requirement
        # requirement как "вид модели"
        if requirement in {k.value for k in ModelKind}:
            for info in cat.values():
                if info.kind.value == requirement:
                    return info.name
        # requirement как kind-enum
        try:
            kind_val = ModelKind(requirement)
        except ValueError:
            kind_val = kind
        for info in cat.values():
            if info.kind == kind_val:
                return info.name
        return None

    def compatibility(self, backend_id: str, required_models: list[str]) -> tuple[bool, list[str]]:
        """Проверка доступности требуемых (точных) имён на конкретном backend.

        Возвращает (all_available, missing) — per-backend, без глобальных допущений.
        """
        missing = [m for m in required_models if not self.is_available(backend_id, m)]
        return (len(missing) == 0, missing)

    def snapshot(self, backend_id: str) -> list[ModelInfo]:
        return copy.deepcopy(self.infos_for(backend_id))
