"""BackendRef — абстракция ссылки на ассет/объект внутри Execution Backend.

Источник истины: docs/07_PROVIDER_MODEL.md (BackendRef, AD-26/NQ-03).
Backend-specific форма reference (для ComfyUI: {filename, subfolder, type}) живёт
внутри backend, НЕ в универсальном контракте ядра.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BackendRef:
    provider: str
    backend: str
    reference: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)
