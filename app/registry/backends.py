"""Backend catalog (AD-29 inv 12) — выбор ExecutionBackend для Agent.

Provider = логический поставщик; Backend = конкретное место исполнения
(local_comfyui / remote_comfyui / cloud_comfyui). Agent выбирает backend из
каталога по capability + (опц.) runtime-совместимости. Различия backend живут
ниже Provider/Backend boundary — в Agent нет if local/remote.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Callable, Optional

from app.registry.registry import WorkflowRegistry
from app.registry.runtime import RuntimeInfo


@dataclass
class BackendSpec:
    backend_id: str
    base_url: str
    kind: str = "remote_comfyui"  # local_comfyui / remote_comfyui / cloud_comfyui
    priority: int = 0
    capabilities: set[str] = field(default_factory=set)  # пусто = все capability
    disabled: bool = False
    description: str = ""


class BackendCatalog:
    """Каталог Known ExecutionBackend и выбор под capability.

    choose() медиа-agnostic: не ветвится по media, просто отбирает backend,
    способный исполнить capability (по declared capabilities / runtime-пробе).
    """

    def __init__(self, backends: list[BackendSpec] | None = None) -> None:
        self.backends: list[BackendSpec] = backends or []

    def add(self, spec: BackendSpec) -> None:
        self.backends.append(spec)

    def by_id(self, backend_id: str) -> Optional[BackendSpec]:
        for b in self.backends:
            if b.backend_id == backend_id:
                return b
        return None

    def choose(
        self,
        capability: str,
        registry: Optional[WorkflowRegistry] = None,
        probe: Optional[Callable[[BackendSpec], Optional[RuntimeInfo]]] = None,
    ) -> Optional[BackendSpec]:
        """Выбрать backend для capability.

        Без probe: из eligibility (не disabled + capability разрешён) берётся
        backend с наивысшим priority. С probe: дополнительно ранжируется по VRAM
        (больше = лучше), probe(None) исключает недоступный backend.
        """
        eligible = [
            b
            for b in self.backends
            if not b.disabled and (not b.capabilities or capability in b.capabilities)
        ]
        if not eligible:
            return None
        if probe is not None:
            scored: list[tuple[float, int, BackendSpec]] = []
            for b in eligible:
                try:
                    rt = probe(b)
                except Exception:
                    rt = None
                if rt is None:
                    continue
                scored.append((rt.vram_total or 0, b.priority, b))
            if scored:
                scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
                return scored[0][2]
        eligible.sort(key=lambda b: b.priority, reverse=True)
        return eligible[0]

    @classmethod
    def from_env(cls) -> "BackendCatalog":
        """Каталог из env: COMFY_BACKENDS (JSON-список) либо одиночный backend.

        COMFY_BACKENDS: [{"backend_id":"remote_comfyui","base_url":"…","priority":10}]
        Иначе: backend из COMFY_REMOTE_URL (priority 10) или COMFY_URL (local).
        """
        raw = os.environ.get("COMFY_BACKENDS")
        if raw:
            try:
                data = json.loads(raw)
                return cls([BackendSpec(**b) for b in data])
            except Exception:
                pass
        url = os.environ.get("COMFY_REMOTE_URL") or os.environ.get("COMFY_URL")
        if url:
            kind = "remote_comfyui" if os.environ.get("COMFY_REMOTE_URL") else "local_comfyui"
            return cls([BackendSpec(backend_id=kind, base_url=url, kind=kind, priority=10)])
        return cls([BackendSpec(backend_id="local_comfyui", base_url="http://127.0.0.1:8188", priority=0)])
