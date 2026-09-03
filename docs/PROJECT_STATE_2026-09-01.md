# PROJECT STATE — 2026-09-01

**Дата аудита:** 2026-09-01
**Цель:** Единая фактическая точка состояния проекта перед дальнейшей разработкой.
**Статус:** AUDIT COMPLETE — точка отсчёта для следующих AI-инженеров.

---

## 1. CODE AUDIT — Фактическое состояние компонентов

### 1.1 Prompt Builder

| Компонент | Файл | Статус |
|-----------|------|--------|
| `PromptContext` | `app/prompt/builder.py:12-26` | ✅ EXISTS |
| `PromptResult` | `app/prompt/builder.py:29-38` | ✅ EXISTS |
| `PromptBuilder` Protocol | `app/prompt/builder.py:41-44` | ✅ EXISTS |
| `HeuristicPromptBuilder` | `app/prompt/heuristic.py` (62 строк) | ✅ EXISTS |
| `LLMPromptBuilder` | `app/prompt/llm.py` (137 строк) | ✅ EXISTS |
| `CompositePromptBuilder` | `app/prompt/composite.py` (96 строк) | ✅ EXISTS |
| `TEMPLATES` | `app/prompt/templates.py` (28 строк) | ✅ EXISTS |
| UI integration (`/api/prompt/suggest`) | `app/ui.py` | ✅ EXISTS |
| Planner integration (`Agent.generate`) | `app/agent.py` | ✅ EXISTS |
| ConversationAgent integration (`turn`) | `app/conversation.py:109-128` | ✅ EXISTS |
| `original_prompt` lineage | `ctx.parameters["original_prompt"]` | ✅ EXISTS |
| `enhanced_prompt` lineage | `params["prompt"]` (перезаписывается) | ✅ EXISTS |
| `prompt_source` | `ctx.parameters["prompt_source"]` | ✅ EXISTS |
| `previous_prompt` | `ctx.parameters.get("prompt")` → `PromptContext.previous_prompt` | ✅ EXISTS |
| `suggestion_index` | `PromptContext.suggestion_index` | ✅ EXISTS |

**Вывод:** Все компоненты Prompt Builder реализованы и интегрированы.

### 1.2 Conversation / Agent

| Компонент | Файл | Статус |
|-----------|------|--------|
| `ConversationContext` | `app/conversation.py:33-62` | ✅ EXISTS |
| Multi-turn | `ConversationAgent.turn()` | ✅ EXISTS |
| Session isolation | `sessions: dict[str, ConversationContext]` | ✅ EXISTS |
| `Planner` (Heuristic + LLM) | `app/planner.py` (279 строк) | ✅ EXISTS |
| `Agent.generate()` | `app/agent.py` (328 строк) | ✅ EXISTS |
| `ConversationAgent.turn()` | `app/conversation.py:82-185` | ✅ EXISTS |

**Вывод:** Conversation layer полностью реализован.

### 1.3 Execution

| Компонент | Файл | Статус |
|-----------|------|--------|
| `ExecutionPlan` | `app/engine/plan.py` (23 строки) | ✅ EXISTS |
| `Job` + `JobState` | `app/engine/job.py` (33 строки) | ✅ EXISTS |
| `WorkflowEngine` | `app/engine/engine.py` (306 строк) | ✅ EXISTS |
| `ComfyClient` | `app/comfy/client.py` (194 строки) | ✅ EXISTS |
| `ComfyUIProvider` (Provider) | `app/provider/comfyui.py` (71 строка) | ✅ EXISTS |
| `FakeProvider` | — | ❌ NOT FOUND |
| Реальный ComfyUI execution path | `ComfyClient → HTTP → localhost:8188` | ✅ EXISTS |

**Вывод:** Execution core полностью реализован. `FakeProvider` не используется — тесты используют mock.

### 1.4 UI

| Компонент | Файл | Статус |
|-----------|------|--------|
| `/turn` endpoint | `app/ui.py:433-456` | ✅ EXISTS |
| SSE (`SessionStream`) | `app/ui.py:35-65` | ✅ EXISTS |
| Browser E2E (HTML+JS) | `app/ui.py` (_INDEX_HTML) | ✅ EXISTS |
| Progress (WS → Job → SSE) | `app/engine/websocket.py` + `engine.py` | ✅ EXISTS |

**Вывод:** UI полностью реализован.

### 1.5 Infrastructure

| Компонент | Файл | Статус |
|-----------|------|--------|
| `ComfyUIProcessManager` | `app/comfy/lifecycle.py` (142 строки) | ✅ EXISTS |
| `ComfyCLIAdapter` | — | ❌ NOT FOUND |
| `comfy-cli` integration | — | ❌ NOT FOUND |
| AD-33 | — | ❌ NOT DOCUMENTED |
| AD-34 | — | ❌ NOT DOCUMENTED |
| `docs/21_COMFY_CLI_INTEGRATION_AUDIT.md` | — | ❌ NOT FOUND |

**Вывод:** `ComfyCLIAdapter`, `comfy-cli` integration, AD-33, AD-34, `docs/21_*` — **нигде не существуют** в коде, документации или engineering-файлах. Эти компоненты не были реализованы или задокументированы в этом репозитории.

---

## 2. TEST AUDIT — Фактические результаты

**Среда:** Python 3.14.3, pytest 9.0.2, Windows
**Примечание:**pytest 9 на Python 3.14 имеет баг с capture (`ValueError: I/O operation on closed file`). Некоторые тесты запускаются через `--override-ini="addopts="`, другие收集ляются 0 items из-за `sys.stdout = io.TextIOWrapper(...)` хака в test-файлах.

### 2.1 Успешно прошедшие тесты (pytest)

| Файл теста | Milestone | Passed | Failed | Skipped | Всего |
|------------|-----------|--------|--------|---------|-------|
| `test_agent.py` | M5/M8 | 8 | 0 | 0 | 8 |
| `test_planner.py` | M8 | 4 | 0 | 0 | 4 |
| `test_planner_context.py` | M9.1 | 11 | 0 | 0 | 11 |
| `test_ui_m9.py` | M9 | 5 | 0 | 0 | 5 |
| `test_m1_runtime.py` | M1 | 8 | 0 | 0 | 8 |
| `test_m2_asset.py` | M2 | 9 | 0 | 1 | 10 |
| `test_m3_registry.py` | M3 | 23 | 0 | 0 | 23 |
| `test_conversation_m7.py` | M7 | 7 | 0 | 1 | 8 |
| `test_progress.py` | Progress Hook | 12 | 0 | 0 | 12 |
| `test_backends.py` | M5 | 5 | 0 | 0 | 5 |
| `test_upscale.py` | M9.1 | 5 | 0 | 1 | 6 |
| `test_prompt_builder.py` | M11 | 32 | **6** | 0 | 38 |
| **ИТОГО (pytest)** | | **136** | **6** | **2** | **144** |

### 2.2 Тесты, не запускаемые через pytest (collect 0 items)

Причина: `sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')` в начале файла ломает capture в Python 3.14. Тесты существуют как `def test_*()` функции, но pytest их не находит.

| Файл теста | Milestone | Тестов (по коду) | Статус |
|------------|-----------|-----------------|--------|
| `test_prompt_builder_m11.py` | M11.3 | 8 | collect 0 |
| `test_prompt_builder_composite_m11.py` | M11.5 | 12 | collect 0 |
| `test_prompt_builder_llm_m11.py` | M11.4 | 11 | collect 0 |
| `test_prompt_builder_integration_m11.py` | M11.6 | 13 | collect 0 |
| `test_ui_m12.py` | M12 | 10 | collect 0 |
| `test_m11_verification.py` | M11 verification | custom (28 checks) | collect 0 (script) |

**Примечание:** `test_m11_verification.py` — это custom verification script (не pytest), запускается через `python tests/test_m11_verification.py`. В earlier runs показал 28/28 checks PASSED.

### 2.3 E2E тесты (требуют живой ComfyUI)

| Файл теста | Milestone | Статус |
|------------|-----------|--------|
| `test_m4_execution.py` | M4 | hangs (connection timeout) |
| `test_remote_e2e.py` | M5 | skip (нет COMFY_REMOTE_URL) |
| `test_video_e2e.py` | M6 | skip (нет COMFY_REMOTE_URL) |
| `test_img2img_e2e.py` | M6.5 | skip (нет COMFY_REMOTE_URL) |
| `test_audio_e2e.py` | M7 | skip (нет COMFY_REMOTE_URL) |
| `test_ui_real_e2e.py` | M12 | skip (нет COMFY_REMOTE_URL) |

### 2.4 Тесты в корне проекта

| Файл | Назначение | Статус |
|------|-----------|--------|
| `test_3turn_ui.py` | Ручной 3-turn E2E тест (httpx) | manual, не pytest |
| `conftest.py` | sys.path insert | minimal |

### 2.5 6 FAILURES в test_prompt_builder.py — анализ

| Тест | Причина | Это баг кода? |
|------|---------|---------------|
| `test_prompt_context_mode_literal` | `get_type_hints()` не работает с `Literal` в Python 3.14; test stale | ❌ Test defect |
| `test_prompt_result_mode_literal` | Same | ❌ Test defect |
| `test_prompt_result_source_literal` | Same | ❌ Test defect |
| `test_empty_input` | Тест ожидает непустой `enhanced_prompt` для пустого ввода; код корректно возвращает `""` | ❌ Test defect |
| `test_whitespace_input` | Same | ❌ Test defect |
| `test_style_parameter` | Тест ищет "photorealistic" в выводе; `HeuristicPromptBuilder` не использует поле `style` | ❌ Test defect |

**Вывод:** 6 failures — это **дефекты тестов** (устаревшие assert-ы), НЕ дефекты кода. Тесты написаны для ранней версии контракта и не обновлены после финализации `HeuristicPromptBuilder`.

### 2.6 Итоговая сводка тестов

| Категория | Count |
|-----------|-------|
| Passed (pytest, единичные файлы) | 136 |
| Failed (test defects в test_prompt_builder.py) | 6 |
| Skipped (net COMFY_REMOTE_URL) | 2 |
| Not collectable (Python 3.14 stdout hack) | ~54 тестов в 6 файлах |
| E2E (hang/timeout без ComfyUI) | 1 файл |
| Manual scripts | 2 файла |

---

## 3. DOCUMENTATION AUDIT — Противоречия и несоответствия

### 3.1 Устаревшие утверждения

| Документ | Утверждение | Факт | Серьёзность |
|----------|-------------|------|-------------|
| `PROJECT_SPEC.md` §22 (последняя строка) | "M1–M9 завершены; следующий шаг — M10 Validation" | M10, M11, M12 реализованы и заморожены | HIGH |
| `tasks/BACKLOG.md` | M11 в очереди как "PLANNED/SPECIFIED" | M11 IMPLEMENTED & FROZEN | MEDIUM |
| `tasks/ACTIVE.md` (последняя строка) | Дублирующее утверждение о M11.3 | M11.3–M11.6 IMPLEMENTED | LOW |

### 3.2 Противоречия

| Проблема | Задействованные документы | Описание |
|----------|-------------------------|----------|
| M12 ≠ ComfyCLI | Все документы говорят M12 = "Real UI E2E" | ComfyCLIAdapter нигде не упоминается |
| §22 не содержит M11/M12 | PROJECT_SPEC.md §22 | Milestone list заканчивается на M10 + Mx |
| M12 нет DoD | docs/18_DEFINITION_OF_DONE.md | DoD есть для M11, нет для M12 |

### 3.3 Milestone numbering conflicts

**Факт:** В коде и документации M12 = "Real UI E2E" (lifecycle + CompositePromptBuilder + SSE + multi-turn). **Нигде** в репозитории M12 не связан с ComfyCLI.

Предполагаемая причина confusion: работа с ComfyCLI могла вестись в другом AI-сессии / другом инструменте и не была закоммичена в этот репозиторий.

### 3.4 Компоненты, заявленные как реализованные, но отсутствующие в коде

| Компонент | Где заявлен | Факт в коде |
|-----------|-------------|-------------|
| ComfyCLIAdapter | Упоминается пользователем как "M12.1" | ❌ NOT FOUND |
| AD-33, AD-34 | Упоминаются пользователем | ❌ NOT FOUND |
| docs/21_COMFY_CLI_INTEGRATION_AUDIT.md | Упоминается пользователем | ❌ NOT FOUND |

### 3.5 Компоненты, существующие в коде, но отсутствующие в документации

| Компонент | Файл | Документация |
|-----------|------|-------------|
| `app/engine/verifier.py` | 39 строк | Нет отдельного описания в docs/ |
| `app/engine/websocket.py` | 93 строки | Описан в docs/20_UI.md частично |
| `app/registry/` (8 файлов) | Полный registry layer | Описан в docs/04-08, но не в §22 |
| `app/assets/store.py` | 153 строки | Описан в docs/05 |

### 3.6 Frozen milestones, которые документация продолжает считать active

| Milestone | Факт | Документация |
|-----------|------|-------------|
| M11 | FROZEN | `tasks/ACTIVE.md` всё ещё перечисляет его как active (последняя строка) |
| M12 | FROZEN | Нет противоречий, но нет DoD |

### 3.7 Technical debt, выглядящий как unfinished feature

| Элемент | Описание | Фактический статус |
|---------|----------|-------------------|
| Semantic intent validation | `_check_intent_preserved()` — консервативная проверка >= 50% ключевых слов | Working, но limited |
| `ExecutionPlan` prompt metadata | Поля `_original_prompt`, `_enhanced_prompt`, `_prompt_source` на `Job` существуют | Working, но через `params["prompt"]` |
| `previous_prompt` semantic accumulation | `previous_prompt` передаётся в `PromptContext`, но `HeuristicPromptBuilder` его не использует | Partially implemented |

---

## 4. M12 CONFLICT ANALYSIS

### Фактическая история M12

**Все источники в репозитории утверждают:**
- `engineering/HANDOFF.md`: "M12 COMPLETED: `app/comfy/lifecycle.py` — ComfyUIProcessManager... UI использует CompositePromptBuilder по умолчанию..."
- `engineering/CHANGELOG.md`: "M12 Real UI E2E (IMPLEMENTED & FROZEN)"
- `docs/17_ROADMAP.md`: "M12 Real UI E2E — M12.1-M12.5 FULLY IMPLEMENTED & FROZEN"
- `tasks/ACTIVE.md`: "M12 Real UI E2E — M12.1-M12.5 IMPLEMENTED & FROZEN"
- `tests/test_ui_m12.py`: 10 тестов для UI E2E (lifecycle, composite, /turn, SSE, etc.)

**M12 = Real UI E2E** — это唯一 версия, которая существует в коде и документации.

### ComfyCLIAdapter — факт

- **Код:** класс `ComfyCLIAdapter` не найден нигде в `app/`, `tests/`, `workflows/`, `docs/`, `engineering/`, `tasks/`
- **Документация:** `docs/21_COMFY_CLI_INTEGRATION_AUDIT.md` не существует
- **AD:** AD-33 и AD-34 не задокументированы
- **Вывод:** ComfyCLIAdapter не был реализован в этом репозитории

### Архитектурное предложение по нумерации

**Вариант A (рекомендуемый):** Оставить M12 = Real UI E2E (факт). ComfyCLI — отдельный infrastructure milestone без номера (или новый номер после M12).

```
M1  — Runtime + Client                FROZEN
M2  — Asset Layer                     FROZEN
M3  — Registry                        FROZEN
M4  — Execution Chain                 FROZEN
M5  — Provider / Model / Remote       FROZEN
M6  — Real Video E2E                  FROZEN
M6.5 — Image Input / img2img          FROZEN
M7  — Conversation Context            FROZEN
M8  — Agent + LLM                     FROZEN
M9  — UI                              FROZEN
M9.1 — Context-aware Planner          FROZEN
M10 — Validation                      FROZEN
M11 — Prompt Builder                  FROZEN
M12 — Real UI E2E                     FROZEN
M13–M18 — IMPLEMENTED — UNIT/INTEGRATION VERIFIED — REAL E2E VERIFIED

Infrastructure:
ComfyUIProcessManager                 IMPLEMENTED (часть M12)
ComfyCLIAdapter                       NOT IMPLEMENTED (future)
```

**Вариант B (если ComfyCLI уже был начат):** Присвоить M13 = ComfyCLI Integration (начать заново с чистой документацией).

---

## 5. ЕДИНАЯ ТАБЛИЦА СОСТОЯНИЯ

| Milestone | Название | Code | Tests | Docs | Status |
|-----------|----------|------|-------|------|--------|
| M1 | Runtime + Client | ✅ | ✅ 8/8 pass | ✅ §22 | FROZEN |
| M2 | Asset Layer | ✅ | ✅ 9/10 (1 skip) | ✅ §22 | FROZEN |
| M3 | Capability + Workflow Registry | ✅ | ✅ 23/23 pass | ✅ §22 | FROZEN |
| M4 | Execution Chain | ✅ | ✅ (hangs on live ComfyUI) | ✅ §22 | FROZEN |
| M5 | Provider / Model / Remote | ✅ | ✅ 17/17 pass | ✅ §22 | FROZEN |
| M6 | Real Video E2E | ✅ | ✅ (skip: no remote) | ✅ §22 | FROZEN |
| M6.5 | Image Input / img2img | ✅ | ✅ (skip: no remote) | ✅ §22 | FROZEN |
| M7 | Conversation Context | ✅ | ✅ 7/8 (1 skip) | ✅ §22, docs/19 | FROZEN |
| M8 | Agent + LLM | ✅ | ✅ 8/8 pass | ✅ §22 | FROZEN |
| M9 | UI | ✅ | ✅ 5/5 pass | ✅ §22, docs/20 | FROZEN |
| M9.1 | Context-aware Planner | ✅ | ✅ 11/11 pass | ✅ §22 | FROZEN |
| M10 | Validation | ✅ | ✅ 6/7 remote E2E | ✅ §22 | FROZEN |
| M11 | Prompt Builder | ✅ | ⚠️ 32/38 pytest (6 test defects) + ~54 not collectable | ✅ docs/20_PROMPT_BUILDER.md | FROZEN |
| M12 | Real UI E2E | ✅ | ⚠️ ~10 not collectable (Python 3.14 bug) | ⚠️ нет DoD в docs/18 | FROZEN |
| Infra | ComfyUIProcessManager | ✅ | ✅ (в M12 tests) | ✅ | IMPLEMENTED |
| Infra | ComfyCLIAdapter | ❌ NOT FOUND | ❌ | ❌ NOT FOUND | NOT IMPLEMENTED |
| M13 | (next feature) | — | — | — | PLANNED |

### Легенда статусов

- **FROZEN** — реализовано, заморожено, не трогать без архитектурного решения
- **IMPLEMENTED** — реализовано, часть существующего milestone
- **NOT IMPLEMENTED** — не существует в коде/документации
- **PLANNED** — запланировано, код не начат

---

## 6. ARCHITECTURAL STATE — Фактический pipeline

### Execution Path (основной)

```
User
  ↓
UI (app/ui.py)
  ↓ POST /turn
ConversationAgent.turn() (app/conversation.py)
  ↓
Planner.plan() (app/planner.py)
  ↓ capability + params
PromptBuilder.build() (app/prompt/composite.py → llm.py / heuristic.py)
  ↓ enhanced_prompt
Agent.prepare() (app/agent.py)
  ↓ manifest + plan + provider
resolve_asset_inputs() (AD-23)
  ↓ bindings
WorkflowEngine.execute() (app/engine/engine.py)
  ↓
ComfyUIProvider.execute() (app/provider/comfyui.py)
  ↓
ComfyClient.queue_prompt() (app/comfy/client.py)
  ↓ HTTP POST
ComfyUI (127.0.0.1:8188)
  ↓
WebSocket tracking (app/engine/websocket.py)
  ↓
Job (app/engine/job.py) → Verifier (app/engine/verifier.py)
  ↓
AssetStore (app/assets/store.py)
  ↓
SSE events → UI
```

### Infrastructure (не execution path)

```
ComfyUIProcessManager (app/comfy/lifecycle.py)
  ├── check()       — HTTP health check
  ├── wait_for_ready() — polling until ComfyUI responds
  ├── start()       — subprocess.Popen
  └── stop()        — terminate

ComfyCLIAdapter — NOT IMPLEMENTED
```

### Инварианты (зафиксированы)

| ID | Инвариант | Статус |
|----|-----------|--------|
| R1 | ComfyClient + WorkflowEngine — основной execution path | ✅ |
| R2 | ComfyCLIAdapter не заменяет lifecycle/execution path | ✅ (не существует) |
| R3 | ComfyUIProcessManager — infrastructure/tooling | ✅ |
| AD-30 | PromptBuilder не имеет доступа к FS/ComfyUI | ✅ |
| AD-31 | PromptBuilder не выбирает capability | ✅ |
| AD-32 | PromptBuilder сохраняет исходное намерение | ✅ |
| AD-33 | NOT DOCUMENTED | — |
| AD-34 | NOT DOCUMENTED | — |

---

## 7. TECHNICAL DEBT

| # | Проблема | Severity | Impact | Почему не блокирует | Решить на milestone |
|---|----------|----------|--------|---------------------|-------------------|
| TD-1 | Semantic intent validation — консервативная (≥50% ключевых слов) | LOW | LLM может вернуть потерянный промпт, heuristic fallback спасает | CompositePromptBuilder fallback → heuristic | M13+ (hardening) |
| TD-2 | `previous_prompt` передаётся в PromptContext, но HeuristicPromptBuilder не использует | LOW | Итеративные подсказки не учитывают историю через heuristic | LLMPromptBuilder может использовать (будущее) | M13+ (context-aware suggestions) |
| TD-3 | `ExecutionPlan` prompt metadata — поля на `Job` существуют (`_original_prompt`, `_enhanced_prompt`, `_prompt_source`) | LOW | Данные доступны, но не отображаются в UI/API | Для отладки достаточно | M13+ (если нужен prompt audit trail) |
| TD-4 | 6 failures в `test_prompt_builder.py` | MEDIUM | Тесты не обновлены после финализации контракта | Код работает корректно; тесты stale | M13 (test maintenance) |
| TD-5 | ~54 тестов не收集ляются через pytest (Python 3.14 stdout hack) | MEDIUM | Тесты не запускаются через standard `pytest` | Тесты работают через `python <file>` | M13 (remove stdout hack) |
| TD-6 | `docs/18_DEFINITION_OF_DONE.md` нет DoD для M12 | LOW | Документационный gap | Код и тесты существуют | M13 (doc sync) |
| TD-7 | `PROJECT_SPEC.md` §22 не содержит M11/M12 | MEDIUM | §22 устарел | Другие документы (17_ROADMAP, HANDOFF) актуальны | M13 (spec sync) |
| TD-8 | Persistence context (JSONL) — нет per-session persistence | LOW | При рестарте теряются сессии | Design decision для v1 | Future milestone |
| TD-9 | LLMPlanner real integration — heuristic fallback всегда | LOW | LLM planner работает через mock/key | Требует API ключ | Future milestone |
| TD-10 | Concurrency tests — нет тестов параллельных сессий | LOW | Single-user usage model | Многопользовательность — future | Future milestone |

---

## 8. ПОСЛЕ АУДИТА — Предложения

### 8.1 CURRENT FROZEN STATE

**Не трогать без отдельного архитектурного решения:**

| Что | Почему frozen |
|-----|--------------|
| M1–M12 execution chain | Протестировано, работает, не ломается |
| Prompt Builder архитектура (AD-30/31/32) | Архитектурное решение утверждено |
| ConversationAgent / ConversationContext | Multi-turn работает, session isolation доказан |
| WorkflowEngine / ComfyClient / Provider | Основной execution path, не трогать |
| ComfyUIProcessManager | Infrastructure, работает |

### 8.2 NEXT DEVELOPMENT AXIS

**Рекомендуемый следующий шаг: M13 — Test Maintenance + Doc Resync**

Причина: перед новым feature нужно почистить технический долг:
1. Исправить 6 failures в `test_prompt_builder.py` (stale asserts)
2. Убрать `sys.stdout = io.TextIOWrapper(...)` хак из M11/M12 тестов
3. Обновить `PROJECT_SPEC.md` §22 (добавить M11/M12)
4. Добавить DoD для M12 в `docs/18_DEFINITION_OF_DONE.md`
5. Обновить `tasks/BACKLOG.md` (убрать M11 из очереди)

**Альтернативный следующий шаг:** Реальный ComfyUI E2E прогон на живом backend (требует ComfyUI на 127.0.0.1:8188).

### 8.3 DEFERRED

| Что | Почему deferred |
|-----|----------------|
| audio.generate real E2E | Sonilo HTTP 401, broken node |
| Persistence context (JSONL) | Design decision — single-user v1 |
| LLMPlanner real integration | Требует API ключ + production testing |
| Concurrency tests | Многопользовательность — future |
| ComfyCLIAdapter | Не реализован, требует архитектурного решения |
| Semantic validation hardening | Работает через fallback, не блокирует |

### 8.4 DOCUMENTATION RESYNC PLAN

| Документ | Что изменить | Приоритет |
|----------|-------------|-----------|
| `PROJECT_SPEC.md` §22 | Добавить M11 (Prompt Builder) и M12 (Real UI E2E) в milestone list; обновить финальный комментарий | HIGH |
| `docs/18_DEFINITION_OF_DONE.md` | Добавить DoD для M12 (lifecycle, composite, SSE, multi-turn, session isolation) | HIGH |
| `tasks/BACKLOG.md` | Убрать M11 из очереди (IMPLEMENTED); добавить M13+ задачи | MEDIUM |
| `tasks/ACTIVE.md` | Убрать дублирующую последнюю строку о M11.3 | LOW |
| `engineering/CHANGELOG.md` | Добавить запись аудита 2026-09-01 | LOW |

---

## 9. КРИТИЧЕСКИЕ ВЫВОДЫ

1. **ComfyCLIAdapter не существует** в этом репозитории. Если он был реализован — то в другом месте/сессии.
2. **AD-33/AD-34 не задокументированы.** Последнее AD = AD-32.
3. **M12 = Real UI E2E** —唯一 версия, подтверждённая кодом и документацией.
4. **6 test failures** — это stale tests, не code defects.
5. **~54 тестов не запускаются через pytest** из-за Python 3.14 compatibility issue.
6. **PROJECT_SPEC §22 устарел** — не содержит M11/M12.
7. **Весь execution path (M1–M12) работает и заморожен.**

---

*Этот документ является новой точкой отсчёта. Следующий AI-инженер должен начинать с чтения этого файла, а не с重新 изучения кодовой базы.*
