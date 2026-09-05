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
- **M10 ✓** Validation — 6/7 remote E2E на живом ComfyUI v0.3.70 (DirectML/CPU). Audio — deferred (Sonilo).
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

Явно НЕ выполнено (gap / deferred) — не объявлять завершённым:
- `audio.generate` real E2E — deferred, SoniloTextToMusic object_info пуст (HTTP 401 / broken node).
- M21 real disconnect E2E — требуется симуляция обрыва связи на живом ComfyUI.

Следующий кандидат: **M25** (TBD) — или E2E валидация на живом ComfyUI для M22-M24.
