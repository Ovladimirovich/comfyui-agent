# M5 — Provider + Model + Backend Runtime (plan, remote-first)

**Статус:** PLAN (не начинать без команды автора). M4 архитектурно завершён (E2E BLOCKED_BY_ENVIRONMENT — железо, не код).

**Ключевой контекст (AD-29, PROJECT_SPEC §27):** Physical location of ExecutionBackend is not an Agent concern.
Удалённый ComfyUI — штатной backend, а не костыль. `Provider` (логический) ≠ `Backend` (место исполнения).
`ComfyUIProvider` делегирует конкретному backend-объекту; различия local/remote — ниже Provider/Backend boundary.

## Scope M5

```text
local Agent
   → Provider (comfyui)
      → ExecutionBackend
            ├── local_comfyui   (http://127.0.0.1:8188)
            └── remote_comfyui  (https://server:8188)   ← штатной сценарий
   → model на сервере
   → Job
   → результат
   → local AssetStore
```

Обязательная проверка реального сценария: **local Agent → Provider → remote ComfyUI → model на сервере → Job → результат → local AssetStore**.
Это настоящая проверка идеи: вычисления могут быть на другой машине, верхние слои не меняются.

## Минимальные изменения (C из audit, НЕ ломают M1–M4)

1. `app/engine/websocket.py`: схема `ws/wss` из `base_url` (`https→wss`).
2. `app/engine/engine.py`: `execute` ловит `ComfyUIWebSocketError` и восстанавливает выхлоп через `provider.get_job(prompt_id)` (`/history`) — reconnect-safe Job (inv 5/6).
3. `app/comfy/client.py`: `DEFAULT_BASE_URL` из `COMFY_URL` env (fallback `127.0.0.1:8188`).
4. Различия local/remote — только в transport/backend layer. **Никаких `if remote:`/`if localhost:` в Engine/Job/Workflow/Asset.**

## Model Registry (треб. 12)

- Источник моделей уже есть: runtime discovery через `/object_info` (M1/M4). M5 поднимает поверх него **Model Catalog** (per-backend),
  не смешиваясь с runtime discovery и не становясь источником моделей для M4.
- Model Registry описывает доступные модели конкретного backend (inv 11): имя, тип, размер, теги, default.

## Multi-backend (inv 12, D из audit)

- `Provider` может указывать backend (`local_comfyui`/`remote_comfyui`); Agent в будущем выбирает backend по capability+runtime+политике.
- M5 НЕ обязан реализовать выбор между несколькими backend сразу; достаточно, чтобы один и тот же Provider работал с обоими endpoint.

## Video E2E

- `video.generate` в M6 стал исполнимым (DECLARED_ONLY снят, AD-27 уточнён); Video E2E доказан отдельным milestone тем же execution engine.
  при появлении remote GPU + нормального video workflow. Не «навсегда вне scope».

## REVIEW_PROTOCOL (M5)

- Не расширять M5 за пределы Provider/Model/Backend Runtime.
- Не ломать M4 (engine/provider/asset/websocket).
- Remote endpoint работает тем же `WorkflowEngine`/`Job`/`Verifier`/`Asset`/`ExecutionPlan` (inv 1–13).
- Никаких `if remote/local` в domain/execution.
- Реальная проверка: E2E на remote ComfyUI (если доступен endpoint), иначе skip (не mock).
