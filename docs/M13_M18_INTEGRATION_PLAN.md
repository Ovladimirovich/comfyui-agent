# M13–M18 INTEGRATION PLAN

**Статус:** READ-ONLY PLANNING DOCUMENT
**Дата:** 2026-09-01
**На основе:** ARCHITECTURE_VERIFICATION_M13_M18.md, PROJECT_STATE_2026-09-01.md, PROJECT_SPEC.md
**Цель:** Определить как превратить существующие M13–M18 модули в реально интегрированную систему

---

## Executive Summary

M13–M18 модули **существуют** и **имеют unit-тесты** (113 тестов проходят). Однако интеграция между ними **не подтверждена** — AdaptivePlanner не подключён к Agent, TaskDecomposer/ExecutionChain не используются, Feedback не влияет на планирование. Документ описывает **минимальные wiring changes** для превращения модулей в интегрированную систему **без переписывания M1–M12**.

---

## 1. Фактическая карта текущих импортов и execution flow

### 1.1. Текущий execution flow (M1–M12 + M13–M18 wiring)

```
UI /turn POST
  └→ ConversationAgent.turn()                          [conversation.py:127]
       ├→ self.session(session_id)                     [conversation.py:97-110]
       │    └→ session_manager.resume(session_id)      [M15: WIRED, conversation.py:106]
       ├→ planner.plan(request, context)               [planner.py:157]
       │    └→ HeuristicPlanner.plan()                 [planner.py:149] (default)
       ├→ prompt_builder.build(ctx)                    [M11: WIRED, conversation.py:158-180]
       ├→ self.prepare(capability, params)             [agent.py:124-170]
       ├→ self.engine.execute(manifest, plan)          [engine.py:173-292]
       ├→ semantic_verifier.verify(...)                [M14: WIRED, conversation.py:270-285]
       ├→ execution_history.record(record)             [M13: WIRED, conversation.py:287-295]
       ├→ retry_policy.decide(state, attempt)          [M13: WIRED, conversation.py:324-328]
       ├→ session_manager.save(session_id, ctx)        [M15: WIRED, conversation.py:367-369]
       └→ return job
```

### 1.2. Что НЕ в текущем flow

| Компонент | Статус | Где должен быть |
|-----------|--------|-----------------|
| AdaptivePlanner | ❌ NOT WIRED | Должен заменять HeuristicPlanner когда история ≥ 3 records |
| TaskDecomposer | ❌ NOT WIRED | Должен вызываться в начале turn() для multi-step detection |
| ExecutionChain | ❌ NOT WIRED | Должен использоваться вместо одиночного engine.execute() для multi-step |
| Feedback → AdaptivePlanner | ❌ NOT WIRED | Feedback должен влиять на weighted analytics |

### 1.3. Импорты M13–M18 в ключевых файлах

| Файл | Импортирует M13–M18 | Статус |
|------|---------------------|--------|
| `agent.py:24-26` | ExecutionHistory, ExecutionRecord, RetryPolicy, classify_error, SemanticVerifier, SemanticVerificationResult | ✅ Wired |
| `conversation.py:30-33` | SessionManager, ExecutionHistory, ExecutionRecord, RetryPolicy, classify_error | ✅ Wired |
| `ui.py:32` | FeedbackRecord, FeedbackStore | ✅ Wired |
| `engine/__init__.py` | ExecutionChain, ChainResult, ChainState | ✅ Exported |
| `planner/__init__.py` | HeuristicPlanner, PlanResult, PlanContext | ✅ Existing |

---

## 2. Анализ по компонентам M13–M18

### 2.1. M13: Execution History + Retry Loop

| Параметр | Значение |
|----------|----------|
| **Существующий модуль** | `app/engine/history.py`, `app/engine/retry.py` |
| **Текущая точка входа** | `Agent.generate()`, `ConversationAgent.turn()` |
| **Подключён?** | ✅ YES — history.record() и retry_policy.decide() вызываются |
| **Где должен быть** | Уже подключён |
| **Какие контракты затрагиваются** | `Agent.__init__`, `ConversationAgent.__init__`, `Job.attempt`, `Job.error_class` |
| **Необходимые изменения** | Нет (wiring complete) |
| **Что доказано unit-тестами** | ExecutionRecord, ExecutionHistory, RetryPolicy, classify_error |
| **Что НЕ доказано** | E2E: retry после реального failure на ComfyUI |

**Статус:** PARTIALLY VERIFIED — wiring exists, нет E2E

### 2.2. M14: Semantic Verification

| Параметр | Значение |
|----------|----------|
| **Существующий модуль** | `app/engine/semantic_verifier.py` |
| **Текущая точка входа** | `Agent.generate()`, `ConversationAgent.turn()` |
| **Подключён?** | ✅ YES — semantic_verifier.verify() вызывается |
| **Где должен быть** | Уже подключён |
| **Какие контракты затрагиваются** | `Agent.__init__`, `ConversationAgent.__init__`, `RetryPolicy.decide()` |
| **Необходимые изменения** | Нет (wiring complete) |
| **Что доказано unit-тестами** | SemanticVerifier (MIME, prompt, parse), SemanticVerificationResult |
| **Что НЕ доказано** | Реальный vision API вызов; все тесты с mock |

**Статус:** MOCK/UNIT ONLY — нет реального vision API теста

### 2.3. M15: Persistent Context

| Параметр | Значение |
|----------|----------|
| **Существующий модуль** | `app/context/persistence.py`, `app/context/session_manager.py` |
| **Текущая точка входа** | `ConversationAgent.session()`, `ConversationAgent.turn()` |
| **Подключён?** | ✅ YES — session_manager.resume() и save() вызываются |
| **Где должен быть** | Уже подключён |
| **Какие контракты затрагиваются** | `ConversationAgent.__init__`, `ConversationContext.as_dict()` |
| **Необходимые изменения** | Нет (wiring complete) |
| **Что доказано unit-тестами** | ContextPersistence, SessionManager |
| **Что НЕ доказано** | Persistence после restart процесса |

**Статус:** PARTIALLY VERIFIED — wiring exists, нет restart test

### 2.4. M16: Adaptive Planner

| Параметр | Значение |
|----------|----------|
| **Существующий модуль** | `app/planner/adaptive.py`, `app/planner/preferences.py`, `app/engine/analytics.py` |
| **Текущая точка входа** | `Agent.generate()` (planner.plan()) |
| **Подключён?** | ❌ NO — Agent использует `self.planner or HeuristicPlanner()`, AdaptivePlanner не передаётся |
| **Где должен быть** | `Agent.__init__` должен создавать AdaptivePlanner когда execution_history доступен |
| **Какие контракты затрагиваются** | `Agent.__init__`, `Planner` protocol, `HeuristicPlanner` (fallback) |
| **Необходимые изменения** | Wire AdaptivePlanner в Agent.generate() |
| **Что доказано unit-тестами** | HistoryAnalytics, UserPreferences, AdaptivePlanner (standalone) |
| **Что НЕ доказано** | Integration: Agent → AdaptivePlanner → params adjustment |

**Статус:** NOT INTEGRATED — модуль существует, но не подключён

### 2.5. M17: User Feedback

| Параметр | Значение |
|----------|----------|
| **Существующий модуль** | `app/context/feedback.py` |
| **Текущая точка входа** | UI: POST /api/feedback, GET /api/feedback/history |
| **Подключён?** | ✅ UI endpoints wired, ❌ Feedback → AdaptivePlanner NOT WIRED |
| **Где должен быть** | Feedback должен влиять на AdaptivePlanner analytics |
| **Какие контракты затрагиваются** | `FeedbackStore`, `HistoryAnalytics`, `AdaptivePlanner` |
| **Необходимые изменения** | Wire Feedback → HistoryAnalytics → AdaptivePlanner |
| **Что доказано unit-тестами** | FeedbackStore |
| **Что НЕ доказано** | Feedback влияет на последующие planning decisions |

**Статус:** NOT INTEGRATED — UI endpoints exist, но feedback не влияет на планирование

### 2.6. M18: Multi-Step Decomposition

| Параметр | Значение |
|----------|----------|
| **Существующий модуль** | `app/planner/decomposer.py`, `app/engine/chain.py` |
| **Текущая точка входа** | ❌ NOT WIRED — нигде не вызывается из execution path |
| **Подключён?** | ❌ NO — Decomposer/Chain существуют, но не используются |
| **Где должен быть** | ConversationAgent.turn() должен детектить multi-step и использовать Chain |
| **Какие контракты затрагиваются** | `ConversationAgent.turn()`, `Agent.generate()`, `WorkflowEngine.execute()` |
| **Необходимые изменения** | Wire TaskDecomposer + ExecutionChain в ConversationAgent |
| **Что доказано unit-тестами** | TaskDecomposer, ExecutionChain (с mock execute_fn) |
| **Что НЕ доказано** | E2E: multi-step chain на реальном ComfyUI |

**Статус:** NOT INTEGRATED — модули существуют, но не подключены

---

## 3. Интеграция по компонентам M1–M12

### 3.1. Agent (`app/agent.py`)

| Что | Статус | Изменения |
|-----|--------|-----------|
| `__init__` принимает execution_history, retry_policy, semantic_verifier | ✅ DONE | Нет |
| `generate()` retry loop | ✅ DONE | Нет |
| `generate()` history.record() | ✅ DONE | Нет |
| `generate()` retry_policy.decide() | ✅ DONE | Нет |
| `generate()` semantic_verifier.verify() | ✅ DONE | Нет |
| **`generate()` AdaptivePlanner** | ❌ NOT WIRED | **Нужно:** добавить conditional creation AdaptivePlanner |

**Необходимое изменение в Agent:**
```python
# В __init__ или generate():
# Если execution_history.count() >= 3 → использовать AdaptivePlanner
# Иначе → fallback на HeuristicPlanner
```

### 3.2. ConversationAgent (`app/conversation.py`)

| Что | Статус | Изменения |
|-----|--------|-----------|
| `__init__` принимает session_manager | ✅ DONE | Нет |
| `session()` session_manager.resume() | ✅ DONE | Нет |
| `turn()` retry loop | ✅ DONE | Нет |
| `turn()` history.record() | ✅ DONE | Нет |
| `turn()` retry_policy.decide() | ✅ DONE | Нет |
| `turn()` semantic_verifier.verify() | ✅ DONE | Нет |
| `turn()` session_manager.save() | ✅ DONE | Нет |
| **`turn()` TaskDecomposer detection** | ❌ NOT WIRED | **Нужно:** добавить multi-step detection |
| **`turn()` ExecutionChain** | ❌ NOT WIRED | **Нужно:** добавить chain execution path |

**Необходимое изменение в ConversationAgent:**
```python
# В turn() перед основным execution:
# 1. task_decomposer.decompose(request) → subtasks
# 2. Если len(subtasks) > 1 → ExecutionChain.execute(subtasks)
# 3. Если len(subtasks) == 1 → существующий single-step path
```

### 3.3. Planner (`app/planner/__init__.py`)

| Что | Статус | Изменения |
|-----|--------|-----------|
| HeuristicPlanner | ✅ EXISTS | Нет |
| LLMPlanner | ✅ EXISTS | Нет |
| Planner protocol | ✅ EXISTS | Нет |
| **AdaptivePlanner** | ✅ EXISTS (в `planner/adaptive.py`) | **Нужно:** export из `planner/__init__.py` |

### 3.4. PromptBuilder (`app/prompt/`)

| Что | Статус | Изменения |
|-----|--------|-----------|
| HeuristicPromptBuilder | ✅ EXISTS | Нет |
| LLMPromptBuilder | ✅ EXISTS | Нет |
| CompositePromptBuilder | ✅ EXISTS | Нет |
| PromptBuilder integration | ✅ DONE | Нет |

**PromptBuilder НЕ требует изменений для M13–M18.**

### 3.5. WorkflowEngine (`app/engine/engine.py`)

| Что | Статус | Изменения |
|-----|--------|-----------|
| execute() | ✅ EXISTS | Нет |
| Retry loop | ✅ DONE (в Agent/ConversationAgent) | Нет |
| Chain execution | ❌ NOT WIRED | **Нужно:** ExecutionChain вызывает engine.execute() для каждого шага |

### 3.6. Verifier (`app/engine/verifier.py`)

| Что | Статус | Изменения |
|-----|--------|-----------|
| verify() (structural) | ✅ EXISTS | Нет |
| SemanticVerifier | ✅ EXISTS | Нет |
| verify_with_diagnostics() | ✅ EXISTS | Нет |

### 3.7. Job (`app/engine/job.py`)

| Что | Статус | Изменения |
|-----|--------|-----------|
| attempt field | ✅ EXISTS | Нет |
| error_class field | ✅ EXISTS | Нет |
| State tracking | ✅ EXISTS | Нет |

### 3.8. Asset/AssetStore (`app/assets/`)

| Что | Статус | Изменения |
|-----|--------|-----------|
| AssetStore | ✅ EXISTS | Нет |
| Asset lineage | ✅ EXISTS | Нет |
| **Chain output assets** | ❌ NOT WIRED | **Нужно:** ExecutionChain должен сохранять output assets |

### 3.9. Persistence (`app/context/`)

| Что | Статус | Изменения |
|-----|--------|-----------|
| ContextPersistence | ✅ EXISTS | Нет |
| SessionManager | ✅ EXISTS | Нет |
| FeedbackStore | ✅ EXISTS | Нет |

### 3.10. SSE/UI (`app/ui.py`)

| Что | Статус | Изменения |
|-----|--------|-----------|
| /turn endpoint | ✅ EXISTS | Нет |
| SSE events | ✅ EXISTS | Нет |
| /api/feedback | ✅ EXISTS | Нет |
| /api/feedback/history | ✅ EXISTS | Нет |
| **Chain progress SSE** | ❌ NOT WIRED | **Нужно:** добавить chain_progress events |

---

## 4. Сквозной интеграционный сценарий

### 4.1. Single-step request (текущий flow + M13–M18)

```
User: "нарисуй кота"
  │
  ▼
ConversationAgent.turn(session_id, request="нарисуй кота")
  │
  ├→ session_manager.resume(session_id)              [M15]
  │    └→ load from JSONL or create new
  │
  ├→ planner.plan(request, context)                  [M11]
  │    ├→ AdaptivePlanner.plan()                     [M16: если история ≥ 3]
  │    │    └→ использует preferred_params из history
  │    └→ HeuristicPlanner.plan()                    [fallback]
  │
  ├→ task_decomposer.decompose(request)              [M18]
  │    └→ [SubTask(image.generate, params)]          [1 subtask = single-step]
  │
  ├→ prompt_builder.build(ctx)                       [M11]
  │    └→ enhanced_prompt
  │
  ├→ self.prepare(capability, params)                [M1-M12]
  │    └→ manifest, plan, provider
  │
  ├→ self.engine.execute(manifest, plan)             [M1-M12]
  │    └→ ComfyUI → Job → output Assets
  │
  ├→ semantic_verifier.verify(request, output)       [M14]
  │    └→ VerificationResult {score, matches_intent, suggested_params}
  │
  ├→ execution_history.record(record)                [M13]
  │    └→ save to in-memory + JSONL
  │
  ├→ retry_policy.decide(state, attempt)             [M13]
  │    └→ ACCEPT | RETRY | FAILED
  │
  ├→ session_manager.save(session_id, ctx)           [M15]
  │    └→ persist to JSONL
  │
  └→ return job
```

### 4.2. Multi-step request (M18 integration)

```
User: "сгенерируй кота и увеличь разрешение"
  │
  ▼
ConversationAgent.turn(session_id, request="сгенерируй кота и увеличь разрешение")
  │
  ├→ session_manager.resume(session_id)              [M15]
  │
  ├→ task_decomposer.decompose(request)              [M18]
  │    └→ [
  │         SubTask(image.generate, {prompt: "кота"}),
  │         SubTask(image.upscale, {width: 1024, height: 1024})
  │       ]                                          [2 subtasks = multi-step]
  │
  ├→ ExecutionChain.execute(subtasks)                [M18]
  │    │
  │    ├→ Step 0: execute_fn(SubTask[0])
  │    │    ├→ planner.plan("кота")                  [M11]
  │    │    ├→ engine.execute()                      [M1-M12]
  │    │    ├→ semantic_verifier.verify()            [M14]
  │    │    ├→ history.record()                      [M13]
  │    │    ├→ retry_policy.decide()                 [M13]
  │    │    └→ Job SUCCESS → output_asset A
  │    │
  │    ├→ Step 1: execute_fn(SubTask[1])
  │    │    ├→ planner.plan("увеличь разрешение")   [M11]
  │    │    ├→ engine.execute(A as input)            [M1-M12]
  │    │    ├→ semantic_verifier.verify()            [M14]
  │    │    ├→ history.record()                      [M13]
  │    │    ├→ retry_policy.decide()                 [M13]
  │    │    └→ Job SUCCESS → output_asset B
  │    │
  │    └→ ChainResult {state: COMPLETED, steps: [step0, step1]}
  │
  ├→ session_manager.save(session_id, ctx)           [M15]
  │
  └→ return final_job (with output_asset B)
```

### 4.3. Feedback → AdaptivePlanner flow (M17 → M16)

```
User: [после генерации] rated 2/5, comment "слишком темно"
  │
  ▼
UI POST /api/feedback {session_id, attempt_id, rating: 2, comment: "слишком темно"}
  │
  ├→ FeedbackStore.record(feedback)                  [M17]
  │    └→ save to JSONL
  │
  └→ [при следующем turn]
       ├→ AdaptivePlanner.plan(request)              [M16]
       │    ├→ HistoryAnalytics.preferred_params()   [M16]
       │    │    └→ анализирует успешные попытки
       │    ├→ FeedbackStore.get_for_session()       [M17]
       │    │    └→ учитывает низкие рейтинги
       │    └→ корректирует params (brightness ↑)
       └→ engine.execute() с скорректированными params
```

---

## 5. M18: Multi-step chain execution on ComfyUI

### 5.1. Детализация цепочки

```
"сгенерируй кота 512x512 и увеличь до 1024x1024"
  │
  ▼
TaskDecomposer.decompose()
  → [
      SubTask(capability="image.generate", params={prompt: "кота", width: 512, height: 512}),
      SubTask(capability="image.upscale", params={width: 1024, height: 1024})
    ]
  │
  ▼
ExecutionChain.execute(subtasks)
  │
  ├─ Step 0: image.generate
  │   ├→ Agent.prepare("image.generate", {prompt: "кота", width: 512, height: 512})
  │   ├→ WorkflowEngine.execute()
  │   │   ├→ Provider.upload_asset() (нет входных ассетов)
  │   │   ├→ build_prompt()
  │   │   ├→ Provider.execute() → ComfyUI POST /prompt
  │   │   ├→ WebSocket.track()
  │   │   ├→ Provider.view() → download output
  │   │   ├→ AssetStore.ingest() → Asset A (image, 512x512)
  │   │   └→ Verifier.verify() (structural)
  │   ├→ SemanticVerifier.verify() → score=0.85
  │   ├→ ExecutionHistory.record()
  │   └→ RetryPolicy.decide() → ACCEPT
  │
  ├─ Step 1: image.upscale (input: Asset A)
  │   ├→ Agent.prepare("image.upscale", {width: 1024, height: 1024})
  │   ├→ resolve_asset_inputs(image=A) → bindings
  │   ├→ WorkflowEngine.execute()
  │   │   ├→ Provider.upload_asset(A) → ComfyUI input
  │   │   ├→ build_prompt()
  │   │   ├→ Provider.execute() → ComfyUI POST /prompt
  │   │   ├→ WebSocket.track()
  │   │   ├→ Provider.view() → download output
  │   │   ├→ AssetStore.ingest() → Asset B (image, 1024x1024, lineage=[B,A])
  │   │   └→ Verifier.verify() (structural)
  │   ├→ SemanticVerifier.verify() → score=0.90
  │   ├→ ExecutionHistory.record()
  │   └→ RetryPolicy.decide() → ACCEPT
  │
  └─ ChainResult {state: COMPLETED, completed_steps: 2, failed_steps: 0}
```

### 5.2. Error handling в chain

```
Step 1: image.upscale → FAILED (transient error)
  │
  ├→ RetryPolicy.decide(error_class="transient", attempt=1) → RETRY
  │   └→ sleep(backoff)
  │
  ├→ Step 1 retry: image.upscale → FAILED (transient error)
  │
  ├→ RetryPolicy.decide(error_class="transient", attempt=2) → RETRY
  │   └→ sleep(backoff)
  │
  ├→ Step 1 retry: image.upscale → SUCCESS
  │
  └→ ChainResult {state: COMPLETED}
```

---

## 6. Минимальный набор integration/E2E tests

### 6.1. Integration tests (mock ComfyUI)

| Тест | Что проверяет | Компоненты |
|------|---------------|------------|
| `test_agent_uses_adaptive_planner` | Agent.generate() вызывает AdaptivePlanner при наличии history | Agent, AdaptivePlanner, ExecutionHistory |
| `test_agent_fallback_to_heuristic` | Agent.generate() fallback на HeuristicPlanner при пустой history | Agent, HeuristicPlanner |
| `test_conversation_detects_multi_step` | ConversationAgent.turn() детектит multi-step request | ConversationAgent, TaskDecomposer |
| `test_conversation_uses_chain_for_multi_step` | ConversationAgent.turn() использует ExecutionChain для multi-step | ConversationAgent, ExecutionChain |
| `test_chain_records_history` | ExecutionChain записывает history для каждого шага | ExecutionChain, ExecutionHistory |
| `test_feedback_affects_analytics` | FeedbackStore.record() влияет на HistoryAnalytics | FeedbackStore, HistoryAnalytics |
| `test_persistence_after_turn` | ConversationAgent.turn() сохраняет context в persistence | ConversationAgent, SessionManager |
| `test_retry_on_verification_failure` | Semantic verification failure → retry | SemanticVerifier, RetryPolicy |

### 6.2. E2E tests (реальный ComfyUI)

| Тест | Что проверяет | Компоненты |
|------|---------------|------------|
| `test_e2e_retry_after_failure` | Запуск с failing workflow → retry → success | Agent, ExecutionHistory, RetryPolicy, ComfyUI |
| `test_e2e_semantic_verification` | Генерация → vision API → score → decision | Agent, SemanticVerifier, ComfyUI |
| `test_e2e_persistence_restart` | Save → restart → resume → active_asset preserved | ConversationAgent, SessionManager |
| `test_e2e_multi_step_chain` | "сгенерируй кота и увеличь" → 2 executions → final asset | ConversationAgent, TaskDecomposer, ExecutionChain, ComfyUI |

### 6.3. Тесты которые ДОЛЖНЫ использовать mock

| Тест | Почему mock |
|------|-------------|
| Unit tests ExecutionRecord/ExecutionHistory | Файловая I/O не требует ComfyUI |
| Unit tests RetryPolicy.decide() | Pure logic |
| Unit tests SemanticVerifier (MIME, prompt, parse) | Pure logic |
| Unit tests ContextPersistence, SessionManager | Файловая I/O |
| Unit tests HistoryAnalytics, UserPreferences | In-memory data |
| Unit tests FeedbackStore | Файловая I/O |
| Unit tests TaskDecomposer | Pure logic |
| Unit tests ExecutionChain (с mock execute_fn) | Chain logic without ComfyUI |

### 6.4. Тесты которые ОБЯЗАНЫ работать с реальным ComfyUI

| Тест | Почему реальный ComfyUI |
|------|------------------------|
| E2E retry после failure | Нужен реальный failure + retry |
| E2E semantic verification | Нужен реальный output + vision API |
| E2E persistence restart | Нужен реальный state |
| E2E multi-step chain | Нужны реальные 2 workflow executions |

---

## 7. Wiring changes (порядок реализации)

### Phase 1: AdaptivePlanner wiring (M16 integration)

**Изменения в `agent.py`:**
1. Добавить import `AdaptivePlanner` из `app.planner.adaptive`
2. В `__init__` или `generate()`: если `execution_history.count() >= 3` → создать `AdaptivePlanner(history=execution_history)`
3. Использовать AdaptivePlanner вместо HeuristicPlanner

**Изменения в `planner/__init__.py`:**
1. Добавить export `AdaptivePlanner`

### Phase 2: TaskDecomposer + ExecutionChain wiring (M18 integration)

**Изменения в `conversation.py`:**
1. Добавить import `TaskDecomposer` из `app.planner.decomposer`
2. Добавить import `ExecutionChain` из `app.engine.chain`
3. В `turn()`: перед основным execution вызвать `TaskDecomposer.decompose(request)`
4. Если `len(subtasks) > 1` → создать `ExecutionChain(execute_fn=..., history=...)` и выполнить
5. Если `len(subtasks) == 1` → существующий single-step path

**Изменения в `agent.py`:**
1. Добавить метод `_execute_subtask(subtask)` который вызывает `self.run()`
2. ExecutionChain будет использовать этот метод как execute_fn

### Phase 3: Feedback → AdaptivePlanner wiring (M17 → M16)

**Изменения в `planner/adaptive.py`:**
1. Добавить parameter `feedback_store` в `AdaptivePlanner.__init__`
2. В `plan()`: учитывать feedback ratings при расчёте preferred_params

**Изменения в `conversation.py`:**
1. Передавать `feedback_store` в `AdaptivePlanner`

### Phase 4: Integration tests

**Новые тесты:**
1. `tests/test_integration_m13_m18.py` — integration tests для wiring
2. `tests/test_e2e_m13_m18.py` — E2E tests с реальным ComfyUI

---

## 8. Риски

| Риск | Вероятность | Impact | Mitigation |
|------|-------------|--------|------------|
| AdaptivePlanner неправильно корректирует params | Medium | Medium | Min attempts threshold (≥3), user override > learned |
| Multi-step chain fails на шаге 2 | Medium | High | Per-step retry, cancel support |
| Semantic verification блокирует execution | Low | Medium | Timeout + fallback to score=0.5 |
| Persistence файлы повреждены | Low | High | try/except, graceful degradation |
| Feedback искажает analytics | Low | Medium | Weighted average, min samples |
| Decomposer неправильно разбивает request | Medium | Medium | Fallback to single-step |

---

## 9. Что НЕ нужно менять

| Компонент | Почему не менять |
|-----------|-----------------|
| M1–M12 execution chain | FROZEN, работает |
| HeuristicPlanner | Fallback, не удалять |
| CompositePromptBuilder | Fallback, не удалять |
| Verifier.verify() | Structural fallback |
| WorkflowEngine.execute() | Core execution, расширять обёрткой |
| Asset/AssetStore | Фундамент lineage |
| Provider/Registry | Boundary, работает |

---

## 10. Итоговая таблица статусов

| Milestone | Код | Unit tests | Wiring | Integration tests | E2E | Итоговый статус |
|-----------|-----|------------|--------|-------------------|-----|-----------------|
| **M13** | ✅ | ✅ 32 pass | ✅ WIRED | ❌ NOT TESTED | ❌ NOT TESTED | PARTIALLY VERIFIED |
| **M14** | ✅ | ✅ 23 pass | ✅ WIRED | ❌ NOT TESTED | ❌ NOT TESTED | MOCK/UNIT ONLY |
| **M15** | ✅ | ✅ 14 pass | ✅ WIRED | ❌ NOT TESTED | ❌ NOT TESTED | PARTIALLY VERIFIED |
| **M16** | ✅ | ✅ 16 pass | ❌ NOT WIRED | ❌ NOT TESTED | ❌ NOT TESTED | NOT INTEGRATED |
| **M17** | ✅ | ✅ 11 pass | ⚠️ PARTIAL | ❌ NOT TESTED | ❌ NOT TESTED | NOT INTEGRATED |
| **M18** | ✅ | ✅ 17 pass | ❌ NOT WIRED | ❌ NOT TESTED | ❌ NOT TESTED | NOT INTEGRATED |

---

## 11. Рекомендуемый порядок реализации

1. **Phase 1:** Wire AdaptivePlanner (M16) — 1-2 дня
2. **Phase 2:** Wire TaskDecomposer + ExecutionChain (M18) — 2-3 дня
3. **Phase 3:** Wire Feedback → AdaptivePlanner (M17 → M16) — 1 день
4. **Phase 4:** Integration tests — 2-3 дня
5. **Phase 5:** E2E tests с реальным ComfyUI — 2-3 дня

**Общий estimated:** 8-12 дней

---

*Документ является READ-ONLY planning document. Production code не изменялся.*
