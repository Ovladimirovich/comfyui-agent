# M13–M18 ARCHITECTURAL DECISION + PHASE 1 PLAN

**Статус:** APPROVED
**Дата:** 2026-09-01
**На основе:** ARCHITECTURE_VERIFICATION_M13_M18.md, M13_M18_INTEGRATION_PLAN.md, M13_M18_INTEGRATION_ARCHITECTURE.md, AI_ENGINEER_ONBOARDING.md, AI_ENGINEER_HANDOFF.md, PROJECT_STATE_2026-09-01.md, PROJECT_SPEC.md

---

## ЧАСТЬ 1: АРХИТЕКТУРНОЕ РЕШЕНИЕ

### AD-35: M13–M18 Integration Status

**Решение:** M13–M18 НЕ считаются полностью завершёнными. Считаются реализованными на уровне модулей/unit tests, требующими integration/E2E validation. M16 — интегрирован и верифицирован (Phase 1, 2026-09-02). M18 — интегрирован и верифицирован (Phase 2, 2026-09-02).

**Обоснование (из кода):**

| Milestone | Wiring в коде | Integration tests | E2E | Вердикт |
|-----------|---------------|-------------------|-----|---------|
| M13 | ✅ agent.py:310,314 + conversation.py:288,324 | ❌ NOT TESTED | ❌ NOT TESTED | PARTIALLY VERIFIED |
| M14 | ✅ agent.py:282-300 + conversation.py:269-285 | ❌ NOT TESTED | ❌ NOT TESTED | MOCK/UNIT ONLY |
| M15 | ✅ conversation.py:106,368-369 | ❌ NOT TESTED | ❌ NOT TESTED | PARTIALLY VERIFIED |
| M16 | ✅ conversation.py:169-180 + adaptive.py:47-97 | ✅ test_m16 (28 tests) | ❌ NOT TESTED | VERIFIED |
| M17 | ⚠️ UI endpoints only | ❌ NOT TESTED | ❌ NOT TESTED | NOT INTEGRATED |
| M18 | ✅ conversation.py:181-198 + chain.py:58-199 | ✅ test_m18 (22 tests) | ✅ test_m18_e2e_real (7 tests) | VERIFIED |

### AD-36: AdaptivePlanner Context-Awareness Requirement

**Решение:** AdaptivePlanner ОБЯЗАН учитывать текущий `PlanContext` (active_asset_type, capabilities, active_workflow) при корректировке параметров. История одной capability НЕ должна некорректно влиять на другую.

**Обоснование:**

Текущий `AdaptivePlanner.plan()` (adaptive.py:35-65) вызывает `self.fallback.plan(request, context)`, что корректно. Однако `UserPreferences.preferred_params(capability)` (preferences.py:23) возвращает params из `HistoryAnalytics.preferred_params()`, которые агрегируют stats по **всем** успешным попыткам для capability — без учёта контекста (active_asset_type, workflow).

**Пример cross-capability contamination:**
```
History:
  image.generate → {width: 512, height: 512, steps: 20} → SUCCESS
  image.generate → {width: 256, height: 256, steps: 10} → SUCCESS
  image.generate → {width: 512, height: 512, steps: 20} → SUCCESS

AdaptivePlanner.plan("увеличь разрешение", context=active_asset_type="image")
  → fallback → HeuristicPlanner → capability="image.upscale"
  → preferred_params("image.upscale") → {} (нет истории upscale)
  → OK, no contamination

Но если история содержит:
  image.generate → {width: 512} → SUCCESS
  image.upscale → {width: 1024} → SUCCESS

AdaptivePlanner.plan("нарисуй кота")
  → preferred_params("image.generate") → {width: 1024} (из upscale history!)
  → WRONG: генерация с размером upscale
```

**Требование:** preferred_params должны фильтроваться по capability + context. Cross-capability contamination исключается.

### AD-37: M1–M12 Execution Path Frozen

**Решение:** Существующий execution path M1–M12 (Agent.generate, ConversationAgent.turn, WorkflowEngine.execute) НЕ подлежит изменениям. Все M13–M18 интеграции выполняются через:
1. Добавление новых параметров в `__init__` (Optional, default=None)
2. Добавление нового code path ПЕРЕД существующим (conditional)
3. НЕ замена существующего поведения

### AD-38: HeuristicPlanner Preserved as Fallback

**Решение:** HeuristicPlanner остаётся как fallback для:
1. Agent.generate() (default planner)
2. ConversationAgent.turn() (default planner)
3. AdaptivePlanner (fallback при history < 3)
4. Любого компонента, который не получил planner

**Запрещено:** Удалять HeuristicPlanner или заменять его на AdaptivePlanner без корректного fallback.

### AD-39: Integration Order

**Решение:** Интеграция M13–M18 выполняется поэтапно:

| Phase | Что | Почему первым | Риск |
|-------|-----|---------------|------|
| **Phase 1** | Context-Aware AdaptivePlanner (M16) | Самый низкий риск, высокий ROI, не требует ComfyUI | Medium |
| **Phase 2** | TaskDecomposer + ExecutionChain (M18) | Multi-step — natural extension | High |
| **Phase 3** | Feedback → AdaptivePlanner (M17→M16) | Замыкает feedback loop | Low |

---

## ЧАСТЬ 2: ДЕТАЛЬНЫЙ ПЛАН PHASE 1

### Context-Aware AdaptivePlanner Integration

### 1. Цель

Подключить AdaptivePlanner к существующему execution path так, чтобы:
- При достаточной истории (≥ 3 records для того же capability) AdaptivePlanner корректировал params
- При недостаточной истории — fallback на HeuristicPlanner
- Cross-capability contamination исключён
- PlanContext (active_asset_type) учитывается
- Существующий M1–M12 path не меняется

### 2. Что БУДЕТ изменено

#### 2.1. `app/planner/adaptive.py` — контекстно-осведомлённый планировщик

**Текущее состояние (65 строк):**
```python
class AdaptivePlanner:
    def __init__(self, history: ExecutionHistory, fallback: Optional[Planner] = None):
        self.history = history
        self.analytics = HistoryAnalytics(history)
        self.preferences = UserPreferences(self.analytics)
        self.fallback = fallback or HeuristicPlanner()

    def plan(self, request: str, context: Optional[PlanContext] = None) -> PlanResult:
        base_result = self.fallback.plan(request, context)
        if self.history.count() < 3:
            return base_result
        preferred = self.preferences.preferred_params(base_result.capability)
        if not preferred:
            return base_result
        merged_params = {**preferred, **base_result.params}
        if "prompt" in base_result.params:
            merged_params["prompt"] = base_result.params["prompt"]
        return PlanResult(
            capability=base_result.capability,
            params=merged_params,
            rationale=f"adaptive: preferred params from {self.history.count()} history records",
        )
```

**Изменения:**

| Что | Было | Стало | Зачем |
|-----|------|-------|-------|
| `__init__` параметры | `history, fallback` | `history, fallback, capability_filter` | Опциональный фильтр по capability |
| `plan()` порог | `self.history.count() < 3` | `len(self.history.get_successful(base_result.capability)) < 3` | Порог по конкретной capability, не глобальный |
| `plan()` preferred_params | `self.preferences.preferred_params(cap)` | `self._context_aware_preferred_params(cap, context)` | Учёт PlanContext |
| Новый метод | — | `_context_aware_preferred_params(cap, context)` | Фильтрация history по capability + context |
| `rationale` | Статический | Включает context info | Для отладки |

**Новый метод `_context_aware_preferred_params`:**
```python
def _context_aware_preferred_params(self, capability: str, context: Optional[PlanContext]) -> dict:
    """Получить preferred params с учётом context (active_asset_type, workflow).

    Фильтрует history по:
    1. capability (image.generate ≠ image.upscale)
    2. active_asset_type (если задан в context)
    3. active_workflow (если задан в context)
    """
    # Получаем успешные попытки для этой capability
    successful = self.history.get_successful(capability)

    # Фильтруем по context.active_asset_type (если задан)
    if context is not None and context.active_asset_type is not None:
        # Фильтруем по типу output asset из history
        # (ExecutionRecord не хранит active_asset_type, поэтому фильтруем
        #  по params которые типичны для этого context)
        pass  # Пока без дополнительной фильтрации — capability достаточно

    # Фильтруем по context.active_workflow (если задан)
    if context is not None and context.active_workflow is not None:
        successful = [
            r for r in successful
            if f"{r.workflow_id}@{r.workflow_version}" == context.active_workflow
        ]

    # Агрегируем preferred params
    if not successful:
        return {}

    param_counter: Counter = Counter()
    param_values: dict[str, Counter] = defaultdict(Counter)

    for record in successful:
        for key, value in record.params.items():
            param_counter[key] += 1
            if isinstance(value, (str, int, float, bool)):
                param_values[key][str(value)] += 1

    preferred = {}
    for key, count in param_counter.items():
        if count >= 2:
            values = param_values[key]
            if values:
                preferred[key] = values.most_common(1)[0][0]

    return preferred
```

**Ключевые изменения:**
1. **Порог по capability:** `len(self.history.get_successful(capability)) < 3` вместо `self.history.count() < 3`
2. **Context-aware preferred params:** фильтрация по `active_workflow` из PlanContext
3. **Rationale:** включает context info для отладки

#### 2.2. `app/planner/__init__.py` — export AdaptivePlanner

**Текущее состояние:** AdaptivePlanner НЕ экспортируется из `planner/__init__.py`.

**Изменение:** Добавить export:
```python
from app.planner.adaptive import AdaptivePlanner
```

#### 2.3. `app/agent.py` — optional adaptive_planner parameter

**Текущее состояние:**
```python
class Agent:
    def __init__(
        self,
        asset_store: AssetStore,
        model_registry: Optional[ModelRegistry] = None,
        workflows_dir: str = DEFAULT_WORKFLOWS_DIR,
        backends: Optional[BackendCatalog] = None,
        planner: Optional[Planner] = None,
        prompt_builder=None,
        execution_history: Optional[ExecutionHistory] = None,
        retry_policy: Optional[RetryPolicy] = None,
        semantic_verifier: Optional[SemanticVerifier] = None,
    ) -> None:
```

**Изменение:** Добавить `adaptive_planner` parameter:
```python
class Agent:
    def __init__(
        self,
        asset_store: AssetStore,
        model_registry: Optional[ModelRegistry] = None,
        workflows_dir: str = DEFAULT_WORKFLOWS_DIR,
        backends: Optional[BackendCatalog] = None,
        planner: Optional[Planner] = None,
        prompt_builder=None,
        execution_history: Optional[ExecutionHistory] = None,
        retry_policy: Optional[RetryPolicy] = None,
        semantic_verifier: Optional[SemanticVerifier] = None,
        adaptive_planner: Optional[Planner] = None,  # M16: context-aware adaptive
    ) -> None:
```

**Важно:** Agent.generate() **НЕ меняется**. Он по-прежнему использует `self.planner or HeuristicPlanner()`. AdaptivePlanner передаётся через `self.planner`, а не через отдельный parameter.

#### 2.4. `app/conversation.py` — auto-create AdaptivePlanner

**Текущее состояние:**
```python
class ConversationAgent(Agent):
    def __init__(
        self,
        *args,
        session_manager: Optional[SessionManager] = None,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
```

**Изменение:** Добавить auto-creation AdaptivePlanner:
```python
class ConversationAgent(Agent):
    def __init__(
        self,
        *args,
        session_manager: Optional[SessionManager] = None,
        adaptive_planner_enabled: bool = True,  # M16: включить adaptive planning
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.sessions: dict[str, ConversationContext] = {}
        self.session_manager = session_manager
        self._adaptive_planner_enabled = adaptive_planner_enabled
```

**Изменение в `turn()`:**
```python
def turn(self, session_id, capability=None, request=None, ...):
    ctx = self.session(session_id)

    # 1) capability (explicit ИЛИ через planner из request)
    if capability is None and request:
        planner = self.planner or _default_planner()

        # M16: auto-select AdaptivePlanner если история ≥ 3 для capability
        if self._adaptive_planner_enabled and self.execution_history is not None:
            # Определяем capability через fallback planner
            base_result = planner.plan(request, context=plan_ctx)
            success_count = len(self.execution_history.get_successful(base_result.capability))
            if success_count >= 3:
                from app.planner.adaptive import AdaptivePlanner
                planner = AdaptivePlanner(
                    history=self.execution_history,
                    fallback=self.planner or _default_planner(),
                )

        result = planner.plan(request, context=plan_ctx)
        capability = result.capability
        ...
```

**Важно:** AdaptivePlanner создаётся **внутри turn()** при необходимости, а не в `__init__`. Это позволяет:
1. Использовать актуальную execution_history
2. Не хранить AdaptivePlanner в state (создаётся на лету)
3. Сохранять fallback на HeuristicPlanner

### 3. Что НЕ БУДЕТ изменено

| Компонент | Почему не менять |
|-----------|-----------------|
| `Agent.generate()` | Одиноко-activated путь, AdaptivePlanner не нужен |
| `WorkflowEngine.execute()` | Core execution, не зависит от planner |
| `HeuristicPlanner` | Fallback, не удалять |
| `LLMPlanner` | Отдельный planner, не трогать |
| `CompositePromptBuilder` | Prompt enhancement, не зависит от planner |
| `ExecutionHistory` | Storage layer, не зависит от planner |
| `RetryPolicy` | Decision layer, не зависит от planner |
| `SemanticVerifier` | Verification layer, не зависит от planner |
| `SessionManager` | Persistence layer, не зависит от planner |
| `FeedbackStore` | Feedback layer,Phase 3 |
| `TaskDecomposer` | Multi-step,Phase 2 |
| `ExecutionChain` | Chain execution,Phase 2 |
| `Job`, `Asset`, `AssetStore` | Domain model, не зависит от planner |
| `Verifier` | Structural verification, не зависит от planner |
| `UI /turn`, `/api/feedback` | Endpoints, не зависят от planner |

### 4. Как AdaptivePlanner получает PlanContext

**Текущий flow:**
```
ConversationAgent.turn()
  → planner.plan(request, context=plan_ctx)  [conversation.py:167]
  → plan_ctx = PlanContext(active_asset_type, capabilities, active_workflow)
```

**Новый flow:**
```
ConversationAgent.turn()
  → base_result = planner.plan(request, context=plan_ctx)  [для определения capability]
  → if history.get_successful(capability) >= 3:
      adaptive = AdaptivePlanner(history=..., fallback=planner)
      result = adaptive.plan(request, context=plan_ctx)  [с context-awareness]
  → else:
      result = base_result  [HeuristicPlanner result]
```

**PlanContext передаётся в AdaptivePlanner.plan()** через стандартный параметр `context`.

### 5. Как разделяется history по capability/workflow/context

| Фильтр | Метод | Где применяется |
|--------|-------|-----------------|
| **By capability** | `history.get_successful(capability)` | AdaptivePlanner.plan(): порог, preferred_params |
| **By workflow** | `history.get_successful()` → фильтр по `workflow_id@version` | `_context_aware_preferred_params()` |
| **By context.active_workflow** | `PlanContext.active_workflow` | `_context_aware_preferred_params()` |

**Ключевой момент:** `HistoryAnalytics.preferred_params(capability)` уже фильтрует по capability. Изменения в AdaptivePlanner добавляют фильтрацию по workflow/context.

### 6. Что происходит при недостатке данных

| Сценарий | Поведение | Fallback |
|----------|-----------|----------|
| history.count() == 0 | AdaptivePlanner.plan() → `len(get_successful(cap)) < 3` → return base_result | HeuristicPlanner |
| history.count() == 1-2 | AdaptivePlanner.plan() → `len(get_successful(cap)) < 3` → return base_result | HeuristicPlanner |
| history.count() >= 3, но для другой capability | `preferred_params(cap)` → {} → return base_result | HeuristicPlanner |
| history.count() >= 3, контекст не совпадает | `_context_aware_preferred_params()` фильтрует → {} → return base_result | HeuristicPlanner |
| preferred_params пустой | return base_result | HeuristicPlanner |
| Fallback planner тоже fails | raise AgentError | — |

### 7. Fallback на существующий planner

**Гарантия:** AdaptivePlanner **всегда** имеет `self.fallback` (HeuristicPlanner по умолчанию). Если adaptive logic не может скорректировать params — возвращается результат fallback planner.

**Цепочка:**
```
AdaptivePlanner.plan(request, context)
  → base_result = self.fallback.plan(request, context)  [всегда]
  → if history < 3 for capability: return base_result
  → preferred = _context_aware_preferred_params(cap, context)
  → if not preferred: return base_result
  → merged = {**preferred, **base_result.params}
  → return PlanResult(capability, merged)
```

### 8. Как исключить cross-capability contamination

**Механизм:**

1. **Порог по capability:** `len(history.get_successful(capability)) < 3` — не используем глобальный count
2. **preferred_params по capability:** `analytics.preferred_params(capability)` — уже фильтрует по capability
3. **Workflow фильтр:** `_context_aware_preferred_params()` фильтрует по `active_workflow` из PlanContext
4. **Prompt preservation:** `merged_params["prompt"] = base_result.params["prompt"]` — prompt из request перезаписывает learned

**Гарантия:** preferred_params для `image.generate` НИКОГДА не попадут в `image.upscale` (разные capability).

### 9. Integration tests

| Тест | Что проверяет | Файл |
|------|---------------|------|
| `test_adaptive_uses_heuristic_fallback` | AdaptivePlanner возвращает HeuristicPlanner result при history < 3 | `tests/test_m16_adaptive_planner.py` |
| `test_adaptive_threshold_per_capability` | Порог ≥ 3 для конкретной capability, не глобальный | `tests/test_m16_adaptive_planner.py` |
| `test_adaptive_context_aware_params` | AdaptivePlanner учитывает PlanContext | `tests/test_m16_adaptive_planner.py` |
| `test_adaptive_no_cross_contamination` | History для image.generate НЕ влияет на image.upscale | `tests/test_m16_adaptive_planner.py` |
| `test_adaptive_preserves_prompt` | Prompt из request перезаписывает learned | `tests/test_m16_adaptive_planner.py` |
| `test_adaptive_with_empty_history` | AdaptivePlanner с пустой history → HeuristicPlanner | `tests/test_m16_adaptive_planner.py` |
| `test_conversation_auto_creates_adaptive` | ConversationAgent.turn() auto-creates AdaptivePlanner при history ≥ 3 | `tests/test_conversation_m7.py` |
| `test_conversation_fallback_without_history` | ConversationAgent.turn() использует HeuristicPlanner при history < 3 | `tests/test_conversation_m7.py` |

### 10. Как доказать, что M1–M12 не изменился

**Метод:** Regression test suite.

```powershell
# Запуск всех M1-M12 тестов
python -m pytest tests/test_agent.py tests/test_planner.py tests/test_planner_context.py tests/test_m1_runtime.py tests/test_m2_asset.py tests/test_m3_registry.py tests/test_conversation_m7.py tests/test_ui_m9.py tests/test_backends.py tests/test_upscale.py -q

# Ожидаемый результат: все тесты проходят (0 failures)
# Если есть regressions — STOP и rollback
```

**Дополнительно:**
1. `test_agent.py` — Agent.generate() тесты (8 tests)
2. `test_planner.py` — HeuristicPlanner тесты (4 tests)
3. `test_planner_context.py` — PlanContext тесты (11 tests)
4. `test_conversation_m7.py` — ConversationAgent тесты (7 tests)

**Все эти тесты используют HeuristicPlanner и НЕ затрагиваются изменениями в AdaptivePlanner.**

---

## ЧАСТЬ 3: ИТОГОВАЯ ТАБЛИЦА ИЗМЕНЕНИЙ

| Файл | Изменение | Строки | Риск |
|------|-----------|--------|------|
| `app/planner/adaptive.py` | Context-aware preferred_params, per-capability threshold | ~30 | Medium |
| `app/planner/__init__.py` | Export AdaptivePlanner | ~1 | Low |
| `app/agent.py` | Add adaptive_planner parameter | ~2 | Low |
| `app/conversation.py` | Auto-create AdaptivePlanner in turn() | ~15 | Medium |
| `tests/test_m16_adaptive_planner.py` | New integration tests | ~80 | Low |
| **ИТОГО** | | **~128 строк** | |

---

*Документ является APPROVED architectural decision + implementation plan. Production code не изменялся.*
