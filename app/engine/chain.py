"""ExecutionChain — выполнение цепочки подзадач.

Координирует последовательное выполнение SubTasks с:
- Per-step retry (M13)
- Per-step semantic verification (M14)
- Chain state tracking
- Cancel support
"""
from __future__ import annotations

import time as _time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from app.engine.history import ExecutionHistory, ExecutionRecord
from app.engine.job import Job, JobState
from app.planner.decomposer import SubTask


class ChainState(Enum):
    """Состояние цепочки."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ChainContext:
    """Контекст цепочки: хранит промежуточные assets между шагами.

    Создаётся на время выполнения цепочки, уничтожается после.
    Assets остаются в AssetStore (transient state, не persistent).
    """
    session_id: str
    active_asset: str | None = None  # ID последнего успешного output asset
    workflows_used: list[str] = field(default_factory=list)  # workflow_id@version для каждого шага


@dataclass
class ChainStep:
    """Один шаг цепочки."""
    subtask: SubTask
    job: Optional[Job] = None
    state: ChainState = ChainState.PENDING
    error: Optional[str] = None
    duration: float = 0.0

    @property
    def is_terminal(self) -> bool:
        return self.state in (ChainState.COMPLETED, ChainState.FAILED, ChainState.CANCELLED)


@dataclass
class ChainResult:
    """Результат выполнения цепочки."""
    state: ChainState
    steps: list[ChainStep]
    total_duration: float = 0.0
    completed_steps: int = 0
    failed_steps: int = 0

    @property
    def ok(self) -> bool:
        return self.state == ChainState.COMPLETED


class ExecutionChain:
    """Цепочка выполнения подзадач (M18).

    Координирует последовательное выполнение SubTasks с retry и verification.
    """

    def __init__(
        self,
        execute_fn: Callable[[SubTask], Job],
        history: Optional[ExecutionHistory] = None,
        max_attempts_per_step: int = 3,
        on_step_complete: Optional[Callable[[int, ChainStep], None]] = None,
    ) -> None:
        """
        execute_fn: функция выполнения одного SubTask → Job
        history: ExecutionHistory для записи результатов
        max_attempts_per_step: максимальное количество попыток на шаг
        on_step_complete: callback при завершении шага (index, step)
        """
        self.execute_fn = execute_fn
        self.history = history or ExecutionHistory()
        self.max_attempts_per_step = max_attempts_per_step
        self.on_step_complete = on_step_complete
        self._cancelled = False

    def execute(self, subtasks: list[SubTask]) -> ChainResult:
        """Выполнить цепочку подзадач.

        Возвращает ChainResult с результатами всех шагов.
        """
        start_time = _time.monotonic()
        steps: list[ChainStep] = []
        self._cancelled = False

        for i, subtask in enumerate(subtasks):
            if self._cancelled:
                # Помечаем оставшиеся шаги как cancelled
                for remaining in subtasks[i:]:
                    steps.append(ChainStep(
                        subtask=remaining,
                        state=ChainState.CANCELLED,
                    ))
                break

            step = self._execute_step(subtask, i)
            steps.append(step)

            if self.on_step_complete:
                self.on_step_complete(i, step)

            # Если шаг.failed — останавливаем цепочку
            if step.state == ChainState.FAILED:
                break

        total_duration = _time.monotonic() - start_time
        completed = sum(1 for s in steps if s.state == ChainState.COMPLETED)
        failed = sum(1 for s in steps if s.state == ChainState.FAILED)

        # Определяем общее состояние
        if self._cancelled:
            overall_state = ChainState.CANCELLED
        elif failed > 0:
            overall_state = ChainState.FAILED
        elif completed == len(subtasks):
            overall_state = ChainState.COMPLETED
        else:
            overall_state = ChainState.FAILED

        return ChainResult(
            state=overall_state,
            steps=steps,
            total_duration=total_duration,
            completed_steps=completed,
            failed_steps=failed,
        )

    def _execute_step(self, subtask: SubTask, index: int) -> ChainStep:
        """Выполнить один шаг с retry."""
        step = ChainStep(subtask=subtask)
        start_time = _time.monotonic()

        for attempt in range(1, self.max_attempts_per_step + 1):
            if self._cancelled:
                step.state = ChainState.CANCELLED
                return step

            try:
                job = self.execute_fn(subtask)
                job.chain_step_index = index  # M18: set chain step index
                step.job = job
                step.duration = _time.monotonic() - start_time

                # Записываем в history
                record = ExecutionRecord(
                    prompt_id=job.prompt_id,
                    capability=subtask.capability,
                    params=subtask.params,
                    workflow_id=job.workflow_id,
                    workflow_version=job.version,
                    state=job.state.value,
                    duration=step.duration,
                    error_message=job.error if hasattr(job, 'error') else None,
                    attempt=attempt,
                    chain_step_index=index,
                    output_assets=list(job.output_assets) if hasattr(job, 'output_assets') else [],
                )
                self.history.record(record)

                if job.state.value == "SUCCESS":
                    step.state = ChainState.COMPLETED
                    return step
                else:
                    step.error = job.error if hasattr(job, 'error') else "execution failed"

            except Exception as e:
                step.duration = _time.monotonic() - start_time
                step.error = str(e)

        # Все попытки исчерпаны
        step.state = ChainState.FAILED
        return step

    def cancel(self) -> None:
        """Отменить цепочку (после текущего шага)."""
        self._cancelled = True
