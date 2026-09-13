"""WorkflowTemplate — модель шаблона для template-based workflow synthesis (S2).

Шаблон описывает graph pattern (e.g. text→image, image→image) и правила
инстанцирования для конкретного CapabilityCandidate + NodeSchema.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class SafetyClass(str, Enum):
    """Классификация безопасности для auto-test."""
    ALLOWED = "ALLOWED"                      # deterministic media processing
    REQUIRES_CONFIRMATION = "REQUIRES_CONFIRMATION"  # custom node, unknown side effects
    FORBIDDEN = "FORBIDDEN"                  # shell/system/destructive


@dataclass(frozen=True)
class TemplateNode:
    """Одна нода в graph skeleton шаблона."""
    role: str                    # e.g. "generator", "save", "load_image", "process"
    class_type: str              # e.g. "SaveImage", "PollinationsImageGen", "__TARGET__"
    default_inputs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TemplateConnection:
    """Связь между нодами в graph skeleton."""
    from_role: str       # source node role
    from_slot: int       # output slot index
    to_role: str         # target node role
    to_field: str        # input field name on target node


@dataclass(frozen=True)
class WorkflowTemplate:
    """Шаблон workflow для template-based synthesis.

    Описывает graph pattern + правила инстанцирования.
    """
    template_id: str
    version: str
    target_capability: str                     # e.g. "image.generate", "video.image_to_video"
    description: str
    nodes: tuple[TemplateNode, ...]
    connections: tuple[TemplateConnection, ...]
    output_role: str                           # which node produces the output
    output_kind: str                           # "image", "video", "audio"
    required_input_types: frozenset[str]       # e.g. frozenset({"IMAGE"}) or frozenset()
    required_model: bool = False               # needs CheckpointLoader?
    parameter_slots: dict[str, str] = field(default_factory=dict)  # {param_name: "role.field"}
    provenance: str = ""
    safety: SafetyClass = SafetyClass.ALLOWED
    limitations: tuple[str, ...] = ()


@dataclass
class WorkflowSynthesisResult:
    """Результат synthesis."""
    manifest: dict
    workflow: dict
    capability: str
    template_id: str
    warnings: list[str] = field(default_factory=list)
    safety: SafetyClass = SafetyClass.ALLOWED
