# pollinations-byop

AI генерация через Pollinations API (бесплатно, без ключа).
Установка: `custom_nodes/pollinations-byop`

---

## PollinationsImageGen
- **Category:** Pollinations/Image
- **Purpose:** Генерация изображений через Pollinations AI
- **Module:** custom_nodes.pollinations-byop
- **Related:** PollinationsTextGen, PollinationsAudioGen

**Inputs:**
- `prompt` (STRING): Текст-промпт для генерации
- `width` (INT, default: 1024): Ширина
- `height` (INT, default: 1024): Высота
- `seed` (INT, default: 0): Сид
- `model` (ENUM: [flux, stable-diffusion-xl, ...], default: flux): Модель

**Outputs:**
- `IMAGE` (IMAGE): Сгенерированное изображение
- `STRING` (STRING): Промпт (для сохранения)

**Configuration:**
- API key: Не требуется (бесплатный API)
- Rate limit: ~10 requests/min

---

## PollinationsTextGen
- **Category:** Pollinations/Text
- **Purpose:** Генерация текста через Pollinations AI
- **Module:** custom_nodes.pollinations-byop

**Inputs:**
- `prompt` (STRING): Текст-промпт
- `model` (ENUM: [openai-gpt-4o, meta-llama/llama-3.3-70b-instruct, ...], default: openai-gpt-4o): Модель
- `max_tokens` (INT, default: 1024): Максимальная длина

**Outputs:**
- `STRING` (STRING): Сгенерированный текст

---

## PollinationsAudioGen
- **Category:** Pollinations/Audio
- **Purpose:** Генерация аудио через Pollinations AI
- **Module:** custom_nodes.pollinations-byop

**Inputs:**
- `prompt` (STRING): Текст-промпт
- `model` (ENUM: [stable-audio-open-1.0, musicgen-large, ...], default: stable-audio-open-1.0): Модель
- `duration` (FLOAT, default: 10): Длительность в секундах

**Outputs:**
- `STRING` (STRING): URL аудио файла

---

## PollinationsVideoGen
- **Category:** Pollinations/Video
- **Purpose:** Генерация видео через Pollinations AI
- **Module:** custom_nodes.pollinations-byop

**Inputs:**
- `prompt` (STRING): Текст-промпт
- `duration` (INT, default: 4): Длительность в секундах

**Outputs:**
- `STRING` (STRING): URL видео файла

---

## PollinationsBYOPLogin
- **Category:** Pollinations/BYOP
- **Purpose:** Аутентификация для BYOP (Bring Your Own Provider)
- **Module:** custom_nodes.pollinations-byop

**Inputs:**
- `api_key` (STRING): API ключ Pollinations
- `provider` (STRING): Название провайдера
- `endpoint` (STRING): URL endpoint

**Outputs:**
- `STRING` (STRING): Статус
- `STRING` (STRING): Пользователь
- `STRING` (STRING): Email
- `INT` (INT): Credits remaining
