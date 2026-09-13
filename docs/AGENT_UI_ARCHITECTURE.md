# AGENT_UI_ARCHITECTURE.md

> **Статус:** DRAFT для утверждения автором (архитектурный проект, реализация НЕ начата).
> **Source of truth:** `docs/PROJECT_SPEC.md` v0.2 (APPROVED). Настоящий документ — производный;
> НЕ вводит новых архитектурных решений сам по себе; предложения новых контрактов помечены и требуют AD.
> **Дата:** 2026-09-08
> **Автор:** архитектурное проектирование Agent UI (Operator UI) поверх существующего Agent Core.

---

## 1. Цели и Non-goals

### Цели
- Спроектировать **Agent UI** как полноценный **Operator UI** для управления агентом (Multimodal Agent Operator поверх ComfyUI).
- Сделать прозрачным для пользователя весь путь: запрос → intent → план → capability → workflow → Job → execution → verification → результат.
- Использовать **существующий Agent Core** как единственный source of truth. UI **отображает и инициирует** операции, но **не** принимает архитектурных решений агента.
- Сохранить совместимость с текущими M9/M12 тестами и поведением `app/ui.py`.
- Определить, что уже можно экспонировать из Agent Core без изменений, а где действительно требуется новый backend-контракт.

### Non-goals (v1 Agent UI)
- НЕ заменять ComfyUI. ComfyUI остаётся execution environment и показывает реальное выполнение workflow через `http://127.0.0.1:8188`.
- НЕ создавать второй execution engine, второй Planner, второй WorkflowEngine, второй Registry, второй AssetStore, вторую state machine агента.
- НЕ показывать внутренний chain-of-thought или скрытые рассуждения LLM.
- НЕ делать media-specific архитектурные ветки (image/video/audio — единообразно; AD-03).
- НЕ создавать UI-заглушки, выдающие себя за реальные события; никакого fake progress / fake states / mock execution.
- НЕ использовать старое `C:\cd\ComfyUI_AMD\ComfyUI` и НЕ создавать скрытый второй ComfyUI runtime.
- НЕ использовать Gemma/comfyui-mcp как альтернативный Agent Core.

---

## 2. Архитектурная роль Agent UI

**Agent UI ≠ ComfyUI.**

- **Agent UI** — операторский интерфейс агента: диалог, понимание запроса, план, выбор capability/workflow, живой статус Job, verification, результаты, история.
- **ComfyUI** — execution UI / визуальный исполнитель. Agent UI даёт кнопку/ссылку перехода в Comfy Desktop, но не копирует его интерфейс.

Целевая схема:

```
User
  → Agent UI              (Operator UI: отображение + инициирование операций)
  → Agent Core            (ConversationAgent / Agent — source of truth)
  → Planner               (intent → capability/chain)
  → Capability / Workflow (Registry — выбор)
  → WorkflowEngine        (сборка prompt + оркестрация)
  → Comfy Desktop         (execution backend, 127.0.0.1:8188)
  → Verification          (Verifier / SemanticVerifier)
  → Result                (AssetStore → Assets)
  → Agent UI              (preview + статус + ответ)
```

Пользователь в Agent UI должен видеть:
1. свой запрос;
2. состояние диалога;
3. сформированный intent (capability);
4. план агента (plan / chain);
5. выбранную Capability;
6. выбранный Workflow (`id@version`);
7. текущий Job;
8. этап выполнения;
9. прогресс;
10. ошибки;
11. verification;
12. полученные Assets;
13. итоговый ответ агента.

ComfyUI при этом продолжает показывать реальное выполнение workflow в самом Comfy Desktop.

---

## 3. Аудит существующей архитектуры (что уже есть)

### 3.1 Agent Core — реальные компоненты (проверено по коду)

| Компонент | Файл | Что даёт для UI |
|-----------|------|------------------|
| `ConversationAgent` | `app/conversation.py` | multi-turn `turn()`, session isolation, retry loop (M13), multi-step chain (M18), decision/failure events (M22–M24), Knowledge pre-flight (S0.5, advisory), experience (M25) |
| `ConversationContext` | `app/conversation.py:39` | `as_dict()` — готовый snapshot состояния сессии (messages, assets, jobs, workflows, active_*, unresolved, dialog_state) — **основа recovery** |
| `dialog_state` | `ConversationContext.dialog_state` | `idle / awaiting_input / awaiting_feedback / error` — реальные states диалога |
| `Agent` | `app/agent.py` | `capabilities()`, `prepare()` (manifest/plan/provider), `generate()`, `resolve_asset_inputs()`, runtime validation (S4) |
| `Job` + `JobState` | `app/engine/job.py` | `QUEUED/RUNNING/SUCCESS/FAILED/CANCELLED` + attempt, error_class, chain_id, backend_execution_identity, decision_*, `_knowledge_readiness`/`_knowledge_gaps` (S0.5, advisory metadata; НЕ в ExecutionRecord persistence) |
| `WorkflowEngine` | `app/engine/engine.py` | единый execution path; WS-трекинг + `/history` fallback; Verifier; lineage |
| `Verifier` / `VerificationResult` | `app/engine/verifier.py` | `verify_with_diagnostics()` — детальная диагностика по output (ok/error_class/error_message) |
| `SemanticVerifier` | `app/engine/semantic_verifier.py` | score/intent check (после SUCCESS, только image/video) |
| `ExecutionHistory` | `app/engine/history.py` | `ExecutionRecord` (по каждой попытке), chain summary (M25), dispatch tracking (M21) |
| `RetryPolicy` / `RetryDecision` | `app/engine/retry.py` | action (`accept/retry/ask_user/failed`), param_adjustments, suggestions |
| `ClusterGateway` | `app/resource/gateway.py` | backend health/state/routing/reconcile (MD-01..05), `list_backends()`, `route()` |
| `BackendCatalog` / `BackendSpec` | `app/registry/backends.py` | перечень известных backend, выбор по capability |
| `BackendResource` / `BackendHealth` / `BackendResourceState` | `app/resource/models.py` | health/state/queue_depth — готово к экспозиции status/health |
| `AssetStore` | `app/assets/store.py` | assets, lineage, ingest, get |
| `ContextPersistence` / `SessionManager` | `app/context/persistence.py`, `app/context/session_manager.py` | JSONL-персистентность сессий (M15) — восстановление после рестарта |
| `Composer` / `CompositionResult` | `app/planner/composer.py`, `composition_result.py` | chain + alternatives + failure_reason + suggestions (M19, AD-41) |
| `TaskDecomposer` / `ExecutionChain` / `ChainResult` | `app/planner/decomposer.py`, `app/engine/chain.py` | chain steps, per-step state (pending/running/completed/failed/cancelled), chain summary |

### 3.2 Текущий UI (M9/M12) — что существует

`app/ui.py` (stdlib `http.server`, inline HTML+JS, БЕЗ Vite+React):

| Endpoint | Метод | Назначение |
|----------|-------|-----------|
| `/` | GET | inline chat-страница (чат + preview + SSE JS) |
| `/turn` | POST | запуск `ConversationAgent.turn` в фоновом потоке; возвращает 200 сразу |
| `/events?session_id=` | GET | SSE: `start`, `status`, `progress`, `chain_step`, `result`, `error` |
| `/api/session?session_id=` | GET | JSON `ConversationContext.as_dict()` + `exists` |
| `/asset/<id>` | GET | байты ассета (preview) |
| `/api/prompt/suggest` | POST | M11: Dynamic Prompt Suggestion |
| `/api/feedback` | POST | M17: запись feedback (rating 1-5) |
| `/api/feedback/history` | GET | M17: история feedback сессии |

**Реальные SSE-события, которые Agent Core уже способен отдавать UI** (через `app/ui.py`):
- `start` (session_id, capability, request)
- `status` (`RUNNING`)
- `progress` (value, max, pct) — реальные WS progress события (честный %)
- `chain_step` (step, total_steps, capability, state) — M18/M19
- `result` (state, active_asset, active_workflow, active_job, assets, preview)
- `error` (error, kind)

**События, реально существующие в `ConversationContext.messages` и `Job`, но НЕ стримящиеся в SSE:**
- `retry_started` / `retry_completed` (M13)
- `decision_failed` (M22), `feedback_request` (M24, `dialog_state=awaiting_feedback`)
- `_decision_reason`, `_decision_suggestions`, `_decision_action` (`ask_user`) на Job
- verification: `SemanticVerifier` score / `Verifier` diagnostics — есть внутри кода, НЕ экспонированы
- `backend_execution_identity`, `state` backend (health/queue) — есть в Gateway/Job, НЕ экспонированы

### 3.3 gaps (что реально не хватает для Operator UI)

| Gap | Детали | Как закрывается |
|-----|--------|-----------------|
| Нет intent/capability/workflow события стримом | UI не видит плана ДО запуска Job | Новый event `plan` (см. Event Model) — требует backend |
| Нет API Job-статуса и списка Job | `GET /api/jobs/{id}` задокументирован в PROJECT_SPEC §21, но **не реализован** | Реализация существующего задокументированного контракта (не новый) |
| Нет cancel в текущем UI | `POST /api/jobs/{id}/cancel` задокументирован, но не реализован; `WorkflowEngine.cancel` есть в коде | Реализация существующего контракта |
| Нет `/api/capabilities`, `/api/workflows`, `/api/runtime` | задокументированы §21, не реализованы | Реализация существующего контракта |
| Нет History API | `ExecutionHistory` есть в памяти, нет endpoint | Новый endpoint `GET /api/history` |
| Нет экспозиции verification | `Verifier.diagnostics`, `SemanticVerifier.score` существуют, не отдаются | Новые поля в result-событии / job API |
| Нет экспозиции backend health/state | `BackendResource`/`Gateway` существуют, не отдаются | Новый `GET /api/backends` (проект) |
| Нет стрима `dialog_state` | state store-ится, но не стримится | Новое поле в SSE |
| Recovery после reload — только active_asset | `/api/session` даёт snapshot, но нет восстановления активного Job/этапа | `/api/session` + `/api/jobs/{id}` (после реализации Job API) |
| Frontend — inline JS, не Vite+React | нет отдельного React-приложения | Новый frontend Vite+React (отдельная фаза UI-2) |
| События retry/decision/feedback не идут в SSE | внутренние для контекста | Новые event types (проект) |

---

## 4. Информационная архитектура: зоны Agent UI

Минимальный набор зон (не привязка к маршрутам; главное — наличие каждого блока):

### A. Conversation (диалог)
- Список сообщений пользователя и агента, вложения (input assets).
- Каждое сообщение-результат связано со своей задачей/Job.

### B. Current Task (текущая задача)
- Запрос пользователя.
- Intent / capability (что агент понял).
- constraints (параметры: ширина/высота/шаги и т.п. — из plan.params).
- Статус задачи (dialog_state).
- Clarification / Confirmation (awaiting_input, awaiting_feedback, ask_user, decision_failed).

### C. Agent Plan (план агента)
- Отображение шагов: Understand → Decompose → Select Capability → Select Workflow → Execute → Verify → Complete.
- Для цепочки (M18/M19): каждый шаг с capability и workflow.
- Plan берётся из реальных артефактов Agent Core (plan, chain, CompositionResult) — НЕ вычисляется во frontend.

### D. Execution (живой статус выполнения)
- Job ID (prompt_id).
- JobState (QUEUED/RUNNING/SUCCESS/FAILED/CANCELLED).
- Capability, Workflow (`id@version`), Backend (backend_execution_identity).
- progress (value/max/pct, честный из WS).
- current stage (chain step, если цепочка).
- elapsed time (from ExecutionRecord.duration или client-side timestamp — допускается локальный подсчёт времени только для отображения).
- errors / retries (error_class, retry_started, decision_reason).

### E. ComfyUI (ссылка/кнопка)
- Кнопка «Открыть Comfy Desktop» → `http://127.0.0.1:8188`.
- НЕ встраивать интерфейс ComfyUI.

### F. Results / Assets (результаты)
- preview (img/video/audio) + Asset id.
- тип результата (asset.type), lineage (source_asset), verification status (ok/diagnostics/score).
- возможность открыть/скачать результат.

### G. History (история)
- Список прошлых tasks (из ExecutionHistory + ConversationContext).
- Фильтр по capability/состоянию/сессии.

### H. System / Providers (опционально, только если архитектура действительно требует)
- Список backends (из `BackendCatalog`/`BackendResource`), их health/state/queue_depth.
- Работоспособность runtime.
- **Не перегружать** техническими деталями; показывать только если есть реальный мультибэкенд.

---

## 5. Модель состояния UI (mapping реальных состояний, НЕ вторая система)

**UI НЕ имеет собственной state machine агента.** UI отображает состояние, полученное от Agent Core.

Требование из задачи: `IDLE → UNDERSTANDING → CLARIFICATION → PLANNING → WAITING_CONFIRMATION → EXECUTING → VERIFYING → COMPLETED → FAILED → CANCELLED`.

Фактические состояния в Agent Core:
- `ConversationContext.dialog_state` ∈ {`idle`, `awaiting_input`, `awaiting_feedback`, `error`}.
- `JobState` ∈ {`QUEUED`, `RUNNING`, `SUCCESS`, `FAILED`, `CANCELLED`}.
- `ChainStep.state` ∈ {`pending`, `running`, `completed`, `failed`, `cancelled`} (внутри цепочки).
- `RetryDecision.action` ∈ {`accept`, `retry`, `ask_user`, `failed`}.
- `ReconcileState` / `RecoveryAction` (M21) — для recovery.

**Mapping** (логика во frontend НЕ порождает новых состояний; это просто группировка нескольких сигналов backend в одно «видимое» состояние):

| UI-видимое состояние | Выводится из (real Agent Core) |
|-----------------------|---------------------------------|
| IDLE | `dialog_state == idle` и нет активного RUNNING Job |
| UNDERSTANDING / PLANNING | новая задача создана (`POST /turn` принят), Job ещё не QUEUED/RUNNING (по SSE `start` без последующего `status(RUNNING)`) |
| CLARIFICATION | `dialog_state == awaiting_input` (unresolved непусто) |
| WAITING_CONFIRMATION | `dialog_state == awaiting_feedback` или Job `_decision_action == ask_user` (событие `feedback_request` / `decision_failed`) |
| EXECUTING | `JobState == RUNNING` (или chain: есть RUNNING step) |
| VERIFYING | Job SUCCESS + verification в процессе (в текущем коде verification синхронна после SUCCESS; UI может показывать VERIFYING по событию `verification.started`, если добавим — проект) |
| COMPLETED | `JobState == SUCCESS` + verification пройдена (result event) |
| FAILED | `JobState == FAILED` (с error_class/reason) или chain failed |
| CANCELLED | `JobState == CANCELLED` |

**Принцип:** источник «состояния» — серверные сигналы. Frontend лишь группирует их для отображения, никогда не «помнит» задачу, если backend её не знает.

---

## 6. Event Model

**Главный принцип:** UI не вычисляет состояние агента самостоятельно; UI отображает состояние, полученное от Agent Core.

Поток: `Agent Core → Backend (app/ui.py) → SSE/WebSocket → Agent UI`.

### 6.1 Существующие события (уже работают)

| Событие | Существует? | Источник | Payload | Новый endpoint? |
|---------|-------------|----------|---------|-----------------|
| `start` | ✅ | `app/ui.py` `run_turn` | session_id, capability, request | нет |
| `status` | ✅ | `app/ui.py` | state (`RUNNING`) | нет |
| `progress` | ✅ | WS progress → engine → ui | value, max, pct | нет |
| `chain_step` | ✅ | `_execute_chain` + on_chain_step | step, state, capability, outputs | нет |
| `result` | ✅ | `app/ui.py` | state, active_asset, active_workflow, active_job, assets, preview | нет |
| `error` | ✅ | `app/ui.py` exception | error, kind | нет |

### 6.2 События, реально существующие в Agent Core, но НЕ стримящиеся в SSE (необходимо добавить как событие/поле)

| Событие | Существует в коде? | Источник | Payload (проект) | Новый endpoint? |
|---------|--------------------|----------|------------------|-----------------|
| `dialog_state` обновление | ✅ (`ctx.dialog_state`) | ConversationContext | `{dialog_state}` | поле в существующих событиях — нет нового endpoint |
| `plan` (intent/capability/workflow до запуска) | частично (PlanResult/plan в `Agent.prepare`) | Planner/Agent | `{request, capability, workflow_id@version, params}` | ✅ **новый** event `plan` (или поле в `start`/`result`) |
| `retry_started` / `retry_completed` | ✅ (ctx.messages) | M13 | `{attempt, max_attempts, reason, job}` | ✅ новое SSE-событие (или расширение `status`) |
| `decision_failed` | ✅ (ctx.messages) | M22 | `{reason, suggestions, job, error_class}` | ✅ новое SSE-событие |
| `feedback_request` / `ask_user` | ✅ (ctx.messages, Job._decision_action) | M24 | `{reason, suggestions, job}` | ✅ новое SSE-событие (или `dialog_state`) |
| `verification.started` / `verification.completed` | частично (SemanticVerifier/Verifier) | M14/M13 | `{job, score, ok, diagnostics}` | ✅ новый event — требует хук в turn/engine (проект) |

### 6.3 Полный проектируемый набор событий Agent UI (для каждой: существует / источник / payload / новый? / source of truth)

| Событие | Сейчас | Источник | Payload | Требует backend-хука? | Source of truth |
|---------|--------|----------|---------|------------------------|------------------|
| `task.created` | ❌ (нет) | ConversationAgent.turn entry | session_id, request, capability, attrs | ✅ (прокинуть in `run_turn`) | ConversationContext |
| `conversation.updated` | ✅ частично (`/api/session`) | ConversationContext.as_dict() | messages, dialog_state, active_* | нет (уже есть через /api/session) | ConversationContext |
| `intent.updated` | ❌ | Planner result (capability) | capability, params, rationale | ✅ (после `planner.plan` дать callback) | Planner/PlanResult |
| `plan.created` | ❌ | ExecutionPlan / chain | steps, workflow_id@version, params | ✅ (после `prepare`/`_execute_chain`) | ExecutionPlan |
| `capability.selected` | ❌ | Planner/Composer | capability (и chain) | ✅ | Planner/Composer |
| `workflow.selected` | ❌ | `_select_manifest` | workflow_id@version | ✅ | WorkflowRegistry/Agent |
| `job.created` | ❌ | `engine.execute` (Job created) | job_id, capability, workflow | ✅ (прокинуть из engine) | Job |
| `job.started` | ✅ (`status RUNNING`) | engine/WS | job_id, state | нет (есть) | Job |
| `job.progress` | ✅ | WS | job_id, value, max, pct | нет | Job |
| `job.completed` | ✅ (`result`) | engine | job_id, state, outputs | нет | Job |
| `job.failed` | ✅ (`error`/`result` state failed) | engine/retry | job_id, error, error_class, reason | нет (есть) | Job |
| `verification.started` | ❌ | Verifier/SemanticVerifier | job_id | ✅ | Verifier |
| `verification.completed` | ❌ | Verifier/SemanticVerifier | job_id, ok, score, diagnostics | ✅ | Verifier |
| `asset.created` | ✅ частично (`result`/`/api/session` assets) | AssetStore / engine | asset_id, preview | ✅ | AssetStore |
| `task.completed` | ✅ (`result`) | ConversationContext | active_asset, workflow, job | нет | ConversationContext |
| `task.failed` | ✅ (`error`) | ConversationContext | unresolved, reason | нет | ConversationContext |

> **Правило:** события `plan`, `intent`, `verification`, `retry`, `decision`, `feedback`, `job.created` — **не добавлять автоматически в backend**. Это **проект**; добавляются только после approval и только там, где нужен хук в уже существующий поток (без изменения архитектурных инвариантов).

### 6.4 Source of truth декларация
- Действительный источник состояния — **Agent Core / ConversationContext / Job / Execution / Verifier / AssetStore / ExecutionHistory / ClusterGateway**.
- Frontend НЕ хранит копию состояния как «истину» на длительное время — только кэш отображения.
- При перезагрузке страницы UI восстанавливает состояние из backend (`/api/session`, `/api/jobs/{id}` после реализации).

---

## 7. API-контракт (frontend ↔ backend)

### 7.1 Существующие endpoints (можно использовать без изменений)
- `POST /turn` — запуск turn (используется как есть; расширение payload — проект).
- `GET /events?session_id=` — SSE (используется; расширение набора событий — проект).
- `GET /api/session?session_id=` — snapshot контекста (для recovery).
- `GET /asset/<id>` — preview/скачивание ассета.
- `POST /api/prompt/suggest` — подсказка промпта (M11).
- `POST /api/feedback` / `GET /api/feedback/history` — обратная связь (M17).

### 7.2 Задокументированные, но НЕ реализованные (PROJECT_SPEC §21) — реализуются как контракт, не как новшество
- `POST /api/chat` — сообщение + опц. attachments (альтернатива `/turn`; определить при реализации).
- `GET /api/jobs/{id}` — статус Job (+progress, outputs).
- `POST /api/jobs/{id}/cancel` — отмена.
- `GET /api/capabilities` — список capabilities.
- `GET /api/workflows` — список workflow (со статусом lifecycle, включая UNKNOWN/UNKNOWN_RUNTIME).
- `GET /api/runtime` — RuntimeInfo.

### 7.3 Новые endpoints (проект, требуют approval)
- `GET /api/history?session_id=&capability=&limit=` — история ExecutionRecord (в т.ч. chain summary).
- `GET /api/jobs/{id}/events?session_id=` — повторный стрим событий конкретного Job (для восстановления).
- `GET /api/backends` — список BackendResource (health/state/queue_depth) — только если реально используется мультибэкенд.
- `POST /api/session` (создать сессию) — опционально.
- `GET /api/session` расширить полем `active_job_state` / `active_chain` (или брать из `/api/jobs/{id}`).

### 7.4 SSE-контракт (проект — расширение существующего)
Добавляемые типы событий (каждый — отдельный `event:` в SSE):
- `intent` (capability, params, rationale)
- `plan` (steps, workflow_id@version)
- `retry_started` / `retry_completed`
- `decision_failed`
- `feedback_request`
- `verification.started` / `verification.completed`
- (опц.) `dialog_state`

Формат payload — JSON, `type` + `session_id` + поля.

### 7.5 Error Model
- **Транспортные ошибки (HTTP/SSE):** 4xx — клиентские (bad json, missing session_id), 5xx — серверные/execution.
- **Ошибки агента:** приходят как `error` SSE-событие с `{error, kind}`; для Job-ошибок — `{error, error_class}` (`transient`/`permanent`/`verification`) + `_decision_reason`/`_decision_suggestions`.
- `AgentError` (планировщик/registry) — отображается как task FAILED с понятным сообщением.
- `Verifier` diagnostics (`VerificationDiagnostic`) — экспонировать в job status/результате.
- UI не должен маскировать ошибки; но и не должен показывать сырые traceback — человекочитаемое сообщение (+ детали при необходимости).

### 7.6 Authentication / Security
- Agent UI работает только на `127.0.0.1` (как и ComfyUI). Aутентификация не требуется (single-user localhost, соответствует §20/§3 PROJECT_SPEC).
- Никаких прод паролеи, токенов в URL; session_id — в localStorage (как сейчас).

### 7.7 Reconnect / State Recovery
- SSE (`EventSource`) автоматически переподключается. `SessionStream` (реплей-буфер) безопасен для поздней подписки (replay-safe).
- **Что происходит при обновлении страницы во время выполнения Job:**
  1. UI открывается → вызывает `GET /api/session?session_id=` → восстанавливает `dialog_state`, `active_job`, `active_asset`, `messages`, `unresolved`.
  2. Если `active_job` существует и ещё RUNNING → UI подписывается на `GET /api/jobs/{id}` (после реализации Job API) или повторно на `/events` (SessionStream отдаст уже записанные события).
  3. UI **не** теряет выполнение: Job уже выполняется в фоновом потоке backend; UI лишь переприсоединяется к нему.
  4. Пока Job API не реализован — fallback: `/api/session` + повторный `/events` (replay).

---

## 8. Взаимодействие пользователя с агентом

| Действие | Механика | Требует подтверждения? |
|----------|----------|------------------------|
| Отправка запроса | `POST /turn` (или `/api/chat`) | нет (запускается сразу) |
| Multi-turn | `turn()` с session_id; контекст сохраняется | нет |
| Clarification (awaiting_input) | UI отображает unresolved и ждёт новый ввод | да (пользователь должен дать недостающие входные ассеты/уточнение) |
| Confirmation (ask_user / awaiting_feedback / decision_failed) | UI показывает suggestions + feedback | да — агент НЕ продолжает без решения |
| Cancel | `POST /api/jobs/{id}/cancel` (проект; `WorkflowEngine.cancel` существует) | нет (немедленное действие) |
| Retry | повторный `POST /turn` (или server-side retry через max_attempts) | автоматический retry агент делает сам (M13); ручной — повторный ввод |
| Повторный запуск | из History — повтор `turn` с теми же параметрами | пользователь подтверждает (если меняются параметры) |
| Просмотр результата | `GET /asset/<id>` / preview | нет |
| Просмотр плана | событие/поля `plan` / `/api/session` | нет |
| Просмотр execution | SSE + `GET /api/jobs/{id}` | нет |
| Переход в ComfyUI | кнопка → `http://127.0.0.1:8188` | нет |

**Что требует подтверждения пользователя (проектом):**
- `awaiting_input` (не хватает входного ассета/параметра) — агент ждёт.
- `awaiting_feedback` / `ask_user` (M24) — агент спрашивает: улучшить/сменить параметры/отменить.
- (опц.) перед выполнением multi-step chain — возможность сначала показать план и подтвердить (design decision, не обязательный для v1).

**Что агент выполняет автоматически:**
- Многошаговые цепочки, retry (M13), adaptive planner (M16), param correction (M23), semantic verification (M14), reconciliation/recovery (M21) — всё на стороне Agent Core; UI лишь отображает ход.

---

## 9. UX для прозрачности агента (4 вопроса)

Интерфейс должен отвечать:
1. **Что я попросил?** — отображать исходный текст запроса (+) вложения.
2. **Что агент понял?** — intent/capability + constraints (params), без chain-of-thought.
3. **Что агент сейчас делает?** — plan/chain, selected workflow, Job state, progress, stage, backend.
4. **Что получилось?** — результат/Asset, preview, verification status, lineage.

**НЕ показывать:**
- внутренний chain-of-thought / скрытые рассуждения LLM;
- трафик между Provider и ComfyUI (байты, node-graph) — не требуется;
- внутренности node-graph (это ComfyUI's дело).

**Показывать (безопасные архитектурные артефакты):**
- intent (capability), plan (шаги), selected capability, workflow (`id@version`), execution status, verification (score/diagnostics), result (Assets).

---

## 10. Связь с Comfy Desktop

- Agent UI НЕ заменяет ComfyUI.
- Реальное выполнение: `Agent Core → WorkflowEngine → официальный Comfy Desktop → 127.0.0.1:8188`.
- Старый `C:\cd\ComfyUI_AMD\ComfyUI` вне проекта — не используется, не анализируется.
- Не создавать второй скрытый ComfyUI runtime.
- Agent UI даёт ссылку «Открыть Comfy Desktop» (`http://127.0.0.1:8188`) из зоны Execution.

---

## 11. Error / Recovery

### Восстановление после перезагрузки страницы
1. `GET /api/session` → восстановить snapshot (dialog_state, active_*, messages, unresolved).
2. `GET /api/jobs/{id}` (после реализации) → получить текущий Job state/progress.
3. Подписка на `/events` (replay) — не потерять события.

### Recovery после разрыва связи / backend сбой
- `WorkflowEngine` уже reconnect-safe (WS → `/history` fallback, AD-29 inv 5/6).
- `ClusterGateway.reconcile()` (M21) — определяет COMPLETED / NOT_ACCEPTED / UNKNOWN; при UNKNOWN — просит пользователя (MD-01), НЕ auto-failover. UI должен отобразить «состояние неизвестно, требуется решение пользователя» + RecoveryAction.
- `SessionManager` (M15) — восстанавливает сессию из persistence после рестарта.

### Ошибки frontend
- Сетевые ошибки: показать «соединение потеряно», ретраить подключение SSE автоматически (EventSource).
- Ошибка валидации (bad JSON, отсутствие session_id): понятные сообщения из error model.

---

## 12. Security

- Только `127.0.0.1` (и ComfyUI, и Agent UI).
- Без публичных endpoints.
- Не передавать секреты (`LLM_API_KEY`, `GEMINI_KEY`) в frontend — только на сервер через env (PROJECT_SPEC §20).
- Ассеты отдаются через `/asset/<id>` без path-traversal (AssetStore confinement, AD-15).
- Никаких произвольных shell/HTTP из UI в ComfyUI — UI взаимодействует только с Agent Core.

---

## 13. UX-принципы

1. **Прозрачность:** всегда видно, что агент понял и что делает (4 вопроса §9).
2. **Честность:** никаких fake progress / fake states. Если прогресс неизвестен — показывать state-based («выполняется…»), не выдумывать проценты.
3. **Отсутствие дублирования:** UI не имеет собственной логики выбора capability/workflow/planner. Только отображение + инициация.
4. **Отсутствие перегруза:** System/Providers — только если реально есть информация.
5. **Media-agnostic:** интерфейс preview выбирает тег по asset.type; никаких media-branch в frontend-логике состояния.
6. **Восстановимость:** потеря страницы не теряет задачу (recovery из backend).
7. **Действие перед отображением:** UI показывает состояние только после подтверждения от backend (SSE / REST), никогда не «предугадывает» результат.

---

## 14. Implementation Phases (кратко; детальный план — в AGENT_UI_IMPLEMENTATION_PLAN.md)

| Фаза | Название | Суть |
|------|----------|------|
| UI-0 | Audit | Завершён (этот документ) |
| UI-1 | Contracts / Events | Реализация задокументированных §21 endpoints + новые события (по approval) |
| UI-2 | Shell + Navigation | Vite+React shell, routing, session management |
| UI-3 | Conversation | Чат, вложения, история сообщений |
| UI-4 | Task / Plan | Current Task + Agent Plan зоны |
| UI-5 | Live Execution | Job status, progress, stage, cancel, ComfyUI link |
| UI-6 | Results / Assets | preview, lineage, verification, download |
| UI-7 | History | список задач + повторный запуск |
| UI-8 | Recovery / Error handling | переподключение, восстановление после reload |
| UI-9 | E2E validation | реальный прогон с Comfy Desktop |

> Порядок определён после аудита. UI-1 может частично совпадать с UI-2 (backend-контракт реализуется параллельно с заготовкой frontend, но ставить UI-1 первым — чтобы frontend имел стабильный слой данных).

---

## 15. DoD (для этапа проектирования)

- [x] Проведён аудит существующего Agent Core (ConversationAgent, Agent, Planner, WorkflowEngine, Registry, Provider, Job/Execution, Gateway, AssetStore, History, Verifier, SemanticVerifier).
- [x] Определена архитектурная роль Agent UI (Operator UI ≠ ComfyUI) и целевая схема потоков.
- [x] Описаны зоны информационной архитектуры (A–H).
- [x] Определена модель состояния UI как mapping реальных состояний (dialog_state + JobState + chain + decision), без второй state machine.
- [x] Описан Event Model: какие события существуют, какие отсутствуют, source of truth.
- [x] Описан API-контракт (существующие, задокументированные-нереализованные, новые-проект).
- [x] Описано взаимодействие пользователя, что требует подтверждения.
- [x] Описаны UX-принципы (4 вопроса) и связь с Comfy Desktop.
- [x] Описаны error/recovery/security.
- [x] Создан `AGENT_UI_IMPLEMENTATION_PLAN.md` (отдельный) с разбиением на A/B/C/D.
- [x] НЕ написано никакого production-кода, НЕ изменён backend/frontend, НЕ добавлены endpoints.

---

*Конец AGENT_UI_ARCHITECTURE.md*