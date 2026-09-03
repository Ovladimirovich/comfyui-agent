> Source of truth: `PROJECT_SPEC.md` v0.2 (APPROVED).
> Derivative document — не вводит новых архитектурных решений.

# 08 — Execution Model

## Единица исполнения
Один `Job` = один `POST /prompt` (один граф) → один `prompt_id`.

- Многостадийный pipeline **внутри** ComfyUI — один граф = один Job.
- Pipeline **через несколько запусков** — несколько Job, связанных lineage (output Asset Job1 = input Asset Job2, AD-10).
- `ExecutionPlan` фиксирует `workflow_id@version` (AD-17).

## Поток
```text
ExecutionPlan
  → Operator.upload_assets (Provider.upload_asset → backend_ref)
  → WorkflowEngine.build (чистый маппинг logical→node/field)
  → Operator.execute(prompt) → prompt_id
  → WS-мониторинг (executing/progress/executed)
  → history
  → Verifier
  → Asset (role=output)
```

## Job Lifecycle
```text
CREATED → VALIDATED → QUEUED → RUNNING → COMPLETED → VERIFIED
FAILED | CANCELLED | TIMEOUT
```

## Cancellation semantics (AD-19 / OAQ-06)
- `Job = CANCELLED` по `cancel(job)` → `interrupt(prompt_id)`.
- ComfyUI может физически успеть создать partial output до interrupt.
- v1-политика: **discard** — частичные backend-outputs НЕ возвращаются агенту и не становятся Asset.
- НЕ утверждается, что ComfyUI гарантированно ничего не создал.

## Retry (OAQ-07)
Авто-retry в v1 нет. Каждый повтор — новый Job.

См. `PROJECT_SPEC.md` §16, §17, AD-10/AD-17/AD-19.
