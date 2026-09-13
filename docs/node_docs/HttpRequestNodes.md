# ComfyUI-HttpRequestNodes

HTTP запросы, конвертеры медиа и утилиты для ComfyUI.
Установка: `custom_nodes/ComfyUI-HttpRequestNodes`

---

## Get Request Node
- **Category:** RequestNode/Get Request
- **Purpose:** HTTP GET запрос
- **Module:** custom_nodes.ComfyUI-HttpRequestNodes
- **Related:** Post Request Node, Rest Api Node, KeyValueNode

**Inputs:**
- `target_url` (STRING, required): URL для запроса
- `headers` (KEY_VALUE, optional): Заголовки HTTP
- `query_list` (KEY_VALUE, optional): Параметры запроса (query string)

**Outputs:**
- `text` (STRING): Ответ как текст
- `file` (BYTES): Ответ как байты
- `json` (JSON): Ответ как JSON
- `any` (ANY): Ответ как байты

**Configuration:**
- proxy: Не используется (proxies={http:None, https:None})
- timeout: System default
- retry: Настраивается через Retry Settings Node

**Example:**
```json
{"target_url": "https://jsonplaceholder.typicode.com/posts/1"}
```

---

## Post Request Node
- **Category:** RequestNode/Post Request
- **Purpose:** HTTP POST запрос с JSON body
- **Module:** custom_nodes.ComfyUI-HttpRequestNodes
- **Related:** Get Request Node, Rest Api Node, Form Post Request Node

**Inputs:**
- `target_url` (STRING, required): URL для запроса
- `headers` (KEY_VALUE, optional): Заголовки HTTP
- `body` (STRING, optional): JSON body запроса

**Outputs:**
- `text` (STRING): Ответ как текст
- `file` (BYTES): Ответ как байты
- `json` (JSON): Ответ как JSON
- `any` (ANY): Ответ как байты

**Configuration:**
- proxy: Не используется
- content-type: application/json

**Example:**
```json
{"target_url": "https://jsonplaceholder.typicode.com/posts", "body": "{\"title\": \"foo\"}"}
```

---

## Form Post Request Node
- **Category:** RequestNode/Post Request
- **Purpose:** HTTP POST запрос с form-data (multipart)
- **Module:** custom_nodes.ComfyUI-HttpRequestNodes
- **Related:** Post Request Node, Media Form Post Node

**Inputs:**
- `target_url` (STRING, required): URL для запроса
- `headers` (KEY_VALUE, optional): Заголовки HTTP
- `form_fields` (KEY_VALUE, optional): Поля формы

**Outputs:**
- `text` (STRING): Ответ как текст
- `json` (JSON): Ответ как JSON
- `any` (ANY): Ответ как байты

**Example:**
```json
{"target_url": "https://httpbin.org/post", "form_fields": {}}
```

---

## Rest Api Node
- **Category:** RequestNode/REST API
- **Purpose:** Универсальный HTTP запрос (GET/POST/PUT/DELETE/PATCH/HEAD/OPTIONS)
- **Module:** custom_nodes.ComfyUI-HttpRequestNodes
- **Related:** Get Request Node, Post Request Node, Retry Settings Node

**Inputs:**
- `target_url` (STRING, required): URL для запроса
- `method` (ENUM [GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS], required): HTTP метод
- `headers` (KEY_VALUE, optional): Заголовки HTTP
- `body` (STRING, optional): Тело запроса
- `retry_config` (RETRY_SETTING, optional): Конфигурация retry

**Outputs:**
- `text` (STRING): Ответ как текст
- `file` (BYTES): Ответ как байты
- `json` (JSON): Ответ как JSON
- `headers` (DICT): Заголовки ответа
- `status_code` (INT): HTTP статус код
- `any` (ANY): Ответ как байты

**Configuration:**
- supports_retry: Да (через Retry Settings Node)
- timeout: System default

**Example:**
```json
{"target_url": "https://api.example.com/data", "method": "GET"}
```

---

## Binary Post Request Node
- **Category:** RequestNode/REST API
- **Purpose:** Отправка сырых байтов (application/octet-stream)
- **Module:** custom_nodes.ComfyUI-HttpRequestNodes
- **Related:** Media Form Post Node, Rest Api Node

**Inputs:**
- `target_url` (STRING, required): URL для запроса
- `body` (BYTES, required): Данные для отправки
- `method` (ENUM [POST, PUT, PATCH], required): HTTP метод
- `content_type` (STRING, optional): Content-Type заголовок
- `headers` (KEY_VALUE, optional): Дополнительные заголовки

**Outputs:**
- `text` (STRING): Ответ как текст
- `response_bytes` (BYTES): Ответ как байты
- `json` (JSON): Ответ как JSON
- `status_code` (INT): HTTP статус код
- `response_headers` (DICT): Заголовки ответа

**Example:**
```json
{"target_url": "https://api.example.com/upload", "method": "POST", "content_type": "application/octet-stream"}
```

---

## Media Form Post Node
- **Category:** RequestNode/Post Request
- **Purpose:** Отправка мультимедиа (IMAGE/AUDIO/VIDEO) через multipart/form-data
- **Module:** custom_nodes.ComfyUI-HttpRequestNodes
- **Related:** Form Post Request Node, Binary Post Request Node

**Inputs:**
- `target_url` (STRING, required): URL для запроса
- `form_fields` (KEY_VALUE, optional): Поля формы
- `headers` (KEY_VALUE, optional): Заголовки
- `image` (IMAGE, optional): Изображение ComfyUI
- `image_bytes` (BYTES, optional): Байты изображения
- `audio_bytes` (BYTES, optional): Байты аудио
- `video_bytes` (BYTES, optional): Байты видео
- `field_name` (STRING, default: "file"): Имя поля формы для файлов

**Outputs:**
- `text` (STRING): Ответ как текст
- `response_bytes` (BYTES): Ответ как байты
- `json` (JSON): Ответ как JSON
- `status_code` (INT): HTTP статус код
- `response_headers` (DICT): Заголовки ответа

**Example:**
```json
{"target_url": "https://api.example.com/upload", "field_name": "file"}
```

---

## Key/Value Node
- **Category:** RequestNode/KeyValue
- **Purpose:** Создаёт пары ключ-значение для HTTP заголовков и параметров
- **Module:** custom_nodes.ComfyUI-HttpRequestNodes
- **Related:** Get Request Node, Post Request Node, Rest Api Node

**Inputs:**
- `key` (STRING): Ключ
- `value` (STRING): Значение

**Outputs:**
- `KEY_VALUE` (KEY_VALUE): Пара ключ-значение

**Example:**
```json
{"key": "Authorization", "value": "Bearer token123"}
```

---

## Retry Settings Node
- **Category:** RequestNode/KeyValue
- **Purpose:** Конфигурация повторных попыток для HTTP запросов
- **Module:** custom_nodes.ComfyUI-HttpRequestNodes
- **Related:** Rest Api Node

**Inputs:**
- `max_retries` (INT, default: 3): Максимальное количество попыток
- `retry_delay` (FLOAT, default: 1.0): Задержка между попытками (секунды)

**Outputs:**
- `RETRY_SETTING` (RETRY_SETTING): Конфигурация retry

**Example:**
```json
{"max_retries": 5, "retry_delay": 2.0}
```

---

## String Replace Node
- **Category:** RequestNode/Utils
- **Purpose:** Замена подстрок в строке (плейсхолдеры)
- **Module:** custom_nodes.ComfyUI-HttpRequestNodes
- **Related:** Key/Value Node

**Inputs:**
- `text` (STRING): Исходная строка
- `old_string` (STRING): Строка для замены
- `new_string` (STRING): Новая строка

**Outputs:**
- `output_string` (STRING): Результат замены

**Example:**
```json
{"text": "Hello {{name}}", "old_string": "{{name}}", "new_string": "World"}
```

---

## Image To Base64 Node
- **Category:** RequestNode/Converters
- **Purpose:** Конвертирует ComfyUI IMAGE → Base64 строку
- **Module:** custom_nodes.ComfyUI-HttpRequestNodes
- **Related:** Image To Blob Node, Blob To Image Node

**Inputs:**
- `image` (IMAGE): Изображение ComfyUI

**Outputs:**
- `base64_string` (STRING): Base64 строка изображения

---

## Image To Blob Node
- **Category:** RequestNode/Converters
- **Purpose:** Конвертирует ComfyUI IMAGE → байты (PNG)
- **Module:** custom_nodes.ComfyUI-HttpRequestNodes
- **Related:** Image To Base64 Node, Blob To Image Node

**Inputs:**
- `image` (IMAGE): Изображение ComfyUI

**Outputs:**
- `image_bytes` (BYTES): Байты изображения (PNG)

---

## Audio To Blob Node
- **Category:** RequestNode/Converters
- **Purpose:** Конвертирует ComfyUI AUDIO → байты WAV
- **Module:** custom_nodes.ComfyUI-HttpRequestNodes
- **Related:** Blob To Audio Node, Base64 To Audio Node

**Inputs:**
- `audio` (AUDIO): Аудио ComfyUI

**Outputs:**
- `wav_bytes` (BYTES): Байты WAV

---

## Video To Blob Node
- **Category:** RequestNode/Converters
- **Purpose:** Конвертирует Comfyui VIDEO → байты (MP4/GIF)
- **Module:** custom_nodes.ComfyUI-HttpRequestNodes
- **Related:** Blob To Video Node

**Inputs:**
- `video` (VIDEO): Видео ComfyUI
- `format` (ENUM [mp4, gif], default: mp4): Выходной формат
- `fps` (INT, default: 24): Кадров в секунду

**Outputs:**
- `video_bytes` (BYTES): Байты видео
- `frame_count` (INT): Количество кадров

---

## Base64 To Audio Node
- **Category:** RequestNode/Converters
- **Purpose:** Конвертирует Base64 строку → ComfyUI AUDIO
- **Module:** custom_nodes.ComfyUI-HttpRequestNodes
- **Related:** Audio To Blob Node, Blob To Audio Node

**Inputs:**
- `base64_string` (STRING): Base64 строка WAV

**Outputs:**
- `audio` (AUDIO): Аудио ComfyUI

---

## Blob To Image Node
- **Category:** RequestNode/Utils
- **Purpose:** Конвертирует байты (PNG/JPEG/BMP/WebP) → ComfyUI IMAGE
- **Module:** custom_nodes.ComfyUI-HttpRequestNodes
- **Related:** Image To Blob Node, Blob To Batch Image Node

**Inputs:**
- `bytes` (BYTES): Байты изображения

**Outputs:**
- `image` (IMAGE): Изображение ComfyUI [batch, height, width, channels]

---

## Blob To Batch Image Node
- **Category:** RequestNode/Utils
- **Purpose:** Конвертирует байты → ComfyUI IMAGE (поддержка multi-page TIFF)
- **Module:** custom_nodes.ComfyUI-HttpRequestNodes
- **Related:** Blob To Image Node

**Inputs:**
- `bytes` (BYTES): Байты изображения

**Outputs:**
- `images` (IMAGE): Изображение ComfyUI

---

## Blob To Audio Node
- **Category:** RequestNode/Utils
- **Purpose:** Конвертирует байты WAV → ComfyUI AUDIO
- **Module:** custom_nodes.ComfyUI-HttpRequestNodes
- **Related:** Audio To Blob Node, Base64 To Audio Node

**Inputs:**
- `bytes` (BYTES): Байты WAV

**Outputs:**
- `audio` (AUDIO): Аудио ComfyUI {"waveform": [batch, channels, samples], "sample_rate": int}

---

## Blob To Video Node
- **Category:** RequestNode/Utils
- **Purpose:** Конвертирует байты видео (MP4/GIF/WebM) → ComfyUI VIDEO
- **Module:** custom_nodes.ComfyUI-HttpRequestNodes
- **Related:** Video To Blob Node

**Inputs:**
- `bytes` (BYTES): Байты видео

**Outputs:**
- `video` (VIDEO): Видео ComfyUI (совместимо с VHS нодами)

---

## Chainable Upload Image
- **Category:** RequestNode/Utils
- **Purpose:** Объединяет изображения в батч для отправки
- **Module:** custom_nodes.ComfyUI-HttpRequestNodes
- **Related:** Image To Blob Node, Media Form Post Node

**Inputs:**
- `image` (IMAGE): Изображение ComfyUI
- `image_batch_in` (IMAGE, optional): Предыдущий батч

**Outputs:**
- `image_batch_out` (IMAGE): Батч изображений
