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
    # M25.4: SequenceExperience как computed view (вложенный dict, единый JSONL)
    sequence_experience: dict | None = None

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


@dataclass
class SequenceExperience:
    """M25.4: computed view над ChainExperience для image-sequence → video.

    Решение M25_ARCHITECTURE_REVIEW §3.4: НЕ отдельная persistence-модель,
    а производное представление. Хранится как вложенный dict внутри
    ChainExperience (единый JSONL, без второго ExperienceStore).
    """

    sequence_id: str
    image_assets: list[str] = field(default_factory=list)
    video_asset: str | None = None
    image_params: list[dict] = field(default_factory=list)
    video_params: dict | None = None
    temporal_consistency: float | None = None
    image_to_video_transition: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "SequenceExperience":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def build_sequence_experience(
    chain_exp: ChainExperience,
    temporal_result: object | None = None,
) -> SequenceExperience:
    """M25.4: построить SequenceExperience (computed view) из ChainExperience.

    Извлекает image-шаги (до video шага) и формирует view последовательности.
    temporal_consistency берётся из chain_exp (заполняется вызывающей стороной
    на основе SemanticVerifier.verify_temporal_consistency) либо из temporal_result.
    """
    steps = chain_exp.steps
    image_steps = [s for s in steps if s.capability.startswith("image.")]
    video_steps = [s for s in steps if s.capability.startswith("video.")]

    image_assets = list(chain_exp.sequence_assets or [])
    image_params = [s.params for s in image_steps]
    video_asset = (
        video_steps[-1].output_assets[0]
        if video_steps and video_steps[-1].output_assets
        else None
    )
    video_params = video_steps[-1].params if video_steps else None

    temporal_consistency = chain_exp.temporal_consistency
    if temporal_consistency is None and temporal_result is not None:
        temporal_consistency = getattr(temporal_result, "temporal_score", None)

    # transition quality — зеркалит семантику SemanticVerifier (>=0.7 success)
    transition = None
    if temporal_consistency is not None:
        if temporal_consistency >= 0.7:
            transition = "success"
        elif temporal_consistency < 0.5:
            transition = "poor"
        else:
            transition = "inconsistent"

    return SequenceExperience(
        sequence_id=chain_exp.chain_id,
        image_assets=image_assets,
        video_asset=video_asset,
        image_params=image_params,
        video_params=video_params,
        temporal_consistency=temporal_consistency,
        image_to_video_transition=transition,
    )


# M26.1: минимальный порог выборки для experience-preference.
# Переиспользует существующую конвенцию частотного порога (analytics.py:72, adaptive.py:99: count >= 2).
# НЕ является magic threshold для значения temporal score — используется только для
# достаточности выборки (ranking по непрерывному score, без произвольного cutoff).
EXPERIENCE_MIN_SAMPLES_FOR_PREFERENCE = 2


@dataclass
class TemporalStats:
    """M26.1: агрегированная temporal-статистика по capability (read-only)."""

    capability: str
    sample_count: int
    avg_score: float
    available: bool
    per_workflow_avg: dict = field(default_factory=dict)


@dataclass
class ExperienceHint:
    """M26.4: lightweight signal от analytics → Composer suggestion.

    Не subsystem — чистые данные для computed suggestion.
    Модель: Experience → analytics → preference/signal → Composer suggestion.
    """

    capability: str
    preferred_params: dict = field(default_factory=dict)
    avg_temporal_consistency: float | None = None
    sample_count: int = 0


class ExperienceAnalytics:
    """M26.1: read-only aggregation над ExperienceStore.

    Не создаёт persistence, не мутирует ChainExperience/SequenceExperience.
    Источник данных — ChainExperience (temporal_consistency, sequence_experience),
    которые HistoryAnalytics (читающий ExecutionHistory) НЕ содержит.

    Результат — planning context / preference signal, НЕ policy.
    Experience = факт: ranking/preference только, никаких prohibition.
    """

    def __init__(self, store: "ExperienceStore") -> None:
        self.store = store

    def load_all(self) -> list["ChainExperience"]:
        """Загрузить все ChainExperience из store (последняя запись per chain)."""
        out: list[ChainExperience] = []
        for cid in self.store.list_chains():
            exp = self.store.get_by_chain(cid)
            if exp is not None:
                out.append(exp)
        return out

    def temporal_stats(self, capability: str) -> "TemporalStats | None":
        """Агрегировать temporal_consistency по цепочкам с шагом `capability`.

        Возвращает None если нет релевантных samples (UNKNOWN → neutral, не влияет).
        Не мутирует исходные ChainExperience.
        """
        scores: list[float] = []
        per_workflow: dict[str, list[float]] = {}
        for exp in self.load_all():
            steps = [s for s in exp.steps if s.capability == capability]
            if not steps:
                continue
            if exp.temporal_consistency is None:
                continue
            scores.append(exp.temporal_consistency)
            last = steps[-1]
            wf_key = f"{last.workflow_id}@{last.workflow_version}"
            per_workflow.setdefault(wf_key, []).append(exp.temporal_consistency)
        if not scores:
            return None
        return TemporalStats(
            capability=capability,
            sample_count=len(scores),
            avg_score=sum(scores) / len(scores),
            available=any(s is not None for s in scores),
            per_workflow_avg={k: sum(v) / len(v) for k, v in per_workflow.items()},
        )

    def preferred_params(
        self,
        capability: str,
        min_samples: int = EXPERIENCE_MIN_SAMPLES_FOR_PREFERENCE,
    ) -> dict:
        """M26.2: experience-derived param preference (ranking, НЕ prohibition).

        Среди цепочек с temporal-опытом по `capability` выбирает цепочку с
        наивысшим temporal_consistency (непрерывный ranking, без magic cutoff)
        и возвращает её video_params как soft preference.

        Недостаточно samples (< min_samples) → {} (fallback, нейтрально, без влияния).
        Возвращает только scalar-совместимые параметры; исходник не мутируется.
        """
        candidates = [
            exp
            for exp in self.load_all()
            if any(s.capability == capability for s in exp.steps)
            and exp.temporal_consistency is not None
        ]
        if len(candidates) < min_samples:
            return {}
        best = max(candidates, key=lambda e: e.temporal_consistency)
        seq = best.sequence_experience or {}
        vp = seq.get("video_params") or {}
        return {
            k: v for k, v in vp.items() if isinstance(v, (str, int, float, bool))
        }
