# AGENT_UI_IMPLEMENTATION_PLAN.md

> **Статус:** Архитектура APPROVED автором; UI-1 и UI-2 реализованы (см. раздел «Статус реализации»); UI-3..UI-9 — ждут команды.
> **Source of truth:** `docs/AGENT_UI_ARCHITECTURE.md` (проект), `docs/PROJECT_SPEC.md` (source of truth).
> **Дата:** 2026-09-08

---

## Важное разбиение: A / B / C / D

Чтобы не смешивать существующий Agent Core с новой UI-обвязкой, все работы делятся на четыре категории:

- **A. Что уже существует и можно использовать** — ничего не меняем, только подключаемся.
- **B. Что необходимо добавить в backend/API** — реализация существующих задокументированных контрактов (§21) + новые events/endpoints (проект).
- **C. Что необходимо реализовать во frontend** — новый Vite+React Operator UI.
- **D. Что является архитектурным решением и требует отдельного approval** — новые контракты, изменение сигнатур, изменение поведения Agent Core.

---

## A. Что уже существует и можно использовать (без изменений)

| Что | Где | Назначение для UI |
|-----|-----|-------------------|
| `POST /turn` | `app/ui.py` | запуск turn |
| `GET /events?session_id=` | `app/ui.py` | SSE: start/status/progress/chain_step/result/error |
| `GET /api/session?session_id=` | `app/ui.py` | snapshot `ConversationContext.as_dict()` (recovery) |
| `GET /asset/<id>` | `app/ui.py` | preview/скачивание |
| `POST /api/prompt/suggest` | `app/ui.py` | M11 подсказка промпта |
| `POST /api/feedback`, `GET /api/feedback/history` | `app/ui.py` | M17 обратная связь |
| `ConversationContext.as_dict()` | `app/conversation.py` | источник состояния для recovery |
| `dialog_state` | `app/conversation.py` | реальные states диалога |
| `Job` + `JobState` + все метаданные (attempt, error_class, chain_id, backend_execution_identity, decision_*) | `app/engine/job.py` | статус выполнения |
| `Verifier.verify_with_diagnostics()` | `app/engine/verifier.py` | verification diagnostics |
| `ExecutionHistory` (record, chain summary, dispatch) | `app/engine/history.py` | история задач |
| `ClusterGateway.list_backends()` + `BackendResource` (health/state) | `app/resource/models.py` + `gateway.py` | backend health (опционально) |
| `BackendCatalog` / `BackendSpec` | `app/registry/backends.py` | известные backend'ы |
| `SessionManager` / `ContextPersistence` | `app/context/*` | восстановление сессии после рестарта |
| `TaskDecomposer` / `ExecutionChain` / `Composer` / `CompositionResult` | `app/planner/*`, `app/engine/chain.py` | plan/chain отображение |
| `SemanticVerifier` score | `app/engine/semantic_verifier.py` | verification (при наличии OpenRouter) |

## B. Что необходимо добавить в backend/API

### B.1 Реализация задокументированных контрактов (PROJECT_SPEC §21) — не новые решения
- `POST /api/chat` — аналог `/turn` (сообщение + attachments). Повторяет поведение `/turn`.
- `GET /api/jobs/{id}` — статус Job: `{prompt_id, capability, workflow_id@version, state, progress, attempt, error_class, error, output_assets, backend_execution_identity, chain_id, chain_step_index, decision_*}`.
- `POST /api/jobs/{id}/cancel` — вызывает `WorkflowEngine.cancel(job, provider)`. **Ограничение:** cancel доступен только для активного Job текущей сессии (single-user localhost). Для chain-cancel реализовать отмену текущего шага (требует внутреннего состояния — см. D).
- `GET /api/capabilities` — `Agent.capabilities()`.
- `GET /api/workflows` — список workflows с lifecycle (через `WorkflowRegistry`; можно отдавать `UNKNOWN`/`AVAILABLE`/`UNAVAILABLE`).
- `GET /api/runtime` — `RuntimeInfo`.

### B.2 Новые endpoints (проект, требуют approval — см. D)
- `GET /api/history?session_id=&capability=&limit=` — список `ExecutionRecord` (+ `chain_summary` при `chain_id`).
- `GET /api/jobs/{id}/events?session_id=` — повторный стрим событий конкретного Job (для восстановления после reload).
- `GET /api/backends` — список `BackendResource` (health/state/queue_depth). **Только если реально используется мультибэкенд** (иначе не добавлять — см. Non-goals «не перегружать»).

### B.3 Новые SSE-события (проект, требуют пропагирующих хуков в `run_turn` / `turn` / `engine`)
- `intent` (capability, params, rationale) — после `planner.plan`.
- `plan` (steps/workflow_id@version/params) — после `prepare` / до chain.
- `retry_started` / `retry_completed` — из M13 loop.
- `decision_failed` — из M22.
- `feedback_request` — из M24 (`dialog_state=awaiting_feedback`).
- `verification.started` / `verification.completed` — требуется хук в `turn()` вокруг `Verifier`/`SemanticVerifier`.
- (опц.) `dialog_state` — при каждом изменении.

> **Реализация:** все хуки — только добавочные `on_event`/`on_state` callback'и, передаваемые в уже существующие методы (например, `turn(..., on_event=...)`). Никаких изменений существующей сигнатуры без D. Все события **не заменяют** существующие `start/status/progress/result/error`, а дополняют их.

## C. Что необходимо реализовать во frontend (новый Vite+React)

### C.1 Shell + Navigation (UI-2)
- Vite + React + TypeScript.
- SPA с левой панелью (сессии) и основной областью (зоны A–H из архитектуры).
- localStorage session_id (как в текущем `app/ui.py`).
- Один API-клиент (fetch wrapper) + SSE client (EventSource с auto-reconnect).

### C.2 Conversation (UI-3)
- Чат: сообщения пользователя + агента, вложения (загрузка через `/api/chat` или `/turn` с `assets`).
- Привязка сообщения → задача → Job.
- Показ `dialog_state`.

### C.3 Task / Plan (UI-4)
- Зона Current Task: запрос, intent, constraints (params), статус, clarification/confirmation.
- Зона Agent Plan: шаги (capability/workflow), основанные на событиях `intent` / `plan` / `chain_step`.

### C.4 Live Execution (UI-5)
- Job card: ID, state, capability, workflow, backend, progress (честный), stage (chain), elapsed, retries/errors.
- Кнопка Cancel (`POST /api/jobs/{id}/cancel`).
- Кнопка «Открыть Comfy Desktop» → `http://127.0.0.1:8188`.

### C.5 Results / Assets (UI-6)
- Preview (img/video/audio по asset.type — media-agnostic).
- Asset id, тип, lineage, verification status (score/diagnostics из результата/Job API).
- Скачивание (ссылка `/asset/<id>`).

### C.6 History (UI-7)
- Список задач из `/api/history` (+ chain summary).
- Фильтр по capability/состоянию.
- Повторный запуск: отправить тот же запрос заново (новый turn — без изменения истории).

### C.7 Recovery / Error handling (UI-8)
- При reload: `GET /api/session` → восстановить snapshot → если active_job — подписаться на `/api/jobs/{id}` / `/events`.
- Сетевые ошибки: бананер, авто-retry EventSource.
- Отображение error_class / decision_reason / suggestions.

### C.8 E2E validation (UI-9)
- Тесты на реальном `app/ui.py` (или новом backend) + Comfy Desktop.
- Сохранение совместимости M9/M12 тестов: `app/ui.py` продолжает работать (inline chat + /turn + /events), новый React-UI обращается к тем же endpoint'ам. Старый inline-UI не удалять до отдельного решения.

## D. Что является архитектурным решением и требует отдельного approval

| № | Решение | Почему требует approval |
|---|---------|--------------------------|
| D-1 | Новые SSE-события (`intent`, `plan`, `retry_*`, `decision_failed`, `feedback_request`, `verification.*`, `dialog_state`) | Добавляют hooks в существующий поток `ConversationAgent.turn()` / `engine` — расширение контрактов (нужен AD) |
| D-2 | Новые endpoints `/api/history`, `/api/jobs/{id}/events`, `/api/backends` | Новые API-контракты (не в §21) |
| D-3 | Расширение `/api/session` полем `active_job_state` (или вынос в Job API) | Дублирование источника состояния; нужно решить, где source of truth (рекомендация: Job API, не session) |
| D-4 | Судьба `app/ui.py`: оставить как есть + добавить `/api/*` в него, ИЛИ вынести API в отдельный модуль (`app/api/`) и UI оставить отдельно | Не предрешаем. Рекомендация: сперва реализовать API в `app/ui.py` (минимально), позже при необходимости вынести. Требует согласования, так как `/turn` и `/events` — уже работающий контракт |
| D-5 | Cancel для chain (отмена текущего шага) | `ExecutionChain.cancel()` существует, но не интегрирован в `turn()`; нужен хук. Требует изменения `ConversationAgent` |
| D-6 | Verification-хук (`verification.started/completed`) | Прямое вмешательство в `turn()` (вызов Verifier/SemanticVerifier) |
| D-7 | Подтверждение перед выполнением multi-step chain | UX-решение: может изменить поведение `turn()` (добавить стадию confirmation). Требует согласования |
| D-8 | `GET /api/backends` (экспозиция health) | Публикация инфраструктурных данных UI; может быть избыточно для single-backend |
| D-9 | Смена порта Agent UI (текущий 8189) или добавление отдельного dev-server для React | Инфраструктурное решение интеграции frontend/backend |

> Все D-решения фиксируются как предложения в DECISION_LOG и реализуются ТОЛЬКО после approval автора. Ни одно из них не является обязательным для UI-0/UI-1/UI-2 базовой части.

---

## Этапы (последовательные, с зависимостями)

```
UI-0 (готово — этот план)
  ↓
UI-1 Contracts/Events  ──┐
  ↓                       │ (backend готов для UI-2+)
UI-2 Shell + Navigation ←─┘
  ↓
UI-3 Conversation
  ↓
UI-4 Task / Plan
  ↓
UI-5 Live Execution
  ↓
UI-6 Results / Assets
  ↓
UI-7 History
  ↓
UI-8 Recovery / Errors
  ↓
UI-9 E2E validation (реальный Comfy Desktop)
```

### Детали по фазам

| Фаза | Содержание | Зависит от | DoD (минимальный) |
|------|-----------|------------|--------------------|
| **UI-1** | Реализовать B.1 (§21 endpoints) + **базовые** события B.3, не затрагивающие архитектуру (plan/intent на этапе старта уже есть в `start` — можно сначала отдавать их в `start`-событии, без новых типов; retry/decision — добавить если approval) | D-решения по B.3 (если approval) | `GET /api/jobs/{id}`, `/api/capabilities`, `/api/workflows`, `/api/runtime` работают; существующие M9/M12 тесты зелёные; никакие существующие контракты не сломаны |
| **UI-2** | Vite+React shell, роутинг, session management, SSE client, API client | UI-1 | SPA открывается на 127.0.0.1, session_id сохр., SSE-подписка работает |
| **UI-3** | Чат + вложения | UI-2 | Отправка запроса, отображение сообщений, вложения (через /turn assets) |
| **UI-4** | Current Task + Plan зоны | UI-3 + события intent/plan (если одобрены — иначе из /api/session) | Отображаются запрос, intent, constraints, plan |
| **UI-5** | Job execution, progress, stage, cancel, ComfyUI link | UI-4 + `/api/jobs/{id}` + (если одобрено) events | Виден Job state, честный прогресс, cancel работает для активного Job |
| **UI-6** | Assets preview, lineage, verification | UI-5 | Preview по asset.type; verification status отображается |
| **UI-7** | History + повторный запуск | `/api/history` (B.2, если одобрено) | Список задач, повторный запуск работает |
| **UI-8** | Recovery после reload, error handling, reconnect | UI-2…7 | Reload сохраняет диалог; ошибки отображаются без traceback |
| **UI-9** | E2E: реальный прогон с Comfy Desktop | все | Полный путь: запрос → intent → plan → Job → verify → результат; старые M9/M12 тесты зелёные; новый React-UI работает параллельно со старым inline |

---

## Риски

1. **Совместимость M9/M12 тестов.** Любое изменение `app/ui.py` (добавление `/api/*`) не должно удалять/менять существующие `/turn`, `/events`, `/api/session`, `/asset/`. → UI-1 добавляет только новые endpoint'ы, старый код не трогает.
2. **Нарушение «UI не хранит state».** Frontend может захотеть локальный optimistic state → риск рассинхрона. → Запрет: frontend хранит только кэш отображения; recovery всегда через `/api/session`/`/api/jobs`.
3. **Добавление events требует изменения контракта.** → Все event-hooks — D-решения; одобряются заранее.
4. **Cancel margin:** `WorkflowEngine.cancel` помечает job CANCELLED, но backend может успеть создать частичный output (AD-19). → UI показывает «отмена запрошена», точный исход — из Job API.
5. **Verification sync:** в текущем коде verification синхронна внутри `turn` (после SUCCESS) — UI может не увидеть VERIFYING как отдельное состояние, пока не добавлен `verification.started`. → UI показывает VERIFYING по факту `result` + наличию score в ответе (опционально).
6. **Single-backend конфигурация.** Если используется один local backend, панель System/Providers может быть пустой → не показывать зону H при отсутствии данных.

---

## DoD (итоговый, для завершения всего этапа проектирования)

- [x] Создан `docs/AGENT_UI_ARCHITECTURE.md` (роль, зоны, state mapping, event model, API, UX, recovery, security).
- [x] Создан `docs/AGENT_UI_IMPLEMENTATION_PLAN.md` с разбиением A/B/C/D.
- [x] `AGENTS.md` дополнен правилами Agent UI (13 правил из задачи).

## Статус реализации (после approval автора — UI-1 и UI-2 выполнены)

- [x] **UI-1 выполнен:** реализованы §21 endpoints в `app/ui.py` (`POST /api/chat`, `GET /api/jobs/{id}`, `POST /api/jobs/{id}/cancel`, `GET /api/capabilities`, `GET /api/workflows`, `GET /api/runtime`). Без новых SSE-событий, без D-решений. Тесты: `tests/test_ui_section21.py` — **8/8 PASSED**.
- [x] **UI-2 выполнен:** Vite+React shell `agent_ui/` (session в localStorage, SSE-подписка на существующие события, recovery через `/api/session`, §21 API client). Build: `npm run build` — OK. Тесты чистых функций: `node --test` — **8/8 PASSED**.
- [x] Ни одно D-решение (D-1..D-9) не принято самостоятельно; новые события/поведение Core не добавлялись.
- [x] Регресс: существующие M9/M12 тесты — падения идентичны pre-existing (окружение: WS-таймаут к 127.0.0.1:9999 без живого ComfyUI); все без turn-а тесты зелёные.
- [x] Остановка после UI-2: дальнейшие фазы (UI-3..UI-9) требуют отдельной команды.

---

*Конец AGENT_UI_IMPLEMENTATION_PLAN.md*