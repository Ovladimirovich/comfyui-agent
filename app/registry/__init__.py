"""Registry package (M3): Capability + Workflow Registry.

Не исполняет workflow и не обращается к ComfyUI /prompt (M3-task §17).
"""
from __future__ import annotations

from .capability import Capability, CapabilityRegistry
from .compatibility import evaluate_compatibility
from .registry import CandidateResult, WorkflowRegistry
from .selection import SelectedCandidate, select_candidate
from .semver import compare_version, max_version, parse_version
from .workflow import (
    AssetInput,
    ManifestError,
    NodeBinding,
    OutputSpec,
    UnavailableReason,
    UnknownReason,
    Workflow,
    WorkflowStatus,
    load_workflow,
    validate_manifest,
    validate_workflow_structure,
)

__all__ = [
    "Capability",
    "CapabilityRegistry",
    "Workflow",
    "WorkflowStatus",
    "UnavailableReason",
    "UnknownReason",
    "ManifestError",
    "NodeBinding",
    "AssetInput",
    "OutputSpec",
    "WorkflowRegistry",
    "CandidateResult",
    "SelectedCandidate",
    "select_candidate",
    "evaluate_compatibility",
    "load_workflow",
    "validate_manifest",
    "validate_workflow_structure",
    "parse_version",
    "compare_version",
    "max_version",
]
