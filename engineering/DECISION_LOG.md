# DECISION_LOG.md

Журнал решений. НЕ заменяет Architectural Decisions внутри PROJECT_SPEC (§24) — дополняет их операционным контекстом.

<!-- id:n7k2pz -->
Формат:
```text
Date
Decision ID
Context
Decision
Reason
Affected components
Author/Agent
```

Новые архитектурные решения сначала получают ID (например, `AD-29`) и только после утверждения
становятся частью baseline (PROJECT_SPEC §24 + derived docs).

## История (уже APPROVED, перенесено в PROJECT_SPEC §24)
- **AD-24** (NQ-01) latest = max VALIDATED/AVAILABLE semver; Job не ссылается на latest. Author: architect-review.
- **AD-25** (NQ-02) limits: null=unlimited, 0=forbidden, positive=limit. Author: architect-review.
- **AD-26** (NQ-03) BackendRef{provider, backend, reference, metadata}; ComfyUI reference backend-specific. Author: architect-review.
- **AD-27** (S-01) DECLARED_ONLY — механизм для capability без исполнимого workflow. Исторически `video_generate` был DECLARED_ONLY на этапе M4; в M6 `video_generate`/`audio_generate` стали исполнимыми (DECLARED_ONLY снят, решение 2026-08-30). Author: architect-review.
- **AD-28** (doc hierarchy) PROJECT_SPEC > docs > engineering > tasks > code; конфликт → STOP→REPORT→DECISION→IMPLEMENT. Author: architect-review.

## Шаблон для новых
```text
Date:
Decision ID: AD-xx
Context:
Decision:
Reason:
Affected components:
Author/Agent:
Status: PROPOSED | APPROVED
```

## 2026-09-01 — AD-30, AD-31, AD-32 (Prompt Builder architectural decisions)
- **Decision ID:** AD-30, AD-31, AD-32
- **Context:** Архитектурное планирование M11 Prompt Builder + Dynamic Prompt Suggestions. Необходимо зафиксировать границы модуля и разделение ответственности с существующим Planner.
- **Decision:**
  - **AD-30:** PromptBuilder — отдельный модуль для улучшения промптов (`user text → quality prompt`), НЕ заменяет Planner (`user intent → capability/workflow`). PromptBuilder не имеет доступа к FS или ComfyUI; получает только декларативный контекст (строки и идентификаторы). Никаких bytes, файлов, путей, внутренних объектов ComfyUI.
  - **AD-31:** PromptBuilder улучшает текст промпта, но НЕ решает "image.generate или image.edit?". Выбор capability — исключительная ответственность Planner. PromptBuilder может использоваться UI напрямую через `/api/prompt/suggest` (MVP) или опционально интегрироваться в Planner/ConversationAgent (future scope).
  - **AD-32:** Улучшенный prompt должен содержать исходное намерение пользователя. `original_preserved` flag проверяется. Исходный пользовательский текст НИКОГДА не уничтожается автоматически без явного выбора пользователя.
- **Reason:** Чёткое разделение ответственности между Planner (capability selection) и PromptBuilder (prompt quality). Безопасность: PromptBuilder не имеет доступа к FS/ComfyUI. UX: пользователь сохраняет контроль над своим текстом.
- **Affected components:** `app/prompt/` (новый модуль), `app/ui.py` (endpoint `/api/prompt/suggest`), `docs/PROJECT_SPEC.md`, `docs/17_ROADMAP.md`, `docs/18_DEFINITION_OF_DONE.md`, `docs/20_PROMPT_BUILDER.md`.
- **Author/Agent:** architect-review
- **Status:** APPROVED (зафиксировано в PROJECT_SPEC §24)

## 2026-09-03 — AD-40 (Intent → Capability Planning Direction)

- **Decision ID:** AD-40
- **Context:** После завершения M18 (Multi-Step Chain) необходимо определить следующий архитектурный скачок в управлении ComfyUI. Рассмотрены два направления: A (Cluster Gateway — управление несколькими ComfyUI instances) и B (Intent-Driven Workflow Composition — автоматическая сборка операций из намерения пользователя).
- **Decision:**
  - **Выбрано направление B: Intent → Capability Planning** с архитектурой: `User Intent → Intent Understanding → Capability Planning → Plan/Capability Graph → Primitive Operations → Workflow Composition → ExecutionChain → WorkflowEngine → ComfyUI`
  - **Workflow Composition собирает ТОЛЬКО из зарегистрированных Capability/Workflow primitives** (из CapabilityRegistry/WorkflowRegistry). Свободная генерация ComfyUI workflow запрещена.
  - **Cluster Gateway (A) отложен** как следующий инфраструктурный этап после B. Gateway НЕ выбирает capability — только определяет "где выполнить" на основе здоровья/нагрузки backends.
  - **M19 не начинать** — сначала архитектурное исследование B.
- **Reason:** M18 уже создал исполнительный механизм для многошаговых задач. Следующий естественный вопрос — научить систему самой выводить необходимые шаги из намерения пользователя, сохраняя CapabilityRegistry/WorkflowRegistry как источник истины. B логически продолжает M18.

## 2026-09-11 — M25 Experience Foundation: FROZEN

- **Decision ID:** M25 (milestone freeze)
- **Context:** M25 прошла `M25_FORENSIC_ACCEPTANCE_AUDIT.md` (первично `NOT ACCEPTED` по B1/B2), затем B1/B2 закрыты (`docs/M25_COMPLETION_REPORT.md` 2026-09-11: `M25 READY FOR ACCEPTANCE`). Требуется зафиксировать M25 как frozen в состоянии проекта.
- **Decision:**
  - M25 = FROZEN. `ChainExperience` + `SequenceExperience` (computed view, НЕ отдельная persistence — решение M25_ARCHITECTURE_REVIEW §3.4), `chain_id` tracking, multi-asset `video.image_to_video`, `verify_temporal_consistency()` в production pipeline (`app/conversation.py:595`), `build_sequence_experience()` в experience flow (`app/conversation.py:643`).
  - **AD-37/38/39/40 (M25_PROPOSAL) и AD-MODEL-BINDING-001** — сохраняют статус PROPOSED→утверждены в рамках M25 (Experience as Data, Sequence as Metadata, Multi-Asset flag, Experience Persistence).
  - **Semantic temporal verification (full, multi-image)** и **Experience → Planning integration** явно DEFERRED в M26+ (решение MASTER §5.4 / M25_ARCHITECTURE_REVIEW §5.4 / NEXT_MILESTONE §7.2).
- **Reason:** Архитектурные инварианты M25 сохранены (Experience = факт, не правило; media-agnostic; single JSONL persistence). Закрытие B1/B2 не меняет публичные контракты M1–M24.
- **Affected components:** `app/engine/experience.py`, `app/engine/semantic_verifier.py`, `app/conversation.py`, `workflows/video_image_to_video/manifest.json`, `tests/test_m25_b1_b2_integration.py`.
- **Author/Agent:** architect-review / opencode
- **Status:** FROZEN

> **DOC ISSUE (RESOLVED-DOCUMENTED, не блокирует):** обнаружен AD-id коллизия — `AD-41` использовался дважды: (a) **Composer architecture** — каноническое значение, подтверждено кодом (`app/planner/composer.py:3`, `capability_graph.py:3`, `composition_result.py:3`); (b) **Intent → Capability Planning Architecture** (2026-09-03) и **Backend-Scoping DEFERRED** (2026-09-08) — исторически записаны под тем же лейблом. Код НЕ переименовывается. Backend-Scoping остаётся DEFERRED и при следующем архитектурном решении получит отдельный ID (предлагается AD-43).
- **Affected components:** Исследование затронет `app/planner/`, `app/registry/`, `app/engine/chain.py`, `docs/PROJECT_SPEC.md`, `docs/17_ROADMAP.md`.
- **Author/Agent:** architect-review
- **Status:** APPROVED

## 2026-09-11 — M26.1/26.2/26.4 IMPLEMENTED (Experience-Driven Planning Loop, partial)

- **Decision ID:** M26 (partial implementation)
- **Context:** M26 forensic design (`docs/M26_PRE_IMPLEMENTATION_FORENSIC_DESIGN.md`) принят. M25 FROZEN. Утверждены M26.1 (Experience Analytics), M26.2 (Experience → AdaptivePlanner), M26.4 (Experience → Composer suggestions). M26.3 (output-video temporal verification) ЗАБЛОКИРОВАН (нет frame-extraction, output-quality-gate semantics требуют AD, threshold `0.7` не имеет контракта).
- **Decision:**
  - **M26.1:** добавлен `ExperienceAnalytics` (read-only aggregation над `ExperienceStore`) в `app/engine/experience.py`. `temporal_stats()`, `preferred_params()` — ranking по непрерывному temporal score. `EXPERIENCE_MIN_SAMPLES_FOR_PREFERENCE=2` (переиспользует конвенцию `count>=2`, без magic `0.7`). `ExperienceHint` dataclass.
  - **M26.2:** `AdaptivePlanner(experience_store=...)` применяет experience-preference как **soft default** (ranking, НЕ prohibition). `PlanContext` M9.1 и `ExecutionRecord` НЕ изменены. Нет magic threshold.
  - **M26.4:** `Composer.compose(experience_hint=...)` добавляет computed suggestion (не меняет chain/alternatives, не auto-policy).
  - **M26.3:** НЕ реализован. Не добавлены cv2/ffmpeg/frame-extraction/новый verifier/новый AD.
  - **D12 (FeedbackStore → AdaptivePlanner):** подтверждённо WIRED (из M24/M19); НЕ изменён, НЕ является gap. AC7 = regression-тест `test_m24_1_production_wiring.py` проходит.
- **Reason:** M26.1/26.2/26.4 реализованы в рамках существующего AD-контура (AD-36/37/38/39, M9.1 FROZEN, single SemanticVerifier path). M26.3 заблокирован architectural решениями (B1/B2/B3 из forensic design).
- **Affected components:** `app/engine/experience.py`, `app/planner/adaptive.py`, `app/planner/composer.py`, `app/conversation.py`, `app/engine/__init__.py`, `tests/test_m26_*.py`.
- **Author/Agent:** opencode
- **Status:** M26.1/26.2/26.4 **ACCEPTED** (2026-09-11). M26.3 **REDEFINED / DEFERRED as Video Editor Integration Boundary** (см. запись ниже). M26 целиком **READY TO FREEZE** после docs reconciliation. D12 **CLOSED** (wiring существует, не изменять).

## 2026-09-11 — M26.3 REDEFINED (Video Editor Integration Boundary) + AD-44 SUPERSEDED

- **Decision ID:** M26.3 (redefinition) / AD-44 (disposition)
- **Context:** У проекта появится отдельный проект **Video Editor / Media Project** (монтаж/сборка episodes, timeline, transitions, audio/sync, effects, final render/mastering, анализ и обработка готового video, video-specific frame extraction и media processing). ComfyUI Agent НЕ должен превращаться в видеоредактор. Исходная постановка M26.3 («frame extraction → temporal score → SUCCESS/FAILED») признана принадлежащей downstream media boundary.
- **Decision:**
  - **M26.3 REDEFINED** как *Downstream Media / Video Editor Integration Boundary*: Agent передаёт generated assets/episodes, Video Editor выполняет media-specific обработку и возвращает результат/feedback как downstream Experience. Agent НЕ содержит video-processing слоя.
  - **Variant A (advisory, старой формулировки):** НЕ реализуется сейчас (video-specific signal требует media-processing слоя Video Editor).
  - **Variant B / AD-44:** **SUPERSEDED / NOT APPROVED** — исходная post-hoc FAILED semantics признана принадлежащей downstream boundary.
  - **Ownership** Agent ↔ Video Editor явно разделён (таблица в `docs/M26.3_FORENSIC_DESIGN.md` PART 2 §20).
  - **Experience:** Agent может принимать downstream feedback как Experience (optional integration; обычный путь `Agent → ComfyUI → asset` НЕ зависит от Video Editor). Не менять `ExecutionRecord`/`PlanContext`.
  - **Future: Video Editor Integration** — отдельный проект определит API/contract, asset handoff, episode representation, processing status, final output, error semantics, optional quality/feedback payload.
- **Reason:** Video-specific analysis — responsibility будущего Video Editor, НЕ Agent Core. Это сохраняет media-agnostic invariant (AD-03) и не добавляет cv2/ffmpeg/frame-extraction в Agent.
- **Affected components:** только документация (`docs/M26.3_FORENSIC_DESIGN.md`, `docs/M26_COMPLETION_REPORT.md`, `docs/MASTER_DEVELOPMENT_ROADMAP.md`, `docs/M26_PRE_IMPLEMENTATION_FORENSIC_DESIGN.md`, `tasks/ACTIVE.md`, `tasks/COMPLETED.md`, `engineering/HANDOFF.md`).
- **Author/Agent:** opencode
- **Status:** M26.3 **REDEFINED / DEFERRED**. AD-44 **SUPERSEDED / NOT APPROVED**. M26.1/26.2/26.4 **ACCEPTED**. M26 **READY TO FREEZE**.

## 2026-09-03 — AD-41 (Intent → Capability Planning Architecture)

- **Decision ID:** AD-41
- **Context:** Архитектурное исследование Intent-Driven Workflow Composition (docs/22_INTENT_CAPABILITY_PLANNING_RESEARCH.md) подтвердило feasibility. Необходимо зафиксировать архитектурные решения для реализации.
- **Decision:**
  - **Composer — отдельный класс**, НЕ часть Planner протокола. Planner отвечает за intent → capability, Composer за capability → chain of capabilities.
  - **Parameter mapping** — начать с identity mapping (params pass-through). Каждый шаг получает params из Planner result.
  - **Intermediate verification** — опционально, по умолчанию выключено. Включается через `Composer(semantic_verifier=...)`.
  - **Max chain length** — 5 шагов. Предотвращает composition explosion.
  - **Alternative paths** — Composer возвращает до 3 вариантов composition. Planner/ConversationAgent выбирает оптимальный на основе history.
  - **CapabilityGraph** — строится из CapabilityRegistry. Edges определяются media type compatibility (output_A ∈ input_B).
  - **CompositionResult** — явный тип результата с `success`, `chain`, `alternatives`, `failure_reason`.
- **Reason:** Чёткое разделение ответственности: Planner (intent → capability), Composer (capability → chain), ExecutionChain (execution). Сохраняет M1-M18 frozen. Минимальная сложность для начала.
- **Affected components:** Новые модули `app/planner/composer.py`, `app/planner/capability_graph.py`, `app/planner/composition_result.py`. Интеграция с `app/conversation.py`.
- **Author/Agent:** architect-review
- **Status:** APPROVED

## 2026-09-03 — M19 ACCEPTED & FROZEN

- **Decision ID:** M19-STATUS
- **Context:** M19 (Intent → Capability Planning + Composer integration) прошёл полный цикл: 386 passed, 3 skipped regression; 53 unit/integration tests; 6 real E2E (generate→upscale через Composer на реальном ComfyUI). Asset handoff, lineage, history, chain_step_index, cancellation — все VERIFIED.
- **Decision:**
  - **M19 ACCEPTED / VERIFIED / FROZEN.** НЕ трогать без отдельного архитектурного решения.
  - **Уточнение ответственности:** CapabilityGraph — это knowledge/constraint layer (composability knowledge), которым пользуется Composer, НЕ отдельный execution-stage после Composer. Реальный control flow: `Planner → Composer ↕ CapabilityGraph → Composition → ExecutionChain`. Код уже соответствует (Composer владеет `CapabilityGraph` как полем `self._graph`); обновлена документация.
- **Reason:** Реально доказан новый контур: User Intent → ConversationAgent → Planner → Composer → CapabilityGraph → ExecutionChain → WorkflowEngine → ComfyUI. M19 добавляет возможность композиции без второго execution path.
- **Affected components:** `app/planner/composer.py`, `app/planner/capability_graph.py`, `app/conversation.py`, `docs/23_COMPOSER_INTEGRATION_AUDIT.md`.
- **Author/Agent:** architect-review
- **Status:** APPROVED & FROZEN

## 2026-09-03 — AD-42 (Cluster Gateway — Architecture Design/Audit, БЕЗ production-кода)

- **Decision ID:** AD-42
- **Context:** После M19 (Intent → Capability Planning, FROZEN) система имеет полный интеллектуальный контур: User → ConversationAgent → Planner → Composer ↕ CapabilityGraph → ExecutionChain → WorkflowEngine → ComfyUI. Следующий архитектурный слой — Cluster Gateway (Execution Resource Layer). Пользователь явно одобрил только **архитектурный дизайн/аудит**, НЕ написание production-кода. Критически важно: failover/factory для ComfyUI НЕ является автоматически безопасным (риск duplicate execution при disconnect после submission).
- **Decision:**
  - **BD: Cluster Gateway APPROVED FOR ARCHITECTURAL DESIGN/AUDIT.** На этом этапе НЕ пишется production-код для Gateway. Сначала — архитектурный дизайн/аудит.
  - **Разделение ответственности в будущем дизайне:**
    - **Intelligence layer (ЧТО делать):** Planner, Composer, CapabilityGraph, AdaptivePlanner, SemanticVerifier.
    - **Execution layer (КАК выполнить):** ExecutionChain, WorkflowEngine, Provider, Backend.
    - **Resource layer (ГДЕ выполнить):** ClusterGateway — health, load, compatibility, routing, failover.
  - **Строгие ограничения (15 вопросов обязательны для ответа):**
    - Gateway НЕ может менять ExecutionPlan — **нет**.
    - Gateway НЕ может выбирать capability — **нет**.
    - Gateway НЕ может создавать workflow — **нет**.
    - Gateway НЕ может обходить WorkflowEngine — **нет**.
  - **Критическое разделение Routing vs Failover:**
    - **Routing** (NEW job → choose backend) — может быть автоматическим.
    - **Failover** (UNKNOWN execution state) — НЕ выполняется автоматически. Обязателен reconcile/inspect/recover, чтобы предотвратить duplicate execution (задача отправлена на Remote-1, сгенерировала результат A; повтор на Remote-2 даст результат B — дубль).
- **Reason:** Исключить риск скрытых дубликатов при неверном автоматическом failover. Обеспечить чистое разделение "intelligence → what, execution → how, resource → where".
- **Affected components:** Новый слой `app/resource/` (Cluster Gateway). M1-M19 frozen, НЕ изменяются. Добавлено поле `backend_execution_identity` в Job/ExecutionRecord (default=None, без нарушения существующих тестов).
- **Author/Agent:** architect-review
- **Status:** APPROVED FOR IMPLEMENTATION (решение пользователя 2026-09-03)

## 2026-09-03 — M20 ACCEPTED & FROZEN

- **Decision ID:** M20-STATUS
- **Context:** M20 (Cluster Gateway, AD-42) реализован как Execution Resource Layer (WHERE). Доказано: Routing, Health-aware selection, Load-aware selection, Capability compatibility, Dispatch tracking, UNKNOWN protection, Safe retry NOT_ACCEPTED. `backend_execution_identity` связывает Job → ExecutionHistory → Gateway.
- **Decision:**
  - **M20 ACCEPTED / VERIFIED / FROZEN.** Routing и recovery-decision доказаны.
  - **Оговорка (важно):** Реальное управление распределённым исполнением при потере связи НЕ доказано (нет fault-injection real E2E). Это нормально — AD-42 разделил Routing и Recovery.
  - **Следующий этап: M21 — Reconciliation & Recovery.** Цель: submit → backend_execution_identity → connection lost → UNKNOWN → reconcile (COMPLETED→recover / RUNNING→observe / FAILED→record / NOT_ACCEPTED→safe retry / UNKNOWN→STOP). Требует реальный E2E fault-injection, не только unit tests.
  - **Automatic failover ⛔ пока запрещён** (только после доказанного M21).
- **Reason:** Gateway должен остаться WHERE-слоем без обратной связи в Intelligence. UNKNOWN-обработка — correctness invariant распределённой системы.
- **Affected components:** M1-M19 frozen. Новый план `docs/25_M21_RECONCILIATION_RECOVERY.md`.
- **Author/Agent:** architect-review
- **Status:** APPROVED & FROZEN


## 2026-09-01 — AD-33, AD-34 (ComfyCLI Optional Infrastructure Adapter)

- **Decision ID:** AD-33, AD-34
- **Context:** Реализация M12.1 — опциональный infrastructure adapter для comfy-cli (diagnostics, валидация, управление процессами). Необходимо зафиксировать безопасность (shell=True запрещён) и опциональность (отсутствие CLI не блокирует Agent).
- **Decision:**
  - **AD-33:** Все subprocess-вызовы через `ComfyCLIAdapter` обязаны использовать `shell=False`. Тест `test_no_shell_true` проверяет это на уровне кода через AST-анализ импортов и вызовов `subprocess.run`. Никаких исключений.
  - **AD-34:** `ComfyCLIAdapter` полностью опциональный. `is_available()` возвращает `False` при отсутствии comfy-cli; все методы возвращают `ComfyCLIResult(ok=False, error="comfy-cli not available")`. Основной execution path (`ComfyClient` + `WorkflowEngine`) не зависит от CLI. Adapter не используется в `Agent`, `ConversationAgent`, `WorkflowEngine`, `Provider`, `AssetStore`. Отсутствие/ошибка CLI никогда не блокирует генерацию или execution.
- **Reason:** Безопасность (shell=True = command injection risk) + надёжность (comfy-cli не обязателен для работы Agent; infrastructure adapter = diagnostics/optional tooling).
- **Affected components:** `app/infrastructure/` (новый модуль), `tests/test_comfy_cli_adapter.py`, `docs/PROJECT_SPEC.md` (§24).
- **Author/Agent:** OpenCode (auto-implemented)
- **Status:** APPROVED (зафиксировано в PROJECT_SPEC §24)

## 2026-09-08 — AD-41 (Backend-Scoping Deferred)

- **Decision ID:** AD-41
- **Context:** Extended Discovery (Steps 1-7 + §H.4 mapping gap) завершился корректно. При аудите обнаружен потенциал для backend-scoping: `Workflow.backend` существует как поле манифеста, но НЕ используется для gating selection или dispatch. Все текущие manifests declare `backend="local_comfyui"`, включая `pollinations_image` (external API через BYOP-узел, но исполняемый локально). AD-01 определяет v1 как 1:1 (`comfyui` ↔ `local_comfyui`). `select_candidate()`, `evaluate_compatibility()`, `_select_manifest()` — все backend-agnostic.
- **Decision:**
  - **ENFORCEMENT DEFERRED:** Gating selection по `Workflow.backend` ≠ selected `BackendSpec.kind` НЕ реализуется на данном этапе.
  - **Rationale:**
    1. AD-01 явно определяет v1 как 1:1 mapping — enforcement redundant при single-backend deployment.
    2. Все 9 существующих workflows корректно declare `backend="local_comfyui"` — ни один не нарушает контракт.
    3. `pollinations_image` семантически корректен: он исполняется ЧЕРЕЗ локальный ComfyUI (BYOP узел делает HTTP-запрос к pollinations API), поэтому `backend="local_comfyui"` верен.
    4. Реальное различие между workflows уже захвачено другими полями: `required_custom_nodes`, `required_models`, `requirements.min_vram_gb`.
    5. premature enforcement создал бы ложные UNAVAILABLE statuses при добавлении новых workflow без multi-backend infrastructure.
  - **EXTENSION POINT сохранён:** TODO-заметка в `app/agent.py:313` фиксирует gap и направление для future AD.
  - **Workflow.backend остаётся metadata** — используется для dispatch identity (`provider.backend_id`) и логирования, но НЕ для selection gating.
  - **Triggers для future implementation:** (a) добавление `remote_comfyui` или `cloud_comfyui` backend в `BackendCatalog`; (b) workflow с `backend != "local_comfyui"`; (c) явное требование architectural review.
- **Reason:** Current single-backend deployment makes enforcement redundant. Deferred enforcement avoids breaking new workflows that legitimately run on local ComfyUI (even if they call external APIs via BYOP nodes). The gap is documented and will be addressed when multi-backend support is introduced.
- **Affected components:** `app/agent.py` (TODO note at line 313), `docs/EXTENDED_DISCOVERY_DESIGN.md` (§G Backend-Scoping Boundary), `engineering/DECISION_LOG.md` (этот записЬ). НЕТ изменений в `app/registry/selection.py`, `app/registry/compatibility.py`, `app/registry/backends.py`.
- **Author/Agent:** Agnes-2.5-flash (extended discovery audit + AD formulation)
- **Status:** APPROVED (deferred enforcement)


## 2026-09-13 - AD-45, AD-46, AD-47 (Ecosystem-First S0.5/S1/S2)

- **Decision ID:** AD-45, AD-46, AD-47
- **Context:** Ecosystem-First baseline (docs/ECOSYSTEM_FIRST_ARCHITECTURE.md, APPROVED) требует трёх слоёв: связи Knowledge с Agent (S0.5), Free-First (S1), моста Candidate→Workflow (S2). Каждый принят автором по ритуалу design → approval → implementation → forensic verification → freeze.
- **Decision:**
  - **AD-45 (Knowledge advisory invariant):** KnowledgeCore pre-flight подключён к `Agent`/`ConversationAgent` как OPTIONAL (`knowledge_core=None` = прежнее поведение) и является **advisory evidence, а НЕ execution eligibility**. Readiness `EXECUTABLE/CANDIDATE_ONLY/GAP/UNKNOWN` описывает только то, что знает Knowledge; право на исполнение остаётся за capability/workflow/compatibility/S1-cost проверками. Knowledge absence ≠ capability absence (fail-open). Metadata `Job._knowledge_readiness/_knowledge_gaps` — runtime-only, НЕ в ExecutionRecord persistence.
  - **AD-46 (CostTier binding + UNKNOWN≠FREE):** `CostTier{FREE,TRIAL,PAID,UNKNOWN}` живёт на `BackendSpec` (default по kind: local_comfyui→FREE, иначе UNKNOWN) и опционально на `Workflow` manifest (workflow override > backend > UNKNOWN). **Per-node cost НЕ вводится** (решение открытого Q1). UNKNOWN≠FREE (аналог AD-18). Auto-selection: filter→ranking (PAID/UNKNOWN исключаются ДО ранжирования; FREE>TRIAL — soft preference). `allow_paid=True` — только явный override, production его не передаёт.
  - **AD-47 (Template-Based Synthesis; synthesis ≠ validation):** one-node workflow synthesis ОТКЛОНЁН feasibility gate'ом (реальный ComfyUI — multi-node графы; IMAGE/MODEL/LATENT inputs требуют upstream; 150+ input types). Принята template-синтез: `CapabilityCandidate + NodeSchema + WorkflowTemplate → manifest/workflow` (deterministic selector, без LLM, без graph solver). Синтез produce'ит **только данные**: нет auto-registration в WorkflowRegistry, нет статуса VALIDATED от факта синтеза, readiness не меняется. Валидация — существующая инфраструктура (load_workflow = статическая; RuntimeValidator = deferred S6). Safety-классификация минимальная: ALLOWED/REQUIRES_CONFIRMATION/FORBIDDEN по python_module/category; при недостатке доказательств → REQUIRES_CONFIRMATION.
- **Reason:** Разделение источников истины: Knowledge — про знание, compatibility/cost-фильтры — про допуск, execution — про факт. Слияние этих слоёв давало бы ложные разрешения на запуск (см. S2 acceptance gate, IMAGE-ноды vs graph fragments).
- **Affected components:** `app/agent.py`, `app/conversation.py`, `app/engine/job.py` (S0.5); `app/registry/cost.py` (new), `app/registry/backends.py`, `app/registry/workflow.py` (S1); `app/synthesis/` (new, S2), `app/knowledge/core.py` (+synthesize_candidates, advisory). Frozen M25/M26 контракты не затронуты.
- **Tech debt (осознанно принята):** `_select_manifest()` без аргумента `backend` пропускает cost-filter (backward-compat прямых вызовов; production path через `prepare()` backend передаёт). Если `_select_manifest` станет публичным — закрыть отдельно.
- **Author/Agent:** OpenCode (implementation) / автор проекта (approval каждого слоя)
- **Status:** APPROVED & FROZEN (S0.5, S1); S2 — ACCEPTED WITH DOCUMENTED RUNTIME GAP (файл-output proof ждёт свободной ComfyUI-очереди; graph принят сервером)
