# M22 — Architectural Audit

**Date:** 2026-09-03
**Status:** AUDIT ONLY — no production code changes
**Goal:** Определить следующий milestone после M21

---

## 1. Текущее состояние execution cycle

```
request → understand → plan → execute → observe → verify → decide → correct/retry/ask → learn → result
    ✓        ✓          ✓       ✓         ✓         ✓        ✓         ✗?              ✗      ✓
```

### Что реализовано

| Фаза | Компонент | Статус | M# |
|------|-----------|--------|-----|
| Understand | HeuristicPlanner, LLMPlanner | ✅ | M8 |
| Plan | Composer + CapabilityGraph | ✅ | M19 |
| Execute | WorkflowEngine → Provider → ComfyUI | ✅ | M4 |
| Observe | ExecutionHistory + dispatch tracking | ✅ | M13+M21 |
| Verify | Verifier (structural) + SemanticVerifier | ✅ | M14 |
| Decide | RetryPolicy.decide() | ✅ | M13 |
| Correct | Параметрическая корректировка через suggested_params | ⚠️ Partial | M14 |
| Learn | AdaptivePlanner (stats-only) | ⚠️ Partial | M16 |

### Что НЕ реализовано

| Gap | Описание | Severity |
|-----|----------|----------|
| **Decision→User bridge** | `RetryDecision.action="failed"` не передаёт контекст пользователю | HIGH |
| **ASK_USER decision** | Нет явного решения "запросить пользователя" | MEDIUM |
| **Correction strategy** | Только suggested_params от SemanticVerifier, нет стратегии "что менять" | MEDIUM |
| **Feedback→Decision** | FeedbackStore не влияет на RetryPolicy/Decision | MEDIUM |
| **Parameter adjustment history** | Нет памяти о предыдущих корректировках | LOW |

---

## 2. Анализ текущего decision loop

### 2.1 Текущий код (Agent.generate())

```python
# M13: retry loop
for attempt in range(1, max_attempts + 1):
    job = self.run(...)

    # M14: semantic verification
    if semantic_verifier and job.success:
        semantic_result = verifier.verify(...)
        # Если suggested_params → скорректировать
        if semantic_result.suggested_params:
            current_params = {**current_params, **semantic_result.suggested_params}

    # M13: retry decision
    decision = retry_policy.decide(state=job.state, attempt=attempt, error_class=...)
    if decision.action == "accept":
        return job
    elif decision.action == "retry":
        sleep(decision.delay)
        continue
    else:  # failed
        return job  # ← Пользователь получает Job с ошибкой, но без контекста
```

### 2.2 Проблема

Когда `decision.action == "failed"`:
- Пользователь получает `Job(state=FAILED, error="...")`
- Нет объяснения ПОЧЕМУ
- Нет sugestций ЧТО ДЕЛАТЬ
- Нет возможности korректировки_params
- Feedback не влияет на следующее решение

### 2.3 Что нужно для M22

```python
# Желаемое поведение:
decision = retry_policy.decide(...)
if decision.action == "failed":
    # Не просто return job — предоставить контекст
    raise AgentFailedError(
        job=job,
        reason=decision.reason,
        suggestions=["try different prompt", "reduce steps", "ask user"],
        semantic_score=semantic_result.score if semantic_result else None,
    )
```

---

## 3. Варианты M22

### Вариант A: Human-in-the-Loop Decision Bridge

**Суть:** Связать decision loop с пользователем через UI/SSE.

**Изменения:**
- `RetryDecision` → добавить `suggestions: list[str]`
- `Agent.generate()` → при `failed` создавать enriched error
- UI → показывать error + suggestions + feedback button
- Feedback → записывается в ExecutionRecord → влияет на AdaptivePlanner

**Объём:** ~50 строк кода, 3 новых теста

**Риски:** Низкие — только добавление optional полей

---

### Вариант B: Parameter Adjustment Strategy

**Суть:** Добавить явную стратегию корректировки параметров при failure.

**Изменения:**
- `CorrectionStrategy` — новый класс (adjust width/height/steps based on failure type)
- Интеграция в retry loop
- History-based adjustment (если предыдущие попытки были с X → попробовать Y)

**Объём:** ~150 строк кода, 8 новых тестов

**Риски:** Средние — новая логика в execution path

---

### Вариант C: Feedback-Driven Decision

**Суть:** Связать FeedbackStore с RetryPolicy для informed decisions.

**Изменения:**
- `RetryPolicy` → добавить `feedback_store` parameter
- `decide()` → учитывать ratings из feedback
- Low rating → adjust params or ASK_USER
- High rating → reinforce current params

**Объём:** ~100 строк кода, 5 новых тестов

**Риски:** Средние — изменение RetryPolicy contract

---

## 4. Рекомендация

**M22 = Вариант A (Human-in-the-Loop Decision Bridge)**

Обоснование:
1. Минимальный объем изменений (~50 строк)
2. Не меняет frozen execution path (только enriched error)
3. Закрывает критический gap: decision "failed" → пользователь не знает что делать
4. Подготовка для Варианта B и C (feedback→decision мост уже есть)
5. Соответствует архитектурному принципу: "Agent not autonomous, user in control"

---

## 5. Что НЕ делать в M22

```
❌ Рефакторить RetryPolicy
❌ Менять WorkflowEngine
❌ Добавлять новый execution path
❌ Изменять M1–M21
❌ Добавлять LLM для correction decisions
❌ Создавать "autonomous learning" (NG3)
```

---

## 6. Критерии готовности M22

```text
[ ] RetryDecision имеет поле suggestions
[ ] Agent.generate() при failed抛 enriched error
[ ] UI показывает error + suggestions
[ ] Feedback записывается в ExecutionRecord
[ ] 5+ тестов покрыты
[ ] 436 regression tests pass
[ ] Документация обновлена
```

---

*Audit complete. Awaiting approval for M22 implementation.*
