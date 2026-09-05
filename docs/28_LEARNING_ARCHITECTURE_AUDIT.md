# Learning Architecture Audit

**Date:** 2026-09-04
**Status:** AUDIT ONLY -- no production code changes
**Goal:** Determine owner of learned policy and resolve learning loop conflicts

---

## 1. Current feedback flow

```
User -> POST /api/feedback -> FeedbackStore (JSONL)
                                  |
                    +-------------+-------------+
                    |             |             |
              HistoryAnalytics  RetryPolicy   UI (GET)
              (M16/M19)        (M24)
                    |             |
              AdaptivePlanner  decide()
              plan()           -> ask_user
              -> preferred_params
```

### Who writes feedback

| Component | Writes? | Path |
|-----------|---------|------|
| ComfyUIServer.record_feedback() | YES | POST /api/feedback -> FeedbackStore.record() |
| Everything else | NO | Read-only |

### Who reads feedback

| Component | Method | What it does |
|-----------|--------|-------------|
| HistoryAnalytics._filter_by_feedback() | get_all() | Filters records: rating < 4 -> excluded from preferred params |
| RetryPolicy._check_feedback_after_success() | get_for_attempt() | rating <= 2 -> action="ask_user" |
| ComfyUIServer.get_feedback_history() | get_for_session() | Serves GET endpoint |

---

## 2. Critical findings

### FINDING 1: DEAD CODE -- FeedbackStore never wired in production

**conversation.py lines 218-221:**
```python
planner = AdaptivePlanner(
    history=self.execution_history,
    fallback=self.planner or _default_planner(),
)
# feedback_store is NEVER passed!
```

**agent.py line 91:**
```python
self.retry_policy = retry_policy or RetryPolicy()
# Default has feedback_store=None
```

Both M19 (feedback-weighted params) and M24 (ask_user) are implemented but **never wired** in production. The feedback integration code is dead.

**Impact:**
- AdaptivePlanner always runs without feedback filtering
- RetryPolicy never checks feedback for ask_user
- All M24 tests pass because they explicitly inject feedback_store

### FINDING 2: Duplicate preferred_params algorithm

The "preferred params" aggregation exists in TWO places:

| Location | Lines | Scope |
|----------|-------|-------|
| HistoryAnalytics.preferred_params() | analytics.py:41-77 | Per-capability only |
| AdaptivePlanner._context_aware_preferred_params() | adaptive.py:61-104 | Per-capability AND per-workflow |

The second adds workflow-level filtering (AD-36) that the first lacks. If both were activated, they would return different scoped data for the same concept.

### FINDING 3: O(N^2) feedback scan (latent)

analytics.py line 87:
```python
all_feedback = self.feedback_store.get_all()
```

Called INSIDE a loop over records. For each record, scans ALL JSONL files. Currently dead code, but would be a bottleneck if activated.

### FINDING 4: No persistent learned state

All learning is recomputed from raw history on every call:
- AdaptivePlanner: counts param frequency across successful records
- HistoryAnalytics: aggregates stats
- RetryPolicy: stateless correction rules (hardcoded)

Nothing writes back "learned" preferences to persistent storage.

### FINDING 5: Competing param adjustments (latent)

| Component | When | What it adjusts |
|-----------|------|-----------------|
| AdaptivePlanner | Before execution (planning) | Preferred params as defaults |
| RetryPolicy | After failure (retry) | param_adjustments via CorrectionStrategy |

Neither knows what the other did. Could cause oscillation:
1. AdaptivePlanner: steps=30 (learned from history)
2. Execution fails, RetryPolicy: steps *= 0.7 -> steps=21
3. Next success: AdaptivePlanner learns 25 (not 30)
4. Policy oscillates

### FINDING 6: No feedback UI in built-in HTML

The embedded M9 UI (ui.py lines 203-348) has no feedback submission form. POST /api/feedback exists but the built-in client cannot call it.

---

## 3. Who should own learned policy?

### Option A: AdaptivePlanner as sole owner

```
Feedback
  |
  v
AdaptivePlanner (planning-time learning)
  - Reads: FeedbackStore, ExecutionHistory
  - Writes: preferred params (transient, recomputed)
  - Decides: what params to use BEFORE execution
  |
  v
RetryPolicy (execution-time correction only)
  - NO feedback access
  - Only CorrectionStrategy (hardcoded rules)
  - Adjusts params only on FAILURE
```

**Pros:** Single owner, no conflicts, clear separation
**Cons:** RetryPolicy cannot leverage feedback for decisions

### Option B: Layered learning (recommended)

```
Feedback
  |
  +---> Planning Layer (AdaptivePlanner)
  |       - Reads: FeedbackStore + ExecutionHistory
  |       - Learns: preferred params per capability/workflow
  |       - Scope: BEFORE execution, long-term preferences
  |       - Threshold: rating >= 4 (high satisfaction)
  |
  +---> Correction Layer (RetryPolicy)
          - Reads: FeedbackStore (only for ask_user)
          - Does NOT learn preferences
          - Adjusts: only on FAILURE via CorrectionStrategy
          - Scope: DURING retry, immediate correction
```

**Pros:** Clear layer separation, no conflicts, each layer has distinct scope
**Cons:** Two readers of same data (but non-conflicting)

### Option C: Unified LearningPolicy

```
Feedback -> LearningPolicy (new class)
              |
              +---> plan() -> preferred params
              +---> correct() -> param_adjustments
              +---> ask_user() -> should ask?
```

**Pros:** Single source of truth
**Cons:** New class, over-engineering for current scale

---

## 4. Recommendation: Option B (Layered learning)

### Clear boundaries

| Layer | Component | When | What | Feedback role |
|-------|-----------|------|------|--------------|
| Planning | AdaptivePlanner | Before execution | Preferred params | Filters low-rated records from preference pool |
| Execution | RetryPolicy | After failure | param_adjustments | Hardcoded CorrectionStrategy rules |
| Interaction | RetryPolicy.decide() | After SUCCESS | ask_user | Checks if user rated <= 2 |

### Resolution of conflicts

1. **AdaptivePlanner sets preferred params** (long-term learning from successes)
2. **RetryPolicy adjusts on failure** (short-term correction, no learning)
3. **No oscillation** because:
   - AdaptivePlanner only learns from SUCCESSFUL records
   - RetryPolicy corrections are applied to FAILED attempts
   - Successful corrections get recorded in history -> AdaptivePlanner learns them
   - The loop converges: successful params -> preferred -> used by default

### What needs to change

| Change | File | Description | Risk |
|--------|------|-------------|------|
| Wire feedback_store to AdaptivePlanner | conversation.py | Pass feedback_store when creating AdaptivePlanner | Low (optional param) |
| Wire feedback_store to RetryPolicy | agent.py, conversation.py | Pass feedback_store to RetryPolicy constructor | Low (optional param) |
| Fix O(N^2) in _filter_by_feedback | analytics.py | Cache get_all() result per call | Low |
| Remove duplicate preferred_params | adaptive.py | Use HistoryAnalytics instead of local duplicate | Medium (needs testing) |
| Add feedback UI to built-in HTML | ui.py | Simple rating form after generation | Low |

### What NOT to change

- RetryPolicy continues to use CorrectionStrategy (hardcoded rules)
- AdaptivePlanner continues to recompute from history (no persistent model)
- No new classes (LearningPolicy etc.) -- over-engineering
- M22-M24 remain frozen

---

## 5. Verification when feedback is wired

After wiring feedback_store:

1. **M19 path:** AdaptivePlanner with feedback_store -> _filter_by_feedback() active -> low-rated records excluded
2. **M24 path:** RetryPolicy with feedback_store -> _check_feedback_after_success() active -> ask_user on low rating
3. **No conflict:** AdaptivePlanner sets defaults, RetryPolicy corrects on failure
4. **Convergence:** Successful corrections appear in history -> AdaptivePlanner learns them

---

*Audit complete. Awaiting approval for wiring changes.*
