> Source of truth: `PROJECT_SPEC.md` v0.2 (APPROVED).
> Derivative document — не вводит новых архитектурных решений.

# 07 — Provider / Execution Backend Model

## Разделение (концептуально, не смешивать)
```text
Capability → Provider → Workflow → Execution Backend
```

## Provider (comfyui)
```text
Provider (comfyui):
  id            — "comfyui"
  backend       — ExecutionBackend.id  ("local_comfyui")
  capabilities  — какие capability обслуживает
  models        — каталог доступных моделей (из /object_info)
  upload_asset(asset) → backend_ref   — транспорт ассета в backend
  execute(prompt) → prompt_id
  get_job(prompt_id) → JobStatus
  cancel(prompt_id)
```

## Execution Backend (local_comfyui)
```text
ExecutionBackend (local_comfyui):
  id            — "local_comfyui"
  kind          — comfyui-local
  (реально выполняет граф на GPU)
```

## Правила
### BackendRef (абстракция, AD-26 / NQ-03)
`Provider.upload_asset(asset) → BackendRef`:
```text
BackendRef:
  provider   — id провайдера ("comfyui")
  backend    — id backend ("local_comfyui")
  reference  — backend-specific ссылка (ComfyUI: {filename, subfolder, type})
  metadata   — открытый словарь (опц.)
```
ComfyUI-specific `reference` ({filename, subfolder, type}) внутри backend-specific, НЕ универсальный контракт. Другой backend — своя форма `reference`.

- v1: ровно один `Provider(comfyui)` поверх `Backend(local_comfyui)` (1:1, но понятия разделены, AD-01).
- Будущий внешний provider = новый класс за тем же интерфейсом; ядро не меняется.
- ComfyUI сам хостит модели/custom nodes — это **модели внутри** провайдера, не отдельные провайдеры.
- **Provider НЕ выбирает workflow** (AD-22). Workflow выбирает Workflow Selection Policy.
- Идентификация модели — точное имя файла из runtime, без fuzzy matching (OAQ-04).

См. `PROJECT_SPEC.md` §10, AD-01/AD-22.
