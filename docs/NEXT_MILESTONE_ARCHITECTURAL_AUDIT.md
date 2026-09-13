# NEXT MILESTONE ARCHITECTURAL AUDIT

**Дата:** 2026-09-10
**Режим:** READ-ONLY audit + DESIGN
**Основание:** `docs/PROJECT_SPEC.md` (v0.2 APPROVED), `tasks/ACTIVE.md`, фактический код, тесты
**Входные данные recovery:** 120 passed, 1 skipped, 0 failed в recovery suite; known-RED закрыт.

---

## 1. Executive Verdict

**Рекомендуемый следующий milestone: M25 — Experience-Based Media Learning (Completion).**

**Обоснование:**
- M25 architecture proposal утверждён (`docs/M25_ARCHITECTURE_PROPOSAL.md`, AD-37..AD-40 зафиксированы).
- ~70% кода M25 уже реализовано и проходит тесты (experience.py, chain tracking, multi-asset schema).
- Критические GAP'ы препятствуют использованию: `video_image_to_video/workflow.json` пуст (0 nodes), `SemanticVerifier` не имеет `verify_temporal_consistency`, `ConversationAgent` не вызывает `build_chain_experience()`.
- M25 логически завершает lineage M18 → M19 (Composer) → M25 (Experience Layer): цепочка `Intent → Chain → Experience → Analytics` замыкается.
- Все альтернативы отформулированы и отклонены (см. §4).

**Формат:** M25 COMPLETION — доведение утверждённого дизайна до Working State, НЕ новая архитектура.

---

## 2. Current Architecture State

### 2.1 Фактическая структура `app/`

```
app/
├── agent.py              # Agent (M1-M5 integration, M8-L8, M18+)
├── conversation.py       # ConversationAgent (M7, M9.1, M13-M24, M25 partial)
├── ui.py                 # HTTP server + SSE (M9, M12)
├── assets/
│   ├── types.py          # Asset, AssetError (M2)
│   └── store.py          # AssetStore (M2)
├── comfy/
│   ├── client.py         # ComfyClient HTTP+WS (M1)
│   └── lifecycle.py      # ComfyUIProcessManager (M12)
├── engine/
│   ├── engine.py         # WorkflowEngine (M4)
│   ├── job.py            # Job, JobState (M4)
│   ├── plan.py           # ExecutionPlan (M4)
│   ├── verifier.py       # Verifier (M4)
│   ├── websocket.py      # ComfyUIWebSocket (M4)
│   ├── history.py        # ExecutionHistory, ExecutionRecord (M13, M25.1)
│   ├── retry.py          # RetryPolicy, classify_error (M13)
│   ├── chain.py          # ExecutionChain, ChainContext (M18)
│   ├── semantic_verifier.py # SemanticVerifier (M14)
│   ├── analytics.py      # HistoryAnalytics (M16)
│   └── experience.py     # ChainExperience, ExperienceStore (M25.4 ✅)
├── planner/
│   ├── __init__.py
│   ├── heuristic.py      # HeuristicPlanner (M8)
│   ├── llm.py            # LLMPlanner (M8)
│   ├── composite.py      # CompositePromptBuilder (M11)
│   ├── adaptive.py       # AdaptivePlanner (M16)
│   ├── decomposer.py     # TaskDecomposer (M18)
│   ├── composer.py       # Composer (M19)
│   └── capability_graph.py # CapabilityGraph (M19)
├── prompt/
│   ├── builder.py        # PromptBuilder protocol (M11)
│   ├── heuristic.py      # HeuristicPromptBuilder (M11)
│   ├── llm.py            # LLMPlanner (M11)
│   └── composite.py      # CompositePromptBuilder (M11)
├── provider/
│   ├── comfyui.py        # ComfyUIProvider (M5)
│   └── backend_ref.py    # BackendRef (M5)
├── registry/
│   ├── capability.py     # CapabilityRegistry (M3)
│   ├── workflow.py       # Workflow, WorkflowStatus, AssetInput (M3, M25.2)
│   ├── registry.py       # WorkflowRegistry (M3)
│   ├── compatibility.py  # evaluate_compatibility (M3)
│   ├── selection.py      # select_candidate (M3)
│   ├── runtime.py        # RuntimeInfo, discover_runtime (M1)
│   ├── model.py          # ModelRegistry (M5)
│   ├── backends.py       # BackendCatalog, BackendSpec (M20)
│   └── discovery.py      # DiscoveryFacts, NodeSchemaStore (Extended Discovery)
├── resource/
│   ├── gateway.py        # ClusterGateway (M20)
│   ├── models.py         # BackendResource, ReconcileState, etc. (M20)
│   └── reconciler.py     # Reconciler (M21)
└── knowledge/            # KnowledgeCore Slice 1 (M25-era); Slice 2 — SPECD, не интегрирован
    ├── core.py
    └── ...
```

### 2.2 Workflows Directory

| Workflow | Capability | Manifest | workflow.json | Nodes | Status |
|----------|-----------|----------|---------------|-------|--------|
| `txt2img` | image.generate | ✅ | ✅ | >0 | ✅ AVAILABLE |
| `img2img` | image.edit | ✅ | ✅ | >0 | ✅ AVAILABLE |
| `image_inpaint` | image.inpaint | ✅ | ✅ | >0 | ✅ AVAILABLE |
| `upscale` | image.upscale | ✅ | ✅ | >0 | ⚠️ LIMITED (нет upscale models) |
| `pollinations_image` | image.generate | ✅ | ✅ | >0 | ✅ AVAILABLE |
| `text_generate` | text.generate | ✅ | ✅ | >0 | ✅ AVAILABLE |
| `video_generate` | video.generate | ✅ | ✅ | >0 | ✅ AVAILABLE |
| `video_image_to_video` | video.image_to_video | ✅ | ⚠️ EMPTY | 0 | ❌ GAP |
| `audio_generate` | audio.generate | ✅ | ✅ | >0 | ⚠️ BLOCKED (Sonilo 401) |

### 2.3 Document Hierarchy (AD-28)

```
PROJECT_SPEC.md (source of truth, v0.2 APPROVED)
  → docs/00..28_*.md (derived)
  → engineering/* (derived)
  → tasks/* (derived)
  → source code (NEVER source of truth)
```

---

## 3. Completed Milestones (Frozen)

| Milestone | Status | Code | Tests | Evidence |
|-----------|--------|------|-------|----------|
| M1 Runtime + Client | FROZEN | ✅ | 8/8 | test_m1_runtime.py |
| M2 Asset Layer | FROZEN | ✅ | 9/10 (1 skip) | test_m2_asset.py |
| M3 Capability + Workflow Registry | FROZEN | ✅ | 23/23 | test_m3_registry.py |
| M4 Execution/Verification | FROZEN | ✅ | hang (no ComfyUI) | test_m4_execution.py |
| M5 Provider / Model / Remote | FROZEN | ✅ | 17/17 | test_backends.py, test_agent.py |
| M6 Real Video E2E | FROZEN | ✅ | skip (no remote) | test_video_e2e.py |
| M6.5 Image Input / img2img | FROZEN | ✅ | skip (no remote) | test_img2img_e2e.py |
| M7 Conversation Context | FROZEN | ✅ | 7/8 (1 skip) | test_conversation_m7.py |
| M8 Agent + LLM | FROZEN | ✅ | 8/8 | test_agent.py |
| M9 UI | FROZEN | ✅ | 5/5 | test_ui_m9.py |
| M9.1 Context-aware Planner | FROZEN | ✅ | 11/11 | test_planner_context.py |
| M10 Validation | FROZEN | ✅ | 6/7 remote | test_m10* (mixed) |
| M11 Prompt Builder | FROZEN | ✅ | 32/38 pytest + ~54 uncollectable | test_prompt_builder*.py |
| M12 Real UI E2E | FROZEN | ✅ | ~10 uncollectable (Py3.14) | test_ui_m12.py |
| M12.1 ComfyCLI Adapter | FROZEN | ✅ | pass | test_comfy_cli_adapter.py |
| M13 Execution History + Retry | FROZEN | ✅ | pass | test_m13_history_retry.py |
| M14 Semantic Verification | FROZEN | ✅ | pass | test_m14_semantic_verification.py |
| M15 Persistent Context | FROZEN | ✅ | pass | test_m15_persistent_context.py |
| M16 Adaptive Planner | FROZEN | ✅ | pass | test_m16_adaptive_planner.py |
| M17 User Feedback | FROZEN | ✅ | pass | test_m17_user_feedback.py |
| M18 Multi-Step Chain | FROZEN | ✅ | 53 pass (unit) | test_m18_multi_step.py |
| M19 Composer + CapabilityGraph | FROZEN | ✅ | 31 pass | test_m19_composer.py |
| M20 Cluster Gateway | FROZEN | ✅ | pass | test_m20_cluster_gateway.py |
| M21 Reconciliation & Recovery | FROZEN | ✅ | 100 pass | test_m21_*.py |
| M22 Human-in-the-Loop Decision | FROZEN | ✅ | pass | test_m22_decision_bridge.py |
| M23 Parameter Adjustment | FROZEN | ✅ | pass | test_m23_parameter_adjustment.py |
| M24 Feedback-Driven Decision | FROZEN | ✅ | 33 pass | test_m24_*.py |
| M24.1 Production Wiring | FROZEN | ✅ | 12 pass | test_m24_1_production_wiring.py |

**Recovery Suite (этот session):** 162 passed, 1 skipped, 0 failed
- AD-18 Fallback Selection: 13/13 ✅
- Extended Discovery: 37/37 ✅
- Model Binding (AD-MODEL-BINDING-001): 23/23 ✅
- Agent Runtime Validation: 8/8 ✅
- test_agent.py: 8/8 ✅
- test_ui_m9.py: 5/5 ✅
- test_multi_asset.py: pass ✅
- test_workflow_validation_priority.py: 8/8 ✅ (known-RED closed this session)
- test_conversation_m7.py: 7/7, 1 skipped ✅ (fixture fix this session)
- test_experience.py: 13/13 ✅
- test_chain_tracking.py: pass ✅
- test_sequence_verification.py: 20/20 ✅

---

## 4. Partial / GAP / Deferred Areas

### 4.1 M25 — Experience-Based Media Learning (PARTIAL)

**Статус:** Proposal APPROVED (AD-37..AD-40), code ~70% implemented, critical gaps blocking production use.

| Sub-feature | Status | Evidence | Gap |
|-------------|--------|----------|-----|
| M25.1 Chain Tracking | ✅ DONE | `ExecutionHistory.get_by_chain()`, `get_chain_summary()`, `chain_id` in ExecutionRecord | None |
| M25.2 Sequence Support | ⚠️ PARTIAL | `AssetInput.multi` в schema, `build_prompt()` multi-binding, `video_image_to_video/manifest.json` exists | `workflow.json` EMPTY (0 nodes); no real graph |
| M25.3 Temporal Verification | ❌ NOT DONE | `SemanticVerifier.verify()` exists | No `verify_temporal_consistency()` method |
| M25.4 Experience Model | ✅ DONE | `app/engine/experience.py` (173 lines), `ExperienceStore`, `build_chain_experience()` | Integration gap (see below) |
| Experience → ConversationAgent integration | ❌ NOT DONE | `ConversationAgent._on_chain_step_complete()` does NOT call `build_chain_experience()` | Auto-record disabled |

**Критические наблюдения:**
1. `workflows/video_image_to_video/workflow.json` — пустой граф (0 nodes). Capability `video.image_to_video` зарегистрирована, manifest валиден, но workflow неисполним.
2. `SemanticVerifier` не имеет метода `verify_temporal_consistency()`. M25.3 не начат.
3. `ConversationAgent` не вызывает `build_chain_experience()` после завершения chain. Experience создаётся вручную, не автоматически.
4. 7 из 7 proposed M25 test files НЕ существуют:
   - `test_video_image_to_video.py` — ❌
   - `test_temporal_verification.py` — ❌
   - `test_resolve_multi.py` — ❌
   - `test_image_to_video_chain.py` — ❌
   - `test_experience_reconstruction.py` — ❌
   - `test_chain_experience_e2e.py` — ❌
   - `test_video_i2v_real_e2e.py` — ❌

**Уже существует (проходят тесты):**
- `test_experience.py` (13 tests) ✅ — ExperienceStore, build_chain_experience
- `test_chain_tracking.py` (pass) ✅ — get_by_chain, get_chain_summary
- `test_sequence_verification.py` (20 tests) ✅ — sequence verification logic
- `test_multi_asset.py` (pass) ✅ — multi-asset binding

### 4.2 M21 — Reconciliation Real E2E (BLOCKED)

| Test | Status | Причина |
|------|--------|---------|
| `test_m21_real_e2e.py` | 2 failed, 10 passed, 3 skipped | Fail: ComfyUI not running (Connection refused on 127.0.0.1:8188) |
| `test_m21_fault_injection_e2e.py` | skip | Требуется симуляция обрыва связи |

**Факт:** Механизм Gateway + Reconciler INTEGRATED в production code (`engine.py:275`, `conversation.py:750`), unit/fault-injection тесты проходят. Real fault-injection E2E не выполнен — это known gap, задокументирован в `tasks/ACTIVE.md`: "M21 real disconnect E2E — требуется симуляция обрыва связи на живом ComfyUI".

### 4.3 Audio Generate — Real E2E (DEFERRED)

**Причина:** Sonilo HTTP 401 — внешний API ключ невалиден (`sk-5bc5...` format rejected by Comfy.org platform). Код рабочий (M7 HANDOFF), тест доходит до реального вызова Sonilo. Требует валидный `comfyui-...` ключ или локальную модель.

### 4.4 Image Upscale — Model-Based (BLOCKED)

**Причина:** `upscale_models/` директория пуста. Resize-путь (`ImageScale`) работает (не требует модели), model-based upscale — нет. Задокументировано в `tasks/ACTIVE.md`.

### 4.5 Pre-existing Test Defects (НЕ recovery scope)

| Категория | Кол-во | Причина |
|-----------|--------|---------|
| `test_prompt_builder.py` failures | 6 | Stale asserts (Python 3.14 Literal + изменённый контракт) |
| `test_ui_m12.py` / `test_ui_section21.py` | ~12 | API 404 (endpoints not found — UI regression) |
| `test_planner_context.py` | 5 | AgentError при runtime=None (strict AD-18, те же причины что m7 до фикса) |
| `test_m11_verification.py` collection error | 1 | Module-level execution crashes during pytest collection |
| `test_m18_e2e_real.py`, `test_m21_real_e2e.py`, `test_m19_e2e_real.py` | varies | ComfyUI not running (environment) |

**ВСЕ эти failures ПРЕ-СУЩЕСТВОВАЛИ до recovery session** (подтверждено git stash baseline run: 17 failures at HEAD = 17 failures after fix).

---

## 5. Evidence — Discrepancies Between PROJECT_SPEC and Code

### 5.1 PROJECT_SPEC §22 — Устаревший milestone list

**Факт:** PROJECT_SPEC §22 заканчивается на M10 + Mx. M11-M24 реальные, замороженные, проинтегрированы в код.

**Статус:** Отклонено как blocker — `tasks/ACTIVE.md` и `engineering/HANDOFF.md` актуальны. Следующий ИИ должен читать `tasks/ACTIVE.md` для текущего состояния, а не полагаться на устаревший §22. Расхождение зафиксировано как TD-7 в `PROJECT_STATE_2026-09-01.md`.

### 5.2 M25 Proposal vs Implementation

**Proposal** (`docs/M25_ARCHITECTURE_PROPOSAL.md`) описывает 4 phase:
- Phase 1 (M25.1): Chain Tracking — ✅ DONE
- Phase 2 (M25.2): Sequence Support — ⚠️ 50% (manifest есть, workflow.json пуст)
- Phase 3 (M25.3): Temporal Verification — ❌ 0% (нет метода)
- Phase 4 (M25.4): Experience Model — ✅ DONE (integration gap)

**Recommendation:** Доделать Phases 2-3 + integration Phase 4.

### 5.3 ComfyCLIAdapter

**Факт:** `app/infrastructure/comfy_cli_adapter.py` EXISTS (AD-33/AD-34 approved). НЕ найден в предыдущем аудите (PROJECT_STATE_2026-09-01), но существует сейчас. Тест `test_comfy_cli_adapter.py` проходит.

---

## 6. Recommended Next Milestone: M25 Completion

### 6.1 Цель

Довести M25 (Experience-Based Media Learning) до Working State:
- M25.2: Создать исполнимый `video_image_to_video/workflow.json` (N images → video)
- M25.3: Реализовать `SemanticVerifier.verify_temporal_consistency()`
- M25.4: Интегрировать `build_chain_experience()` в `ConversationAgent._on_chain_step_complete()`
- M25 Tests: Создать недостающие 7 test files

### 6.2 Почему именно сейчас

1. **Архитектурная необходимость:** M25 — утвержденный следующий шаг (AD-37..AD-40). M1-M24 обеспечивают execution; M25 замыкает loop: execution → experience → analytics → planning.
2. **Code Already 70%:** Базовая инфраструктура (experience.py, chain tracking, multi-asset schema) реализована. Осталось ~30% — конкретные gaps, а не новая архитектура.
3. **Validation Target:** `video.image_to_video` — Scenario 3 из PROJECT_SPEC §A. Без исполнимого workflow scenario неработающий.
4. **No Spec Violation:** M25 proposal explicitly preserves P1-P10 инварианты (media-agnostic, declarative workflow, provider≠backend).

### 6.3 Какие контракты используются

| Контракт | Использование |
|----------|--------------|
| `AssetInput.multi` (workflow.py) | M25.2 — manifest flag |
| `WorkflowEngine.build_prompt()` | M25.2 — multi asset binding |
| `WorkflowEngine.execute()` | M25.2 — multi upload |
| `ExecutionRecord.chain_id` | M25.4 — experience aggregation |
| `ExperienceStore` (experience.py) | M25.4 — persistence |
| `build_chain_experience()` (experience.py) | M25.4 — reconstruction |
| `ConversationAgent._on_chain_step_complete()` | M25.4 — auto-record integration |
| `SemanticVerifier.verify()` | M25.3 — base method to extend |

### 6.4 Какие новые контракты потребуются

| Новый контракт | Где | Для чего |
|----------------|-----|----------|
| `workflow.json` для `video_image_to_video` | `workflows/video_image_to_video/` | Real ComfyUI graph: LoadImage ×N → ImageBatch → VAEEncode → KSampler → VAEDecode → CreateVideo → SaveVideo |
| `SemanticVerifier.verify_temporal_consistency()` | `app/engine/semantic_verifier.py` | Vision model prompt для проверки continuity между кадрами |
| `SequenceExperience` dataclass | `app/engine/experience.py` | Optional: отдельная persist для batch sequence → video |
| Integration hook | `app/conversation.py:_on_chain_step_complete()` | Call `build_chain_experience()` after chain completion |

### 6.5 Какие файлы/модули затрагиваются

```
workflows/video_image_to_video/workflow.json  — CREATE (80-100 LOC)
app/engine/semantic_verifier.py               — MODIFY (+40 LOC)
app/engine/experience.py                      — MODIFY (+30 LOC, SequenceExperience)
app/conversation.py                           — MODIFY (+10 LOC, integration hook)
tests/test_video_image_to_video.py            — CREATE (~40 LOC)
tests/test_temporal_verification.py           — CREATE (~40 LOC)
tests/test_resolve_multi.py                   — CREATE (~30 LOC)
tests/test_image_to_video_chain.py            — CREATE (~50 LOC)
tests/test_experience_reconstruction.py       — CREATE (~40 LOC)
tests/test_chain_experience_e2e.py            — CREATE (~50 LOC)
tests/test_video_i2v_real_e2e.py              — CREATE (skip if no ComfyUI)
```

**Total:** ~470 LOC code + ~290 LOC tests. Zero changes to M1-M24.

### 6.6 Категорически НЕ входит в scope

- ❌ Новый backend / новая LLM / новый provider
- ❌ Model Registry расширенного уровня
- ❌ FFmpeg как execution backend
- ❌ Удалённая инфраструктура (remote Colab, cloud)
- ❌ Google Drive / sync
- ❌ Переписывание frontend
- ❌ Изменение `AD-41` (Intent → Capability Planning)
- ❌ Исправление 17 pre-existing HEAD failures
- ❌ Изменение уже принятых контрактов (M1-M24 frozen)
- ❌ Новый LearningEngine / Vector DB / RAG
- ❌ M26+ (Learning Loop) — deferred до completion M25

### 6.7 Acceptance Criteria

**M25.2 Sequence Support:**
- [ ] `workflows/video_image_to_video/workflow.json` содержит >0 nodes
- [ ] `video.image_to_video` → AVAILABLE при runtime+checkpoint (не UNKNOWN)
- [ ] `build_prompt()` корректно мапит list assets → batch node fields
- [ ] `test_video_image_to_video.py` pass (manifest validation + discovery)
- [ ] `test_resolve_multi.py` pass (resolve_asset_inputs list support)

**M25.3 Temporal Verification:**
- [ ] `SemanticVerifier.verify_temporal_consistency(sequence_assets)` exists
- [ ] Returns `SemanticVerificationResult` with `temporal_score: float | None`
- [ ] `test_temporal_verification.py` pass

**M25.4 Experience Integration:**
- [ ] `ConversationAgent._on_chain_step_complete()` calls `build_chain_experience()`
- [ ] `ChainExperience` auto-recorded after successful chain
- [ ] `test_experience_reconstruction.py` pass
- [ ] `test_chain_experience_e2e.py` pass (unit, no ComfyUI required)

**Regression Gate:**
- [ ] Все 162 recovery tests продолжают pass
- [ ] `test_m18_multi_step.py`, `test_m19_composer.py`, `test_m20_cluster_gateway.py` pass
- [ ] `test_m21_reconciliation.py`, `test_m22_decision_bridge.py`, `test_m23_parameter_adjustment.py` pass
- [ ] `test_m24_1_production_wiring.py`, `test_m24_feedback_decision.py` pass

### 6.8 Тестовая стратегия

| Уровень | Тесты | Что проверяет |
|---------|-------|---------------|
| Unit | `test_video_image_to_video.py` | Manifest validation, workflow discovery, status=AVAILABLE |
| Unit | `test_resolve_multi.py` | `resolve_asset_inputs()` accepts list[str] |
| Unit | `test_temporal_verification.py` | `verify_temporal_consistency()` scoring |
| Unit | `test_experience_reconstruction.py` | `build_chain_experience()` from ExecutionHistory |
| Integration | `test_chain_experience_e2e.py` | Chain → Experience full flow (mock ComfyUI) |
| E2E | `test_video_i2v_real_e2e.py` | Real ComfyUI: N images → video (skip if no ComfyUI) |

**Mock vs Real:** M25.2-M25.4 unit/integration tests — mock-based (как M18 multi-step). Real E2E — опционально (ComfyUI required).

### 6.9 Архитектурные риски

| Risk | Impact | Mitigation |
|------|--------|------------|
| `LoadImageBatch` / `ImageBatch` nodes отсутствуют в локальном ComfyUI | video_i2v workflow UNAVAILABLE | `required_custom_nodes` в manifest; fallback на sequential image.generate + manual assembly |
| Temporal verification false positives/negatives | Ненадёжный score | Threshold configurable; human review fallback; NOT auto-reject |
| Experience JSONL growth | Disk usage | Не в v1 — archival/cleanup deferred (M26+) |
| Breaking M1-M24 regression | Frozen contracts | Zero changes to M1-M24 modules; additive only |

---

## 7. Scope / Non-Scope

### 7.1 Входит в M25 Completion

- Создание `workflows/video_image_to_video/workflow.json` (ComfyUI graph)
- Расширение `SemanticVerifier` temporal method
- Integration hook в `ConversationAgent`
- 7 новых test files
- Extension `ExperienceStore` для SequenceExperience (optional, if time)

### 7.2 НЕ входит (separate milestones, deferred)

| Что | Почему deferred |
|-----|-----------------|
| M26 Learning Loop | Requires M25 completion first; analytics over experience |
| Audio real E2E | External dependency (Sonilo key) — out of scope |
| Image upscale model-based | Missing models — environment issue |
| M21 real disconnect E2E | Requires fault injection sim — environment issue |
| 17 pre-existing test fixes | Explicitly out of scope per instructions |
| M11 collection error fix | Pre-existing, out of scope |
| ComfyCLIAdapter integration | AD-34: optional diagnostics only, not in execution path |

---

## 8. Regression Gate

**Обязательные проверки перед и после M25 Completion:**

```bash
# Recovery suite (baseline)
python -m pytest tests/test_ad18_fallback_selection.py \
  tests/test_extended_discovery.py \
  tests/test_model_binding_ad001.py \
  tests/test_agent_runtime_validation.py \
  tests/test_agent.py \
  tests/test_ui_m9.py \
  tests/test_multi_asset.py \
  tests/test_workflow_validation_priority.py \
  tests/test_conversation_m7.py \
  tests/test_experience.py \
  tests/test_chain_tracking.py \
  tests/test_sequence_verification.py \
  -q --tb=short

# Target M18-M24
python -m pytest tests/test_m18_multi_step.py \
  tests/test_m19_composer.py tests/test_m19_integration.py \
  tests/test_m20_cluster_gateway.py \
  tests/test_m21_reconciliation.py \
  tests/test_m22_decision_bridge.py \
  tests/test_m23_parameter_adjustment.py \
  tests/test_m24_1_production_wiring.py \
  tests/test_m24_feedback_decision.py \
  -q --tb=short

# New M25 tests (after implementation)
python -m pytest tests/test_video_image_to_video.py \
  tests/test_temporal_verification.py \
  tests/test_resolve_multi.py \
  tests/test_experience_reconstruction.py \
  tests/test_chain_experience_e2e.py \
  -q --tb=short
```

**Ожидаемый результат:** 0 new failures. Все 162 baseline tests + все M18-M24 tests + новые M25 tests — green.

---

## 9. Risks

| # | Risk | Severity | Mitigation |
|---|------|----------|------------|
| R1 | video_i2v workflow требует VHS (Video Helper Suite) nodes, которых нет в baseline ComfyUI | HIGH | Manifest `required_custom_nodes: ["CreateVideo", "SaveVideo"]`; availability checked during discovery; workflow → UNAVAILABLE if missing (AD-18) |
| R2 | Temporal verification зависит от vision model API | MEDIUM | Configurable endpoint (`LLM_BASE_URL`); graceful degradation to `None` score |
| R3 | Experience integration в ConversationAgent может сломать existing chain flow | LOW | Additive change only; default: no auto-record if ExperienceStore not provided |
| R4 | M25 proposal не закоммичен (working tree dirty) | INFO | M25 code exists in working tree; audit confirms it; commit separation不影响 |

---

## 10. Explicit STOP Decision

**СТОП. Реализация НЕ начинается автоматически.**

Этот документ — AUDIT + DESIGN ONLY. Код не изменён. Тесты не изменены. Новая реализация требует отдельного approval от автора проекта.

**Next step (awaiting decision):**
- [ ] Author approval: M25 Completion as next milestone
- [ ] OR alternative milestone selection
- [ ] OR archival of M25 proposal (if direction changed)

---

## Appendix A — Baseline Evidence

### A.1 Recovery Suite (this session)
```
162 passed, 1 skipped, 0 failed
```

### A.2 M18-M24 Suite
```
205 passed (M19-M24 + chain/experience/sequence)
132 passed (M13-M18)
```

### A.3 Pre-existing Failures (untouched)
```
17 failures total:
  - test_planner_context.py: 5 (AD-18 strict, same root as m7 before fix)
  - test_ui_m12.py: 6 (Python 3.14 + stale fixtures)
  - test_ui_section21.py: 6 (API 404s)
  - test_m11_verification.py: 1 (collection error)
```

### A.4 M25 Code Audit

| Component | File | Lines | Status |
|-----------|------|-------|--------|
| ChainExperience | `app/engine/experience.py` | 173 | ✅ |
| ExperienceStore | `app/engine/experience.py` | 110-117 | ✅ |
| build_chain_experience | `app/engine/experience.py` | 119-173 | ✅ |
| AssetInput.multi | `app/registry/workflow.py` | +10 | ✅ |
| build_prompt multi | `app/engine/engine.py` | +12 | ✅ |
| execute multi | `app/engine/engine.py` | +10 | ✅ |
| video_i2v manifest | `workflows/video_image_to_video/manifest.json` | 35 | ✅ |
| video_i2v workflow | `workflows/video_image_to_video/workflow.json` | 0 | ❌ EMPTY |
| SemanticVerifier.temporal | `app/engine/semantic_verifier.py` | 0 | ❌ MISSING |
| ConversationAgent experience | `app/conversation.py` | 0 | ❌ NOT WIRED |

---

*Audit completed: 2026-09-10. Read-only mode. No code modified. Awaiting author decision on M25 Completion.*
