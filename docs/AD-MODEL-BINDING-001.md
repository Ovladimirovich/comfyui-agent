# AD-MODEL-BINDING-001: Model Requirement Semantics

**Status:** PROPOSED  
**Date:** 2026-09-09  
**Type:** Contract Extension  
**Affected Layers:** Manifest, Registry, Compatibility, Execution  
**Related ADs:** AD-18 (cache ≠ live), AD-29 (ModelRegistry), AD-41 (Backend-Scoping Deferred)

---

## 1. Context

ComfyUI Agent v1 selects and executes workflows based on declared manifest requirements. Models are a first-class resource: every image/video generation workflow requires a checkpoint model. The current contract for expressing model requirements is ambiguous, leading to a semantic gap between declaration and execution.

---

## 2. Problem

### Current `required_models` semantics

```python
# app/registry/workflow.py
required_models: list[str] = field(default_factory=list)
```

Docstring in `evaluate_compatibility` (app/registry/compatibility.py:12):
> required_models — точное имя модели (exact identity). Пример: "model.safetensors".

Contract enforcement (app/registry/compatibility.py:73-82):
```python
for m in workflow.required_models:
    if m not in models:
        reasons.append(UnavailableReason.MISSING_MODEL)
        break
```

This is **exact identity**: `"checkpoint"` means "a model literally named 'checkpoint'".

### Current historical manifests

All 5 generation workflows use placeholder:
```json
"required_models": ["checkpoint"]
```

Files:
- `workflows/txt2img/manifest.json`
- `workflows/img2img/manifest.json`
- `workflows/image_inpaint/manifest.json`
- `workflows/video_generate/manifest.json`
- `workflows/video_image_to_video/manifest.json`

### Current execution behavior

`WorkflowEngine._bind_models()` (app/engine/engine.py:163-176):
```python
def _bind_models(self, prompt: dict, provider) -> None:
    if self.model_registry is not None:
        chosen = self.model_registry.resolve(provider.backend_id, "checkpoint")
    else:
        checkpoints = provider.discover_checkpoints()
        chosen = checkpoints[0] if checkpoints else None
    ...
```

`ModelRegistry.resolve()` (app/registry/model.py):
```python
def resolve(self, backend_id: str, requirement: str, kind: ModelKind = ModelKind.CHECKPOINT):
    cat = self._catalog.get(backend_id, {})
    if requirement in cat:
        return requirement  # exact match
    if requirement in {k.value for k in ModelKind}:
        for info in cat.values():
            if info.kind.value == requirement:
                return info.name  # kind-based fallback
    ...
```

**Result:** `_bind_models()` interprets `"checkpoint"` as `ModelKind.CHECKPOINT` and returns the first discovered checkpoint.

### The Gap

| Layer | Interpretation of `"checkpoint"` | Result |
|-------|----------------------------------|--------|
| Manifest contract | Exact model name | Literal string `"checkpoint"` |
| Compatibility check | Exact model name | **UNAVAILABLE** — `"checkpoint" not in {"real_model.safetensors"}` |
| Execution binding | ModelKind placeholder | First discovered checkpoint |

**The execution layer performs unauthorized semantic substitution.**

Additionally:
- Tests pass because they mock `discover_checkpoints()` to return `["checkpoint"]`
- Production discovery returns real filenames: `["cyberrealistic_v80.safetensors", ...]`
- Selection fails before execution is reached (AgentError: no AVAILABLE candidates)
- If selection were bypassed, execution would bind a different model than declared

### ModelRegistry does NOT solve this

```python
mr = ModelRegistry()
mr._catalog['local'] = {'a.safetensors': ..., 'b.safetensors': ...}

mr.resolve('local', 'checkpoint')  # → 'a.safetensors' (first, by insertion order)
```

ModelRegistry improves lookup AFTER requirement is understood, but does not define what `"checkpoint"` means. The interpretation happens in `_bind_models()`, which bypasses the compatibility layer.

---

## 3. Existing Contract

### Manifest schema
```json
{
  "required_models": ["checkpoint"],
  "requirements": {"min_vram_gb": 4, "fp16": true}
}
```

### DiscoveryFacts
```python
@dataclass
class DiscoveryFacts:
    runtime: Optional[RuntimeInfo]
    runtime_available: bool
    models: set[str]              # model filenames only
    models_available: bool
    custom_nodes: CustomNodeInventory
    custom_nodes_available: bool
```

Note: `models` is `set[str]` — **no kind information**. Discovery returns filenames, not typed models.

### ModelRegistry
```python
class ModelRegistry:
    _catalog: dict[str, dict[str, ModelInfo]]  # backend_id -> name -> ModelInfo

    def resolve(self, backend_id: str, requirement: str, kind: ModelKind = ModelKind.CHECKPOINT):
        # 1. exact match
        # 2. kind-based fallback (treats requirement as ModelKind)
```

### evaluate_compatibility
```python
for m in workflow.required_models:
    if m not in models:
        reasons.append(UnavailableReason.MISSING_MODEL)
        break
```

---

## 4. Existing Violation

**Violation:** Execution layer interprets `"checkpoint"` as ModelKind, but compatibility layer treats it as exact identity.

**Consequence:**
1. Workflow selection fails (UNAVAILABLE) because `"checkpoint" not in real_models`
2. If selection were bypassed, execution would bind a concrete model
3. The bound model may differ from what user expects
4. Behavior is non-deterministic (depends on dict order, discovery order)

**Test mask:** Tests pass because `FakeClient.discover_checkpoints()` returns `["checkpoint"]`, making compatibility and execution agree on the same placeholder. Production discovery returns real names, breaking the agreement.

---

## 5. Options

### Option A: Only Exact Identity

```json
{
  "required_models": ["cyberrealistic_v80.safetensors"]
}
```

**Pros:**
- Contract is simple and trivial to enforce
- Fully deterministic
- No ambiguity

**Cons:**
- Workflow becomes environment-specific
- Cannot express "any checkpoint" portably
- Requires updating all 5 manifests with environment-specific names
- Breaks cross-environment portability

**Verdict:** Rejected. Insufficient for agent use case where models vary by deployment.

---

### Option B: Separate Identity and Kind Fields

```json
{
  "required_models": ["exact_model.safetensors"],
  "required_model_kind": "checkpoint"
}
```

**Analysis:**

Can both fields coexist?
- If `required_models` is non-empty → exact identity takes precedence
- If `required_models` is empty and `required_model_kind` is set → kind-based selection
- Both empty → no model requirement

Issues:
- Two fields create potential for inconsistency
- What if both are set with different semantics?
- Compatibility layer needs dual-check logic
- Migration complexity: how to handle existing `required_models=["checkpoint"]`?

**Verdict:** Partially viable but introduces field coupling complexity.

---

### Option C: Typed ModelRequirement (RECOMMENDED)

Introduce structured requirement type:

```python
@dataclass(frozen=True)
class ModelRequirement:
    """Declares a model requirement with explicit semantics."""
    kind: Optional[ModelKind] = None
    identity: Optional[str] = None

    def __post_init__(self):
        if self.kind is not None and self.identity is not None:
            raise ValueError("ModelRequirement cannot have both kind and identity")
        if self.kind is None and self.identity is None:
            raise ValueError("ModelRequirement must have either kind or identity")

    @classmethod
    def exact(cls, name: str) -> 'ModelRequirement':
        """Require exact model by filename."""
        return cls(identity=name)

    @classmethod
    def kind(cls, kind: ModelKind) -> 'ModelRequirement':
        """Require any model of specified kind."""
        return cls(kind=kind)
```

Manifest usage:
```json
{
  "model_requirements": [
    {"kind": "checkpoint"},
    {"identity": "lora.safetensors"}
  ]
}
```

Or single requirement:
```json
{
  "model_requirements": [{"kind": "checkpoint"}]
}
```

**Pros:**
- Explicit semantics: kind vs identity is type-enforced
- No field coupling issues
- Extensible for future requirement types
- Clear error on misconfiguration

**Cons:**
- Requires schema change in Workflow dataclass
- Requires migration of existing manifests
- More complex than flat fields

**Verdict:** Recommended for clean semantics.

---

### Option D: Capability/Constraint Model

Express model requirement as workflow capability constraint:

```json
{
  "capabilities": ["image.generate"],
  "constraints": {"model_type": "checkpoint"}
}
```

**Analysis:**
- Model selection is NOT a capability concern
- Capabilities describe WHAT the workflow does
- Models are RESOURCES required for execution
- Conflating resources with capabilities violates separation of concerns

**Verdict:** Rejected. Wrong abstraction layer.

---

## 6. Ownership

### Manifest
**Responsibility:** Declare requirement with explicit semantics.

```json
{
  "model_requirements": [
    {"kind": "checkpoint"}
  ]
}
```

Or for exact identity:
```json
{
  "model_requirements": [
    {"identity": "cyberrealistic_v80.safetensors"}
  ]
}
```

The manifest does NOT decide which concrete model is selected. It declares WHAT is needed, not WHICH.

### Discovery
**Responsibility:** Collect available models with their kinds.

Current: `models: set[str]` (filenames only)  
Proposed: Enrich with kind information, OR keep as-is and use ModelRegistry for kind lookup.

Discovery returns facts, not decisions.

### Compatibility
**Responsibility:** Check if discovered models satisfy declared requirements.

For `kind` requirement: any model of that kind satisfies.
For `identity` requirement: exact filename match required.

Returns `(WorkflowStatus, list[reasons])`.

### Selection
**Responsibility:** Choose ONE concrete model from candidates.

Policy (see Section 8).

Selection happens AFTER compatibility passes, BEFORE execution.

### ModelRegistry
**Responsibility:** Store per-backend model catalog with kind metadata.

`resolve(backend_id, requirement)` returns concrete model name.

Does NOT interpret requirement semantics. If requirement is `"checkpoint"` (kind), returns first matching model. If requirement is exact identity, returns that model or None.

**Critical:** ModelRegistry must NOT silently reinterpret exact-identity requirements as kind-based.

### ExecutionPlan
**Responsibility:** Contain resolved concrete model identity before execution.

```python
@dataclass
class ExecutionPlan:
    capability: str
    workflow_id: str
    version: str
    params: dict
    asset_bindings: dict
    model_bindings: dict  # NEW: {role: concrete_model_name}
```

Execution receives concrete model name, not requirement.

### Provider
**Responsibility:** Transport assets across backend boundary.

Provider does NOT select models. Provider uploads assets provided by ExecutionPlan.

### Backend
**Responsibility:** Execute workflow with provided prompt.

Backend NEVER interprets workflow requirements semantically. Backend receives concrete prompt with concrete model name.

---

## 7. Selection Semantics

### Single candidate
Trivial: select the only candidate.

### Multiple candidates
When `kind=checkpoint` and candidates are `["a.safetensors", "b.safetensors", "c.safetensors"]`:

**Selection policy (priority order):**

1. **Explicit user preference** (from params/context)
   - If user specified `model="b.safetensors"` in params, use that
   - Only applies to identity requirements or explicit override

2. **ModelRegistry metadata** (if available)
   - Priority score (higher = preferred)
   - Last used timestamp (most recent = preferred)
   - Usage count (most used = preferred)

3. **Deterministic tiebreaker**
   - Sort by model name (ascending, locale-independent)
   - Select first

4. **Ambiguity error**
   - If no metadata and multiple candidates remain after name sort
   - Raise explicit error: "Ambiguous model requirement: multiple candidates [a, b, c]. Specify exact model or configure preference."

**Never:** Use dict insertion order, filesystem order, or `/object_info` response order as selection criterion.

### No candidates
Raise `AgentError`: "No model of kind 'checkpoint' available on backend 'local_comfyui'."

---

## 8. Determinism

### Current behavior (non-deterministic)
```python
chosen = checkpoints[0]  # depends on dict/discovery order
```

### Proposed behavior (deterministic)
```python
candidates = filter_by_kind(discovered_models, required_kind)
if len(candidates) == 0:
    raise AmbiguousModelError("no candidates")
if len(candidates) == 1:
    chosen = candidates[0]
else:
    # Apply selection policy
    chosen = select_model(candidates, preferences, registry_metadata)
    if chosen is None:
        raise AmbiguousModelError(f"multiple candidates: {candidates}")
```

### Guarantees
- Same input → same output (deterministic)
- No dependency on dict order, filesystem order, or backend response order
- Explicit error on ambiguity (no silent first())

---

## 9. Multi-Backend Context

AD-41 (Backend-Scoping Deferred) remains deferred.

**Design constraint:** Architecture must not assume global model availability.

```
Per-backend discovery:
  local_comfyui → [a.safetensors, b.safetensors]
  remote_comfyui → [c.safetensors, d.safetensors]

Model requirement evaluation:
  Backend-specific: requirement checked against backend's discovered models only

No cross-backend model sharing:
  local_comfyui cannot use models from remote_comfyui
```

Implementation: `ModelRegistry` is already per-backend (`_catalog: dict[backend_id, ...]`). Selection uses `provider.backend_id` to scope lookup.

---

## 10. UNKNOWN / Cache Semantics

AD-18 must be preserved: cache discovery cannot elevate UNKNOWN to AVAILABLE.

### Live discovery
```
models_available = True
candidates = discovered models
compatibility CAN evaluate → AVAILABLE or UNAVAILABLE
```

### Cache discovery (NodeSchemaStore)
```
models_available = False
candidates = cached models (known but not verified)
compatibility MUST return UNKNOWN for kind-based requirements
```

**Rationale:** Cached models are last-known, not guaranteed-present. Using them for availability would violate AD-18.

### Can cached models participate in planning?

Yes, but with UNKNOWN status:
- Planning layer can see cached candidates
- But workflow status remains UNKNOWN
- Selection does NOT happen (AgentError raised before selection)
- User must enable live discovery or configure ModelRegistry

**Example:**
```python
# Cache has ['a.safetensors', 'b.safetensors']
# But models_available = False

compatibility(kind="checkpoint", models={'a', 'b'}, models_available=False)
→ UNKNOWN (candidates known but availability not confirmed)
```

---

## 11. Manifest Migration

### Current manifests (legacy-invalid)
```json
"required_models": ["checkpoint"]
```

These are legacy-invalid because:
1. `"checkpoint"` is not a real model filename
2. Execution layer interprets it as ModelKind (semantic gap)
3. Compatibility layer rejects it (exact identity check fails)

### Migration options

**Option 1: Explicit migration (recommended)**
Update all 5 manifests to new contract:
```json
"model_requirements": [{"kind": "checkpoint"}]
```

Remove `required_models` field (or keep as empty list for backward compat).

**Option 2: Backward compatibility wrapper (temporary)**
Add compatibility layer that interprets `required_models=["checkpoint"]` as kind-based:
```python
# In evaluate_compatibility
if workflow.required_models and not workflow.model_requirements:
    # Legacy manifest: interpret as kind-based
    if "checkpoint" in workflow.required_models:
        # Treat as kind requirement
        ...
```

**Verdict:** Option 1 (explicit migration) recommended. No silent reinterpretation.

### Migration timeline
1. Adopt new contract in code
2. Update manifests in parallel commit
3. Remove legacy compatibility after migration
4. Document breaking change in CHANGELOG

---

## 12. Backward Compatibility

### Question: Should old manifests work?

**Answer:** Only with explicit, versioned, tested compatibility layer.

If backward compatibility requires interpreting `"checkpoint"` as ModelKind:
- Must be versioned: only for manifests with `"contract_version": "1"`
- Must be explicit: logged as deprecation warning
- Must be deterministic: same selection policy as new contract
- Must be tested: covered by migration tests

**No silent heuristics.**

### Proposed compatibility approach
```python
# In Workflow loading
if "required_models" in data and "model_requirements" not in data:
    # Legacy manifest
    if data.get("contract_version", 1) == 1:
        # Convert to new format
        model_reqs = []
        for m in data["required_models"]:
            try:
                kind = ModelKind(m)
                model_reqs.append({"kind": kind.value})
            except ValueError:
                model_reqs.append({"identity": m})
        data["model_requirements"] = model_reqs
        data.pop("required_models")
```

This is explicit, versioned, and deterministic.

---

## 13. Recommended Contract

### Data model
```python
@dataclass(frozen=True)
class ModelRequirement:
    kind: Optional[ModelKind] = None
    identity: Optional[str] = None

    def __post_init__(self):
        if self.kind is not None and self.identity is not None:
            raise ValueError("Cannot specify both kind and identity")
        if self.kind is None and self.identity is None:
            raise ValueError("Must specify either kind or identity")

    @classmethod
    def exact(cls, name: str) -> 'ModelRequirement':
        return cls(identity=name)

    @classmethod
    def kind(cls, kind: ModelKind) -> 'ModelRequirement':
        return cls(kind=kind)
```

### Manifest schema
```json
{
  "model_requirements": [
    {"kind": "checkpoint"},
    {"identity": "lora.safetensors"}
  ]
}
```

### Workflow dataclass
```python
@dataclass
class Workflow:
    # ... existing fields ...
    model_requirements: list[ModelRequirement] = field(default_factory=list)
    # required_models DEPRECATED: keep for loading legacy manifests only
```

### Compatibility
```python
def evaluate_compatibility(workflow, runtime, models, custom_nodes):
    # ... existing checks ...

    # Model requirements
    for req in workflow.model_requirements:
        if req.identity:
            # Exact identity check
            if req.identity not in models:
                reasons.append(UnavailableReason.MISSING_MODEL)
        elif req.kind:
            # Kind-based check
            kind_models = {m for m in models if is_kind(m, req.kind)}
            if not kind_models:
                reasons.append(UnavailableReason.MISSING_MODEL)
```

### Selection
```python
def select_model(requirements, candidates, preferences=None, registry=None):
    """Deterministic selection from candidates."""
    result = {}
    for req in requirements:
        if req.identity:
            # Exact: must match exactly
            if req.identity in candidates:
                result[req.identity] = req.identity
            else:
                raise ModelSelectionError(f"Required model not found: {req.identity}")
        elif req.kind:
            # Kind-based: filter and select
            kind_candidates = [m for m in candidates if get_kind(m) == req.kind]
            if not kind_candidates:
                raise ModelSelectionError(f"No model of kind {req.kind.value}")
            if len(kind_candidates) == 1:
                result[req.identity or req.kind.value] = kind_candidates[0]
            else:
                # Apply selection policy
                chosen = apply_selection_policy(kind_candidates, preferences, registry)
                if chosen is None:
                    raise AmbiguousModelError(
                        f"Multiple candidates for kind {req.kind.value}: {kind_candidates}"
                    )
                result[req.kind.value] = chosen
    return result
```

---

## 14. Rejected Alternatives

### Option A (Only Exact Identity)
**Rejected because:** Cannot express portable workflows. Agent must work across environments with different model names.

### Option B (Separate Fields)
**Rejected because:** Field coupling complexity. Two fields create inconsistency surface. Typed dataclass is cleaner.

### Option D (Capability/Constraint)
**Rejected because:** Wrong abstraction layer. Model selection is resource management, not capability declaration.

---

## 15. Required Implementation Changes

### After AD approval, these files require changes:

1. **`app/registry/workflow.py`**
   - Add `ModelRequirement` dataclass
   - Add `model_requirements` field to `Workflow`
   - Keep `required_models` for legacy loading (deprecated)

2. **`app/registry/compatibility.py`**
   - Update `evaluate_compatibility` for `model_requirements`
   - Support both `kind` and `identity` semantics
   - Deprecate `required_models` check (or keep for backward compat)

3. **`app/engine/engine.py`**
   - Update `_bind_models` to use resolved model from ExecutionPlan
   - Remove heuristic `"checkpoint"` interpretation
   - Bind concrete model name, not requirement

4. **`app/engine/plan.py`**
   - Add `model_bindings: dict[str, str]` to `ExecutionPlan`

5. **`app/registry/model.py`**
   - Potentially extend `resolve()` to handle typed requirements
   - Or keep as-is (resolve is lookup, not interpretation)

6. **`workflows/*/manifest.json`** (5 files)
   - Migrate to new `model_requirements` format
   - Remove or empty `required_models`

7. **`app/registry/discovery.py`**
   - Potentially enrich `DiscoveryFacts.models` with kind information
   - Or keep as-is (kinds resolved via ModelRegistry at selection time)

---

## 16. Required Tests

### After AD approval, add these tests:

1. **`test_model_requirement_exact_identity`**
   - `ModelRequirement.exact("foo.safetensors")` creates correct object
   - Compatibility checks exact match

2. **`test_model_requirement_kind`**
   - `ModelRequirement.kind(ModelKind.CHECKPOINT)` creates correct object
   - Compatibility finds any checkpoint model

3. **`test_model_requirement_both_rejected`**
   - Cannot create requirement with both kind and identity
   - ValueError raised

4. **`test_model_requirement_neither_rejected`**
   - Cannot create requirement with neither kind nor identity
   - ValueError raised

5. **`test_deterministic_kind_selection`**
   - Multiple candidates → deterministic selection
   - Same input → same output
   - Not dependent on dict order

6. **`test_selection_with_preference`**
   - User preference overrides deterministic tiebreaker

7. **`test_selection_ambiguous_raises`**
   - Multiple candidates, no preference, no metadata
   - AmbiguousModelError raised

8. **`test_legacy_manifest_migration`**
   - Old `required_models=["checkpoint"]` migrated to new format
   - Explicit warning logged

9. **`test_kind_not_becoming_identity`**
   - Kind requirement does not silently become exact identity
   - Test ModelRegistry.resolve does not reinterpret

10. **`test_cache_remains_unknown`**
    - Cached models → availability stays UNKNOWN
    - AD-18 preserved

11. **`test_execution_plan_has_concrete_model`**
    - ExecutionPlan.model_bindings contains resolved concrete names
    - Not requirements, but resolved identities

12. **`test_provider_does_not_select`**
    - Provider receives concrete model from ExecutionPlan
    - Provider does not perform hidden selection

---

## 17. Open Questions

### Q1: Should `required_models` be kept for backward compatibility?
**Decision:** Keep as deprecated field during transition. Remove after all manifests migrated.

### Q2: How to handle `ModelKind.UNKNOWN`?
**Decision:** `ModelKind.UNKNOWN` is for internal tracking, not for user-facing requirements. Reject in validation.

### Q3: Should selection policy be configurable per-workflow?
**Decision:** No. Selection policy is global (priority → last_used → name sort). Per-workflow configuration adds unnecessary complexity.

### Q4: What happens if ModelRegistry is not configured?
**Decision:** Selection falls back to deterministic name sort. Metadata-based preferences unavailable.

### Q5: Should we support multiple model requirements of same kind?
**Decision:** Yes. `model_requirements: [{"kind": "checkpoint"}, {"kind": "lora"}]` is valid. Each requirement resolved independently.

### Q6: How to handle model versioning?
**Decision:** Out of scope for this AD. ModelIdentity is filename-based. Versioning is orthogonal concern.

---

## Summary

**RECOMMENDED: Option C — Typed ModelRequirement**

**RATIONALE:**
- Explicit semantics (kind vs identity type-enforced)
- No field coupling issues
- Extensible for future requirements
- Clean separation of concerns

**REJECTED:**
- A — Insufficient for portability
- B — Field coupling complexity
- D — Wrong abstraction layer

**CONTRACT:**
```json
{
  "model_requirements": [
    {"kind": "checkpoint"},
    {"identity": "lora.safetensors"}
  ]
}
```

**OWNERSHIP:**
- Manifest: declares requirement
- Discovery: collects candidates
- Compatibility: validates satisfaction
- Selection: chooses concrete model (deterministic)
- ExecutionPlan: contains resolved identity
- Provider: transports, does not select
- Backend: executes, does not interpret

**SELECTION:**
1. User preference
2. ModelRegistry metadata
3. Name sort (deterministic tiebreaker)
4. Ambiguity error if unresolved

**UNKNOWN/CACHE:**
- Live discovery → can evaluate → AVAILABLE/UNAVAILABLE
- Cache discovery → candidates known but → UNKNOWN (AD-18 preserved)

**MIGRATION:**
- Explicit migration of 5 manifests
- No silent reinterpretation
- Temporary backward compat wrapper (versioned)

**BACKWARD COMPATIBILITY:**
- Versioned: only for `contract_version: 1`
- Explicit: logged as deprecation
- Deterministic: same policy as new contract
- Tested: migration tests required

---

**STATUS: PROPOSED — AWAITING APPROVAL**

**NO CODE CHANGES YET.**
