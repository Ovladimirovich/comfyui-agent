# upscale — Увеличение разрешения изображения

Capability: `image.upscale`

## Граф
```
LoadImage (10) → ImageScale (20, lanczos) → SaveImage (30)
```

## Входы
| Параметр | Тип | Описание |
|----------|-----|----------|
| `image` | asset (image) | Входное изображение |
| `upscale_method` | string | Алгоритм масштабирования: `lanczos` (default), `bilinear`, `bicubic`, `nearest-exact` |
| `width` | int | Целевая ширина (1–8192) |
| `height` | int | Целевая высота (1–8192) |

## Выходы
| Имя | Тип | Описание |
|-----|-----|----------|
| `result` | image | Увеличенное изображение |

## Примеры
- `«увеличь изображение до 2048x2048»` → `image.upscale`, params: width=2048, height=2048
- Multi-turn: `«сгенерируй кота» → «сделай реалистивнее» → «увеличь до 1024x1024»`

## Требования
- Встроенные ноды ComfyUI (LoadImage, ImageScale, SaveImage)
- Без custom nodes
- min_vram_gb: 2
