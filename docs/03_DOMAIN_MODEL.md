> Source of truth: `PROJECT_SPEC.md` v0.2 (APPROVED).
> Derivative document — не вводит новых архитектурных решений.

# 03 — Domain Model

## Сущности
```text
Asset              — медиа-объект системы (не файл)
Capability          — логич. способность (image.generate, video.generate, …)
Provider            — абстракция доступа к execution (comfyui)
ExecutionBackend    — то, что реально исполняет (local_comfyui)
Model               — конкретная модель/чекпоинт внутри provider
Workflow            — исполняемый граф + manifest (с version)
WorkflowManifest    — декларативное описание workflow
RuntimeInfo         — реальные возможности железа/рантайма
Intent              — намерение агента (capability + params + assets)
ExecutionPlan       — capability + workflow_id@version + provider + bindings + params
Job                 — единица исполнения (один POST /prompt)
Result              — верифицированные выходные ассеты
ConversationContext — сообщения + активные assets/jobs/workflows
```

## Связи
```text
Capability → Workflow → Provider → Model
Asset → ExecutionPlan → Job → Asset (lineage)
Intent → Capability → Provider → Workflow → ExecutionPlan
ConversationContext → (Assets, Jobs, Workflows, Parameters, active_asset, active_job)
```

## Пояснения
- `ExecutionPlan` фиксирует конкретную версию workflow (AD-17) — основа воспроизводимости.
- `Asset` — объект с metadata+path, не сам файл (AD-05).
- `Provider` и `ExecutionBackend` разделены концептуально (AD-01).

См. `PROJECT_SPEC.md` §7.
