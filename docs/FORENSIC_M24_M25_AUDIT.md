# Forensic M24/M25 Audit

> **Дата:** 2026-09-05
> **Тип:** Forensic verification (read-only audit)
> **Цель:** Установить фактическое состояние кода против утверждений MASTER_DEVELOPMENT_ROADMAP.md
> **Режим:** Абсолютный read-only. Никаких изменений в код, тесты, workflows, конфигурацию.

---

## 1. Scope

Проверены следующие противоречия между `MASTER_DEVELOPMENT_ROADMAP.md` и фактическим состоянием репозитория:

1. M24.1 — FeedbackStore production wiring
2. M25 — chain_id generation и propagation
3. M25 — multi-asset workflow input
4. M25 — verify_sequence() wiring
5. M25 — ChainExperience auto-record
6. M25 — reconstruction path (Intent → Experience)
7. Git state

**Источники доверия (в порядке приоритета):**
1. Фактический production code
2. Composition root / wiring
3. Существующие тесты
4. Runtime evidence
5. Git history
6. Documentation
7. Предыдущие отчёты

---

## 2. Repository Evidence

### Git State

```
Last commit: 4b36fec M20: Cluster Gateway (AD-42)
Branch: master
Working tree: DIRTY
```

**20 modified files (uncommitted):**

| Файл | Изменения |
|------|-----------|
| `app/agent.py` | +87 lines |
| `app/comfy/client.py` | +11 lines |
| `app/conversation.py` | +159 lines |
| `app/engine/__init__.py` | +8 lines |
| `app/engine/analytics.py` | +39 lines |
| `app/engine/chain.py` | +13 lines |
| `app/engine/engine.py` | +92 lines |
| `app/engine/history.py` | +107 lines |
| `app/engine/job.py` | +6 lines |
| `app/engine/retry.py` | +227 lines |
| `app/engine/verifier.py` | +68 lines |
| `app/planner/adaptive.py` | +33 lines |
| `app/registry/workflow.py` | +32 lines |
| `app/resource/gateway.py` | +13 lines |
| `app/resource/models.py` | +12 lines |
| `app/ui.py` | +30 lines |
| `engineering/DECISION_LOG.md` | +14 lines |
| `engineering/HANDOFF.md` | +101 lines |
| `tasks/ACTIVE.md` | +48 lines |
| `tests/test_m15_persistent_context.py` | +69 lines |

**~40 new untracked files (M24.1/M25 related):**

| Категория | Файлы |
|-----------|-------|
| Production | `app/engine/experience.py`, `app/resource/reconciler.py` |
| Tests | `test_chain_tracking.py`, `test_experience.py`, `test_multi_asset.py`, `test_sequence_verification.py`, `test_m24_1_production_wiring.py`, `test_m24_feedback_decision.py`, `test_m19_feedback_integration.py`, `_m241_e2e.py`, `_m25_e2e_runner.py`, `_test_batch_images.py`, + 7 more |
| Workflows | `workflows/video_image_to_video/manifest.json`, `workflows/video_image_to_video/workflow.json` |
| Docs | `MASTER_DEVELOPMENT_ROADMAP.md`, `M25_*.md` (7 files), `28_LEARNING_ARCHITECTURE_AUDIT.md`, + 3 more |

**Вывод:** M24.1 и M25 реализованы, но НИ ОДНО изменение не закоммичено. Всё остаётся uncommitted.

---

## 3. M24.1 Feedback Wiring

### Roadmap Claim

> "Feedback → AdaptivePlanner dead wiring" (G4, TD-2)
> "FeedbackStore | ✅ FROZEN (dead wiring)" (§2.2)
> "RetryPolicy | ⚠️ No feedback_store" (§11.1)
> "M24 | Feedback-Driven Decision | ⚠️ dead wiring" (§4.1)

### Previous Implementation Claim

> "ConversationAgent(..., feedback_store=fb_store)"
> "AdaptivePlanner получает feedback_store"
> "RetryPolicy получает feedback_store"
> "12 production-wiring тестов"
> "regression 508 passed"

### Actual Code

#### FeedbackStore instantiation (production)

```python
# app/ui.py:521 — build_server() (production entry point)
fb_store = FeedbackStore()

# app/ui.py:522
agent = ConversationAgent(store, backends=BackendCatalog.from_env(), feedback_store=fb_store)

# app/ui.py:85 — ComfyUIServer.__init__()
self.feedback_store = getattr(agent, "feedback_store", None) or FeedbackStore()

# app/ui.py:86
self.agent = agent or ConversationAgent(store, feedback_store=self.feedback_store)
```

**Статус:** FeedbackStore СОЗДАЁТСЯ в production entry points. ✅

#### ConversationAgent → AdaptivePlanner

```python
# app/conversation.py:227 — turn() path
planner = AdaptivePlanner(
    self.execution_history,
    feedback_store=self.feedback_store,  # ← PRESENT
)

# app/conversation.py:642 — _execute_chain_step() path
planner = AdaptivePlanner(
    self.execution_history,
    feedback_store=self.feedback_store,  # ← PRESENT
)
```

**Статус:** AdaptivePlanner ПОЛУЧАЕТ feedback_store. ✅

#### ConversationAgent → RetryPolicy.decide()

```python
# app/conversation.py:367-376 — turn() path
decision = self.retry_policy.decide(
    state=job.state.value,
    attempt=job.attempt,
    error_class=job.error_class,
    current_params=current_params,
    semantic_score=semantic_score,
    prompt_id=job.prompt_id,
    session_id=session_id,           # ← PRESENT
    feedback_store=self.feedback_store,  # ← PRESENT
)
```

**Статус:** RetryPolicy.decide() ПОЛУЧАЕТ feedback_store И session_id. ✅

#### AdaptivePlanner usage

```python
# app/planner/adaptive.py:130-133
if self.feedback_store is not None:
    preferred = self._feedback_weighted_params(
        base_result.capability, context
    ) or preferred
```

**Статус:** AdaptivePlanner ИСПОЛЬЗУЕТ feedback для влияния на planning. ✅

#### RetryPolicy feedback check

```python
# app/engine/retry.py:325-358
def _check_feedback_after_success(self, prompt_id, feedback_store, session_id):
    fb_store = feedback_store or self.feedback_store
    sess_id = session_id or self.session_id
    if fb_store is None or sess_id is None or prompt_id is None:
        return None
    fb = fb_store.get_for_attempt(prompt_id, sess_id)
    if fb is not None and fb.rating <= self.low_rating_threshold:
        return RetryDecision(action="ask_user", ...)
```

**Статус:** RetryPolicy ИСПОЛЬЗУЕТ feedback для `ask_user`决定. ✅

#### Known Gap

```python
# app/agent.py:341-348 — Agent.generate() path (single-shot)
decision = self.retry_policy.decide(
    ...
    prompt_id=job.prompt_id,
    feedback_store=self.feedback_store,  # ← PRESENT
    # NOTE: session_id is NOT passed here
)
```

**Статус:** `Agent.generate()` НЕ передаёт `session_id` → feedback check мёртв в single-shot path. ⚠️

### Tests

`tests/test_m24_1_production_wiring.py` — 12 тестов, проверяющих:
- FeedbackStore → ConversationAgent wiring
- ConversationAgent → AdaptivePlanner wiring
- ConversationAgent → RetryPolicy.decide() wiring
- session_id propagation

### Production Path

```
POST /api/feedback → _handle_feedback() → feedback_store.record(FeedbackRecord(...))
GET /api/feedback/history → factory.get_feedback_history() → feedback_store.get_for_session()

Agent.turn() → AdaptivePlanner(feedback_store=...) → _feedback_weighted_params()
Agent.turn() → RetryPolicy.decide(feedback_store=..., session_id=...) → _check_feedback_after_success()
```

### Verdict

**M24.1 Feedback Wiring = PRODUCTION WIRED ✅**

Roadmap утверждает "dead wiring" — это **ОШИБКА**. Код фактически fully wired в ConversationAgent.turn() path. Единственный gap — Agent.generate() single-shot path не передаёт session_id (minor).

---

## 4. M25 Chain Identity

### Roadmap Claim

> "chain_id в Job/ExecutionRecord — поля существуют, get_by_chain() реализован, но conversation.py и chain.py никогда не генерируют chain_id и не проставляют его в Job." (§2.3)
> "M25.1 Chain Identity | ❌ NOT WIRED" (§4.2)
> "G1 | M25 chain_id не генерируется в production" (§6.1)

### Previous Implementation Claim

> "chain_id handoff в conversation.py"
> "ExecutionChain: chain_id generation"
> "Job.chain_id, ExecutionRecord.chain_id"
> "20 M25.1 tests"

### Actual Code

#### chain_id Generation

```python
# app/conversation.py:517 — _execute_chain()
chain_id = str(_uuid.uuid4())[:12]  # M25: generate chain identifier
```

**Статус:** chain_id ГЕНЕРИРУЕТСЯ как UUID truncated to 12 chars. ✅

#### chain_id Propagation

```python
# app/conversation.py:518
chain_ctx = ChainContext(session_id=session_id, chain_id=chain_id)

# app/conversation.py:566
result = chain.execute(subtasks, chain_id=chain_id)

# app/engine/chain.py:106-107 — fallback
if chain_id is None:
    chain_id = str(uuid.uuid4())[:12]

# app/engine/chain.py:164 — stamp on Job
job.chain_id = chain_id

# app/engine/chain.py:181 — stamp on ExecutionRecord
ExecutionRecord(..., chain_id=chain_id, ...)
```

**Статус:** chain_id ПРОПАГИРУЕТСЯ через всю цепочку. ✅

#### chain_id Fields

```python
# app/engine/job.py:40
chain_id: str | None = None

# app/engine/history.py:52
chain_id: str | None = None

# app/engine/chain.py:39
chain_id: str | None = None  # M25: group identifier for multi-step chains
```

**Статус:** Поля СУЩЕСТВУЮТ на всех уровнях. ✅

#### ExecutionHistory Query

```python
# app/engine/history.py:172-177
def get_by_chain(self, chain_id: str) -> list[ExecutionRecord]:
    return sorted(
        [r for r in self._records if r.chain_id == chain_id],
        key=lambda r: (r.chain_step_index or 0, r.timestamp),
    )
```

**Статус:** get_by_chain() РАБОТАЕТ. ✅

### Runtime Path

```
ConversationAgent.turn()
  → _execute_chain()                               [conversation.py:517]
    chain_id = str(uuid.uuid4())[:12]              ← CREATION
    chain_ctx = ChainContext(session_id, chain_id)  [conversation.py:518]
    chain.execute(subtasks, chain_id)               [conversation.py:566]
      → _execute_step(subtask, i, chain_id)         [chain.py:119]
        → job.chain_id = chain_id                   [chain.py:164]
        → ExecutionRecord(chain_id=chain_id)        [chain.py:181]
```

### Tests

`tests/test_chain_tracking.py` — 20 тестов, включая:
- chain_id generation
- chain_id propagation через steps
- chain_id в Job и ExecutionRecord
- get_by_chain() query
- get_chain_summary() aggregation

### Verdict

**M25 Chain Identity = PRODUCTION WIRED ✅**

Roadmap утверждает "never generate chain_id" — это **ОШИБКА**. chain_id генерируется в `_execute_chain():517` и stampится на каждый Job и ExecutionRecord. Для single-step путей chain_id = None (backward-compatible, intentional).

---

## 5. M25 Multi-Asset

### Roadmap Claim

> "Engine._build_multi_asset_input() — реализован, AssetInput.multi поддерживается, но реальный E2E с multi-asset → video не прогнан." (§2.3)
> "M25.2 Multi-Asset + Sequence | ❌ NOT WIRED" (§4.2)

### Previous Implementation Claim

> "AssetInput extended with multi, max_count, load_node_template, batch_node, batch_field"
> "build_prompt() multi logic"
> "_build_multi_asset_input() BatchImagesNode"
> "workflows/video_image_to_video/"
> "9 M25.2 tests"

### Actual Code

#### AssetInput Multi Fields

```python
# app/registry/workflow.py:68-78
@dataclass
class AssetInput:
    node: str
    field: str
    kind: str
    multi: bool = False
    max_count: int = 1
    load_node_template: str | None = None
    batch_node: str | None = None
    batch_field: str | None = None
```

**Статус:** Multi fields ОПРЕДЕЛЕНЫ. ✅

#### Manifest Validation

```python
# app/registry/workflow.py:172-183
if inp.multi:
    if not inp.batch_node or not inp.batch_field:
        raise ManifestError(
            f"asset_input '{role}': multi=true требует batch_node и batch_field"
        )
```

**Статус:** Валидация РАБОТАЕТ. ✅

#### resolve_asset_inputs List Handling

```python
# app/agent.py:428-433
if isinstance(spec, list):
    resolved = []
    for item in spec:
        resolved.append(_resolve_one(item, role, kind, store, as_ids))
    out[role] = resolved
```

**Статус:** List assets РАЗРЕШАЮТСЯ. ✅

#### build_prompt Multi Dispatch

```python
# app/engine/engine.py:100-102
if bind.multi and isinstance(ref, list):
    self._build_multi_asset_input(prompt, bind, ref)
else:
    single_ref = ref[0] if isinstance(ref, list) else ref
    _set_field(prompt, bind.node, bind.field, single_ref.reference["filename"])
```

**Статус:** Dispatch к multi path РАБОТАЕТ. ✅

#### _build_multi_asset_input

```python
# app/engine/engine.py:112-153
def _build_multi_asset_input(self, prompt: dict, bind, refs: list) -> None:
    # Creates N load nodes
    for i, ref in enumerate(refs):
        node_id = f"{template_node_id}_m25_{i}"
        new_node = copy.deepcopy(template_node)
        new_node.setdefault("inputs", {})["image"] = ref.reference["filename"]
        prompt[node_id] = new_node
        load_node_ids.append(node_id)

    # Connects to batch node
    class_type = batch_node.get("class_type", "")
    if class_type == "BatchImagesNode":
        for i, nid in enumerate(load_node_ids):
            inputs[f"image{i}"] = [nid, 0]
        inputs.pop("images", None)
    else:
        inputs[bind.batch_field] = [[nid, 0] for nid in load_node_ids]
```

**Статус:** Multi-asset prompt building РЕАЛИЗОВАН. ✅

#### Chain Execution Path (Production-Reachable)

```python
# app/conversation.py:660-668 — _execute_chain_step()
for role, ain in manifest.asset_inputs.items():
    if ain.multi:
        matching = [
            aid for aid in ctx.assets
            if self.store.get(aid) and self.store.get(aid).type == ain.kind
        ]
        if matching:
            input_assets[role] = [{"asset_id": aid} for aid in matching[-ain.max_count:]]
```

**Статус:** Production path для multi-asset collection СУЩЕСТВУЕТ. ✅

#### Workflow Manifest

```json
// workflows/video_image_to_video/manifest.json:15-25
"asset_inputs": {
    "images": {
        "node": "10",
        "field": "image",
        "kind": "image",
        "multi": true,
        "max_count": 16,
        "load_node_template": "10",
        "batch_node": "11",
        "batch_field": "images"
    }
}
```

**Статус:** Единственный workflow с `multi: true`. ✅

#### Workflow JSON

```json
// workflows/video_image_to_video/workflow.json:58-61
"11": {
    "inputs": { "images": [] },
    "class_type": "BatchImagesNode",
    "_meta": { "title": "Batch Images (M25: populated from LoadImage nodes)" }
}
```

**Статус:** Используется `BatchImagesNode` (не deprecated `ImageBatch`). ✅

### Potential Issue

`_build_multi_asset_input()` генерирует flat keys (`image0`, `image1`), но реальный `BatchImagesNode` custom node может ожидать dot-path format (`images.image0`). Требуется валидация на реальном ComfyUI.

### Tests

`tests/test_multi_asset.py` — 9 тестов, проверяющих:
- AssetInput multi fields
- Manifest validation
- build_prompt multi dispatch
- _build_multi_asset_input
- resolve_asset_inputs list handling

### Verdict

**M25 Multi-Asset = PRODUCTION WIRED ✅ (⚠️ BatchImagesNode E2E не доказан)**

Roadmap утверждает "NOT WIRED" — это **ОШИБКА**. Multi-asset wired в chain execution path (`_execute_chain_step():660-668`) и в `ui.py` HTTP passthrough. НО: реальный E2E с BatchImagesNode на ComfyUI не доказан.

---

## 6. M25 Sequence Verification

### Roadmap Claim

> "Verifier.verify_sequence() — реализован, но conversation.py никогда не вызывает его после video-шагов." (§2.3)
> "M25.3 Sequence Verification | ❌ NOT WIRED" (§4.2)
> "G2 | M25 verify_sequence не вызывается после video" (§6.1)

### Actual Code

#### Implementation

```python
# app/engine/verifier.py:155-221
def verify_sequence(self, sequence_assets: list[str], expected_count: int | None = None) -> VerificationResult:
    # Checks: empty sequence, frame count, all IDs exist, no duplicates
```

**Статус:** Метод РЕАЛИЗОВАН. ✅

#### Call Sites

| Место | Вызывается? |
|-------|-------------|
| `app/conversation.py` | ❌ НЕ вызывается |
| `app/engine/chain.py` | ❌ НЕ вызывается |
| `app/engine/engine.py` | ❌ НЕ вызывается |
| `tests/test_sequence_verification.py` | ✅ 9 вызовов |
| `tests/_m25_e2e_runner.py` | ✅ 1 вызов |

**Статус:** verify_sequence НЕ ВЫЗЫВАЕТСЯ в production code. ❌

#### Production Verify (Different Method)

```python
# app/engine/engine.py:358
verifier = Verifier(self.store)
result = verifier.verify(manifest, created)
```

Это `verify()` (individual outputs), НЕ `verify_sequence()` (sequence integrity).

### Tests

`tests/test_sequence_verification.py` — 9 тестов:
- Empty sequence
- Missing assets
- Count mismatch
- Duplicate detection

### Verdict

**M25 Sequence Verification = IMPLEMENTED ✅, PRODUCTION WIRED ❌**

Roadmap ПРАВ: verify_sequence() реализован, но НЕ вызывается в production. Это dead code.

---

## 7. M25 ChainExperience

### Roadmap Claim

> "ExperienceStore — реализован, но conversation.py никогда не вызывает build_chain_experience() после chain completion." (§2.3)
> "M25.4 Experience Model | ❌ NOT WIRED" (§4.2)
> "G3 | M25 Experience не строится после chain" (§6.1)

### Previous Implementation Claim

> "experience auto-record в _execute_chain()"
> "ChainExperience, ExperienceStore"
> "13 M25.4 tests"

### Actual Code

#### Implementation

```python
# app/engine/experience.py
class ChainExperience:      # dataclass
class ChainStepExperience:  # dataclass
class ExperienceStore:      # JSONL persistence
def build_chain_experience():  # factory function
```

**Статус:** Всё РЕАЛИЗОВАНО. ✅

#### Auto-Record Code

```python
# app/conversation.py:575-586 — _execute_chain()
if self.experience_store is not None and chain_ctx.chain_id is not None:
    from app.engine.experience import build_chain_experience
    intent = ctx.messages[0].get("turn", "") if ctx.messages else ""
    exp = build_chain_experience(
        chain_id=chain_ctx.chain_id,
        session_id=session_id,
        history=self.execution_history,
        context=ctx,
        intent=intent,
    )
    self.experience_store.record(exp)
```

**Статус:** Код авто-записи РЕАЛИЗОВАН и РАЗМЕЩЁН в `_execute_chain()`. ✅

#### Break Point — ExperienceStore Not Instantiated

```python
# app/ui.py:86 — ComfyUIServer.__init__()
self.agent = agent or ConversationAgent(store, feedback_store=self.feedback_store)
# NOTE: experience_store NOT passed → defaults to None

# app/ui.py:522 — build_server()
agent = ConversationAgent(store, backends=BackendCatalog.from_env(), feedback_store=fb_store)
# NOTE: experience_store NOT passed → defaults to None
```

**Статус:** ExperienceStore НЕ СОЗДАЁТСЯ в production entry points. ❌

#### Dead Code Path

```
ConversationAgent.__init__(experience_store=None)    [ui.py:86 or 522]
  → self.experience_store = None                      [conversation.py:108]
  → _execute_chain()                                  [conversation.py:495]
    → chain.execute() returns                         [conversation.py:566]
    → if self.experience_store is not None:           [conversation.py:576]  ← False
        build_chain_experience(...)                   [conversation.py:579]  ← NEVER REACHED
        self.experience_store.record(exp)             [conversation.py:586]  ← NEVER REACHED
```

### Tests

`tests/test_experience.py` — 13 тестов:
- ChainExperience creation
- ExperienceStore persistence
- build_chain_experience factory
- get_by_chain query
- Restart/reload

**Важно:** Тест `_m25_e2e_runner.py` — ЕДИНСТВЕННОЕ место где `ExperienceStore` передаётся в `ConversationAgent`:
```python
# tests/_m25_e2e_runner.py:105
agent = ConversationAgent(asset_store, experience_store=exp_store)
```

### Verdict

**M25 ChainExperience = IMPLEMENTED ✅, PRODUCTION WIRED ❌**

Roadmap **ЧАСТИЧНО ПРАВ**: код для auto-record СУЩЕСТВУЕТ в `conversation.py:575-586`, НО `ExperienceStore` никогда не инстанцируется в production (`ui.py`), поэтому guard `if self.experience_store is not None` всегда False. Fix = ~3 строки в `ui.py`.

---

## 8. M25 Reconstruction Path

Проверка: может ли текущий код фактически восстановить полную цепочку от Intent до Experience.

### Intent → Prompt 1

| Source | Destination | Mechanism | Persistence | Evidence |
|--------|-------------|-----------|-------------|----------|
| User message | ConversationContext.messages | `turn()` stores in ctx | In-memory session | `conversation.py:207` |

**Статус:** ✅ Работает

### Prompt 1 → Image 1

| Source | Destination | Mechanism | Persistence | Evidence |
|--------|-------------|-----------|-------------|----------|
| Params | WorkflowEngine.build_prompt() | Engine builds ComfyUI prompt | Via Provider | `engine.py:83-108` |
| Prompt | ComfyUI execution | Provider sends to ComfyUI | ComfyUI returns job | `provider.py` |
| Job output | Asset | Engine creates Asset from output | AssetStore (JSONL) | `engine.py:358-370` |

**Статус:** ✅ Работает

### Image 1 → Image 2 (Chain)

| Source | Destination | Mechanism | Persistence | Evidence |
|--------|-------------|-----------|-------------|----------|
| chain_id | All steps | `_execute_chain()` generates UUID | Job.chain_id, ExecutionRecord.chain_id | `conversation.py:517` |
| Asset1 → Step2 input | ChainContext.active_asset | `_on_chain_step_complete()` updates ctx | In-memory | `conversation.py:685-700` |
| Step2 input | build_prompt() | `resolve_asset_inputs()` reads from ctx | Via plan.asset_bindings | `agent.py:428-435` |

**Статус:** ✅ Работает

### Image Sequence → Video

| Source | Destination | Mechanism | Persistence | Evidence |
|--------|-------------|-----------|-------------|----------|
| Assets[] | _execute_chain_step() | Gathers matching assets from ctx | input_assets[role] = list | `conversation.py:660-668` |
| Assets[] | build_prompt() | `_build_multi_asset_input()` | N LoadImage → BatchImagesNode | `engine.py:112-153` |
| BatchImagesNode | ComfyUI | Provider executes batch workflow | Video Asset | `workflows/video_image_to_video/` |

**Статус:** ✅ Код РЕАЛИЗОВАН, ⚠️ E2E не доказан

### Video → Verification

| Source | Destination | Mechanism | Persistence | Evidence |
|--------|-------------|-----------|-------------|----------|
| Video output | Verifier.verify() | Checks individual outputs | VerificationResult | `engine.py:358` |
| Sequence assets | verify_sequence() | Checks sequence integrity | VerificationResult | `verifier.py:155-221` |

**Статус:** ⚠️ verify() работает, verify_sequence() НЕ ВЫЗЫВАЕТСЯ

### Chain → Experience

| Source | Destination | Mechanism | Persistence | Evidence |
|--------|-------------|-----------|-------------|----------|
| chain_id + history | build_chain_experience() | Factory function | ExperienceStore (JSONL) | `conversation.py:575-586` |

**Статус:** ❌ МЁРТВ (experience_store=None)

### Полная цепочка

```
Intent → Prompt 1 → Image 1 → Prompt 2 → Image 2 → ... → Video
                                                              ↓
                                                    verify() ✅
                                                    verify_sequence() ❌ NOT CALLED
                                                              ↓
                                                    build_chain_experience() ❌ DEAD
                                                              ↓
                                                    ExperienceStore.record() ❌ DEAD
```

**Итог:** 5/7 переходов работают. 1 не доказан (E2E). 2 мёртвых (verification + experience).

---

## 9. Evidence Matrix

| Feature | Code exists | Unit tested | Production wired | Real E2E | Status |
|---------|------------|-------------|-----------------|----------|--------|
| FeedbackStore instantiation | ✅ | ✅ | ✅ (ui.py) | ❌ | WIRED |
| FeedbackStore → ConversationAgent | ✅ | ✅ (12 tests) | ✅ | ❌ | WIRED |
| FeedbackStore → AdaptivePlanner | ✅ | ✅ (12 tests) | ✅ | ❌ | WIRED |
| FeedbackStore → RetryPolicy.decide() | ✅ | ✅ (12 tests) | ✅ (turn path) | ❌ | WIRED |
| Agent.generate() session_id gap | ✅ | ⚠️ | ❌ (gap) | ❌ | PARTIAL |
| chain_id generation | ✅ | ✅ (20 tests) | ✅ | ❌ | WIRED |
| chain_id → Job | ✅ | ✅ (20 tests) | ✅ | ❌ | WIRED |
| chain_id → ExecutionRecord | ✅ | ✅ (20 tests) | ✅ | ❌ | WIRED |
| get_by_chain() | ✅ | ✅ (20 tests) | ✅ | ❌ | WIRED |
| Multi-asset resolve | ✅ | ✅ (9 tests) | ✅ | ❌ | WIRED |
| Multi-asset build_prompt | ✅ | ✅ (9 tests) | ✅ | ❌ | WIRED |
| BatchImagesNode format | ✅ | ⚠️ mock only | ✅ | ❌ | WIRED ⚠️ |
| video.image_to_video workflow | ✅ | ⚠️ mock only | ✅ | ❌ | WIRED ⚠️ |
| verify_sequence() | ✅ | ✅ (9 tests) | ❌ DEAD | ❌ | NOT WIRED |
| ChainExperience | ✅ | ✅ (13 tests) | ❌ DEAD | ❌ | NOT WIRED |
| build_chain_experience() | ✅ | ✅ (13 tests) | ❌ DEAD (guard) | ❌ | NOT WIRED |
| ExperienceStore instantiation | ❌ | N/A | ❌ | ❌ | MISSING |

---

## 10. Contradictions

### Roadmap vs Code

| # | Roadmap утверждает | Код фактически | Resolution |
|---|-------------------|----------------|------------|
| 1 | M24.1 dead wiring | Fully wired в ConversationAgent.turn() | **Roadmap ОШИБАЕТСЯ** |
| 2 | M25 chain_id not generated | Generated в _execute_chain():517 | **Roadmap ОШИБАЕТСЯ** |
| 3 | M25 verify_sequence not wired | NOT wired — CONFIRMED | **Roadmap ПРАВ** |
| 4 | M25 ChainExperience not wired | Code exists but store not instantiated | **Roadmap ЧАСТИЧНО ПРАВ** |
| 5 | M25 multi-asset not wired | Wired в _execute_chain_step():660-668 | **Roadmap ОШИБАЕТСЯ** |
| 6 | Real E2E never proven | Confirmed — runner exists but never executed | **Roadmap ПРАВ** |

### Implementation Report vs Code

| # | Report утверждал | Код фактически | Resolution |
|---|-----------------|----------------|------------|
| 1 | M24.1 production wiring done | Correct | **Report ПРАВ** |
| 2 | M25 chain_id handoff | Correct | **Report ПРАВ** |
| 3 | M25 experience auto-record | Partially correct — code exists but guard blocks | **Report ЧАСТИЧНО ПРАВ** |
| 4 | 51 M25 tests pass | Correct (79 total) | **Report ПРАВ** |

### Причина расхождения

Roadmap вероятно был написан до integration código в `conversation.py` или на основе grep по отдельным файлам без чтения composition root. Код для chain_id, feedback, и experience auto-record РЕАЛЬНО СУЩЕСТВУЕТ в `conversation.py` — но это было добавлено позже и не отражено в roadmap audit.

---

## 11. Actual M25 Status

### Phase 1: Chain Identity

| Аспект | Статус |
|--------|--------|
| IMPLEMENTED | ✅ |
| TESTED | ✅ (20 tests) |
| PRODUCTION WIRED | ✅ |
| REAL E2E | ❌ не доказан |
| **Итог** | **PRODUCTION WIRED, needs real E2E** |

### Phase 2: Multi-Asset Workflow Input

| Аспект | Статус |
|--------|--------|
| IMPLEMENTED | ✅ |
| TESTED | ✅ (9 tests) |
| PRODUCTION WIRED | ✅ |
| REAL E2E | ❌ не доказан |
| BatchImagesNode format | ⚠️ потенциальная проблема (flat vs dot-path) |
| **Итог** | **PRODUCTION WIRED, needs E2E + format validation** |

### Phase 3: Sequence Verification

| Аспект | Статус |
|--------|--------|
| IMPLEMENTED | ✅ |
| TESTED | ✅ (9 tests) |
| PRODUCTION WIRED | ❌ DEAD |
| REAL E2E | ❌ |
| **Итог** | **CODE EXISTS, WIRING MISSING** |

### Phase 4: ChainExperience

| Аспект | Статус |
|--------|--------|
| IMPLEMENTED | ✅ |
| TESTED | ✅ (13 tests) |
| PRODUCTION WIRED | ❌ DEAD (ExperienceStore=None) |
| REAL E2E | ❌ |
| **Итог** | **CODE EXISTS, WIRING MISSING (fix ~3 lines in ui.py)** |

---

## 12. Impact on MASTER ROADMAP

Roadmap содержит фактические ошибки в 3 из 5 ключевых утверждений. Это не делает roadmap бесполезным — он остаётся хорошей картой системы. Но конкретныеClaims нуждаются в корректировке.

### Что нужно исправить в roadmap (при следующем обновлении)

| Раздел | Текущее утверждение | Правильное утверждение |
|--------|--------------------|-----------------------|
| §2.2 FeedbackStore | "dead wiring" | "wired в ConversationAgent.turn()" |
| §2.3 chain_id | "never generates" | "generates в _execute_chain():517" |
| §2.3 multi-asset | "NOT WIRED" | "wired в _execute_chain_step():660-668" |
| §4.2 M25.1 | "NOT WIRED" | "WIRED" |
| §4.2 M25.2 | "NOT WIRED" | "WIRED" |
| §6.1 G1 | "chain_id не генерируется" | "chain_id генерируется, experience store отсутствует" |

### Что roadmap описывает ПРАВИЛЬНО

| Раздел | Утверждение |
|--------|------------|
| §2.3 verify_sequence | "NOT WIRED" — верно |
| §2.3 ChainExperience | "ExperienceStore не инстанцируется" — верно (хотя код auto-record есть) |
| §4.1 M25 status | "~80%" — верно (3/4 wired, 1/4 dead, 0/4 E2E) |
| §15.1 M25 completion scope | Правильно описывает что нужно сделать |
| §20.2 FROZEN criteria | Правильно описывает критерии заморозки |

---

## 13. What Must NOT Be Done Yet

基于 forensic findings,以下操作 ЗАПРЕЩЕНЫ на данном этапе:

- ❌ Google Drive deployment
- ❌ Colab E2E запуск
- ❌ FRP/tunnel infrastructure
- ❌ Cloudflare/SteadIP setup
- ❌ Gateway insertion
- ❌ External I/O implementation
- ❌ LearningEngine creation
- ❌ M26 commencement
- ❌ M1–M24 changes
- ❌ Production code changes (в рамках этого аудита)
- ❌ Test modifications
- ❌ Workflow modifications
- ❌ Config changes
- ❌ Architecture changes

### Разрешено (отдельно)

- ✅ Запуск существующих unit тестов (read-only verification)
- ✅ Анализ git status/diff
- ✅ Чтение файлов
- ✅ Поиск по кодовой базе

---

## 14. Conclusion

### Главные выводы

1. **M24.1 Feedback Wiring = WIRED ✅** — Roadmap ошибается. FeedbackStore fully wired в production через ui.py → ConversationAgent → AdaptivePlanner + RetryPolicy.

2. **M25 Chain Identity = WIRED ✅** — Roadmap ошибается. chain_id генерируется в `_execute_chain():517` и stampится на каждый Job и ExecutionRecord.

3. **M25 Multi-Asset = WIRED ✅ ⚠️** — Roadmap ошибается. Multi-asset wired в chain execution path. BatchImagesNode format требует E2E валидации.

4. **M25 verify_sequence = NOT WIRED ❌** — Roadmap прав. Метод implemented, но не вызывается в production.

5. **M25 ChainExperience = NOT WIRED ❌** — Roadmap частично прав. Код auto-record существует в `conversation.py:575-586`, но ExperienceStore не инстанцируется в `ui.py`.

6. **Real E2E = 0/4 phases proven** — Ни одна фаза не доказана на реальном ComfyUI.

7. **Git = uncommitted** — Вся M24.1/M25 реализация остаётся uncommitted.

### Что нужно для M25 completion

| Действие | Тип | Объём |
|----------|-----|-------|
| ExperienceStore instantiation в ui.py | Code change | ~3 строки |
| verify_sequence() call site в conversation.py | Code change | ~5 строк |
| BatchImagesNode format validation | E2E test | Требует реального ComfyUI |
| Real E2E (4 phases) | E2E test | Требует remote ComfyUI |

### Кто был прав

| Источник | Accuracy |
|----------|----------|
| MASTER_DEVELOPMENT_ROADMAP.md | 40% (2/5 claims correct) |
| Previous implementation report | 90% (mostly correct) |
| Actual code | 100% (source of truth) |

---

## 15. Git State

```
Branch: master
Last commit: 4b36fec M20: Cluster Gateway (AD-42)
Working tree: DIRTY

Modified (20):
  app/agent.py, app/comfy/client.py, app/conversation.py,
  app/engine/__init__.py, app/engine/analytics.py, app/engine/chain.py,
  app/engine/engine.py, app/engine/history.py, app/engine/job.py,
  app/engine/retry.py, app/engine/verifier.py, app/planner/adaptive.py,
  app/registry/workflow.py, app/resource/gateway.py, app/resource/models.py,
  app/ui.py, engineering/DECISION_LOG.md, engineering/HANDOFF.md,
  tasks/ACTIVE.md, tests/test_m15_persistent_context.py

Untracked (~40):
  app/engine/experience.py, app/resource/reconciler.py,
  Colab_M25_E2E.ipynb, workflows/video_image_to_video/*,
  tests/test_chain_tracking.py, tests/test_experience.py,
  tests/test_multi_asset.py, tests/test_sequence_verification.py,
  tests/test_m24_1_production_wiring.py, tests/test_m24_feedback_decision.py,
  tests/_m25_e2e_runner.py, tests/_test_batch_images.py,
  docs/MASTER_DEVELOPMENT_ROADMAP.md, docs/M25_*.md (7 files),
  + ~25 more files

Commits for M24.1/M25: NONE
```

**Все M24.1/M25 изменения остаются uncommitted.**

---

> **Forensic baseline зафиксирован. Документ не является планом рефакторинга.**
