> Source of truth: `PROJECT_SPEC.md` v0.2 (APPROVED).
> Derivative document — не вводит новых архитектурных решений.

# 14 — Runtime Compatibility

## RuntimeInfo
```text
accelerator     — directml | cuda | cpu   (v2: cpu)
vram_gb         — доступный объём VRAM
fp16            — поддержка fp16 (v1: true, --force-fp16)
xformers        — (v1: false, --disable-xformers)
lowvram         — (v1: true, --lowvram)
comfyui_version — фактическая версия (может быть UNKNOWN)
```

## Правило совместимости
```text
workflow.requirements + workflow.min_comfyui_version → RuntimeInfo
  → AVAILABLE | UNAVAILABLE | UNKNOWN
```
- KNOWN + compatible → AVAILABLE
- KNOWN + incompatible → UNAVAILABLE (reason)
- UNKNOWN (версия ComfyUI не определена) → UNKNOWN, НЕ AVAILABLE (AD-18)
- UNKNOWN (поля RuntimeInfo — vram/accelerator/fp16/xformers — не определены) → `unknown_runtime`, НЕ AVAILABLE (AD-18)

## Особенности текущего runtime (CPU)
- ComfyUI 0.34.5 + Python 3.13.12 + Torch 2.12.1+cpu.
- Первая генерация грузит модель ~20s/20 steps; очередь последовательная.
- Ноды на xformers/CUDA несовместимы → отбрасываются.
- `min_comfyui_version` сверяется с фактической версией; неопределённая → UNKNOWN (override только осознанный).
- WS execution events не приходят → fallback на /history polling (inv 5/6).

## Legacy v1 (AMD DirectML) — historical reference
- Первая генерация грузит модель в VRAM 10–30с; очередь последовательная.
- Ноды на xformers/CUDA несовместимы → отбрасываются на AMD.
- `min_comfyui_version` сверяется с фактической версией; неопределённая → UNKNOWN (override только осознанный).

См. `PROJECT_SPEC.md` §13, AD-18.
