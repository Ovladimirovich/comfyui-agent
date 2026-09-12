# M26 Completion Report (partial: M26.1 / M26.2 / M26.4)

**Milestone:** M26 — Experience-Driven Planning Loop
**Date:** 2026-09-11
**Status:** M26.1 / M26.2 / M26.4 — **ACCEPTED**. M26.3 — **REDEFINED / DEFERRED as Video Editor Integration Boundary** (см. `docs/M26.3_FORENSIC_DESIGN.md` PART 2). M26 — **READY TO FREEZE**.
**Baseline:** M25 FROZEN. M1–M25 не изменялись.

> M26 целиком **READY TO FREEZE** после docs reconciliation (M26.3 REDEFINED/DEFERRED, AD-44 SUPERSEDED).

---

## 1. Changed files (M26 scope only)

Production code:
- `app/engine/experience.py` — +`ExperienceAnalytics` (read-only aggregation над `ExperienceStore`), +`ExperienceHint` dataclass, +`TemporalStats` dataclass, +`EXPERIENCE_MIN_SAMPLES_FOR_PREFERENCE = 2`.
- `app/planner/adaptive.py` — `AdaptivePlanner.__init__(experience_store=...)`; блок M26.2 (experience-preference как soft default); инициализация `feedback_info` перенесена выше.
- `app/planner/composer.py` — `compose(..., experience_hint=None)`; добавляет computed suggestion в `CompositionResult.suggestions`.
- `app/conversation.py` — wiring `experience_store=self.experience_store` в оба call-site `AdaptivePlanner` (turn + `_execute_chain_step`); построение `ExperienceHint` для `Composer.compose()` в multi-step path.
- `app/engine/__init__.py` — экспорт `ExperienceAnalytics`, `ExperienceHint`, `TemporalStats`.

Tests (new):
- `tests/test_m26_experience_analytics.py` (9)
- `tests/test_m26_adaptive_planner.py` (6)
- `tests/test_m26_composer_suggestion.py` (4)

Docs:
- `docs/M26_COMPLETION_REPORT.md` (this file)
- `docs/M26_PRE_IMPLEMENTATION_FORENSIC_DESIGN.md` (forensic design, уже существовал)
- State: `tasks/ACTIVE.md`, `tasks/COMPLETED.md`, `engineering/DECISION_LOG.md`, `engineering/HANDOFF.md`, `docs/MASTER_DEVELOPMENT_ROADMAP.md` — обновлены статусы M26.

> **Примечание по git:** рабочая копия содержит множество ПРЕДЫДУЩИХ незакоммиченных изменений (M25 B1/B2, `semantic_verifier.py`, `agent.py`, `manifest.json` и др.). Они НЕ относятся к M26. M26-изменения ограничены перечисленными выше файлами.

---

## 2. Production call graph — BEFORE / AFTER

### M26.2 (BEFORE)
```
ConversationAgent.turn() / _execute_chain_step()
  → planner auto-select → AdaptivePlanner(history, feedback_store)
      plan(): fallback.plan → if history<3 return; else context_aware_preferred_params (history only)
  → experience НЕ участвовал
```

### M26.2 (AFTER)
```
ConversationAgent.turn() / _execute_chain_step()
  → planner auto-select → AdaptivePlanner(history, feedback_store, experience_store)   # NEW param
      plan():
        1. base = fallback.plan(request, ctx)
        2. if history < 3 for capability → return base
        3. preferred = context_aware_preferred_params(...)            # history (AD-36)
        4. if experience_store:                                       # M26.2
             exp_pref = ExperienceAnalytics(store).preferred_params(capability)
             if exp_pref: preferred = {**preferred, **exp_pref}       # soft default, НЕ prohibition
        5. merged = {**preferred, **base.params}                     # explicit user params win
```

### M26.4 (AFTER)
```
ConversationAgent.turn() multi-step path:
  experience_hint = ExperienceAnalytics(store).temporal_stats(target) → ExperienceHint   # NEW
  composer.compose(target_capability, params, available_types, experience_hint=...)        # NEW param
    → CompositionResult.ok(chain, alternatives) + suggestions.append("Experience (n=…) …")  # NEW
```

---

## 3. M26.1 result — Experience Analytics

`ExperienceAnalytics` (read-only) над существующим `ExperienceStore`:
- `load_all()` — читает все `ChainExperience` (без мутации).
- `temporal_stats(capability)` — агрегирует `temporal_consistency` по релевантным цепочкам; `None` если нет samples (UNKNOWN → neutral).
- `preferred_params(capability)` — выбирает цепочку с **наивысшим** temporal score (непрерывный ranking, без magic cutoff) и возвращает её `video_params` как soft preference; `{}` при < `EXPERIENCE_MIN_SAMPLES_FOR_PREFERENCE` (2).

Нет новой persistence. `ChainExperience`/`SequenceExperience` не мутируются. Результат — preference signal, НЕ policy.

---

## 4. M26.2 result — Experience → AdaptivePlanner

- Интеграция через благословлённый путь: опциональный `experience_store` (аналог `feedback_store`).
- Experience влияет **только на ranking/preference** (soft default). Никаких hard prohibition / capability ban / workflow ban.
- `no experience` → старое поведение. `experience insufficient` (<2 samples) → fallback. `experience available` → observable preference в `plan().params`.
- `PlanContext` (M9.1) НЕ изменён. `ExecutionRecord` НЕ изменён. Нет magic `0.7`.

---

## 5. M26.4 result — Experience → Composer suggestions

- `Composer.compose(experience_hint=...)` добавляет **computed suggestion** в `CompositionResult.suggestions`.
- Не меняет `chain`/`alternatives`, не запрещает capability, не делает auto-replanning.
- `Experience → signal → suggestion` (НЕ `Experience → automatic policy`).
- Существующий `CompositionResult` поведён обратно-совместимо (поле `suggestions` уже существовало). Новый subsystem не создан.

---

## 6. D12 status (FeedbackStore → AdaptivePlanner)

**Подтверждено:** wiring уже существует и НЕ изменён.
```
AdaptivePlanner._feedback_weighted_params → HistoryAnalytics.preferred_params(feedback_weighted=True)
  → _filter_by_feedback → FeedbackStore.get_all()
```
Регрессионный тест `tests/test_m24_1_production_wiring.py` **проходит** (часть baseline). D12 НЕ является gap; новый функциональный scope не создавался (AC7).

---

## 7. M26.3 — REDEFINED / DEFERRED as Video Editor Integration Boundary

НЕ реализовано как video-processing внутри Agent. Не добавлены: cv2, ffmpeg, frame-extraction, video decoder, output-video quality gate, новый verifier.

**Новая семантика (2026-09-11):** M26.3 — интеграционный boundary между ComfyUI Agent и будущим отдельным проектом **Video Editor / Media Project**. Agent передаёт generated assets/episodes, Video Editor выполняет media-specific обработку и возвращает результат/feedback как downstream Experience. Agent НЕ содержит video-processing слоя.

**Исторические причины блокировки (forensic design, PART 1):** (1) отсутствует frame-extraction capability; (2) output-quality-gate semantics требовали AD; (3) threshold `0.7` не контракт. После появления решения об отдельном Video Editor — исходная постановка «frame extraction → temporal score → SUCCESS/FAILED» признана принадлежащей downstream media boundary; **AD-44 SUPERSEDED / NOT APPROVED**.

См. `docs/M26.3_FORENSIC_DESIGN.md` (PART 1 findings + PART 2 redefinition).

---

## 8. Invariants audit

| Invariant | M26.1/2/4 |
|-----------|------------|
| AD-03 media-agnostic | ✅ signal keyed by capability; фрейм-экстрактор не добавлен (M26.3 blocked) |
| AD-05 Asset ≠ file | ✅ experience ссылается на asset по id/path |
| AD-18 UNKNOWN ≠ AVAILABLE | ✅ `temporal_consistency=None` → neutral, не влияет |
| AD-28 doc hierarchy | ✅ |
| AD-36/37/38/39 | ✅ experience consumption только как preference; per-capability изоляция сохранена |
| AD-MODEL-BINDING-001 | ✅ без изменений |
| M25 Experience = fact | ✅ analytics/suggestions/ranking only; НЕ prohibition |
| Finding A (collect→verify→ingest) | ✅ не затронут (M26.3 не реализован) |
| PlanContext M9.1 frozen | ✅ НЕ изменён |
| ExecutionRecord schema | ✅ НЕ изменён |

---

## 9. Targeted test results

```
tests/test_m26_experience_analytics.py   9 passed
tests/test_m26_adaptive_planner.py      6 passed
tests/test_m26_composer_suggestion.py    4 passed
--- 19 new M26 tests, all GREEN
```

AC1 (aggregation, no mutation) ✅ · AC2 (ranking, fallback, no prohibition) ✅ · AC3 (observable preference) ✅ · AC4 (suggestion, backward-compat) ✅.

---

## 10. Full relevant regression

```
M25-related:      experience, temporal_verification, video_i2v, m25_b1_b2  → PASS
M14:              test_m14_semantic_verification                            → PASS
M16:              test_m16_adaptive_planner                                → PASS
M19:              test_m19_composer, test_m19_integration,
                  test_m19_feedback_integration                             → PASS
planner:          test_planner                                             → PASS
                  test_planner_context  → 5 FAILED (PRE-EXISTING, see §11)
conversation:     test_conversation_m7  (40 passed, 1 skipped)            → PASS
agent:            test_agent  (8 passed)                                   → PASS
D12 wiring:       test_m24_1_production_wiring                             → PASS
M26 new:          test_m26_*  (19 passed)                                  → PASS
```
**Aggregate: 192 passed, 1 skipped, 0 new failures.**

---

## 11. Pre-existing failures (NOT fixed, NOT M26-related)

`tests/test_planner_context.py` — 5 failures: `AgentError: no workflow with confirmed compatibility` (AD-18 runtime compatibility; environment lacks workflow compatibility data). Идентичны baseline до M26; не исправлялись (вне scope, unrelated).

Полный `tests/` содержит и другие инфра-зависимые падения (knowledge DB, live HTTP, реальный ComfyUI) — вне scope M26.

---

## 12. git diff / stat (annotated)

M26-изменения (этот session):
- `app/engine/experience.py` — +~190 LOC (ExperienceAnalytics + dataclasses)
- `app/planner/adaptive.py` — +20 LOC
- `app/planner/composer.py` — +21 LOC
- `app/conversation.py` — +M26 wiring (внутри уже существовавших M25-изменений рабочей копии)
- `app/engine/__init__.py` — +10 LOC (exports)
- `tests/test_m26_*.py` — 3 new files (19 tests)
- docs/state — статусы обновлены

Прочие изменения в `git diff --stat` (agent.py, semantic_verifier.py, manifest.json, registry/*, docs/14/18, HANDOFF, BACKLOG и др.) — **ПРЕДЫДУЩИЕ незакоммиченные изменения (M25/earlier)**, НЕ часть M26.

---

## 13. Self-review

- [x] M26.1/2/4 реализованы в рамках существующего AD-контура (AD-36/37/38/39, M9.1 FROZEN, single SemanticVerifier path).
- [x] Нет новых persistence layers / subsystems / AD.
- [x] `PlanContext` и `ExecutionRecord` не изменены.
- [x] Нет magic threshold `0.7` — ranking по непрерывному score, min-samples=2 (существующая конвенция).
- [x] Experience НЕ запрещает capability/workflow (проверено тестами).
- [x] D12 не изменён; regression-тест проходит.
- [x] M26.3 НЕ реализован (blockers соблюдены, workaround не применялись).
- [x] 0 new failures относительно baseline.
- [x] M25 / M1–M24 не затронуты.

---

## 14. Final verdict

**M26.1 / M26.2 / M26.4 — READY FOR ACCEPTANCE.**

**M26.3 — REDEFINED / DEFERRED** как Video Editor Integration Boundary (не video-processing внутри Agent). **AD-44 — NOT APPROVED / SUPERSEDED**. M26 целиком **READY TO FREEZE** после docs reconciliation.

---

*Report generated 2026-09-11. Implementation follows the approved forensic design (`docs/M26_PRE_IMPLEMENTATION_FORENSIC_DESIGN.md`). Read-only non-scope constraints honoured.*
