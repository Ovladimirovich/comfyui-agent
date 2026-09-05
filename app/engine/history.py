"""M13 — Execution History: запись и хранение результатов выполнения.

ExecutionRecord — одна попытка выполнения (один POST /prompt).
ExecutionHistory — in-memory коллекция записей с JSONL persistence.
M21: dispatch tracking для Reconciliation & Recovery.

Usage:
    history = ExecutionHistory()
    record = ExecutionRecord.from_job(job, params, duration=1.5)
    history.record(record)
    attempts = history.get_attempts(capability="image.generate")
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.resource.models import ExecutionDispatchRecord


@dataclass
class ExecutionRecord:
    """Одна попытка выполнения workflow.

    Связывает prompt_id (Job) с контекстом: capability, params, workflow,
    результатом (success/failure), длительностью, ошибкой.
    """

    prompt_id: str
    capability: str
    params: dict = field(default_factory=dict)
    workflow_id: str = ""
    workflow_version: str = ""
    state: str = "QUEUED"  # QUEUED/RUNNING/SUCCESS/FAILED/CANCELLED
    duration: float = 0.0  # секунды
    error_message: str | None = None
    error_class: str | None = None  # transient/permanent/verification
    attempt: int = 1
    output_assets: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    # M18: chain step index for multi-step execution
    chain_step_index: int | None = None
    # M20/AD-42: backend execution identity (кто физически выполнял задачу)
    backend_execution_identity: str | None = None
    # M23: какие стратегии корректировки были применены
    corrections_applied: list[dict] | None = None  # [{strategy, from_params, to_params}]
    # M25: group identifier for multi-step chains
    chain_id: str | None = None

    @classmethod
    def from_job(
        cls,
        job,
        params: dict | None = None,
        duration: float = 0.0,
        error_class: str | None = None,
        attempt: int = 1,
        corrections_applied: list[dict] | None = None,  # M23
    ) -> ExecutionRecord:
        """Создать ExecutionRecord из Job объекта."""
        return cls(
            prompt_id=job.prompt_id,
            capability=job.capability,
            params=params or {},
            workflow_id=job.workflow_id,
            workflow_version=job.version,
            state=job.state.value if hasattr(job.state, "value") else str(job.state),
            duration=duration,
            error_message=job.error if hasattr(job, "error") else None,
            error_class=error_class,
            attempt=attempt,
            output_assets=list(job.output_assets) if job.output_assets else [],
            chain_step_index=getattr(job, 'chain_step_index', None),
            backend_execution_identity=getattr(job, 'backend_execution_identity', None),
            corrections_applied=corrections_applied,
            chain_id=getattr(job, 'chain_id', None),
        )

    def to_dict(self) -> dict:
        """Сериализация в dict (для JSONL persistence)."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> ExecutionRecord:
        """Десериализация из dict."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class ExecutionHistory:
    """In-memory коллекция ExecutionRecord с JSONL persistence.

    append-only: записи не изменяются после добавления.
    """

    def __init__(self, persist_path: str | None = None) -> None:
        self._records: list[ExecutionRecord] = []
        self._persist_path = persist_path
        self._dispatch_records: dict[str, dict] = {}  # M21: dispatch tracking
        if persist_path and os.path.exists(persist_path):
            self._load()
            self._load_dispatches()  # M21: load dispatch records

    def record(self, rec: ExecutionRecord) -> None:
        """Добавить запись в историю."""
        self._records.append(rec)
        if self._persist_path:
            self._append_jsonl(rec)

    def get_attempts(self, capability: str | None = None, chain_step_index: int | None = None) -> list[ExecutionRecord]:
        """Получить все попытки, опционально фильтруя по capability и/или chain_step_index."""
        result = self._records
        if capability:
            result = [r for r in result if r.capability == capability]
        if chain_step_index is not None:
            result = [r for r in result if r.chain_step_index == chain_step_index]
        return list(result)

    def get_recent(self, n: int = 10) -> list[ExecutionRecord]:
        """Последние N записей."""
        return self._records[-n:]

    def get_by_prompt_id(self, prompt_id: str) -> ExecutionRecord | None:
        """Найти запись по prompt_id."""
        for r in self._records:
            if r.prompt_id == prompt_id:
                return r
        return None

    def get_successful(self, capability: str | None = None) -> list[ExecutionRecord]:
        """Только успешные попытки."""
        return [
            r for r in self.get_attempts(capability)
            if r.state == "SUCCESS"
        ]

    def get_failed(self, capability: str | None = None) -> list[ExecutionRecord]:
        """Только неуспешные попытки."""
        return [
            r for r in self.get_attempts(capability)
            if r.state == "FAILED"
        ]

    def success_rate(self, capability: str | None = None) -> float:
        """Доля успешных попыток (0.0–1.0). Если попыток нет — 0.0."""
        attempts = self.get_attempts(capability)
        if not attempts:
            return 0.0
        successful = sum(1 for r in attempts if r.state == "SUCCESS")
        return successful / len(attempts)

    def avg_duration(self, capability: str | None = None) -> float:
        """Средняя длительность успешных попыток. Если нет — 0.0."""
        successful = self.get_successful(capability)
        if not successful:
            return 0.0
        return sum(r.duration for r in successful) / len(successful)

    def count(self, capability: str | None = None) -> int:
        """Количество попыток."""
        return len(self.get_attempts(capability))

    def clear(self) -> None:
        """Очистить историю (для тестов)."""
        self._records.clear()

    # --- M25: Chain-level queries ---

    def get_by_chain(self, chain_id: str) -> list[ExecutionRecord]:
        """Все записи одной цепочки, упорядоченные по chain_step_index и timestamp."""
        return sorted(
            [r for r in self._records if r.chain_id == chain_id],
            key=lambda r: (r.chain_step_index or 0, r.timestamp),
        )

    def get_chain_summary(self, chain_id: str) -> dict:
        """Агрегированная статистика по цепочке."""
        records = self.get_by_chain(chain_id)
        if not records:
            return {"chain_id": chain_id, "total_steps": 0}
        successful = [r for r in records if r.state == "SUCCESS"]
        return {
            "chain_id": chain_id,
            "total_steps": len(records),
            "completed_steps": len(successful),
            "failed_steps": len(records) - len(successful),
            "capabilities": list({r.capability for r in records}),
            "total_duration": sum(r.duration for r in records),
            "workflows": list({f"{r.workflow_id}@{r.workflow_version}" for r in records if r.workflow_id}),
        }

    # --- M21: Dispatch tracking for Reconciliation ---

    def record_dispatch(
        self,
        prompt_id: str,
        backend_id: str,
        endpoint_url: str = "",
    ) -> None:
        """Записать факт диспетчеризации задачи на backend.

        M21: Dispatch record хранится отдельно от ExecutionRecord,
        но сохраняется в тот же JSONL файл (если persist_path задан).
        """
        self._dispatch_records[prompt_id] = {
            "prompt_id": prompt_id,
            "backend_id": backend_id,
            "endpoint_url": endpoint_url,
            "submitted_at": time.time(),
        }
        if self._persist_path:
            self._append_dispatch_jsonl(prompt_id, backend_id, endpoint_url)

    def get_dispatch(self, prompt_id: str) -> dict | None:
        """Получить запись о диспетчеризации по prompt_id."""
        return self._dispatch_records.get(prompt_id)

    def get_dispatches_by_backend(self, backend_id: str) -> list[dict]:
        """Получить все dispatch записи для backend."""
        return [
            d for d in self._dispatch_records.values()
            if d["backend_id"] == backend_id
        ]

    def _append_dispatch_jsonl(
        self, prompt_id: str, backend_id: str, endpoint_url: str
    ) -> None:
        """Дописать dispatch запись в JSONL файл."""
        # Dispatch сохраняется в тот же файл, что и history
        if not self._persist_path:
            return
        with open(self._persist_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "_dispatch": True,
                "prompt_id": prompt_id,
                "backend_id": backend_id,
                "endpoint_url": endpoint_url,
                "submitted_at": time.time(),
            }, ensure_ascii=False) + "\n")

    def _load_dispatches(self) -> None:
        """Загрузить dispatch записи из JSONL файла."""
        if not self._persist_path:
            return
        if not os.path.exists(self._persist_path):
            return
        with open(self._persist_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        d = json.loads(line)
                        # Dispatch records have "_dispatch": True marker
                        if d.get("_dispatch"):
                            self._dispatch_records[d["prompt_id"]] = d
                    except (json.JSONDecodeError, TypeError, KeyError):
                        continue

    def _append_jsonl(self, rec: ExecutionRecord) -> None:
        """Дописать запись в JSONL файл."""
        os.makedirs(os.path.dirname(self._persist_path) or ".", exist_ok=True)
        with open(self._persist_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec.to_dict(), ensure_ascii=False) + "\n")

    def _load(self) -> None:
        """Загрузить записи из JSONL файла."""
        if not self._persist_path or not os.path.exists(self._persist_path):
            return
        with open(self._persist_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        self._records.append(ExecutionRecord.from_dict(json.loads(line)))
                    except (json.JSONDecodeError, TypeError):
                        continue
