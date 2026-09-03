# 19 — Conversation Context (M7)

> Source of truth: `PROJECT_SPEC.md` §15 (APPROVED). Derivative document — не вводит новых архитектурных решений.

## Назначение
Многоходовой контекст поверх уже существующего Agent/Asset/Execution слоя. Позволяет
пользователю не передавать каждый раз путь к предыдущему результату: «её/теперь/ещё» резолвится
в `active_asset`.

## Реализация
- `app/conversation.py`
  - `ConversationContext` (dataclass) — media-agnostic: хранит **только** идентификаторы и строки:
    `session_id`, `messages`, `assets: set[id]`, `jobs: set[id]`, `workflows: set["id@version"]`,
    `parameters`, `active_task`, `active_workflow`, `active_job`, `active_asset`, `unresolved`, `dialog_state`.
    НЕТ `ImageContext`/`VideoContext` и НЕТ ветвления по media-типу.
  - `ConversationAgent(Agent)` — композиционное расширение `Agent`. Владеет
    `sessions: dict[session_id, ConversationContext]`. Метод `turn(...)` реализует один ход.

## Conversation lifecycle (turn)
```text
turn(session_id, capability|request, params, assets)
  → ConversationContext (история / active_asset / active_job / active_workflow)
  → Agent.prepare(capability)                      # выбор workflow (media-agnostic)
  → Agent.resolve_asset_inputs(...)                 # explicit > active_asset > reference (AD-23)
  → WorkflowEngine.execute(...)                     # тот же путь image/video/audio
  → Job + output Asset'ы
  → успех: active_asset = выходной Asset; ошибка: active_asset НЕ заменяется (→ unresolved)
```

## active_asset семантика
- Успешный output (единственный выходной Asset workflow) становится `active_asset`.
- Следующий запрос может использовать `active_asset` как вход (через `asset_inputs`).
- При сбое исполнения `active_asset` **не** самопроизвольно заменяется битым/неуспешным результатом.

## Asset resolution — приоритет (AD-23)
1. Явно указанный пользователем Asset/path (`assets[role]`).
2. `ConversationContext.active_asset` — только если `active_asset.type == required_roles[role].kind`
   (без resize/conversion/transcoding).
3. Явная ссылка на предыдущий Asset/turn (`assets[role] = {"asset_id": id}` / `{"reference": id}`).

Неразрешённая роль → `AgentError`, запись в `unresolved`. LLM не получает произвольного доступа
к файловой системе: ссылки резолвятся через `AssetStore.get(id)`.

## Session isolation
Разные `session_id` → разные `ConversationContext`. `active_asset` / `assets` / `jobs` / `workflows`
изолированы по session; `Agent` (и `AssetStore`) общий, но контекст ссылается только на свои id.

## Media-agnostic invariant (AD-03)
`ConversationContext` и `ConversationAgent` не содержат `if image/elif video/elif audio`. Типы
сопоставляются по строковым полям manifest (`asset_inputs[role].kind`) и Asset (`type`).

## Тесты
`tests/test_conversation_m7.py` (8): поля контекста; multi-turn chain (generate → image.edit на
active_asset → `lineage(B)==[B,A]`); session isolation; explicit override; error не заменяет
active_asset; type-mismatch active → unresolved (AD-23); приоритет резолюции; real chain на
remote ComfyUI (skip без `COMFY_REMOTE_URL`, не fake-success).

См. `PROJECT_SPEC.md` §15, `docs/11_CONVERSATION_MODEL.md`, AD-03, AD-23, AD-29.
