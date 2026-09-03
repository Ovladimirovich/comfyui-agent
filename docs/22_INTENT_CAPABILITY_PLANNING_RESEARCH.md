# Intent → Capability Planning — Architectural Research

**Date:** 2026-09-03
**Status:** RESEARCH IN PROGRESS
**Decision:** AD-40 (APPROVED)
**Goal:** Investigate feasibility of Intent-Driven Workflow Composition

---

## 1. Existing Capability Primitives Analysis

### 1.1 Registered Capabilities (from `app/registry/capability.py`)

| ID | media_input | media_output | operation | default_workflow |
|----|-------------|--------------|-----------|------------------|
| `image.generate` | () | image | text-to-image | txt2img |
| `image.edit` | (image,) | image | image-to-image | — |
| `image.inpaint` | (image, mask) | image | inpaint | — |
| `image.upscale` | (image,) | image | upscale | — |
| `video.generate` | () | video | text-to-video | — |
| `video.image_to_video` | (image, video) | video | image-to-video | — |
| `video.upscale` | (video,) | video | upscale | — |
| `audio.generate` | () | audio | text-to-audio | — |
| `custom.execute` | () | other | custom | — |

### 1.2 Registered Workflows (from `workflows/`)

| Workflow | Capability | Status |
|----------|------------|--------|
| txt2img | image.generate | AVAILABLE |
| img2img | image.edit | AVAILABLE |
| upscale | image.upscale | AVAILABLE |
| video_generate | video.generate | AVAILABLE |
| audio_generate | audio.generate | AVAILABLE |

### 1.3 Gap Analysis

**Registered but no workflow:**
- `image.inpaint` — no workflow.json
- `video.image_to_video` — no workflow.json
- `video.upscale` — no workflow.json
- `custom.execute` — no workflow.json

**Workflow exists but capability not registered:**
- None (all workflows map to registered capabilities)

---

## 2. Composability Analysis

### 2.1 Compatibility Matrix

Composability rule: `capability_A.media_output ∈ capability_B.media_input`

| From ↓ / To → | image.generate | image.edit | image.inpaint | image.upscale | video.generate | video.image_to_video | video.upscale | audio.generate |
|---------------|----------------|------------|---------------|---------------|----------------|----------------------|---------------|----------------|
| **image.generate** | ✅ | ✅ | ❌ (needs mask) | ✅ | ❌ | ✅ | ❌ | ❌ |
| **image.edit** | ✅ | ✅ | ❌ (needs mask) | ✅ | ❌ | ✅ | ❌ | ❌ |
| **image.inpaint** | ✅ | ✅ | ❌ (needs mask) | ✅ | ❌ | ✅ | ❌ | ❌ |
| **image.upscale** | ✅ | ✅ | ❌ (needs mask) | ✅ | ❌ | ✅ | ❌ | ❌ |
| **video.generate** | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ |
| **video.image_to_video** | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ |
| **video.upscale** | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ |
| **audio.generate** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

### 2.2 Composable Chains (Examples)

**Image domain:**
```
image.generate → image.upscale ✅
image.generate → image.edit ✅
image.generate → image.edit → image.upscale ✅
image.edit → image.upscale ✅
```

**Video domain:**
```
video.generate → video.upscale ✅
image.generate → video.image_to_video ✅
image.generate → video.image_to_video → video.upscale ✅
```

**Cross-domain (image → video):**
```
image.generate → video.image_to_video ✅
image.generate → video.image_to_video → video.upscale ✅
```

**Non-composable:**
```
image.generate → audio.generate ❌ (image ∉ audio.generate.input)
video.generate → image.edit ❌ (video ∉ image.edit.input)
```

### 2.3 Key Insight

**Composability is determined by media type compatibility.** The `media_input` and `media_output` fields in Capability already provide the contract needed for composition.

---

## 3. Input/Output Contracts

### 3.1 Existing Contract Model

```python
@dataclass(frozen=True)
class Capability:
    id: str
    media_input: tuple[str, ...]      # Required input media types
    media_output: str | None           # Output media type
    operation: str                     # Semantic operation
    description: str
    default_workflow: str | None
    parameters: tuple[str, ...]        # Supported parameters
```

### 3.2 Contract Sufficiency

**For composition, we need:**
1. ✅ Output type of step N (from `media_output`)
2. ✅ Input type of step N+1 (from `media_input`)
3. ✅ Compatibility check (output ∈ input)

**Current contract is sufficient for type-based composition.**

### 3.3 Missing Contract Elements

For advanced composition, we may need:
- **Parameter mapping** — how params from step N map to step N+1
- **Asset role naming** — "input_image" vs "reference_image" for clarity
- **Quality constraints** — minimum resolution, fps, etc.

**Recommendation:** Start with type-based composition. Add parameter mapping later if needed.

---

## 4. Capability Graph Representation

### 4.1 Graph Structure

```
Nodes: Capabilities
Edges: Composability (output_A ∈ input_B)
```

### 4.2 Example Graph

```
image.generate ──→ image.edit ──→ image.upscale
      │                │
      └──→ video.image_to_video ──→ video.upscale

video.generate ──→ video.upscale
      │
      └──→ video.image_to_video ──→ video.upscale
```

### 4.3 Graph Traversal

**Goal:** Find path from user intent to final output.

**Algorithm:**
1. Parse intent → target capability (or capabilities)
2. Find all paths from available inputs to target
3. Rank paths by: length, history success rate, estimated duration
4. Select optimal path → ExecutionChain

### 4.4 Implementation Approach

```python
class CapabilityGraph:
    def __init__(self, registry: CapabilityRegistry):
        self._registry = registry
        self._build_graph()
    
    def find_paths(self, target: str, available_types: set[str]) -> list[list[str]]:
        """Find all composable paths to target capability."""
        # BFS/DFS with type compatibility check
    
    def get_composability(self, from_cap: str, to_cap: str) -> bool:
        """Check if two capabilities are composable."""
        from_output = self._registry.get(from_cap).media_output
        to_inputs = self._registry.get(to_cap).media_input
        return from_output in to_inputs
```

---

## 5. Planner vs Composer Boundary

### 5.1 Current Planner Responsibility

```python
class Planner(Protocol):
    def plan(self, request: str, context: PlanContext | None = None) -> PlanResult:
        """user intent → capability + params"""
```

**Current flow:**
```
User Intent → Planner → PlanResult(capability, params)
```

### 5.2 Proposed Boundary

| Component | Responsibility | Input | Output |
|-----------|---------------|-------|--------|
| **Planner** | Intent → Capability selection | User request | Single capability + params |
| **Composer** | Capability → Chain of capabilities | Target capability + context | List of (capability, params) |
| **ExecutionChain** | Execute chain | List of subtasks | ChainResult |

### 5.3 New Flow

```
User Intent
    ↓
Planner.plan() → PlanResult(capability="image.upscale", params={...})
    ↓
Composer.compose(target="image.upscale", context=plan_ctx)
    ↓
[("image.generate", {prompt, ...}), ("image.upscale", {factor, ...})]
    ↓
ExecutionChain.execute(subtasks)
    ↓
ChainResult
```

### 5.4 Key Insight

**Planner stays unchanged.** Composer is a new layer that wraps Planner + CapabilityGraph + ExecutionChain.

---

## 6. SemanticVerifier in Intermediate Steps

### 6.1 Current Verifier Usage

```python
# In WorkflowEngine.execute():
verifier.verify(job, manifest)  # Structural verification
```

### 6.2 Proposed Intermediate Verification

```python
# In ExecutionChain.execute():
for step in chain:
    job = execute_step(step)
    if semantic_verifier:
        result = semantic_verifier.verify(step.intent, job.output_assets)
        if result.score < threshold:
            # Retry step or abort chain
```

### 6.3 Benefits

- **Early failure detection** — don't continue chain if step N failed
- **Quality assurance** — verify intermediate results match intent
- **Adaptive retry** — adjust params based on verification feedback

### 6.4 Risks

- **Latency** — each verification adds 2-5s
- **False negatives** — verifier may reject valid intermediate results

**Recommendation:** Make intermediate verification optional (configurable per chain).

---

## 7. Handling Impossible Composition

### 7.1 Failure Scenarios

1. **No path exists** — target capability cannot be reached from available inputs
2. **Missing workflow** — capability exists but no AVAILABLE workflow
3. **Incompatible constraints** — runtime/model requirements not met

### 7.2 Fallback Strategies

| Scenario | Fallback |
|----------|----------|
| No path exists | Ask user to clarify or provide input asset |
| Missing workflow | Suggest alternative capability |
| Incompatible constraints | Explain limitation and suggest alternatives |

### 7.3 User Communication

```python
class CompositionResult:
    success: bool
    chain: list[SubTask] | None
    failure_reason: str | None
    suggestions: list[str]  # Alternative approaches
```

---

## 8. Avoiding Second Execution Path

### 8.1 Current Execution Path (M1-M18)

```
Agent.generate() → WorkflowEngine.execute() → Job
ConversationAgent.turn() → WorkflowEngine.execute() → Job
ExecutionChain.execute() → WorkflowEngine.execute() → Job (per step)
```

### 8.2 Constraint

**All execution MUST go through WorkflowEngine.execute().**

### 8.3 Composer Integration

Composer does NOT execute. It only plans:

```python
class Composer:
    def compose(self, target: str, context: PlanContext) -> CompositionResult:
        """Returns chain of subtasks, NOT execution"""
        # Use CapabilityGraph to find path
        # Return list of SubTask for ExecutionChain
```

ExecutionChain (M18) handles actual execution via WorkflowEngine.

### 8.4 Verification

- Composer has no reference to WorkflowEngine
- Composer only uses CapabilityRegistry and CapabilityGraph
- ExecutionChain remains the single entry point for execution

---

## 9. Keeping M1-M18 Frozen

### 9.1 Modules NOT to Modify

| Module | Reason |
|--------|--------|
| `app/engine/engine.py` | Core execution, M4 |
| `app/engine/chain.py` | M18, already supports multi-step |
| `app/planner/` | M8/M16, already supports context-aware planning |
| `app/registry/capability.py` | M3, source of truth |
| `app/registry/workflow.py` | M3, source of truth |
| `app/agent.py` | M8, entry point |
| `app/conversation.py` | M7, session management |

### 9.2 New Modules to Create

| Module | Responsibility |
|--------|---------------|
| `app/planner/composer.py` | Intent → Capability chain composition |
| `app/planner/capability_graph.py` | Capability composability graph |
| `app/planner/composition_result.py` | Result type for composition |

### 9.3 Integration Points

```python
# In ConversationAgent.turn():
if self.composer and self.execution_history:
    composition = self.composer.compose(target, context)
    if composition.success:
        return self.execution_chain.execute(composition.chain)
    else:
        # Fallback to single-step or ask user
```

---

## 10. Composition Without New workflow.json

### 10.1 Question

> Can we get composition without writing a new workflow.json for each new user scenario?

### 10.2 Answer: YES

**Mechanism:**
1. Composer selects chain of existing capabilities
2. Each capability maps to an existing workflow (via `default_workflow` or registry)
3. ExecutionChain executes each workflow sequentially
4. Output of step N → Input of step N+1 (via AssetStore)

### 10.3 Example

**User request:** "Сгенерируй кота и увеличь разрешение"

**Composer output:**
```python
[
    SubTask(capability="image.generate", params={"prompt": "кот", ...}),
    SubTask(capability="image.upscale", params={"factor": 2, ...}),
]
```

**Execution:**
1. Execute `txt2img` workflow → Asset A (image)
2. Asset A → input for step 2
3. Execute `upscale` workflow → Asset B (upscaled image)

**No new workflow.json needed.**

### 10.4 Limitations

- Composition limited to existing capabilities/workflows
- Cannot create truly new operations (e.g., "style transfer") without new workflow
- Complex operations (e.g., "face detection + crop + enhance") require pre-built workflows

### 10.5 Future Extension

For operations not covered by existing workflows:
1. Register new capability in CapabilityRegistry
2. Add workflow.json for new capability
3. Composer can now include it in chains

---

## 11. Research Summary

### 11.1 Feasibility: ✅ HIGH

| Criterion | Status | Notes |
|-----------|--------|-------|
| Existing primitives sufficient | ✅ | 9 capabilities, 5 workflows |
| Composability possible | ✅ | Type-based compatibility works |
| Contracts sufficient | ✅ | media_input/media_output sufficient |
| No second execution path | ✅ | Composer doesn't execute |
| M1-M18 can stay frozen | ✅ | New layer on top |
| No new workflow.json needed | ✅ | For existing capabilities |

### 11.2 Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Complex intent parsing | MEDIUM | Start with keyword-based, evolve |
| Composition explosion | MEDIUM | Limit chain length, use history |
| Intermediate verification latency | LOW | Make optional |
| Impossible composition | LOW | Fallback to user |

### 11.3 Recommended Next Steps

1. **Create `CapabilityGraph`** — build composability graph from CapabilityRegistry
2. **Create `Composer`** — implement composition algorithm
3. **Integrate with ConversationAgent** — use Composer when multi-step detected
4. **Test with real scenarios** — validate on complex user requests
5. **Document findings** — update PROJECT_SPEC with new architectural layer

---

## 12. Open Questions for AD

1. Should Composer be a separate class or part of Planner protocol?
2. How to handle parameter mapping between steps?
3. Should intermediate verification be on by default?
4. Maximum chain length limit?
5. How to represent "alternative paths" to user?

---

*Research document. Not an architectural decision. Awaiting AD based on findings.*