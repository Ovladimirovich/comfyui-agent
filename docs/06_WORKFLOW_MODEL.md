> Source of truth: `PROJECT_SPEC.md` v0.2 (APPROVED).
> Derivative document — не вводит новых архитектурных решений.

# 06 — Workflow Model

## Состав
Workflow = `workflow.json` (ComfyUI API-формат графа) + `manifest.json` (декларативное описание).

## Manifest (ключевые поля)
Пример — `txt2img` (без входных ассетов):
```json
{
  "id": "txt2img",
  "version": "1.0.0",
  "capability": "image.generate",
  "provider": "comfyui",
  "backend": "local_comfyui",
  "inputs": { "prompt": {"node":"6","field":"text"}, "width": {"node":"5","field":"width"} },
  "outputs": { "result": {"node":"9","kind":"image"} },
  "parameters": { "steps": {"default":20,"min":1,"max":60} },
  "required_models": ["checkpoint"],
  "required_custom_nodes": [],
  "min_comfyui_version": "0.0.0",
  "requirements": {"accelerator":"any","xformers":false,"min_vram_gb":4,"fp16":true},
  "limits": { "max_upload_bytes": 209715200, "max_asset_duration": 0,
              "max_video_width": 0, "max_video_height": 0, "max_sequence_length": 0 }
}
```

`txt2img` НЕ имеет `asset_inputs` (text-to-image без входного медиа).

Пример — `img2img` (входной ассет через реальный `LoadImage`):
```json
{
  "id": "img2img",
  "version": "1.0.0",
  "capability": "image.edit",
  "provider": "comfyui",
  "backend": "local_comfyui",
  "inputs": { "prompt": {"node":"6","field":"text"}, "denoise": {"node":"15","field":"denoise"} },
  "asset_inputs": { "image": {"node":"10","field":"image","kind":"image"} },
  "outputs": { "result": {"node":"9","kind":"image"} },
  "parameters": { "steps": {"default":20,"min":1,"max":60} },
  "required_models": ["checkpoint"],
  "required_custom_nodes": [],
  "min_comfyui_version": "0.0.0",
  "requirements": {"accelerator":"any","xformers":false,"min_vram_gb":4,"fp16":true},
  "limits": { "max_upload_bytes": 209715200 }
}
```

## Правила
- `manifest.inputs` — логич. параметры → node/field (LLM видит только логику, AD-04).
- `manifest.asset_inputs` — роли входных ассетов → node/field/kind (input compatibility); показан на `img2img` с реальным `LoadImage` (node 10).
- `manifest.outputs` — контракт результата (kind для верификации).
- Manifest НЕ содержит image-specific логики.
- `version` — semver; `latest` = max VALIDATED/AVAILABLE semver (только candidate/selection); ExecutionPlan фиксирует `workflow_id@version` (AD-17/AD-24).
- `limits` — capability/workflow-aware ограничения (AD-21); семантика: null=unlimited, 0=forbidden, positive=limit (AD-25).
- `declared_only:true` — манифест объявляет capability без `workflow.json`; НЕ в AVAILABLE; для архитектурных тестов M4 (AD-27).

## Workflow Lifecycle
```text
DISCOVERED → VALIDATED → AVAILABLE | UNAVAILABLE | UNKNOWN
```
Причины UNAVAILABLE: missing_model, missing_custom_node, incompatible_runtime, insufficient_vram, invalid_manifest, invalid_workflow, input_incompatible.
Причина UNKNOWN: unknown_version, unknown_runtime (AD-18). UNKNOWN ≠ AVAILABLE.

## Validation (OAQ-05)
1. validation манифеста (схема);
2. структурная валидация `workflow.json`.
Не гарантирует успешное исполнение графа — окончательно проверяется runtime.

См. `PROJECT_SPEC.md` §11, §12, AD-04/AD-17/AD-21.
