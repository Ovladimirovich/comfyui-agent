# M22–M24: Decision Bridge + Parameter Adjustment + Feedback-Driven Decision

**Date:** 2026-09-04
**Status:** COMPLETED, FROZEN
**Tests:** 70 new (14 + 35 + 21), 496 total regression pass

---

## M22: Human-in-the-Loop Decision Bridge

**Цель:** `decision=failed` передаёт контекст + suggestions пользователю.

### Изменения

| Файл | Изменение |
|------|-----------|
| `app/engine/retry.py` | `RetryDecision.suggestions: list[str]` — подсказки для каждого failed branch |
| `app/engine/job.py` | `Job._decision_reason`, `Job._decision_suggestions` — enriched failure context |
| `app/agent.py` | `generate()` — обогащает job при failed и all-attempts-exhausted |
| `app/conversation.py` | `turn()` — `decision_failed` event в `ctx.messages`, enriched `ctx.unresolved` |

### поведение

```
При failed:
  job._decision_reason = "permanent error: permanent"
  job._decision_suggestions = ["проверьте доступность модели", ...]
  ctx.messages += {"type": "decision_failed", "reason": ..., "suggestions": [...]}
  ctx.unresolved += {..., "reason": ..., "suggestions": [...]}
```

---

## M23: Parameter Adjustment Strategy

**Цель:** Системная корректировка параметров при retry.

### Изменения

| Файл | Изменение |
|------|-----------|
| `app/engine/retry.py` | `CorrectionStrategy` class + 5 встроенных adjust_fn |
| `app/engine/retry.py` | `DEFAULT_CORRECTION_STRATEGIES` — 3 стратегии (verification + transient) |
| `app/engine/retry.py` | `RetryDecision.param_adjustments: dict | None` |
| `app/engine/retry.py` | `RetryPolicy._compute_adjustments()` — применяет стратегии |
| `app/engine/retry.py` | `decide()` — принимает `current_params`, `semantic_score` |
| `app/engine/history.py` | `ExecutionRecord.corrections_applied: list[dict] | None` |
| `app/agent.py` | `generate()` — `param_adjustments` > `semantic suggested_params` |
| `app/conversation.py` | `turn()` — `param_adjustments` в retry path |

### Встроенные стратегии

| Error Class | Стратегия | Эффект |
|-------------|-----------|--------|
| verification | score < 0.3 | steps *= 0.7 (min 5) |
| verification | score ≥ 0.3 | steps *= 1.3 (max 50) |
| verification | always | CFG ±1.0 по score |
| transient | always | timeout *= 1.5 (max 300) |

### Приоритет

```
decision.param_adjustments (стратегия) > semantic suggested_params (fallback)
```

---

## M24: Feedback-Driven Decision

**Цель:** FeedbackStore влияет на RetryPolicy — low rating → ask_user.

### Изменения

| Файл | Изменение |
|------|-----------|
| `app/engine/retry.py` | `RetryPolicy.feedback_store`, `session_id`, `low_rating_threshold` |
| `app/engine/retry.py` | `_check_feedback_after_success()` — проверка rating после SUCCESS |
| `app/engine/retry.py` | `decide()` — принимает `prompt_id`, проверяет feedback |
| `app/engine/job.py` | `Job._decision_action: str | None` ("ask_user") |
| `app/agent.py` | `generate()` — обрабатывает `action="ask_user"` |
| `app/conversation.py` | `turn()` — `feedback_request` event, `dialog_state="awaiting_feedback"` |

### поведение

```
SUCCESS + rating <= 2 → action="ask_user"
  job._decision_action = "ask_user"
  ctx.messages += {"type": "feedback_request", "reason": ..., "suggestions": [...]}
  ctx.dialog_state = "awaiting_feedback"
```

### Backward compatibility

- `feedback_store=None` → поведение как раньше (нет feedback check)
- `prompt_id=None` → поведение как раньше
- Все существующие тесты продолжают работать

---

## Тесты

| Файл | Тестов | Coverage |
|------|--------|----------|
| `test_m22_decision_bridge.py` | 14 | RetryDecision.suggestions, Agent enriched failure, ConversationAgent events |
| `test_m23_parameter_adjustment.py` | 35 | adjust_fn, CorrectionStrategy, param_adjustments, ExecutionRecord.corrections |
| `test_m24_feedback_decision.py` | 21 | feedback_store, ask_user, _check_feedback, backward compat |

---

## Execution Cycle (обновление)

```
request → understand → plan → execute → observe → verify → decide → correct/retry/ask → learn → result
    ✓        ✓          ✓       ✓         ✓         ✓        ✓         ✓ (M22-M24)    ✗      ✓
```

Фаза 7 (CORRECT) теперь полностью закрыта:
- M23: param_adjustments от CorrectionStrategy
- M22: enriched failure context для пользователя
- M24: feedback-driven ask_user

Фаза 8 (LEARN) — AdaptivePlanner (M16) частично покрывает, но не влияет на decisions.

---

*Frozen: M22-M24. Do not modify core logic.*
