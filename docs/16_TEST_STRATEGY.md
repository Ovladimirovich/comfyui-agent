> Source of truth: `PROJECT_SPEC.md` v0.2 (APPROVED).
> Derivative document — не вводит новых архитектурных решений.

# 16 — Test Strategy

## Уровни
### Unit (без ComfyUI)
- Asset, Capability, Manifest, Router, Workflow Engine, Job, Verifier.

### Integration
- Agent → Operator; Operator → ComfyUI (на реальном ComfyUI).

### E2E (реальный ComfyUI, без mock)
```text
input → workflow → ComfyUI → output
```

## Обязательное
- **Без mock считается только реальный E2E** (M10).
- **Media-agnostic тест (M4):** capability роутится тем же pipeline (Agent/Operator/Job/WorkflowEngine) без изменения ядра — единый путь для `txt2img`/`video_generate`/`audio_generate`. Доказывает отсутствие image-specific coupling. На этапе M4 использовался declared-only `video.generate`; в M6 `video_generate` стал исполнимым и реальный video-E2E доказан (M6). DECLARED_ONLY-механизм (AD-27) сохранён для будущих capability без графа.

## Покрытие по milestone
- M1: Client+Runtime против живого ComfyUI (`/system_stats`,`/object_info`,`/queue`).
- M2: AssetStore (файл→Asset).
- M3: resolve `image.generate` → AVAILABLE workflow через фильтры.
- M4: реальный txt2img E2E + media-agnostic video.generate тест.
- M5: Provider/Model catalog (bind checkpoint).
- M6: реальный Video E2E (`video_generate` исполним, доказан на remote Colab T4). Исходный roadmap-M6 (img2img/upscale + input compatibility) — future gap.
- M7: многоходовый context (скрипт).
- M8: Agent+LLM (Planner/Tools).
- M9: UI (чат+preview+progress).
- M10: полный реальный E2E без mock.

См. `PROJECT_SPEC.md` §22, §23, AD-14/AD-16.
