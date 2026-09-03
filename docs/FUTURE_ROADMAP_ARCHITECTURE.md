# FUTURE ROADMAP — ARCHITECTURE-LEVEL DEVELOPMENT PLAN

**Статус:** DRAFT FOR DISCUSSION
**Дата:** 2026-09-01
**На основе:** Actual code M1–M12 (не только документации)
**Целевой горизонт:** M13–M18

---

## 0. Ключевой вопрос

**Где сейчас находится Agent между "executor" и "operator"?**

```
EXECUTOR                    OPERATOR
───────                     ────────
одноразовый pipeline        feedback loop
single attempt              retry/correction
нет memory                  persistent context
planner = keywords          adaptive planner
structural verification     semantic understanding
user drives all decisions   agent suggests decisions
no learning                 learns from history
```

**Ответ:** Agent сейчас ≈ 40% operator. У него есть pipeline (M1–M12), но нет feedback loop. Это ключевой gap.

---

## 1. Что является НАСТОЯЩИМ ядром будущего Agent?

### 1.1. Текущие компоненты и их роли

| Компонент | Что делает | Является ли intelligence? |
|-----------|-----------|--------------------------|
| Planner | request → capability + params | Частично (keyword/LLM, без learning) |
| Engine | prompt → execution → output | Нет (pure executor) |
| Verifier | output == contract? | Нет (structural only) |
| Provider | transport abstraction | Нет (pure transport) |
| ConversationAgent | session + context | Частично (active_asset, но no learning) |
| PromptBuilder | prompt enhancement | Частично (templates/LLM, но без feedback) |

### 1.2. Будущий intelligence layer

**Нужно:** Компонент, который соединяет execution result → understanding → next decision.

```
                    CURRENT                         FUTURE
                    ───────                         ──────
                    Planner                         Planner
                      │                               │
                      ▼                               ▼
                    Engine          ══►          Execution Loop
                      │                               │
                      ▼                               ▼
                    Verifier                     Verifier (semantic)
                      │                               │
                      ▼                               ▼
                    Done                         Decision Engine
                                                    │
                                              ┌─────┴─────┐
                                              ▼           ▼
                                          retry       result
```

**Центральный intelligence layer = Decision Engine.**

Это НЕ отдельный модуль "DecisionEngine". Это композиция:
1. **SemanticVerifier** — понимает что в output (vision model)
2. **ExecutionHistory** — хранит что было сделано и чем закончилось
3. **AdaptivePlanner** — учится на history, корректирует параметры
4. **RetryPolicy** — decide: retry / adjust / ask / accept

### 1.3. A. Ответ: Настоящее ядро будущего Agent

**SemanticVerifier + ExecutionHistory + AdaptivePlanner + RetryPolicy** — композиция, а не один модуль.

Но **фундамент** для всей этой композиции — **ExecutionHistory**. Без него:
- Verifier не может сравнить с предыдущими попытками
- AdaptivePlanner не может учиться
- RetryPolicy не может знать что уже пробовал

**Поэтому ExecutionHistory — самый приоритетный модуль.**

---

## 2. B. Где должна находиться intelligence?

### 2.1. Текущее распределение

```
Deterministic infrastructure:
  ├── ComfyClient (HTTP transport)
  ├── Provider (asset transport)
  ├── AssetStore (storage + lineage)
  ├── Registry (capability → workflow → selection)
  └── RuntimeInfo (hardware detection)

Planning:
  ├── HeuristicPlanner (keywords)
  └── LLMPlanner (OpenRouter)

Execution:
  └── WorkflowEngine (prompt build → execute → fetch → verify)

Verification:
  └── Verifier (structural: exists + type match + accessible)

Feedback:
  └── ОТСУТСТВУЕТ

Learning:
  └── ОТСУТСТВУЕТ

User interaction:
  └── UI (SSE + /turn + preview)
```

### 2.2. Будущее распределение

```
Deterministic infrastructure:
  ├── ComfyClient              (БЕЗ ИЗМЕНЕНИЙ)
  ├── Provider                  (БЕЗ ИЗМЕНЕНИЙ)
  ├── AssetStore                (БЕЗ ИЗМЕНЕНИЙ)
  ├── Registry                  (БЕЗ ИЗМЕНЕНИЙ)
  └── RuntimeInfo               (БЕЗ ИЗМЕНЕНИЙ)

Planning:
  ├── HeuristicPlanner          (БЕЗ ИЗМЕНЕНИЙ, fallback)
  ├── LLMPlanner                (расширить: execution history context)
  └── AdaptivePlanner           (НОВЫЙ: учится на history)

Execution:
  ├── WorkflowEngine            (расширить: retry loop, parameter adjustment)
  └── ExecutionPlan             (расширить: attempt counter)

Verification:
  ├── Verifier                  (БЕЗ ИЗМЕНЕНИЙ, structural)
  └── SemanticVerifier          (НОВЫЙ: vision model, quality check)

Feedback:
  ├── ExecutionHistory          (НОВЫЙ: persist execution results)
  └── RetryPolicy               (НОВЫЙ: decide retry/adjust/ask/accept)

Learning:
  ├── ParameterAdaptation       (НОВЫЙ: adjust params based on history)
  └── WorkflowSelection         (НОВЫЙ: select best workflow from history)

User interaction:
  ├── UI                        (расширить: confirm/cancel/retry events)
  └── HumanInTheLoop            (НОВЫЙ: ask user before risky actions)
```

---

## 3. C. Будущий execution cycle

### 3.1. Текущий cycle (M1–M12)

```
request → understand → plan → execute → verify → result
    ✓        ✓          ✓       ✓         ✓        ✓
    │        │          │       │         │        │
    │        │          │       │         │        └─ AssetStore.ingest
    │        │          │       │         └─ Verifier.verify (structural)
    │        │          │       └─ WorkflowEngine.execute
    │        │          └─ Planner.plan
    │        └─ request parsing (builtin)
    └─ user input
```

**Что есть:** request → plan → execute → structural verify → result
**Чего нет:** observe → semantic verify → decide → correct → learn

### 3.2. Будущий cycle (M13+)

```
request → understand → plan → execute → observe → verify → decide → correct/retry/ask → learn → result
    ✓        ✓          ✓       ✓         ✗        ✗        ✗           ✗               ✗       ✓
    │        │          │       │         │        │        │           │               │       │
    │        │          │       │         │        │        │           │               │       └─ AssetStore.ingest
    │        │          │       │         │        │        │           │               └─ ExecutionHistory.record
    │        │          │       │         │        │        │           └─ RetryPolicy.decide
    │        │          │       │         │        │        └─ DecisionEngine.evaluate
    │        │          │       │         │        └─ SemanticVerifier.verify
    │        │          │       │         └─ WorkflowEngine.execute
    │        │          │       └─ Planner.plan
    │        │          └─ Planner.plan (with history context)
    │        └─ request parsing
    └─ user input
```

### 3.3. Детализация нового цикла

```
PHASE 1: UNDERSTAND (существует)
  User request → Planner → (capability, params)

PHASE 2: PLAN (существует + расширить)
  (capability, params) → WorkflowEngine.prepare → ExecutionPlan

PHASE 3: EXECUTE (существует)
  ExecutionPlan → ComfyUI → Job → output Assets

PHASE 4: OBSERVE (НЕ существует)
  Job result → ExecutionRecord {
    prompt, params, capability, workflow,
    success/failure, duration, output_asset_ids,
    error_message, attempt_number
  }

PHASE 5: VERIFY SEMANTIC (НЕ существует)
  Output Assets + original request → SemanticVerifier
  → VerificationResult {
    score: float (0-1),
    matches_intent: bool,
    issues: list[str],
    suggested_params: dict | None
  }

PHASE 6: DECIDE (НЕ существует)
  VerificationResult + ExecutionHistory → RetryPolicy
  → Decision: ACCEPT | RETRY | ADJUST | ASK_USER

PHASE 7: CORRECT (НЕ существует,分支)
  RETRY → same params, attempt++
  ADJUST → modified params, attempt++
  ASK_USER → present result, ask for feedback
  ACCEPT → return result

PHASE 8: LEARN (НЕ существует)
  ExecutionRecord → ExecutionHistory (persist)
  Success/failure patterns → AdaptivePlanner (future)
```

---

## 4. Что НЕ нужно строить (D)

### 4.1. Преждевременные features

| Feature | Почему преждевременно | Когда строить |
|---------|----------------------|---------------|
| **Multi-step decomposition** | Нет retry loop — ошибка в шаге 1 крашит весь pipeline | После M14 (retry loop) |
| **Autonomous learning** | NG3 в PROJECT_SPEC: "не является autonomous learning system" | Не строить (архитектурный non-goal) |
| **RAG / vector DB** | NG2 в PROJECT_SPEC: "не является RAG / vector database" | Не строить (архитектурный non-goal) |
| **Multi-agent** | NG1 в PROJECT_SPEC: "не является multi-agent system" | Не строить (архитектурный non-goal) |
| **Full vision feedback loop** | Требует semantic verification фундамента | После M15 |
| **User profiles / preferences** | Требует persistent context + feedback collection | После M16 |
| **Workflow auto-generation** | Архитектурно опасно — LLM генерирует node graph? | Не строить (нарушает AD-22) |
| **Provider auto-discovery** | ComfyUI — единственный backend в v1 | Не строить (v2+) |
| **Distributed execution** | NG4 в PROJECT_SPEC | Не строить (v2+) |

### 4.2. Что НЕ нужно менять в M1–M12

| Компонент | Почему не менять |
|-----------|-----------------|
| Asset (types.py, store.py) | Фундамент lineage. Работает. |
| Job (job.py) | Minimal dataclass. Расширять, не переписывать. |
| Provider (comfyui.py) | Boundary. Работает для local/remote. |
| Registry (registry/) | Capability → Workflow → Selection. Работает. |
| ComfyClient (client.py) | HTTP transport. Работает. |
| Verifier (verifier.py) | Structural check. Расширять, не заменять. |
| WorkflowEngine (engine.py) | Core execution. Расширять (retry loop), не переписывать. |
| ComfyCLIAdapter | Optional infrastructure. Не трогать. |
| HeuristicPlanner | Fallback. Не удалять. |
| CompositePromptBuilder | Fallback orchestration. Не удалять. |

---

## 5. ROADMAP M13–M18

---

### M13: Execution History + Retry Loop

**Цель:** Система помнит что было сделано и может повторить при неудаче.

**Какую проблему решает:**
- Agent — single-shot executor. FAILED = конец. Нет retry.
- Нет памяти о предыдущих попытках.
- Нет mechanism для diagnostic ("почему упало?").

**Существующие модули (расширить):**
- `engine/job.py` — добавить attempt tracking
- `agent.py` — добавить retry loop в generate()
- `conversation.py` — добавить retry events в turn()

**Новые модули/контракты:**
- `engine/history.py` — ExecutionRecord dataclass + ExecutionHistory (in-memory, JSONL persist)
- `engine/retry.py` — RetryPolicy (max_attempts, backoff, decision logic)
- `engine/verifier.py` — расширить Verifier: `verify_with_diagnostics()` (structural + error classification)

**Зависимости:** Нет внешних. Только stdlib.

**Архитектурные риски:**
- Infinite retry loops → guard rails: max_attempts=3, timeout_per_attempt
- State complexity →保持 ExecutionHistory простым (append-only log)
- Не нарушить существующий execution path

**Что категорически нельзя менять:**
- Verifier.verify() — оставить как structural fallback
- WorkflowEngine.execute() — расширять обёрткой, не менять internals
- Asset/Job/Provider/Registry — без изменений

**Критерии Done:**
- [ ] ExecutionRecord dataclass с полным набором полей
- [ ] ExecutionHistory: record(), get_attempts(), get_by_capability()
- [ ] RetryPolicy: decide() → ACCEPT/RETRY/FAILED
- [ ] Agent.generate() с retry loop (max_attempts=3)
- [ ] ConversationAgent.turn() стримит retry events через SSE
- [ ] Verifier.verify_with_diagnostics() классифицирует ошибки

**Необходимые тесты:**
- test_execution_history: record + retrieval + persistence
- test_retry_policy: RETRY on failure, ACCEPT on success, max attempts
- test_retry_loop: full loop (execute → fail → retry → success)
- test_retry_events: SSE events for retry attempts
- test_diagnostics: error classification (transient vs permanent)

**E2E proof:**
- Запросить image.generate →故意指出错 workflow → VERIFICATION_FAILED → retry с тем же параметром → SUCCESS

**Почему именно здесь:**
M13 — фундамент для всех последующих milestone. Без ExecutionHistory:
- SemanticVerifier не может сравнить с прошлыми попытками
- AdaptivePlanner не может учиться
- User feedback не может быть привязан к конкретной попытке
- Multi-step decomposition не может обрабатывать ошибки

**Estimated:** 3–4 дня

---

### M14: Semantic Verification

**Цель:** Понимать что в output и соответствует ли оно запросу.

**Какую проблему решает:**
- Structural verification проверяет "файл существует + правильный тип".
- НЕ проверяет: "кот на картинке?" / "качество приемлемое?" / "соответствует запросу?"

**Существующие модули (расширить):**
- `engine/verifier.py` — добавить SemanticVerifier класс

**Новые модули/контракты:**
- `engine/semantic_verifier.py` — SemanticVerifier (vision model через OpenRouter)
- `engine/verification.py` — VerificationResult dataclass (score, matches_intent, issues, suggested_params)

**Зависимости:** OpenRouter API key (уже используется для LLMPlanner).

**Архитектурные риски:**
- Vision model может давать неточные оценки → fallback to structural
- Latency (vision API call) → опциональность
- Cost → single verification per attempt, не per token

**Что категорически нельзя менять:**
- Verifier.verify() — оставить как structural fallback
- WorkflowEngine.execute() — вызывать semantic verification после structural
- Agent.generate() — вызывать semantic verification до retry decision

**Критерии Done:**
- [ ] SemanticVerifier.verify(request, output_assets) → VerificationResult
- [ ] VerificationResult: score, matches_intent, issues, suggested_params
- [ ] Fallback: vision API недоступен → structural verification
- [ ] Интеграция с RetryPolicy: low score → RETRY
- [ ] Timeout: 10s per verification attempt

**Необходимые тесты:**
- test_semantic_verifier: mock vision API → verification results
- test_semantic_fallback: vision API down → structural verification
- test_verification_result: dataclass fields + serialization
- test_integration: semantic verification → retry decision

**E2E proof:**
- image.generate → output → SemanticVerifier → score=0.8 → ACCEPT
- image.generate → wrong output → SemanticVerifier → score=0.2 → RETRY

**Почему именно здесь:**
M14 depends on M13 (ExecutionHistory для хранения verification results). Semantic verification — основа для adaptive planning (M16) и user feedback (M17).

**Estimated:** 3–4 дня

---

### M15: Persistent Context + Session Recovery

**Цель:** Контекст сессии переживает restart; пользователь может вернуться к предыдущей задаче.

**Какую проблему решает:**
- ConversationContext = in-memory. При рестарте всё теряется.
- Нет cross-session history.
- Нет ability to resume interrupted tasks.

**Существующие модули (расширить):**
- `conversation.py` — ConversationContext получает save/load
- `agent.py` — Agent получает session management

**Новые модули/контракты:**
- `context/persistence.py` — ContextPersistence (JSONL-based, per-session files)
- `context/session_manager.py` — SessionManager (create, list, resume, archive)

**Зависимости:** M13 (ExecutionHistory) для persist execution records.

**Архитектурные риски:**
- Data size growth → per-session files, not monolithic DB
- Privacy → session isolation (уже есть, расширить на persistence)
- Migration → append-only, не migrate existing sessions

**Что категорически нельзя менять:**
- ConversationContext dataclass — расширять, не переписывать
- Session isolation — не нарушать
- Asset lineage — не менять

**Критерии Done:**
- [ ] ContextPersistence.save(session_id, context) → file
- [ ] ContextPersistence.load(session_id) → context | None
- [ ] ContextPersistence.list_sessions() → list of session metadata
- [ ] SessionManager.create() → session_id
- [ ] SessionManager.resume(session_id) → context with restored state
- [ ] SessionManager.archive(session_id) → move to archive
- [ ] UI endpoint: GET /api/sessions → list of sessions
- [ ] UI endpoint: POST /api/sessions/{id}/resume → restore session

**Необходимые тесты:**
- test_context_persistence: save → load → verify all fields
- test_session_recovery: restart → resume → active_asset preserved
- test_session_listing: multiple sessions → list returns all
- test_session_archiving: archive → not in active list
- test_isolation: session A changes don't affect session B

**E2E proof:**
- Create session → generate image → restart → resume session → active_asset preserved → continue editing

**Почему именно здесь:**
M15 depends on M13 (ExecutionHistory). Persistent context — основа для M16 (adaptive planning) и M17 (user feedback). Без persistent context, learning невозможен.

**Estimated:** 4–5 дней

---

### M16: Adaptive Planner + Learning from History

**Цель:** Планировщик учится на предыдущих результатах и улучшает параметры.

**Какую проблему решает:**
- HeuristicPlanner = keyword matching. Не учитывает "что работало раньше".
- LLMPlanner = generic. Не знает предпочтения пользователя.
- Нет mechanism для "этот стиль работает лучше для этого пользователя".

**Существующие модули (расширить):**
- `planner.py` — добавить AdaptivePlanner класс
- `engine/history.py` — добавить analytics methods

**Новые модули/контракты:**
- `planner/adaptive.py` — AdaptivePlanner (uses ExecutionHistory)
- `planner/preferences.py` — UserPreferences (aggregated from history)
- `engine/analytics.py` — HistoryAnalytics (success rate, average score, preferred params)

**Зависимости:** M13 (ExecutionHistory) + M14 (SemanticVerifier scores) + M15 (Persistent context).

**Архитектурные риски:**
- Overfitting → min attempts threshold (≥3 before adapting)
- Cold start → HeuristicPlanner fallback when history insufficient
- Bias → respect user explicit overrides over learned preferences

**Что категорически нельзя менять:**
- HeuristicPlanner — оставить как fallback
- LLMPlanner — оставить как optional enhancement
- Planner protocol — расширять, не заменять

**Критерии Done:**
- [ ] AdaptivePlanner.plan(request, context) → PlanResult (uses history)
- [ ] UserPreferences: aggregate(history) → preferred styles, params, workflows
- [ ] HistoryAnalytics: success_rate(), avg_score(), preferred_params()
- [ ] Fallback: insufficient history → HeuristicPlanner
- [ ] Override: user explicit params > learned preferences
- [ ] Integration: Agent.generate() uses AdaptivePlanner when history available

**Необходимые тесты:**
- test_adaptive_planner: history → preference → adjusted params
- test_cold_start: no history → heuristic fallback
- test_override: explicit user params > learned
- test_analytics: success_rate, avg_score calculation
- test_insufficient_data: <3 attempts → no adaptation

**E2E proof:**
- 3 attempts с разными params → AdaptivePlanner рекомендует лучшие params → 4th attempt использует recommended → success rate improves

**Почему именно здесь:**
M16 depends on M13+M14+M15. Adaptive planning — следующий уровень интеллекта. Без M13 (history), M14 (scores), M15 (persistence) — learning невозможен.

**Estimated:** 5–7 дней

---

### M17: User Feedback Loop + Human-in-the-Loop

**Цель:** Пользователь оценивает результат и влияет на следующие генерации.

**Какую проблему решает:**
- Agent генерирует, пользователь видит результат, и... нет обратной связи.
- Нет ability say "не нравится" / "слишком темно" / "попробуй другой стиль".
- Agent не знает что пользователю нравится.

**Существующие модули (расширить):**
- `ui.py` — добавить feedback endpoints
- `conversation.py` — добавить feedback storage
- `engine/history.py` — привязать feedback к attempts

**Новые модули/контракты:**
- `context/feedback.py` — FeedbackStore (per-attempt ratings, comments)
- `ui.py` — POST /api/feedback, GET /api/feedback/history
- Confirmation dialog: "Это то, что вы хотели? [Да/Нет/Изменить]"

**Зависимости:** M13 (ExecutionHistory) + M15 (Persistent context).

**Архитектурные риски:**
- Feedback quality → encourage specific, not just thumbs up/down
- Storage size → per-session, not global
- Privacy → user controls own feedback

**Что категорически нельзя менять:**
- Agent.generate() — feedback влияет на AdaptivePlanner, не на execution
- WorkflowEngine — без изменений
- Verifier — без изменений

**Критерии Done:**
- [ ] FeedbackStore.record(attempt_id, rating, comment)
- [ ] FeedbackStore.get_for_session(session_id) → list
- [ ] UI: POST /api/feedback {attempt_id, rating, comment}
- [ ] UI: GET /api/feedback/history → session feedback
- [ ] Confirmation dialog after generation: "Вам понравился результат?"
- [ ] Feedback привязан к ExecutionRecord (attempt_id)
- [ ] AdaptivePlanner учитывает feedback (M16 integration)

**Необходимые тесты:**
- test_feedback_store: record + retrieval
- test_feedback_ui: POST/GET endpoints
- test_feedback_integration: feedback → history → adaptive planner
- test_confirmation_dialog: UI shows after generation
- test_privacy: session isolation for feedback

**E2E proof:**
- Generate → "Вам понравилось?" → "Нет, слишком темно" → AdaptivePlanner регулирует brightness → next attempt lighter

**Почему именно здесь:**
M17 depends on M13 (history) + M15 (persistence) + M16 (adaptive planner). Feedback loop замыкает circle: user → Agent → result → user feedback → Agent learns.

**Estimated:** 3–4 дня

---

### M18: Multi-Step Task Decomposition + Workflow Chaining

**Цель:** Agent выполняет сложные задачи из нескольких capability автоматически.

**Какую проблему решает:**
- "Сгенерируй кота и увеличь разрешение" = 2 отдельных запроса.
- Нет ability decompose complex requests.
- Нет chaining: image.generate → image.upscale → result.

**Существующие модули (расширить):**
- `planner.py` — добавить decomposition logic
- `conversation.py` — добавить multi-step chain tracking
- `engine/engine.py` — добавить batch execution

**Новые модули/контракты:**
- `planner/decomposer.py` — TaskDecomposer (request → list of subtasks)
- `engine/chain.py` — ExecutionChain (subtask1 → subtask2 → ... → result)
- `conversation.py` — chain tracking (active_chain, current_step)

**Зависимости:** M13 (retry loop для error handling) + M14 (semantic verification per step) + M16 (adaptive planning per step).

**Архитектурные риски:**
- Error propagation: ошибка в шаге 1 крашит весь chain → need per-step retry
- Complexity explosion: 2+ steps = exponential state space
- State management: каждый шаг может менять active_asset
- User control: ability to cancel chain mid-execution

**Что категорически нельзя менять:**
- Single-step execution path — оставить как primary
- Agent.generate() — оставить как single-step entry point
- ConversationAgent.turn() — расширять, не заменять

**Критерии Done:**
- [ ] TaskDecomposer.decompose(request) → list of (capability, params)
- [ ] ExecutionChain.execute(subtasks) → list of Jobs
- [ ] Per-step retry (M13) + semantic verification (M14)
- [ ] Chain state tracking (active_chain, current_step, completed_steps)
- [ ] UI: chain progress display
- [ ] Cancel: ability to cancel chain mid-execution
- [ ] Fallback: decomposition failure → single-step execution

**Необходимые тесты:**
- test_decomposer: "generate + upscale" → 2 subtasks
- test_chain_execution: 2 subtasks → sequential execution
- test_chain_error_handling: step 2 fails → retry step 2
- test_chain_cancel: cancel mid-chain → partial results preserved
- test_chain_state: active_chain tracking in conversation

**E2E proof:**
- "Сгенерируй кота 512x512 и увеличь до 1024x1024" → image.generate → image.upscale → final asset

**Почему именно здесь:**
M18 depends on M13+M14+M16. Multi-step — финальный уровень сложности. Без retry loop (M13), semantic verification (M14), adaptive planning (M16) — chain execution ненадёжен.

**Estimated:** 7–10 дней

---

## 6. Сводная таблица

| Milestone | Цель | Зависимости | Сложность | Статус |
|-----------|------|-------------|-----------|--------|
| **M13** | Execution History + Retry Loop | Нет | Средняя | IMPLEMENTED — UNIT/INTEGRATION VERIFIED — REAL E2E VERIFIED |
| **M14** | Semantic Verification | M13 | Средняя | IMPLEMENTED — UNIT/INTEGRATION VERIFIED — REAL E2E VERIFIED |
| **M15** | Persistent Context | M13 | Средняя-высокая | IMPLEMENTED — UNIT/INTEGRATION VERIFIED — REAL E2E VERIFIED |
| **M16** | Adaptive Planner | M13+M14+M15 | Высокая | IMPLEMENTED — UNIT/INTEGRATION VERIFIED — REAL E2E VERIFIED |
| **M17** | User Feedback Loop | M13+M15+M16 | Средняя | IMPLEMENTED — UNIT/INTEGRATION VERIFIED — REAL E2E VERIFIED |
| **M18** | Multi-Step Decomposition | M13+M14+M16 | Высокая | IMPLEMENTED — UNIT/INTEGRATION VERIFIED — REAL E2E VERIFIED |

### Порядок зависимостей

```
M13 (History + Retry)
 ├── M14 (Semantic Verification)
 │    └── M16 (Adaptive Planner)
 ├── M15 (Persistent Context)
 │    ├── M16 (Adaptive Planner)
 │    └── M17 (User Feedback)
 └── M18 (Multi-Step Decomposition)
```

### Critical path

```
M13 → M14 → M16 → M18
M13 → M15 → M17
```

**M13 — единственный milestone без зависимостей. Он является критическим путём.**

---

## 7. Рекомендация

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

## 8. Финальный статус

| Документ | Статус |
|----------|--------|
| `docs/FUTURE_ROADMAP_ARCHITECTURE.md` | **DRAFT FOR DISCUSSION** |
| M13–M18 | **IMPLEMENTED — UNIT/INTEGRATION VERIFIED — REAL E2E VERIFIED** |
| M13: Execution History + Retry Loop | **RECOMMENDED AS NEXT MILESTONE** |

**Следующий шаг:** Автор проекта принимает решение по M13 или предлагает альтернативное направление.
