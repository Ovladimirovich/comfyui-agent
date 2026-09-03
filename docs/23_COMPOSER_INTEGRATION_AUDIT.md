# Composer Integration Audit

**Date:** 2026-09-03
**Status:** AUDIT COMPLETE
**Goal:** Define minimal integration of Composer into ConversationAgent

---

## 1. Current Flow Analysis

### 1.1 ConversationAgent.turn() Flow

```
turn(session_id, capability|request, params, assets, ...)
    │
    ├─ M18 Multi-step detection (lines 155-173)
    │   └─ TaskDecomposer.decompose(request) → subtasks
    │       └─ if len(subtasks) > 1 → _execute_chain()
    │
    └─ Single-step path (lines 176-350)
        └─ Planner.plan() → capability + params
            └─ Agent.prepare() → manifest + plan + provider
                └─ WorkflowEngine.execute() → Job
```

### 1.2 TaskDecomposer Analysis

**Location:** `app/planner/decomposer.py`
**Method:** keyword-based splitting by conjunctions
**Limitations:**
- Doesn't check capability compatibility
- Doesn't use CapabilityGraph
- Can produce invalid chains (e.g., audio → image)
- No validation of input/output contracts

### 1.3 Composer Analysis

**Location:** `app/planner/composer.py`
**Method:** graph-based composition using CapabilityGraph
**Capabilities:**
- Validates composability via media type compatibility
- Finds optimal paths through capability graph
- Returns structured CompositionResult with alternatives
- Supports max chain length constraint

> **Важно (уточнение ответственности, AD-41/M19-STATUS):**
> `CapabilityGraph` — это **knowledge/constraint layer** (знание о composability), которым пользуется Composer внутри себя (`self._graph`), а не отдельный следующий execution-stage после Composer.
>
> Реальный control flow:
> ```
> Planner → Composer ↕ CapabilityGraph → Composition → ExecutionChain
> ```
> Composer оркестрирует построение композиции, обращаясь к CapabilityGraph как к справочнику. Код уже соответствует (Composer владеет CapabilityGraph как полем `self._graph`).

---

## 2. Integration Point

### 2.1 Minimal Integration (Recommended)

**Insert Composer as validation/enhancement layer after TaskDecomposer:**

```python
# In ConversationAgent.turn(), after TaskDecomposer:
from app.planner.decomposer import TaskDecomposer
from app.planner.composer import Composer

decomposer = TaskDecomposer()
subtasks = decomposer.decompose(request)

if len(subtasks) > 1:
    # NEW: Validate and enhance via Composer
    if self.composer is not None:
        # Extract target capability from last subtask
        target = subtasks[-1].capability
        composition = self.composer.compose(
            target_capability=target,
            params=params or {},
            available_types=set(),  # Could be enhanced with asset detection
        )
        if composition.success:
            subtasks = composition.chain  # Use Composer's validated chain
    
    return self._execute_chain(...)
```

### 2.2 Integration Location

**File:** `app/conversation.py`
**Lines:** ~155-173 (M18 multi-step section)
**Changes:** Add Composer validation after TaskDecomposer

---

## 3. Required Changes

### 3.1 New Files
None (Composer, CapabilityGraph, CompositionResult already exist)

### 3.2 Modified Files

| File | Change | Lines |
|------|--------|-------|
| `app/conversation.py` | Add Composer validation in multi-step path | ~155-173 |
| `app/conversation.py.__init__` | Add `composer` parameter | ~85-95 |

### 3.3 New Parameters

```python
class ConversationAgent(Agent):
    def __init__(
        self,
        *args,
        session_manager: Optional[SessionManager] = None,
        adaptive_planner_enabled: bool = True,
        composer: Optional[Composer] = None,  # NEW
        **kwargs,
    ) -> None:
```

---

## 4. Risks and Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| Composer produces different chain than TaskDecomposer | LOW | Use Composer as enhancement, not replacement |
| Composer returns failure for valid requests | LOW | Graceful fallback to TaskDecomposer output |
| Performance impact (graph traversal) | LOW | Graph is small (9 nodes), cache results |
| Regression in existing M18 tests | LOW | Composer is optional, TaskDecomposer remains default |

---

## 5. Invariant Verification

| Invariant | Status | Notes |
|-----------|--------|-------|
| M1-M12 execution path unchanged | ✅ | Only M18 path modified |
| ExecutionChain remains sole execution mechanism | ✅ | Composer doesn't execute |
| WorkflowEngine remains sole execution engine | ✅ | No changes to engine |
| CapabilityRegistry remains source of truth | ✅ | Composer reads from registry |
| Composer has no direct ComfyUI access | ✅ | Composer only plans, doesn't execute |
| Single-step path unaffected | ✅ | Changes only in multi-step branch |
| No second Planner | ✅ | Composer is not a Planner |
| No second execution engine | ✅ | No new execution mechanisms |

---

## 6. Implementation Plan

### Step 1: Add Composer parameter to ConversationAgent.__init__
- Add `composer: Optional[Composer] = None`
- Store as `self.composer`

### Step 2: Integrate Composer in multi-step path
- After `TaskDecomposer.decompose()`, check if `self.composer` is set
- If yes, use Composer to validate/enhance the chain
- Fall back to TaskDecomposer output if Composer fails

### Step 3: Update ConversationAgent factory/constructor calls
- Pass `composer=` where ConversationAgent is instantiated

### Step 4: Add tests
- Test Composer integration with ConversationAgent
- Test graceful fallback
- Test regression of existing M18 tests

---

## 6. Conclusion

**Integration is feasible with minimal changes:**
- 1 new parameter in `__init__`
- ~10 lines of code in `turn()`
- No changes to M1-M12
- No new execution paths
- Backward compatible (Composer is optional)

**Next step:** Implement minimal integration (ЭТАП 2).

---

*Audit document. Awaiting approval for implementation.*