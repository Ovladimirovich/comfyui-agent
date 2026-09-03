"""Runtime / model / custom-node / input compatibility (M3).

Источник истины: docs/14_RUNTIME_COMPATIBILITY.md, docs/06_WORKFLOW_MODEL.md, M3-task §6-§10.

Правило: UNKNOWN != AVAILABLE. Если требование нельзя достоверно проверить
(версия ComfyUI неизвестна, поле runtime UNKNOWN) — UNKNOWN, а не AVAILABLE.

Registry НЕ обращается к ComfyUI и не исполняет workflow — данные о моделях и
custom-нодах передаются явно (в M3 из тестов/фикстур; в проде — из M1 client).
"""
from __future__ import annotations

from typing import Optional

from app.assets import Asset
from app.registry.runtime import RuntimeInfo
from app.registry.semver import compare_version
from app.registry.workflow import (
    AssetInput,
    UnavailableReason,
    UnknownReason,
    Workflow,
    WorkflowStatus,
)


def evaluate_compatibility(
    workflow: Workflow,
    runtime: RuntimeInfo,
    models: Optional[set[str]] = None,
    custom_nodes: Optional[set[str]] = None,
    assets: Optional[list[Asset]] = None,
) -> tuple[WorkflowStatus, list]:
    """Вернуть (статус, причины) совместимости workflow с окружением.

    Декларативная проверка контракта — без запуска ComfyUI и без обработки медиа.
    """
    # declared_only никогда не исполним
    if workflow.declared_only:
        return WorkflowStatus.DECLARED_ONLY, []

    # манифест/граф уже невалидны — статус не пересматриваем
    if (
        UnavailableReason.INVALID_MANIFEST in workflow.reasons
        or UnavailableReason.INVALID_WORKFLOW in workflow.reasons
    ):
        return WorkflowStatus.UNAVAILABLE, list(workflow.reasons)

    reasons: list[UnavailableReason] = []
    unknown: list[UnknownReason] = []
    req = workflow.requirements

    # --- accelerator ---
    accel_req = req.get("accelerator")
    if accel_req and accel_req != "any":
        if runtime.accelerator is None:
            unknown.append(UnknownReason.UNKNOWN_RUNTIME)
        elif runtime.accelerator != accel_req:
            reasons.append(UnavailableReason.INCOMPATIBLE_RUNTIME)

    # --- vram ---
    min_vram = req.get("min_vram_gb")
    if min_vram is not None:
        if runtime.vram_gb is None:
            unknown.append(UnknownReason.UNKNOWN_RUNTIME)
        elif runtime.vram_gb < min_vram:
            reasons.append(UnavailableReason.INSUFFICIENT_VRAM)

    # --- fp16 ---
    fp16_req = req.get("fp16")
    if fp16_req is True:
        if runtime.fp16 is None:
            unknown.append(UnknownReason.UNKNOWN_RUNTIME)
        elif runtime.fp16 is False:
            reasons.append(UnavailableReason.INCOMPATIBLE_RUNTIME)

    # --- xformers ---
    xformers_req = req.get("xformers")
    if xformers_req is True:
        if runtime.xformers is None:
            unknown.append(UnknownReason.UNKNOWN_RUNTIME)
        elif runtime.xformers is False:
            reasons.append(UnavailableReason.INCOMPATIBLE_RUNTIME)

    # --- comfyui version ---
    mcv = workflow.min_comfyui_version
    if mcv and mcv != "0.0.0":
        if runtime.comfyui_version is None:
            unknown.append(UnknownReason.UNKNOWN_VERSION)
        else:
            try:
                if compare_version(runtime.comfyui_version, mcv) < 0:
                    reasons.append(UnavailableReason.INCOMPATIBLE_RUNTIME)
            except ValueError:
                unknown.append(UnknownReason.UNKNOWN_VERSION)

    # --- required models (по точному имени) ---
    if workflow.required_models:
        if models is None:
            # не можем подтвердить наличие → считаем отсутствующей
            reasons.append(UnavailableReason.MISSING_MODEL)
        else:
            for m in workflow.required_models:
                if m not in models:
                    reasons.append(UnavailableReason.MISSING_MODEL)
                    break

    # --- required custom nodes (по идентификатору из object_info) ---
    if workflow.required_custom_nodes:
        if custom_nodes is None:
            reasons.append(UnavailableReason.MISSING_CUSTOM_NODE)
        else:
            for c in workflow.required_custom_nodes:
                if c not in custom_nodes:
                    reasons.append(UnavailableReason.MISSING_CUSTOM_NODE)
                    break

    # --- input compatibility (контракт, не обработка медиа) ---
    if assets is not None:
        provided_kinds = {a.type for a in assets}
        for role, ain in workflow.asset_inputs.items():
            if ain.kind not in provided_kinds:
                reasons.append(UnavailableReason.INPUT_INCOMPATIBLE)
                break

    if reasons:
        return WorkflowStatus.UNAVAILABLE, list(reasons)
    if unknown:
        return WorkflowStatus.UNKNOWN, list(unknown)
    return WorkflowStatus.AVAILABLE, []
