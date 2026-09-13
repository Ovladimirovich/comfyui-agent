# PRODUCTION ARCHITECTURE AUDIT REPORT
## Execution / Provider / Backend / Job / Asset / SSE

**Date:** 2026-09-09  
**Scope:** Read-only forensic trace of production execution path  
**Status:** BLOCKED — 1 HIGH severity finding

---

## Executive Verdict

**ARCHITECTURE AUDIT BLOCKED**

One HIGH severity finding requires resolution:
- **Finding A:** Asset created BEFORE verification (violates stated invariant)

All other invariants verified. No CRITICAL findings.

---

## Findings

### FINDING A — HIGH (B): Asset Created Before Verification

**Location:** `app/engine/engine.py:347-387`

**Issue:**
The comment on line 347 states:
> выхлоп → Asset с lineage (только ПОСЛЕ успешной проверки контракта, point 8)

But the code creates Asset BEFORE verification:

```python
# Line 370: Asset created INSIDE try block
asset = self.store.ingest(...)
created[name] = asset

# Line 383: Verification happens AFTER asset creation
Verifier(self.store).verify(manifest, created)

# Line 386: On failure, only Job state is set to FAILED
job.state = JobState.FAILED
# NO cleanup of orphaned asset!
```

**Impact:**
- If verification fails, Asset remains in store with no Job reference
- Violates the invariant: "Asset only after successful verification"
- Creates orphaned assets that consume storage
- UI may see Asset without corresponding successful Job

**Expected behavior:**
```python
# Verify first (no side effects)
Verifier(self.store).verify(manifest, executed_outputs)
# Then create assets
for name, spec in manifest.outputs.items():
    asset = self.store.ingest(...)
    created[name] = asset
```

**Classification:** HIGH (B)
- Real semantic gap in production code
- Violates stated invariant
- Creates orphaned resources

---

### FINDING B — MEDIUM (C): Fallback Path in _bind_models

**Location:** `app/engine/engine.py:184-195`

**Issue:**
The fallback path in `_bind_models` still uses heuristic selection:
```python
if self.model_registry is not None:
    chosen = self.model_registry.resolve(provider.backend_id, "checkpoint")
else:
    checkpoints = provider.discover_checkpoints()
    chosen = checkpoints[0] if checkpoints else None
```

**Impact:**
- This path is ONLY used when `plan.model_bindings` is empty
- After AD-MODEL-BINDING-001 migration, production manifests use `model_requirements`
- The fallback is defensive coding for legacy/test paths
- NOT a production issue if Migration is complete

**Classification:** MEDIUM (C)
- Technical debt, not active bug
- Acceptable as fallback with explicit comment

---

### FINDING C — ACCEPTED (D): ConversationAgent Modifies JobState

**Location:** `app/conversation.py:249, 464`

**Issue:**
ConversationAgent sets `job.state = JobState.FAILED` (semantic verification failure) and `job.state = JobState.CANCELLED`.

**Impact:**
- This is INTENTIONAL behavior for:
  1. Semantic verification (M14)
  2. User cancellation (D-5A)
- JobState is mutable by design (not frozen)
- Multiple owners is acceptable for different failure modes

**Classification:** ACCEPTED (D)
- Already documented behavior
- No action required

---

## Verified Invariants

| # | Invariant | Status |
|---|-----------|--------|
| 1 | ExecutionPlan has all required fields | ✅ |
| 2 | Provider does not select workflow/model | ✅ |
| 3 | Job lifecycle is standard (QUEUED→RUNNING→terminal) | ✅ |
| 4 | Single JobState.SUCCESS assignment in execute() | ✅ |
| 5 | SSE terminal events defined | ✅ |
| 6 | Conversation/Execution boundary properly gated | ✅ |
| 7 | AD-18 preserved (cache ≠ live) | ✅ |
| 8 | ModelRegistry does not redefine semantics | ✅ |
| 9 | Deterministic selection (name sort fallback) | ✅ |
| 10 | Legacy manifests auto-migrated | ✅ |
| 11 | No hidden model resolvers in production path | ✅ |
| 12 | Provider ≠ Backend boundary respected | ✅ |

---

## Component Trace

### ExecutionPlan → Provider
- ExecutionPlan contains: capability, workflow_id, version, params, asset_bindings, model_bindings
- Provider receives: manifest, plan, provider instance
- Provider does NOT select workflow/model/capability
- Provider does NOT re-evaluate compatibility
- **OK**

### Provider → Backend
- Provider methods: cancel, discover_checkpoints, execute, get_job, upload_asset, view
- Provider is transport layer only
- Backend (ComfyUI) receives concrete prompt with concrete model name
- Backend does NOT interpret ModelKind
- **OK**

### ExecutionPlan Completeness
- workflow identity/version: ✅ (workflow_id, version)
- capability: ✅
- resolved model identity: ✅ (model_bindings)
- backend identity: ✅ (backend field)
- input assets: ✅ (asset_bindings)
- parameters: ✅ (params)
- **OK**

### Job Lifecycle
- QUEUED → RUNNING: ✅ (on POST /prompt)
- RUNNING → SUCCESS: ✅ (after verification)
- RUNNING → FAILED: ✅ (on exception)
- RUNNING → CANCELLED: ✅ (on user request)
- No double terminal transitions: ✅
- **OK**

### Verification Boundary
- Asset creation: INSIDE try block (BEFORE verification) ⚠️
- Verification: AFTER asset creation
- On failure: job.state = FAILED, but asset already in store
- **ISSUE: Finding A**

### Asset / AssetStore
- Creation: via `store.ingest()` inside try block
- No cleanup on verification failure
- Delete method exists but not called on failure
- **ISSUE: Finding A**

### SSE / UI
- Terminal events: ("result", "error")
- Event ordering: start → status → progress → result/error
- Session isolation: ✅ (per session_id)
- **OK**

### Conversation → Execution
- Execution gated through `ConversationAgent.turn()`
- Retry logic present (M13)
- Cancellation propagation present (D-5A)
- **OK**

---

## Test Coverage

```
111 passed in 19.57s
0 failed
```

**New tests:** `tests/test_model_binding_ad001.py` (23 tests)
- Contract validation (10 tests)
- Resolution determinism (5 tests)
- Compatibility with typed requirements (4 tests)
- Legacy migration (2 tests)
- ExecutionPlan bindings (2 tests)

**Updated tests:** `tests/test_extended_discovery.py::test_step7_existing_required_models_semantics`
- Now verifies migration to kind requirement

---

## Recommended Fix for Finding A

**Option 1: Move verification before asset creation (RECOMMENDED)**
```python
# Verify first (no side effects)
Verifier(self.store).verify(manifest, executed_outputs)
# Then create assets
for name, spec in manifest.outputs.items():
    asset = self.store.ingest(...)
    created[name] = asset
```

**Option 2: Add cleanup on verification failure**
```python
except Exception:
    job.state = JobState.FAILED
    # Cleanup orphaned assets
    for asset in created.values():
        self.store.delete(asset.id)
    raise
```

**Recommended:** Option 1 (verify first, then create)

---

## Git Diff Summary

```
app/registry/workflow.py     +125 lines (ModelRequirement, Workflow fields)
app/registry/compatibility.py +30 lines (typed requirements support)
app/engine/plan.py            +1 line (model_bindings field)
app/engine/engine.py          +20 lines (plan-aware _bind_models)
app/agent.py                  +50 lines (_resolve_model_requirements, prepare update)
tests/test_model_binding_ad001.py +240 lines (new)
tests/test_extended_discovery.py  updated
workflows/*/manifest.json     5 files migrated
docs/AD-MODEL-BINDING-001.md  created
```

---

## Conclusion

**STATUS: ARCHITECTURE AUDIT BLOCKED**

One HIGH severity finding (Finding A) requires resolution before acceptance.

**Next step:** Fix Asset creation timing or escalate to architectural decision.

**NO CODE CHANGES MADE IN THIS AUDIT.**
