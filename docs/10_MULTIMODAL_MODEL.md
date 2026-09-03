> Source of truth: `PROJECT_SPEC.md` v0.2 (APPROVED).
> Derivative document — не вводит новых архитектурных решений.

# 10 — Multimodal Model

## Входные modalities
Text, Image, Video, Audio (+ комбинации).

```text
Agent
  ↓
Asset ingestion (файл → Asset с metadata)
  ↓
Metadata extraction (тип/размер/длительность)
  ↓
[опц.] Vision/Audio understanding → текст (для Intent)
  ↓
Intent
```

## Два разных действия
- **Передача файла в ComfyUI** (asset wiring) — делает Provider/upload_asset; vision не нужен.
- **Понимание файла** (vision) — опционально, deferred (M6+); интерфейс `VisionUnderstand(asset)→text` pluggable, через тот же OpenAI-совместимый endpoint; для видео — семпл кадров.

## Ingestion limits (AD-21 / OAQ-10)
Применяются capability-aware limits из манифеста `limits` (duration/width/height/sequence) + глобальный `MAX_UPLOAD_BYTES`.

## Важно
Понимание файла и передача файла в ComfyUI — РАЗНЫЕ операции. Ядро не зависит от vision-понимания (M1–M4 работают без него).

См. `PROJECT_SPEC.md` §14, AD-21.
