"""Conversation Context (M7) — многоходовой контекст поверх существующего Agent/Asset/Execution.

Media-agnostic: ConversationContext хранит только идентификаторы и строки
(asset id, job id, workflow id@version, capability) — НЕТ ImageContext/VideoContext
и НЕТ ветвления по media-типу. Резолюция входных ассетов опирается на
manifest.asset_inputs[role].kind (строка) против asset.type (строка) — без
if image/elif video/elif audio (AD-03, AD-23).

Источник истины: docs/PROJECT_SPEC.md §15, docs/11_CONVERSATION_MODEL.md.

Поток (media-agnostic):
    turn(session_id, capability|request, params, assets)
      → ConversationContext (история/active_asset/active_job/active_workflow)
      → Agent.prepare (выбор workflow по capability)
      → resolve_asset_inputs (explicit > active_asset > reference; AD-23)
      → WorkflowEngine.execute (тот же путь image/video/audio)
      → Job + output Asset'ы
      → обновление контекста (успех → active_asset; ошибка → active_asset НЕ заменяется)

M13: retry loop с SSE events (retry_started, retry_completed).
"""
from __future__ import annotations

import time as _time
import uuid as _uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from app.agent import Agent, AgentError
from app.context.session_manager import SessionManager
from app.engine.chain import ChainContext, ExecutionChain, ChainState
from app.engine.history import ExecutionHistory, ExecutionRecord
from app.engine.job import Job, JobState
from app.engine.retry import RetryPolicy, classify_error
from app.planner import PlanContext, Composer


@dataclass
class ConversationContext:
    """Состояние одной conversation session (process/session scoped, без БД).

    Хранит только идентификаторы и строки — media-agnostic по определению.
    """

    session_id: str
    messages: list[dict] = field(default_factory=list)
    assets: set[str] = field(default_factory=set)
    jobs: set[str] = field(default_factory=set)
    workflows: set[str] = field(default_factory=set)
    parameters: dict = field(default_factory=dict)
    active_task: Optional[str] = None
    active_workflow: Optional[str] = None
    active_job: Optional[str] = None
    active_asset: Optional[str] = None
    unresolved: list[dict] = field(default_factory=list)
    dialog_state: str = "idle"

    def as_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "messages": self.messages,
            "assets": sorted(self.assets),
            "jobs": sorted(self.jobs),
            "workflows": sorted(self.workflows),
            "parameters": self.parameters,
            "active_task": self.active_task,
            "active_workflow": self.active_workflow,
            "active_job": self.active_job,
            "active_asset": self.active_asset,
            "unresolved": self.unresolved,
            "dialog_state": self.dialog_state,
        }


class ConversationAgent(Agent):
    """Media-agnostic многоходовой оркестратор (M7).

    Расширяет Agent поддержкой ConversationContext на основе session_id.
    Никакого media-ветвления: тот же Agent.prepare / WorkflowEngine.execute /
    Job / Asset, что у одноходовых вызовов.

    M13: retry loop с SSE events (retry_started, retry_completed).
    """

    def __init__(
        self,
        *args,
        session_manager: Optional[SessionManager] = None,  # M15
        adaptive_planner_enabled: bool = True,  # M16: включить adaptive planning
        composer: Optional[Composer] = None,  # M19: Intent → Capability Planning
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.sessions: dict[str, ConversationContext] = {}
        self.session_manager = session_manager
        self._adaptive_planner_enabled = adaptive_planner_enabled
        self.composer = composer

    # --- session management (изоляция сессий) ---

    def session(self, session_id: str) -> ConversationContext:
        """Получить или создать ConversationContext для session (изоляция по session_id).

        M15: если session_manager задан, пытается загрузить из persistence.
        """
        ctx = self.sessions.get(session_id)
        if ctx is None:
            # M15: попытка загрузки из persistence
            if self.session_manager is not None:
                ctx = self.session_manager.resume(session_id)
            if ctx is None:
                ctx = ConversationContext(session_id=session_id)
            self.sessions[session_id] = ctx
        return ctx

    def context(self, session_id: str) -> ConversationContext:
        return self.session(session_id)

    def active_asset_id(self, session_id: str) -> Optional[str]:
        ctx = self.sessions.get(session_id)
        return ctx.active_asset if ctx else None

    def active_asset(self, session_id: str):
        ctx = self.sessions.get(session_id)
        if ctx is None or ctx.active_asset is None:
            return None
        return self.store.get(ctx.active_asset)

    # --- multi-turn ---

    def turn(
        self,
        session_id: str,
        capability: Optional[str] = None,
        request: Optional[str] = None,
        params: Optional[dict] = None,
        assets: Optional[dict] = None,
        backend_id: str = "local_comfyui",
        provider=None,
        base_url: Optional[str] = None,
        ws_timeout: Optional[int] = None,
        on_progress=None,
        max_attempts: int = 1,  # M13: количество попыток (1 = без retry)
    ):
        """Один ход диалога: capability/request → Job, с обновлением ConversationContext.

        M13: поддержка retry loop. max_attempts > 1 включает повтор при FAILED.
        on_retry callback: on_retry(attempt, reason, delay) — для SSE events.

        Приоритет резолюции входных ассетов (ref: AD-23, §15):
          1) явно указанный пользователем Asset/path (assets[role]);
          2) ConversationContext.active_asset (если тип совпадает с role.kind);
          3) явная ссылка на предыдущий Asset/turn (assets[role]={"asset_id": id}).
        """
        ctx = self.session(session_id)

        # M18: multi-step detection — decompose BEFORE single-step planner
        if capability is None and request:
            from app.planner.decomposer import TaskDecomposer
            decomposer = TaskDecomposer()
            subtasks = decomposer.decompose(request)
            if len(subtasks) > 1:
                # M19: Validate and enhance via Composer (AD-41)
                if self.composer is not None:
                    target = subtasks[-1].capability
                    composition = self.composer.compose(
                        target_capability=target,
                        params=params or {},
                        available_types=set(),
                    )
                    if composition.success:
                        subtasks = composition.chain
                    # else: fallback to TaskDecomposer output
                
                # MULTI-STEP PATH (M18) — early return
                return self._execute_chain(
                    session_id=session_id,
                    subtasks=subtasks,
                    params=params,
                    assets=assets,
                    backend_id=backend_id,
                    provider=provider,
                    base_url=base_url,
                    ws_timeout=ws_timeout,
                    on_progress=on_progress,
                    max_attempts=max_attempts,
                )
            # else: single-step — fall through to existing code

        # 1) capability (explicit ИЛИ через planner из request; Conversation Context
        #    существует независимо от LLM — planner опционален)
        if capability is None and request:
            active_asset_obj = self.active_asset(session_id)
            plan_ctx = PlanContext(
                active_asset_type=active_asset_obj.type if active_asset_obj else None,
                capabilities=tuple(self.capabilities()),
                active_workflow=ctx.active_workflow,
                previous_prompt=ctx.parameters.get("prompt"),
            )
            planner = self.planner or _default_planner()

            # M16: auto-select AdaptivePlanner если история >= 3 для capability
            # AD-36: порог считается по конкретной capability при вызове plan().
            if self._adaptive_planner_enabled and self.execution_history is not None:
                from app.planner.adaptive import AdaptivePlanner, MIN_SUCCESSFUL_PER_CAPABILITY
                # Определяем capability через fallback planner
                base_result = planner.plan(request, context=plan_ctx)
                # Проверяем порог по конкретной capability
                success_count = len(self.execution_history.get_successful(base_result.capability))
                if success_count >= MIN_SUCCESSFUL_PER_CAPABILITY:
                    if not isinstance(planner, AdaptivePlanner):
                        planner = AdaptivePlanner(
                            history=self.execution_history,
                            fallback=self.planner or _default_planner(),
                        )

            result = planner.plan(request, context=plan_ctx)
            capability = result.capability
            if params is None:
                params = result.params

            # M11.6: Prompt enhancement (только для generation capabilities)
            if (
                self.prompt_builder is not None
                and capability in self.GENERATION_CAPABILITIES
                and params is not None
                and "prompt" in params
            ):
                from app.prompt import PromptContext
                prompt_ctx = PromptContext(
                    original_text=params["prompt"],
                    mode="completion",
                    capability=capability,
                    active_asset_type=plan_ctx.active_asset_type if plan_ctx else None,
                    previous_prompt=ctx.parameters.get("prompt") if ctx.parameters else None,
                )
                prompt_result = self.prompt_builder.build(prompt_ctx)
                if prompt_result.original_preserved and prompt_result.enhanced_prompt:
                    params["prompt"] = prompt_result.enhanced_prompt
                    ctx.parameters["original_prompt"] = prompt_result.original_prompt or params.get("prompt")
                    ctx.parameters["prompt_source"] = prompt_result.source

        if capability is None:
            raise AgentError("turn требует capability или request")
        params = params or {}

        # 2) выбор workflow (media-agnostic, тот же Agent.prepare)
        manifest, plan, provider = self.prepare(
            capability, params, provider=provider, backend_id=backend_id, base_url=base_url
        )

        # 3) резолюция входных ассетов (explicit > active_asset > reference; AD-23)
        required_roles = {role: ain.kind for role, ain in manifest.asset_inputs.items()}
        bindings = self.resolve_asset_inputs(
            assets, context=ctx, store=self.store, as_ids=True, required_roles=required_roles
        )
        missing = [r for r in required_roles if r not in bindings]
        if missing:
            note = {
                "turn": request or capability,
                "capability": capability,
                "missing_inputs": missing,
                "reason": "не указан явно и нет совместимого active_asset",
            }
            ctx.unresolved.append(note)
            ctx.dialog_state = "awaiting_input"
            raise AgentError(
                f"capability {capability} требует входные ассеты для ролей {missing}, "
                f"но они не указаны и отсутствует совместимый active_asset"
            )

        plan.asset_bindings = bindings

        # 4) M13: retry loop
        last_job = None
        for attempt in range(1, max_attempts + 1):
            start_time = _time.monotonic()

            try:
                job = self.engine.execute(
                    manifest, plan, provider=provider,
                    ws_timeout=ws_timeout, on_progress=on_progress,
                )
            except Exception as e:
                # Ошибка execution — логируем, НО re-raise (M7 behavior)
                # active_asset НЕ заменяется при ошибке
                duration = _time.monotonic() - start_time
                error_class = classify_error(str(e))
                import uuid as _uuid
                job = Job(
                    prompt_id=str(_uuid.uuid4()),
                    workflow_id=manifest.id if manifest else "",
                    version=manifest.version if manifest else "",
                    capability=capability,
                    state=JobState.FAILED,
                    error=str(e),
                    error_class=error_class,
                    attempt=attempt,
                )
                record = ExecutionRecord.from_job(
                    job, params=params, duration=duration,
                    error_class=error_class, attempt=attempt,
                )
                self.execution_history.record(record)

                ctx.unresolved.append({"turn": request or capability, "error": str(e)})
                ctx.dialog_state = "error"
                raise  # M7: re-raise после логирования

            duration = _time.monotonic() - start_time
            job.attempt = attempt

            # M11.6: set prompt metadata on job (from context if available)
            if ctx.parameters.get("original_prompt"):
                job._original_prompt = ctx.parameters["original_prompt"]
                job._enhanced_prompt = params.get("prompt")
                job._prompt_source = ctx.parameters.get("prompt_source")

            # M14: semantic verification (только для успешных_JOB с output assets)
            if (
                self.semantic_verifier is not None
                and job.state.value == "SUCCESS"
                and job.output_assets
            ):
                output_asset = self.store.get(job.output_assets[0])
                if output_asset and output_asset.type in ("image", "video"):
                    semantic_result = self.semantic_verifier.verify(
                        request=request or capability,
                        output_path=output_asset.path,
                        capability=capability,
                    )
                    if not semantic_result.ok and semantic_result.error is None:
                        job.state = JobState.FAILED
                        job.error = f"semantic verification failed: score={semantic_result.score:.2f}"
                        job.error_class = "verification"

            # Записываем в execution history
            record = ExecutionRecord.from_job(
                job,
                params=params,
                duration=duration,
                error_class=job.error_class,
                attempt=attempt,
            )
            self.execution_history.record(record)
            last_job = job

            if job.state.value == "SUCCESS":
                # 5) успех → обновление контекста (active_asset = последний выходной Asset)
                ctx.active_task = capability
                ctx.active_workflow = f"{manifest.id}@{manifest.version}"
                ctx.active_job = job.prompt_id
                primary = job.output_assets[0] if job.output_assets else None
                if primary is not None:
                    ctx.active_asset = primary
                for aid in job.output_assets:
                    ctx.assets.add(aid)
                ctx.jobs.add(job.prompt_id)
                ctx.workflows.add(f"{manifest.id}@{manifest.version}")
                ctx.parameters = params
                ctx.messages.append({
                    "turn": request or capability,
                    "capability": capability,
                    "workflow": f"{manifest.id}@{manifest.version}",
                    "job": job.prompt_id,
                    "outputs": list(job.output_assets),
                    "active_asset": ctx.active_asset,
                    "attempt": attempt,
                })
                ctx.dialog_state = "idle"
                return job

            # Решение о retry
            decision = self.retry_policy.decide(
                state=job.state.value,
                attempt=attempt,
                error_class=job.error_class,
            )

            if decision.action == "retry":
                # SSE event: retry_started
                ctx.messages.append({
                    "type": "retry_started",
                    "attempt": attempt,
                    "max_attempts": max_attempts,
                    "reason": decision.reason,
                    "job": job.prompt_id,
                })
                # Ждём перед следующей попыткой
                if decision.delay > 0:
                    _time.sleep(decision.delay)
                continue
            else:
                # failed или accept — выходим
                break

        # Все попытки исчерпаны или permanent error
        job = last_job
        if job.state.value != "SUCCESS":
            ctx.unresolved.append({
                "turn": request or capability,
                "job": job.prompt_id,
                "state": job.state.value,
                "attempt": job.attempt,
            })
            ctx.dialog_state = "error"

        # SSE event: retry_completed (если были retry)
        if job.attempt > 1:
            ctx.messages.append({
                "type": "retry_completed",
                "attempt": job.attempt,
                "state": job.state.value,
                "job": job.prompt_id,
            })

        # M15: auto-save context after turn
        if self.session_manager is not None:
            self.session_manager.save(session_id, ctx)

        return job

    # --- M18: multi-step chain execution ---

    def _execute_chain(
        self,
        session_id: str,
        subtasks: list,
        params: Optional[dict] = None,
        assets: Optional[dict] = None,
        backend_id: str = "local_comfyui",
        provider=None,
        base_url: Optional[str] = None,
        ws_timeout: Optional[int] = None,
        on_progress=None,
        max_attempts: int = 1,
    ) -> Job:
        """Выполнить цепочку подзадач (M18).

        Возвращает Job последнего шага (или failed step).
        Каждый шаг использует output предыдущего шага как input.
        """
        from app.planner.decomposer import TaskDecomposer

        ctx = self.session(session_id)
        chain_ctx = ChainContext(session_id=session_id)

        # Если есть явные assets — передаём их в chain_ctx
        if assets:
            for role, spec in assets.items():
                if isinstance(spec, str):
                    # path — ingest в store
                    asset = self.store.ingest(spec, type="input", role="input")
                    chain_ctx.active_asset = asset.id
                elif isinstance(spec, dict) and "asset_id" in spec:
                    chain_ctx.active_asset = spec["asset_id"]

        chain = ExecutionChain(
            execute_fn=lambda subtask: self._execute_chain_step(
                subtask=subtask,
                chain_ctx=chain_ctx,
                backend_id=backend_id,
                provider=provider,
                base_url=base_url,
                ws_timeout=ws_timeout,
                on_progress=on_progress,
            ),
            history=self.execution_history,
            max_attempts_per_step=max_attempts,
            on_step_complete=lambda i, step: self._on_chain_step_complete(
                session_id, i, step, ctx, chain_ctx,
            ),
        )

        result = chain.execute(subtasks)

        # Обновляем контекст сессии
        if chain_ctx.active_asset:
            ctx.active_asset = chain_ctx.active_asset
        if chain_ctx.workflows_used:
            ctx.active_workflow = chain_ctx.workflows_used[-1]
        ctx.dialog_state = "idle" if result.ok else "error"

        # Возвращаем Job последнего завершённого шага
        last_step = result.steps[-1] if result.steps else None
        if last_step and last_step.job:
            return last_step.job

        # Если нет шагов — создаём dummy failed job
        return Job(
            prompt_id=str(_uuid.uuid4()),
            workflow_id="",
            version="",
            capability="chain",
            state=JobState.FAILED,
            error="empty chain",
        )

    def _execute_chain_step(
        self,
        subtask,
        chain_ctx: ChainContext,
        backend_id: str = "local_comfyui",
        provider=None,
        base_url: Optional[str] = None,
        ws_timeout: Optional[int] = None,
        on_progress=None,
    ) -> Job:
        """Выполнить один шаг цепочки с asset handoff.

        1. Определяем PlanContext с учётом текущего active_asset
        2. Планируем через HeuristicPlanner/AdaptivePlanner
        3. Резолюция входных assets
        4. Execute
        """
        # 1) PlanContext с учётом текущего состояния цепочки
        active_asset_obj = None
        if chain_ctx.active_asset:
            active_asset_obj = self.store.get(chain_ctx.active_asset)

        plan_ctx = PlanContext(
            active_asset_type=active_asset_obj.type if active_asset_obj else None,
            capabilities=tuple(self.capabilities()),
            active_workflow=chain_ctx.workflows_used[-1] if chain_ctx.workflows_used else None,
        )

        # 2) Planner (HeuristicPlanner/AdaptivePlanner)
        planner = self.planner or _default_planner()
        if self._adaptive_planner_enabled and self.execution_history is not None:
            from app.planner.adaptive import AdaptivePlanner, MIN_SUCCESSFUL_PER_CAPABILITY
            base_result = planner.plan(subtask.description, context=plan_ctx)
            success_count = len(self.execution_history.get_successful(base_result.capability))
            if success_count >= MIN_SUCCESSFUL_PER_CAPABILITY:
                if not isinstance(planner, AdaptivePlanner):
                    planner = AdaptivePlanner(
                        history=self.execution_history,
                        fallback=self.planner or _default_planner(),
                    )

        result = planner.plan(subtask.description, context=plan_ctx)
        capability = result.capability
        merged_params = {**subtask.params, **result.params}

        # 3) Подготовка (manifest, plan, provider)
        manifest, plan, provider_obj = self.prepare(
            capability, merged_params, provider=provider, backend_id=backend_id, base_url=base_url,
        )

        # 4) Резолюция входных assets
        input_assets = {}
        if chain_ctx.active_asset:
            # Определяем role для входного asset
            required_roles = {role: ain.kind for role, ain in manifest.asset_inputs.items()}
            for role, kind in required_roles.items():
                if active_asset_obj and active_asset_obj.type == kind:
                    input_assets[role] = {"asset_id": chain_ctx.active_asset}
                    break

        bindings = self.resolve_asset_inputs(
            input_assets, context=None, store=self.store, as_ids=True,
            required_roles={role: ain.kind for role, ain in manifest.asset_inputs.items()},
        )
        plan.asset_bindings = bindings

        # 5) Execute
        job = self.engine.execute(
            manifest, plan, provider=provider_obj,
            ws_timeout=ws_timeout, on_progress=on_progress,
        )
        return job

    def _on_chain_step_complete(
        self,
        session_id: str,
        index: int,
        step,
        ctx,
        chain_ctx: ChainContext,
    ) -> None:
        """Callback при завершении шага цепочки."""
        if step.state == ChainState.COMPLETED and step.job:
            # Обновляем chain_ctx
            if step.job.output_assets:
                chain_ctx.active_asset = step.job.output_assets[0]
            if step.job.workflow_id:
                chain_ctx.workflows_used.append(
                    f"{step.job.workflow_id}@{step.job.version}"
                )

            # Обновляем ConversationContext
            for aid in step.job.output_assets:
                ctx.assets.add(aid)
            ctx.jobs.add(step.job.prompt_id)
            if step.job.workflow_id:
                ctx.workflows.add(f"{step.job.workflow_id}@{step.job.version}")

            # Записываем в messages
            ctx.messages.append({
                "type": "chain_step",
                "step": index,
                "capability": step.subtask.capability,
                "job": step.job.prompt_id,
                "outputs": list(step.job.output_assets),
                "state": step.state.value,
            })


def _default_planner():
    from app.planner import HeuristicPlanner
    return HeuristicPlanner()
