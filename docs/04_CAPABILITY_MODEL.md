> Source of truth: `PROJECT_SPEC.md` v0.2 (APPROVED).
> Derivative document — не вводит новых архитектурных решений.

# 04 — Capability Model

## Определение
`Capability` — НЕ workflow. Одна capability может иметь много workflow.

```text
Capability:
  id            — "image.generate" | "image.edit" | "image.inpaint" | "image.upscale"
                  | "video.generate" | "video.image_to_video" | "video.video_to_video"
                  | "video.upscale" | "audio.generate" | "custom.execute"
  media_input   — допустимые типы входных ассетов (для input compatibility)
  media_output  — тип выходного ассета
  operation     — семантика
  parameters    — логич. параметры (prompt, model, width, height, duration, fps, seed, …)
  requirements  — общие требования (accelerator, vram, …)
  constraints   — ограничения
```

## Правила
- Capability-список плоский и расширяемый.
- Конкретная модель (WAN/SD/…) — свойство workflow/provider-конфигурации, НЕ capability и НЕ архитектуры (AD-07).
- `media_input` используется Compatibility Filter для input compatibility (AD-23).

## Input compatibility (AD-23 / OAQ-14)
Выбор workflow зависит не только от `capability + runtime`, но и от доступных ассетов:
```text
Capability: video.image_to_video
Available:  asset_001=image, asset_002=video
Workflow A requires {image}  → совместим (есть image)
Workflow B requires {video}  → НЕсовместим (нет свободного video как вход)
```
Compatibility Filter проверяет: для каждого candidate сравнить `asset_inputs` (kind) с доступными Asset (type) и наличием обязательных inputs.

См. `PROJECT_SPEC.md` §9, §6 (Compatibility Filter), AD-23.
