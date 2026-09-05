"""M25 — ChainExperience: факт о выполненном media workflow.

ChainExperience = one chain execution, aggregated from ExecutionRecords.
Append-only JSONL persistence.

ChainExperience фиксирует:
  Intent → Prompt → Image₁ → Image₂ → ... → Video → Outcome → Corrections → Parameters

ChainExperience НЕ используется для:
  - автоматического обучения
  - изменения параметров
  - рейтингов
  - запрета параметров

ChainExperience — это факт, не правило.

Usage:
    store = ExperienceStore("data/experience")
    exp = build_chain_experience(chain_id, history, context)
    store.record(exp)
    loaded = store.get_by_chain(chain_id)
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass
class ChainStepExperience:
    """Опыт одного шага цепочки."""
    step_index: int
    capability: str
    input_assets: list[str] = field(default_factory=list)
    output_assets: list[str] = field(default_factory=list)
    params: dict = field(default_factory=dict)
    workflow_id: str = ""
    workflow_version: str = ""
    duration: float = 0.0
    state: str = "QUEUED"
    attempt: int = 1
    error: str | None = None
    error_class: str | None = None
    corrections: list[dict] | None = None


@dataclass
class ChainExperience:
    """Опыт выполнения цепочки media workflow.

    Intent → Prompt → Image₁ → Image₂ → ... → Video → Outcome → Corrections → Parameters
    """
    chain_id: str
    session_id: str
    intent: str = ""
    timestamp: float = field(default_factory=time.time)
    steps: list[ChainStepExperience] = field(default_factory=list)
    # Summary
    total_duration: float = 0.0
    overall_state: str = "PENDING"
    completed_steps: int = 0
    failed_steps: int = 0
    # Sequence-specific (computed, not separate persistence)
    sequence_assets: list[str] | None = None
    temporal_consistency: float | None = None
    animation_quality: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> ChainExperience:
        steps_data = data.pop("steps", [])
        steps = [ChainStepExperience(**s) for s in steps_data]
        return cls(steps=steps, **{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class ExperienceStore:
    """Append-only JSONL persistence для ChainExperience."""

    def __init__(self, base_dir: str = "data/experience") -> None:
        self._base_dir = base_dir
        self._chains_dir = os.path.join(base_dir, "chains")
        os.makedirs(self._chains_dir, exist_ok=True)

    def record(self, exp: ChainExperience) -> None:
        """Записать experience в JSONL."""
        path = os.path.join(self._chains_dir, f"{exp.chain_id}.jsonl")
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(exp.to_dict(), ensure_ascii=False) + "\n")

    def get_by_chain(self, chain_id: str) -> ChainExperience | None:
        """Загрузить experience по chain_id (последняя запись)."""
        path = os.path.join(self._chains_dir, f"{chain_id}.jsonl")
        if not os.path.exists(path):
            return None
        last_line = None
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    last_line = line
        if last_line is None:
            return None
        return ChainExperience.from_dict(json.loads(last_line))

    def list_chains(self) -> list[str]:
        """Список chain_id файлов."""
        return [
            f.replace(".jsonl", "")
            for f in os.listdir(self._chains_dir)
            if f.endswith(".jsonl")
        ]


def build_chain_experience(
    chain_id: str,
    session_id: str,
    history,  # ExecutionHistory
    context=None,  # ConversationContext (optional)
    intent: str = "",
) -> ChainExperience:
    """Построить ChainExperience из ExecutionHistory + ConversationContext.

    Intent → Prompt → Image₁ → Image₂ → ... → Video → Outcome → Corrections → Parameters
    """
    records = history.get_by_chain(chain_id) if hasattr(history, 'get_by_chain') else []

    steps = []
    for i, rec in enumerate(records):
        steps.append(ChainStepExperience(
            step_index=rec.chain_step_index or i,
            capability=rec.capability,
            output_assets=rec.output_assets,
            params=rec.params,
            workflow_id=rec.workflow_id,
            workflow_version=rec.workflow_version,
            duration=rec.duration,
            state=rec.state,
            attempt=rec.attempt,
            error=rec.error_message,
            error_class=rec.error_class,
            corrections=rec.corrections_applied,
        ))

    completed = sum(1 for s in steps if s.state == "SUCCESS")
    failed = sum(1 for s in steps if s.state == "FAILED")

    # Sequence detection: если chain содержит image→image→...→video
    sequence_assets = None
    if steps and any(s.capability.startswith("video.") for s in steps):
        # Собираем все image outputs до видео шага
        img_assets = []
        for s in steps:
            if s.capability.startswith("image."):
                img_assets.extend(s.output_assets)
        if img_assets:
            sequence_assets = img_assets

    return ChainExperience(
        chain_id=chain_id,
        session_id=session_id,
        intent=intent,
        steps=steps,
        total_duration=sum(s.duration for s in steps),
        overall_state="COMPLETED" if completed == len(steps) and len(steps) > 0 else ("FAILED" if failed > 0 else "PENDING"),
        completed_steps=completed,
        failed_steps=failed,
        sequence_assets=sequence_assets,
    )
