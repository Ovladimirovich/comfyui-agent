# S1 Design — CostTier / Free-First Routing

> **Статус:** DESIGN ONLY — не реализация.
> **Дата:** 2026-09-13.
> **Base:** `docs/ECOSYSTEM_FIRST_ARCHITECTURE.md` (APPROVED), `docs/ECOSYSTEM_FIRST_S0_5_DESIGN.md` (APPROVED/IMPLEMENTED).
> **Ограничения:** production code NO, tests NO, UI NO, commit NO.

---

## 1. Forensic Audit — Current State

### 1.1 Cost/pricing data in codebase

| Место | Наличие cost-данных |
|---|---|
| `BackendSpec` (backends.py:20-27) | **Нет.** Поля: backend_id, base_url, kind, priority, capabilities, disabled, description |
| `Workflow` (workflow.py:130-158) | **Нет.** 22 поля, ни одного cost-related |
| `_select_manifest` (agent.py:347-400) | **Нет.** Ranking: validation_score → priority → min_vram_gb → id → version |
| `BackendCatalog.choose` (backends.py:49-82) | **Нет.** Eligibility: not disabled + capability. Ranking: priority (+ VRAM probe) |
| `ModelInfo` (model.py) | **Нет.** Поля: name, backend_id, kind, path |
| Manifest JSON files (9 штук) | **Нет.** Ни одного cost/free/paid поля |
| `app/` Python grep `cost\|price\|free\|paid\|trial` | **Нет бизнес-совпадений.** Только `free_memory` (VRAM diagnostics) в comfy_cli_adapter.py |

**Вывод:** в коде нет ни одного механизма для различения free/paid ресурсов. Политика «PAID не запускается автоматически» невыразима.

### 1.2 Existing ranking/filter mechanisms

| Механизм | Где | Что делает |
|---|---|---|
| `WorkflowStatus` filter | `_select_manifest` | Отбрасывает DECLARED_ONLY, UNKNOWN, UNAVAILABLE. Оставляет только AVAILABLE. |
| `_calculate_validation_score` | `_select_manifest` ranking | Score по validated nodes (currently always 0). |
| `priority` | `_select_manifest` + `BackendCatalog.choose` | Descending sort (higher = preferred). |
| `min_vram_gb` | `_select_manifest` ranking | Ascending sort (lower VRAM = preferred, ties). |
| `capabilities` | `BackendCatalog.choose` | Capability filter (empty = all). |
| `disabled` | `BackendCatalog.choose` | Hard exclude. |

CostTier будет новым критерием — filter + ranking.

### 1.3 Architectural constraints

- **PROJECT_SPEC §5 / AD-18:** UNKNOWN ≠ AVAILABLE. Analogous pattern for UNKNOWN ≠ FREE.
- **ECOSYSTEM §15:** Frozen M25/M26 contracts: PlanContext, ExecutionRecord, JobState, ExperienceStore format. CostTier не затрагивает эти контракты.
- **ECOSYSTEM §11:** Free/local/cloud — варианты, не иерархия. PAID не запускается автоматически.
- **AD-29:** Provider ≠ Backend. CostTier живёт на уровне backend/manifest, не provider.

---

## 2. Problem Statement

Агент не различает бесплатные и платные ресурсы. При выборе workflow или backend агент может выбрать платный cloud backend или workflow с платной зависимостью, не информируя пользователя.

**Требования (из ECOSYSTEM §11):**
1. Различать FREE / TRIAL / PAID / UNKNOWN.
2. PAID не запускается автоматически (без явного подтверждения пользователя).
3. UNKNOWN ≠ FREE (аналогия с AD-18).
4. Free/local/cloud — варианты, не иерархия.
5. Дополнительный критерий ranking (не hard-gate, кроме PAID).

---

## 3. S1 Scope

### В scope

1. `CostTier` enum: `FREE`, `TRIAL`, `PAID`, `UNKNOWN`.
2. Optional `cost_tier` field on `BackendSpec` (default UNKNOWN).
3. Optional `cost_tier` field on `Workflow` manifest (default: not set → inherit from backend).
4. Filter in `_select_manifest`: exclude PAID unless explicitly allowed.
5. Filter in `BackendCatalog.choose`: exclude PAID unless explicitly allowed.
6. Ranking bonus: FREE > TRIAL > UNKNOWN > PAID (when PAID is allowed).
7. Integration with S0.5: knowledge preflight remains unchanged (advisory).
8. Tests: filter, ranking, backward compatibility.

### НЕ в scope (explicit non-goals)

- CostTier on `ModelInfo` — deferred (models inherit from backend/manifest).
- CostTier on `ExperienceStore` / `ExecutionRecord` — frozen M25/M26.
- Billing integration — N/A (ECOSYSTEM §11).
- Marketplace/hosting — N/A.
- UI for cost display — deferred.
- PAID user confirmation flow — deferred (S1 marks PAID as excluded; confirmation is a UI/conversation concern).
- Changes to PlanContext, ExecutionRecord, JobState — frozen.

---

## 4. Proposed Contract

### 4.1 CostTier enum

```python
class CostTier(str, Enum):
    FREE = "FREE"
    TRIAL = "TRIAL"
    PAID = "PAID"
    UNKNOWN = "UNKNOWN"
```

**Placement:** `app/registry/cost.py` (new file, ~15 lines).

**Design rationale:**
- `str` enum: JSON-serializable, readable in logs/manifests.
- `UNKNOWN` default: same pattern as AD-18 (UNKNOWN ≠ FREE, UNKNOWN ≠ AVAILABLE).
- `TRIAL`: free-tier with limits (e.g. rate-limited cloud, limited duration). Separate from FREE because policy may differ.

### 4.2 BackendSpec — cost_tier field

```python
@dataclass
class BackendSpec:
    backend_id: str
    base_url: str
    kind: str = "remote_comfyui"
    priority: int = 0
    capabilities: set[str] = field(default_factory=set)
    disabled: bool = False
    description: str = ""
    cost_tier: CostTier = CostTier.UNKNOWN  # NEW
```

**Default = UNKNOWN.** Existing BackendSpec instances (tests, from_env) don't set cost_tier → UNKNOWN.

**Semantics:**
- `FREE`: local ComfyUI, free cloud tier, open-source hosted.
- `TRIAL`: free-tier with rate limits, limited duration, limited VRAM.
- `PAID`: requires payment/subscription/API key with billing.
- `UNKNOWN`: cost not determined. Treated as NOT FREE for auto-selection.

### 4.3 Workflow — cost_tier field

```python
@dataclass
class Workflow:
    ...
    cost_tier: Optional[CostTier] = None  # NEW, optional override
```

**Default = None** (not set → inherit from backend).

**Semantics:**
- `None`: workflow cost is determined by backend cost_tier.
- `FREE`: workflow is free regardless of backend (e.g. local-only workflow).
- `TRIAL`: workflow is trial-tier.
- `PAID`: workflow requires payment (e.g. uses paid external API like Sonilo).
- Override rule: **manifest cost_tier takes precedence over backend cost_tier** when set.

### 4.4 Manifest JSON — cost_tier field

```json
{
  "id": "pollinations_image",
  "cost_tier": "FREE",
  ...
}
```

**Optional.** Absent = inherit from backend. Valid values: `"FREE"`, `"TRIAL"`, `"PAID"`, `"UNKNOWN"`.

### 4.5 Conflict Resolution

When workflow cost_tier ≠ backend cost_tier:

| Backend | Workflow | Effective cost_tier | Rationale |
|---|---|---|---|
| FREE | None | FREE | Inherit |
| FREE | FREE | FREE | Consistent |
| FREE | PAID | **PAID** | Workflow declares it needs payment (e.g. external API) |
| PAID | None | PAID | Inherit |
| PAID | FREE | **FREE** | Workflow overrides — it's free even on paid backend |
| UNKNOWN | None | UNKNOWN | Inherit |
| UNKNOWN | PAID | PAID | Workflow is explicit |
| UNKNOWN | FREE | FREE | Workflow is explicit |

**Rule:** workflow `cost_tier` overrides backend `cost_tier` when set. This allows a free workflow to run on a paid backend (e.g. local workflow on cloud GPU) and a paid workflow to be flagged even on a free backend (e.g. Sonilo API dependency).

---

## 5. Guard Policy

### 5.1 Auto-selection (Agent.generate, ConversationAgent.turn)

**Rule:** Auto-selection (no explicit user confirmation) excludes PAID and UNKNOWN.

| CostTier | Auto-selection allowed? |
|---|---|
| FREE | ✅ Yes |
| TRIAL | ✅ Yes (zero current cost to user; no auto-escalation to PAID) |
| PAID | ❌ No — excluded from candidates |
| UNKNOWN | ❌ No — excluded from candidates |

**Rationale:**
- PAID: user should explicitly opt in (future: confirmation flow).
- UNKNOWN: cannot assume free (UNKNOWN ≠ FREE, same as AD-18).
- TRIAL: allowed by default — zero current cost, no auto-escalation. If trial requires credit card / auto-converts to PAID → user should declare it as PAID, not TRIAL.

> **Оговорка (approved 2026-09-13).** `TRIAL` = нулевая текущая стоимость для пользователя, без автоматического перехода в платный режим. Trial с required credit card / auto-escalation → declare as PAID, not TRIAL.

> **Оговорка (approved 2026-09-13).** Ranking `FREE > TRIAL > UNKNOWN > PAID` применяется ПОСЛЕ eligibility filter. Главный контракт: **filter → ranking** (не наоборот). UNKNOWN/PAID исключаются ДО ranking; ranking有意义 только среди допущенных (FREE vs TRIAL).

### 5.2 Explicit override

When user explicitly specifies `workflow` or `backend` (not auto-selected), cost_tier is advisory only (logged, not blocking). This preserves the ability to use paid resources when the user explicitly chooses.

### 5.3 Effect on _select_manifest

After compatibility filter (AVAILABLE only), add cost_tier filter:

```python
# Current:
confirmed = [c for c in candidates if c.status == AVAILABLE]

# S1 addition:
confirmed = [c for c in confirmed if _cost_allowed(c, allow_paid=allow_paid)]
```

Where `_cost_allowed` checks the effective cost_tier (workflow override → backend → UNKNOWN).

### 5.4 Effect on BackendCatalog.choose

After capability + disabled filter, add cost_tier filter:

```python
# Current:
eligible = [b for b in self.backends if not b.disabled and capability_ok]

# S1 addition:
eligible = [b for b in eligible if _backend_cost_allowed(b, allow_paid=allow_paid)]
```

---

## 6. Integration Point

### 6.1 Where in the call graph

```text
Agent.generate(request)
  │
  ├─ planner.plan(request) → PlanResult{capability, params}
  │
  ├─ Agent.run(capability, params)
  │    ├─ Agent.prepare(capability, params)
  │    │    ├─ BackendCatalog.choose(capability, registry, probe)
  │    │    │    └─ [S1] cost_tier filter on backends
  │    │    ├─ _discover_facts(client, backend_id)
  │    │    ├─ _select_manifest(capability, runtime, models, custom_nodes)
  │    │    │    └─ [S1] cost_tier filter on workflows
  │    │    └─ ExecutionPlan(...)
  │    │
  │    ├─ _knowledge_preflight(capability, manifest)  [S0.5, unchanged]
  │    └─ engine.execute(manifest, plan, provider) → Job
  │
  └─ return Job
```

**Two integration points:**
1. `BackendCatalog.choose` — backend-level cost filter.
2. `_select_manifest` — workflow-level cost filter.

Both are **filter + ranking**, not new architecture.

### 6.2 How cost_tier is resolved

```python
def _effective_cost_tier(workflow: Workflow, backend: BackendSpec) -> CostTier:
    """Resolve effective cost_tier: workflow override > backend > UNKNOWN."""
    if workflow.cost_tier is not None:
        return workflow.cost_tier
    return backend.cost_tier  # default UNKNOWN
```

### 6.3 How allow_paid is determined

```python
# Agent.run / Agent.generate:
allow_paid = False  # default: auto-selection excludes PAID/UNKNOWN

# If user explicitly specified workflow_id or backend_id:
# → allow_paid = True (advisory only, not blocking)
```

**S1 implementation:** `allow_paid` is always `False` for auto-selection. Explicit override (user specifies workflow) — deferred to future UI/conversation layer. S1 only implements the filter for auto-selection.

---

## 7. Ranking Impact

When PAID is allowed (explicit override), or for cost-aware ranking among FREE/TRIAL candidates:

| CostTier | Ranking score (higher = better) |
|---|---|
| FREE | 3 |
| TRIAL | 2 |
| UNKNOWN | 1 |
| PAID | 0 |

**Integration into _select_manifest ranking tuple:**

```python
# Current:
key = (-validation_score, -priority, min_vram_gb, id, version)

# S1:
key = (-validation_score, -cost_score, -priority, min_vram_gb, id, version)
```

Where `cost_score = _COST_RANKING[_effective_cost_tier(workflow, backend)]`.

This ensures FREE workflows rank above TRIAL, TRIAL above UNKNOWN, etc. — as a **soft preference**, not a hard gate.

---

## 8. Backward Compatibility

| Сценарий | Поведение |
|---|---|
| Existing `BackendSpec` (no cost_tier) | `cost_tier` defaults to `CostTier.UNKNOWN` → excluded from auto-selection (UNKNOWN ≠ FREE) |
| Existing `Workflow` (no cost_tier in manifest) | `cost_tier` defaults to `None` → inherits from backend |
| Existing manifest JSON (no `cost_tier` field) | Parsed as `cost_tier=None` → inherits from backend |
| `BackendCatalog.from_env()` (COMFY_BACKENDS JSON) | Backends without `cost_tier` → UNKNOWN |
| All existing workflows are local (backend=local_comfyui) | Backend cost_tier=UNKNOWN by default → excluded from auto-selection |

**CRITICAL BACKWARD COMPATIBILITY ISSUE:**

All existing backends default to UNKNOWN → all existing workflows would be excluded from auto-selection (UNKNOWN ≠ FREE). This breaks all existing functionality.

**Resolution:** `from_env()` and default backend creation must set `cost_tier=CostTier.FREE` for `local_comfyui` kind. Local ComfyUI is inherently free (no billing). Remote/cloud backends default to UNKNOWN (cost not determined).

```python
# In BackendCatalog.from_env():
kind = "remote_comfyui" if ... else "local_comfyui"
cost = CostTier.FREE if kind == "local_comfyui" else CostTier.UNKNOWN
```

Also in the default fallback:
```python
BackendSpec(
    backend_id="local_comfyui",
    base_url="http://127.0.0.1:8188",
    kind="local_comfyui",
    cost_tier=CostTier.FREE,  # local = free
)
```

Existing manifests that use `backend: "local_comfyui"` → effective cost_tier = FREE (from backend) → allowed in auto-selection. **No regression.**

Remote backends (COMFY_REMOTE_URL) → cost_tier=UNKNOWN → excluded from auto-selection until user sets cost_tier. This is correct: remote cost is unknown until declared.

---

## 9. Persistence Impact

| Контракт | Impact |
|---|---|
| `BackendSpec` (in-memory, from_env) | New field, default. Not persisted directly. |
| `Workflow` (loaded from manifest.json) | New optional field parsed from JSON. Existing manifests without field → None. |
| `ExecutionRecord` (JSONL) | **No change.** CostTier not recorded on ExecutionRecord. |
| `Job` | **No change.** CostTier not recorded on Job. |
| `PlanContext` | **No change.** Frozen M25/M26. |
| `ExecutionPlan` | **No change.** |

CostTier is purely selection-time metadata. Not persisted with execution results.

---

## 10. Ecosystem-First Lifecycle Mapping

```text
DISCOVER     — cost_tier not relevant (discovery is about existence)
INSPECT      — cost_tier not relevant (inspection is about capabilities)
UNDERSTAND   — cost_tier not relevant (understanding is about semantics)
SELF-TEST    — cost_tier not relevant (validation is about correctness)
VERIFY       — cost_tier not relevant (verification is about evidence)
EXPLAIN      — FUTURE (S2): explain could include cost info
CO-USE       — [S1] cost_tier filters backends/workflows in selection
REMEMBER     — cost_tier not relevant (memory is about experience)
REUSE        — [S1] cost_tier influences ranking (FREE preferred)
```

S1 affects only CO-USE (selection) and REUSE (ranking). All other stages unchanged.

---

## 11. Free-First Implications

**S1 IS the Free-First implementation.**

- CostTier enum + fields = data model for free-first.
- Guard policy = enforcement of "PAID not auto".
- Ranking bonus = "free-first routing".

**No hidden paid path:**
- Auto-selection excludes PAID and UNKNOWN.
- Only explicit user override (future) can select PAID.
- Knowledge preflight (S0.5) doesn't trigger any cost.
- RuntimeValidator (deferred) doesn't add cost.

---

## 12. Relationship to S0.5

S0.5 knowledge preflight is **unchanged** by S1. KnowledgeCore.query() doesn't know about cost_tier. Knowledge remains advisory about capabilities/readiness, not about cost.

Future: Knowledge preflight could include cost information in its advisory output (e.g. "this workflow is PAID"). Deferred to S2+.

---

## 13. Test Matrix (design only)

| # | Тест | Ожидаемое поведение |
|---|---|---|
| T1 | `CostTier` enum values | FREE, TRIAL, PAID, UNKNOWN. str enum. |
| T2 | `BackendSpec` default cost_tier | UNKNOWN |
| T3 | `BackendSpec(kind="local_comfyui")` via from_env | cost_tier=FREE |
| T4 | `BackendSpec` remote via from_env | cost_tier=UNKNOWN |
| T5 | `Workflow` default cost_tier | None |
| T6 | Manifest JSON without cost_tier → Workflow.cost_tier | None |
| T7 | Manifest JSON with `"cost_tier": "FREE"` → Workflow.cost_tier | CostTier.FREE |
| T8 | Auto-selection: local backend (FREE) + workflow (None) | Effective=FREE → allowed |
| T9 | Auto-selection: remote backend (UNKNOWN) + workflow (None) | Effective=UNKNOWN → excluded |
| T10 | Auto-selection: remote backend (UNKNOWN) + workflow (FREE) | Effective=FREE → allowed |
| T11 | Auto-selection: backend (PAID) + workflow (None) | Effective=PAID → excluded |
| T12 | Auto-selection: backend (FREE) + workflow (PAID) | Effective=PAID → excluded |
| T13 | Ranking: FREE > TRIAL > UNKNOWN among allowed candidates | Correct order |
| T14 | `BackendCatalog.choose` excludes PAID backends | PAID backend not selected |
| T15 | `BackendCatalog.choose` excludes UNKNOWN backends | UNKNOWN backend not selected |
| T16 | `BackendCatalog.choose` allows FREE + TRIAL | Selected |
| T17 | No regression: all existing manifests → cost_tier=None → inherit FREE from local backend | Existing behavior preserved |
| T18 | `from_env` with COMFY_BACKENDS JSON without cost_tier | Backends default to UNKNOWN (remote) or FREE (local) |
| T19 | `_effective_cost_tier` override logic | Workflow override > backend > UNKNOWN |
| T20 | No change to ExecutionRecord persistence | cost_tier not in from_job / to_dict |

---

## 14. Explicit Non-Goals (S1)

1. **НЕ добавлять** cost_tier на `ModelInfo` (deferred).
2. **НЕ добавлять** cost_tier на `ExecutionRecord` / `Job` (frozen).
3. **НЕ добавлять** cost_tier на `PlanContext` (frozen).
4. **НЕ делать** billing integration.
5. **НЕ делать** PAID user confirmation flow (S1 only excludes; confirmation is UI/conversation concern).
6. **НЕ менять** S0.5 knowledge preflight.
7. **НЕ менять** RuntimeValidator / `_calculate_validation_score`.
8. **НЕ менять** Planner behavior.
9. **НЕ делать** UI for cost display.
10. **НЕ менять** manifest JSON files (cost_tier is optional, existing files work without it).

---

## 15. Open Architectural Questions

### Q1. Should PAID require explicit user confirmation per execution, or per session?

**Options:**
- Per execution: every PAID workflow requires fresh confirmation.
- Per session: once user confirms PAID for a session, all subsequent PAID selections are allowed.
- Per backend: user declares backend as "paid-ok" once.

**Recommendation for S1:** Defer. S1 only implements filter (exclude PAID from auto-selection). Confirmation flow is a UI/conversation concern beyond S1 scope.

### Q2. Should TRIAL have its own policy (rate limits, max executions)?

**Recommendation:** Defer. TRIAL is treated as FREE in S1 (allowed in auto-selection). Future: TRIAL-specific limits as a separate extension.

### Q3. Should cost_tier be visible in knowledge preflight (S0.5)?

**Recommendation:** Defer to S2. Knowledge preflight currently doesn't know about cost. Adding cost awareness to KnowledgeQuery is a separate extension.

### Q4. How does cost_tier interact with BackendCatalog.from_env COMFY_BACKENDS JSON?

**Answer:** COMFY_BACKENDS JSON entries can optionally include `"cost_tier": "FREE"` etc. Without it, defaults based on `kind` field (local=FREE, remote=UNKNOWN).

### Q5. Should Agent.run / ConversationAgent.turn accept `allow_paid` parameter?

**Recommendation:** Defer to future (when PAID confirmation flow is designed). S1 only implements the filter logic; the flag is always False for auto-selection.

---

## 16. Implementation Checklist (for the next milestone)

- [ ] `app/registry/cost.py`: new file, `CostTier` enum (~15 lines).
- [ ] `app/registry/backends.py`: add `cost_tier: CostTier = CostTier.UNKNOWN` to `BackendSpec`.
- [ ] `app/registry/backends.py`: update `from_env()` — local_comfyui kind → cost_tier=FREE.
- [ ] `app/registry/backends.py`: update `choose()` — filter by cost_tier (exclude PAID/UNKNOWN for auto).
- [ ] `app/registry/workflow.py`: add `cost_tier: Optional[CostTier] = None` to `Workflow`.
- [ ] `app/registry/workflow.py`: parse `cost_tier` from manifest JSON in `load_workflow()`.
- [ ] `app/agent.py`: add `_effective_cost_tier(workflow, backend)` helper.
- [ ] `app/agent.py`: update `_select_manifest()` — cost_tier filter + ranking.
- [ ] `app/agent.py`: update `prepare()` — pass backend cost_tier context.
- [ ] `app/conversation.py`: no changes (inherits from Agent).
- [ ] `tests/test_cost_tier.py`: test matrix T1-T20.
- [ ] Regression: `python -m pytest tests/` — zero new failures.
- [ ] Documentation: update `tasks/ACTIVE.md`, `engineering/HANDOFF.md`.

---

## 17. Minimal Required Changes Summary

| Файл | Изменение | Lines |
|---|---|---|
| `app/registry/cost.py` | NEW: `CostTier` enum | ~15 |
| `app/registry/backends.py` | `BackendSpec.cost_tier` field + `from_env()` update + `choose()` filter | ~25 |
| `app/registry/workflow.py` | `Workflow.cost_tier` field + `load_workflow()` parse | ~15 |
| `app/agent.py` | `_effective_cost_tier()` + `_select_manifest()` filter/ranking | ~30 |
| `tests/test_cost_tier.py` | NEW: ~20 tests | ~200 |

**Total: ~85 lines production code, ~200 lines tests.** Zero changes to frozen contracts (PlanContext, ExecutionRecord, JobState, ExperienceStore).

---

## 18. Risk Assessment

| Риск | Вероятность | Impact | Mitigation |
|---|---|---|---|
| Existing remote backends excluded (UNKNOWN) | Высокая | Remote workflows stop working in auto-selection | Document: remote backends need explicit cost_tier. from_env can parse it from COMFY_BACKENDS JSON. |
| All local workflows default to FREE | Низкая | None (correct behavior) | Local = free by definition. |
| Cost conflict (backend FREE + workflow PAID) | Низкая | Unexpected exclusion | Override rule: workflow takes precedence. Document. |
| Scope creep to billing | Низкая | Delay | Explicit non-goal. |
| Performance impact | Negligible | None | Simple field comparison, no I/O. |

---

**S1 DESIGN STATUS: READY**

All forensic findings confirmed. Contract defined. Backward compatibility addressed (local=FREE default). Frozen contracts untouched. Test matrix complete.

**IMPLEMENTATION APPROVAL: NOT REQUESTED**

**STOP / WAIT FOR APPROVAL.**
