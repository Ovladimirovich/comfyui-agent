# M26 — Pre-Implementation Forensic Design

**Milestone under design:** M26 — Experience-Driven Planning Loop
**Date:** 2026-09-11
**Mode:** READ-ONLY forensic / architectural design audit. **No production code, no test changes, no new subsystems, no new persistence, no new AD, no planner/verifier rewrites, M25 unchanged.**
**Baseline:** M25 FROZEN (`engineering/DECISION_LOG.md` 2026-09-11).

---

## 1. Executive Summary

M26 = Experience-Driven Planning Loop is confirmed as the **correct next milestone** after M25. The two items explicitly deferred out of M25 (`docs/M25_ARCHITECTURE_REVIEW.md` §4.3 / §5.4, `MASTER_DEVELOPMENT_ROADMAP.md` §5.4, `DECISION_LOG` 2026-09-11) are exactly "full multi-image semantic temporal verification" and "Experience → Planning integration". M26 closes both (D4 + D5 / Learning Loop).

Forensic facts established:
- **D12 (FeedbackStore → AdaptivePlanner "dead wiring") does NOT exist.** The code is fully wired (`AdaptivePlanner._feedback_weighted_params → HistoryAnalytics.preferred_params(feedback_weighted=True) → FeedbackStore.get_all`). Confirmed by `docs/FORENSIC_M24_M25_AUDIT.md` ("Roadmap ошибается"). → **Exclude from M26 (already closed).**
- **`PlanContext` is FROZEN M9.1.** Experience MUST reach the planner without changing it (`M25_ARCHITECTURE_REVIEW.md` §7.2/7.5). Blessed path: optional `ExperienceStore` param on `AdaptivePlanner` (analog to `feedback_store`).
- **Output-video temporal verification needs a frame-extraction utility that does NOT exist** (no `cv2`/`ffmpeg`/`extract_frames` in code). → **Blocker for M26.3.**
- **AC3 (low output-temporal → FAILED) is a new output-quality-gate semantic** that extends the AD-37/38/39 envelope. It has an existing precedent (`agent.py:638` fails outputs on semantic `score<0.5`), but the threshold and FAILED-vs-advisory choice requires an **architectural decision**. → **Blocker for M26.3.**

**Verdict: READY WITH DECISIONS.** M26.1 + M26.2 + M26.4 are implementable within the existing AD envelope (no new AD). M26.3 is implementable only after two bounded decisions (frame-extraction dependency; AC3 FAILED semantic).

> **Superseded by 2026-09-11 redefinition:** M26.3 более не планируется как video-processing внутри Agent. Исходные blockers (B1 frame-extraction, B2 AC3 FAILED semantic) закрыты решением вынести media analysis в отдельный Video Editor; AD-44 (вариант B) NOT APPROVED. M26.1/2/4 — ACCEPTED; M26 — READY TO FREEZE.

---

## 2. Current State (verified from code)

| Component | File | Status | Notes |
|-----------|------|--------|-------|
| `ChainExperience` | `app/engine/experience.py:51` | EXISTS (M25.4) | Fields incl. `temporal_consistency`, `sequence_experience` (computed view). |
| `SequenceExperience` | `app/engine/experience.py:179` | EXISTS (M25.4, computed view) | `build_sequence_experience()` at :203. |
| `ExperienceStore` | `app/engine/experience.py:83` | EXISTS (M25) | Append-only JSONL `data/experience/{chain_id}.jsonl`. `get_by_chain`, `list_chains`. |
| `HistoryAnalytics` | `app/engine/analytics.py:20` | EXISTS (M16/M19) | Reads `ExecutionHistory` — **has NO temporal/sequence fields** (those live only in `ChainExperience`). |
| `UserPreferences` | `app/planner/preferences.py:13` | EXISTS (M16) | Wraps `HistoryAnalytics`. |
| `AdaptivePlanner` | `app/planner/adaptive.py:29` | EXISTS (M16) | `plan()` merges preferred params as defaults; gates adaptive mode by `>=3` successful records (AD-36). Accepts `feedback_store`. |
| `Composer` | `app/planner/composer.py:23` | EXISTS (M19, AD-41) | `compose()` returns `CompositionResult` with `chain`, `alternatives`, `suggestions`. |
| `SemanticVerifier` | `app/engine/semantic_verifier.py:59` | EXISTS (M14/M25.3) | `verify()` (single output) + `verify_temporal_consistency(sequence_assets)` — **analyzes INPUT image list**, NOT a generated video. |
| `FeedbackStore` | `app/context/feedback.py:32` | EXISTS (M17) | JSONL per session. **WIRED into AdaptivePlanner** (`adaptive.py:130-133`, `analytics.py:79-91`). |
| Frame-extraction util | — | **ABSENT** | No `cv2`/`ffmpeg`/`extract_frames` anywhere in code. |

**M25 production wiring (verified):**
```
app/conversation.py:595  self.semantic_verifier.verify_temporal_consistency(
app/conversation.py:643  build_sequence_experience(exp, temporal_result)
app/conversation.py:645  self.experience_store.record(exp)
```

---

## 3. M25 → M26 Dependency Proof

1. M25 produced `ChainExperience`/`SequenceExperience` (facts) + `verify_temporal_consistency()` in the production pipeline + `build_sequence_experience()` in the experience flow. These are the **inputs** M26 consumes.
2. Explicitly deferred from M25 (sources cited in §1) = "full multi-image semantic temporal verification" (→ M26.3) + "Experience → Planning integration" (→ M26.1 + M26.2 + M26.4).
3. M16 (`AdaptivePlanner`) and M19 (`Composer`) are the **consumers** M26 feeds into. M26 closes the Learning Loop (D5) without replacing them.
4. No M26 component requires a new subsystem, new persistence, or a new AD beyond the two bounded decisions in M26.3.

**Conclusion:** M26 is the immutably-correct successor of M25.

---

## 4. M26.1 — Experience Analytics (forensic design)

**Integration point:** read-only aggregation over `ExperienceStore` (existing JSONL). **No new persistence.**

**Available data (per `ChainExperience`):**
- `steps[]`: `capability`, `workflow_id@workflow_version`, `params`, `state` (SUCCESS/FAILED).
- `temporal_consistency: float|None` — populated for image→video chains (M25.3).
- `sequence_experience: dict|None` — `temporal_consistency`, `image_to_video_transition` (`success`/`inconsistent`/`poor`), `image_params`, `video_params`.
- `overall_state`, `failed_steps`.

**Capability-level vs sequence/context-aware:**
- Capability-level: aggregate across ALL chains of a capability (e.g., `image.generate` success rate, param frequency).
- Sequence-aware: filter chains where `sequence_experience is not None` (i.e., image→video chains); compute `avg(temporal_consistency)`, transition histogram. Distinguish via the presence of `sequence_experience`.

**Reuse / new object:**
- `HistoryAnalytics` is keyed on `ExecutionHistory` and lacks temporal fields → **cannot** aggregate `temporal_consistency`. 
- Recommend a **new read-only `ExperienceAnalytics` class** (e.g., in `app/engine/experience.py` or `analytics.py`) that takes `ExperienceStore`, calls `list_chains()` + `get_by_chain()`, and returns aggregate stats. This is an extension, **not a subsystem**; no persistence added.

**Invariant (Experience = fact):** `ExperienceAnalytics` returns only statistics. Consumers apply them as preference/ranking, **never as prohibition**.

**No new persistence:** confirmed — reads existing `data/experience/*.jsonl`.

---

## 5. M26.2 — Experience → AdaptivePlanner (forensic design)

**Verified production call graph:**
```
ConversationAgent.turn()                         (app/conversation.py:144)
  → planner auto-select                         (conversation.py:218-232)
      base = planner.plan(request, plan_ctx)    (conversation.py:221)
      if history>=3 for capability → AdaptivePlanner(...)  (conversation.py:226)
  → result = planner.plan(request, plan_ctx)    (conversation.py:232)
  → capability/params

ConversationAgent._execute_chain_step()         (app/conversation.py:662)
  → planner auto-select                         (conversation.py:692-704)
  → planner.plan(subtask.description, plan_ctx) (conversation.py:704)

Agent.generate()                               (app/agent.py:540)
  → planner.plan(request)                       (app/agent.py:552)
```

**Integration point:** `AdaptivePlanner.plan()`. **Do NOT change `PlanContext` (FROZEN M9.1).**

**Blessed approach (`M25_ARCHITECTURE_REVIEW.md` §7.3/7.5):** add optional `experience_store: Optional[ExperienceStore] = None` to `AdaptivePlanner.__init__` (analog to `feedback_store`). Build `ExperienceAnalytics` from it.

**How experience enters (no architectural break):**
1. Run existing AD-36 flow (threshold `>=3` successful records per capability; context-aware preferred params).
2. If `experience_store` present, compute experience-derived **soft ranking** (e.g., prefer workflow whose historical `avg(temporal_consistency) >= threshold` for the target capability).
3. Apply as **ranking/default preference**, merged exactly like existing preferred params (explicit user params always win).

**Fallback (no experience):** `experience_store=None` or empty store → behavior **identical** to current.

**`temporal_consistency=None` handling:** UNKNOWN → neutral → **ignored** (never influences). Mirrors AD-18 `UNKNOWN != AVAILABLE`.

**Filtering vs prohibition boundary (CRITICAL):**
- AD-36 currently only **gates whether adaptive mode is ON**; it never prohibits a capability/workflow.
- New experience signal MUST mirror this: it can **rank / prefer / deprioritize**, never **exclude / disable / FAILED**.
- Even if a workflow's `avg(temporal_consistency) < 0.5` across `>=3` experiences, the strongest allowed action is **deprioritize / prefer an alternative** — NOT prohibit. Prohibiting = hard ban = violation of "Experience = fact".
- Verified: current `AdaptivePlanner` has **no prohibition mechanism** (only merges preferred params as defaults). M26.2 preserves this.

**No new planner architecture, no new AD** for this shape (within AD-36/37/38/39 envelope).

---

## 6. D12 — FeedbackStore Dead Wiring (DECISION)

**Finding:** D12 is **NOT a gap**. The MASTER roadmap's "FeedbackStore → AdaptivePlanner dead wiring (GAP D12)" is **stale/incorrect**.

Wiring proven in code:
```
AdaptivePlanner.plan()              (adaptive.py:130)
  → if feedback_store: _feedback_weighted_params()        (adaptive.py:153)
      → analytics.preferred_params(capability, feedback_weighted=True)  (analytics.py:41)
          → _filter_by_feedback() → feedback_store.get_all()           (analytics.py:79-91)
```
`feedback_store` is passed into `AdaptivePlanner` at both `conversation.py:229` and `conversation.py:701`. `docs/FORENSIC_M24_M25_AUDIT.md` (§3) states verbatim: *"Roadmap утверждает 'dead wiring' — это ОШИБКА … fully wired в ConversationAgent.turn() path."*

Residual (minor, separate): `Agent.generate()` single-shot path does not pass `session_id` (feedback check partially inert there) — `FORENSIC_M24_M25_AUDIT.md:194`. Not a planning-path gap; not M26 scope.

**RECOMMENDATION: B — exclude from M26 scope.** D12 is already closed by M19/M24. If richer feedback integration is desired later, that is a separate decision, not a blocker.

---

## 7. M26.3 — Output-Video Temporal Verification (forensic analysis)

> **Note (2026-09-11, docs reconciliation):** исходная постановка M26.3 («frame extraction → temporal score → SUCCESS/FAILED») **REDEFINED** как *Video Editor Integration Boundary*. Video-specific analysis передан будущему отдельному проекту Video Editor; Agent НЕ содержит video-processing слоя. Variant A (advisory) старой формулировки НЕ реализуется сейчас; Variant B / AD-44 **SUPERSEDED / NOT APPROVED**. Ниже сохранён исторический forensic analysis. См. `docs/M26.3_FORENSIC_DESIGN.md` PART 1 (findings) + PART 2 (redefinition).

### What is checked NOW (M25.3)
`verify_temporal_consistency(image_seq_paths)` analyzes the **INPUT image sequence** (collected at `conversation.py:587-593` from `asset.type=="image"`). It does **NOT** analyze the generated video output. The failure path (`conversation.py:603-614`) marks the chain's last (video) step FAILED on low INPUT continuity.

### Where the generated video output physically is
- Produced by `video.image_to_video` step inside `chain.execute()`; ingested as a video `Asset` (type `"video"`), available at `result.steps[-1].job.output_assets[0]` → `Asset.path`.
- Already canonical-ingested **during step execution**, before the post-chain temporal block runs (`conversation.py:568+`).

### collect → verify → ingest (Finding A)
For the OUTPUT video, the Asset is already ingested **before** any verification. This is the **existing pattern**: `agent.py:630-641` also verifies a single output *after* ingest and marks it FAILED post-hoc. So M26.3 must keep the **post-hoc** pattern to avoid an architectural break. True pre-ingest gating would require an AD (reorder execution→verify→ingest). **Recommendation: post-hoc, consistent with M25/M14.**

### Can we verify the generated video before canonical ingest?
No, not without restructuring execution ordering → would need AD. Out of scope for M26 as a "must".

### Frame sampling without new backend
To verify the output video we must **extract frames** and pass them as `sequence_assets` to the existing `verify_temporal_consistency()` (which already does image-pair comparison). **No frame-extraction utility exists.** → **BLOCKER 1: choose dependency** (`imageio-ffmpeg` / `opencv` / `ffmpeg` subprocess). Must degrade to neutral (`temporal_score=None`) when unavailable (mirror M25 fallback).

### Existing video/frame utility
None. Must be added (generic: any video → frames; feeds generic image-pair comparison → **no media-specific core branching**, satisfies AD-03).

### External dependencies
`ffmpeg` or `opencv` or `imageio` — needs explicit decision + graceful fallback.

### If temporal analysis impossible
`None` → neutral → **do NOT fail** (mirror M25).

### Invariant preservation
- **AD-18 UNKNOWN≠AVAILABLE:** no analysis → neutral, not success. ✓
- **Experience = fact:** score is a recorded fact; failing on low score is a quality gate (post-hoc), must not become a permanent rule. ✓
- **Single SemanticVerifier path:** REUSE `verify_temporal_consistency` with extracted frames — no second verifier. ✓
- **No canonical Asset before verification:** post-hoc is the existing M25/M14 pattern (documented deviation — outputs verified post-ingest). ✓
- **AD-03 no media branching:** frame extractor is generic. ✓

### CRITICAL: is "low temporal score → FAILED" a correct semantic contract for OUTPUT video?
- M25.3 FAILED = INPUT-sequence discontinuity (pre-generation). Extending to OUTPUT video is a **new output-quality gate**.
- **Precedent exists:** `agent.py:638` already fails a single output on semantic `score<0.5`. So an output-quality FAILED is architecturally permissible and consistent.
- **Caution:** the output video is the final deliverable; vision-based temporal scoring is subjective → false-negative + retry-cost risk.
- **Decision required (BLOCKER 2 / AC3):** either (a) reuse `0.5` threshold + post-hoc FAILED (consistent with M14), or (b) **advisory-only** (record output `temporal_consistency` on the video Asset/Experience, surface as suggestion, do NOT fail). This extends the AD-37/38/39 envelope → **requires an AD**. Cannot be coded as-is.

---

## 8. M26.4 — Composer Suggestion (forensic design)

**Verified Composer call graph:**
```
ConversationAgent.turn()                    (conversation.py:172-187)
  → TaskDecomposer.decompose(request)
  → if len(subtasks)>1 and self.composer:
        composition = self.composer.compose(
            target_capability=target, params=..., available_types=set())  (conversation.py:180)
        if composition.success: subtasks = composition.chain
```

**Existing suggestion surface:** `CompositionResult` already carries `alternatives` (≤3) and `suggestions: list[str]` (`composition_result.py:16-43`). So a suggestion mechanism already exists.

**Where experience enters:** `compose()` may accept an **optional experience hint** (e.g., `preferred_workflow` / `sequence_context`) and use it to (a) **rank** `alternatives`, (b) append a `suggestions` string ("based on N past image→video chains, workflow X avg temporal 0.8"). Extending `compose()` signature is a **safe local change** (Composer is M19/AD-41 class, NOT the frozen `PlanContext`).

**Model:** Experience → signal → **suggestion** (NOT Experience → automatic policy). Composer MUST NOT auto-replace the chosen chain; only order/annotate alternatives and populate `suggestions`.

**No hard prohibition:** suggestions never remove capabilities. **No new contract strictly required.**

---

## 9. Architecture Invariants

| Invariant | M26 compliance |
|-----------|----------------|
| AD-03 media-agnostic | Frame extractor generic; experience signals keyed by capability, not media type. ✓ (if implemented generically) |
| AD-05 Asset ≠ file | Experience references assets by id/path; no file-identity assumptions. ✓ |
| AD-18 UNKNOWN ≠ AVAILABLE | `temporal_consistency=None` / no analysis → neutral, never success. ✓ |
| AD-28 doc hierarchy | M26 design follows source-of-truth order. ✓ |
| AD-36 per-capability, no cross-contamination | Experience ranking must remain per-capability (reuse existing `get_successful(capability)` filter). ✓ |
| AD-37/38/39 (Experience=Data, Sequence=Metadata, Multi-Asset) | M26 **consumes** these facts; does not alter them. ✓ |
| AD-MODEL-BINDING-001 | No model-binding changes. ✓ |
| M25 invariant: Experience = fact; Learning = preference/suggestion | Analytics/suggestions/ranking only; never prohibition. ✓ |
| Finding A: collect → verify → ingest | M26.3 post-hoc (consistent with M25/M14). Documented. ✓ |

**No invariant violation introduced by the proposed design.**

---

## 10. AD-41 Collision Finding

`engineering/DECISION_LOG.md` contains **two AD-41** entries:
- `2026-09-03 — AD-41 (Intent → Capability Planning Architecture)` (Composer, authoritative).
- `2026-09-08 — AD-41 (Backend-Scoping Deferred)`.

Canonical AD range is AD-24..AD-42. The `2026-09-08` Backend-Scoping entry should be **renamed AD-43** (proposed in DECISION_LOG TODO at line 75). References to fix: `docs/AD-MODEL-BINDING-001.md:7` ("AD-41 (Backend-Scoping Deferred)" → AD-43), and any other occurrences.

**This is a documentation-only issue. It MUST NOT be silently folded into M26 implementation.** Recommend a separate doc-task: rename Backend-Scoping AD-41 → AD-43 + update references. Not a blocker for M26.

---

## 11. Scope / Non-Scope

**INCLUDE in M26:**
- M26.1 Experience Analytics (read-only `ExperienceAnalytics` over `ExperienceStore`; no new persistence).
- M26.2 Experience → AdaptivePlanner (optional `experience_store` param + soft ranking; no `PlanContext` change).
- M26.4 Composer experience-derived suggestions (optional hint → rank/annotate alternatives).
- M26.3 Output-video temporal verification **subject to two decisions** (frame-extraction dependency; AC3 semantic).

**EXCLUDE from M26:**
- D12 FeedbackStore dead wiring (already wired — §6).
- AD-41 rename (separate doc fix — §10).
- Any new persistence layer, new subsystem, new AD (except the bounded M26.3 AD for AC3), planner rewrite, verifier rewrite, automatic policy/prohibition, M25/M1–M24 changes.

---

## 12. Blockers

| ID | Blocker | Resolution required before implementation |
|----|---------|-------------------------------------------|
| B1 | Frame-extraction utility absent for M26.3 | Decide dependency (`imageio-ffmpeg` / `opencv` / `ffmpeg`); add generic extractor with neutral fallback. |
| B2 | AC3 output-video temporal → FAILED is a new output-quality-gate semantic | AD decision: (a) reuse 0.5 + post-hoc FAILED (consistent w/ M14), or (b) advisory-only. Cannot code AC3 without this. |
| B3 | AC2 threshold `0.7` has no architectural contract | Define explicit named constant with documented basis (verifier prompt convention) or require decision. |

*(Note: if B2 resolves to advisory-only, M26.3 ships as "record output temporal + surface suggestion" — no FAILED, no AD needed.)*

---

## 13. Proposed Production Call Graphs

**M26.1 + M26.2 (Experience → Planning):**
```
ConversationAgent.turn() / _execute_chain_step()
  → planner auto-select → AdaptivePlanner(history, feedback_store, experience_store)   # NEW param
      plan():
        1. base = fallback.plan(request, ctx)                      # unchanged
        2. if history < 3 for capability → return base            # AD-36, unchanged
        3. preferred = context_aware_preferred_params(...)        # unchanged
        4. if experience_store:
             exp = ExperienceAnalytics(experience_store)
             rank = exp.rank_workflows(capability)                # SOFT ranking only
             preferred = merge(rank, preferred)                   # preference, not prohibition
        5. merged = {**preferred, **base.params}                  # explicit user params win
        return PlanResult(capability, merged, rationale)
```

**M26.3 (Output-video temporal, post-hoc):**
```
_execute_chain() after chain.execute():
  video_asset = result.steps[-1].job.output_assets[0]  (type=="video")
  frames = extract_frames(video_asset.path)             # NEW util (B1); None on failure
  if frames and semantic_verifier:
      r = semantic_verifier.verify_temporal_consistency(frames, request, capability)
      if r.temporal_score is not None and < THRESHOLD:  # B2/AC3 decision
          last_job.state = FAILED; error_class="verification"   # post-hoc, like M25/M14
  # record into ExperienceStore (ChainExperience.temporal_consistency) — unchanged M25 path
```

**M26.4 (Composer suggestion):**
```
Composer.compose(target_capability, params, available_types, experience_hint=None)  # NEW optional param
  paths = graph.find_paths(...)
  best = min(paths, key=len)
  alternatives = paths[:3]
  if experience_hint:
      rank alternatives by experience_hint
      suggestions.append("based on N past chains, prefer workflow X (avg temporal 0.8)")
  return CompositionResult.ok(chain=best, alternatives=ranked, suggestions=suggestions)
```

---

## 14. Revised Acceptance Criteria

| AC | Revised | Status |
|----|---------|--------|
| AC1 | `ExperienceAnalytics` aggregates `temporal_consistency` per capability/workflow from `ExperienceStore`; **0 new persistence**; unit-tested on synthetic `ChainExperience` set. | Implementable |
| AC2 | Planner applies experience signal as **ranking only** (no prohibition). Threshold for "prefer" → **explicit named constant** with documented basis (verifier's `0.7` convention), NOT hardcoded magic. Observable: given `>=3` experiences with avg temporal `>=` threshold for workflow X, planner prefers X over available alternative Y. **BLOCKER B3** (define constant). | Needs decision |
| AC3 | Output-video temporal → FAILED. **BLOCKER B2** — requires AD: (a) reuse `0.5` + post-hoc FAILED (consistent w/ M14), or (b) advisory-only. Define precisely before coding. | BLOCKED |
| AC4 | Observable planner change: deterministic test asserts merged params / `rationale` reflect experience preference when experience present vs absent (stubbed store). | Implementable |
| AC5 | **0 new failures** in M25-related + planner + experience + semantic-verifier + conversation suites (baseline: 191 passed, 1 skipped, 5 PRE-EXISTING INFRA failures — see §15). | Baseline set |
| AC6 | Invariants enforced by tests: `temporal_consistency=None` → no influence; no capability ever FAILED/disabled by experience; single verifier path; verifier creates no Asset. | Implementable |
| AC7 | D12 already closed — AC7 becomes: regression test that `FeedbackStore → AdaptivePlanner` remains wired after M26, and document D12 as NOT a gap. **Recommendation B.** | Exclude/verify |

---

## 15. Regression Baseline (run 2026-09-11, no code changes)

| Suite | Result | Label |
|-------|--------|-------|
| `test_experience.py` | PASS | M25 regression |
| `test_temporal_verification.py` | PASS | M25 / SemanticVerifier |
| `test_video_image_to_video.py` | PASS | M25 / video workflow |
| `test_m25_b1_b2_integration.py` | PASS | M25 B1/B2 |
| `test_m14_semantic_verification.py` | PASS | M14 |
| `test_m16_adaptive_planner.py` | PASS | M16 |
| `test_planner.py` | PASS | Planner |
| `test_planner_context.py` | **5 FAILED** (`AgentError: no workflow with confirmed compatibility`) | PRE-EXISTING / INFRA (AD-18 runtime compatibility; environment, not M25/M26) |
| `test_m19_composer.py`, `test_m19_integration.py` | PASS | M19 |
| `test_m19_feedback_integration.py` | PASS | M19 / D12 wiring |
| `test_m19_e2e_real.py` | (not run) | INFRA (ComfyUI not running) |
| `test_conversation_m7.py` | 40 passed, 1 skipped | Conversation integration |
| `test_agent.py` | 8 passed | Agent |

**Aggregate:** ~191 passed, 1 skipped, 5 PRE-EXISTING INFRA failures (`test_planner_context.py`, AD-18 runtime compatibility — unrelated to M25/M26). No M25/M26-related failures. Baseline set without modifying any tests.

---

## 16. Recommendation

**VERDICT: READY WITH DECISIONS.**

- **M26.1, M26.2, M26.4** — READY FOR IMPLEMENTATION. Implementable within the existing AD envelope (AD-36/37/38/39, M9.1 PlanContext frozen, single SemanticVerifier path). No new AD required for these shapes.
- **M26.3** — BLOCKED on two bounded decisions:
  - **B1:** frame-extraction dependency (no util exists today).
  - **B2 (AC3):** output-video temporal → FAILED semantic requires an AD (or resolve to advisory-only, which removes the AD need and ships M26.3 as record+suggest).
- **D12** — EXCLUDE (already wired; recommendation B).
- **AD-41 collision** — separate documentation fix (rename Backend-Scoping → AD-43); not folded into M26.

**Required decisions before M26 implementation may start:**
1. Frame-extraction dependency choice (B1).
2. AC3 output-quality FAILED semantic: AD (reuse 0.5) vs advisory-only (B2).
3. AC2 preference threshold constant + documented basis (B3).

M25 remains FROZEN and unchanged.

---

*Generated 2026-09-11. Read-only forensic audit. No speculative code, tests, subsystems, persistence, or ADs created.*
