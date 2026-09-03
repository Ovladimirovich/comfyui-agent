"""Workflow Model + Manifest validation (M3).

Источник истины: docs/06_WORKFLOW_MODEL.md, docs/PROJECT_SPEC.md §11/§12.

Workflow Registry НЕ исполняет workflow (это M4/M5). Здесь только:
- декларативная модель Workflow;
- статическая валидация manifest.json (схема);
- базовая структурная валидация workflow.json (если присутствует).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from .capability import CapabilityRegistry
from .semver import parse_version


class WorkflowStatus(str, Enum):
    """Жизненный цикл workflow из PROJECT_SPEC §12 + DECLARED_ONLY (docs/06)."""

    DISCOVERED = "DISCOVERED"
    VALIDATED = "VALIDATED"
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"
    DECLARED_ONLY = "DECLARED_ONLY"


class UnavailableReason(str, Enum):
    """Причины UNAVAILABLE (docs/06 + M3-task §5/§10)."""

    INVALID_MANIFEST = "invalid_manifest"
    INVALID_WORKFLOW = "invalid_workflow"
    INCOMPATIBLE_RUNTIME = "incompatible_runtime"
    INSUFFICIENT_VRAM = "insufficient_vram"
    MISSING_MODEL = "missing_model"
    MISSING_CUSTOM_NODE = "missing_custom_node"
    INPUT_INCOMPATIBLE = "input_incompatible"


class UnknownReason(str, Enum):
    """Причины UNKNOWN (невозможно достоверно проверить совместимость)."""

    UNKNOWN_VERSION = "unknown_version"
    UNKNOWN_RUNTIME = "unknown_runtime"


class ManifestError(Exception):
    """Ошибка валидации манифеста/структуры workflow."""

    def __init__(self, message: str, reasons: list[Enum]) -> None:
        super().__init__(message)
        self.reasons = reasons


@dataclass
class NodeBinding:
    node: str
    field: str


@dataclass
class AssetInput:
    node: str
    field: str
    kind: str


@dataclass
class OutputSpec:
    node: str
    kind: str


@dataclass
class Workflow:
    """Декларативное описание workflow (без исполнимого кода)."""

    id: str
    version: str
    capability: str
    provider: str
    backend: str
    inputs: dict[str, NodeBinding] = field(default_factory=dict)
    asset_inputs: dict[str, AssetInput] = field(default_factory=dict)
    outputs: dict[str, OutputSpec] = field(default_factory=dict)
    parameters: dict[str, Any] = field(default_factory=dict)
    required_models: list[str] = field(default_factory=list)
    required_custom_nodes: list[str] = field(default_factory=list)
    min_comfyui_version: str = "0.0.0"
    requirements: dict[str, Any] = field(default_factory=dict)
    limits: dict[str, Any] = field(default_factory=dict)
    declared_only: bool = False
    priority: int = 0
    status: WorkflowStatus = WorkflowStatus.DISCOVERED
    reasons: list[Enum] = field(default_factory=list)
    manifest_path: Optional[str] = None
    workflow_path: Optional[str] = None

    def status_available(self) -> bool:
        return self.status == WorkflowStatus.AVAILABLE


# --------------------------------------------------------------------------- #
# Загрузка и валидация манифеста
# --------------------------------------------------------------------------- #

def _require_str(data: dict, key: str, where: str) -> str:
    val = data.get(key)
    if not isinstance(val, str) or not val.strip():
        raise ManifestError(f"{where}: поле '{key}' должно быть непустой строкой", [UnavailableReason.INVALID_MANIFEST])
    return val


def _check_node_binding(value: Any, where: str, require_kind: bool = False) -> dict:
    if not isinstance(value, dict):
        raise ManifestError(f"{where}: ожидался объект {{node, field}}", [UnavailableReason.INVALID_MANIFEST])
    if "node" not in value or "field" not in value:
        raise ManifestError(f"{where}: требуются node и field", [UnavailableReason.INVALID_MANIFEST])
    if not isinstance(value["field"], str):
        raise ManifestError(f"{where}: field должен быть строкой", [UnavailableReason.INVALID_MANIFEST])
    if require_kind and not isinstance(value.get("kind"), str):
        raise ManifestError(f"{where}: требуется kind (строка)", [UnavailableReason.INVALID_MANIFEST])
    return value


def validate_manifest(data: dict, capabilities: Optional[CapabilityRegistry] = None) -> None:
    """Статическая валидация схемы манифеста. Бросает ManifestError при ошибке."""
    if not isinstance(data, dict):
        raise ManifestError("manifest должен быть объектом", [UnavailableReason.INVALID_MANIFEST])

    _require_str(data, "id", "manifest")
    # version — semver
    version = data.get("version")
    if not isinstance(version, str):
        raise ManifestError("manifest.version должен быть строкой", [UnavailableReason.INVALID_MANIFEST])
    try:
        parse_version(version)
    except ValueError as e:
        raise ManifestError(f"manifest.version: {e}", [UnavailableReason.INVALID_MANIFEST])

    capability = _require_str(data, "capability", "manifest")
    if capabilities is not None and not capabilities.exists(capability):
        raise ManifestError(f"manifest.capability неизвестен: {capability}", [UnavailableReason.INVALID_MANIFEST])

    _require_str(data, "provider", "manifest")

    # inputs
    inputs = data.get("inputs", {})
    if not isinstance(inputs, dict):
        raise ManifestError("manifest.inputs должен быть объектом", [UnavailableReason.INVALID_MANIFEST])
    for name, val in inputs.items():
        _check_node_binding(val, f"inputs.{name}")

    # asset_inputs (требует kind)
    asset_inputs = data.get("asset_inputs", {})
    if not isinstance(asset_inputs, dict):
        raise ManifestError("manifest.asset_inputs должен быть объектом", [UnavailableReason.INVALID_MANIFEST])
    for name, val in asset_inputs.items():
        _check_node_binding(val, f"asset_inputs.{name}", require_kind=True)

    # outputs (требует node + kind, БЕЗ field — docs/06)
    outputs = data.get("outputs", {})
    if not isinstance(outputs, dict):
        raise ManifestError("manifest.outputs должен быть объектом", [UnavailableReason.INVALID_MANIFEST])
    for name, val in outputs.items():
        if not isinstance(val, dict) or "node" not in val or not isinstance(val.get("kind"), str):
            raise ManifestError(f"outputs.{name}: ожидался объект {{node, kind}}", [UnavailableReason.INVALID_MANIFEST])

    # parameters — struct
    parameters = data.get("parameters", {})
    if not isinstance(parameters, dict):
        raise ManifestError("manifest.parameters должен быть объектом", [UnavailableReason.INVALID_MANIFEST])

    # required_models / required_custom_nodes — списки
    for key in ("required_models", "required_custom_nodes"):
        val = data.get(key, [])
        if not isinstance(val, list):
            raise ManifestError(f"manifest.{key} должен быть списком", [UnavailableReason.INVALID_MANIFEST])

    # min_comfyui_version — semver
    mcv = data.get("min_comfyui_version", "0.0.0")
    if not isinstance(mcv, str):
        raise ManifestError("manifest.min_comfyui_version должен быть строкой", [UnavailableReason.INVALID_MANIFEST])
    try:
        parse_version(mcv)
    except ValueError as e:
        raise ManifestError(f"manifest.min_comfyui_version: {e}", [UnavailableReason.INVALID_MANIFEST])

    # requirements — struct (опционально)
    if "requirements" in data and not isinstance(data["requirements"], dict):
        raise ManifestError("manifest.requirements должен быть объектом", [UnavailableReason.INVALID_MANIFEST])


def _extract_nodes(workflow_json: Any) -> dict[str, dict]:
    """Извлечь map node_id -> node из workflow.json (graph или API-формат)."""
    if not isinstance(workflow_json, dict):
        return {}
    if "nodes" in workflow_json and isinstance(workflow_json["nodes"], list):
        nodes: dict[str, dict] = {}
        for n in workflow_json["nodes"]:
            if isinstance(n, dict) and "id" in n:
                nodes[str(n["id"])] = n
        return nodes
    # API-формат: ключи — node id (отфильтровываем служебные)
    nodes = {}
    for k, v in workflow_json.items():
        if isinstance(v, dict) and ("class_type" in v or "inputs" in v):
            nodes[str(k)] = v
    return nodes


def validate_workflow_structure(workflow: "Workflow", workflow_json: Any) -> None:
    """Базовая целостность workflow.json (docs/06 §Validation).

    Проверяет: граф — dict, node IDs из манифеста существуют, поля bindings
    присутствуют в node.inputs. Не валидирует семантику ComfyUI-нод (это M4+).
    """
    nodes = _extract_nodes(workflow_json)
    if not nodes and isinstance(workflow_json, dict) is False:
        raise ManifestError("workflow.json: ожидался граф (dict)", [UnavailableReason.INVALID_WORKFLOW])

    def _check(bind: NodeBinding, where: str) -> None:
        node = nodes.get(bind.node)
        if node is None:
            raise ManifestError(f"{where}: node '{bind.node}' не найден в workflow.json", [UnavailableReason.INVALID_WORKFLOW])
        inputs = node.get("inputs") if isinstance(node, dict) else None
        if not isinstance(inputs, dict) or bind.field not in inputs:
            raise ManifestError(f"{where}: поле '{bind.field}' отсутствует в node '{bind.node}'", [UnavailableReason.INVALID_WORKFLOW])

    for name, b in workflow.inputs.items():
        _check(b, f"inputs.{name}")
    for name, a in workflow.asset_inputs.items():
        _check(NodeBinding(a.node, a.field), f"asset_inputs.{name}")
    for name, o in workflow.outputs.items():
        if o.node not in nodes:
            raise ManifestError(f"outputs.{name}: node '{o.node}' не найден в workflow.json", [UnavailableReason.INVALID_WORKFLOW])


def load_workflow(manifest_path: str | os.PathLike, capabilities: Optional[CapabilityRegistry] = None) -> Workflow:
    """Загрузить и валидировать workflow из manifest.json.

    Для обычного workflow проверяется и структура workflow.json (если есть рядом).
    Для declared_only — только манифест, исполнимый граф не требуется.
    При ошибке валидации возвращает Workflow со status=UNAVAILABLE и reasons,
    НЕ бросает (чтобы discovery мог зарегистрировать проблемный workflow).
    """
    manifest_path = Path(manifest_path)
    raw = manifest_path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return Workflow(
            id=manifest_path.parent.name, version="0.0.0", capability="",
            provider="", backend="", status=WorkflowStatus.UNAVAILABLE,
            reasons=[UnavailableReason.INVALID_MANIFEST], manifest_path=str(manifest_path),
        )

    try:
        validate_manifest(data, capabilities)
    except ManifestError as e:
        return Workflow(
            id=str(data.get("id", manifest_path.parent.name)), version=str(data.get("version", "0.0.0")),
            capability=str(data.get("capability", "")), provider=str(data.get("provider", "")),
            backend=str(data.get("backend", "")), status=WorkflowStatus.UNAVAILABLE,
            reasons=e.reasons, manifest_path=str(manifest_path),
        )

    declared_only = bool(data.get("declared_only", False))
    wf = Workflow(
        id=data["id"],
        version=data["version"],
        capability=data["capability"],
        provider=data["provider"],
        backend=data.get("backend", ""),
        inputs={k: NodeBinding(str(v["node"]), v["field"]) for k, v in data.get("inputs", {}).items()},
        asset_inputs={k: AssetInput(str(v["node"]), v["field"], v["kind"]) for k, v in data.get("asset_inputs", {}).items()},
        outputs={k: OutputSpec(str(v["node"]), v["kind"]) for k, v in data.get("outputs", {}).items()},
        parameters=data.get("parameters", {}),
        required_models=list(data.get("required_models", [])),
        required_custom_nodes=list(data.get("required_custom_nodes", [])),
        min_comfyui_version=data.get("min_comfyui_version", "0.0.0"),
        requirements=data.get("requirements", {}),
        limits=data.get("limits", {}),
        declared_only=declared_only,
        priority=int(data.get("priority", 0)),
        manifest_path=str(manifest_path),
    )

    workflow_json_path = manifest_path.parent / "workflow.json"
    if workflow_json_path.exists():
        wf.workflow_path = str(workflow_json_path)
        if not declared_only:
            try:
                wf_json = json.loads(workflow_json_path.read_text(encoding="utf-8"))
                validate_workflow_structure(wf, wf_json)
            except ManifestError as e:
                wf.status = WorkflowStatus.UNAVAILABLE
                wf.reasons = e.reasons
                return wf
            except json.JSONDecodeError:
                wf.status = WorkflowStatus.UNAVAILABLE
                wf.reasons = [UnavailableReason.INVALID_WORKFLOW]
                return wf
        # declared_only: исполнимый граф не обязателен
        wf.status = WorkflowStatus.DECLARED_ONLY if declared_only else WorkflowStatus.VALIDATED
    else:
        if declared_only:
            wf.status = WorkflowStatus.DECLARED_ONLY
        else:
            # обычный workflow без workflow.json — исполнимый граф отсутствует
            wf.status = WorkflowStatus.UNAVAILABLE
            wf.reasons = [UnavailableReason.INVALID_WORKFLOW]

    return wf
