# comfyui-openai-compatible

LLM через OpenAI-compatible endpoints (OpenAI, OpenRouter, Groq, LM Studio, Ollama, vLLM).
Установка: `custom_nodes/comfyui-openai-compatible`

---

## OpenAICompatibleChat
- **Category:** api/text
- **Purpose:** Чат с LLM через OpenAI-compatible API
- **Module:** custom_nodes.comfyui-openai-compatible
- **Related:** OpenAI API, OpenRouter, Groq, LM Studio, Ollama

**Inputs:**
- `base_url` (STRING, default: https://api.openai.com/v1): URL endpoint
- `api_key` (STRING, optional): API ключ (или env OPENAI_COMPATIBLE_API_KEY)
- `model` (STRING, default: gpt-4o): Модель для использования
- `text_1` (STRING, optional): Первый текстовый ввод
- `text_2` (STRING, optional): Второй текстовый ввод
- `text_3` (STRING, optional): Третий текстовый ввод
- ... (до 16 текстовых вводов)

**Outputs:**
- `text` (STRING): Ответ модели
- `text_1` ... `text_16` (STRING): Дополнительные выходы

**Configuration:**
- API key: можно задать через env переменные
- Models: автозагрузка через /models endpoint
- Max inputs: 16 текстовых входов

**Example:**
```json
{
  "base_url": "https://api.openai.com/v1",
  "api_key": "sk-...",
  "model": "gpt-4o",
  "text_1": "Hello, how are you?"
}
```
