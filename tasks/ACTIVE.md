# ACTIVE — выполняемые задачи

- **M1 ✓** Runtime + Client — ComfyClient + RuntimeInfo.
- **M2 ✓** Asset Layer — AssetStore + Asset (media-agnostic, lineage, security).
- **M3 ✓** Capability + Workflow Registry.
- **M4 ✓** Execution/Verification — txt2img E2E РЕАЛЬНО прошёл на локальном ComfyUI.
- **M5 ✓** Provider + Model Registry + Remote Execution — AD-29 доказан (local + remote Colab T4).
- **M6 ✓** Real Video E2E — `video_generate` исполнимый workflow; E2E доказан на remote Colab (Tesla T4) → локальный AssetStore.
- **M6.5 ✓** Image Input / img2img — `image.edit` исполнимый workflow (`workflows/img2img`); закрыт gap AD-23 (asset_inputs.image декларативно связывает Asset → ComfyUI input; video Asset → INPUT_INCOMPATIBLE). Media-agnostic (тот же WorkflowEngine/Job/Verifier/Asset).
- **M7 ✓** Conversation Context — `ConversationContext` (media-agnostic) + `ConversationAgent` (session-scoped) поверх Agent/Asset/Execution. Multi-turn chain доказан офлайн (generate → image.edit на active_asset → Asset B, `lineage(B)==[B,A]`); session isolation; explicit override; error не заменяет active_asset; AD-23 type-match (без транскодинга). Существует независимо от LLM.
- **M9 ✓** UI — минимальный веб-сервер `app/ui.py` (stdlib http.server, без новых зависимостей) поверх ConversationAgent: `GET /` (чат+preview), `POST /turn` (→ `ConversationAgent.turn` в фоне), `GET /events` (SSE: start→status→result/error), `GET /asset/<id>` (preview), `GET /api/session` (контекст). Честный progress = переходы состояния Job (без fake-процентов). Multi-turn chain виден в UI; session isolation сохранён.
- **M9.1 ✓** Context-aware Planner — `PlanContext` (декларативный контекст: active_asset_type, capabilities, active_workflow) + `HeuristicPlanner` edit-hints + upscale-hints (35+ хинтов: «улучши», «сделай реалистивнее», «увеличь разрешение», «upscale» и др.) + `LLMPlanner` context в system prompt + `image.upscale` в `_VALID`. Multi-turn цепочка «сгенерируй → сделай реалистивнее → увеличь разрешение» работает через ConversationAgent.
- **image.upscale ✓** — `workflows/upscale` (LoadImage → ImageScale (lanczos) → SaveImage). Capability `image.upscale`, asset_inputs.image (kind=image), без checkpoint/custom nodes. AD-23: image → AVAILABLE, video → INPUT_INCOMPATIBLE.
- **M10 ✓** Validation — 6/7 remote E2E на живом ComfyUI v0.3.70 (DirectML/CPU): txt2img (91s), img2img (261s), video (397s), upscale (242s), conversation chain (741s). Audio — deferred (Sonilo).
- **Progress Hook ✓** — гранулярный % в UI: WS progress events → Job.progress (thread-safe) → SSE → progress bar. 12 тестов (включая backend limitation + ws_timeout=15 regression).
  - **Backend limitation:** ComfyUI 0.3.70 + DirectML/CPU НЕ шлёт WS execution events (executing/progress/executed) — только status. Engine falling back на /history polling. Progress bar показывает честные 0%→hide (без fake-процентов). Это ограничение backend, НЕ баг агента. На совместимых серверах (GPU, non-DirectML) granular progress работает.
  - **ComfyUI history bug FIXED** — `prompt_worker` в `main.py` не имел try/except вокруг `e.execute()`. При DirectML-ошибке worker-поток молча умирал, `task_done()` не вызывался, prompt_id не попадал в history. Фикс: try/except + `e.history_result = {"outputs": {}, "meta": {}}` + логирование. `/history` retry workaround в engine.py убран (root cause исправлен).
  - **History polling fix** — WS timeout=15s истекает ДО завершения execution на DirectML (>60s). После WS timeout engine polling `/history` каждые 2s до завершения execution (max 5min). Раньше проверка `/history` была однократной → "нет выхлопа".
  - **Planner dimension parsing** — `_parse_image_params()` в `planner.py` извлекает width×height и steps из текста пользователя ("64x64 3 steps" → `{width: 64, height: 64, steps: 3}`).
- **WS timeout fix ✓** — `ws_timeout` 300→15с (UI). DirectML backend: execution ~15с → WS timeout → /history fallback → result. Вместо прежних 300+с ожидания — теперь ~15-20с. GPU path (WS available) не затронут.
- **Real 3-turn UI test ✓** — 3/3 turns succeeded через agent UI (POST /turn → SSE events → ComfyUI execution → Asset → session context). Вертикальный слой целиком работает: chat → planner → context → workflow → ComfyUI → Asset → lineage → next turn.
- **Hardware optimization ✓** — AMD Radeon RX 570 4GB + DirectML: VRAM diagnostics (256-640 OK, 768 OOM), manifest defaults 384×384/10 steps, `--lowvram --cache-ram 8` flags, VRAM auto-detection через wmic → safe resolution. 3-turn test with different sizes: 3/3 OK.

Следующий кандидат (по команде): **M11 — Prompt Builder + Dynamic Prompt Suggestions** ✅ M11.3-M11.6 FULLY IMPLEMENTED & FROZEN (2026-09-01). HeuristicPromptBuilder (offline) + LLMPromptBuilder (online) + CompositePromptBuilder (fallback orchestration) + Planner integration (Agent.generate, ConversationAgent.turn). AD-30/31/32 соблюдены. Триуровневая архитектура завершена. **M11 ARCHITECTURAL FREEZE — не расширять без архитектурного решения.**

**M12 Real UI E2E** — ✅ M12.1-M12.5 IMPLEMENTED & FROZEN (2026-09-01). ComfyUI lifecycle manager + UI uses CompositePromptBuilder by default + Real /turn execution + SSE progress + Browser E2E. 10 M12 tests passed. **M12 ARCHITECTURAL FREEZE — не расширять без архитектурного решения.**

**M12.1 ComfyCLI Adapter** — ✅ IMPLEMENTED (2026-09-01). `app/infrastructure/comfy_cli_adapter.py` — опциональный infrastructure adapter для comfy-cli (version, stop_port, validate_workflow, system_info, env_info, model_list, free_memory). AD-33 (shell=False), AD-34 (comfy-cli optional). 34 теста passed. Не интегрирован в Agent execution path (diagnostics only).

Явно НЕ выполнено (gap / deferred) — не объявлять завершённым:
- `audio.generate` real E2E — deferred, SoniloTextToMusic object_info пуст (HTTP 401 / broken node).
