> Source of truth: `PROJECT_SPEC.md` v0.2 (APPROVED).
> Derivative document — не вводит новых архитектурных решений.

# 13 — UI Contract

## Минимальный UI (НЕ Control Center)
```text
┌───────────────────────────────┐
│          CHAT                 │
│ user message                  │
│ image/video attachment         │
│ agent status                  │
│ [generated image/video]        │
├───────────────────────────────┤
│ Attach │ message         Send │
└───────────────────────────────┘
```

## Требования
- Чат + preview ассетов + progress-bar.
- Без сложного редактора workflow.
- Attach принимает изображения/видео как входные ассеты (роль input).
- Статус агента и прогресс Job отображаются явно.
- Сгенерированный результат — как Asset (image/video), с lineage к предыдущим.

## Границы
- UI — только интерфейс оператора; вся логика выбора — на сервере (Agent/Registry).

См. `PROJECT_SPEC.md` §21 (UI).
