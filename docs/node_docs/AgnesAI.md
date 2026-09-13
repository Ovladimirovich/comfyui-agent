# ComfyUI-Agnes-AI

Cloud-based AI generation via Agnes API.
Установка: `custom_nodes/ComfyUI-Agnes-AI`

---

## AgnesVideo
- **Category:** AILab/Agnes-AI
- **Purpose:** Генерация видео через Agnes API (текст→видео, изображение→видео)
- **Module:** custom_nodes.ComfyUI-Agnes-AI
- **Related:** AgnesImage, AgnesText

**Inputs:**
- `mode` (ENUM [Text To Video, Image To Video, First and Last Frame], default: Text To Video): Режим генерации
- `prompt` (STRING): Текст-промпт для генерации
- `quality` (ENUM [360p, 720p], default: 720p): Качество видео
- `image` (IMAGE, optional): Входное изображение (для Image To Video)
- `first_frame` (IMAGE, optional): Первый кадр (для First and Last Frame)
- `last_frame` (IMAGE, optional): Последний кадр (для First and Last Frame)
- `duration` (INT, default: 4): Длительность в секундах
- `seed` (INT, default: 0): Сид для воспроизводимости

**Outputs:**
- `video` (VIDEO): Сгенерированное видео
- `frames` (IMAGE): Все кадры видео
- `last_frame` (IMAGE): Последний кадр
- `audio` (AUDIO): Аудио из видео (если есть)

**Configuration:**
- API key: через `agnes_config.json` или панель настроек
- Base URL: https://api.agnes.ai/v1
- Timeout: system default

**Example:**
```json
{"mode": "Text To Video", "prompt": "a cat walking on the beach", "quality": "720p"}
```

---

## AgnesImage
- **Category:** AILab/Agnes-AI
- **Purpose:** Генерация изображений через Agnes API
- **Module:** custom_nodes.ComfyUI-Agnes-AI
- **Related:** AgnesVideo, AgnesText

**Inputs:**
- `prompt` (STRING): Текст-промпт для генерации
- `quality` (ENUM [standard, high], default: standard): Качество
- `size` (ENUM [512x512, 768x768, 1024x1024], default: 1024x1024): Размер
- `seed` (INT, default: 0): Сид для воспроизводимости

**Outputs:**
- `image` (IMAGE): Сгенерированное изображение

**Configuration:**
- API key: через `agnes_config.json`

---

## AgnesText
- **Category:** AILab/Agnes-AI
- **Purpose:** Генерация текста через Agnes API
- **Module:** custom_nodes.ComfyUI-Agnes-AI
- **Related:** AgnesImage, AgnesVideo

**Inputs:**
- `prompt` (STRING): Текст-промпт
- `max_tokens` (INT, default: 512): Максимальная длина ответа

**Outputs:**
- `text` (STRING): Сгенерированный текст
