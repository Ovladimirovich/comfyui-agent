# ACTIVE — выполняемые задачи

- **M1 ✓** Runtime + Client — ComfyClient + RuntimeInfo.
- **M2 ✓** Asset Layer — AssetStore + Asset (media-agnostic, lineage, security).
- **M3 ✓** Capability + Workflow Registry.
- **M4 ✓** Execution/Verification — txt2img E2E РЕАЛЬНО прошёл на локальном ComfyUI.
- **M5 ✓** Provider + Model Registry + Remote Execution — AD-29 доказан (local + remote Colab T4).
- **M6 ✓** Real Video E2E — `video_generate` исполнимый workflow; E2E доказан на remote Colab (Tesla T4) → локальный AssetStore.
- **M6.5 ✓** Image Input / img2img — `image.edit` исполнимый workflow (`workflows/img2img`); закрыт gap AD-23.
- **M7 ✓** Conversation Context — `ConversationContext` + `ConversationAgent`. Multi-turn chain доказан офлайн.
- **M9 ✓** UI — минимальный веб-сервер `app/ui.py` (stdlib http.server). SSE events, progress, preview.
- **M9.1 ✓** Context-aware Planner — `PlanContext` + HeuristicPlanner edit-hints + LLMPlanner context.
- **image.upscale ✓** — `workflows/upscale` (LoadImage → ImageScale lanczos → SaveImage).
- **M10 ✓** Validation — 6/7 remote E2E на живом ComfyUI (CPU). Audio — deferred (Sonilo).
- **Progress Hook ✓** — гранулярный % в UI: WS progress events → Job.progress → SSE → progress bar.
- **M11 ✓** Prompt Builder — M11.3-M11.6 FULLY IMPLEMENTED & FROZEN.
- **M12 ✓** Real UI E2E — M12.1-M12.5 IMPLEMENTED & FROZEN.
- **M12.1 ✓** ComfyCLI Adapter — опциональный infrastructure adapter (diagnostics only).
- **M13 ✓** Execution History + Retry Loop.
- **M14 ✓** Semantic Verification — OpenRouter vision model integration.
- **M15 ✓** Persistent Context — JSONL-based persistence.
- **M16 ✓** Adaptive Planner — History analytics + UserPreferences + AdaptivePlanner (AD-36).
- **M17 ✓** User Feedback — FeedbackRecord + FeedbackStore (JSONL).
- **M18 ✓** Multi-Step Decomposition — TaskDecomposer + ExecutionChain. **REAL E2E VERIFIED** (generate→upscale через живой ComfyUI).
- **M19 ✓** Composer + CapabilityGraph — УЖЕ РЕАЛИЗОВАНО. TaskDecomposer → Composer validation → ExecutionChain. AD-41.
- **M20 ✓** Cluster Gateway — `app/resource/gateway.py` EXISTS (routing, health, dispatch).
- **M21 ✓** Reconciliation & Recovery — FROZEN. 31 tests passed (18 unit + 7 fault-injection + 6 real ComfyUI). MD-01 (UNKNOWN→STOP), MD-03 (NOT_ACCEPTED→safe retry) enforced on real ComfyUI. Dispatch persistence verified.
- **M22 ✓** Human-in-the-Loop Decision Bridge — FROZEN. RetryDecision.suggestions, enriched failure context, decision_failed event. 14 tests.
- **M23 ✓** Parameter Adjustment Strategy — FROZEN. CorrectionStrategy + 5 adjust_fn, param_adjustments, ExecutionRecord.corrections_applied. 35 tests.
- **M24 ✓** Feedback-Driven Decision — FROZEN. RetryPolicy.feedback_store, action="ask_user", feedback_request event. 21 tests.
- **TD-5 ✓** Feedback → AdaptivePlanner integration — `HistoryAnalytics` + `_filter_by_feedback()` для rating < 4.
- **TD-6 ✓** UI chain progress SSE — `chain_step` events in `_execute_chain()`, frontend handler.
- **TD-7 ✓** Persistence restart tests — `TestPersistenceRestart` для chain state preservation.
- **Knowledge Core Slice 1 ✓** — `app/knowledge/` package: NodeSchema, Evidence, Claims, Candidates, Gaps, Core, Research contracts. Runtime discovery via ComfyClient.get_object_info(). 31 unit tests + 20 integration tests. All criteria PASS.
- **Knowledge Core Slice 2 ✓** — Minimal Agent integration: `Agent.generate()` + `ConversationAgent.turn()` query KnowledgeCore pre-flight. Readiness stored on Job as `_knowledge_readiness` / `_knowledge_gaps`. Zero regression.
  - **PLAN_LOCAL_E2E_VALIDATION ✓ (2026-09-08)** — PHASE 0–3 выполнены на реальном локальном Comfy Desktop 0.34.5 (:8188). 6 capabilities READY, image.upscale LIMITED (нет upscale-моделей), audio.generate DEPENDENCY_BLOCKED (нет Comfy.org ключа). Исправлены Defect: text_generate workflow (SaveText/format, Autogrow dotted, api_key) и `_build_multi_asset_input` (BatchImagesNode dotted). Сводка: `docs/PLAN_LOCAL_E2E_VALIDATION.md` (PHASE 1 RESULTS) + ENGINEERING_HANDOFF 2026-09-08.
  - **M25 ✓** Experience Foundation — FROZEN (2026-09-11). ChainExperience + SequenceExperience (computed view, M25_ARCHITECTURE_REVIEW §3.4), chain_id tracking (M25.1), multi-asset `video.image_to_video` workflow (M25.2), `SemanticVerifier.verify_temporal_consistency()` подключён в production pipeline (`app/conversation.py:595`, B1), `build_sequence_experience()` встроен в experience flow (`app/conversation.py:643`, B2). 38 M25 tests + 97 M25-related pass, 0 new failures. Детали: `docs/M25_COMPLETION_REPORT.md`, `docs/M25_FORENSIC_ACCEPTANCE_AUDIT.md`.
  - **M26.1 ✓** Experience Analytics — ACCEPTED (2026-09-11). `ExperienceAnalytics` (read-only aggregation над `ExperienceStore`): `temporal_stats()`, `preferred_params()` (ranking по непрерывному temporal score, `EXPERIENCE_MIN_SAMPLES_FOR_PREFERENCE=2`). Нет новой persistence, нет mutation исходных Experience. `ExperienceHint` dataclass для signal.
  - **M26.2 ✓** Experience → AdaptivePlanner — ACCEPTED (2026-09-11). `AdaptivePlanner(experience_store=...)` применяет experience-preference как soft default (ranking, НЕ prohibition). `PlanContext` M9.1 и `ExecutionRecord` НЕ изменены. Нет magic threshold `0.7` — ranking по continuous score.
  - **M26.4 ✓** Experience → Composer suggestions — ACCEPTED (2026-09-11). `Composer.compose(experience_hint=...)` добавляет computed suggestion (не меняет chain/alternatives, не auto-policy). `Experience → signal → suggestion`.

Явно НЕ выполнено (gap / deferred) — не объявлять завершённым:
  - **M26.3 🔄 REDEFINED / DEFERRED** — **Video Editor Integration Boundary** (НЕ video-processing внутри Agent). Исходная постановка «frame extraction → temporal score → SUCCESS/FAILED» переопределена: media analysis принадлежит будущему отдельному проекту **Video Editor / Media Project**. Agent передаёт generated assets/episodes, принимает downstream feedback как Experience. Variant A (advisory) старой формулировки НЕ реализуется сейчас; Variant B / AD-44 SUPERSEDED / NOT APPROVED. Обычный путь `Agent → ComfyUI → asset` НЕ зависит от Video Editor. Детали: `docs/M26.3_FORENSIC_DESIGN.md` (PART 1 findings + PART 2 redefinition).
  - **D12 ✗ CLOSED** — FeedbackStore → AdaptivePlanner wiring уже существует (М24/М19) и подтверждён regression-тестом `test_m24_1_production_wiring.py`. НЕ gap, НЕ изменять.

FUTURE (deferred, отдельный проект — НЕ часть M26):
  - **Video Editor Integration** — отдельный проект определит: API/contract, asset handoff, episode/project representation, processing status, final output, error semantics, optional quality/feedback payload, как Agent получает downstream Experience. НЕ реализуется в текущем M26.3.
- `audio.generate` real E2E — DEPENDENCY_BLOCKED: SoniloTextToMusic = облачный API Comfy.org, нужен ключ `auth_token_comfy_org`/`api_key_comfy_org` (команда автора / локальная модель).
- `image.upscale` model-based — BLOCKED: `upscale_models/` пуст (resize-путь ImageScale работает, это НЕ upscale).
- M21 real disconnect E2E — требуется симуляция обрыва связи на живом ComfyUI.

Следующий кандидат: **M26 — Experience-Driven Planning Loop**. M26.1/26.2/26.4 — **ACCEPTED**. M26.3 — **REDEFINED / DEFERRED** как Video Editor Integration Boundary (AD-44 SUPERSEDED). M26 целиком **READY TO FREEZE** после docs reconciliation. Заблокированные deferred (вне M26 без внешних зависимостей): `audio.generate` real E2E (Sonilo 401), `image.upscale` model-based (нет `upscale_models/`), M21 real disconnect E2E (нужен fault-injection harness), Future: Video Editor Integration (отдельный проект). Детали: `docs/M26_COMPLETION_REPORT.md`, `docs/M26_PRE_IMPLEMENTATION_FORENSIC_DESIGN.md`, `docs/M26.3_FORENSIC_DESIGN.md`.
