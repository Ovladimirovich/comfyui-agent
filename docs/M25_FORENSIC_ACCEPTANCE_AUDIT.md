# M25 Forensic Acceptance Audit

**Дата:** 2026-09-10
**Режим:** READ-ONLY forensic verification
**Основание:** `docs/M25_COMPLETION_REPORT.md`, `docs/M25_ARCHITECTURE_PROPOSAL.md`, `docs/NEXT_MILESTONE_ARCHITECTURAL_AUDIT.md`

---

## STATUS: GREEN WITH DOC GAPS

M25 реализован частично. Критический gap: temporal verification не wired в production pipeline.

---

## M25.1 Chain Tracking

| Критерий | Статус |
|----------|--------|
| `chain_id` в ExecutionRecord | ✅ EXISTS |
| `ExecutionHistory.get_by_chain()` | ✅ EXISTS |
| `ExecutionHistory.get_chain_summary()` | ✅ EXISTS |
| Генерация chain_id в ExecutionChain | ✅ EXISTS |
| Тесты: test_chain_tracking.py | ✅ 22/22 pass |

**Verdict: COMPLETE** ✅

---

## M25.2 Video Workflow

### Forensic проверка HEAD vs working tree

```
HEAD workflow.json:   10 nodes ✅ (аудит ошибочно сообщил 0)
HEAD manifest:        required_custom_nodes=["CreateVideo","SaveVideo","LoadImageBatch"]
                      required_models=["checkpoint"]
                      model_requirements=None
                      contract_version=None

Working tree manifest:required_custom_nodes=["CreateVideo","SaveVideo"] (убран LoadImageBatch)
                       required_models=[]
                       model_requirements=[{"kind":"checkpoint"}] (перенос из required_models)
                       contract_version=2
```

### Проверка workflow.json (10 nodes)

| Node ID | class_type | Роль |
|---------|-----------|------|
| 1 | CheckpointLoaderSimple | Model |
| 2 | CLIPTextEncode | Positive prompt |
| 4 | CLIPTextEncode | Negative prompt |
| 5 | KSampler | Generation |
| 6 | VAEDecode | Decode latent |
| 7 | CreateVideo | Assemble frames |
| 8 | SaveVideo | Output (video) |
| 10 | LoadImage | Template for multi-input |
| 11 | BatchImagesNode | Batch images |
| 12 | VAEEncode | Encode to latent |

**Граф связан:** все edges ссылаются на существующие nodes ✅
**Output node 8:** SaveVideo, kind=video ✅
**Manifest ↔ Workflow согласованы:** inputs/asset_inputs/outputs маппятся на node IDs ✅

### Проверка manifest contract

- `capability: video.image_to_video` ✅
- `model_requirements: [{"kind": "checkpoint"}]` (AD-MODEL-BINDING-001) ✅
- `required_custom_nodes: ["CreateVideo", "SaveVideo"]` ✅
- `asset_inputs.images.multi=true, max_count=16` ✅
- `limits.max_sequence_length=16` ✅
- `requirements: min_vram_gb=4, fp16=True` ✅

### Capability selection

```
С runtime + checkpoint + {CreateVideo,SaveVideo} → AVAILABLE ✅
С runtime + checkpoint + {} → AgentError (AD-18 strict) ✅
```

**Verdict: COMPLETE** ✅

---

## M25.3 Temporal Verifier

### Что реализовано

| Компонент | Статус |
|-----------|--------|
| `SemanticVerificationResult.temporal_score` | ✅ field added |
| `SemanticVerificationResult.temporal_issues` | ✅ field added |
| `SemanticVerifier.verify_temporal_consistency()` | ✅ method (+176 LOC) |
| `_sample_indices()` | ✅ helper |
| `_compare_frame_pair()` | ✅ helper |
| Tests: test_temporal_verification.py (11) | ✅ all pass |

### Критический gap: production wiring

```bash
$ grep -rn "verify_temporal_consistency" app/
app/engine/semantic_verifier.py:262:    def verify_temporal_consistency(
```

Метод вызывается **ТОЛЬКО в тестах**. В production code (engine.py, conversation.py, agent.py) — **ни одного вызова**.

Существующий production pipeline:
```python
# app/conversation.py:342
semantic_result = self.semantic_verifier.verify(
    request=request, output_path=output_asset.path, capability=capability
)
```

Вызывается `verify()` (single output), НЕ `verify_temporal_consistency()` (sequence).

### Архитектурный анализ

`verify_temporal_consistency()` — read-only анализ, НЕ создаёт Asset. Не нарушает `collect → verify → ingest`.

**Вопрос:** должен ли temporal verifier быть wired в pipeline?

M25 proposal DoD (M25.3):
```
- [ ] SemanticVerifier.verify_temporal_consistency(sequence_assets) → SemanticVerificationResult
- [ ] SemanticVerificationResult.temporal_score: float | None
- [ ] Temporal prompt проверяет visual continuity
- [ ] Тесты: temporal consistency scoring
```

DoD **НЕ требует** wire в pipeline. Но acceptance criteria из task:
```
[ ] temporal verification подключён в правильный verification pipeline
```

**Конфликт между proposal DoD и task acceptance criteria.**

**Решение:** Метод реализован корректно, tests pass. Wire в pipeline — это архитектурное решение, выходящее за рамки M25 completion (требует определения когда и как вызывать temporal check). **Не blocker для M25, но gap для full utility.**

**Verdict: PARTIAL** ⚠️ (method implemented, tests pass, production wiring deferred)

---

## M25.4 Experience Model

### Что реализовано

| Компонент | Статус |
|-----------|--------|
| `ChainExperience` dataclass | ✅ EXISTS |
| `ChainStepExperience` dataclass | ✅ EXISTS |
| `ExperienceStore` (JSONL) | ✅ EXISTS |
| `build_chain_experience()` | ✅ EXISTS |
| ConversationAgent integration (lines 585-596) | ✅ EXISTS |
| Тесты: test_experience.py | ✅ 13/13 pass |

### Чего НЕ хватает

```python
# app/engine/experience.py
# SequenceExperience — НЕ существует
# build_sequence_experience() — НЕ существует
```

M25 proposal DoD (M25.4):
```
- [ ] SequenceExperience dataclass + JSONL persistence  ← НЕ ВЫПОЛНЕНО
- [ ] build_sequence_experience() из ConversationContext ← НЕ ВЫПОЛНЕНО
```

**Verdict: PARTIAL** ⚠️ (ChainExperience done, SequenceExperience missing)

---

## TEST INTEGRITY

### M25-specific tests (26 tests)

| Файл |Tests | meaningful assertions | tautological? | mocking? |
|------|------|----------------------|---------------|----------|
| test_temporal_verification.py | 11 | ✅ empty/single/no-key/missing/good/poor/sampling/regression | ❌ Нет | ✅ mock API |
| test_video_image_to_video.py | 15 | ✅ manifest/graph/build_prompt/capability/limits | ❌ Нет | ❌ Минимальный |

**Оценка:** Тесты not tautological, проверяют architectural invariants (AD-18, media-agnostic, multi-asset binding).

### Regression suite

```
341 passed, 1 skipped, 0 failed
```

Baseline: 315 passed → 341 passed (+26 M25 tests). **0 new failures.** ✅

### E2E tests (environmental)

```
test_m18_e2e_real.py: 8 failed, 5 passed, 3 skipped (ComfyUI not running)
test_m21_real_e2e.py: 2 failed, 10 passed, 3 skipped (ComfyUI not running)
```

Pre-existing, not M25-related. ✅

---

## ARCHITECTURE

### Invariants check

| ID | Инвариант | Статус |
|----|-----------|--------|
| P1 | Media-agnostic core | ✅ `multi` flag declarative |
| P3 | Layered responsibility | ✅ Execution ≠ Experience |
| P5 | Asset-first | ✅ Sequence = Asset group |
| AD-03 | No media-branching | ✅ _compare_frame_pair universal |
| AD-18 | UNKNOWN ≠ AVAILABLE | ✅ video_i2v UNAVAILABLE without custom nodes |
| AD-28 | Doc hierarchy | ✅ код следует proposal |

### Production call graph

```
ConversationAgent.turn()
  → Agent.prepare() → _select_manifest() → WorkflowRegistry
  → WorkflowEngine.execute()
    → build_prompt() → _build_multi_asset_input() [M25.2]
    → Provider.execute() → ComfyUI
    → Verifier.verify() [M14]
    → AssetStore.ingest()
  → semantic_verifier.verify() [M14, single output]
  → _on_chain_step_complete()
    → build_chain_experience() [M25.4, ChainExperience only]
    → experience_store.record()
```

**Gap:** `verify_temporal_consistency()` не в call graph.

---

## SPEC COMPLIANCE

### M25 Proposal DoD check

| DoD Item | Status |
|----------|--------|
| M25.1: chain_id, get_by_chain, get_chain_summary | ✅ |
| M25.2: AssetInput.multi, build_prompt multi, workflow.json | ✅ |
| M25.3: verify_temporal_consistency(), temporal_score, tests | ⚠️ метод есть, wiring deferred |
| M25.4: ChainExperience, ExperienceStore, CA integration | ✅ |
| M25.4: SequenceExperience, build_sequence_experience() | ❌ НЕ ВЫПОЛНЕНО |

### Task acceptance criteria check

| Criterion | Status |
|-----------|--------|
| video workflow не пустой | ✅ 10 nodes |
| workflow соответствует ComfyUI schema | ✅ все edges valid |
| manifest ↔ workflow согласованы | ✅ node IDs match |
| ModelRequirement корректен | ✅ checkpoint kind |
| video workflow проходит contract validation | ✅ AVAILABLE with runtime+nodes |
| verify_temporal_consistency() реализован | ✅ |
| temporal verification в verification pipeline | ⚠️ метод есть, wiring deferred |
| canonical Assets не создаются до verification | ✅ порядок сохранён |
| ConversationAgent использует build_chain_experience() | ✅ (lines 585-596) |
| session isolation сохранён | ✅ |
| chain/retry/persistence не сломаны | ✅ regression green |
| M25 tests существуют и проходят | ✅ 26/26 pass |
| M18-M25 regression проходит | ✅ 341 passed |

---

## REGRESSION

```
Baseline: 315 passed, 1 skipped
After M25: 341 passed, 1 skipped
Delta: +26 M25 tests, 0 new failures
```

**Verdict: NO REGRESSION** ✅

---

## GIT STATE

### M25-specific changes:
| Файл | Изменение |
|------|-----------|
| `app/engine/semantic_verifier.py` | +181 LOC (temporal) |
| `workflows/video_image_to_video/manifest.json` | fix custom_nodes + model_requirements |
| `tests/test_temporal_verification.py` | NEW (11 tests) |
| `tests/test_video_image_to_video.py` | NEW (15 tests) |
| `docs/M25_COMPLETION_REPORT.md` | NEW (report) |

### Pre-existing changes (recovery session, not M25):
- 18 files modified (agent.py, conversation.py, tests, docs, etc.)
- Не трогать

### Untracked files (not M25):
- `__test_finding_a_success__/`, `_*.py`, `agent_ui/`, `app/data/`, `app/knowledge/`, etc.
- Не трогать

---

## DOCUMENTATION

### M25_COMPLETION_REPORT.md vs факт

| Утверждение в report | Факт | Корректно? |
|---------------------|------|-----------|
| workflow.json: 10 nodes | 10 nodes | ✅ |
| workflow.json был пуст (0 nodes) | ОШИБКА: всегда был 10 nodes | ❌ Report inaccurate |
| ConversationAgent integration уже существовала | lines 585-596 exist | ✅ |
| M25.3 method implemented | verify_temporal_consistency() exists | ✅ |
| M25.3 NOT wired into pipeline | Confirmed: no production calls | ❌ Report misses this gap |
| SequenceExperience not implemented | Confirmed: missing | ❌ Report doesn't mention |

**Doc gaps:**
1. Report claims "workflow.json был пуст" — but it was NEVER empty (10 nodes at HEAD)
2. Report doesn't mention `SequenceExperience` is missing
3. Report doesn't mention temporal verification is NOT wired into production

---

## PREVIOUS AUDIT ERROR ANALYSIS

**Вопрос:** Почему предыдущий аудит сообщил `workflow.json = 0 nodes`?

**Факты:**
- HEAD commit: `e694e50 M21-M25: Decision Bridge, Feedback, Experience, Chain Identity, Multi-Asset, Sequence Verification`
- HEAD workflow.json: 10 nodes (verified via `git show HEAD:workflows/...`)
- Working tree workflow.json: 10 nodes (verified via direct read)
- Метод чтения в аудите: `len(json.load(open('...'))) ` — корректный

**Вероятная причина:** Аудит читал файл в момент, когда он был временно пуст (например, во время промежуточной стадии реализации предыдущим AI-агентом). Либо использовался stale cache. Файл был восстановлен до 10 nodes до начала текущей сессии.

**Риск аналогичных ошибок:** Низкий — теперь верификация выполняется через `git show HEAD:file` для objective baseline.

---

## FINDINGS

- **F1 (Medium):** `verify_temporal_consistency()` не вызывается в production code. Method exists but dead in production.
- **F2 (Medium):** `SequenceExperience` и `build_sequence_experience()` отсутствуют в `app/engine/experience.py`. M25 proposal DoD требует.
- **F3 (Low):** `M25_COMPLETION_REPORT.md` содержит неточность: утверждает что workflow.json был "пуст (0 nodes)", но фактически он всегда содержал 10 nodes.
- **F4 (Low):** Предыдущий аудит ошибочно сообщил 0 nodes в workflow.json — вероятнее всего stale state в момент чтения.

---

## BLOCKERS

- **B1:** `verify_temporal_consistency()` не wired в production pipeline (acceptance criteria требует "подключён в правильный verification pipeline")
- **B2:** `SequenceExperience` not implemented (M25 proposal DoD requires it)

---

## FINAL VERDICT

```
M25 NOT ACCEPTED
```

**Причина:** Два blocker'а:
1. Temporal verification method не интегрирован в production pipeline (acceptance criteria violation)
2. SequenceExperience не реализован (M25 proposal DoD violation)

**Рекомендация:**
- M25.3: Определить point of integration для `verify_temporal_consistency()` в verification pipeline (after chain completion? after video generation?)
- M25.4: Реализовать `SequenceExperience` dataclass + `build_sequence_experience()` + tests

**Работающий код:** 341 passed, 1 skipped, 0 failed. Regression clean. Ядро M25 (ChainExperience, multi-asset, video workflow) — functional.

---

## CODE CHANGES

```
0  (audit is read-only; no code changes made)
```

---

*Forensic acceptance audit completed: 2026-09-10. Read-only mode. Awaiting approval for next steps.*
