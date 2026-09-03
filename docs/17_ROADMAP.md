> Source of truth: `PROJECT_SPEC.md` v0.2 (APPROVED).
> Derivative document — не вводит новых архитектурных решений.

# 17 — Roadmap

## Milestones
- **M1 Runtime + Client** — ComfyClient (HTTP API) + RuntimeInfo. Тест: живой ComfyUI. ✓
- **M2 Asset Layer** — AssetStore + Asset. ✓
- **M3 Capability + Workflow Registry** — manifest+workflow; фильтр по capability+runtime+inputs. ✓
- **M4 Execution chain (БЕЗ LLM)** — WorkflowEngine + Operator + WS + JobManager + Verifier. Реальный txt2img E2E + media-agnostic тест. ✓
- **M5 Provider / Model** — Provider + Model catalog (`/object_info`), bind model slot → checkpoint; remote ComfyUI proven (AD-29). ✓
- **M6 Real Video E2E** — `video.generate` исполнимый workflow; реальный video-E2E доказан на remote Colab (Tesla T4) → локальный AssetStore. ✓
- **M6.5 Image Input / img2img** — `image.edit` исполнимый workflow (`workflows/img2img`, реальный ComfyUI graph: LoadImage → VAEEncode → KSampler → VAEDecode → SaveImage). Закрыт gap AD-23: `asset_inputs.image` (kind=image) связывает Asset → ComfyUI input декларативно через manifest; video Asset → INPUT_INCOMPATIBLE. Media-agnostic (тот же WorkflowEngine/Job/Verifier/Asset, без ImageEngine/ImageAsset). ✓
- **M7 Conversation Context (скрипт, без LLM)** — `ConversationContext` (media-agnostic) + `ConversationAgent` (session-scoped): multi-turn chain доказан офлайн (generate → image.edit на active_asset → Asset B, `lineage(B)==[B,A]`); session isolation; explicit asset override; error не заменяет active_asset; AD-23 type-match (без транскодинга). ✓
- **M8 Agent + LLM** — реализован: `Agent` + `HeuristicPlanner` + `LLMPlanner` (OpenRouter), multi-backend catalog, asset inputs. ✓
- **M9 UI** — минимальный чат + preview + progress (SSE): `app/ui.py` (stdlib http.server, без новых зависимостей). `POST /turn` → `ConversationAgent.turn` (фоновый поток) → `GET /events` (SSE: start→status→result/error) → `GET /asset/<id>` preview. Multi-turn chain виден в UI (active_asset обновляется). Session isolation сохранён. ✓
- **M9.1 Context-aware Planner** — `PlanContext` (декларативный контекст) + `HeuristicPlanner` edit-hints (25 хинтов: «улучши», «сделай реалистивнее», «enhance» и др.) + `LLMPlanner` context в system prompt. Multi-turn «сгенерируй → сделай реалистивнее → image.edit» работает через UI. ✓
- **image.upscale** — `workflows/upscale` (LoadImage → ImageScale (lanczos) → SaveImage). Capability `image.upscale`, asset_inputs.image (kind=image), без checkpoint/custom nodes. AD-23: image → AVAILABLE, video → INPUT_INCOMPATIBLE. ✓
- **M10 Validation** — реальный ComfyUI + workflow + модель + результат, цепь §6, без mock. ✓ 6/7 remote E2E (txt2img, img2img, video, upscale, conversation chain, remote_e2e). Audio deferred (Sonilo).
- **Progress Hook** — гранулярный % в UI: WS progress events → Job.progress → SSE → progress bar. 7 тестов. ✓
- **M11 Prompt Builder + Dynamic Prompt Suggestions** — ✅ M11.1-M11.6 FULLY IMPLEMENTED & FROZEN. HeuristicPromptBuilder (offline) + LLMPromptBuilder (online) + CompositePromptBuilder (fallback orchestration) + Planner integration (Agent.generate, ConversationAgent.turn). AD-30/31/32 соблюдены. Триуровневая архитектура: Heuristic → LLM → Composite/fallback → Planner. **M11 FROZEN — architectural layer stable.**

**M12 Real UI E2E** — ✅ M12.1-M12.5 FULLY IMPLEMENTED & FROZEN. ComfyUIProcessManager (lifecycle) + UI uses CompositePromptBuilder by default + LLM unavailable → heuristic fallback + SSE progress events + Multi-turn context + Session isolation. **M12 FROZEN — real UI flow verified.**

**M13 Execution History + Retry Loop** — ✅ IMPLEMENTED. ExecutionRecord + ExecutionHistory (in-memory + JSONL persistence) + RetryPolicy (max_attempts, backoff, error classification) + verify_with_diagnostics() + Agent.generate() retry loop + ConversationAgent.turn() retry with SSE events. 32 tests. **M13 COMPLETE — retry capability added.**

**M14 Semantic Verification** — ✅ IMPLEMENTED. SemanticVerifier (vision model via OpenRouter) + SemanticVerificationResult (score, matches_intent, issues, suggested_params). Fallback: API unavailable → score=0.5. Integration с retry loop: low score → retry с suggested_params. 23 tests. **M14 COMPLETE — semantic verification added.**

**M15 Persistent Context** — ✅ IMPLEMENTED. ContextPersistence (JSONL-based, per-session files) + SessionManager (create, resume, list_sessions, save, delete). Auto-save после каждого turn. Lazy import для избежания circular dependency. 14 tests. **M15 COMPLETE — session persistence added.**

**M16 Adaptive Planner** — ✅ IMPLEMENTED. HistoryAnalytics (success_rate, avg_duration, preferred_params, error_patterns) + UserPreferences (preferred_params, preferred_workflow, recommended_resolution) + AdaptivePlanner (uses ExecutionHistory, fallback на HeuristicPlanner). User explicit params > learned preferences. 16 tests. **M16 COMPLETE — adaptive planning added.**

**M17 User Feedback** — ✅ IMPLEMENTED. FeedbackRecord (dataclass) + FeedbackStore (JSONL persistence, per-session files) + UI endpoints (POST /api/feedback, GET /api/feedback/history). Rating 1-5, comments. 11 tests. **M17 COMPLETE — user feedback loop added.**

**M18 Multi-Step Decomposition** — ✅ IMPLEMENTED. TaskDecomposer (request → list of SubTasks) + ExecutionChain (subtask1 → subtask2 → ... → result). Per-step retry, cancel support, chain state tracking. 17 tests. **M18 COMPLETE — multi-step decomposition added.**

- **Mx (future)** — persistence контекста (in-memory → DB), LLMPlanner real integration, concurrency tests.
- **Mx (future)** — audio real E2E (deferred, external Sonilo dependency, 401).

## Связи
Каждый M* ссылается на требования (01) и DoD (18). Roadmap не вводит новых архитектурных решений.

См. `PROJECT_SPEC.md` §22.
