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
from app.registry.discovery import (
    DiscoveryFacts,
    checkpoints_from_node_schema_store,
    custom_nodes_from_node_schema_store,
)
from app.registry.model import ModelKind, ModelRegistry
from app.registry.registry import WorkflowRegistry
from app.registry.runtime import RuntimeInfo, discover_runtime
from app.registry.workflow import (
    ModelRequirement,
    UnknownReason,
    UnavailableReason,
    Workflow,
    WorkflowStatus,
)


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


def _has_runtime_dependent_requirements(workflow: Workflow) -> bool:
    """Совместимость workflow зависит от runtime-сведений?

    AD-18: если runtime неизвестен (None), workflow с runtime-dependent
    требованиями НЕ может быть подтверждён как AVAILABLE. Сюда входят:
      - accelerator, отличный от "any";
      - fp16 == True;
      - min_vram_gb > 0;
      - min_comfyui_version вне ("", "0.0.0") (уже после semver-парсинга).
    """
    req = workflow.requirements
    if req.get("accelerator") and req.get("accelerator") != "any":
        return True
    if req.get("fp16") is True:
        return True
    if (req.get("min_vram_gb") or 0) > 0:
        return True
    mcv = workflow.min_comfyui_version
    if mcv and mcv not in ("", "0.0.0"):
        return True
    return False


def _resolve_model_requirements(
    reqs: list[ModelRequirement],
    models: set | None = None,
    model_registry: Optional[ModelRegistry] = None,
    backend_id: Optional[str] = None,
    user_preference: Optional[str] = None,
) -> dict[str, str]:
    """Разрешить typed model requirements в concrete model bindings (AD-MODEL-BINDING-001).

    Возвращает {role_or_identity: concrete_model_name}, например
    {"checkpoint": "cyberrealistic_v80.safetensors"}.

    Определения:
      - kind requirement: role (например "checkpoint") → точное имя модели backend'а;
      - identity requirement: точное имя (identity) → binding["<identity>"] = identity.

    Детерминированность: при нескольких кандидатах берётся первый алфавитно.
    user_preference переопределяет выбор для kind requirement, если модель
    присутствует в catalog'е нужного вида (identity requirements не трогаем).
    """
    from app.registry.model import ModelKind

    models = models or set()
    bindings: dict[str, str] = {}
    for req in reqs:
        if req.identity is not None:
            if req.identity in models:
                bindings[req.identity] = req.identity
            # absent identity — пропускаем (downstream увидит MISSING_MODEL в compatibility)
            continue
        # kind requirement
        key = req.kind.value if req.kind is not None else "model"
        candidates: list[str] = []
        if model_registry is not None and backend_id is not None:
            for name, info in model_registry._catalog.get(backend_id, {}).items():
                if name in models and info.kind == req.kind:
                    candidates.append(name)
            candidates = sorted(set(candidates))
        else:
            candidates = sorted(models, key=str)
        if not candidates:
            continue  # пропускаем при пустых models (downstream MISSING_MODEL)
        if user_preference and user_preference in candidates:
            bindings[key] = user_preference
        else:
            bindings[key] = candidates[0]
    return bindings


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
        runtime_validator=None,  # S4: валидатор нод на реальном ComfyUI
        knowledge_core=None,  # S0.5: optional KnowledgeCore for pre-flight advisory
    ) -> None:
        self.store = asset_store
        self.model_registry = model_registry
        self.backends = backends
        self.planner = planner
        self.prompt_builder = prompt_builder  # M11.6
        # S4: RuntimeValidator и кэш валидированных нод (node_class -> success bool)
        self.runtime_validator = runtime_validator
        self._validated_nodes: dict[str, bool] = {}
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
        # S0.5: KnowledgeCore для pre-flight advisory (read-only, non-blocking)
        self.knowledge_core = knowledge_core

    # --- discovery (media-agnostic) ---

    def _discover_facts(
        self, client, backend_id: str
    ) -> DiscoveryFacts:
        """Extended Discovery (Step 7): собрать факты о runtime, моделях, custom nodes.

        Словарь-инвентарь моделей и custom nodes с graceful degradation:
        если live-источник недоступен — кэш NodeSchemaStore (models_available /
        custom_nodes_available остаётся False). AD-18: cache ≠ live.
        """
        from app.comfy.client import ComfyClient

        runtime: Optional[RuntimeInfo] = None
        runtime_available = False
        try:
            runtime = discover_runtime(client)
            runtime_available = True
        except Exception:
            runtime = None

        models: set[str] = set()
        models_available = False
        try:
            if self.model_registry is not None:
                self.model_registry.discover(client, backend_id)
                names = set(self.model_registry.models_for(backend_id))
            else:
                names = set(client.discover_checkpoints() or [])
            if names:
                models = names
                models_available = True
            else:
                # Live вернул [] — knowledge gap, подставляем cache.
                # models_available остаётся False (cache ≠ live).
                cached = checkpoints_from_node_schema_store()
                if cached:
                    models = cached
        except Exception:
            cached = checkpoints_from_node_schema_store()
            if cached:
                models = cached

        custom_nodes: dict[str, set[str]] = {}
        custom_nodes_available = False
        try:
            inventory = ComfyClient.discover_custom_node_packages(client)
            custom_nodes = inventory or {}
            # Live success — даже если empty, это реальность, не cache.
            custom_nodes_available = True
        except Exception:
            cached = custom_nodes_from_node_schema_store()
            if cached:
                custom_nodes = cached

        return DiscoveryFacts(
            runtime=runtime,
            runtime_available=runtime_available,
            models=models,
            models_available=models_available,
            custom_nodes=custom_nodes,
            custom_nodes_available=custom_nodes_available,
        )

    def _compatibility_from_known(
        self,
        workflow: Workflow,
        runtime: Optional[RuntimeInfo],
        models: set,
        custom_nodes: set,
    ) -> tuple[WorkflowStatus, list]:
        """Подтвердить совместимость workflow исходя из known-данных (AD-18).

        В отличие от evaluate_compatibility (полный контракт с runtime), здесь
        runtime может быть None (неизвестен). Если у workflow есть runtime-dependent
        требования и runtime==None — это UNKNOWN, а НЕ AVAILABLE (AD-18 инвариант).
        Проверяем так же declarative требования (models/custom_nodes) до runtime-branch.
        """
        # declared_only никогда не исполним (даже offline)
        if workflow.declared_only:
            return WorkflowStatus.DECLARED_ONLY, []

        # манифест/граф уже невалидны
        if (
            UnavailableReason.INVALID_MANIFEST in workflow.reasons
            or UnavailableReason.INVALID_WORKFLOW in workflow.reasons
        ):
            return WorkflowStatus.UNAVAILABLE, list(workflow.reasons)

        # --- declarative requirements (проверяем ДО runtime-branch, AD-18 Case B) ---
        model_reqs = list(getattr(workflow, "model_requirements", None) or [])
        if model_reqs:
            # Typed ModelRequirement: kind (any model of kind) / identity (exact name)
            if not models:
                return WorkflowStatus.UNAVAILABLE, [UnavailableReason.MISSING_MODEL]
            for mr in model_reqs:
                if mr.identity is not None and mr.identity not in models:
                    return WorkflowStatus.UNAVAILABLE, [UnavailableReason.MISSING_MODEL]
                elif mr.kind is not None and not models:
                    return WorkflowStatus.UNAVAILABLE, [UnavailableReason.MISSING_MODEL]
        elif workflow.required_models:
            # Legacy: точное совпадение имён (backward-compat, как в compatibility.py)
            if not models:
                return WorkflowStatus.UNAVAILABLE, [UnavailableReason.MISSING_MODEL]
            for m in workflow.required_models:
                if m not in models:
                    return WorkflowStatus.UNAVAILABLE, [UnavailableReason.MISSING_MODEL]

        if workflow.required_custom_nodes:
            from app.registry.discovery import _custom_node_names

            names = _custom_node_names(custom_nodes)
            if not names:
                return WorkflowStatus.UNAVAILABLE, [UnavailableReason.MISSING_CUSTOM_NODE]
            for c in workflow.required_custom_nodes:
                if c not in names:
                    return WorkflowStatus.UNAVAILABLE, [UnavailableReason.MISSING_CUSTOM_NODE]

        # --- runtime-dependent branch (AD-18) ---
        if runtime is None:
            if _has_runtime_dependent_requirements(workflow):
                return WorkflowStatus.UNKNOWN, [UnknownReason.UNKNOWN_RUNTIME]
            return WorkflowStatus.AVAILABLE, []

        # runtime present — полная проверка контракта
        from app.registry.compatibility import evaluate_compatibility

        return evaluate_compatibility(
            workflow, runtime, models=models, custom_nodes=custom_nodes
        )

    def _calculate_validation_score(self, workflow: "Workflow") -> int:
        """Кол-во валидированных нод в workflow (S4).

        Каждая нода workflow["nodes"][*]["type"] считается если в
        self._validated_nodes[type] == True. Для MagicMock-совместимости
        (тесты S4) допускаем workflow-объекты, у которых есть атрибут .workflow.
        """
        nodes = getattr(workflow, "workflow", None)
        if not nodes:
            return 0
        node_list = nodes.get("nodes") if isinstance(nodes, dict) else None
        if not node_list:
            return 0
        score = 0
        for node in node_list:
            if not isinstance(node, dict):
                continue
            cls = node.get("type")
            if cls and self._validated_nodes.get(cls) is True:
                score += 1
        return score

    def _select_manifest(
        self,
        capability: str,
        runtime: Optional[RuntimeInfo],
        models: set,
        custom_nodes: set,
    ):
        """Строгий выбор workflow (AD-18 + S4): по by_capability + совместимости.

        Falls back НЕ происходит молча: кандидат выбирается только если его
        совместимость ПОДТВЕРЖДЕНА (AVAILABLE) через _compatibility_from_known.
        При runtime=None workflow с runtime-dependent требованиями → UNKNOWN и
        НЕ выбирается. Если ни один кандидат не подтверждён — AgentError.
        """
        candidates = self.registry.by_capability(capability)
        if not candidates:
            raise AgentError(f"capability не найден: {capability}")

        # Оцениваем каждого кандидата и выбираем подтверждённые (AVAILABLE).
        confirmed: list[Workflow] = []
        for c in candidates:
            if getattr(c, "declared_only", False):
                c.status = WorkflowStatus.DECLARED_ONLY
                c.reasons = []
                continue
            try:
                wf = self.registry.get(c.id, c.version) or c
            except Exception:
                wf = c
            status, reasons = self._compatibility_from_known(wf, runtime, models, custom_nodes)
            c.status = status
            c.reasons = reasons
            if status == WorkflowStatus.AVAILABLE:
                confirmed.append(c)

        if not confirmed:
            raise AgentError("нет workflow с подтверждённой совместимостью")

        # S4: приоритет валидированным workflow (validated-score desc) ПЕРВЫМ,
        # затем priority desc, min_vram_gb asc, id, версия (детерминированный tie-break).
        ranked = sorted(
            confirmed,
            key=lambda w: (
                -self._calculate_validation_score(
                    self.registry.get(w.id, w.version) or w
                ),
                getattr(w, "priority", 0) * -1,
                ((w.requirements or {}).get("min_vram_gb") or 0),
                getattr(w, "id", ""),
                getattr(w, "version", ""),
            ),
        )
        chosen = ranked[0]
        return self.registry.get(chosen.id, chosen.version) or chosen

    # --- discovery (media-agnostic) ---

    def capabilities(self) -> list[str]:
        """Все известные capability (image.generate, video.generate, audio.generate, …)."""
        return sorted({wf.capability for wf in self.registry.workflows if wf.capability})

    # --- S4: validated nodes cache ---

    def get_validated_nodes(self) -> dict[str, bool]:
        """Вернуть кэш валидированных нод (node_class -> True/False)."""
        return dict(self._validated_nodes)

    def _validate_capability_nodes_background(self, capability: str) -> None:
        """S4: фоновая runtime-валидация нод workflow кандидатов capability.

        Запускает daemon-поток: для каждого workflow в capability вызывает
        runtime_validator.validate_node(node_type) и обновляет _validated_nodes.
        Пропускается если runtime_validator не задан или нет валидатора.
        """
        validator = self.runtime_validator
        if validator is None:
            return
        import threading as _threading

        from app.knowledge.runtime_validator import RuntimeValidator, ValidationResult

        def _run():
            for cand in self.registry.by_capability(capability):
                wf_id = getattr(cand, "workflow_id", None) or getattr(cand, "id", None)
                ver = getattr(cand, "version", None)
                if not wf_id:
                    continue
                try:
                    wf = self.registry.get(wf_id, ver)
                except Exception:
                    wf = None
                if wf is None:
                    continue
                nodes_data = getattr(wf, "workflow", None)
                if not isinstance(nodes_data, dict):
                    continue
                node_list = nodes_data.get("nodes")
                if not isinstance(node_list, list):
                    continue
                for node in node_list:
                    node_type = node.get("type") if isinstance(node, dict) else None
                    if not node_type:
                        continue
                    try:
                        evidence = validator.validate_node(node_type)
                        ok = getattr(evidence, "validation_result", None) == ValidationResult.SUCCESS
                        self._validated_nodes[node_type] = bool(ok)
                    except Exception:
                        self._validated_nodes[node_type] = False

        _threading.Thread(target=_run, daemon=True).start()

    # --- S0.5: Knowledge pre-flight (advisory, non-blocking) ---

    def _plan_result_to_query(
        self,
        result: PlanResult,
        manifest: Optional[Workflow] = None,
    ) -> Optional["KnowledgeQuery"]:
        """Адаптер PlanResult+Workflow → KnowledgeQuery.

        Возвращает None если knowledge_core не задан или capability пустая.
        """
        if self.knowledge_core is None:
            return None
        if not result.capability:
            return None

        from app.knowledge.core import KnowledgeQuery

        # media_input из manifest asset_inputs
        if manifest is not None:
            asset_inputs = getattr(manifest, "asset_inputs", None) or {}
            media_input = tuple(sorted({ain.kind for ain in asset_inputs.values()})) if asset_inputs else ()
            cardinality = len(asset_inputs)
        else:
            media_input = ()
            cardinality = 0

        # media_output из capability_registry или heuristic parse
        media_output = self._infer_media_output(result.capability)

        task_description = result.params.get("prompt", "") if result.params else ""

        return KnowledgeQuery(
            required_operation=result.capability,
            required_media_input=media_input,
            required_media_output=media_output,
            input_cardinality=cardinality,
            task_description=task_description,
        )

    def _infer_media_output(self, capability: str) -> str:
        """Infer media output type from capability name or CapabilityRegistry."""
        # Try CapabilityRegistry first
        try:
            from app.registry.capability import CapabilityRegistry
            cr = CapabilityRegistry()
            cap = cr.get(capability)
            if cap is not None and getattr(cap, "media_output", None):
                return cap.media_output
        except Exception:
            pass
        # Heuristic: "image.generate" → "image", "video.image_to_video" → "video"
        if "." in capability:
            prefix = capability.split(".")[0]
            if prefix in ("image", "video", "audio", "text"):
                return prefix
        return ""

    def _knowledge_preflight(
        self,
        capability: str,
        manifest: Optional[Workflow] = None,
        result: Optional[PlanResult] = None,
    ) -> Optional[dict]:
        """S0.5: Knowledge pre-flight query. Advisory only, non-blocking.

        Returns dict with 'readiness' (str) and 'gaps' (list[str]),
        or None if knowledge_core not available or query failed.
        """
        if self.knowledge_core is None:
            return None

        plan_result = result or PlanResult(capability=capability)
        query = self._plan_result_to_query(plan_result, manifest)
        if query is None:
            return None

        try:
            response = self.knowledge_core.query(query)
            return {
                "readiness": response.readiness.value,
                "gaps": [g.needed for g in response.gaps] if response.gaps else [],
            }
        except Exception:
            return None

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

        facts = self._discover_facts(provider.client, backend_id)
        manifest = self._select_manifest(capability, facts.runtime, facts.models, facts.custom_nodes)


        asset_bindings: dict = {}
        if asset_paths:
            for role, path in asset_paths.items():
                asset = self.store.ingest(path, type="input", role="input")
                asset_bindings[role] = asset.id

        # AD-MODEL-BINDING-001: resolved model bindings в ExecutionPlan
        model_bindings: dict = {}
        reqs = list(getattr(manifest, "model_requirements", None) or [])
        if reqs:
            model_bindings = _resolve_model_requirements(
                reqs, facts.models, self.model_registry, backend_id
            )

        plan = ExecutionPlan(
            capability=capability,
            workflow_id=manifest.id,
            version=manifest.version,
            params=params or {},
            asset_bindings=asset_bindings,
            model_bindings=model_bindings,
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
        # S0.5: Knowledge pre-flight (advisory, non-blocking)
        knowledge_meta = self._knowledge_preflight(capability, manifest)
        job = self.engine.execute(
            manifest, plan, provider=provider, ws_timeout=ws_timeout,
            gateway=gateway or self.gateway,
            history=history or self.execution_history,
        )
        # S0.5: attach knowledge metadata to Job (additive, non-blocking)
        if knowledge_meta is not None:
            job._knowledge_readiness = knowledge_meta["readiness"]
            job._knowledge_gaps = knowledge_meta["gaps"]
        return job

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
    def explicit_asset_type(assets: Any = None, store: Any = None) -> Optional[str]:
        """Тип ДОБАВОЧНОГО explicit input текущего turn (S9, AD-23 приоритет).

        Возвращает первый известный media-тип из `assets`, если неявно указанный
        пользователем Asset (не активный ассет сессии). Отличия от
        `resolve_asset_inputs`: эта функция НЕ трогает session.active_asset и
        вызывается до определения capability (для planner context).
        """
        if not assets or not isinstance(assets, dict):
            return None
        for role, spec in assets.items():
            if isinstance(spec, list):
                for item in spec:
                    t = _resolve_one_type(item, store)
                    if t:
                        return t
                continue
            t = _resolve_one_type(spec, store)
            if t:
                return t
        return None

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


def _resolve_one_type(spec: Any, store: Any) -> Optional[str]:
    """Медиа-тип одного explicit asset (для planner context), без изменения active_asset."""
    import mimetypes
    import os
    from pathlib import Path

    if isinstance(spec, str):
        # path → по расширению (mime guess, без чтения файла)
        mime, _ = mimetypes.guess_type(spec)
        if mime and mime.startswith("image/"):
            return "image"
        if mime and mime.startswith("video/"):
            return "video"
        if mime and mime.startswith("audio/"):
            return "audio"
        return None
    if isinstance(spec, dict):
        if "asset_id" in spec or "reference" in spec:
            aid = spec.get("asset_id") or spec.get("reference")
            asset = store.get(aid) if store else None
            return asset.type if asset is not None else None
        if "path" in spec:
            return _resolve_one_type(spec["path"], store)
        if "data" in spec:
            name = spec.get("name", "")
            mime, _ = mimetypes.guess_type(name)
            if mime and mime.startswith("image/"):
                return "image"
            return None
    return None


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
