> Source of truth: `PROJECT_SPEC.md` v0.2 (APPROVED).
> Derivative document — не вводит новых архитектурных решений.

# 05 — Asset Model

## Asset (объект, не файл)
```text
Asset:
  id            — уникальный
  type          — image|video|audio|mask|sequence|document|other (расширяемо)
  mime          — MIME-тип
  path          — путь к файлу на диске (в разрешённом root)
  metadata      — открытый словарь (width,height,duration,fps,…)
  role          — input|output|reference
  source_asset  — id входного ассета (lineage)
  created_from  — id Job, породившего ассет
  created_at    — timestamp
```

## Lineage
```text
image_001 ──(Job J1)──▶ video_001 ──(Job J2)──▶ video_002
```
- `Asset.source_asset` + `Asset.created_from` задают рёбра lineage-графа.
- `Job.input_assets` / `Job.output_assets` фиксируют связку.
- `AssetStore.lineage(asset_id)` обходит цепочку по `source_asset`.
- Lineage — основа многоходового контекста («её/теперь/ещё» → `active_asset`).

## Владение файлами (AD-20 / OAQ-08/09)
- Persistent assets: `data/assets`, `static/assets` (range/streaming отдача).
- Execution temp: отдельный класс; cleanup только после подтверждения backend-ом (signal safe-to-cleanup). Не удалять по возврату `backend_ref`, пока backend может читать файл (критично для видео).
- Path confinement: только разрешённые roots; запрет traversal.

См. `PROJECT_SPEC.md` §8, §19.
