# MASTER DEVELOPMENT ROADMAP

**Версия:** 1.0
**Дата аудита:** 2026-09-05
**Статус:** AUDIT COMPLETE — единая карта эволюции системы
**Режим:** READ-ONLY — никаких изменений production-кода

---

## 0. Executive Summary

### Где система находится сейчас

ComfyUI Agent v1 — **Multimodal Agent Operator** поверх ComfyUI. Находится на границе **M25** (Experience Foundation).

**Фактическое состояние:**
- M1–M24: реализованы, протестированы, заморожены
- M25: инфраструктура реализована на ~80%, но **не полностью интегрирована в production-путь** и **не подтверждена реальным E2E**
- Всего 496+ тестов, 0 новых ошибок

**Что является фундаментом:**
- Media-agnostic execution pipeline (M1–M4)
- Conversation + LLM + Planning (M7–M9.1)
- Execution History + Retry + Semantic Verification (M13–M14)
- Multi-Step Decomposition + ExecutionChain (M18)
- Composer + CapabilityGraph (M19)
- Cluster Gateway + Reconciler (M20–M21)
- Decision Bridge + Parameter Adjustment + Feedback (M22–M24)

**Что заморожено:**
- AD-01..AD-42 (архитектурные решения)
- M1–M24 (milestone-контракты)
- Domain model: Asset, Capability, Provider, Workflow, Job, ExecutionPlan
- Provider ≠ Backend boundary
- Media-agnostic core invariant

**Текущая граница:** M25 Experience Foundation — инфраструктура создана, но не "замыкает цикл" в production.

**Куда движемся:** См. §15 (Proposed Future Milestones).

---

## 1. Project Evolution

### 1.1 M1 → Current: Хронология

| Период | Milestone | Ключевой результат |
|--------|-----------|-------------------|
| 2026-08-29 | M1–M6.5 | Execution pipeline, Asset, Registry, Provider, Video E2E, img2img |
| 2026-08-30 | M7–M9.1 | Conversation, Agent+LLM, UI, Context-aware Planner, upscale |
| 2026-08-31 | M10–M12 | Validation, Prompt Builder, Real UI E2E, ComfyCLI |
| 2026-09-01 | M13–M18 | History, Retry, Semantic Verify, Persistence, Adaptive, Feedback, Multi-Step |
| 2026-09-01 | Hardening | TD-1..TD-4 closed, 374 tests collected |
| 2026-09-03 | M19 | Composer + CapabilityGraph (Intent → Capability Planning) |
| 2026-09-03 | M20 | Cluster Gateway (Resource Layer) |
| 2026-09-03 | M21 | Reconciliation & Recovery (Reconciler) |
| 2026-09-04 | M22–M24 | Decision Bridge + Parameter Adjustment + Feedback-Driven Decision |
| 2026-09-04 | M25 design | Architecture proposal + review + implementation plan |
| 2026-09-04 | M25 impl | Experience, chain_id, multi-asset, sequence verification — реализовано |

---

## 2. Current Architecture

### 2.1 Фактический control flow (production)

```
User
  ↓
UI (app/ui.py)  →  POST /turn
  ↓
ConversationAgent.turn() (app/conversation.py)
  ├─ M18: TaskDecomposer.decompose() → subtasks → _execute_chain()
  └─ Single-step:
      ↓
      Planner.plan() (Heuristic/LLM)
      ↓
      Composer.compose() + CapabilityGraph (M19, optional)
      ↓
      Agent.prepare() → resolve_asset_inputs()
      ↓
      WorkflowEngine.execute() → Provider → ComfyUI
      ↓
      WebSocket tracking → /history fallback
      ↓
      Verifier.verify() → AssetStore.ingest() → lineage
      ↓
      SemanticVerifier (M14, optional)
      ↓
      RetryPolicy.decide() → RETRY/ACCEPT/FAILED/ASK_USER
      ↓
      ExecutionHistory.record() + dispatch tracking
      ↓
      SSE events → UI
```

### 2.2 Компоненты и их статус

| Компонент | Файл | Статус | Milestone |
|-----------|------|--------|-----------|
| `ComfyClient` | `app/comfy/client.py` | ✅ FROZEN | M1 |
| `RuntimeInfo` | `app/registry/runtime.py` | ✅ FROZEN | M1 |
| `Asset` + `AssetStore` | `app/assets/` | ✅ FROZEN | M2 |
| `CapabilityRegistry` | `app/registry/capability.py` | ✅ FROZEN | M3 |
| `WorkflowRegistry` | `app/registry/` | ✅ FROZEN | M3 |
| `WorkflowEngine` | `app/engine/engine.py` | ✅ FROZEN+M25 ext | M4/M25 |
| `ComfyUIProvider` | `app/provider/comfyui.py` | ✅ FROZEN | M5 |
| `ConversationContext` | `app/conversation.py` | ✅ FROZEN | M7 |
| `ConversationAgent` | `app/conversation.py` | ✅ FROZEN | M7/M9 |
| `Planner` (Heuristic/LLM) | `app/planner/` | ✅ FROZEN | M8/M9.1 |
| `PromptBuilder` (3-layer) | `app/prompt/` | ✅ FROZEN | M11 |
| `ComfyUIProcessManager` | `app/comfy/lifecycle.py` | ✅ FROZEN | M12 |
| `ComfyCLIAdapter` | `app/infrastructure/` | ✅ FROZEN | M12.1 |
| `ExecutionHistory` | `app/engine/history.py` | ✅ FROZEN+M25 ext | M13/M25 |
| `RetryPolicy` | `app/engine/retry.py` | ✅ FROZEN | M13/M22/M23/M24 |
| `SemanticVerifier` | `app/engine/semantic_verifier.py` | ✅ FROZEN | M14 |
| `SessionManager` | `app/context/` | ✅ FROZEN | M15 |
| `AdaptivePlanner` | `app/planner/adaptive.py` | ✅ FROZEN | M16 |
| `FeedbackStore` | `app/context/feedback.py` | ✅ FROZEN (dead wiring) | M17 |
| `TaskDecomposer` | `app/planner/decomposer.py` | ✅ FROZEN | M18 |
| `ExecutionChain` | `app/engine/chain.py` | ✅ FROZEN | M18 |
| `Composer` | `app/planner/composer.py` | ✅ FROZEN | M19 |
| `CapabilityGraph` | `app/planner/capability_graph.py` | ✅ FROZEN | M19 |
| `ClusterGateway` | `app/resource/gateway.py` | ✅ FROZEN | M20 |
| `Reconciler` | `app/resource/reconciler.py` | ✅ FROZEN | M21 |
| `CorrectionStrategy` | `app/engine/retry.py` | ✅ FROZEN | M23 |
| `ChainExperience` | `app/engine/experience.py` | ⚠️ IMPLEMENTED, not wired | M25.4 |
| `Verifier.verify_sequence()` | `app/engine/verifier.py` | ⚠️ IMPLEMENTED, not wired | M25.3 |
| `Engine._build_multi_asset_input()` | `app/engine/engine.py` | ⚠️ IMPLEMENTED, not wired | M25.2 |

### 2.3 Критическое наблюдение: M25 wiring gap

**M25 infrastructure exists but is NOT wired into production execution path:**

1. **`chain_id` в Job/ExecutionRecord** — поля существуют, `get_by_chain()` реализован, но `conversation.py` и `chain.py` **никогда не генерируют chain_id** и не проставляют его в Job.
2. **`Verifier.verify_sequence()`** — реализован, но `conversation.py` **никогда не вызывает** его после video-шагов.
3. **`ExperienceStore`** — реализован, но `conversation.py` **никогда не вызывает** `build_chain_experience()` после chain completion.
4. **`Engine._build_multi_asset_input()`** — реализован, `AssetInput.multi` поддерживается, но реальный E2E с multi-asset → video **не прогнан**.
5. **`FeedbackStore` → AdaptivePlanner/RetryPolicy** — `feedback_store` существует как параметр, но **не передаётся** из `conversation.py` в production (dead code, подтверждено `docs/28_LEARNING_ARCHITECTURE_AUDIT.md`).

---

## 3. Frozen Architecture

### 3.1 Architectural Decisions (не нарушать)

| ID | Решение | Источник | Статус |
|----|---------|----------|--------|
| AD-01 | Provider ≠ Execution Backend | PROJECT_SPEC §24 | FROZEN |
| AD-02 | Asset Transport вынесен из WorkflowEngine | PROJECT_SPEC §24 | FROZEN |
| AD-03 | Media-agnostic core | PROJECT_SPEC §24 | FROZEN |
| AD-04 | Manifest-маппинг | PROJECT_SPEC §24 | FROZEN |
| AD-05 | Workflow Lifecycle | PROJECT_SPEC §24 | FROZEN |
| AD-06 | v1 на image-workflows, ядро media-agnostic | PROJECT_SPEC §24 | FROZEN |
| AD-07 | No-WAN coupling | PROJECT_SPEC §24 | FROZEN |
| AD-08 | LLM через OpenAI-совместимый endpoint | PROJECT_SPEC §24 | FROZEN |
| AD-09 | Model = свойство Provider | PROJECT_SPEC §24 | FROZEN |
| AD-10 | Multi-stage = цепь Job | PROJECT_SPEC §24 | FROZEN |
| AD-11 | Selection policy | PROJECT_SPEC §24 | FROZEN |
| AD-12 | Custom-node фильтр | PROJECT_SPEC §24 | FROZEN |
| AD-13 | Lineage на Asset+Job | PROJECT_SPEC §24 | FROZEN |
| AD-14 | No-LLM-first | PROJECT_SPEC §24 | FROZEN |
| AD-15 | Storage | PROJECT_SPEC §24 | FROZEN |
| AD-16 | Real E2E only | PROJECT_SPEC §24 | FROZEN |
| AD-17 | Version pinning | PROJECT_SPEC §24 | FROZEN |
| AD-18 | UNKNOWN ≠ AVAILABLE | PROJECT_SPEC §24 | FROZEN |
| AD-19 | Cancellation semantics | PROJECT_SPEC §24 | FROZEN |
| AD-20 | Temp ownership | PROJECT_SPEC §24 | FROZEN |
| AD-21 | Capability-aware limits | PROJECT_SPEC §24 | FROZEN |
| AD-22 | Selection split | PROJECT_SPEC §24 | FROZEN |
| AD-23 | Input compatibility | PROJECT_SPEC §24 | FROZEN |
| AD-24 | latest-selection | PROJECT_SPEC §24 | FROZEN |
| AD-25 | limits semantics | PROJECT_SPEC §24 | FROZEN |
| AD-26 | BackendRef abstraction | PROJECT_SPEC §24 | FROZEN |
| AD-27 | DECLARED_ONLY | PROJECT_SPEC §24 | FROZEN |
| AD-28 | Doc hierarchy | PROJECT_SPEC §24 | FROZEN |
| AD-29 | Physical location ≠ Agent concern | PROJECT_SPEC §27 | FROZEN |
| AD-30 | PromptBuilder boundary/security | PROJECT_SPEC §24 | FROZEN |
| AD-31 | PromptBuilder не выбирает capability | PROJECT_SPEC §24 | FROZEN |
| AD-32 | PromptBuilder сохраняет intent | PROJECT_SPEC §24 | FROZEN |
| AD-33 | ComfyCLI: shell=False | PROJECT_SPEC §24 | FROZEN |
| AD-34 | ComfyCLI: optional | PROJECT_SPEC §24 | FROZEN |
| AD-36 | AdaptivePlanner per-capability threshold ≥3 | DECISION_LOG | FROZEN |
| AD-37 | Experience as Data, Not Engine | M25_PROPOSAL | PROPOSED |
| AD-38 | Sequence as Metadata, Not Type | M25_PROPOSAL | PROPOSED |
| AD-39 | Multi-Asset via Manifest Flag | M25_PROPOSAL | PROPOSED |
| AD-40 | Intent → Capability Planning Direction | DECISION_LOG | FROZEN |
| AD-41 | Composer architecture | DECISION_LOG | FROZEN |
| AD-42 | Cluster Gateway: Routing ≠ Failover | DECISION_LOG | FROZEN |

### 3.2 Domain Model (frozen)

```text
Asset ≠ File              Asset = media object, type is string
Capability ≠ Workflow      Capability = logical ability
Provider ≠ Model           Provider = access abstraction
Provider ≠ Backend         Provider = logical, Backend = physical location
Workflow ≠ Node Graph      LLM never sees node-ids
ComfyUI ≠ Agent            Agent operates through Operator only
```

### 3.3 Что future work must NOT violate

1. No `if image/elif video` in core execution (engine, job, verifier, asset)
2. LLM never has direct ComfyUI HTTP access
3. Agent never calls ComfyUI directly (only through Provider/Operator)
4. ExecutionPlan always fixes `workflow_id@version` (never `latest`)
5. UNKNOWN compatibility ≠ AVAILABLE
6. Provider never selects workflow
7. Workflow Registry never "smart agent" — only storage + filter
8. Physical backend location never affects domain logic

---

## 4. Milestone Status

### 4.1 Полная таблица M1 → Current

| Milestone | Название | Code | Tests | Real E2E | Frozen | Evidence |
|-----------|----------|------|-------|----------|--------|----------|
| M1 | Runtime + Client | ✅ | ✅ 8/8 | ✅ | ✅ | `app/comfy/client.py`, `test_m1_runtime.py` |
| M2 | Asset Layer | ✅ | ✅ 9/10 | ✅ | ✅ | `app/assets/`, `test_m2_asset.py` |
| M3 | Capability + Workflow Registry | ✅ | ✅ 23/23 | N/A | ✅ | `app/registry/`, `test_m3_registry.py` |
| M4 | Execution Chain | ✅ | ✅ | ✅ (local) | ✅ | `app/engine/engine.py`, `test_m4_execution.py` |
| M5 | Provider / Model / Remote | ✅ | ✅ | ✅ (Colab T4) | ✅ | `app/provider/`, `test_remote_e2e.py` |
| M6 | Real Video E2E | ✅ | ✅ | ✅ (Colab T4) | ✅ | `workflows/video_generate/`, `test_video_e2e.py` |
| M6.5 | Image Input / img2img | ✅ | ✅ | ✅ (Colab T4) | ✅ | `workflows/img2img/`, `test_img2img_e2e.py` |
| M7 | Conversation Context | ✅ | ✅ 7/8 | ✅ offline | ✅ | `app/conversation.py`, `test_conversation_m7.py` |
| M8 | Agent + LLM | ✅ | ✅ 8/8 | ✅ offline | ✅ | `app/agent.py`, `test_agent.py` |
| M9 | UI | ✅ | ✅ 5/5 | ✅ offline | ✅ | `app/ui.py`, `test_ui_m9.py` |
| M9.1 | Context-aware Planner | ✅ | ✅ 11/11 | ✅ offline | ✅ | `app/planner/`, `test_planner_context.py` |
| — | image.upscale | ✅ | ✅ 5/6 | ✅ (Colab T4) | ✅ | `workflows/upscale/`, `test_upscale.py` |
| M10 | Validation | ✅ | ✅ 6/7 | ✅ (6/7 remote) | ✅ | Multiple test files |
| — | Progress Hook | ✅ | ✅ 7/7 | ✅ | ✅ | `test_progress.py` |
| M11 | Prompt Builder | ✅ | ✅ 44+ | ✅ offline | ✅ | `app/prompt/`, `test_prompt_builder*.py` |
| M12 | Real UI E2E | ✅ | ✅ 10 | ✅ offline | ✅ | `test_ui_m12.py` |
| M12.1 | ComfyCLI Adapter | ✅ | ✅ 34 | N/A | ✅ | `app/infrastructure/`, `test_comfy_cli_adapter.py` |
| M13 | Execution History + Retry | ✅ | ✅ 32 | ✅ offline | ✅ | `app/engine/history.py`, `retry.py`, `test_m13_history_retry.py` |
| M14 | Semantic Verification | ✅ | ✅ 23 | ⚠️ needs API key | ✅ | `app/engine/semantic_verifier.py`, `test_m14_semantic_verification.py` |
| M15 | Persistent Context | ✅ | ✅ 14 | ✅ offline | ✅ | `app/context/`, `test_m15_persistent_context.py` |
| M16 | Adaptive Planner | ✅ | ✅ 16 | ✅ offline | ✅ | `app/planner/adaptive.py`, `test_m16_adaptive_planner.py` |
| M17 | User Feedback | ✅ | ✅ 11 | ⚠️ dead wiring | ✅ | `app/context/feedback.py`, `test_m17_user_feedback.py` |
| M18 | Multi-Step Decomposition | ✅ | ✅ 17+8 | ✅ real E2E | ✅ | `app/planner/decomposer.py`, `chain.py`, `test_m18_*.py` |
| M19 | Composer + CapabilityGraph | ✅ | ✅ 53+ | ✅ real E2E | ✅ | `app/planner/composer.py`, `test_m19_*.py` |
| M20 | Cluster Gateway | ✅ | ✅ 10+ | ✅ offline | ✅ | `app/resource/gateway.py`, `test_m20_cluster_gateway.py` |
| M21 | Reconciliation & Recovery | ✅ | ✅ 31 | ✅ real E2E | ✅ | `app/resource/reconciler.py`, `test_m21_*.py` |
| M22 | Decision Bridge | ✅ | ✅ 14 | ✅ offline | ✅ | `app/engine/retry.py`, `test_m22_decision_bridge.py` |
| M23 | Parameter Adjustment | ✅ | ✅ 35 | ✅ offline | ✅ | `app/engine/retry.py`, `test_m23_parameter_adjustment.py` |
| M24 | Feedback-Driven Decision | ✅ | ✅ 21 | ⚠️ dead wiring | ✅ | `app/engine/retry.py`, `test_m24_*.py` |
| **M25** | **Experience Foundation** | **⚠️ ~80%** | **⚠️ unit only** | **❌ NOT PROVEN** | **❌ NOT FROZEN** | `app/engine/experience.py`, `verifier.py`, `engine.py` |

### 4.2 M25 Detailed Status

| Phase | Компонент | Code | Tests | Production Wired | Real E2E |
|-------|-----------|------|-------|-----------------|----------|
| M25.1 | Chain Identity (`chain_id`) | ✅ | ✅ unit | ❌ NOT WIRED | ❌ |
| M25.2 | Multi-Asset + Sequence | ✅ | ✅ unit | ❌ NOT WIRED | ❌ |
| M25.3 | Sequence Verification | ✅ | ✅ unit | ❌ NOT WIRED | ❌ |
| M25.4 | Experience Model | ✅ | ✅ unit | ❌ NOT WIRED | ❌ |

**M25 Real E2E Status:** `tests/_m25_e2e_runner.py` и `tests/_m25_smoke_check.py` существуют, но **никогда не запускались** на реальном ComfyUI. Smoke check заблокирован окружением (SteadIP Windows Access Denied, `docs/M25_STADIP_AUDIT_PHASE1.md`).

---

## 5. Legacy Roadmap Preservation

### 5.1 Направления из FUTURE_ROADMAP_ARCHITECTURE.md (M13–M18)

| Legacy Plan | Status | New Mapping |
|-------------|--------|-------------|
| M13 Execution History + Retry | ✅ IMPLEMENTED & FROZEN | M13 |
| M14 Semantic Verification | ✅ IMPLEMENTED & FROZEN | M14 |
| M15 Persistent Context | ✅ IMPLEMENTED & FROZEN | M15 |
| M16 Adaptive Planner | ✅ IMPLEMENTED & FROZEN | M16 |
| M17 User Feedback | ✅ IMPLEMENTED & FROZEN | M17 |
| M18 Multi-Step Decomposition | ✅ IMPLEMENTED & FROZEN | M18 |

### 5.2 Направления из DEVELOPMENT_PLAN_M13_M18.md

Все реализованы как M13–M18. Документ `docs/DEVELOPMENT_PLAN_M13_M18.md` — исторический, не переписывать.

### 5.3 Предложенные направления M26–M30 (из ранних обсуждений)

| Legacy Plan | Status | Notes |
|-------------|--------|-------|
| M26 Model Knowledge Foundation | ❌ NOT STARTED | Superseded by M25 Experience-first approach |
| M27 Model Discovery / Registry | ❌ NOT STARTED | Model Registry exists (M5), but Model Knowledge — future |
| M28 Model Selection | ❌ NOT STARTED | Requires Experience foundation first |
| M29 Model Experience | ❌ NOT STARTED | Requires Experience foundation first |
| M30 Contextual Model Selection | ❌ NOT STARTED | Requires Experience foundation first |

**Решение:** M26–M30 — **предложенное направление (DRAFT), не утверждённый план**. После M25 Experience Foundation необходимо пересмотреть на основе реального опыта.

### 5.4 Superseded / Rejected Directions

| Direction | Status | Reason |
|-----------|--------|--------|
| Rating-based learning (1–5 → permanent ban) | ❌ REJECTED | Superseded by Experience model (context + action + outcome) |
| LearningEngine class | ❌ REJECTED | AD-37: Experience = data, not engine |
| SequenceExperience as separate entity | ❌ REJECTED | M25_REVIEW: merged into ChainExperience |
| Semantic temporal verification in M25 | ❌ DEFERRED | Requires multi-image SemanticVerifier → M26+ |
| PlanContext changes for Experience | ❌ REJECTED | M9.1 frozen; use ExecutionHistory path |
| Pillow dependency for image processing | ❌ REJECTED | No image processing in M25 |
| ComfyCLIAdapter as M12 | ❌ SUPERSEDED | M12 = Real UI E2E; ComfyCLI = M12.1 |

---

## 6. Current Gaps

### 6.1 CRITICAL (блокируют дальнейшее развитие)

| # | Проблема | Доказательство | Затрагивает | Риск |
|---|----------|---------------|-------------|------|
| G1 | M25 chain_id не генерируется в production | `search_files` по `chain_id` в `app/` = 0 результатов | M25.1, M25.4 | Experience не работает |
| G2 | M25 verify_sequence не вызывается после video | `conversation.py` не вызывает `verify_sequence()` | M25.3 | Sequence не верифицируется |
| G3 | M25 Experience не строится после chain | `conversation.py` не вызывает `build_chain_experience()` | M25.4 | Experience не сохраняется |
| G4 | Feedback → AdaptivePlanner dead wiring | `docs/28_LEARNING_ARCHITECTURE_AUDIT.md` | M17, M24 | Feedback не влияет на planning |

### 6.2 HIGH (архитектурно значимые)

| # | Проблема | Доказательство | Затрагивает |
|---|----------|---------------|-------------|
| G5 | M25 Real E2E не подтверждён | `docs/M25_STADIP_AUDIT_PHASE1.md` (blocked), `_m25_e2e_runner.py` не запускался | M25 все фазы |
| G6 | `docs/25_M21_RECONCILIATION_RECOVERY.md` устарел | Утверждает "Reconciler не существует", но `app/resource/reconciler.py` существует | Документация |
| G7 | Audio real E2E заблокирован | Sonilo HTTP 401 | M6 audio |
| G8 | Capabilities без workflow | `image.inpaint`, `video.upscale`, `custom.execute` — нет workflow.json | Extensibility |

### 6.3 MEDIUM (quality/maintainability)

| # | Проблема | Доказательство |
|---|----------|---------------|
| G9 | `PROJECT_SPEC.md` §22 не содержит M13–M24 | `docs/PROJECT_STATE_2026-09-01.md` §3.1 |
| G10 | `docs/18_DEFINITION_OF_DONE.md` нет DoD для M13–M24 | Проверка файла |
| G11 | `docs/24_CLUSTER_GATEWAY_DESIGN_AUDIT.md` статус "БЕЗ production-кода" | Код существует (gateway.py, reconciler.py) |
| G12 | Semantic intent validation консервативная (≥50% keywords) | `app/prompt/llm.py` `_check_intent_preserved()` |

### 6.4 LOW (можно отложить)

| # | Проблема |
|---|----------|
| G13 | `ComfyUIProcessManager` не интегрирован в UI как diagnostics panel |
| G14 | `BackendCatalog.choose` не использует `probe` для live VRAM selection |
| G15 | Нет concurrency tests для параллельных сессий |
| G16 | `Asset.metadata` не заполняется при ingest (size/hash) |

---

## 7. Technical Debt

### 7.1 By Priority

| # | Debt | Severity | Milestone | Можно отложить? | Блиокирует roadmap? |
|---|------|----------|-----------|-----------------|-------------------|
| TD-1 | M25 production wiring (chain_id, verify_sequence, experience) | CRITICAL | M25 | Нет | Да — M25 не завершён |
| TD-2 | Feedback dead wiring (AdaptivePlanner, RetryPolicy) | HIGH | M17/M24 | Нет | Да — learning loop не замкнут |
| TD-3 | M25 Real E2E not proven | HIGH | M25 | Нет | Да — M25 не может быть frozen |
| TD-4 | Docs resync (PROJECT_SPEC §22, M21 design doc, Gateway design doc) | MEDIUM | — | Да | Нет |
| TD-5 | Audio E2E blocked (Sonilo 401) | MEDIUM | M6 | Да (external) | Нет |
| TD-6 | Stale test asserts (6 failures in test_prompt_builder.py) | LOW | M11 | Да | Нет |
| TD-7 | ~54 tests not collectable (Python 3.14 stdout hack removed, but some remain) | LOW | M11/M12 | Да | Нет |

---

## 8. Experience Architecture

### 8.1 Концептуальная модель

```
Intent → Prompt → Image₁ → Image₂ → ... → Video → Result → Experience
  │         │        │        │              │        │
  │         │        │        │              │        └─ ChainExperience (факт)
  │         │        │        │              └─ Video Asset (sequence input)
  │         │        │        └─ Image Asset (lineage chain)
  │         │        └─ Image Asset (lineage)
  │         └─ enhanced_prompt (PromptBuilder)
  └─ user request
```

### 8.2 Текущее состояние vs Целевое

| Transition | Текущее состояние | Целевое состояние |
|------------|-------------------|-------------------|
| Intent → Prompt | ✅ PromptBuilder (M11) | ✅ Работает |
| Prompt → Asset | ✅ WorkflowEngine (M4) | ✅ Работает |
| Asset → Next Prompt | ✅ active_asset + resolve_asset_inputs (M7) | ✅ Работает |
| Asset → Asset (lineage) | ✅ source_asset (M2) | ✅ Работает |
| Assets → Sequence | ⚠️ metadata exists, logic missing | Sequence grouping in conversation.py |
| Sequence → Video | ⚠️ workflow exists, not wired | video.image_to_video via multi-asset |
| Video → Result | ✅ Job.output_assets | ✅ Работает |
| Result → Experience | ⚠️ ExperienceStore exists, not called | Auto-record on chain complete |
| Experience → Planning | ⚠️ AdaptivePlanner exists, no experience input | Chain-aware preferred_params |

### 8.3 Принцип Experience (AD-37)

**Experience ≠ permanent rule.**
**Experience = факт о выполненном media workflow, сохранённый для последующего анализа.**

- Не ML/fine-tuning/vector-RAG
- Не "rating 1 → permanent ban"
- А: `context + action + model + workflow + parameters + input + result + correction + outcome → Experience → future contextual recommendation`

---

## 9. Model Intelligence Roadmap

### 9.1 Текущее состояние

Model Registry существует с M5 (`app/registry/model.py`):
- `ModelInfo` (точное имя, backend_id, kind)
- `ModelRegistry` (per-backend каталог)
- `discover(client, backend_id)` — runtime discovery из `/object_info`
- `resolve`, `compatibility` — per-backend

### 9.2 Что отсутствует (Model Knowledge)

| Компонент | Статус | Зависимость |
|-----------|--------|-------------|
| Model identity (version, provider) | ❌ | Experience |
| Model capabilities (inputs/outputs) | ❌ | Experience |
| Model constraints (VRAM, precision) | ⚠️ partial (requirements in manifest) | — |
| Model workflow compatibility | ⚠️ partial (required_models) | — |
| Model observed behaviour | ❌ | Experience |
| Model experience (success/failure per context) | ❌ | M25 Experience |

### 9.3 Предлагаемая последовательность

```
M25 Experience Foundation (текущая граница)
  ↓
M26 Model Knowledge (identity, capabilities, constraints)
  ↓
M27 Model Experience (observed behaviour per context)
  ↓
M28 Contextual Model Selection (task → model based on experience)
  ↓
M29 Model Workflow Selection (model + task → optimal workflow)
```

**Принцип:** Модель должна стать operational object с полным набором атрибутов (identity, version, provider, capabilities, inputs, outputs, parameters, constraints, workflow compatibility, runtime requirements, observed behaviour, experience). Но это **невозможно до появления Experience**.

---

## 10. Media Intelligence Roadmap

### 10.1 Текущее состояние

| Media | Generate | Edit | Upscale | Sequence | Video |
|-------|----------|------|---------|----------|-------|
| Image | ✅ txt2img | ✅ img2img | ✅ upscale | ⚠️ metadata only | — |
| Video | ✅ video_generate | ❌ | ❌ | — | ⚠️ i2v workflow exists |
| Audio | ⚠️ code only | ❌ | ❌ | — | — |

### 10.2 Dependency Chain

```
Image Generation (M1–M6, ✅)
  ↓
Image Editing (M6.5, ✅)
  ↓
Image Sequence (M25.2, ⚠️ infrastructure)
  ↓
Image → Video (M25.2, ⚠️ workflow exists)
  ↓
Temporal Consistency (M25.3, ⚠️ deterministic only)
  ↓
Animation-Aware Image Generation (future, ❌)
  ↓
Experience-Driven Media Selection (future, ❌)
```

### 10.3 Принцип

Не внедрять semantic temporal learning сейчас. Сначала:
1. Замкнуть M25 Experience loop (chain_id → experience → persistence)
2. Накопить реальные данные о sequence → video
3. На основе данных определить паттерны

---

## 11. Learning Roadmap

### 11.1 Текущая архитектура обучения

| Компонент | Статус | Что делает | Production |
|-----------|--------|-----------|------------|
| `ExecutionHistory` | ✅ FROZEN | Per-execution audit trail | ✅ Wired |
| `HistoryAnalytics` | ✅ FROZEN | success_rate, preferred_params | ⚠️ Partial (no feedback filter) |
| `AdaptivePlanner` | ✅ FROZEN | Learns from history ≥3 | ⚠️ No feedback_store |
| `FeedbackStore` | ✅ FROZEN | User ratings 1–5 | ❌ Dead wiring |
| `RetryPolicy` | ✅ FROZEN | CorrectionStrategy, ask_user | ⚠️ No feedback_store |
| `ChainExperience` | ⚠️ M25 | Chain-level experience | ❌ Not wired |

### 11.2 Предлагаемая последовательность

```
M25 Experience (chain_id → experience → persistence)
  ↓
M26 Feedback Wiring (feedback_store → AdaptivePlanner + RetryPolicy)
  ↓
M27 Experience Analysis (chain-aware preferred_params)
  ↓
M28 Contextual Recommendation (context + experience → params/workflow)
  ↓
M29 Adaptive Behaviour (convergence: successful params → preferred → default)
```

### 11.3 Принцип (AD-37)

- **НЕ** rating 1 → permanent ban
- **А:** context + action + model + workflow + parameters + input + result + correction + outcome → Experience → future contextual recommendation
- Experience = факт, не правило
- Learning = aggregate statistics, не self-modification (NG3)
- Нет LearningEngine класса — композиция существующих компонентов

---

## 12. Execution Environment Strategy

### 12.1 Реальные среды (из аудита)

| Environment | Real E2E | What it exposed | Architectural lesson |
|-------------|----------|-----------------|---------------------|
| Local ComfyUI / AMD DirectML | ✅ M4, M10 | 1GB VRAM OOM, slow first gen, WS timeout | `--lowvram`, history fallback, 5min poll |
| Remote ComfyUI / Colab Tesla T4 | ✅ M5, M6, M6.5, M10 | Cloudflare tunnel, WS via wss | AD-29: remote = first-class backend |
| SteadIP tunnel | ❌ Blocked | Windows Access Denied (WinError 5) | External I/O = separate module |
| FRP tunnel | ❌ Audit only | Oracle VPS, integration point identified | External I/O = separate module |

### 12.2 Стратегия

- **Local ComfyUI:** primary development + validation environment
- **Remote ComfyUI (Colab):** secondary, for GPU-heavy tasks (video, large images)
- **External I/O (FRP/SteadIP/Cloud):** отдельный заменяемый модуль, НЕ в core
- **Multi-backend selection:** отложить до накопления реального опыта на разных исполнителях

---

## 13. Future External I/O Boundary

### 13.1 Принцип

External I/O должен быть **отдельным заменяемым модулем/границей**. Core не должен знать о Colab, FRP, Cloud.ru, Agnes, конкретном HTTP transport, конкретной cloud platform.

### 13.2 Архитектурное место

```
┌─────────────────────────────────────────────────────────┐
│                      CORE                                │
│  Agent → Planner → Composer → ExecutionChain →          │
│  WorkflowEngine → Provider → BackendRef                 │
│                                                          │
│  Core знает: capability, workflow, asset, job,          │
│  provider abstraction, backend_id, base_url              │
└────────────────────────────┬────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────┐
│                 EXTERNAL I/O LAYER                       │
│  (transport, auth, upload, download, polling,           │
│   websocket, reconnect, timeout, remote errors,         │
│   result normalization)                                  │
│                                                          │
│  Этот слой потенциально отвечает за:                     │
│  - tunnel management (FRP, SteadIP, ngrok, cloudflare)  │
│  - authentication (API keys, tokens)                    │
│  - asset upload/download (multipart, streaming)         │
│  - job submission (HTTP POST, queue management)         │
│  - status polling (HTTP GET, websocket)                 │
│  - reconnect logic (exponential backoff)                │
│  - remote error normalization                           │
│  - result download + verification                       │
└─────────────────────────────────────────────────────────┘
```

### 13.3 Что НЕ делать в этом аудите

- ❌ Не проектировать External I/O module
- ❌ Не реализовывать FRP/SteadIP/ngrok integration
- ❌ Не создавать новые классы для external transport
- ❌ Не менять Provider/Backend boundary

### 13.4 Когда проектировать

После накопления реального опыта на разных исполнителях (минимум 2–3 разных среды с реальным E2E).

---

## 14. Dependency Graph

### 14.1 Основная цепь зависимостей

```
M25 Experience Foundation (текущая граница, ~80%)
  │
  ├── M25.1 Chain Identity ─── chain_id wiring ──────────────────┐
  ├── M25.2 Multi-Asset ────── video.image_to_video E2E ────────┤
  ├── M25.3 Sequence Verify ── verify_sequence wiring ──────────┤
  └── M25.4 Experience ─────── build_chain_experience wiring ───┘
                              │
                              ▼
                    M25 REAL E2E VALIDATION
                              │
                              ▼
                    M25 FROZEN
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
    M26 Feedback        M26 Model           M26 External
    Wiring              Knowledge           I/O Preparation
          │                   │                   │
          ▼                   ▼                   ▼
    M27 Experience      M27 Model           M27 External
    Analysis            Experience          I/O Design
          │                   │                   │
          ▼                   ▼                   ▼
    M28 Contextual      M28 Contextual       M28 External
    Recommendation      Model Selection      I/O Implementation
          │                   │                   │
          └───────────────────┼───────────────────┘
                              ▼
                    M29 Adaptive Behaviour
                              │
                              ▼
                    M30 Media Intelligence
```

### 14.2 Параллельные workstreams

После M25 FROZEN, можно параллельно:
- **Learning stream:** Feedback wiring → Experience analysis → Contextual recommendation
- **Model stream:** Model Knowledge → Model Experience → Contextual Model Selection
- **External stream:** Real E2E on multiple environments → External I/O design

---

## 15. Proposed Future Milestones

### 15.1 M25 Completion (NEXT — текущий приоритет)

**Purpose:** Замкнуть M25 Experience loop в production и доказать реальным E2E.

**Dependencies:** Нет (инфраструктура уже создана).

**Scope:**
1. Генерация `chain_id` в `ExecutionChain.execute()` и `conversation.py`
2. Проставление `chain_id` в каждый Job/ExecutionRecord в chain
3. Вызов `Verifier.verify_sequence()` после video-шагов
4. Вызов `build_chain_experience()` + `ExperienceStore.record()` после chain completion
5. Real E2E: image → image → video → experience → persistence → restart → query

**Non-goals:**
- Semantic temporal verification (M26+)
- Experience → Planning integration (M26+)
- Multi-image SemanticVerifier (M26+)

**Prerequisites:**
- Доступ к реальному ComfyUI (local или remote) с установленными VHS нодами (CreateVideo, SaveVideo, ImageBatch)

**Verification:**
- Unit tests: chain_id propagation, experience building, sequence verification
- Integration tests: full chain → experience → persistence → reconstruction
- Real E2E: 2–3 images → video → ChainExperience persisted → restart → queryable

**Exit criteria:**
- [ ] `chain_id` генерируется и проставляется в production
- [ ] `verify_sequence()` вызывается после video-шагов
- [ ] `build_chain_experience()` вызывается после chain completion
- [ ] Real E2E: image sequence → video → experience → persistence → restart → query PASSED
- [ ] M25 FROZEN

---

### 15.2 M26: Feedback Wiring + Experience Analysis

**Purpose:** Замкнуть feedback loop и начать анализ experience.

**Dependencies:** M25 FROZEN.

**Scope:**
1. Интеграция `feedback_store` в `AdaptivePlanner` и `RetryPolicy` в production
2. `HistoryAnalytics._filter_by_feedback()` активен (rating < 4 исключаются из preferred_params)
3. Chain-aware analytics: `preferred_params_for_chain(chain_id)`
4. Experience → Planning: AdaptivePlanner читает ChainExperience для context-aware params

**Non-goals:**
- Automatic parameter changes (только statistics)
- Cross-session experience aggregation
- Model Knowledge

**Verification:**
- Unit tests: feedback filtering, chain-aware analytics
- Integration tests: feedback → planning → adjusted params → success
- Real E2E: user rates result → next attempt uses adjusted params

**Exit criteria:**
- [ ] Feedback wired in production (conversation.py passes feedback_store)
- [ ] Chain-aware preferred_params works
- [ ] Experience → Planning path functional

---

### 15.3 M27: Model Knowledge Foundation

**Purpose:** Превратить Model в operational object с полным набором атрибутов.

**Dependencies:** M25 Experience (для observed behaviour).

**Scope:**
1. Model identity: version, provider, family
2. Model capabilities: inputs, outputs, parameters, constraints
3. Model workflow compatibility: which workflows work with this model
4. Model observed behaviour: success rate, typical quality, common failures
5. Model experience: per-context success/failure

**Non-goals:**
- Model Selection (M28)
- Model auto-downloading
- Model fine-tuning

**Verification:**
- Unit tests: model identity, capability queries
- Integration tests: model → workflow compatibility check
- Real E2E: model metadata populated from real execution

---

### 15.4 M28: Contextual Model + Workflow Selection

**Purpose:** Выбирать model и workflow на основе experience и контекста задачи.

**Dependencies:** M26 (Feedback + Experience Analysis), M27 (Model Knowledge).

**Scope:**
1. Task → Model mapping based on experience
2. Task → Workflow mapping based on experience
3. Context-aware selection: "для анимации этот model работает лучше"
4. Fallback: HeuristicPlanner when experience insufficient

**Non-goals:**
- Automatic model switching mid-execution
- Multi-model workflows

---

### 15.5 M29: External I/O Module

**Purpose:** Поддержка внешних execution environments как отдельный заменяемый модуль.

**Dependencies:** Реальный опыт на нескольких исполнителях (минимум 2–3).

**Scope:**
1. External I/O boundary design
2. Transport abstraction (HTTP, WebSocket, tunnel)
3. Authentication management
4. Asset upload/download
5. Job submission + status polling
6. Reconnect + error recovery
7. Result normalization

**Non-goals:**
- Core changes
- Specific cloud platform coupling
- Distributed execution orchestration

---

### 15.6 M30: Media Intelligence

**Purpose:** Animation-aware image generation, temporal consistency optimization.

**Dependencies:** M25 Experience (sequence data), M28 (Model Selection).

**Scope:**
1. Image characteristics → animation suitability
2. Sequence consistency → model/workflow choice
3. Temporal consistency measurement (semantic, multi-image)
4. Experience-driven media planning

**Non-goals:**
- Full video editing
- Audio-visual synchronization
- Real-time generation

---

## 16. Parallel Workstreams

После M25 FROZEN, можно развивать параллельно (не ломая core):

### Stream A: Learning
```
M26 Feedback Wiring → M27 Experience Analysis → M28 Contextual Recommendation
```

### Stream B: Models
```
M27 Model Knowledge → M28 Model Experience → M29 Contextual Model Selection
```

### Stream C: External I/O
```
Real E2E on multiple environments → M29 External I/O Design → M30 External I/O Implementation
```

### Stream D: Media
```
M30 Temporal Verification (semantic) → M31 Animation-Aware Generation
```

**Изоляция:** Каждый stream работает в своей директории (`app/learning/`, `app/model/`, `app/external/`, `app/media/`) и не меняет core contracts.

---

## 17. Deferred Work

| Что | Почему откладено | Когда рассмотреть |
|-----|-----------------|-------------------|
| Semantic temporal verification | Требует multi-image SemanticVerifier | M30 |
| Cross-session experience aggregation | Требует shared ExecutionHistory (design decision) | M27+ |
| Automatic parameter tuning | AdaptivePlanner уже делает это (stats) | M26+ |
| LLMPlanner real integration | Требует API key + production testing | M26+ |
| Concurrency tests | Многопользовательность — future | M27+ |
| Persistence context (DB) | JSONL достаточно для v1 | M28+ |
| image.inpaint workflow | Не критично для core | M27+ |
| video.upscale workflow | Не критично для core | M28+ |
| custom.execute workflow | Не критично для core | M28+ |
| Audio real E2E | Внешняя зависимость Sonilo (401) | Когда доступен ключ/модель |
| ComfyUIProcessManager diagnostics panel | Infrastructure, не core | M26+ |
| BackendCatalog.choose live probe | Требует реального multi-backend | M29+ |

---

## 18. Superseded Work

| Что | Заменено на | Причина |
|-----|-------------|---------|
| Rating-based learning (1–5 → permanent ban) | Experience model (context + action + outcome) | Слишком упрощённая модель |
| LearningEngine class | Experience = data + existing components | AD-37: over-engineering |
| SequenceExperience as separate entity | ChainExperience with sequence fields | M25_REVIEW: merged |
| Semantic temporal verification in M25 | Deterministic checks only | Требует multi-image SemanticVerifier |
| PlanContext changes for Experience | ExecutionHistory path | M9.1 frozen |
| Pillow dependency | No image processing | Нет необходимости в M25 |
| ComfyCLIAdapter as M12 | M12 = Real UI E2E, ComfyCLI = M12.1 | Фактическое состояние кода |

---

## 19. Architecture Risks

| # | Риск | Вероятность | Влияние | Mitigation |
|---|------|-------------|---------|------------|
| R1 | M25 Real E2E не пройдёт на доступном железе | Medium | High | Использовать remote Colab T4 (уже доказан M5/M6) |
| R2 | chain_id wiring сломает M18 chain semantics | Low | High | Тесты `test_m18_e2e_real.py` + backward compat (chain_id=None) |
| R3 | Feedback wiring создаёт oscillation | Medium | Medium | Layered learning: AdaptivePlanner (planning) ≠ RetryPolicy (correction) |
| R4 | Experience JSONL растёт бесконечно | Low | Medium | Не в v1; future archival/cleanup |
| R5 | Multi-image SemanticVerifier неточный | Medium | Low | Threshold tuning + human review fallback |
| R6 | External I/O module потребует изменения Provider | Low | High | Provider abstraction уже поддерживает remote (AD-29) |
| R7 | Model Knowledge требует реальных моделей | Medium | Medium | Начать с данных из Experience |
| R8 | Capability explosion (too many capabilities) | Low | Medium | Плоский расширяемый список (уже работает) |

---

## 20. Definition of Done for Roadmap Governance

### 20.1 Правила перехода между этапами

1. **MILESTONE FROZEN** = Code ✅ + Tests ✅ + Real E2E ✅ + Docs ✅ + Self-review ✅
2. **Нельзя начинать M26 до M25 FROZEN** — M25 Experience является фундаментом для всех последующих
3. **Нельзя менять frozen AD без архитектурного решения** — STOP → REPORT → DECISION → UPDATE SPEC → IMPLEMENT
4. **Каждый новый компонент должен иметь доказанную зависимость** — не добавлять технологии ради технологий
5. **Real E2E = реальный ComfyUI + реальный workflow + реальная модель + реальный результат** — mock не считается
6. **Документация описывает намерение, код и тесты подтверждают факт** — при конфликте: зафиксировать расхождение

### 20.2 Критерии FROZEN для M25

- [ ] `chain_id` генерируется и проставляется в production
- [ ] `verify_sequence()` вызывается после video-шагов
- [ ] `build_chain_experience()` вызывается после chain completion
- [ ] Real E2E: image sequence → video → experience → persistence → restart → query PASSED
- [ ] 496+ тестов зелёных, 0 новых ошибок
- [ ] Self-review checklist пройден
- [ ] HANDOFF.md обновлён

### 20.3 Правила работы с документацией

1. **Не переписывать старые milestone документы** — история сохраняется
2. **SUPERSEDED/DEFERRED фиксируется здесь**, в MASTER ROADMAP
3. **PROJECT_SPEC.md — единственный источник архитектурной истины** — при конфликте: правится код, не спека
4. **Производные документы (docs/00..28, engineering/*) не могут менять архитектуру**

---

## Appendix A: Audit Evidence

### A.1 Files Inspected (source)

| Directory | Key Files |
|-----------|-----------|
| `app/` | `__init__.py`, `agent.py`, `conversation.py`, `ui.py` |
| `app/assets/` | `types.py`, `store.py` |
| `app/comfy/` | `client.py`, `lifecycle.py` |
| `app/context/` | `persistence.py`, `session_manager.py`, `feedback.py` |
| `app/engine/` | `engine.py`, `job.py`, `history.py`, `chain.py`, `verifier.py`, `retry.py`, `semantic_verifier.py`, `analytics.py`, `experience.py`, `websocket.py`, `plan.py` |
| `app/planner/` | `__init__.py`, `composer.py`, `capability_graph.py`, `composition_result.py`, `adaptive.py`, `preferences.py`, `decomposer.py` |
| `app/prompt/` | `builder.py`, `heuristic.py`, `llm.py`, `composite.py`, `templates.py` |
| `app/provider/` | `comfyui.py`, `backend_ref.py` |
| `app/registry/` | `capability.py`, `workflow.py`, `model.py`, `registry.py`, `compatibility.py`, `selection.py`, `semver.py`, `backends.py`, `runtime.py` |
| `app/resource/` | `gateway.py`, `models.py`, `reconciler.py` |
| `app/infrastructure/` | `comfy_cli_adapter.py` |

### A.2 Files Inspected (tests)

| File | Milestone | Tests |
|------|-----------|-------|
| `test_m1_runtime.py` | M1 | 8 |
| `test_m2_asset.py` | M2 | 10 |
| `test_m3_registry.py` | M3 | 23 |
| `test_m4_execution.py` | M4 | 5 |
| `test_agent.py` | M5/M8 | 8 |
| `test_backends.py` | M5 | 5 |
| `test_planner.py` | M8 | 4 |
| `test_planner_context.py` | M9.1 | 11 |
| `test_ui_m9.py` | M9 | 5 |
| `test_upscale.py` | — | 6 |
| `test_progress.py` | — | 12 |
| `test_prompt_builder*.py` | M11 | 81+ |
| `test_ui_m12.py` | M12 | 10 |
| `test_comfy_cli_adapter.py` | M12.1 | 34 |
| `test_m13_history_retry.py` | M13 | 32 |
| `test_m14_semantic_verification.py` | M14 | 23 |
| `test_m15_persistent_context.py` | M15 | 14 |
| `test_m16_adaptive_planner.py` | M16 | 16 |
| `test_m17_user_feedback.py` | M17 | 11 |
| `test_m18_multi_step.py` | M18 | 17 |
| `test_m18_e2e_real.py` | M18 | 8 |
| `test_m19_composer.py` | M19 | 10 |
| `test_m19_integration.py` | M19 | 15 |
| `test_m19_e2e_real.py` | M19 | 6 |
| `test_m19_feedback_integration.py` | M19 | 12 |
| `test_m20_cluster_gateway.py` | M20 | 10 |
| `test_m21_reconciliation.py` | M21 | 18 |
| `test_m21_fault_injection_e2e.py` | M21 | 7 |
| `test_m21_real_e2e.py` | M21 | 6 |
| `test_m22_decision_bridge.py` | M22 | 14 |
| `test_m23_parameter_adjustment.py` | M23 | 35 |
| `test_m24_feedback_decision.py` | M24 | 21 |
| `test_m24_1_production_wiring.py` | M24.1 | 12 |
| `test_experience.py` | M25.4 | 15 |
| `test_chain_tracking.py` | M25.1 | ~10 |
| `test_multi_asset.py` | M25.2 | ~10 |
| `test_sequence_verification.py` | M25.3 | ~10 |

### A.3 Documentation Inspected

`PROJECT_SPEC.md`, `PROJECT_STATE_2026-09-01.md`, `17_ROADMAP.md`, `FUTURE_ROADMAP_ARCHITECTURE.md`, `DEVELOPMENT_PLAN_M13_M18.md`, `22_INTENT_CAPABILITY_PLANNING_RESEARCH.md`, `23_COMPOSER_INTEGRATION_AUDIT.md`, `24_CLUSTER_GATEWAY_DESIGN_AUDIT.md`, `25_M21_RECONCILIATION_RECOVERY.md`, `26_M22_ARCHITECTURAL_AUDIT.md`, `27_M22_M24_DECISION_INTEGRATION.md`, `28_LEARNING_ARCHITECTURE_AUDIT.md`, `M25_ARCHITECTURE_PROPOSAL.md`, `M25_ARCHITECTURE_REVIEW.md`, `M25_IMPLEMENTATION_PLAN.md`, `M25_SMOKE_CHECK_PLAN.md`, `M25_STADIP_AUDIT_PHASE1.md`, `M25_FRP_AUDIT_REPORT.md`, `M25_NGROK_AUDIT.md`, `AI_ENGINEER_ONBOARDING.md`, `AI_ENGINEER_HANDOFF.md`, `ARCHITECTURE_AUDIT_2026-09-01.md`, `AUDIT_NEXT_LEARNING_ARCHITECTURE.md`, `engineering/DECISION_LOG.md`, `engineering/HANDOFF.md`, `engineering/AGENT_PROTOCOL.md`, `engineering/CHANGE_PROTOCOL.md`, `engineering/REVIEW_PROTOCOL.md`, `engineering/TEST_PROTOCOL.md`, `tasks/ACTIVE.md`, `tasks/BACKLOG.md`, `tasks/COMPLETED.md`.

### A.4 Milestone Documents

M1–M24: подтверждены через HANDOFF.md, ACTIVE.md, CHANGELOG.md.
M25: подтверждены через M25_PROPOSAL, M25_REVIEW, M25_IMPL_PLAN, M25_SMOKE, M25_STADIP, M25_FRP.

### A.5 Architecture Decisions

AD-01..AD-42: подтверждены через PROJECT_SPEC.md §24, DECISION_LOG.md.
AD-37..AD-39: PROPOSED (M25), не утверждены.

---

## Appendix B: Code Changes

**Code changes during audit:** 0

**Единственное изменение:** создание `docs/MASTER_DEVELOPMENT_ROADMAP.md`

**git diff:** должен показать только этот файл.

---

*Конец документа. Аудит завершён. Ожидается архитектурное решение по M25 и дальнейшему пути развития.*