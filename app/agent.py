"""Agent — слой оркестрации (главная задача проекта).

Связывает готовые куски M1–M5 (WorkflowRegistry + ModelRegistry + WorkflowEngine +
Provider + AssetStore) в единый вызов. Media-agnostic: Agent НЕ ветвится по
media-типу — он принимает capability (image.generate / video.generate / audio.generate / …)
и params и исполняет его тем же путём для любого media. Это тот слой, которого
не хватало M1–M5 (HANDOFF: «Ни Agent/LLM/UI не добавлено»).

Поток (media-agnostic):
    capability + params
      → WorkflowRegistry.discover / by_capability / select   (выбор workflow)
      → ModelRegistry.discover (per-backend, опц.)            (точные имена моделей)
      → ExecutionPlan                                       (логич. параметры)
      → WorkflowEngine.execute                               (upload→bind→POST→WS/history→Asset→Verifier)
      → Job (с output Asset'ами в local AssetStore)
"""
from __future__ import annotations

import os
from typing import Any, Optional

from app.assets.store import AssetStore
from app.engine import ExecutionPlan, Job, JobState, WorkflowEngine
from app.engine.history import ExecutionHistory, ExecutionRecord
from app.engine.retry import RetryPolicy, classify_error
from app.engine.semantic_verifier import SemanticVerifier, SemanticVerificationResult
from app.planner import HeuristicPlanner, PlanResult, Planner
from app.provider.comfyui import ComfyUIProvider
from app.registry.backends import BackendCatalog, BackendSpec
from app.registry.model import ModelKind, ModelRegistry
from app.registry.registry import WorkflowRegistry
from app.registry.runtime import RuntimeInfo, discover_runtime


DEFAULT_WORKFLOWS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "workflows"
)


class AgentError(RuntimeError):
    """Ошибка оркестрации Agent (capability не найден, ничего не выбрано и т.п.)."""


def _build_provider(backend_id: str, base_url: Optional[str] = None) -> ComfyUIProvider:
    """Собрать ComfyUIProvider из base_url (env COMFY_REMOTE_URL / COMFY_URL)."""
    from app.comfy.client import ComfyClient

    url = base_url or os.environ.get("COMFY_REMOTE_URL") or os.environ.get("COMFY_URL")
    if not url:
        raise AgentError(
            "не задан ComfyUI endpoint: передайте base_url или env COMFY_REMOTE_URL/COMFY_URL"
        )
    return ComfyUIProvider(ComfyClient(base_url=url), backend_id=backend_id)


class Agent:
    """Media-agnostic оркестратор генерации через ComfyUI.

    Не содержит if image/elif video/elif audio — весь media-specific спрятан в
    workflow.json + manifest.json (Registry) и WorkflowEngine.
    """

    # Capability, для которых требуется enhancement промпта (M11.6)
    GENERATION_CAPABILITIES = {"image.generate", "video.generate", "audio.generate"}

    def __init__(
        self,
        asset_store: AssetStore,
        model_registry: Optional[ModelRegistry] = None,
        workflows_dir: str = DEFAULT_WORKFLOWS_DIR,
        backends: Optional[BackendCatalog] = None,
        planner: Optional[Planner] = None,
        prompt_builder=None,  # M11.6: CompositePromptBuilder или None
        execution_history: Optional[ExecutionHistory] = None,  # M13
        retry_policy: Optional[RetryPolicy] = None,  # M13
        semantic_verifier: Optional[SemanticVerifier] = None,  # M14
        adaptive_planner: Optional[Planner] = None,  # M16: context-aware adaptive
        gateway=None,  # M21: optional ClusterGateway for dispatch tracking
        reconciler=None,  # M21: optional Reconciler for recovery
        feedback_store=None,  # M24.1: хранилище feedback для RetryPolicy
    ) -> None:
        self.store = asset_store
        self.model_registry = model_registry
        self.backends = backends
        self.planner = planner
        self.prompt_builder = prompt_builder  # M11.6
        self.registry = WorkflowRegistry()
        self.registry.discover(workflows_dir)
        self.engine = WorkflowEngine(asset_store, model_registry=model_registry)
        # M13: execution history и retry policy
        self.execution_history = execution_history or ExecutionHistory()
        self.retry_policy = retry_policy or RetryPolicy()
        # M14: semantic verification (vision model)
        self.semantic_verifier = semantic_verifier
        # M16: adaptive planner (context-aware, AD-36)
        self.adaptive_planner = adaptive_planner
        # M21: Gateway и Reconciler для reconciliation & recovery
        self.gateway = gateway
        self.reconciler = reconciler
        # M24.1: FeedbackStore для failure-time feedback
        self.feedback_store = feedback_store

    # --- discovery (media-agnostic) ---

    def capabilities(self) -> list[str]:
        """Все известные capability (image.generate, video.generate, audio.generate, …)."""
        return sorted({wf.capability for wf in self.registry.workflows if wf.capability})

    def _select_manifest(
        self,
        capability: str,
        runtime: Optional[RuntimeInfo],
        models: set,
        custom_nodes: set,
    ):
        # Честный выбор по совместимости (если есть runtime). None → fallback ниже.
        sel = None
        if runtime is not None:
            sel = self.registry.select(
                capability, runtime, models=models, custom_nodes=custom_nodes
            )
        if sel:
            return self.registry.get(sel.workflow_id, sel.version)
        candidates = self.registry.by_capability(capability)
        if not candidates:
            raise AgentError(f"capability не найден: {capability}")
        # fallback: первый VALIDATED/AVAILABLE (исполнимый), иначе первый.
        for c in candidates:
            if c.status.value in ("VALIDATED", "AVAILABLE"):
                return c
        return candidates[0]

    # --- подготовка (без исполнения) — для инспекции/тестов ---

    def prepare(
        self,
        capability: str,
        params: Optional[dict] = None,
        asset_paths: Optional[dict] = None,
        backend_id: str = "local_comfyui",
        provider: Optional[ComfyUIProvider] = None,
        base_url: Optional[str] = None,
    ):
        """Собрать (manifest, plan, provider) без запуска графа.

        asset_paths: {role: локальный_путь} — входные ассеты (ингестятся в AssetStore).
        """
        if provider is None:
            if self.backends is not None:
                spec = self.backends.choose(capability, self.registry)
                if spec is not None:
                    provider = _build_provider(spec.backend_id, base_url=spec.base_url)
            if provider is None:
                provider = _build_provider(backend_id, base_url=base_url)

        runtime: Optional[RuntimeInfo] = None
        models: set = {"checkpoint"}
        custom_nodes: set = set()
        try:
            runtime = discover_runtime(provider.client)
            if self.model_registry is not None:
                self.model_registry.discover(
                    provider.client, backend_id, kinds=[ModelKind.CHECKPOINT]
                )
                models |= set(self.model_registry.models_for(backend_id))
        except Exception:
            # окруженческая недоступность ComfyUI — продолжаем без runtime-фильтрации
            runtime = None

        manifest = self._select_manifest(capability, runtime, models, custom_nodes)

        asset_bindings: dict = {}
        if asset_paths:
            for role, path in asset_paths.items():
                asset = self.store.ingest(path, type="input", role="input")
                asset_bindings[role] = asset.id

        plan = ExecutionPlan(
            capability=capability,
            workflow_id=manifest.id,
            version=manifest.version,
            params=params or {},
            asset_bindings=asset_bindings,
        )
        return manifest, plan, provider

    # --- исполнение (media-agnostic) ---

    def run(
        self,
        capability: str,
        params: Optional[dict] = None,
        asset_paths: Optional[dict] = None,
        backend_id: str = "local_comfyui",
        provider: Optional[ComfyUIProvider] = None,
        base_url: Optional[str] = None,
        ws_timeout: Optional[int] = None,
        gateway=None,  # M21
        history=None,  # M21
    ) -> Job:
        """Полный media-agnostic путь: capability → Job с output-ассетами.

        M21: gateway и history для dispatch tracking и reconciliation.
        """
        manifest, plan, provider = self.prepare(
            capability, params, asset_paths, backend_id, provider, base_url
        )
        return self.engine.execute(
            manifest, plan, provider=provider, ws_timeout=ws_timeout,
            gateway=gateway or self.gateway,
            history=history or self.execution_history,
        )

    # --- natural-language вход (planner) ---

    def generate(
        self,
        request: str,
        asset_paths: Optional[dict] = None,
        backend_id: str = "local_comfyui",
        provider: Optional[ComfyUIProvider] = None,
        base_url: Optional[str] = None,
        ws_timeout: Optional[int] = None,
        max_attempts: int = 1,  # M13: количество попыток (1 = без retry)
    ) -> Job:
        """Natural-language генерация: planner(request) → (capability, params) → run().

        M13: поддержка retry loop. max_attempts > 1 включает повтор при FAILED.
        planner берётся из self.planner или HeuristicPlanner (офлайн по умолчанию).
        M11.6: если задан prompt_builder, enhances prompt для generation capabilities.
        """
        planner = self.planner or HeuristicPlanner()
        result: PlanResult = planner.plan(request)
        
        # M11.6: Prompt enhancement (только для generation capabilities)
        original_prompt = None
        enhanced_prompt = None
        prompt_source = None
        if (
            self.prompt_builder is not None
            and result.capability in self.GENERATION_CAPABILITIES
            and "prompt" in result.params
        ):
            from app.prompt import PromptContext
            ctx = PromptContext(
                original_text=result.params["prompt"],
                mode="completion",
                capability=result.capability,
            )
            prompt_result = self.prompt_builder.build(ctx)
            original_prompt = prompt_result.original_prompt or result.params["prompt"]
            enhanced_prompt = prompt_result.enhanced_prompt
            prompt_source = prompt_result.source
            # AD-32: не заменяем prompt если original_preserved=False
            if prompt_result.original_preserved and enhanced_prompt:
                result = PlanResult(
                    capability=result.capability,
                    params={**result.params, "prompt": enhanced_prompt},
                    rationale=result.rationale,
                )

        # M13: retry loop
        last_job = None
        current_params = dict(result.params)  # копия для возможной корректировки
        for attempt in range(1, max_attempts + 1):
            import time as _time
            start_time = _time.monotonic()

            try:
                job = self.run(
                    result.capability,
                    params=current_params,
                    asset_paths=asset_paths,
                    backend_id=backend_id,
                    provider=provider,
                    base_url=base_url,
                    ws_timeout=ws_timeout,
                    gateway=self.gateway,  # M21
                    history=self.execution_history,  # M21
                )
            except Exception as e:
                # Ошибка execution — создаём failed Job для diagnostic
                import uuid as _uuid
                job = Job(
                    prompt_id=str(_uuid.uuid4()),
                    workflow_id="",
                    version="",
                    capability=result.capability,
                    state=JobState.FAILED,
                    error=str(e),
                    error_class=classify_error(str(e)),
                    attempt=attempt,
                )

            duration = _time.monotonic() - start_time
            job.attempt = attempt

            # Сохраняем prompt metadata в job
            if original_prompt or enhanced_prompt:
                job._original_prompt = original_prompt
                job._enhanced_prompt = enhanced_prompt
                job._prompt_source = prompt_source

            # M14: semantic verification (только для успешных_JOB с output assets)
            semantic_result = None
            if (
                self.semantic_verifier is not None
                and job.state.value == "SUCCESS"
                and job.output_assets
            ):
                output_asset = self.store.get(job.output_assets[0])
                if output_asset and output_asset.type in ("image", "video"):
                    semantic_result = self.semantic_verifier.verify(
                        request=request,
                        output_path=output_asset.path,
                        capability=result.capability,
                    )
                    # Если score низкий — помечаем как verification error для retry
                    if not semantic_result.ok and semantic_result.error is None:
                        job.state = JobState.FAILED
                        job.error = f"semantic verification failed: score={semantic_result.score:.2f}"
                        job.error_class = "verification"

            # Записываем в execution history — M23: corrections_applied
            record = ExecutionRecord.from_job(
                job,
                params=current_params,
                duration=duration,
                error_class=job.error_class,
                attempt=attempt,
                corrections_applied=getattr(last_job, '_applied_corrections', None),
            )
            self.execution_history.record(record)
            last_job = job

            # Решение о retry — M23: передаём params и semantic_score для корректировки
            semantic_score = None
            if semantic_result is not None and not semantic_result.error:
                semantic_score = semantic_result.score

            decision = self.retry_policy.decide(
                state=job.state.value,
                attempt=attempt,
                error_class=job.error_class,
                current_params=current_params,
                semantic_score=semantic_score,
                prompt_id=job.prompt_id,  # M24: для feedback lookup
                feedback_store=self.feedback_store,  # M24.1: feedback store
            )

            # M23: сохраняем applied corrections для следующей записи
            applied_corrections = None
            if decision.param_adjustments:
                applied_corrections = [{
                    "error_class": job.error_class,
                    "from_params": {k: current_params.get(k) for k in decision.param_adjustments},
                    "to_params": decision.param_adjustments,
                }]
            job._applied_corrections = applied_corrections

            if decision.action == "accept":
                return job
            elif decision.action == "retry":
                # M23: param_adjustments от стратегии (приоритет) > semantic suggested_params
                if decision.param_adjustments and attempt < max_attempts:
                    current_params = {**current_params, **decision.param_adjustments}
                elif (
                    semantic_result is not None
                    and semantic_result.suggested_params
                    and attempt < max_attempts
                ):
                    current_params = {**current_params, **semantic_result.suggested_params}
                # Ждём перед следующей попыткой
                if decision.delay > 0:
                    import time as _time
                    _time.sleep(decision.delay)
                continue
            elif decision.action == "ask_user":  # M24: feedback-driven
                job._decision_action = "ask_user"
                job._decision_reason = decision.reason
                job._decision_suggestions = decision.suggestions
                return job
            else:  # failed — M22: обогащаем job контекстом решения
                job._decision_reason = decision.reason
                job._decision_suggestions = decision.suggestions
                return job

        # Все попытки исчерпаны — M22: обогащаем контекстом
        if last_job is not None and last_job._decision_reason is None:
            last_job._decision_reason = "all attempts exhausted"
            last_job._decision_suggestions = [
                "попробуйте изменить промпт",
                "уменьшите сложность запроса",
            ]
        return last_job

    # --- входные ассеты (path / base64 / active_asset / reference) ---

    @staticmethod
    def resolve_asset_inputs(
        assets: Any = None,
        context: Any = None,
        store: Any = None,
        as_ids: bool = False,
        required_roles: Optional[dict] = None,
    ) -> dict:
        """Нормализовать входные ассеты в role → path (as_ids=False) или role → asset_id (as_ids=True).

        Приоритет резолюции (ref: AD-23, Conversation Model §15):
          1) явно указанный пользователем Asset/path (assets[role]);
          2) иначе context.active_asset — если его тип совпадает с required_roles[role].kind
             (без resize/conversion/transcoding);
          3) иначе явная ссылка на предыдущий Asset/turn
             (assets[role] = {"asset_id": id} / {"reference": id}).

        Роли, не разрешённые ни одним способом, отсутствуют в результате.
        Обратная совместимость: вызов без context/store/as_ids эквивалентен старому
        поведению (role → path для явного path/base64).
        """
        out: dict = {}
        assets = assets or {}
        required_roles = required_roles or {}

        # сначала роли, требуемые workflow (explicit > active_asset > reference)
        for role, kind in required_roles.items():
            spec = assets.get(role)
            if spec is not None:
                # M25: list support для multi-asset roles
                if isinstance(spec, list):
                    resolved = []
                    for item in spec:
                        resolved.append(_resolve_one(item, role, kind, store, as_ids))
                    out[role] = resolved
                else:
                    out[role] = _resolve_one(spec, role, kind, store, as_ids)
                continue
            if context is not None and getattr(context, "active_asset", None):
                active = store.get(context.active_asset) if store else None
                if active is not None and active.type == kind:
                    out[role] = (active.id if as_ids else active.path)
                    continue

        # внештатные явные роли (не в required_roles) — тоже разрешаем
        for role, spec in assets.items():
            if role in out:
                continue
            # M25: list support для multi-asset roles
            if isinstance(spec, list):
                resolved = []
                for item in spec:
                    resolved.append(_resolve_one(item, role, required_roles.get(role), store, as_ids))
                out[role] = resolved
            else:
                out[role] = _resolve_one(spec, role, required_roles.get(role), store, as_ids)
        return out


def _resolve_one(spec: Any, role: str, kind: Optional[str], store: Any, as_ids: bool) -> str:
    """Разрешить один явный входной ассет в path (as_ids=False) или asset_id (as_ids=True)."""
    import base64
    import os
    import tempfile
    from pathlib import Path

    if isinstance(spec, str):
        path = spec
    elif isinstance(spec, dict):
        if "asset_id" in spec or "reference" in spec:
            # явная ссылка на предыдущий Asset/turn (AD-23, §15) — без LLM-FS-доступа
            aid = spec.get("asset_id") or spec.get("reference")
            asset = store.get(aid) if store else None
            if asset is None:
                raise AgentError(f"asset '{role}': ссылка {aid} не найдена в store")
            return asset.id if as_ids else asset.path
        if "path" in spec:
            path = spec["path"]
        elif "data" in spec:
            name = spec.get("name", f"{role}.bin")
            suffix = Path(name).suffix or ".bin"
            fd, p = tempfile.mkstemp(suffix=suffix)
            with os.fdopen(fd, "wb") as f:
                f.write(base64.b64decode(spec["data"]))
            path = p
        else:
            raise AgentError(f"asset '{role}': нужны 'path' / 'data' / 'asset_id' / 'reference'")
    else:
        raise AgentError(f"asset '{role}': неверный формат")

    if as_ids:
        if store is None:
            raise AgentError(f"asset '{role}': для as_ids требуется store")
        asset = store.ingest(path, type=kind or "input", role="input")
        return asset.id
    return path
