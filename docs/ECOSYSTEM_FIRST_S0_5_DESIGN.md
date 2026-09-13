# S0.5 Design — Knowledge Core Slice 2: Agent Pre-flight Wiring

> **Статус:** DESIGN ONLY — не реализация.
> **Дата:** 2026-09-13.
> **Base:** `docs/ECOSYSTEM_FIRST_ARCHITECTURE.md` (APPROVED), текущий HEAD.
> **Ограничения:** production code NO, tests NO, UI NO, commit NO. Только проектирование и forensic audit.

---

## 1. Current Call Graph (single-step)

Фактический execution path по HEAD (без Knowledge Core):

```text
Agent.generate(request)
  │
  ├─ planner.plan(request)                    → PlanResult{capability, params}
  ├─ prompt_builder.build(ctx)                → enhanced prompt (M11.6, optional)
  ├─ self.run(capability, params)
  │    ├─ self.prepare(capability, params)
  │    │    ├─ BackendCatalog.choose()        → provider
  │    │    ├─ _discover_facts(client)        → DiscoveryFacts{runtime, models, custom_nodes}
  │    │    ├─ _select_manifest(capability,   → Workflow (AVAILABLE, ranked)
  │    │    │      runtime, models, custom_nodes)
  │    │    │    ├─ _compatibility_from_known → status, reasons
  │    │    │    └─ _calculate_validation_score (ranking, S4 — currently always 0)
  │    │    ├─ _resolve_model_requirements    → model_bindings
  │    │    └─ ExecutionPlan(...)             → plan
  │    └─ engine.execute(manifest, plan, provider) → Job
  ├─ retry_policy.decide(...)                 → accept/retry/ask_user/failed
  └─ execution_history.record(...)

ConversationAgent.turn(session_id, request)
  │
  ├─ [multi-step detection]                   → _execute_chain OR single-step
  ├─ planner.plan(request, PlanContext{...})  → PlanResult{capability, params}
  ├─ prompt_builder.build(ctx)                → enhanced prompt (M11.6, optional)
  ├─ self.prepare(capability, params)         → (same as Agent.prepare)
  ├─ resolve_asset_inputs(...)                → bindings
  ├─ engine.execute(manifest, plan, provider) → Job
  ├─ retry loop (M13/M14)
  ├─ update ctx (active_asset, active_workflow)
  └─ experience_store.record(chain_exp)       → (M25)
```

### Ключевые observation

1. **Capability определяется ДО manifest selection.** `planner.plan()` → `PlanResult.capability`. На этом этапе мы знаем operation, но не знаем конкретный workflow.
2. **Manifest selection (_select_manifest) определяет конкретный Workflow.** После этого знаем workflow_id@version, asset_inputs, required_models, required_custom_nodes.
3. **Execution (engine.execute) — точка невозврата.** После неё — реальный ComfyUI Job.
4. **Job — mutable @dataclass (не frozen).** Уже содержит underscore-prefixed optional metadata: `_original_prompt`, `_enhanced_prompt`, `_prompt_source`, `_decision_reason`, `_decision_suggestions`, `_decision_action`, `_applied_corrections`. Паттерн additive metadata — established.
5. **KnowledgeCore.query() — read-only, in-memory.** Не делает HTTP, не трогает ComfyUI, не требует runtime. Возвращает `KnowledgeResponse{known_capabilities, candidate_nodes, claims, gaps, readiness, research_requests}`.

---

## 2. Problem Statement

Knowledge Core (Slice 1) существует как изолированный пакет `app/knowledge/`. Он умеет:
- обнаруживать schemas нод (NodeSchemaStore);
- генерировать candidates (CandidateGenerator);
- собирать claims/evidence (EvidenceStore, LocalResearchProvider);
- оценивать readiness (KnowledgeCore.query());
- запускать runtime validation (RuntimeValidator).

**Проблема:** Agent и ConversationAgent не знают о Knowledge Core. KnowledgeCore.query() никогда не вызывается в production path. Информация о readiness, gaps, candidates не влияет ни на planning, ни на execution, ни на observability.

**Следствие:**
- Для новой ноды без workflow Agent не знает, что capability-кандидат существует;
- Gaps (NO_WORKFLOW, INSUFFICIENT_EVIDENCE) не видны в Job metadata;
- Research requests не генерируются в production;
- `_calculate_validation_score` всегда 0 (нет данных validated_nodes в Agent);
- Полный цикл Tool Learning (DISCOVER→UNDERSTAND→VERIFY→REUSE) разорван между knowledge и execution.

---

## 3. S0.5 Scope

### В scope

1. Optional `knowledge_core` param в `Agent.__init__` (backward-compatible, default=None).
2. Query adapter: `PlanResult` + `Workflow` → `KnowledgeQuery`.
3. Advisory call to `KnowledgeCore.query()` AFTER manifest selection, BEFORE engine.execute.
4. Knowledge metadata на Job: `_knowledge_readiness`, `_knowledge_gaps` (optional, additive, same pattern as existing Job metadata).
5. ConversationAgent passthrough (same optional param, forward to Agent).

### НЕ в scope (explicit non-goals)

- RuntimeValidator repair (_validate_capability_nodes_background) — отдельный deferred milestone.
- `_calculate_validation_score` activation — отдельный deferred milestone.
- Knowledge → Planner influence (knowledge changing which capability/workflow is selected) — FUTURE.
- CostTier — S1.
- user_confirmed — S3.
- Explain contract — S2.
- usage/limitation claims — S4.
- New persistence layer — Knowledge uses existing ClaimsPersistence.
- Changes to PlanContext, ExecutionRecord, JobState, ExperienceStore format (frozen M25/M26).

---

## 4. Proposed Contract

### A. Input — что KnowledgeCore получает

Из PlanResult + Workflow (после _select_manifest):

| Поле KnowledgeQuery | Источник | Mapping |
|---|---|---|
| `required_operation` | `PlanResult.capability` | Прямое присвоение (строка, напр. `"image.generate"`) |
| `required_media_input` | `Workflow.asset_inputs` (dict of role → AssetInput) | `{ain.kind for ain in manifest.asset_inputs.values()}` → tuple, напр. `("image",)` или `()` |
| `required_media_output` | `Workflow.capability` или `CapabilityRegistry` | Из `CapabilityRegistry.get(capability).media_output` если есть; fallback — inference из capability name (`"image.generate"` → `"image"`) |
| `input_cardinality` | `len(Workflow.asset_inputs)` | `int`, напр. 0 для txt2img, 1 для img2img, 2 для first-and-last |
| `task_description` | `request` (original user text, optional) | Строка, может быть пустой |

**Что НЕ передаётся (и почему):**
- workflow_id@version — KnowledgeCore не фильтрует по конкретному workflow, а оценивает capability-level readiness.
- model_requirements — KnowledgeCore не проверяет модели (это делает compatibility filter).
- backend_id — Knowledge не зависит от backend.
- params — параметры генерации не влияют на knowledge readiness.

### B. Query Adapter — `_plan_result_to_query()`

```python
def _plan_result_to_query(
    self,
    result: PlanResult,
    manifest: Optional[Workflow] = None,
) -> Optional[KnowledgeQuery]:
```

**Input:**
- `result: PlanResult` — от planner (capability + params).
- `manifest: Optional[Workflow]` — от _select_manifest (workflow с asset_inputs, required_models, и т.д.).

**Output:**
- `KnowledgeQuery` если capability валидна и knowledge_core доступен.
- `None` если adapter не может сформировать query (graceful fallback).

**Mapping logic:**
1. `required_operation = result.capability` (строка).
2. `required_media_input = tuple(sorted({ain.kind for ain in manifest.asset_inputs.values()}))` если manifest задан; иначе `()`.
3. `required_media_output = _infer_media_output(result.capability)` — lookup в CapabilityRegistry если есть; fallback — heuristic parse (e.g. `"image.generate"` → `"image"`, `"video.image_to_video"` → `"video"`); если не определено — пустая строка.
4. `input_cardinality = len(manifest.asset_inputs)` если manifest задан; иначе `0`.
5. `task_description = result.params.get("prompt", "")` (optional, для research requests).

**При неполном плане:**
- Если `manifest=None` (вызвано до _select_manifest): query формируется только из capability name, media_input=(), input_cardinality=0. Менее точный, но всё ещё полезный (проверяет existence capability).
- Если capability неизвестна (пустая строка): возвращает `None`, knowledge пропускается.

**При отсутствии knowledge_core:**
- `self.knowledge_core is None` → query не формируется, `None`, knowledge пропускается.

**При UNKNOWN readiness:**
- Не блокирует execution. UNKNOWN = отсутствие knowledge данных, НЕ отсутствие capability. Job.metadata получает `readiness=UNKNOWN, gaps=[]`.

**При конфликтующих evidence:**
- KnowledgeCore уже обрабатывает conflicting claims internally (CONFLICTING_KNOWLEDGE gap). Gap попадает в `response.gaps` и далее в Job metadata. Не блокирует.

### C. Readiness Semantics

| Readiness | Значение в S0.5 | Действие |
|---|---|---|
| `EXECUTABLE` | Capability найдена в WorkflowRegistry, workflow AVAILABLE, gaps отсутствуют | Proceed normally. Advisory only. |
| `CANDIDATE_ONLY` | Кандидаты (CapabilityCandidate) найдены, но нет production workflow | Proceed normally. Advisory only. Gap logged on Job. |
| `GAP` | Knowledge gaps detected (INSUFFICIENT_EVIDENCE, NO_WORKFLOW, etc.) | Proceed normally. Advisory only. Gaps logged on Job. |
| `UNKNOWN` | Ни capability, ни candidates не найдены | Proceed normally. Advisory only. **Knowledge absence ≠ capability absence.** |

**Критическое правило: Knowledge readiness НИКОГДА не блокирует execution.**
- Если `knowledge_core=None`: execution идёт как раньше (zero behavioral change).
- Если KnowledgeCore пуст (нет schemas, не вызывался refresh): query вернёт UNKNOWN. Execution идёт как раньше.
- Если KnowledgeCore вернул GAP: execution идёт как раньше.
- Knowledge — observability layer, не execution controller.

> **ARCHITECTURAL INVARIANT (approved 2026-09-13).** Readiness (`EXECUTABLE / CANDIDATE_ONLY / GAP / UNKNOWN`) означает **что Knowledge Core знает о готовности**, НЕ «можно запускать». Реальное решение об executable eligibility остаётся за существующими capability/workflow/provider/backend validation механизмами. Knowledge → advisory evidence. Existing capability/provider/backend checks → actual execution eligibility. `Knowledge says EXECUTABLE` НЕ означает `Agent executes` — это разные слои проверки.

### D. Integration Point

**Точка интеграции: после _select_manifest, перед engine.execute.**

Обоснование по call graph:

1. **После planner.plan():** имеем capability. Но ещё не знаем конкретный workflow.
2. **После _select_manifest():** имеем capability + конкретный Workflow (manifest). Теперь query точнее: media_input/output/cardinality определены из manifest.
3. **Перед engine.execute():** knowledge response записывается на Job до execution. Если execution упадёт, Job всё равно содержит knowledge metadata (диагностика).
4. **НЕ после engine.execute():** knowledge не зависит от результата execution (это Experience layer).

**Место в коде:**

В `Agent.generate()` — после `self.run()` → внутри `run()` → после `prepare()` → перед `engine.execute()`:

```python
def run(self, capability, params, ...):
    manifest, plan, provider = self.prepare(capability, params, ...)
    
    # S0.5: Knowledge pre-flight (advisory, non-blocking)
    knowledge_meta = self._knowledge_preflight(capability, manifest)
    
    job = self.engine.execute(manifest, plan, provider=provider, ...)
    
    # Attach knowledge metadata to job (post-execution, additive)
    if knowledge_meta is not None:
        job._knowledge_readiness = knowledge_meta["readiness"]
        job._knowledge_gaps = knowledge_meta["gaps"]
    
    return job
```

В `ConversationAgent.turn()` — аналогично, после `self.prepare()`, перед `self.engine.execute()`. Knowledge metadata на Job после execution.

**Альтернатива: отдельный service boundary (KnowledgeAdvisor).**
Не в S0.5 — это over-engineering для advisory-only layer. Если knowledge станет blocking (FUTURE), service boundary будет justified.

### E. Job Metadata

**Что добавляется на Job:**

```python
# В app/engine/job.py — additive, optional, underscore-prefixed
_knowledge_readiness: str | None = None   # "EXECUTABLE" / "CANDIDATE_ONLY" / "GAP" / "UNKNOWN"
_knowledge_gaps: list[str] | None = None  # human-readable gap descriptions, e.g. ["no_workflow for video.generate"]
```

**Обоснование:**
- Паттерн совпадает с `_original_prompt`, `_enhanced_prompt`, `_prompt_source`, `_decision_reason`, `_decision_suggestions`, `_decision_action`, `_applied_corrections` — все underscore-prefixed optional metadata на Job.
- Job — mutable @dataclass, не frozen. Добавление optional полей с default=None backward-compatible.
- ExecutionRecord (persistence) НЕ захватывает knowledge поля — они runtime-only. Если позже knowledge persistence нужна — расширить ExecutionRecord отдельно.
- Поля не влияют на serialization Job (Job не сериализуется напрямую; persistence идёт через ExecutionRecord.from_job()).
- SSE/UI может отображать knowledge readiness — существующие UI endpoints (`GET /events`, `GET /api/session`) получают job.as_dict() (если есть) или могут быть расширены позже.

**Альтернатива (отвергнута):** отдельный `KnowledgeResult` object alongside Job. Не justified: knowledge metadata — свойство решения о запуске, логически привязано к Job. Отдельный объект добавляет complexity без benefit.

---

## 5. Data Flow

```text
user request
  │
  ▼
planner.plan(request) → PlanResult{capability, params}
  │
  ▼
Agent.prepare(capability, params)
  ├─ _discover_facts(client) → DiscoveryFacts
  ├─ _select_manifest(capability, ...) → Workflow (manifest)
  │    ├─ _compatibility_from_known → AVAILABLE
  │    └─ _calculate_validation_score → 0 (S4 dead, deferred)
  ├─ ExecutionPlan(...)
  │
  ▼  ──── S0.5 insertion point ────
  │
  ├─ _plan_result_to_query(PlanResult, manifest) → KnowledgeQuery
  │    ├─ required_operation = capability
  │    ├─ required_media_input = {ain.kind for ain in manifest.asset_inputs.values()}
  │    ├─ required_media_output = infer from capability/capability_registry
  │    ├─ input_cardinality = len(manifest.asset_inputs)
  │    └─ task_description = params.get("prompt", "")
  │
  ├─ knowledge_core.query(KnowledgeQuery) → KnowledgeResponse
  │    ├─ known_capabilities: list[str]
  │    ├─ candidate_nodes: list[CapabilityCandidate]
  │    ├─ claims: list[KnowledgeClaim]
  │    ├─ gaps: list[KnowledgeGap]
  │    ├─ readiness: Readiness
  │    └─ research_requests: list[ResearchRequest]
  │
  ├─ _knowledge_preflight metadata extracted:
  │    readiness = response.readiness.value    # "EXECUTABLE" / "GAP" / ...
  │    gaps = [g.needed for g in response.gaps] # human-readable strings
  │
  ▼  ──── end S0.5 ────
  │
  ▼
engine.execute(manifest, plan, provider) → Job
  │
  ▼  ──── S0.5: attach metadata ────
  │
  job._knowledge_readiness = readiness
  job._knowledge_gaps = gaps
  │
  ▼
return Job (with knowledge metadata)
```

---

## 6. Error / Fallback Semantics

| Сценарий | Поведение |
|---|---|
| `knowledge_core=None` | Query не выполняется. `_knowledge_readiness=None`, `_knowledge_gaps=None` на Job. Execution path identical to current. |
| `KnowledgeCore` пуст (нет schemas, refresh не вызывался) | Query возвращает `readiness=UNKNOWN, gaps=[], candidates=[], known_capabilities=[]`. Execution proceeds normally. |
| `_plan_result_to_query()` возвращает `None` (неизвестная capability) | Query пропускается. `_knowledge_readiness=None`, `_knowledge_gaps=None`. |
| `KnowledgeCore.query()` бросает исключение | Caught silently. `_knowledge_readiness=None`, `_knowledge_gaps=None`. Log warning (optional). Execution proceeds normally. |
| Malformed KnowledgeQuery (пустая capability) | `_plan_result_to_query` returns `None`. No query made. |
| `READINESS.GAP` | Advisory only. Execution proceeds. Gaps logged on Job for diagnostics. |
| `READINESS.UNKNOWN` | Advisory only. Execution proceeds. Knowledge absence ≠ capability absence. |
| Conflicting evidence | KnowledgeCore returns gaps with `CONFLICTING_KNOWLEDGE` type. Logged on Job. Execution proceeds. |
| Capability неизвестна KnowledgeCore но известна WorkflowRegistry | `known_capabilities` в response. `readiness=EXECUTABLE`. Normal path. |

**Критическое invariant:**
```python
# Если knowledge_core=None ИЛИ query failed ИЛИ readiness=UNKNOWN:
# → execution proceeds IDENTICAL to current behavior
# → no behavioral change, no regression, no blocking
```

---

## 7. Backward Compatibility

| Сценарий | Поведение |
|---|---|
| `Agent(store)` (без knowledge_core) | `knowledge_core=None` по умолчанию. `_knowledge_preflight()` returns None. Job без knowledge metadata. **Identical to current.** |
| `ConversationAgent(store)` (без knowledge_core) | Same. `knowledge_core=None` forward from `**kwargs`. |
| Старые persisted Jobs (ExecutionRecord) | ExecutionRecord не содержит knowledge полей. При загрузке — knowledge metadata = None. **Identical to current.** |
| Старые Conversation sessions | ConversationContext не содержит knowledge полей. Нет impact. |
| Старые ExecutionPlans | ExecutionPlan не содержит knowledge полей. Нет impact. |
| `Agent(store, knowledge_core=core)` | Knowledge pre-flight выполняется. Job содержит `_knowledge_readiness` и `_knowledge_gaps`. **Additive, non-breaking.** |
| Existing tests (test_agent.py, test_m3_registry.py, etc.) | Не задают knowledge_core → knowledge_core=None → identical behavior. **No regression.** |

---

## 8. Relationship to RuntimeValidator

**S0.5 НЕ включает RuntimeValidator integration.**

Текущее состояние:
- `_validate_capability_nodes_background` (agent.py:411) — dead code (нет production-вызовов), сигнатурно несовместим (`validate_node(node_type)` без `workflow`).
- `Agent._validated_nodes` пуст в production → `_calculate_validation_score` всегда 0.
- `KnowledgeCore._validated_nodes` загружается из ClaimsPersistence (свой кэш, не shared с Agent).

**S0.5 не чинит и не трогает:**
- `_validate_capability_nodes_background`.
- `_calculate_validation_score`.
- Связку Agent._validated_nodes ↔ RuntimeValidator.

**Отношение к Knowledge pre-flight:**
- Knowledge pre-flight использует KnowledgeCore.query() — это candidates/claims/readiness, НЕ runtime validation.
- RuntimeValidator — это SELF-TEST стадия (validate node on live ComfyUI). Pre-flight — UNDERSTAND/VERIFY стадии.
- Они дополняют друг друга, но не зависят друг от друга. S0.5 работает без RuntimeValidator.

**Deferred milestone: S0.6 (RuntimeValidator → Agent)**
- Repair `_validate_capability_nodes_background` (fix signature, add production caller).
- Or: separate RuntimeValidatorService that populates Agent._validated_nodes.
- Or: KnowledgeCore → Agent validated_nodes sync.
- Requires separate design + approval.

---

## 9. Relationship to `_calculate_validation_score`

**S0.5 НЕ активирует `_calculate_validation_score`.**

Текущее состояние:
- `_calculate_validation_score` (agent.py:322) — real code, called in `_select_manifest` ranking.
- Источник данных: `self._validated_nodes` (dict[str, bool]).
- Production значение: пустой dict → score всегда 0 → ranking: priority → min_vram → id → version.

**Почему S0.5 не включает это:**
1. `_validated_nodes` заполняется `_validate_capability_nodes_background` (dead code).
2. Активация требует RuntimeValidator repair (отдельный scope).
3. Knowledge pre-flight не влияет на `_validated_nodes` — это разные механизмы:
   - `_validated_nodes` = runtime-доказательство «нода X работает на ComfyUI» (SELF-TEST).
   - KnowledgeCore readiness = semantic-оценка «capability X известна и имеет evidence» (UNDERSTAND/VERIFY).
4. Смешивание этих concerns в S0.5 привело бы к scope creep.

**Deferred milestone (после S0.5):**
- Repair RuntimeValidator hook → Agent._validated_nodes populated.
- `_calculate_validation_score` начнёт возвращать > 0.
- Workflow ranking улучшится: validated workflows выше.
- Это НЕ S0.5, это отдельный architectural decision.

---

## 10. Ecosystem-First Lifecycle Mapping

S0.5 реализует связку между **UNDERSTAND/VERIFY** стадиями и **REUSE** observability:

```text
DISCOVER     — NodeSchemaStore.refresh()            [IMPL, не трогается S0.5]
INSPECT      — NodeDocStore + LocalResearchProvider  [IMPL, не трогается S0.5]
UNDERSTAND   — CandidateGenerator + KnowledgeCore   [IMPL, не трогается S0.5]
SELF-TEST    — RuntimeValidator                      [IMPL (module), dead hook — DEFERRED]
VERIFY       — ClaimsPersistence + EvidenceStore     [IMPL, не трогается S0.5]
EXPLAIN      — (нет контракта)                       [FUTURE, S2]
CO-USE       — Agent.generate/ConversationAgent.turn [IMPL, S0.5 добавляет knowledge metadata]
REMEMBER     — ExecutionHistory + ExperienceStore     [IMPL, не трогается S0.5]
REUSE        — _calculate_validation_score           [IMPL (code), data empty — DEFERRED]
             — Knowledge pre-flight on Job           [S0.5 — НОВОЕ]
```

**S0.5 закрывает конкретный gap:** knowledge response (candidates, claims, gaps, readiness) → Job metadata. Цикл DISCOVER→UNDERSTAND→VERIFY→CO-USE(observability) становится замкнутым. REUSE (ranking influence) остаётся deferred.

**Knowledge advisory в lifecycle:**
- DISCOVER/INSPECT/UNDERSTAND/VERIFY: модули существуют, S0.5 не трогает.
- CO-USE: S0.5 добавляет knowledge → Job metadata. Knowledge влияет на observability, не на execution choice.
- REUSE: _calculate_validation_score = deferred. Knowledge pre-flight на Job = first step toward reuse observability.

---

## 11. Free-First Implications

**S0.5 не создаёт скрытого платного execution path.**

| Проверка | Результат |
|---|---|
| KnowledgeCore.query() делает HTTP/external calls? | Нет. In-memory read-only query against cached schemas/claims. |
| Knowledge pre-flight запускает ComfyUI workflow? | Нет. Advisory only, перед engine.execute. |
| Knowledge pre-flight выбирает provider/backend? | Нет. Provider выбирается в Agent.prepare() ДО knowledge query. |
| Knowledge pre-flight влияет на cost? | Нет. CostTier не существует (S1 — FUTURE). |
| RuntimeValidator в S0.5? | Нет. RuntimeValidator может запускать workflow на ComfyUI, но S0.5 его не вызывает. |

Knowledge pre-flight = pure read-only advisory. Zero cost implication.

---

## 12. Test Matrix (design only, не писать)

| # | Тест | Ожидаемое поведение |
|---|---|---|
| T1 | Legacy path: `Agent(store)` без knowledge_core | `job._knowledge_readiness=None`, `job._knowledge_gaps=None`. Execution identical. |
| T2 | Legacy path: `ConversationAgent(store)` без knowledge_core | Same as T1. |
| T3 | Knowledge hit (EXECUTABLE): `Agent(store, knowledge_core=core)` с реальным core.refresh(client) | `job._knowledge_readiness="EXECUTABLE"`, `job._knowledge_gaps=[]` (or empty). Execution proceeds. |
| T4 | Knowledge miss (UNKNOWN): knowledge_core без schemas | `job._knowledge_readiness="UNKNOWN"`, `job._knowledge_gaps=[]`. Execution proceeds. |
| T5 | GAP detected: capability без workflow | `job._knowledge_readiness="GAP"`, gaps contain description. Execution proceeds. |
| T6 | CANDIDATE_ONLY: кандидат без production workflow | `job._knowledge_readiness="CANDIDATE_ONLY"`. Execution proceeds. |
| T7 | Conflicting evidence | Gaps contain CONFLICTING_KNOWLEDGE. Execution proceeds. |
| T8 | KnowledgeCore exception | Caught silently. `job._knowledge_readiness=None`. Execution proceeds. No regression. |
| T9 | _plan_result_to_query unknown capability | Returns None. No query. `job._knowledge_readiness=None`. |
| T10 | ConversationAgent multi-turn with knowledge | Each turn gets independent knowledge query. Context update unaffected. |
| T11 | Persistence compatibility: old Jobs loaded | `job._knowledge_readiness` not in old ExecutionRecord. On load — None. No error. |
| T12 | Multi-step chain (_execute_chain) | Knowledge pre-flight per step? TBD — likely per-step in chain step execution. |
| T13 | No regression M1–M26: full test suite | All existing tests pass (knowledge_core=None default). |

---

## 13. Explicit Non-Goals (S0.5)

1. **НЕ чинить** `_validate_capability_nodes_background` (dead code, wrong signature).
2. **НЕ чинить** `_calculate_validation_score` (always 0 due to empty `_validated_nodes`).
3. **НЕ менять** Planner behavior (knowledge doesn't influence capability/workflow selection).
4. **НЕ менять** PlanContext, ExecutionRecord, JobState, ExperienceStore format (frozen M25/M26).
5. **НЕ добавлять** new persistence layer.
6. **НЕ добавлять** confidence scoring (existing ClaimStatus sufficient).
7. **НЕ добавлять** user_confirmed (S3 scope).
8. **НЕ добавлять** explain contract (S2 scope).
9. **НЕ добавлять** CostTier (S1 scope).
10. **НЕ добавлять** usage/limitation claims (S4 scope).
11. **НЕ делать** Knowledge blocking (knowledge absence ≠ capability absence).
12. **НЕ вызывать** RuntimeValidator (self-test = separate milestone).
13. **НЕ менять** WorkflowRegistry, CapabilityRegistry, or any registry.
14. **НЕ менять** WorkflowEngine.execute or Verifier.

---

## 14. Open Architectural Questions

### Q1. Where in ConversationAgent._execute_chain?

Для multi-step chains: knowledge pre-flight per step или per chain?

**Вариант A:** Per step — каждый chain step получает свой knowledge query (точнее, но больше queries).
**Вариант B:** Per chain — один query на всю chain (меньше queries, но менее точно).

**Рекомендация:** Per step (consistent with single-step path). Chain steps вызывают `self.prepare()` → knowledge query между prepare и engine.execute. Impact: knowledge metadata на каждом chain step Job.

### Q2. Should knowledge gaps trigger research requests automatically?

KnowledgeResponse содержит `research_requests`. Should S0.5:
- (a) log them on Job metadata (advisory only), or
- (b) trigger automatic research (LocalResearchProvider)?

**Рекомендация:** (a) advisory only. Auto-research requires runtime access and is a separate concern.

### Q3. Should knowledge readiness appear in SSE events?

`GET /events` stream включает `status`, `result`, `error`. Should knowledge readiness be in the result event?

**Рекомендация:** Deferred. S0.5 adds metadata to Job; UI exposure is a separate concern.

### Q4. KnowledgeCore lifecycle: who owns initialization?

Currently KnowledgeCore requires `capability_registry` and `workflow_registry` in __init__. Should Agent:
- (a) construct KnowledgeCore internally, or
- (b) receive it as injection (like `knowledge_core` param)?

**Рекомендация:** (b) injection. KnowledgeCore is a dependency, Agent shouldn't own its lifecycle. The caller (UI, CLI, test) constructs KnowledgeCore with required registries and passes it to Agent.

### Q5. ConversationAgent.__init__ — how does knowledge_core reach Agent?

ConversationAgent uses `*args, **kwargs` → `super().__init__(**kwargs)`. Adding `knowledge_core` to `Agent.__init__` means it can be passed via kwargs. But ConversationAgent has explicit params like `feedback_store`, `experience_store`. Should `knowledge_core` be:
- (a) explicit param on ConversationAgent.__init__, or
- (b) forwarded via **kwargs to Agent?

**Рекомендация:** (a) explicit param. Consistent with `feedback_store` and `experience_store` pattern. Avoids silent kwarg forwarding.

---

## 15. Implementation Checklist (for the next milestone, NOT now)

Чек-лист для будущей реализации (после approval):

- [ ] `app/agent.py`: добавить `knowledge_core=None` param в `Agent.__init__`, сохранить как `self.knowledge_core`.
- [ ] `app/agent.py`: добавить `_plan_result_to_query(self, result, manifest)` method.
- [ ] `app/agent.py`: добавить `_knowledge_preflight(self, capability, manifest)` method.
- [ ] `app/agent.py`: в `run()` — вызов `_knowledge_preflight` после `prepare()`, присвоение metadata на Job после `engine.execute()`.
- [ ] `app/conversation.py`: добавить `knowledge_core=None` explicit param в `ConversationAgent.__init__`, forward to `super().__init__()`.
- [ ] `app/conversation.py`: в `turn()` — knowledge pre-flight (same pattern as Agent.run).
- [ ] `app/conversation.py`: в `_execute_chain_step()` — knowledge pre-flight per step.
- [ ] `app/engine/job.py`: добавить `_knowledge_readiness: str | None = None` и `_knowledge_gaps: list[str] | None = None`.
- [ ] `tests/test_knowledge_s05.py`: test matrix §12, T1-T13.
- [ ] Regression: `python -m pytest tests/` — zero failures.
- [ ] Documentation: update `tasks/ACTIVE.md`, `tasks/COMPLETED.md`, `engineering/HANDOFF.md`.

---

## 16. Minimal Required Changes Summary

| Файл | Изменение | Type |
|---|---|---|
| `app/agent.py` | `__init__` + `knowledge_core` param | Additive, default=None |
| `app/agent.py` | `_plan_result_to_query()` | New private method (~20 lines) |
| `app/agent.py` | `_knowledge_preflight()` | New private method (~15 lines) |
| `app/agent.py` | `run()` — 2 lines (call preflight, attach to job) | Insertion |
| `app/conversation.py` | `__init__` + `knowledge_core` explicit param | Additive, default=None |
| `app/conversation.py` | `turn()` — knowledge pre-flight | Insertion (~5 lines) |
| `app/conversation.py` | `_execute_chain_step()` — knowledge pre-flight | Insertion (~5 lines) |
| `app/engine/job.py` | 2 optional fields | Additive, default=None |
| `tests/test_knowledge_s05.py` | New test file | New, ~200 lines |

**Total: ~50-60 lines of production code, ~200 lines of tests.** Zero changes to existing methods' signatures or behavior. Zero changes to frozen M25/M26 contracts.

---

## 17. Risk Assessment

| Риск | Вероятность | Impact | Mitigation |
|---|---|---|---|
| KnowledgeCore.query() slow (many schemas) | Низкая (in-memory, ~959 schemas) | Execution delay ~ms | Advisory only; could add timeout |
| KnowledgeCore not initialized (no refresh) | Средняя (first run) | UNKNOWN readiness, non-blocking | Expected behavior; document |
| Breaking existing tests | Низкая (default=None) | Test failure | Full regression before merge |
| Scope creep to RuntimeValidator | Средняя | Delay | Explicit non-goal, separate milestone |
| Confusion between knowledge readiness and compatibility | Средняя | Design error | Clear documentation: knowledge ≠ compatibility |

---

## 18. Recommendation to Architecture

S0.5 — минимальный, безопасный, backward-compatible bridge между Knowledge Core и Agent execution path. Он:

1. **Замыкает observability gap** — knowledge readiness/gaps видны на Job.
2. **Не блокирует execution** — knowledge absence ≠ capability absence.
3. **Не трогает frozen контракты** — additive metadata only.
4. **Не смешивает concerns** — knowledge pre-flight ≠ runtime validation ≠ validation score.
5. **Подготавливает почву** для S1-S6 (explain, user_confirmed, usage/limitation, cost-tier, external sources).

**Альтернатива (если S0.5 считается premature):** DEFERRED до тех пор, пока RuntimeValidator hook не будет отремонтирован (S0.6). Knowledge pre-flight без runtime validation = knowledge query использует только schema/claims, не runtime evidence. Это всё ещё полезно (UNDERSTAND/VERIFY stages), но менее мощно. Решение за автором.

---

**S0.5 DESIGN STATUS: READY**

Все forensic findings подтверждены. Контракт определён. Backward compatibility доказана. Non-goals explicit. Frozen контракты не тронуты. Test matrix составлена.

**IMPLEMENTATION APPROVAL: NOT REQUESTED**

Production code не написан. Tests не написаны. Commit не выполнен.

**STOP / WAIT FOR APPROVAL.**
