# qwen3vl_api

Qwen3-VL Vision Language Model через API.
Установка: `custom_nodes/qwen3vl_api`

---

## QWEN_APIKey
- **Category:** QWEN3VL_API
- **Purpose:** Установка API ключа для Qwen
- **Module:** custom_nodes.qwen3vl_api

**Inputs:**
- `api_key` (STRING): API ключ

**Outputs:**
- `STRING` (STRING): Статус

---

## QWEN3VL_Image
- **Category:** QWEN3VL_API
- **Purpose:** Анализ изображения через Qwen3-VL
- **Module:** custom_nodes.qwen3vl_api

**Inputs:**
- `image` (IMAGE): Входное изображение
- `prompt` (STRING): Запрос к модели
- `api_key` (STRING, optional): API ключ

**Outputs:**
- `STRING` (STRING): Ответ модели

---

## QWEN3VL_Video
- **Category:** QWEN3VL_API
- **Purpose:** Анализ видео через Qwen3-VL
- **Module:** custom_nodes.qwen3vl_api

**Inputs:**
- `video` (VIDEO): Входное видео
- `prompt` (STRING): Запрос к модели
- `api_key` (STRING, optional): API ключ

**Outputs:**
- `STRING` (STRING): Ответ модели

---

## QWEN3_Text
- **Category:** QWEN3VL_API
- **Purpose:** Генерация текста через Qwen3
- **Module:** custom_nodes.qwen3vl_api

**Inputs:**
- `prompt` (STRING): Текст-промпт
- `api_key` (STRING, optional): API ключ
- `max_tokens` (INT, default: 512): Максимальная длина ответа

**Outputs:**
- `STRING` (STRING): Сгенерированный текст
- `STRING` (STRING): Дополнительная информация

---

## QWEN_TextProcess
- **Category:** QWEN3VL_API
- **Purpose:** Обработка текста (подсчет токенов и т.д.)
- **Module:** custom_nodes.qwen3vl_api

**Inputs:**
- `text` (STRING): Входной текст

**Outputs:**
- `STRING` (STRING): Обработанный текст
- `INT` (INT): Количество токенов

---

## QWEN_TextOperation
- **Category:** QWEN3VL_API
- **Purpose:** Операции с текстом (конкатенация, замена)
- **Module:** custom_nodes.qwen3vl_api

**Inputs:**
- `text1` (STRING): Первый текст
- `text2` (STRING): Второй текст
- `operation` (ENUM: [concat, replace]): Операция

**Outputs:**
- `STRING` (STRING): Результат

---

## LoadImageFromFolder
- **Category:** QWEN3VL_API
- **Purpose:** Загрузка изображений из папки
- **Module:** custom_nodes.qwen3vl_api

**Inputs:**
- `folder_path` (STRING): Путь к папке
- `file_name` (STRING): Имя файла

**Outputs:**
- `IMAGE` (IMAGE): Загруженное изображение
- `STRING` (STRING): Путь к файлу

---

## LoadVideoFromFolder
- **Category:** QWEN3VL_API
- **Purpose:** Загрузка видео из папки
- **Module:** custom_nodes.qwen3vl_api

**Inputs:**
- `folder_path` (STRING): Путь к папке
- `file_name` (STRING): Имя файла

**Outputs:**
- `VIDEO` (VIDEO): Загруженное видео
- `STRING` (STRING): Путь к файлу
