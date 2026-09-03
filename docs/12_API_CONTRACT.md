> Source of truth: `PROJECT_SPEC.md` v0.2 (APPROVED).
> Derivative document — не вводит новых архитектурных решений.

# 12 — API Contract

## Эндпоинты (бэкенд)
```text
POST /api/chat                  — сообщение + опц. attachments
POST /api/assets                — загрузка ассета
GET  /api/assets/{id}           — отдача ассета (range/streaming)
GET  /api/jobs/{id}             — статус Job (+progress, outputs)
POST /api/jobs/{id}/cancel      — отмена
GET  /api/capabilities          — список capabilities
GET  /api/workflows             — список workflow (со статусом lifecycle, включая UNKNOWN)
GET  /api/runtime               — RuntimeInfo
```

## Поток ответов
- Агент отвечает через SSE (или WebSocket) от `/api/chat`.
- Прогресс Job — через `GET /api/jobs/{id}` либо события в SSE.

## Границы
- Фронтенд и бэкенд НЕ придумывают свой API — контракт зафиксирован здесь.
- LLM tool interface НЕ содержит прямых путей ОС (OAQ-11).

См. `PROJECT_SPEC.md` §21.
