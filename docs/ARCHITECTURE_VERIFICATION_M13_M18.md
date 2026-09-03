# ARCHITECTURE VERIFICATION M13–M18

**Статус:** READ-ONLY AUDIT
**Дата:** 2026-09-01
**Аудитор:** AI Engineer (opencode)
**Цель:** Подтвердить фактическое состояние M13–M18 как интегрированной системы

---

## Executive Summary

M13–M18 реализованы как **модульные компоненты с unit-тестами**. Интеграция между компонентами **существует в коде** (agent.py, conversation.py, ui.py), но **не подтверждена интеграционными тестами** или реальным E2E с ComfyUI. Все 239 тестов проходят, но 113 из них (M13-M18) тестируют компоненты изолированно или с mocks.

---

## 1. Фактическое состояние кода

### 1.1. Source Files (все существуют)

| Компонент | Файл | Строк | Статус |
|-----------|------|-------|--------|
| M13 | `app/engine/history.py` | 165 | ✅ Существует |
| M13 | `app/engine/retry.py` | 152 | ✅ Существует |
| M14 | `app/engine/semantic_verifier.py` | 252 | ✅ Существует |
| M15 | `app/context/persistence.py` | 87 | ✅ Существует |
| M15 | `app/context/session_manager.py` | 71 | ✅ Существует |
| M16 | `app/engine/analytics.py` | 141 | ✅ Существует |
| M16 | `app/planner/preferences.py` | 74 | ✅ Существует |
| M16 | `app/planner/adaptive.py` | 65 | ✅ Существует |
| M17 | `app/context/feedback.py` | 95 | ✅ Существует |
| M18 | `app/planner/decomposer.py` | 145 | ✅ Существует |
| M18 | `app/engine/chain.py` | 179 | ✅ Существует |

### 1.2. Test Files (все существуют)

| Компонент | Файл | Тестов | Статус |
|-----------|------|--------|--------|
| M13 | `tests/test_m13_history_retry.py` | 32 | ✅ Все проходят |
| M14 | `tests/test_m14_semantic_verification.py` | 23 | ✅ Все проходят |
| M15 | `tests/test_m15_persistent_context.py` | 14 | ✅ Все проходят |
| M16 | `tests/test_m16_adaptive_planner.py` | 16 | ✅ Все проходят |
| M17 | `tests/test_m17_user_feedback.py` | 11 | ✅ Все проходят |
| M18 | `tests/test_m18_multi_step.py` | 17 | ✅ Все проходят |

---

## 2. Интеграция:事实 vs claims

### 2.1. Интеграционные точки в коде (подтверждено)

| Интеграция | Файл:Строка | Код | Статус |
|------------|-------------|-----|--------|
| Agent → History.record() | `agent.py:310` | `self.execution_history.record(record)` | ✅ Wired |
| Agent → RetryPolicy.decide() | `agent.py:314-318` | `decision = self.retry_policy.decide(...)` | ✅ Wired |
| Agent → SemanticVerifier.verify() | `agent.py:291-295` | `semantic_result = self.semantic_verifier.verify(...)` | ✅ Wired |
| Agent → classify_error() | `agent.py:269` | `error_class=classify_error(str(e))` | ✅ Wired |
| ConversationAgent → SessionManager.resume() | `conversation.py:106` | `ctx = self.session_manager.resume(session_id)` | ✅ Wired |
| ConversationAgent → SessionManager.save() | `conversation.py:368-369` | `self.session_manager.save(session_id, ctx)` | ✅ Wired |
| ConversationAgent → SemanticVerifier | `conversation.py:277-281` | `self.semantic_verifier.verify(...)` | ✅ Wired |
| UI → FeedbackStore | `ui.py:499` | `factory.record_feedback(...)` | ✅ Wired |
| UI → GET /api/feedback/history | `ui.py:373-375` | `factory.get_feedback_history(sid)` | ✅ Wired |

### 2.2. Что НЕ интегрировано

| Компонент | Статус | Проблема |
|-----------|--------|----------|
| AdaptivePlanner → Agent.generate() | ❌ NOT WIRED | Agent использует `self.planner or HeuristicPlanner()`. AdaptivePlanner не передаётся. |
| TaskDecomposer → Agent/ConversationAgent | ❌ NOT WIRED | Decomposer существует, но нигде не вызывается из execution path. |
| ExecutionChain → Agent/ConversationAgent | ❌ NOT WIRED | Chain существует, но нигде не используется для multi-step. |
| FeedbackStore → AdaptivePlanner | ❌ NOT WIRED | Feedback не влияет на планирование. |
| Feedback → History/Analytics | ❌ NOT WIRED | Feedback не привязан к ExecutionRecord. |

---

## 3. Execution Flow:事实 vs documentation

### 3.1. Заявленный flow (из docs)

```
ConversationAgent → Planner → WorkflowEngine → History → Retry → SemanticVerifier → Persistence → Adaptive → Feedback → Decomposer → Chain
```

### 3.2. Фактический flow (из кода)

```
UI /turn POST
  → ConversationAgent.turn()
    → self.session(session_id)           [M15: session_manager.resume() — WIRED]
    → self.prepare()                     [workflow selection]
    → self.engine.execute()              [ComfyUI execution]
    → self.semantic_verifier.verify()    [M14: WIRED]
    → self.execution_history.record()    [M13: WIRED]
    → self.retry_policy.decide()         [M13: WIRED]
    → self.session_manager.save()        [M15: WIRED]
```

**Что НЕ в flow:**
- AdaptivePlanner (не используется)
- TaskDecomposer (не используется)
- ExecutionChain (не используется)
- Feedback (не влияет на планирование)

---

## 4. Тесты: unit vs integration

### 4.1. M13 (History + Retry)

| Тест | Тип | Mock? | Реальный runtime? |
|------|-----|-------|-------------------|
| ExecutionRecord dataclass | Unit | No | Yes (stdlib) |
| ExecutionHistory.record() | Unit | No | Yes (file I/O) |
| ExecutionHistory.load() | Unit | No | Yes (file I/O) |
| RetryPolicy.decide() | Unit | No | Yes (pure logic) |
| classify_error() | Unit | No | Yes (pure function) |
| **Integration: Agent → History → Retry** | **NOT TESTED** | — | — |

### 4.2. M14 (Semantic Verification)

| Тест | Тип | Mock? | Реальный runtime? |
|------|-----|-------|-------------------|
| SemanticVerificationResult | Unit | No | Yes (stdlib) |
| SemanticVerifier MIME/prompt/parse | Unit | No | Yes (stdlib) |
| SemanticVerifier.verify() | Integration | **Yes (mocked API)** | No real API call |
| **Integration: Agent → SemanticVerifier** | **NOT TESTED** | — | — |
| **Integration: SemanticVerifier → Retry** | **NOT TESTED** | — | — |

### 4.3. M15 (Persistent Context)

| Тест | Тип | Mock? | Реальный runtime? |
|------|-----|-------|-------------------|
| ContextPersistence save/load | Unit | No | Yes (file I/O) |
| SessionManager create/resume | Unit | No | Yes (file I/O) |
| Session isolation | Unit | No | Yes (file I/O) |
| **Integration: ConversationAgent → SessionManager** | **NOT TESTED** | — | — |
| **Persistence after restart** | **NOT TESTED** | — | — |

### 4.4. M16 (Adaptive Planner)

| Тест | Тип | Mock? | Реальный runtime? |
|------|-----|-------|-------------------|
| HistoryAnalytics methods | Unit | No | Yes (in-memory) |
| UserPreferences methods | Unit | No | Yes (in-memory) |
| AdaptivePlanner.plan() | Integration | No (real history) | Yes (but no ComfyUI) |
| **Integration: Agent → AdaptivePlanner** | **NOT TESTED** | — | — |
| **Integration: History → Adaptive → Params** | **Partial** | No | Yes (in-memory) |

### 4.5. M17 (User Feedback)

| Тест | Тип | Mock? | Реальный runtime? |
|------|-----|-------|-------------------|
| FeedbackRecord dataclass | Unit | No | Yes (stdlib) |
| FeedbackStore record/get | Unit | No | Yes (file I/O) |
| **Integration: UI → FeedbackStore** | **NOT TESTED** | — | — |
| **Integration: Feedback → AdaptivePlanner** | **NOT TESTED** | — | — |

### 4.6. M18 (Multi-Step)

| Тест | Тип | Mock? | Реальный runtime? |
|------|-----|-------|-------------------|
| TaskDecomposer.decompose() | Unit | No | Yes (pure logic) |
| ExecutionChain.execute() | Integration | **Yes (mocked execute_fn)** | No ComfyUI |
| Chain cancel/retry | Integration | **Yes (mocked)** | No ComfyUI |
| **Integration: Agent → Chain** | **NOT TESTED** | — | — |
| **E2E: Chain on ComfyUI** | **NOT TESTED** | — | — |

---

## 5. Runtime readiness

### 5.1. External Dependencies

| Компонент | Зависимость | Required? | Fallback |
|-----------|-------------|-----------|----------|
| ExecutionHistory | None (stdlib) | N/A | N/A |
| RetryPolicy | None (stdlib) | N/A | N/A |
| SemanticVerifier | OPENROUTER_API_KEY | Optional | score=0.5 neutral |
| ContextPersistence | Filesystem | Required | N/A (crash on init) |
| SessionManager | ContextPersistence | Required | N/A |
| FeedbackStore | Filesystem | Required | N/A (crash on init) |
| AdaptivePlanner | ExecutionHistory | Required | HeuristicPlanner fallback |
| TaskDecomposer | None (stdlib) | N/A | N/A |
| ExecutionChain | ExecutionHistory | Required | Creates own |

### 5.2. Runtime Risks

| Риск | Описание | Mitigation |
|------|----------|------------|
| SemanticVerifier uses `urllib.request.urlopen` | May conflict with Hiddify proxy | External API (not localhost), should be fine |
| ContextPersistence/FeedbackStore filesystem | May fail on read-only filesystem | Will crash on init, no graceful degradation |
| AdaptivePlanner cold start | Needs ≥3 history records | Falls back to HeuristicPlanner |
| ExecutionChain not wired | Cannot be used from Agent/ConversationAgent | Scaffolding only |

---

## 6. Architectural Invariants: проверка

| Инвариант | Статус | Доказательство |
|-----------|--------|----------------|
| MEDIA_AGNOSTIC (нет if image/elif video) | ✅ VERIFIED | Все M13-M18 модули media-agnostic |
| SESSION_ISOLATION | ✅ VERIFIED | SessionManager, FeedbackStore per-session files |
| ASSET_LINEAGE | ✅ NOT AFFECTED | M13-M18 не модифицируют Asset |
| NG1 (no multi-agent) | ✅ NOT VIOLATED | Нет multi-agent в M13-M18 |
| NG2 (no RAG) | ✅ NOT VIOLATED | Нет RAG в M13-M18 |
| NG3 (no autonomous learning) | ✅ NOT VIOLATED | AdaptivePlanner = aggregate statistics only |
| HeuristicPlanner preserved as fallback | ✅ VERIFIED | AdaptivePlanner falls back to HeuristicPlanner |
| ComfyUI boundary | ✅ NOT VIOLATED | M13-M18 не ходят в ComfyUI напрямую |

---

## 7. E2E Results

### 7.1. Что протестировано с реальным ComfyUI

| Тест | ComfyUI? | Результат |
|------|----------|-----------|
| M1-M12 regression (126 tests) | No (mocked) | ✅ Pass |
| M13-M18 (113 tests) | No (mocked/unit) | ✅ Pass |
| **E2E: Retry после failure** | **NOT TESTED** | — |
| **E2E: Semantic verification** | **NOT TESTED** | — |
| **E2E: Persistence после restart** | **NOT TESTED** | — |
| **E2E: Multi-step chain** | **NOT TESTED** | — |

### 7.2. Что требует реального ComfyUI для验证

1. **Retry loop**: Запуск с intentionally failing workflow → retry → success
2. **Semantic verification**: Генерация изображения → vision API → score
3. **Persistence**: Restart процесса → resume session → active_asset preserved
4. **Multi-step chain**: "сгенерируй кота и увеличь" → 2 workflow executions

---

## 8. Gaps между кодом и документацией

| GAP | Описание | Severity |
|-----|----------|----------|
| AdaptivePlanner not wired | Документация утверждает "adaptive planning added", но Agent его не использует | HIGH |
| TaskDecomposer not wired | Документация утверждает "multi-step decomposition added", но нигде не вызывается | HIGH |
| ExecutionChain not wired | Chain существует, но не используется из Agent/ConversationAgent | HIGH |
| Feedback → Adaptive not connected | Feedback не влияет на планирование | MEDIUM |
| No integration tests | Все тесты M13-M18 are unit/isolated | HIGH |
| No E2E with ComfyUI | Нет подтверждения работы с реальным ComfyUI | HIGH |
| Persistence restart not tested | Нет теста "restart → resume" | MEDIUM |

---

## 9. Technical Debt

| Debt | Описание | Priority |
|------|----------|----------|
| TD-1 | AdaptivePlanner not integrated into Agent.generate() | HIGH |
| TD-2 | TaskDecomposer not integrated into execution path | HIGH |
| TD-3 | ExecutionChain not integrated into Agent/ConversationAgent | HIGH |
| TD-4 | Feedback not connected to AdaptivePlanner | MEDIUM |
| TD-5 | No integration tests for M13-M18 | HIGH |
| TD-6 | No E2E tests with ComfyUI for M13-M18 | HIGH |
| TD-7 | Persistence crash on read-only filesystem | LOW |
| TD-8 | SemanticVerifier uses urllib (Hiddify risk) | LOW |

---

## 10. Risks

| Риск | Вероятность | Impact | Mitigation |
|------|-------------|--------|------------|
| AdaptivePlanner never used | High | Medium | Wire into Agent.generate() |
| Multi-step never works | High | High | Wire TaskDecomposer + ExecutionChain |
| Feedback loop never closes | Medium | Medium | Wire Feedback → AdaptivePlanner |
| Persistence fails in production | Low | High | Add try/except, graceful degradation |
| Semantic verification blocks execution | Low | Medium | Timeout + fallback to score=0.5 |

---

## 11. Что realmente готово

| Компонент | Готов? | Доказательство |
|-----------|--------|----------------|
| ExecutionHistory (record, load, query) | ✅ YES | Unit tests + file I/O verified |
| RetryPolicy (decide, backoff) | ✅ YES | Unit tests verified |
| classify_error() | ✅ YES | Unit tests verified |
| SemanticVerifier (parse, MIME, prompt) | ✅ YES | Unit tests verified |
| ContextPersistence (save, load) | ✅ YES | Unit tests + file I/O verified |
| SessionManager (create, resume) | ✅ YES | Unit tests verified |
| HistoryAnalytics | ✅ YES | Unit tests verified |
| UserPreferences | ✅ YES | Unit tests verified |
| AdaptivePlanner (standalone) | ✅ YES | Integration test with real history |
| FeedbackStore (record, get) | ✅ YES | Unit tests + file I/O verified |
| TaskDecomposer (decompose) | ✅ YES | Unit tests verified |
| ExecutionChain (execute, cancel) | ✅ YES | Integration test with mocked fn |

---

## 12. Что является scaffolding/mock

| Компонент | Статус | Реальность |
|-----------|--------|------------|
| AdaptivePlanner integration | SCAFFOLDING | Существует, но не подключён к execution path |
| TaskDecomposer integration | SCAFFOLDING | Существует, но не подключён к execution path |
| ExecutionChain integration | SCAFFOLDING | Существует, но не подключён к execution path |
| Feedback → Adaptive | SCAFFOLDING | Существует, но не соединены |
| Semantic verification with real API | MOCKED | Все тесты с mock vision API |
| Retry on real failure | MOCKED | Нет E2E с реальным ComfyUI failure |
| Persistence after restart | MOCKED | Нет теста restart → resume |

---

## 13. Рекомендации

### 13.1. Immediate (до объявления M13-M18 завершёнными)

1. **Wire AdaptivePlanner** в Agent.generate() — заменить `self.planner or HeuristicPlanner()` на `AdaptivePlanner(history=self.execution_history)` когда история доступна
2. **Wire TaskDecomposer + ExecutionChain** в ConversationAgent.turn() — добавить проверку "is multi-step?" и chain execution
3. **Add integration tests** — тесты которые vérifie что Agent.generate() 실제로 вызывает history.record() и retry_policy.decide()
4. **Add E2E test** — реальный ComfyUI + retry после failure

### 13.2. Short-term (M19+)

1. **Feedback → AdaptivePlanner** — использовать feedback для weighted analytics
2. **Persistence restart test** — тест "save → restart → resume → verify state"
3. **UI chain progress** — SSE events для multi-step chain
4. **LLM-based decomposer** — заменить keyword-based на LLM decomposition

### 13.3. Long-term

1. **Real E2E suite** — все M13-M18 компоненты с реальным ComfyUI
2. **Performance benchmarks** — retry latency, semantic verification overhead
3. **Production hardening** — error handling, logging, monitoring

---

## 14. Final Status

| Milestone | Статус | Вердикт |
|-----------|--------|---------|
| **M13** | PARTIALLY VERIFIED | Код exists, unit tests pass, интеграция wired, но нет E2E |
| **M14** | MOCK/UNIT ONLY | Код exists, unit tests pass, все тесты с mock API |
| **M15** | PARTIALLY VERIFIED | Код exists, unit tests pass, интеграция wired, но нет restart test |
| **M16** | NOT INTEGRATED | Код exists, unit tests pass, но AdaptivePlanner не подключён к Agent |
| **M17** | NOT INTEGRATED | Код exists, unit tests pass, но Feedback не влияет на планирование |
| **M18** | NOT INTEGRATED | Код exists, unit tests pass, но Decomposer/Chain не подключены |

**Общий вердикт:** M13–M18 реализованы как **набор модулей**, но **НЕ как интегрированная система**. Интеграционные точки существуют в коде, но не подтверждены тестами или E2E.

---

## 15. Regression Test Results

| Suite | Tests | Passed | Skipped | Failed |
|-------|-------|--------|---------|--------|
| M1-M12 regression | 129 | 126 | 3 | 0 |
| M13-M18 | 113 | 113 | 0 | 0 |
| **Total** | **242** | **239** | **3** | **0** |

**Примечание:** Все тесты проходят, но это unit/isolated тесты. Интеграционные тесты отсутствуют.

---

**Документ является READ-ONLY audit. Production code не изменялся.**
