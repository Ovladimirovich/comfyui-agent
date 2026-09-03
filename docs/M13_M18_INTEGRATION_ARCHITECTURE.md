# M13–M18 INTEGRATION ARCHITECTURE

**Статус:** SUPERSEDED BY M13_M18_ARCHITECTURAL_DECISION.md (APPROVED)
**Дата:** 2026-09-01
**На основе:** полного анализа исходного кода (agent.py, conversation.py, planner/, engine/, context/, ui.py)
**Цель:** определить правильный порядок интеграции M13–M18 в существующий M1–M12 execution path
**Примечание:** Этот документ заменён на `M13_M18_ARCHITECTURAL_DECISION.md` (APPROVED). См. его для утверждённого порядка интеграции и детального плана Phase 1.

---

## 1. Фактический execution flow ДО интеграции

### 1.1. Agent.generate() — одноходовый путь

```
Agent.generate(request, max_attempts=1)
  │
  ├→ planner = self.planner or HeuristicPlanner()        [agent.py:212]
  ├→ result = planner.plan(request)                       [agent.py:213]
  ├→ if prompt_builder: result = prompt_builder.build()   [agent.py:219-240]
  │
  ├→ for attempt in range(1, max_attempts+1):             [agent.py:245]
  │    ├→ job = self.run(capability, params)              [agent.py:250-258]
  │    │    └→ self.engine.execute(manifest, plan)        [agent.py:192]
  │    │
  │    ├→ if semantic_verifier: verify(job.output)        [agent.py:282-300]
  │    │    └→ if !ok: job.state = FAILED                 [agent.py:298-300]
  │    │
  │    ├→ execution_history.record(record)                [agent.py:303-310]
  │    ├→ decision = retry_policy.decide(state, attempt)  [agent.py:314-318]
  │    │    ├→ "accept" → return job                      [agent.py:320-321]
  │    │    ├→ "retry"  → continue (с suggested_params)   [agent.py:322-334]
  │    │    └→ "failed" → return job                      [agent.py:335-336]
  │
  └→ return last_job                                      [agent.py:339]
```

**Что уже интегрировано в Agent.generate():**
- ✅ Planner (HeuristicPlanner или inject)
- ✅ PromptBuilder (optional)
- ✅ RetryLoop (max_attempts > 1)
- ✅ ExecutionHistory.record()
- ✅ RetryPolicy.decide()
- ✅ SemanticVerifier.verify()
- ✅ suggested_params from semantic verification

**Что НЕ интегрировано в Agent.generate():**
- ❌ AdaptivePlanner (не создаётся, не используется)
- ❌ TaskDecomposer (не вызывается)
- ❌ ExecutionChain (не используется)
- ❌ Feedback (не влияет на планирование)

### 1.2. ConversationAgent.turn() — многоходовый путь

```
ConversationAgent.turn(session_id, request, max_attempts=1)
  │
  ├→ ctx = self.session(session_id)                      [conversation.py:151]
  │    └→ session_manager.resume(session_id)              [conversation.py:106] (M15)
  │
  ├→ planner = self.planner or _default_planner()        [conversation.py:156]
  ├→ plan_ctx = PlanContext(active_asset_type, caps)      [conversation.py:158-166]
  ├→ result = planner.plan(request, context=plan_ctx)    [conversation.py:167]
  │
  ├→ if prompt_builder: result = prompt_builder.build()   [conversation.py:172-191]
  │
  ├→ manifest, plan, provider = self.prepare()            [conversation.py:198-200]
  ├→ bindings = self.resolve_asset_inputs()               [conversation.py:204-206]
  │
  ├→ for attempt in range(1, max_attempts+1):             [conversation.py:226]
  │    ├→ job = self.engine.execute(manifest, plan)       [conversation.py:230-233]
  │    │
  │    ├→ if semantic_verifier: verify(job.output)        [conversation.py:269-285]
  │    │    └→ if !ok: job.state = FAILED                 [conversation.py:282-285]
  │    │
  │    ├→ execution_history.record(record)                [conversation.py:288-295]
  │    │
  │    ├→ if SUCCESS: update ctx (active_asset, etc.)     [conversation.py:298-321]
  │    │    └→ return job                                  [conversation.py:321]
  │    │
  │    ├→ decision = retry_policy.decide()                [conversation.py:324-328]
  │    │    ├→ "retry" → SSE retry_started, continue      [conversation.py:330-342]
  │    │    └→ other → break                               [conversation.py:343-345]
  │
  ├→ session_manager.save(session_id, ctx)                [conversation.py:368-369] (M15)
  └→ return job                                           [conversation.py:371]
```

**Что уже интегрировано в ConversationAgent.turn():**
- ✅ SessionManager (resume/save)
- ✅ Planner (HeuristicPlanner или inject)
- ✅ PromptBuilder (optional)
- ✅ Asset resolution (AD-23)
- ✅ RetryLoop
- ✅ ExecutionHistory.record()
- ✅ RetryPolicy.decide()
- ✅ SemanticVerifier.verify()
- ✅ Context update (active_asset, active_workflow, etc.)

**Что НЕ интегрировано в ConversationAgent.turn():**
- ❌ AdaptivePlanner (не создаётся, не используется)
- ❌ TaskDecomposer (не вызывается)
- ❌ ExecutionChain (не используется)
- ❌ Feedback (не влияет на планирование)
- ❌ SSE chain_progress events (не существуют)

---

## 2. Анализ по компонентам M13–M18

### 2.1. M13: Execution History + Retry Loop

| Параметр | Значение |
|----------|----------|
| **Модули** | `app/engine/history.py`, `app/engine/retry.py` |
| **Контракты** | `ExecutionRecord.from_job()`, `ExecutionHistory.record()`, `RetryPolicy.decide()` |
| **Текущая точка входа** | `Agent.generate()`, `ConversationAgent.turn()` |
| **Подключён?** | ✅ FULLY WIRED |
| **Вызывает** | Agent.generate() и ConversationAgent.turn() |
| **Получает** | Job, params, duration, error_class, attempt |
| **Возвращает** | RetryDecision (accept/retry/failed) |
| **Затрагивает контракты** | `Job.attempt`, `Job.error_class`, `ExecutionRecord.from_job()` |
| **Необходимые изменения** | НЕТ |
| **Integration tests** | `test_m13_history_retry.py` — 32 tests (unit only) |
| **E2E тест** | НЕОБХОДИМ: retry после реального failure на ComfyUI |

**Статус:** PARTIALLY VERIFIED — wiring complete, нет E2E

### 2.2. M14: Semantic Verification

| Параметр | Значение |
|----------|----------|
| **Модуль** | `app/engine/semantic_verifier.py` |
| **Контракт** | `SemanticVerifier.verify(request, output_path, capability)` → `SemanticVerificationResult` |
| **Текущая точка входа** | `Agent.generate():282-300`, `ConversationAgent.turn():269-285` |
| **Подключён?** | ✅ FULLY WIRED |
| **Вызывает** | Agent.generate() и ConversationAgent.turn() |
| **Получает** | request (str), output_path (str), capability (str) |
| **Возвращает** | SemanticVerificationResult (score, matches_intent, suggested_params, ok) |
| **Затрагивает контракты** | `Job.state = FAILED` (при verification error), `error_class = "verification"` |
| **Необходимые изменения** | НЕТ |
| **Integration tests** | `test_m14_semantic_verification.py` — 23 tests (mock API) |
| **E2E тест** | НЕОБХОДИМ: реальный vision API вызов |

**Статус:** MOCK/UNIT ONLY — нет реального vision API теста

### 2.3. M15: Persistent Context

| Параметр | Значение |
|----------|----------|
| **Модули** | `app/context/persistence.py`, `app/context/session_manager.py` |
| **Контракты** | `SessionManager.resume()`, `SessionManager.save()`, `ContextPersistence.save/load()` |
| **Текущая точка входа** | `ConversationAgent.session():106`, `ConversationAgent.turn():368-369` |
| **Подключён?** | ✅ FULLY WIRED |
| **Вызывает** | ConversationAgent |
| **Получает** | session_id (str), ConversationContext |
| **Возвращает** | ConversationContext или None |
| **Затрагивает контракты** | `ConversationContext.as_dict()`, `ConversationAgent.__init__` |
| **Необходимые изменения** | НЕТ |
| **Integration tests** | `test_m15_persistent_context.py` — 14 tests (unit only) |
| **E2E тест** | НЕОБХОДИМ: persistence после restart процесса |

**Статус:** PARTIALLY VERIFIED — wiring complete, нет restart test

### 2.4. M16: Adaptive Planner

| Параметр | Значение |
|----------|----------|
| **Модули** | `app/planner/adaptive.py`, `app/planner/preferences.py`, `app/engine/analytics.py` |
| **Контракты** | `AdaptivePlanner(history, fallback).plan(request, context)` → `PlanResult` |
| **Текущая точка входа** | ❌ NOT WIRED |
| **Подключён?** | ❌ NO |
| **Кто ДОЛЖЕН вызывать** | `Agent.generate()` и `ConversationAgent.turn()` |
| **Получает** | request (str), context (PlanContext), ExecutionHistory (injected) |
| **Возвращает** | PlanResult (capability, params, rationale) |
| **Затрагивает контракты** | `Planner` protocol, `HeuristicPlanner` (fallback) |
| **Необходимые изменения** | Wire AdaptivePlanner в Agent и ConversationAgent |
| **Integration tests** | `test_m16_adaptive_planner.py` — 16 tests (unit only) |
| **E2E тест** | НЕ ТРЕБУЕТСЯ: логика планирования не зависит от ComfyUI |

**Статус:** NOT INTEGRATED — модуль существует, но не подключён

### 2.5. M17: User Feedback

| Параметр | Значение |
|----------|----------|
| **Модуль** | `app/context/feedback.py` |
| **Контракты** | `FeedbackStore.record()`, `FeedbackStore.get_for_session()` |
| **Текущая точка входа** | UI: `POST /api/feedback`, `GET /api/feedback/history` |
| **Подключён?** | ⚠️ PARTIAL — UI endpoints exist, но feedback НЕ влияет на планирование |
| **Кто ДОЛЖЕН вызывать** | `AdaptivePlanner` (через `HistoryAnalytics` или напрямую) |
| **Получает** | FeedbackRecord (attempt_id, session_id, rating, comment) |
| **Возвращает** | list[FeedbackRecord], float (avg_rating) |
| **Затрагивает контракты** | `FeedbackStore`, `HistoryAnalytics`, `AdaptivePlanner` |
| **Необходимые изменения** | Wire Feedback → AdaptivePlanner (чтобы feedback влиял на planning) |
| **Integration tests** | `test_m17_user_feedback.py` — 11 tests (unit only) |
| **E2E тест** | НЕ ТРЕБУЕТСЯ: feedback логика не зависит от ComfyUI |

**Статус:** NOT INTEGRATED — UI endpoints exist, но feedback не влияет на планирование

### 2.6. M18: Multi-Step Decomposition

| Параметр | Значение |
|----------|----------|
| **Модули** | `app/planner/decomposer.py`, `app/engine/chain.py` |
| **Контракты** | `TaskDecomposer.decompose(request)` → `list[SubTask]`, `ExecutionChain.execute(subtasks)` → `ChainResult` |
| **Текущая точка входа** | ❌ NOT WIRED |
| **Подключён?** | ❌ NO |
| **Кто ДОЛЖЕН вызывать** | `ConversationAgent.turn()` |
| **Получает** | request (str), execute_fn (Callable), ExecutionHistory |
| **Возвращает** | ChainResult (state, steps, completed_steps, failed_steps) |
| **Затрагивает контракты** | `ConversationAgent.turn()`, `Agent.run()`, `WorkflowEngine.execute()` |
| **Необходимые изменения** | Wire TaskDecomposer + ExecutionChain в ConversationAgent |
| **Integration tests** | `test_m18_multi_step.py` — 17 tests (unit only, mock execute_fn) |
| **E2E тест** | НЕОБХОДИМ: multi-step chain на реальном ComfyUI |

**Статус:** NOT INTEGRATED — модули существуют, но не подключены

---

## 3. Интеграция по компонентам M1–M12

### 3.1. Agent (`app/agent.py:66-91`)

| Что | Статус | Изменения для M16-M18 |
|-----|--------|----------------------|
| `__init__` принимает execution_history, retry_policy, semantic_verifier | ✅ DONE | Нет |
| `__init__` принимает planner (Optional) | ✅ DONE | Нет |
| `generate()` retry loop | ✅ DONE | Нет |
| `generate()` history.record() | ✅ DONE | Нет |
| `generate()` retry_policy.decide() | ✅ DONE | Нет |
| `generate()` semantic_verifier.verify() | ✅ DONE | Нет |
| **`generate()` AdaptivePlanner** | ❌ NOT WIRED | Нужно: создавать AdaptivePlanner когда история ≥ N |
| **`generate()` TaskDecomposer** | ❌ NOT WIRED | Нужно: декомпозиция перед execution |

**Важно:** Agent.generate() — это одноходовый путь. TaskDecomposer/ExecutionChain для него **не нужны** — они для ConversationAgent.turn().

### 3.2. ConversationAgent (`app/conversation.py:74-93`)

| Что | Статус | Изменения для M16-M18 |
|-----|--------|----------------------|
| `__init__` принимает session_manager | ✅ DONE | Нет |
| `session()` session_manager.resume() | ✅ DONE | Нет |
| `turn()` retry loop | ✅ DONE | Нет |
| `turn()` history.record() | ✅ DONE | Нет |
| `turn()` retry_policy.decide() | ✅ DONE | Нет |
| `turn()` semantic_verifier.verify() | ✅ DONE | Нет |
| `turn()` session_manager.save() | ✅ DONE | Нет |
| **`turn()` AdaptivePlanner** | ❌ NOT WIRED | Нужно: передавать AdaptivePlanner в planner |
| **`turn()` TaskDecomposer** | ❌ NOT WIRED | Нужно: декомпозиция перед execution |
| **`turn()` ExecutionChain** | ❌ NOT WIRED | Нужно: chain execution для multi-step |

### 3.3. Planner (`app/planner/__init__.py`)

| Что | Статус | Изменения |
|-----|--------|-----------|
| Planner protocol | ✅ EXISTS | Нет |
| HeuristicPlanner | ✅ EXISTS | Нет |
| LLMPlanner | ✅ EXISTS | Нет |
| **AdaptivePlanner** | ✅ EXISTS (в `planner/adaptive.py`) | **Нужно:** export из `planner/__init__.py` |

### 3.4. WorkflowEngine (`app/engine/engine.py:173-292`)

| Что | Статус | Изменения |
|-----|--------|-----------|
| execute() | ✅ EXISTS | Нет |
| build_prompt() | ✅ EXISTS | Нет |
| _bind_models() | ✅ EXISTS | Нет |
| cancel() | ✅ EXISTS | Нет |

**WorkflowEngine НЕ требует изменений.** ExecutionChain будет вызывать engine.execute() для каждого шага через execute_fn.

### 3.5. Verifier (`app/engine/verifier.py`)

| Что | Статус | Изменения |
|-----|--------|-----------|
| verify() (structural) | ✅ EXISTS | Нет |
| verify_with_diagnostics() | ✅ EXISTS | Нет |

### 3.6. Job (`app/engine/job.py:20-36`)

| Что | Статус | Изменения |
|-----|--------|-----------|
| attempt field | ✅ EXISTS | Нет |
| error_class field | ✅ EXISTS | Нет |
| State tracking | ✅ EXISTS | Нет |
| **chain_step_index** | ❌ NOT EXISTS | **Нужно:** для multi-step chain tracing |

### 3.7. Asset/AssetStore (`app/assets/`)

| Что | Статус | Изменения |
|-----|--------|-----------|
| AssetStore | ✅ EXISTS | Нет |
| Asset lineage | ✅ EXISTS | Нет |

**AssetStore НЕ требует изменений.** ExecutionChain будет передавать output assets между шагами через execute_fn.

### 3.8. Persistence/SessionManager (`app/context/`)

| Что | Статус | Изменения |
|-----|--------|-----------|
| ContextPersistence | ✅ EXISTS | Нет |
| SessionManager | ✅ EXISTS | Нет |
| **SessionManager для chain state** | ❌ NOT WIRED | **Нужно:** сохранять chain state в context |

### 3.9. SSE/UI (`app/ui.py`)

| Что | Статус | Изменения |
|-----|--------|-----------|
| /turn endpoint | ✅ EXISTS | Нет |
| SSE events (start, status, progress, result, error) | ✅ EXISTS | Нет |
| /api/feedback | ✅ EXISTS | Нет |
| /api/feedback/history | ✅ EXISTS | Нет |
| **SSE chain_progress events** | ❌ NOT EXISTS | **Нужно:** chain_start, step_complete, chain_complete |

### 3.10. Feedback (`app/context/feedback.py`)

| Что | Статус | Изменения |
|-----|--------|-----------|
| FeedbackStore.record() | ✅ EXISTS | Нет |
| FeedbackStore.get_for_session() | ✅ EXISTS | Нет |
| **Feedback → AdaptivePlanner** | ❌ NOT WIRED | **Нужно:** feedback влияет на planning |

---

## 4. Критический анализ Phase 1: AdaptivePlanner → Agent.generate()

### 4.1. Предложение из M13_M18_INTEGRATION_PLAN.md

> "Если execution_history.count() >= 3 → создать AdaptivePlanner вместо HeuristicPlanner"

### 4.2. Проверка нарушений

| Контракт/Инвариант | Нарушается? | Объяснение |
|---------------------|-------------|------------|
| **LLMPlanner** | ❌ НЕТ | AdaptivePlanner использует HeuristicPlanner как fallback, не LLMPlanner |
| **CompositePromptBuilder** | ❌ НЕТ | PromptBuilder вызывается ПОСЛЕ planner.plan(), не зависит от типа planner |
| **Session context** | ⚠️ ДА | AdaptivePlanner не учитывает PlanContext (active_asset_type). См. §4.3 |
| **Provider-neutral architecture** | ❌ НЕТ | Planner не зависит от provider |
| **Deterministic fallback** | ⚠️ ДА | При history < 3 AdaptivePlanner возвращает HeuristicPlanner result — это OK. Но при history ≥ 3 результат может быть НЕдетерминированным (зависит от истории) |
| **M1–M12 invariants** | ❌ НЕТ | Planner не затрагивает execution core |

### 4.3. КРИТИЧЕСКАЯ ПРОБЛЕМА: AdaptivePlanner не учитывает PlanContext

`AdaptivePlanner.plan()` (adaptive.py:35) вызывает `self.fallback.plan(request, context)`, но **НЕ передаёт context в fallback**. Смотри adaptive.py:43:

```python
base_result = self.fallback.plan(request, context)  # ✅ context передаётся
```

Однако `UserPreferences.preferred_params()` (preferences.py:23) НЕ учитывает `active_asset_type`. Это значит:

1. Пользователь делает `image.generate` → получает output
2. Пользователь делает `image.upscale` (context.active_asset_type = "image")
3. AdaptivePlanner может скорректировать params для `image.upscale` на основе истории `image.generate`
4. **НО** `preferred_params("image.upscale")` вернёт params из `image.generate` history, что может быть неверно

**Вывод:** AdaptivePlanner безопасен для use case "тот же capability", но **опасен для cross-capability learning** (generate → upscale).

### 4.4. Рекомендация по Phase 1

**НЕ заменять HeuristicPlanner на AdaptivePlanner.** Вместо этого:

1. **Agent.generate():** оставить HeuristicPlanner как default
2. **ConversationAgent.turn():** передавать AdaptivePlanner как опциональный planner через `__init__`
3. **AdaptivePlanner должен учитывать PlanContext** (active_asset_type) при корректировке params
4. **Порог history:** ≥ 3 records ТОЛЬКО для того же capability (не cross-capability)

---

## 5. Минимальный вертикальный срез

### 5.1. Определение

Вертикальный срез — это **один complete flow** от запроса пользователя до результата, который демонстрирует интеграцию M13–M18.

### 5.2. Предлагаемый срез: "Single-session multi-step с feedback и adaptive planning"

```
Session 1:
  Turn 1: "нарисуй кота 512x512"
    → HeuristicPlanner → image.generate → ComfyUI → SUCCESS
    → history.record() → 1 record
    → session_manager.save()

  Turn 2: "нарисуй собаку"
    → HeuristicPlanner → image.generate → ComfyUI → SUCCESS
    → history.record() → 2 records
    → session_manager.save()

  Turn 3: "нарисуй кота"
    → HeuristicPlanner → image.generate → ComfyUI → SUCCESS
    → history.record() → 3 records
    → session_manager.save()
    → user feedback: rating=2, comment="слишком темно"

Session 2 (новая сессия):
  Turn 1: "нарисуй кота"
    → AdaptivePlanner (history ≥ 3) → скорректированные params → ComfyUI → SUCCESS
    → history.record() → 4 records
    → session_manager.save()

  Turn 2: "нарисуй кота и увеличь разрешение"
    → TaskDecomposer.decompose() → [image.generate, image.upscale]
    → ExecutionChain.execute([
        Step 0: image.generate → SUCCESS (output A)
        Step 1: image.upscale (input A) → SUCCESS (output B)
      ])
    → history.record() для каждого шага
    → session_manager.save()
```

### 5.3. Что этот срез доказывает

| M13 | ✅ history.record() для каждого turn/step |
| M13 | ✅ retry_policy.decide() (если будет failure) |
| M14 | ✅ semantic_verifier.verify() (если задан) |
| M15 | ✅ session_manager.save/resume между сессиями |
| M16 | ✅ AdaptivePlanner.plan() с учётом истории |
| M17 | ✅ feedback записывается и влияет на AdaptivePlanner |
| M18 | ✅ TaskDecomposer + ExecutionChain для multi-step |

### 5.4. Необходимые integration tests

| Тест | Что проверяет |
|------|---------------|
| `test_integration_adaptive_plan_with_history` | AdaptivePlanner используется когда history ≥ 3 для того же capability |
| `test_integration_adaptive_fallback` | AdaptivePlanner fallback на HeuristicPlanner при history < 3 |
| `test_integration_adaptive_with_context` | AdaptivePlanner учитывает PlanContext (active_asset_type) |
| `test_integration_decomposer_single_step` | TaskDecomposer возвращает 1 SubTask для простого запроса |
| `test_integration_decomposer_multi_step` | TaskDecomposer возвращает 2+ SubTask для сложного запроса |
| `test_integration_chain_execute` | ExecutionChain выполняет SubTasks последовательно |
| `test_integration_chain_with_retry` | ExecutionChain retry на failed step |
| `test_integration_feedback_affects_planning` | FeedbackStore.record() → AdaptivePlanner учитывает |
| `test_integration_persistence_across_sessions` | SessionManager resume/save между сессиями |

---

## 6. Порядок интеграции (рекомендация)

### Phase 0: Подготовка (без изменения behavior)

| Действие | Файл | Зачем |
|----------|------|-------|
| Export AdaptivePlanner из `planner/__init__.py` | `app/planner/__init__.py` | Импорт из единого места |
| Export TaskDecomposer, SubTask из `planner/__init__.py` | `app/planner/__init__.py` | Импорт из единого места |
| Добавить `chain_step_index` в Job | `app/engine/job.py` | Multi-step tracing |

### Phase 1: AdaptivePlanner wiring (M16)

| Действие | Файл | Изменение |
|----------|------|-----------|
| AdaptivePlanner учитывает PlanContext | `app/planner/adaptive.py` | `plan(request, context)` → context-aware preferred_params |
| Agent принимает adaptive_planner | `app/agent.py` | `__init__(..., adaptive_planner=None)` |
| ConversationAgent создаёт AdaptivePlanner | `app/conversation.py` | Если execution_history.count() ≥ 3 → AdaptivePlanner |
| Export AdaptivePlanner | `app/planner/__init__.py` | `from app.planner.adaptive import AdaptivePlanner` |

**НЕ трогать:** Agent.generate() default behavior (оставить HeuristicPlanner).

### Phase 2: TaskDecomposer + ExecutionChain wiring (M18)

| Действие | Файл | Изменение |
|----------|------|-----------|
| ConversationAgent проверяет multi-step | `app/conversation.py` | `task_decomposer.decompose(request)` перед execution |
| ConversationAgent использует ExecutionChain | `app/conversation.py` | `ExecutionChain(execute_fn=self._execute_subtask)` |
| Agent._execute_subtask() | `app/agent.py` | Новый метод для execution одного SubTask |
| SSE chain events | `app/ui.py` | `chain_start`, `step_complete`, `chain_complete` |

**НЕ трогать:** Существующий single-step path в ConversationAgent.turn().

### Phase 3: Feedback → AdaptivePlanner (M17 → M16)

| Действие | Файл | Изменение |
|----------|------|-----------|
| AdaptivePlanner принимает feedback_store | `app/planner/adaptive.py` | `__init__(..., feedback_store=None)` |
| AdaptivePlanner учитывает feedback | `app/planner/adaptive.py` | `plan()` → weighted avg с учётом ratings |
| ConversationAgent передаёт feedback_store | `app/conversation.py` | В AdaptivePlanner constructor |

**НЕ трогать:** UI feedback endpoints (оставить как есть).

---

## 7. Риски и митигации

| Риск | Вероятность | Impact | Митигация |
|------|-------------|--------|-----------|
| AdaptivePlanner неправильно корректирует params | Medium | High | Min attempts threshold (≥3), user override > learned |
| TaskDecomposer неправильно разбивает request | Medium | Medium | Fallback to single-step (1 SubTask = существующий path) |
| ExecutionChain fails на шаге 2 | Medium | High | Per-step retry, cancel support, graceful degradation |
| Feedback искажает analytics | Low | Medium | Weighted average, min samples, user explicit > learned |
| AdaptivePlanner ломает PlanContext | High | High | **Обязательно:** context-aware preferred_params |

---

## 8. Что НЕ нужно менять

| Компонент | Почему |
|-----------|--------|
| M1–M12 execution chain | FROZEN, работает |
| HeuristicPlanner | Fallback, не удалять |
| CompositePromptBuilder | Fallback, не удалять |
| Verifier.verify() | Structural fallback |
| WorkflowEngine.execute() | Core execution |
| Asset/AssetStore | Фундамент lineage |
| Provider/Registry | Boundary |
| UI /turn, /api/feedback | Уже работают |

---

## 9. Итоговая таблица статусов

| Milestone | Код | Unit tests | Wiring | Integration tests | E2E | Итоговый статус |
|-----------|-----|------------|--------|-------------------|-----|-----------------|
| **M13** | ✅ | ✅ 32 pass | ✅ WIRED | ❌ NOT TESTED | ❌ NOT TESTED | PARTIALLY VERIFIED |
| **M14** | ✅ | ✅ 23 pass | ✅ WIRED | ❌ NOT TESTED | ❌ NOT TESTED | MOCK/UNIT ONLY |
| **M15** | ✅ | ✅ 14 pass | ✅ WIRED | ❌ NOT TESTED | ❌ NOT TESTED | PARTIALLY VERIFIED |
| **M16** | ✅ | ✅ 16 pass | ❌ NOT WIRED | ❌ NOT TESTED | ❌ NOT TESTED | NOT INTEGRATED |
| **M17** | ✅ | ✅ 11 pass | ⚠️ PARTIAL | ❌ NOT TESTED | ❌ NOT TESTED | NOT INTEGRATED |
| **M18** | ✅ | ✅ 17 pass | ❌ NOT WIRED | ❌ NOT TESTED | ❌ NOT TESTED | NOT INTEGRATED |

---

## 10. Рекомендация

### Какой milestone интегрировать первым

**M16 (AdaptivePlanner) — ПЕРВЫМ.**

### Почему именно его

1. **Самый низкий риск:** AdaptivePlanner уже существует и работает standalone
2. **Самый высокий ROI:** AdaptivePlanner улучшает качество planning для всех существующих вызовов
3. **Не требует ComfyUI:** Lогика планирования не зависит от execution backend
4. **Не ломает M1–M12:** HeuristicPlanner остаётся fallback
5. **Подготовка для M17:** Feedback → AdaptivePlanner — естественный следующий шаг

### Какие изменения потребуются

1. `app/planner/adaptive.py`: AdaptivePlanner учитывает PlanContext (active_asset_type)
2. `app/planner/__init__.py`: export AdaptivePlanner
3. `app/agent.py`: `__init__` принимает `adaptive_planner` parameter
4. `app/conversation.py`: создаёт AdaptivePlanner когда history ≥ 3 для того же capability

### Какие тесты должны доказать интеграцию

1. `test_integration_adaptive_with_history`: AdaptivePlanner используется когда history ≥ 3
2. `test_integration_adaptive_fallback`: AdaptivePlanner fallback на HeuristicPlanner при history < 3
3. `test_integration_adaptive_context_aware`: AdaptivePlanner учитывает PlanContext

### Какие M13–M18 пока нельзя считать завершёнными

| Milestone | Почему не завершён |
|-----------|-------------------|
| **M13** | Нет E2E теста с реальным retry на ComfyUI |
| **M14** | Все тесты с mock vision API, нет реального вызова |
| **M15** | Нет теста persistence после restart процесса |
| **M16** | Не подключён к Agent/ConversationAgent |
| **M17** | Feedback не влияет на планирование |
| **M18** | TaskDecomposer/ExecutionChain не используются |

---

*Документ является DRAFT FOR APPROVAL. Production code не изменялся.*
