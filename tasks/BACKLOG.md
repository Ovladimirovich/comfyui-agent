# BACKLOG — будущие задачи

Простейший task-management слой. Не превращать в Jira.

Завершённые (история):
- **M1** Runtime + Client — ✓
- **M2** Asset Layer — ✓
- **M3** Capability + Workflow Registry — ✓
- **M4** Execution chain + реальный txt2img E2E — ✓
- **M5** Provider / Model catalog + Remote Execution (AD-29) — ✓
- **M6** Real Video E2E (video_generate исполним, E2E доказан) — ✓
- **M6.5** Image Input / img2img (`image.edit`, `workflows/img2img`; AD-23 закрыт) — ✓
- **M7** Conversation Context (`ConversationContext` + `ConversationAgent`; multi-turn chain доказан офлайн) — ✓
- **M8** Agent + LLM (Agent + HeuristicPlanner + LLMPlanner + multi-backend) — ✓
- **M9** UI (минимальный чат + preview + progress SSE; `app/ui.py`) — ✓
- **M9.1** Context-aware Planner (`PlanContext` + HeuristicPlanner edit-hints + LLMPlanner context) — ✓
- **image.upscale** workflow (`workflows/upscale`, ImageScale lanczos, без checkpoint) — ✓
- **M10 Validation** — 6/7 remote E2E на живом ComfyUI (CPU). Audio deferred — ✓
- **Progress Hook** — гранулярный % в UI: WS → Job → SSE → progress bar. 7 тестов. ✓
- **M11 Prompt Builder** — M11.3-M11.6 FULLY IMPLEMENTED. HeuristicPromptBuilder + LLMPromptBuilder + CompositePromptBuilder + Planner integration. AD-30/31/32. ✓
- **M12 Real UI E2E** — M12.1-M12.5 IMPLEMENTED & FROZEN. ComfyUIProcessManager + CompositePromptBuilder default + real /turn execution + SSE + Browser E2E. ✓
- **M12.1 ComfyCLI Adapter** — опциональный infrastructure adapter (diagnostics only). ✓
- **M13** Execution History + Retry Loop — ✓
- **M14** Semantic Verification — OpenRouter vision model integration — ✓
- **M15** Persistent Context — JSONL-based persistence — ✓
- **M16** Adaptive Planner — History analytics + UserPreferences + AdaptivePlanner (AD-36) — ✓
- **M17** User Feedback — FeedbackRecord + FeedbackStore (JSONL) — ✓
- **M18** Multi-Step Decomposition — TaskDecomposer + ExecutionChain, REAL E2E — ✓
- **M19** Composer + CapabilityGraph — AD-41 — ✓
- **M20** Cluster Gateway — routing, health, dispatch — ✓
- **M21** Reconciliation & Recovery — FROZEN, 31 tests — ✓
- **M22** Human-in-the-Loop Decision Bridge — FROZEN — ✓
- **M23** Parameter Adjustment Strategy — FROZEN — ✓
- **M24** Feedback-Driven Decision — FROZEN — ✓
- **Knowledge Core Slice 1** — `app/knowledge/` package (NodeSchema, Evidence, Claims, Candidates, Gaps, Core, Research contracts). Runtime discovery via ComfyClient.get_object_info(). 51 tests (31 unit + 20 integration). All DoD criteria PASS. ✓
- **Knowledge Core Slice 2 (via S0.5)** — Agent/ConversationAgent pre-flight (`knowledge_core` optional), `_plan_result_to_query`, `Job._knowledge_readiness/_knowledge_gaps` — advisory invariant (AD-45). FROZEN/VERIFIED 2026-09-13. 30 tests + 8-point forensic. ✓
- **S1 CostTier / Free-First** — `app/registry/cost.py`, BackendSpec/Workflow cost_tier, filter→ranking, local→FREE (AD-46). FROZEN/VERIFIED 2026-09-13. 32 tests + 8-point forensic. ✓
- **S2 Template-Based Workflow Synthesis** — `app/synthesis/` (4 шаблона, deterministic selector, builder, safety 3-класса), `synthesize_candidates()` advisory без auto-registration (AD-47). ACCEPTED WITH RUNTIME GAP 2026-09-13. 20 tests; живой ComfyUI принял synthesized graph. ✓
Очередь:
- **S3 Ecosystem Facts & Provenance Queries (forensic audit → design)** — read-only query слой над `app/knowledge/` + GAP-реестр; provenance = существующие `EvidenceTrustLevel`/`ClaimStatus`; self-test — только design-контракт. Порядок: audit → STOP → design → approval → impl → forensic.
- **S2 runtime E2E proof — перезапуск** — `scripts/s2_proof.py` при свободной ComfyUI-очереди (graph принят сервером, файл-результат не получен из-за занятости очереди пользователем).
- **S6 RuntimeValidator activation + self-test whitelist** — после S3 (safety data). Чинит `_calculate_validation_score`=0. Запрет на «починку по дороге».
- **Real UI E2E на живом ComfyUI** — прогон `test_m4_execution.py`, `test_video_e2e.py`, `test_img2img_e2e.py`, `test_ui_real_e2e.py` с поднятым ComfyUI на 127.0.0.1:8188.
- **audio.generate real E2E** — deferred, внешний ключ Sonilo (HTTP 401). Код пайплайна доказан.
- **Concurrency tests** — SessionStream threading, race conditions.
- **Persistence контекста** — ConversationContext in-memory → DB (Supabase/SQLite).
- **Asset metadata** — size/hash при ingest.

Future (явные gap / external dependency):
- **audio real E2E** — deferred, внешняя зависимость Sonilo (HTTP 401 на ключ `sk-5bc5…`); код пайплайна доказан.
- **MP4** — необязательный future workflow/post-processing (video E2E уже доказан MP4 / анимированным WEBP).
- **Future** models.json / aliases (S-02, НЕ в v1).

Tech debt (не milestone, по мере необходимости):
- **LLM-резолюция ссылок** — реальное местоимение «её/теперь» должен резолвить `LLMPlanner`, глядя в `active_asset` (HeuristicPlanner не context-aware).
- **`probe` в `BackendCatalog.choose`** — live-выбор backend по VRAM.