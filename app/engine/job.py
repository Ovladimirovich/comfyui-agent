"""Job (M4) — единица исполнения: один POST /prompt → один prompt_id.

Источник истины: docs/08_EXECUTION_MODEL.md (один Job = один граф).
Жизненный цикл: QUEUED → RUNNING → SUCCESS | FAILED | CANCELLED.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class JobState(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class Job:
    prompt_id: str
    workflow_id: str
    version: str
    capability: str
    state: JobState = JobState.QUEUED
    progress: float = 0.0
    output_assets: list = field(default_factory=list)
    error: str | None = None
    # M11.6: prompt metadata (optional, set by Agent.generate)
    _original_prompt: str | None = None
    _enhanced_prompt: str | None = None
    _prompt_source: str | None = None
    # M13: attempt tracking
    attempt: int = 1
    error_class: str | None = None  # transient/permanent/verification
    # M18: chain step index for multi-step execution
    chain_step_index: int | None = None
    # M20/AD-42: backend execution identity (кто физически выполнял задачу)
    backend_execution_identity: str | None = None
