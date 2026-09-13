# ComfyUI-Qwen-VL-API

VLM (Vision Language Model) через Qwen API.
Установка: `custom_nodes/ComfyUI-Qwen-VL-API`

---

## QWenVL_API_S_Zho
- **Category:** QWenVL/Chinese
- **Purpose:** Распознавание текста на изображении (Chinese OCR)
- **Module:** custom_nodes.ComfyUI-Qwen-VL-API

**Inputs:**
- `image` (IMAGE): Входное изображение
- `prompt` (STRING, optional): Дополнительный запрос

**Outputs:**
- `text` (STRING): Распознанный текст

**Configuration:**
- API key: через `config.json` (QWENVL_API_KEY)

---

## QWenVL_API_S_Multi_Zho
- **Category:** QWenVL/Multi
- **Purpose:** Многоязычное распознавание текста на изображении
- **Module:** custom_nodes.ComfyUI-Qwen-VL-API

**Inputs:**
- `image` (IMAGE): Входное изображение
- `prompt` (STRING, optional): Дополнительный запрос
- `language` (STRING, default: "auto"): Язык распознавания

**Outputs:**
- `text` (STRING): Распознанный текст
