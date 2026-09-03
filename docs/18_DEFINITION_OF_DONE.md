> Source of truth: `PROJECT_SPEC.md` v0.2 (APPROVED).
> Derivative document — не вводит новых архитектурных решений.

# 18 — Definition of Done

## M4 считается готовым только если
```text
[✓] реальный ComfyUI (127.0.0.1:8188)
[✓] реальный workflow (txt2img@версия)
[✓] реальная модель (cyberrealistic_v80)
[✓] POST /prompt → prompt_id
[✓] WebSocket-мониторинг (progress/executed)
[✓] completion через history
[✓] output скачан (/view)
[✓] Asset создан (role=output)
[✓] Verifier прошёл
[✓] media-agnostic тест зелёный — ядро не трогалось
    (доказывает отсутствие image-specific coupling; НЕ доказывает реальную генерацию видео)
[✓] тест зелёный (без mock)
[✓] реальный video E2E — доказан в M6 (НЕ входит в M4 по исходному плану; закрыт отдельно)
[✓] реальный img2img E2E — доказан в M6.5 (image.edit; закрыт отдельно)
```

## M6 считается готовым только если (Real Video E2E)
```text
[✓] реальный remote ComfyUI (Colab, Tesla T4, Cloudflare Tunnel)
[✓] реальный video workflow (video_generate@версия)
[✓] POST /prompt → prompt_id → execution
[✓] output (MP4 / анимированный WEBP) скачан в локальный AssetStore (Windows)
[✓] Asset(type=video) создан; Verifier(kind=video) прошёл
[✓] тест зелёный (без mock; skip при отсутствии COMFY_REMOTE_URL)
```

## M6.5 считается готовым только если (Image Input / img2img)
```text
[✓] реальный ComfyUI (local 127.0.0.1:8188 или remote Colab) с LoadImage/VAEEncode (ядро)
[✓] исполнимый img2img workflow (img2img@версия), НЕ DECLARED_ONLY
[✓] manifest декларативно описывает asset_inputs.image (node/field/kind) — без хардкода в Agent/Engine
[✓] AD-23: image Asset → совместим; video Asset → INPUT_INCOMPATIBLE (без resize/conversion)
[✓] Asset(type=image) на входе → POST /prompt → execution → Asset(type=image) на выходе
[✓] lineage сохранён: output.source_asset == input Asset.id
[✓] media-agnostic: тот же WorkflowEngine/Job/Verifier/Asset (без ImageEngine/ImageAsset)
[✓] тест зелёный (без mock; real-E2E skip при отсутствии COMFY_REMOTE_URL)
```

## M7 считается готовым только если (Conversation Context)
```text
[✓] ConversationContext media-agnostic (только id/строки: asset/job/workflow/capability) — нет ImageContext/VideoContext
[✓] multi-turn chain: generate → Asset A → image.edit(active_asset) → Asset B; lineage(B)==[B,A]
[✓] active_asset: успешный output становится активным; ошибка НЕ заменяет active_asset
[✓] asset resolution: приоритет explicit > active_asset > reference; тип active сопоставляется с role.kind (AD-23, без транскодинга)
[✓] session isolation: разные session не видят чужие active_asset/assets/jobs
[✓] explicit asset override активного — работает
[✓] Conversation Context существует независимо от LLM (офлайн-доказательство через HeuristicPlanner/явный capability)
[✓] нет LLM filesystem access (ссылки резолвятся через store по id, не по произвольному пути)
[✓] нет mock-success: real-E2E skip при отсутствии COMFY_REMOTE_URL
```

## M9 считается готовым только если (UI: чат + preview + SSE)
```text
[✓] минимальный веб-сервер поверх ConversationAgent (без новых зависимостей / без дублирования execution core)
[✓] POST /turn запускает ConversationAgent.turn и возвращает 200 (исполнение в фоновом потоке)
[✓] GET /events стримит SSE-события: start → status(RUNNING) → result|error (с превью active_asset)
[✓] GET /asset/<id> отдаёт байты ассета (preview картинки/видео/аудио по типу)
[✓] GET /api/session возвращает контекст session (active_asset / assets / active_job / active_workflow)
[✓] честный progress: переходы состояния Job, без fake-процентов
[✓] session isolation: разные session не смешивают active_asset через UI
[✓] тест зелёный (офлайн через FakeProvider; real-E2E при наличии backend)
```

## M11 считается готовым только если (Prompt Builder + Dynamic Prompt Suggestions)
```text
[✓] PromptBuilder contract определён (PromptContext, PromptResult, PromptBuilder protocol)
[✓] HeuristicPromptBuilder реализован (offline, шаблоны, детерминированная логика)
[✓] UI endpoint POST /api/prompt/suggest реализован (app/ui.py)
[✓] Кнопка "✨ Подсказка" добавлена в UI (HTML + JavaScript)
[✓] Dynamic Suggestions работают: каждое нажатие даёт новый вариант (suggestion_index)
[✓] Исходный пользовательский текст НЕ уничтожается автоматически (original_preserved check)
[✓] PromptBuilder не имеет доступа к FS/ComfyUI (AD-30 проверен)
[✓] PromptBuilder не выбирает capability (AD-31 проверен)
[✓] Unit тесты для HeuristicPromptBuilder (шаблоны, детерминированность, suggestion_index)
[✓] Интеграционные тесты для UI endpoint (/api/prompt/suggest)
[✓] Документация обновлена (PROJECT_SPEC AD-30/31/32, ROADMAP M11, docs/20_PROMPT_BUILDER.md)
[✓] MVP НЕ требует изменений WorkflowEngine/Provider/Asset/Registry/execution core
[✓] MVP НЕ требует доступа PromptBuilder к filesystem/ComfyUI
[✓] MVP НЕ требует автоматического выполнения prompt
```

**Примечание:** M11 разделён на подэтапы M11.1-M11.6.
- **M11.1-M11.3 ✅ IMPLEMENTED:** Prompt Builder contract + HeuristicPromptBuilder + UI endpoint + кнопка ✨.
- **M11.4-M11.6 ✅ IMPLEMENTED:** LLMPromptBuilder (online) + CompositePromptBuilder (fallback orchestration) + Planner integration (Agent.generate + ConversationAgent.turn).

## M13 считается готовым только если (Execution History + Retry)
```text
[✓] ExecutionHistory (JSONL) сохраняет record после каждого turn
[✓] RetryPolicy: max_attempts, backoff, transient vs permanent classification
[✓] Agent.generate поддерживает retry loop (max_attempts > 1)
[✓] ConversationAgent.turn поддерживает retry loop
[✓] SSE events: retry_started, retry_completed
[✓] История используется AdaptivePlanner (M16)
[✓] тест зелёный (без mock для JSONL; remote skip при отсутствии COMFY_REMOTE_URL)
```

## M14 считается готовым только если (Semantic Verification)
```text
[✓] SemanticVerifier: vision model через OpenAI-compatible API
[✓] configurable threshold (default 0.5)
[✓] pass/fail результат интегрирован в WorkflowEngine.execute
[✓] failed verification → Job.state = FAILED с error_class="verification"
[✓] test зелёный (mock vision model для unit; real E2E skip без ключа)
```

## M15 считается готовым только если (Persistent Context)
```text
[✓] SessionManager: JSONL persistence per session
[✓] auto-save after each turn
[✓] restore session on reconnect (session_id lookup)
[✓] cross-turn context survival (active_asset, messages, parameters)
[✓] тест зелёный (offline через InMemorySessionManager)
```

## M16 считается готовым только если (Adaptive Planner)
```text
[✓] AdaptivePlanner: plan с историей, fallback на HeuristicPlanner
[✓] AD-36: per-capability threshold (≥3 successful), не глобально
[✓] AD-36: cross-capability contamination исключён
[✓] preferred_params: агрегация по most-common values
[✓] active_workflow context-aware filtering
[✓] тест зелёный (offline, mock history)
```

## M17 считается готовым только если (User Feedback)
```text
[✓] FeedbackStore: rating 1-5, JSONL per session
[✓] UI endpoint POST /api/feedback
[✓] AdaptivePlanner использует feedback для weights
[✓] тест зелёный (offline)
```

## M18 считается готовым только если (Multi-Step Chain)
```text
[✓] TaskDecomposer: keyword-based decomposition (no LLM)
[✓] ExecutionChain: sequential callback-based execution
[✓] per-step retry with configurable max_attempts_per_step
[✓] cancel support (after current step completes)
[✓] chain stops on first failed step
[✓] Lineage сохраняется между шагами
[✓] тест зелёный (offline, mock execution)
```

## Общие критерии Done
- Каждый модуль покрыт unit-тестами (16).
- E2E валидация — только на реальном ComfyUI без mock (AD-16).
- Все OAQ закрыты (03/04/05/07/11 — APPROVED как стances; 01/02/06/08/09/10/13/14 — в AD).
- Ни один запрет из §5 не нарушен.

## По milestone
Каждый M* имеет свой чек-лист DoD в производных документах (см. 01/16/17).

См. `PROJECT_SPEC.md` §23.
