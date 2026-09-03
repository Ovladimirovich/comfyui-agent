> Source of truth: `PROJECT_SPEC.md` v0.2 (APPROVED).
> Derivative document — не вводит новых архитектурных решений.

# 11 — Conversation Model

## ConversationContext
```text
ConversationContext:
  messages      — история сообщений
  assets        — известные ассеты сессии
  jobs          — известные Job'ы
  workflows     — использованные workflow (id@version)
  parameters    — последние параметры
  active_task   — текущая capability
  active_workflow
  active_job    — последний Job
  active_asset  — последний выходной Asset (для «её/теперь/ещё»)
  unresolved    — открытые уточнения
```

## Пример многоходового диалога
```text
User: [image] Сделай из неё видео.
 → image_001 → video.generate → workflow_X@ver → video_001

User: Сделай камеру медленнее.
 → active_asset = video_001 → modify/re-generate → video_002
```
Context хранит не только текст, но и активные assets/jobs/workflows. Lineage (source_asset/created_from) связывает результаты.

## Правила
- `active_asset` резолвит местоимения («её/теперь/ещё вариант») в предыдущий результат.
- `workflows` хранятся с версией (`id@version`) для воспроизводимости.

## Реализация (M7, 2026-08-30)
- `app/conversation.py`: `ConversationContext` (dataclass, только id/строки) + `ConversationAgent(Agent)` (session-scoped `sessions: dict[session_id, ConversationContext]`).
- `ConversationAgent.turn(session_id, capability|request, params, assets)` — один ход: выбор workflow (`Agent.prepare`) → резолюция входов (`Agent.resolve_asset_inputs`, расширен explicit > active_asset > reference) → `WorkflowEngine.execute` (тот же путь) → обновление контекста.
- `active_asset` становится активным только при `Job.SUCCESS`; при ошибке/исключении контекст НЕ перезаписывается (записывается в `unresolved`).
- `Agent.resolve_asset_inputs` расширен (обратно совместимо): `context`/`store`/`as_ids`/`required_roles`. Роль резолвится из active_asset только если `active_asset.type == required_roles[role]` (AD-23, без транскодинга).
- Persistence: process/session scoped (PROJECT_SPEC §15 не требует БД). При необходимости — отдельный минимальный механизм.
- См. `docs/19_CONVERSATION_CONTEXT.md`, `PROJECT_SPEC.md` §15.
