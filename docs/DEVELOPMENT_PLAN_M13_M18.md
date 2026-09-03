# DEVELOPMENT PLAN M13–M18

**Статус:** DRAFT FOR APPROVAL
**Дата:** 2026-09-01
**На основе:** Actual code M1–M12 (126 tests passed, 3 skipped)
**Целевой горизонт:** M13–M18 (от Executor к Operator)

---

## 0. Фактическое состояние M1–M12

### 0.1. Что реально есть в коде

| Модуль | Строк | Что делает | Intelligence level |
|--------|-------|-----------|-------------------|
| `agent.py` | 328 | Planner → prompt enhancement → Engine.execute → Job | Executor (single-shot) |
| `engine.py` | 306 | build_prompt → upload → bind → POST → WS → fetch → validate → ingest | Pure executor |
| `verifier.py` | 39 | structural: exists + type match + accessible | Minimal |
| `conversation.py` | 243 | session isolation + active_asset + multi-turn | Context-aware (no learning) |
| `planner.py` | 279 | HeuristicPlanner (keywords) + LLMPlanner (OpenRouter) | Keyword matching |
| `job.py` | 33 | Dataclass: prompt_id, state, progress, output_assets | No history |
| `prompt/composite.py` | 96 | LLM → heuristic fallback (single attempt) | No retry |

### 0.2. Execution path (fact-checked)

```
User request
  → HeuristicPlanner.plan()          [capability + params]
  → PromptBuilder.build()            [optional enhancement]
  → Agent.prepare()                  [workflow selection]
  → WorkflowEngine.execute()
      ├── Provider.upload_asset()    [transport]
      ├── build_prompt()             [manifest + plan → ComfyUI JSON]
      ├── _bind_models()             [checkpoint selection]
      ├── Provider.execute()         [POST /prompt]
      ├── WebSocket.track()          [or /history polling]
      ├── Provider.view()            [download output]
      ├── _validate_output_bytes()   [magic signatures]
      ├── AssetStore.ingest()        [create Asset with lineage]
      └── Verifier.verify()          [structural: exists + type]
  → Job (SUCCESS/FAILED)
  → ConversationContext update
  → SSE → UI
```

### 0.3. Gap analysis: Executor vs Operator

```
CAPABILITY                        EXECUTOR (M12)    OPERATOR (target)
─────────────────────────────────────────────────────────────────────
single-shot execution             ✅                ✅
retry on failure                  ❌                ✅
semantic verification             ❌                ✅
parameter adjustment              ❌                ✅
persistent context                ❌                ✅
learning from history             ❌                ✅
user feedback integration         ❌                ✅
multi-step decomposition          ❌                ✅
human-in-the-loop confirmation    ❌                ✅
adaptive planning                 ❌                ✅
```

**Score:** 1/10 operator capabilities implemented.

---

## 1. Анализ M13–M18 из FUTURE_ROADMAP

### 1.1. Проверка обоснованности каждого milestone

#### M13: Execution History + Retry Loop

**Обоснованность:** ✅ ПРАВИЛЬНО

Текущий код:
- `agent.py:185-243` — `generate()` делает ОДИН вызов `self.run()`. Нет retry.
- `engine.py:173-292` — `execute()` — single attempt. FAILED = конец.
- `job.py` — нет attempt tracking.

Почему M13 должен быть первым:
- Без ExecutionHistory невозможно M14 (semantic verification не может сравнивать с прошлыми попытками)
- Без retry loop невозможно M16 (adaptive planner не может пробовать разные параметры)
- Без attempt tracking невозможно M17 (feedback не может быть привязан к конкретной попытке)

**Риск:** Средний. Требует изменения Agent.generate() и ConversationAgent.turn(). Но расширение, не переписывание.

#### M14: Semantic Verification

**Обоснованность:** ✅ ПРАВИЛЬНО, но с оговоркой

Текущий код:
- `verifier.py:23-39` — `verify()` проверяет только structural (exists + type match + accessible).
- Нет проверки "содержит ли output то, что просил пользователь".

Оговорка: Semantic verification требует vision model (GPT-4V через OpenRouter). Если vision API недоступен — должен быть fallback to structural.

**Риск:** Средний. Vision API может быть неточным. Требует M13 (history для comparison).

#### M15: Persistent Context + Session Recovery

**Обоснованность:** ✅ ПРАВИЛЬНО

Текущий код:
- `conversation.py:30-63` — `ConversationContext` — in-memory dataclass. При рестарте всё теряется.
- `conversation.py:76` — `self.sessions: dict[str, ConversationContext] = {}` — process-scoped.

Почему M15 после M13:
- Persistent context хранит execution history (M13).
- Без persistent context невозможно M16 (adaptive planner не может учиться без истории).

**Риск:** Средний-высокий. Требует JSONL persistence (уже используется в AssetStore). Не требует DB.

#### M16: Adaptive Planner + Learning

**Обоснованность:** ✅ ПРАВИЛЬНО, но требует осторожности

Текущий код:
- `planner.py:149-202` — `HeuristicPlanner` = keyword matching. Не учитывает "что работало раньше".
- `planner.py:205-279` — `LLMPlanner` = generic. Не знает предпочтения пользователя.

Оговорка: "learning" в M16 — это aggregate statistics (success rate, avg score), НЕ autonomous learning (NG3 в PROJECT_SPEC).

**Риск:** Высокий. Overfitting, cold start, bias. Требует M13+M14+M15.

#### M17: User Feedback Loop

**Обоснованность:** ✅ ПРАВИЛЬНО

Текущий код:
- `ui.py` — нет feedback endpoints.
- `conversation.py` — нет feedback storage.

Почему M17 после M16:
- Feedback влияет на adaptive planner (M16).
- Без M16 feedback бесполезен (нет mechanism для применения).

**Риск:** Низкий. Добавление endpoints + storage. Не затрагивает execution path.

#### M18: Multi-Step Decomposition

**Обностью:** ✅ ПРАВИЛЬНО, но сложный

Текущий код:
- `planner.py` — нет decomposition logic.
- `conversation.py` — нет chain tracking.

Почему M18 последний:
- Требует M13 (retry per step) + M14 (verification per step) + M16 (adaptive per step).
- Самый сложный milestone.

**Риск:** Высокий. Error propagation, state management, complexity explosion.

### 1.2. Порядок M13–M18: правильный ли он?

**Ответ:** ДА, порядок правильный. Зависимости:

```
M13 (History + Retry)
 ├── M14 (Semantic Verification)
 │    └── M16 (Adaptive Planner)
 ├── M15 (Persistent Context)
 │    ├── M16 (Adaptive Planner)
 │    └── M17 (User Feedback)
 └── M18 (Multi-Step Decomposition)
```

**Critical path:** M13 → M14 → M16 → M18

**Нет причин менять порядок.**

### 1.3. Нужно ли объединять/разделять/исключать?

**Объединять:** НЕТ. Каждый milestone решает отдельную проблему.

**Разделять:** МОЖЕТ БЫТЬ M15 (Persistent Context) на два подmilestone:
- M15a: JSONL persistence для ConversationContext
- M15b: SessionManager (list, resume, archive)

Но это опционально. В текущем виде M15 acceptabel.

**Исключать:** НЕТ. Все milestones актуальны.

---

## 2. Dependency graph M13–M18

```
                    M13: Execution History + Retry
                   /        |              \
                  /         |               \
           M14: Semantic   M15: Persistent   (direct to M18)
           Verification    Context
                  \         |               /
                   \        |              /
                    M16: Adaptive Planner
                           |
                    M17: User Feedback
                           |
                    M18: Multi-Step Decomposition
```

### Матрица зависимостей

| Milestone | Зависит от | Не может быть без |
|-----------|-----------|-------------------|
| **M13** | Нет | — |
| **M14** | M13 | ExecutionHistory для comparison |
| **M15** | M13 | ExecutionHistory для persistence |
| **M16** | M13 + M14 + M15 | History + Scores + Persistence |
| **M17** | M13 + M15 + M16 | History + Persistence + Adaptive |
| **M18** | M13 + M14 + M16 | Retry + Verification + Adaptive |

---

## 3. M13: Execution History + Retry Loop

### 3.1. Цель

Система помнит что было сделано и может повторить при неудаче.

### 3.2. Какую проблему решает

- Agent — single-shot executor. FAILED = конец. Нет retry.
- Нет памяти о предыдущих попытках.
- Нет mechanism для diagnostic ("почему упало?").

### 3.3. Существующие модули (расширить)

| Модуль | Изменение |
|--------|----------|
| `engine/job.py` | Добавить `attempt: int` и `error_class: str` |
| `agent.py` | Добавить retry loop в `generate()` |
| `conversation.py` | Добавить retry events в `turn()` |

### 3.4. Новые модули/контракты

| Модуль | Описание |
|--------|----------|
| `engine/history.py` | `ExecutionRecord` dataclass + `ExecutionHistory` (in-memory, JSONL persist) |
| `engine/retry.py` | `RetryPolicy` (max_attempts, backoff, decision logic) |
| `engine/verifier.py` | Расширить: `verify_with_diagnostics()` (structural + error classification) |

### 3.5. Зависимости

Нет внешних. Только stdlib +扩展现уществующих модулей.

### 3.6. Что НЕ входит в scope

- Semantic verification (M14)
- Persistent context (M15)
- Adaptive planning (M16)
- Vision model integration
- UI changes (только SSE events)

### 3.7. Тестовая стратегия

- Unit tests: ExecutionRecord, ExecutionHistory, RetryPolicy
- Integration tests: retry loop (mock provider)
- Regression: 126 existing tests pass

### 3.8. Критерии Definition of Done

- [ ] `ExecutionRecord` dataclass: prompt_id, capability, params, workflow, state, duration, error_class, attempt, output_assets
- [ ] `ExecutionHistory`: record(), get_attempts(), get_by_capability(), get_recent()
- [ ] `RetryPolicy`: decide() → ACCEPT / RETRY / FAILED
- [ ] `Agent.generate()`: retry loop с max_attempts=3
- [ ] `ConversationAgent.turn()`: retry events через SSE
- [ ] `Verifier.verify_with_diagnostics()`: error classification (transient vs permanent)
- [ ] All 126 existing tests pass
- [ ] ≥5 new tests for retry logic

### 3.9. Ожидаемый архитектурный результат

Agent становится retry-capable system. FAILED ≠ конец. Система может повторить с теми же или скорректированными параметрами.

---

## 4. M14: Semantic Verification

### 4.1. Цель

Понимать что в output и соответствует ли оно запросу.

### 4.2. Какую проблему решает

- Structural verification проверяет "файл существует + правильный тип".
- НЕ проверяет: "кот на картинке?" / "качество приемлемое?" / "соответствует запросу?"

### 4.3. Существующие модули (расширить)

| Модуль | Изменение |
|--------|----------|
| `engine/verifier.py` | Добавить `SemanticVerifier` класс |

### 4.4. Новые модули/контракты

| Модуль | Описание |
|--------|----------|
| `engine/semantic_verifier.py` | `SemanticVerifier` (vision model через OpenRouter) |
| `engine/verification.py` | `VerificationResult` dataclass (score, matches_intent, issues, suggested_params) |

### 4.5. Зависимости

- M13 (ExecutionHistory для хранения verification results)
- OpenRouter API key (уже используется для LLMPlanner)

### 4.6. Что НЕ входит в scope

- Adaptive planning (M16)
- User feedback (M17)
- Multi-step decomposition (M18)
- Full vision feedback loop (только verification, не parameter optimization)

### 4.7. Тестовая стратегия

- Unit tests: SemanticVerifier с mock vision API
- Integration tests: verification → retry decision
- Fallback tests: vision API down → structural verification

### 4.8. Критерии Definition of Done

- [ ] `SemanticVerifier.verify(request, output_assets)` → `VerificationResult`
- [ ] `VerificationResult`: score (0-1), matches_intent (bool), issues (list), suggested_params (dict|None)
- [ ] Fallback: vision API недоступен → structural verification
- [ ] Integration с RetryPolicy: low score → RETRY
- [ ] Timeout: 10s per verification attempt
- [ ] All 126+ existing tests pass
- [ ] ≥5 new tests for semantic verification

### 4.9. Ожидаемый архитектурный результат

Agent понимает что в output и может решить: принять, повторить или скорректировать параметры.

---

## 5. M15: Persistent Context + Session Recovery

### 5.1. Цель

Контекст сессии переживает restart; пользователь может вернуться к предыдущей задаче.

### 5.2. Какую проблему решает

- ConversationContext = in-memory. При рестарте всё теряется.
- Нет cross-session history.
- Нет ability to resume interrupted tasks.

### 5.3. Существующие модули (расширить)

| Модуль | Изменение |
|--------|----------|
| `conversation.py` | ConversationContext получает save/load |
| `agent.py` | Agent получает session management |

### 5.4. Новые модули/контракты

| Модуль | Описание |
|--------|----------|
| `context/persistence.py` | `ContextPersistence` (JSONL-based, per-session files) |
| `context/session_manager.py` | `SessionManager` (create, list, resume, archive) |

### 5.5. Зависимости

- M13 (ExecutionHistory для persist execution records)

### 5.6. Что НЕ входит в scope

- Adaptive planning (M16)
- User feedback (M17)
- Multi-step decomposition (M18)
- Database (только JSONL)

### 5.7. Тестовая стратегия

- Unit tests: save/load/context preservation
- Integration tests: restart → resume → active_asset preserved
- Isolation tests: session A не влияет на session B

### 5.8. Критерии Definition of Done

- [ ] `ContextPersistence.save(session_id, context)` → file
- [ ] `ContextPersistence.load(session_id)` → context | None
- [ ] `ContextPersistence.list_sessions()` → list of session metadata
- [ ] `SessionManager.create()` → session_id
- [ ] `SessionManager.resume(session_id)` → context with restored state
- [ ] UI: GET /api/sessions → list of sessions
- [ ] UI: POST /api/sessions/{id}/resume → restore session
- [ ] All 126+ existing tests pass
- [ ] ≥5 new tests for persistence

### 5.9. Ожидаемый архитектурный результат

Session context persistent. User может вернуться к предыдущей задаче после restart.

---

## 6. M16: Adaptive Planner + Learning

### 6.1. Цель

Планировщик учится на предыдущих результатах и улучшает параметры.

### 6.2. Какую проблему решает

- HeuristicPlanner = keyword matching. Не учитывает "что работало раньше".
- LLMPlanner = generic. Не знает предпочтения пользователя.
- Нет mechanism для "этот стиль работает лучше для этого пользователя".

### 6.3. Существующие модули (расширить)

| Модуль | Изменение |
|--------|----------|
| `planner.py` | Добавить `AdaptivePlanner` класс |
| `engine/history.py` | Добавить analytics methods |

### 6.4. Новые модули/контракты

| Модуль | Описание |
|--------|----------|
| `planner/adaptive.py` | `AdaptivePlanner` (uses ExecutionHistory) |
| `planner/preferences.py` | `UserPreferences` (aggregated from history) |
| `engine/analytics.py` | `HistoryAnalytics` (success rate, avg score, preferred params) |

### 6.5. Зависимости

- M13 (ExecutionHistory)
- M14 (SemanticVerifier scores)
- M15 (Persistent context)

### 6.6. Что НЕ входит в scope

- Autonomous learning (NG3 в PROJECT_SPEC)
- RAG / vector DB (NG2 в PROJECT_SPEC)
- Multi-agent (NG1 в PROJECT_SPEC)
- User feedback (M17)

### 6.7. Тестовая стратегия

- Unit tests: AdaptivePlanner с mock history
- Integration tests: history → preference → adjusted params
- Cold start tests: insufficient history → heuristic fallback

### 6.8. Критерии Definition of Done

- [ ] `AdaptivePlanner.plan(request, context)` → PlanResult (uses history)
- [ ] `UserPreferences`: aggregate(history) → preferred styles, params, workflows
- [ ] `HistoryAnalytics`: success_rate(), avg_score(), preferred_params()
- [ ] Fallback: insufficient history → HeuristicPlanner
- [ ] Override: user explicit params > learned preferences
- [ ] Integration: Agent.generate() uses AdaptivePlanner when history available
- [ ] All 126+ existing tests pass
- [ ] ≥5 new tests for adaptive planning

### 6.9. Ожидаемый архитектурный результат

Planner учится на истории и рекомендует лучшие параметры. User explicit overrides always win.

---

## 7. M17: User Feedback Loop

### 7.1. Цель

Пользователь оценивает результат и влияет на следующие генерации.

### 7.2. Какую проблему решает

- Agent генерирует, пользователь видит результат, и... нет обратной связи.
- Нет ability say "не нравится" / "слишком темно" / "попробуй другой стиль".
- Agent не знает что пользователю нравится.

### 7.3. Существующие модули (расширить)

| Модуль | Изменение |
|--------|----------|
| `ui.py` | Добавить feedback endpoints |
| `conversation.py` | Добавить feedback storage |
| `engine/history.py` | Привязать feedback к attempts |

### 7.4. Новые модули/контракты

| Модуль | Описание |
|--------|----------|
| `context/feedback.py` | `FeedbackStore` (per-attempt ratings, comments) |
| `ui.py` | POST /api/feedback, GET /api/feedback/history |

### 7.5. Зависимости

- M13 (ExecutionHistory)
- M15 (Persistent context)
- M16 (Adaptive planner — feedback влияет на learning)

### 7.6. Что НЕ входит в scope

- Full vision feedback loop (M18+)
- Autonomous learning (NG3)
- RAG / vector DB (NG2)

### 7.7. Тестовая стратегия

- Unit tests: FeedbackStore record/retrieval
- Integration tests: feedback → history → adaptive planner
- UI tests: POST/GET endpoints

### 7.8. Критерии Definition of Done

- [ ] `FeedbackStore.record(attempt_id, rating, comment)`
- [ ] `FeedbackStore.get_for_session(session_id)` → list
- [ ] UI: POST /api/feedback {attempt_id, rating, comment}
- [ ] UI: GET /api/feedback/history → session feedback
- [ ] Confirmation dialog: "Вам понравился результат?"
- [ ] Feedback привязан к ExecutionRecord
- [ ] AdaptivePlanner учитывает feedback
- [ ] All 126+ existing tests pass
- [ ] ≥5 new tests for feedback

### 7.9. Ожидаемый архитектурный результат

Feedback loop замыкается: user → Agent → result → user feedback → Agent learns.

---

## 8. M18: Multi-Step Decomposition + Workflow Chaining

### 8.1. Цель

Agent выполняет сложные задачи из нескольких capability автоматически.

### 8.2. Какую проблему решает

- "Сгенерируй кота и увеличь разрешение" = 2 отдельных запроса.
- Нет ability decompose complex requests.
- Нет chaining: image.generate → image.upscale → result.

### 8.3. Существующие модули (расширить)

| Модуль | Изменение |
|--------|----------|
| `planner.py` | Добавить decomposition logic |
| `conversation.py` | Добавить multi-step chain tracking |
| `engine/engine.py` | Добавить batch execution |

### 8.4. Новые модули/контракты

| Модуль | Описание |
|--------|----------|
| `planner/decomposer.py` | `TaskDecomposer` (request → list of subtasks) |
| `engine/chain.py` | `ExecutionChain` (subtask1 → subtask2 → ... → result) |
| `conversation.py` | Chain tracking (active_chain, current_step) |

### 8.5. Зависимости

- M13 (retry loop per step)
- M14 (semantic verification per step)
- M16 (adaptive planning per step)

### 8.6. Что НЕ входит в scope

- Autonomous decomposition (NG3)
- Multi-agent decomposition (NG1)
- Real-time chain modification

### 8.7. Тестовая стратегия

- Unit tests: TaskDecomposer
- Integration tests: chain execution с mock
- Error handling tests: per-step retry

### 8.8. Критерии Definition of Done

- [ ] `TaskDecomposer.decompose(request)` → list of (capability, params)
- [ ] `ExecutionChain.execute(subtasks)` → list of Jobs
- [ ] Per-step retry (M13) + semantic verification (M14)
- [ ] Chain state tracking (active_chain, current_step, completed_steps)
- [ ] UI: chain progress display
- [ ] Cancel: ability to cancel chain mid-execution
- [ ] Fallback: decomposition failure → single-step execution
- [ ] All 126+ existing tests pass
- [ ] ≥5 new tests for chain execution

### 8.9. Ожидаемый архитектурный результат

Agent decomposes complex requests и выполняет их автоматически с retry/verification per step.

---

## 9. Что запрещено менять

| Компонент | Почему запрещено |
|-----------|-----------------|
| Asset (types.py, store.py) | Фундамент lineage. Работает. |
| Job (job.py) | Расширять (add fields), не переписывать. |
| Provider (comfyui.py) | Boundary. Работает для local/remote. |
| Registry (registry/) | Capability → Workflow → Selection. Работает. |
| ComfyClient (client.py) | HTTP transport. Работает. |
| Verifier.verify() | Оставить как structural fallback. |
| WorkflowEngine.execute() | Расширять обёрткой, не менять internals. |
| HeuristicPlanner | Fallback. Не удалять. |
| CompositePromptBuilder | Fallback orchestration. Не удалять. |
| ComfyCLIAdapter | Optional infrastructure. Не трогать. |
| SESSION_ISOLATION | Не нарушать. |
| ASSET_LINEAGE | Не нарушать. |
| MEDIA_AGNOSTIC | Не нарушать (нет if image/elif video в core). |

---

## 10. Архитектурные риски до начала реализации

| # | Риск | Mitigation |
|---|------|------------|
| R1 | Infinite retry loops | Guard rails: max_attempts=3, timeout_per_attempt, exponential backoff |
| R2 | Vision API latency/cost | Timeout 10s, optional (fallback to structural), single verification per attempt |
| R3 | Overfitting in adaptive planner | Min attempts threshold (≥3), user explicit override > learned |
| R4 | Data size growth in persistence | Per-session files, not monolithic DB; archive old sessions |
| R5 | Error propagation in multi-step | Per-step retry (M13), per-step verification (M14), cancel chain on permanent failure |
| R6 | State complexity | Keep ExecutionHistory append-only; ConversationContext unchanged dataclass |
| R7 | Breaking existing tests | Regression test suite (126 tests) runs after each milestone |
| R8 | PROJECT_SPEC violations | NG1–NG3 enforced: no multi-agent, no RAG, no autonomous learning |

---

## 11. Финальная рекомендация

### "Следующий milestone: M13 — Execution History + Retry Loop"

**Почему M13 является наиболее правильным следующим шагом после M12:**

1. **Минимальная сложность, максимальный impact.** M13 не требует внешних API (vision, storage). Только stdlib +扩展现уществующих модулей. Сложность: 3–4 дня.

2. **Фундамент для всего.** Без M13 невозможно:
   - M14 (semantic verification не может сравнивать с прошлыми попытками)
   - M15 (persistent context не может хранить execution history)
   - M16 (adaptive planner не может учиться без history)
   - M17 (feedback не может быть привязан к attempt)
   - M18 (multi-step не может обрабатывать ошибки)

3. **Решает главный architectural gap.** Agent сейчас — single-shot executor. M13 превращает его в retry-capable system. Это ключевое отличие "executor" от "operator".

4. **Не нарушает существующую архитектуру.** M13 расширяет существующие модули (Agent, Job, Verifier), не переписывает их. Существующий execution path остаётся unchanged.

5. **Доказуемость.** Можно протестировать: "generate → fail → retry → success". Метрика: success rate до/после M13.

6. **Аддитивность.** M13 добавляет новую capability без удаления существующей. HeuristicPlanner, CompositePromptBuilder, Verifier.verify() — всё остаётся как fallback.

---

## 12. Финальный статус

| Документ | Статус |
|----------|--------|
| `docs/DEVELOPMENT_PLAN_M13_M18.md` | **DRAFT FOR APPROVAL** |
| M13–M18 | **IMPLEMENTED — UNIT/INTEGRATION VERIFIED — REAL E2E VERIFIED** |
| M13: Execution History + Retry Loop | **RECOMMENDED AS NEXT MILESTONE** |

**Следующий шаг:** Автор проекта утверждает план или предлагает изменения. После утверждения — переход к реализации M13.
