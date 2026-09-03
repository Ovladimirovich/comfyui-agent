"""Workflow Registry (M3) — оркестрация discovery / candidates / latest / select.

Источник истины: docs/06_WORKFLOW_MODEL.md, M3-task §2/§12/§16.

Реестр обнаруживает workflow в workflows/, валидирует манифесты, фильтрует по
совместимости и возвращает кандидатов. Он НЕ исполняет workflow (это M4/M5) и
НЕ обращается к ComfyUI /prompt (M3-task §17).

Допустимые зависимости: Capability Registry → Workflow Registry → RuntimeInfo → Asset.
Запрещённые: Provider.execute(), LLM, ComfyUI /prompt.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.assets import Asset
from app.registry.capability import CapabilityRegistry
from app.registry.compatibility import evaluate_compatibility
from app.registry.runtime import RuntimeInfo
from app.registry.selection import SelectedCandidate, select_candidate
from app.registry.semver import max_version
from app.registry.workflow import (
    Workflow,
    WorkflowStatus,
    load_workflow,
)


@dataclass
class CandidateResult:
    available: list[Workflow] = field(default_factory=list)
    report: dict[str, tuple[Workflow, WorkflowStatus, list]] = field(default_factory=dict)


class WorkflowRegistry:
    def __init__(self, capabilities: Optional[CapabilityRegistry] = None) -> None:
        self.capabilities = capabilities or CapabilityRegistry()
        self.workflows: list[Workflow] = []

    # --- discovery ---------------------------------------------------------

    def discover(self, root: str | Path) -> list[Workflow]:
        """Обнаружить workflow в каталоге (subdir/manifest.json)."""
        root = Path(root)
        self.workflows = []
        if not root.exists():
            return []
        for sub in sorted(root.iterdir()):
            if sub.is_dir():
                mp = sub / "manifest.json"
                if mp.exists():
                    self.workflows.append(load_workflow(mp, self.capabilities))
        return self.workflows

    # --- lookup ------------------------------------------------------------

    def by_capability(self, capability_id: str) -> list[Workflow]:
        return [w for w in self.workflows if w.capability == capability_id]

    def get(self, workflow_id: str, version: Optional[str] = None) -> Workflow | None:
        for w in self.workflows:
            if w.id == workflow_id and (version is None or w.version == version):
                return w
        return None

    # --- compatibility / candidates ---------------------------------------

    def evaluate(
        self,
        workflow: Workflow,
        runtime: RuntimeInfo,
        models: Optional[set[str]] = None,
        custom_nodes: Optional[set[str]] = None,
        assets: Optional[list[Asset]] = None,
    ) -> tuple[WorkflowStatus, list]:
        return evaluate_compatibility(workflow, runtime, models, custom_nodes, assets)

    def candidates(
        self,
        capability_id: str,
        runtime: RuntimeInfo,
        assets: Optional[list[Asset]] = None,
        models: Optional[set[str]] = None,
        custom_nodes: Optional[set[str]] = None,
    ) -> CandidateResult:
        """Вернуть допустимые workflow и отчёт, почему остальные недоступны.

        Отвечает на DoD: «Для capability X, runtime Y, assets Z — какие workflow
        допустимы и почему остальные недоступны?» — без запуска workflow.
        """
        result = CandidateResult()
        for wf in self.by_capability(capability_id):
            status, reasons = self.evaluate(wf, runtime, models, custom_nodes, assets)
            wf.status = status
            wf.reasons = reasons
            result.report[wf.id] = (wf, status, reasons)
            if status == WorkflowStatus.AVAILABLE:
                result.available.append(wf)
        return result

    # --- versioning --------------------------------------------------------

    def latest(self, workflow_id: str) -> str | None:
        """AD-24: latest = max VALIDATED/AVAILABLE semver для workflow_id.

        DECLARED_ONLY и невалидные исключаются. Возвращает КОНКРЕТНУЮ версию.
        """
        vers: list[str] = []
        for w in self.workflows:
            if w.id == workflow_id and w.status in (WorkflowStatus.VALIDATED, WorkflowStatus.AVAILABLE):
                vers.append(w.version)
        return max_version(vers)

    # --- selection ---------------------------------------------------------

    def select(
        self,
        capability_id: str,
        runtime: RuntimeInfo,
        assets: Optional[list[Asset]] = None,
        models: Optional[set[str]] = None,
        custom_nodes: Optional[set[str]] = None,
        override: Optional[str] = None,
    ) -> SelectedCandidate | None:
        """Выбрать один конкретный workflow (concrete version) из допустимых."""
        res = self.candidates(capability_id, runtime, assets, models, custom_nodes)
        return select_candidate(capability_id, res.available, override, self.capabilities)
