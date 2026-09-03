"""Candidate Selection Policy (M3).

Источник истины: M3-task §11 (Candidate Selection != Workflow Selection).

Registry ОТБИРАЕТ кандидатов (какие workflow допустимы) — это делает
WorkflowRegistry. Здесь — отдельная детерминированная политика выбора ОДНОГО
конкретного workflow ИЗ уже допустимого набора. Политика НЕ исполняет workflow.

Базовая политика (PROJECT_SPEC §6): explicit override → default → priority →
min_vram_gb → stable deterministic tie-break.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.registry.capability import CapabilityRegistry
from app.registry.semver import parse_version
from app.registry.workflow import AssetInput, Workflow


@dataclass
class SelectedCandidate:
    workflow_id: str
    version: str
    capability: str


def select_candidate(
    capability_id: str,
    available: list[Workflow],
    override: str | None = None,
    capability_registry: CapabilityRegistry | None = None,
) -> SelectedCandidate | None:
    """Выбрать один конкретный workflow из допустимых (AVAILABLE).

    Возвращает SelectedCandidate с зафиксированной версией (concrete version),
    НЕ 'latest' (AD-24: latest не должен попадать в Job).
    """
    available = [w for w in available if w.status_available()]
    if not available:
        return None

    # 1. explicit override ("id" или "id@version")
    if override:
        oid = override
        over_ver: str | None = None
        if "@" in override:
            oid, over_ver = override.split("@", 1)
        matches = [w for w in available if w.id == oid and (over_ver is None or w.version == over_ver)]
        if matches:
            chosen = max(matches, key=lambda w: parse_version(w.version))
            return SelectedCandidate(chosen.id, chosen.version, capability_id)
        return None  # override указывает на недоступный workflow

    # 2. default из capability
    if capability_registry is not None:
        cap = capability_registry.get(capability_id)
        if cap is not None and cap.default_workflow:
            dw = cap.default_workflow
            matches = [w for w in available if w.id == dw]
            if matches:
                chosen = max(matches, key=lambda w: parse_version(w.version))
                return SelectedCandidate(chosen.id, chosen.version, capability_id)

    # 3-5. priority ↓, min_vram_gb ↑, стабильный tie-break (id, version)
    ranked = sorted(
        available,
        key=lambda w: (
            -w.priority,
            w.requirements.get("min_vram_gb", 0) or 0,  # легче — предпочтительнее
            w.id,
            parse_version(w.version),
        ),
    )
    chosen = ranked[0]
    return SelectedCandidate(chosen.id, chosen.version, capability_id)
