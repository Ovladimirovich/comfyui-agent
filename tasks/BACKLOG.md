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
- **M10 Validation** — 6/7 remote E2E на живом ComfyUI (DirectML/CPU). Audio deferred — ✓
- **Progress Hook** — гранулярный % в UI: WS → Job → SSE → progress bar. 7 тестов. ✓
- **M11 Prompt Builder** — M11.3-M11.6 FULLY IMPLEMENTED. HeuristicPromptBuilder + LLMPromptBuilder + CompositePromptBuilder + Planner integration. AD-30/31/32. ✓

Очередь:
- **Real UI E2E** — живой ComfyUI + progress в браузере (продуктовый тест).
- **LLMPlanner real integration** — LLM с реальным ключом OpenRouter/GigaChat.
- **Concurrency tests** — SessionStream threading, race conditions.
- **Persistence контекста** — ConversationContext in-memory → DB (Supabase/SQLite).
- **Asset metadata** — size/hash при ingest.

Future (явные gap / external dependency):
- **audio real E2E** — deferred, внешняя зависимость Sonilo (HTTP 401 на ключ `sk-5bc5…`); код пайплайна доказан.
- **MP4** — необязательный future workflow/post-processing (video E2E уже доказан MP4 / анимированным WEBP).
- **Future** models.json / aliases (S-02, НЕ в v1).

Тех-долг / улучшения (не milestone, по мере необходимости):
- **Persistence контекста** — JSONL-лог `ConversationContext` в `data/`, только если M9/M10 потребует переживать рестарт (PROJECT_SPEC §15 БД не требует).
- **LLM-резолюция ссылок** — реальное местоимение «её/теперь» должен резолвить `LLMPlanner`, глядя в `active_asset` (HeuristicPlanner не context-aware).
- **multi-step planner** — intent «generate → make realistic → upscale» в несколько `turn` с сохранением `active_asset`.
- **`probe` в `BackendCatalog.choose`** — live-выбор backend по VRAM.