# S2 Design — Candidate → Workflow Bridge (Template-Based Synthesis)

> **Статус:** DESIGN ONLY — не реализация.
> **Дата:** 2026-09-13.
> **Base:** `docs/ECOSYSTEM_FIRST_ARCHITECTURE.md` (APPROVED), S0.5 + S1 (FROZEN).
> **Gate decision:** MODIFY (one-node synthesis insufficient → template-based).
> **Ограничения:** production code NO, tests NO, commit NO.

---

## 1. Problem

Knowledge Core Slice 1 создаёт `CapabilityCandidate` для неизвестных нод (e.g. AgnesVideo → `video.image_to_video`). Но кандидат не может быть исполнен: нет `manifest.json` + `workflow.json`. Agent не может запустить capability без workflow. Lifecycle обрывается между UNDERSTAND и CO-USE.

**Gap:** `CANDIDATE_NO_WORKFLOW` — кандидат есть, исполнимого workflow нет.

---

## 2. Evidence — Why One-Node Synthesis Fails

ComfyUI workflow = **граф из нод с explicit connections**. Даже простейший workflow:

```
upscale = LoadImage → ImageScale → SaveImage  (3 ноды)
txt2img = CheckpointLoader → CLIPEncode×2 → KSampler → VAEDecode → SaveImage  (6+ нод)
```

**Реальные данные из /object_info (959 нод):**

| Тип ноды | Standalone? | Проблема |
|---|---|---|
| ImageScale | ❌ | Нужен LoadImage upstream + SaveImage downstream |
| PollinationsImageGen | ⚠️ | Нет IMAGE input, но нужна SaveImage для сохранения |
| AgnesVideo (Text To Video mode) | ⚠️ | prompt → VIDEO output, но нужна CreateVideo+SaveVideo |
| AgnesVideo (Image To Video mode) | ❌ | Нужен IMAGE input → LoadImage upstream |
| CheckpointLoaderSimple | ❌ | Это loader — часть графа, не standalone |
| KSampler | ❌ | Нужен MODEL+LATENT+CLIP+CONDITIONING = 4+ upstream ноды |

**Все input types в экосистеме:** 150+ типов. Из них standalone-safe: STRING, INT, FLOAT, ENUM, BOOLEAN. IMAGE/AUDIO/VIDEO требуют upstream load nodes. MODEL/CLIP/VAE/LATENT/CONDITIONING требуют specific upstream nodes.

**Вывод:** one-node workflow НЕ валиден для ComfyUI. Нужен multi-node graph.

---

## 3. Modified Approach — Template-Based Synthesis

### 3.1 Concept

```
CapabilityCandidate (from Knowledge Core)
    +
NodeSchema (from /object_info)
    +
WorkflowTemplate (pattern from existing workflows)
    ↓
synthesized manifest.json + workflow.json
    ↓
WorkflowRegistry registration
    ↓
executable capability
```

### 3.2 Template Library

Existing 9 workflows provide patterns:

| Pattern | Template source | Trigger (candidate → pattern match) |
|---|---|---|
| **text→image** | `txt2img` or `pollinations_image` | output=IMAGE, no IMAGE input, has prompt |
| **image→image** | `img2img` or `upscale` | output=IMAGE, has IMAGE input |
| **text→video** | `video_generate` | output=VIDEO, no IMAGE input, has prompt |
| **image→video** | `video_image_to_video` | output=VIDEO, has IMAGE input |
| **text→audio** | `audio_generate` | output=AUDIO, has prompt |
| **image→upscale** | `upscale` | output=IMAGE, has IMAGE input, category=upscaling |

### 3.3 Matching Logic

```python
def match_template(candidate: CapabilityCandidate, schema: NodeSchema) -> Optional[WorkflowTemplate]:
    """Match candidate + schema to a workflow template pattern."""
    output_types = set(schema.output_types)
    has_image_input = any(f.type == "IMAGE" for f in schema.input_required + schema.input_optional)
    has_prompt = any(f.name in ("prompt", "text") for f in schema.input_required)
    
    if "IMAGE" in output_types and not has_image_input and has_prompt:
        return TEMPLATES["text_to_image"]
    if "IMAGE" in output_types and has_image_input:
        return TEMPLATES["image_to_image"]
    if "VIDEO" in output_types and not has_image_input and has_prompt:
        return TEMPLATES["text_to_video"]
    if "VIDEO" in output_types and has_image_input:
        return TEMPLATES["image_to_video"]
    if "AUDIO" in output_types and has_prompt:
        return TEMPLATES["text_to_audio"]
    return None  # no matching template
```

### 3.4 Template Instantiation

Each template defines:
1. **Graph skeleton** — list of node types with connections (e.g. `[LoadImage, TargetNode, SaveImage]`)
2. **Parameter mapping** — which candidate inputs map to which template node fields
3. **Output mapping** — which template node produces the output

Template instantiation:
1. Take graph skeleton
2. Replace `TargetNode` placeholder with actual `class_type` from candidate
3. Map candidate's required inputs to skeleton's input fields
4. Set defaults from NodeSchema
5. Add save node (SaveImage/SaveAudio/CreateVideo) if not present
6. Generate workflow.json + manifest.json

---

## 4. Contract

### 4.1 Input

```python
@dataclass
class WorkflowSynthesisRequest:
    candidate: CapabilityCandidate  # from Knowledge Core
    schema: NodeSchema              # from /object_info
    template: WorkflowTemplate      # matched pattern
```

### 4.2 Output

```python
@dataclass
class WorkflowSynthesisResult:
    manifest: dict        # manifest.json content
    workflow: dict        # workflow.json content
    capability: str       # e.g. "video.image_to_video"
    warnings: list[str]   # e.g. "model requirement inferred, not confirmed"
    safety_class: str     # "SAFE" / "REQUIRES_CONFIRMATION" / "FORBIDDEN"
```

### 4.3 WorkflowTemplate

```python
@dataclass
class WorkflowTemplate:
    name: str                           # e.g. "text_to_image"
    pattern_capability: str             # e.g. "image.generate"
    graph_skeleton: list[dict]          # [{id, class_type, role}]
    connections: list[tuple[str, str, str, str]]  # [(from_id, from_slot, to_id, to_slot)]
    output_node_role: str               # which skeleton node produces output
    parameter_slots: dict[str, str]     # {candidate_input_name: skeleton_node.field}
```

### 4.4 Safety Classification

```python
def classify_safety(schema: NodeSchema) -> str:
    """Classify node for auto-test safety."""
    module = schema.python_module.lower()
    category = schema.category.lower()
    
    # FORBIDDEN: known dangerous
    if any(kw in module for kw in ("shell", "system", "exec", "subprocess")):
        return "FORBIDDEN"
    
    # REQUIRES_CONFIRMATION: external API / network
    if any(kw in module for kw in ("api", "http", "cloud", "remote")):
        return "REQUIRES_CONFIRMATION"
    if any(kw in category for kw in ("api", "cloud", "remote")):
        return "REQUIRES_CONFIRMATION"
    
    # SAFE: built-in or known-safe custom nodes
    if module.startswith("nodes") or module.startswith("comfy_extras"):
        return "SAFE"
    
    # Unknown custom node → REQUIRES_CONFIRMATION
    return "REQUIRES_CONFIRMATION"
```

---

## 5. Generated Workflow Lifecycle

```
1. CandidateGenerator creates CapabilityCandidate (INFERENCE)
2. Template matching → WorkflowTemplate selected
3. Template instantiation → manifest.json + workflow.json
4. Safety classification → SAFE / REQUIRES_CONFIRMATION / FORBIDDEN
5. If SAFE: auto-register in WorkflowRegistry (status=VALIDATED)
6. If REQUIRES_CONFIRMATION: store as proposal, ask user
7. If FORBIDDEN: reject, log
8. Registered workflow → available for _select_manifest / Agent.run
9. RuntimeValidator can now validate (has workflow.json)
10. Execution → Job → ExecutionRecord → ExperienceStore
11. ClaimsPersistence → CONFIRMED claim
```

---

## 6. Integration Points

### 6.1 Where in the architecture

```text
KnowledgeCore.query()
    ↓
CANDIDATE_NO_WORKFLOW gap detected
    ↓
[S2] WorkflowSynthesizer.synthesize(candidate, schema)
    ↓
manifest.json + workflow.json → WorkflowRegistry.register()
    ↓
Capability now AVAILABLE (not just CANDIDATE_ONLY)
```

### 6.2 Invocation

S2 synthesis is triggered **explicitly** (not background):
- User says "разберись с этими нодами" → Agent discovers candidates → synthesizes workflows
- KnowledgeCore.query() returns CANDIDATE_NO_WORKFLOW gap → synthesis attempted
- NOT automatic background synthesis (NG3 compliance)

### 6.3 Interaction with S0.5

S0.5 knowledge preflight sees the newly registered workflow → readiness changes from CANDIDATE_ONLY to EXECUTABLE.

### 6.4 Interaction with S1

Synthesized workflow gets `cost_tier=None` (inherit from backend → FREE for local). Correct behavior.

### 6.5 RuntimeValidator handoff

After synthesis + registration, RuntimeValidator can validate the workflow:
```python
# Future (not S2):
validator.validate_node(candidate.node_class, synthesized_workflow)
```
S2 does NOT activate RuntimeValidator (deferred).

---

## 7. Failure States

| Failure | Behavior |
|---|---|
| No matching template | Log "no template for candidate", return None. Candidate remains CANDIDATE_ONLY. |
| Template instantiation fails (missing required input) | Log warning, return partial result with warnings. |
| Safety = FORBIDDEN | Reject synthesis, log. Candidate remains CANDIDATE_ONLY. |
| Safety = REQUIRES_CONFIRMATION | Store as proposal. User must confirm before registration. |
| Workflow.json invalid (ComfyUI rejects) | Registration fails, log error. Candidate remains CANDIDATE_ONLY. |
| Execution fails (runtime error) | Job FAILED, normal error handling (retry/feedback). |

---

## 8. Provenance

Synthesized workflow carries provenance metadata:
- `manifest.source = "synthesized"` (vs "handcrafted" for existing workflows)
- `manifest.synthesized_from = {"candidate": node_class, "template": template_name}`
- `manifest.safety_class = "SAFE" / "REQUIRES_CONFIRMATION"`
- ClaimsPersistence records synthesis evidence

---

## 9. Non-Goals

1. **НЕ создавать** universal workflow planner (LLM-based graph construction) — FUTURE.
2. **НЕ создавать** arbitrary multi-node graph synthesis — too complex, too unsafe.
3. **НЕ менять** existing handcrafted workflows.
4. **НЕ активировать** RuntimeValidator — deferred until after S2.
5. **НЕ делать** background auto-synthesis — explicit user scenario only (NG3).
6. **НЕ менять** frozen M25/M26 contracts.
7. **НЕ менять** Planner, Engine, Verifier, AssetStore.
8. **НЕ добавлять** new input types to manifest schema.
9. **НЕ проектировать** safety sandboxing (G5 full) — minimal classification only.

---

## 10. Test Matrix

| # | Test | Expected |
|---|---|---|
| T1 | Template matching: text→image candidate | Matches text_to_image template |
| T2 | Template matching: image→video candidate | Matches image_to_video template |
| T3 | Template matching: unknown pattern | Returns None |
| T4 | Instantiation: PollinationsImageGen (text→image) | Valid manifest + workflow (2 nodes: gen + save) |
| T5 | Instantiation: AgnesVideo Text To Video mode | Valid manifest + workflow |
| T6 | Instantiation: AgnesVideo Image To Video mode | Valid manifest + workflow (needs LoadImage) |
| T7 | Safety: built-in node (ImageScale) | SAFE |
| T8 | Safety: custom node (PollinationsImageGen) | REQUIRES_CONFIRMATION |
| T9 | Safety: node with "api" in module | REQUIRES_CONFIRMATED |
| T10 | Safety: node with "shell" in module | FORBIDDEN |
| T11 | Registration: SAFE → WorkflowRegistry | Workflow registered, status=VALIDATED |
| T12 | Registration: REQUIRES_CONFIRMATION → stored as proposal | Not registered until user confirms |
| T13 | Backward compatibility: existing workflows unchanged | All 9 workflows still work |
| T14 | S0.5 interaction: synthesized workflow → knowledge preflight | Readiness changes to EXECUTABLE |
| T15 | S1 interaction: synthesized workflow cost_tier | None → inherits FREE from local backend |
| T16 | Provenance: synthesized manifest has source="synthesized" | Correct metadata |
| T17 | No template match → graceful degradation | Candidate remains CANDIDATE_ONLY |
| T18 | Generated workflow valid for build_prompt | Engine can build prompt from synthesized manifest |

---

## 11. Acceptance Criteria

1. At least 3 template patterns implemented (text→image, image→image, text→video).
2. PollinationsImageGen candidate → synthesized workflow → registered → executable.
3. AgnesVideo candidate (Text To Video mode) → synthesized workflow → registered.
4. Safety classification works (SAFE/REQUIRES_CONFIRMATION/FORBIDDEN).
5. Existing 9 workflows unaffected (zero regression).
6. Synthesized workflow passes `validate_manifest()` + `validate_workflow_structure()`.
7. No background auto-synthesis (NG3 compliance).
8. Provenance metadata present on synthesized workflows.

---

## 12. Scope Summary

| Item | In S2? |
|---|---|
| WorkflowTemplate model | ✅ |
| Template library (3-5 patterns) | ✅ |
| Template matching logic | ✅ |
| Template instantiation | ✅ |
| Safety classification (minimal) | ✅ |
| WorkflowRegistry registration | ✅ |
| Provenance metadata | ✅ |
| Tests (18 tests) | ✅ |
| RuntimeValidator activation | ❌ (deferred) |
| LLM-based graph construction | ❌ (FUTURE) |
| Background auto-synthesis | ❌ (NG3) |
| UI for user confirmation | ❌ (deferred) |
| Sandbox/G5 full safety | ❌ (deferred) |

**Estimated scope: ~200 lines production code, ~250 lines tests.**

---

**S2 DESIGN STATUS: READY (MODIFIED from original hypothesis)**

Original hypothesis (one-node synthesis) was REJECTED by feasibility gate.
Modified approach (template-based synthesis) is architecturally sound.

**IMPLEMENTATION APPROVAL: NOT REQUESTED**

**STOP / WAIT FOR APPROVAL.**
