# AGENT_UI_UI3_DESIGN.md — архитектурная проработка UI-3 (Conversation)

> **Статус:** DRAFT для утверждения. НИЧЕГО НЕ РЕАЛИЗОВАНО.
> **Scope:** зона A (Conversation) — чат, сообщения, вложения, статусы, clarification/confirmation.
> **Source of truth:** `docs/PROJECT_SPEC.md`, `docs/AGENT_UI_ARCHITECTURE.md` (APPROVED), `docs/AGENT_UI_IMPLEMENTATION_PLAN.md` (UI-1/UI-2 выполнены).
> **Дата:** 2026-09-08

---

## 1. Цель документа

Подготовить UI-3 к реализации:
1. Определить судьбу решений **D-1..D-9** (из IMPLEMENTATION_PLAN) применительно к Conversation-сценариям.
2. Сверить **существующие backend-контракты** с будущими UX-сценариями зоны Conversation.
3. Предложить **минимальные изменения** (только те, без которых UX-сценарии невозможны).
4. НЕ реализовывать ничего до утверждения.

---

## 2. UX-сценарии зоны Conversation (что должен уметь пользователь)

| # | Сценарий | Что видит пользователь | Текущий backend-контракт | Достаточно? |
|---|----------|------------------------|--------------------------|-------------|
| S1 | Отправить текстовый запрос | Своё сообщение + события старта/результата | `POST /api/chat` (UI-1) + SSE `start/status/result` | ✅ да |
| S2 | Увидеть ход выполнения в диалоге | Статус, progress %, chain_step | SSE `status/progress/chain_step` | ✅ да |
| S3 | Увидеть результат в чате | Preview asset + workflow | SSE `result` (`active_asset`, `preview`, `active_workflow`) | ✅ да |
| S4 | Увидеть ошибку выполнения | Понятное сообщение + причина | SSE `error` (`error`, `kind`) | ⚠️ частично: `error_class`/`decision_reason`/`suggestions` **не стримятся** |
| S5 | Clarification (не хватает входного ассета) | Вопрос агента + что предоставить | `AgentError` → SSE `error`; `ctx.unresolved` только в `/api/session` ПОСЛЕ факта | ⚠️ частично: пользователь видит ошибку, но **не как диалоговое ожидание ввода** |
| S6 | Confirmation (M24 `ask_user`) | Предложения агента + выбор пользователя | `feedback_request`/`decision_failed` — только в `ctx.messages`, **НЕ в SSE** | ❌ нет: UI не узнает о вопросе без polling `/api/session` |
| S7 | Retry после ошибки | Повторная отправка запроса | Повторный `POST /api/chat` — работает | ✅ да (ручной retry); авто-retry M13 виден только как пауза |
| S8 | Обновить страницу во время выполнения | Восстановить диалог | `/api/session` snapshot + replay `/events` | ⚠️ частично: replay отдаёт события последнего turn; предыдущие turn'ы — только через `messages` в snapshot |
| S9 | Вложение (input asset) в чат | Прикрепить файл/сослаться на asset | `assets` в payload `/turn`, **но нет endpoint загрузки файлов** (`POST /api/assets` §21 не реализован) | ❌ нет: файл нельзя загрузить из UI |
| S10 | Multi-turn контекст («сделай её ночью») | Агент использует active_asset | `ConversationAgent.turn` (M7/M9.1) | ✅ да |
| S11 | Job-статус конкретного сообщения | Открыть детали Job | `GET /api/jobs/{id}` (UI-1) | ✅ да |
| S12 | Отменить выполняющуюся задачу | Кнопка Cancel в чате | `POST /api/jobs/{id}/cancel` (UI-1) | ⚠️ ограниченно: cancel работает для Job из истории; live-Job в `turn()` не хранится как объект → cancel реально не прервёт текущий `engine.execute` (см. D-5) |

**Итог сверки:** S1–S3, S7, S10, S11 закрыты существующими контрактами. Критичные разрывы: **S6 (confirmation), S9 (загрузка ассетов), S4/S5 (детали ошибки/clarification), S8 (полнота recovery), S12 (реальный cancel)**.

---

## 3. Решения D-1..D-9 — формулировка применительно к UI-3

### D-1. Новые SSE-события
**Что предлагается (минимум, без которого Conversation неполон):**

| Событие | Закрывает сценарий | Хук (минимальный) |
|---------|--------------------|--------------------|
| `dialog_state` (поле в существующих `start`/`status`/`result`/`error` ИЛИ отдельное событие) | S5, S6 — UI видит `awaiting_input` / `awaiting_feedback` | Добавочное поле в `stream.push()` в `run_turn` — без изменения `turn()` |
| `decision_failed` (прокинуть из `ctx.messages` после `turn`) | S6 — причина + suggestions | После возврата из `turn()`: если последний message имеет `type in (feedback_request, decision_failed, retry_*)` — отправить его в stream как событие `agent_message` |
| `agent_message` (обобщённое) — альтернатива пяти отдельным типам | S4, S5, S6 | Один новый тип вместо пяти; payload = запись из `ctx.messages` |

**Варианты:**
- **Вариант A (рекомендуемый):** одно новое событие `agent_message` + поле `dialog_state` в terminal-событиях. Минимум изменений: только в `app/ui.py::run_turn`, `turn()` НЕ трогается. Source of truth остаётся `ctx.messages`/`ctx.dialog_state`.
- **Вариант B:** полная таблица событий из Event Model (intent/plan/retry/...). Требует хуков в `turn()` — глубже, отложить до UI-4/UI-5.

**Требует:** approval (новый SSE-тип = расширение контракта /events).

### D-2. Новые endpoints (`/api/history`, `/api/jobs/{id}/events`, `/api/backends`)
**Для UI-3 не требуются.** Conversation восстанавливается из `/api/session` (messages уже в snapshot). Отложить до UI-7 (History). **Рекомендация: не одобрять сейчас.**

### D-3. Расширение `/api/session` полем `active_job_state`
**Для UI-3 требуется ограниченно:** после reload пользователь должен понять, что задача ещё идёт (S8). Сейчас snapshot даёт `active_job` (id), но не state.
**Минимальный вариант:** UI после recovery вызывает `GET /api/jobs/{active_job}` (уже реализовано в UI-1) — **изменение `/api/session` НЕ требуется**. **Рекомендация: не менять; закрывается существующим UI-1 контрактом.**

### D-4. Судьба `app/ui.py` (backend для React)
**Факт UI-1/UI-2:** §21 endpoints реализованы в `app/ui.py`, работает, тесты зелёные.
**Рекомендация:** зафиксировать как **текущее решение**: backend API живёт в `app/ui.py`; вынос в `app/api/` — только при необходимости (не в UI-3). Позволяет не менять импорты/тесты.

### D-5. Cancel для live-Job
**Проблема (S12):** `run_turn` выполняет `agent.turn()` в фоновом потоке; Job-объект создаётся внутри `engine.execute` и наружу не отдаётся до завершения. `cancel_job(prompt_id)` в UI-1 находит запись только в истории — т.е. **после** завершения. Реальная отмена живого выполнения сейчас невозможна через API.
**Минимальное изменение (предложение):** `ComfyUIServer` хранит `active_jobs: dict[session_id → threading.Event/flag]`; в `run_turn` передавать в `turn()` (или проверять между попытками retry) флаг отмены; при cancel — ставить флаг и вызывать `engine.cancel` c provider. **Но:** прерывание внутри `engine.execute` (блокирующий WS-track) требует либо cooperative-check в цикле retry, либо не прерывать текущий POST, а помечать следующую попытку отменённой.
**Вариант A (минимальный, рекомендуемый):** «мягкая отмена» — flag в `ComfyUIServer`; отмена срабатывает на границе попыток retry (M13) и на границе шагов chain (M18); текущий ComfyUI-граф дозавершается физически (AD-19 семантика это допускает). Изменения: только `app/ui.py` + опциональный параметр `cancel_check: Callable[[], bool]` в `turn()` (добавочный kwarg с default=None — обратимо совместимо).
**Вариант B:** немедленный `provider.cancel(prompt_id)` — требует, чтобы prompt_id был известен до завершения; этого нет в текущем потоке без изменения `engine.execute`. Не рекомендую для UI-3.
**Требует:** approval (новый kwarg в `turn()`).

### D-6. Verification-хук (`verification.started/completed`)
**Для UI-3 не требуется** (verification отображается в UI-6). Verification уже отражается в итоговом state (SUCCESS/FAILED+`verification`). **Рекомендация: отложить до UI-6.**

### D-7. Подтверждение перед multi-step chain
**Для UI-3 допустимо без изменения Core:** UI-3 может показывать chain-прогресс через существующий `chain_step`. Полное «show plan → confirm → execute» меняет семантику `turn()` — **рекомендация: отложить; UI-3 показывает выполнение как есть**. Если автор хочет confirmation — это отдельное решение с стадией в `turn()` (изменение поведения Core).

### D-8. `GET /api/backends`
**Для UI-3 не требуется** (System/Providers — зона H, опциональна). **Рекомендация: не одобрять сейчас.**

### D-9. Порты / интеграция dev-server
**Факт UI-2:** Vite dev на 5173 c proxy → 8189. Для постоянной работы нужны варианты:
- **Вариант A (рекомендуемый):** `app/ui.py` раздаёт собранный `agent_ui/dist/` как статику по `/app/` (или на `/`); один процесс, порт 8189, без Node в runtime. Изменение: `_send_html`/роут в `app/ui.py` (сервинг файлов из dist) — контракты не меняются.
- **Вариант B:** держать два процесса (uv/vite dev) — только для разработки.
**Требует:** approval только для Варианта A (изменение выдачи `/`); существующий inline-UI оставить на отдельном пути (напр. `/legacy`) для совместимости M9-тестов — либо не трогать `/` вовсе и отдавать React на `/app`.

---

## 4. Сводная таблица решений (что предлагаю утвердить)

| Решение | Рекомендация | Минимальное изменение | Что НЕ делаем |
|---------|--------------|------------------------|----------------|
| D-1 | ✅ Одобрить Вариант A: событие `agent_message` + `dialog_state` в terminal-событиях | `run_turn` в `app/ui.py`; `turn()` не трогаем | Пять отдельных типов событий; хуки в `turn()` |
| D-2 | ❌ Отклонить для UI-3 | — | History/backends/jobs-events |
| D-3 | ❌ Не требуется (закрыто `GET /api/jobs/{id}`) | — | Изменение `/api/session` |
| D-4 | ✅ Зафиксировать: API в `app/ui.py` | нет изменений | Вынос `app/api/` |
| D-5 | ✅ Одобрить Вариант A: мягкая отмена (flag + `cancel_check` kwarg) | `ComfyUIServer.active_jobs` + добавочный kwarg `cancel_check` в `turn()` (default None) | Немедленное прерывание внутри `engine.execute` |
| D-6 | ❌ Отложить до UI-6 | — | verification-хуки |
| D-7 | ❌ Отложить (chain показываем как есть через `chain_step`) | — | confirmation-стадия в `turn()` |
| D-8 | ❌ Отклонить для UI-3 | — | `/api/backends` |
| D-9 | ⏳ На выбор автора: A (статика dist в `app/ui.py`, React на `/app`) или B (dev-процессы) | A: статик-роут в `app/ui.py` | Снос legacy inline-UI |

---

## 5. Backend-контракты vs UX-сценарии: что минимально необходимо

### 5.1 Достаточно без изменений (используем как есть)
- `POST /api/chat` (+`assets` в payload — когда появится загрузка), SSE `start/status/progress/chain_step/result/error`, `/api/session`, `/asset/<id>`, `GET /api/jobs/{id}`, `POST /api/jobs/{id}/cancel`.

### 5.2 Минимальные изменения (все — с согласования выше)
1. **`agent_message` событие** (D-1A): после `turn()` в `run_turn` просмотреть новые записи `ctx.messages` (по индексу до/после) и отправить новые как `agent_message`. Закрывает S4/S5/S6: error_class, decision reason/suggestions, feedback_request, retry-уведомления — **данные уже есть в Core**, просто не стримятся.
2. **`dialog_state` в terminal-событиях** (D-1A): поле в `result`/`error` payload — одно значение из `ctx.dialog_state`. Закрывает отображение `awaiting_input`/`awaiting_feedback`/`error`.
3. **Мягкая отмена** (D-5A): `ComfyUIServer.active_cancel_flags: dict[str, threading.Event]`; `run_turn` регистрирует флаг; `turn(..., cancel_check=...)` проверяет между попытками retry и шагами chain; `POST /api/jobs/{id}/cancel` ставит флаг. AD-19: физический граф дозавершается, состояние → CANCELLED на границе.
4. **(Опционально, D-9A)** статика `agent_ui/dist` на `/app` в `app/ui.py`.

### 5.3 Разрыв, требующий отдельного §21-эндпоинта (был задокументирован, не реализован)
- `POST /api/assets` — загрузка файла-вложения (S9). Это **существующий задокументированный контракт §21** («POST /api/assets — загрузка ассета»), не новый D. Предлагаю включить в UI-3 как реализацию утверждённого контракта: ingest через `AssetStore.ingest` → вернуть `{asset_id}`; UI затем передаёт `assets[role]={"asset_id"}` в `/api/chat`.
  - Вопрос автору: подтвердить включение `POST /api/assets` в UI-3 (реализация существующего §21) или отложить вложения на позже.

### 5.4 Что остаётся вне UI-3 (переносится)
- intent/plan отображение (UI-4, ждёт D-1B или `/api/session`-поля), verification (UI-6), History (UI-7), reconnect-hardening (UI-8), E2E с живым Comfy Desktop (UI-9).

---

## 6. Риски минимальных изменений

1. **Replay-буфер и `agent_message`:** события добавятся в `SessionStream` — существующие потребители (M9 inline UI, тесты) не подписаны на новый тип; `EventSource` игнорирует неизвестные события → обратная совместимость сохранена. Тесты SSE-набора (`test_ui_sse_progress_events` проверяет подмножество) не сломаются.
2. **`cancel_check` kwarg:** default=None → все существующие вызовы `turn()` работают без изменений (обратимо совместимо, SAFE CHANGE форма). Требуется добавить тест: отмена на границе retry.
3. **AD-19 семантика отмены:** UI обязан показывать «отмена запрошена» и финальное состояние из `result` (CANCELLED), а не предполагать немедленную остановку.
4. **`/api/assets` (если одобрен):** лимиты размеров (MAX_UPLOAD_BYTES, AD-21), mime-валидация, path-confinement — через существующий `AssetStore.ingest`; ограничение размера на уровне http-хендлера.
5. **dialog_state в payload:** дублирование `dialog_state` (snapshot + событие) — источник истины остаётся `ConversationContext`; событие — только уведомление (не рассинхронизирует, т.к. терминальное).

---

## 7. Предлагаемый состав работ UI-3 (после approval — отдельной командой)

**Backend (минимум):**
1. D-1A: `agent_message` + `dialog_state` в terminal-событиях (`app/ui.py::run_turn`).
2. D-5A: мягкая отмена (`active_cancel_flags` + `cancel_check` kwarg в `turn()`).
3. (по approval) `POST /api/assets` — реализация §21.
4. (по выбору D-9A) статика React на `/app`.

**Frontend (`agent_ui/`):**
5. Зона Conversation: список сообщений (user/agent/system/error) с привязкой к job; индикатор `dialog_state`; отображение `agent_message` (причины, suggestions); вложение файлов (если `/api/assets` одобрен); Cancel-кнопка активной задачи.

**Тесты:**
6. SSE содержит `agent_message` при feedback_request/decision_failed (unit, FakeProvider + принудительная запись в ctx.messages).
7. `dialog_state` присутствует в terminal payload.
8. Cancel на границе retry: max_attempts=3, флаг после первой попытки → CANCELLED, не SUCCESS.
9. (если одобрен) `POST /api/assets` → asset_id → `/api/chat` с `assets[role]={"asset_id"}`.
10. Регресс: существующие §21 + чистые функции UI + non-turn M9/M12.

---

## 8. Ожидание решений автора (checklist для approval)

- [ ] D-1: одобрить Вариант A (`agent_message` + `dialog_state`)?  
- [ ] D-5: одобрить мягкую отмену (`cancel_check` kwarg)?  
- [ ] `POST /api/assets`: включить в UI-3 (реализация §21)?  
- [ ] D-9: Вариант A (статика dist на `/app`) или B (dev-процессы)?  
- [ ] D-2/D-3/D-6/D-7/D-8: подтвердить отклонение/отложение.  
- [ ] D-4: зафиксировать backend в `app/ui.py`.

**До утверждения — ничего не реализуется.**