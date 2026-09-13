# План P0 Фиксов — Agent Core Learning Loop

**Дата:** 2026-09-07
**Статус:** Planning

---

## Контекст

Learning Loop v1 доказан. Теперь нужно закрыть P0 разрывы чтобы Agent мог реально работать с существующими возможностями ComfyUI.

---

## P0-1: Planner Keywords Bug

### Проблема
```python
AUDIO_KEYWORDS = ("трек", "музыка", "звук", "аудио", "lo-fi", "beat", "sound")
# НЕТ слова "audio"!
```

Запрос "generate audio" → image.generate (default), потому что "audio" не в ключе.

### Фикс
**Файл:** `app/planner/heuristic.py:36`

```python
AUDIO_KEYWORDS = ("трек", "музыка", "звук", "аудио", "audio", "lo-fi", "beat", "sound")
```

### Проверка
```python
context = PlanContext(capabilities=['audio.generate', 'image.generate'])
result = planner.plan('generate audio', context)
assert result.capability == 'audio.generate'
assert 'audio_keyword' in result.rationale
```

---

## P0-2: KnowledgeCore Auto-Refresh

### Проблема
```python
kc = KnowledgeCore()
print(kc.get_schemas())  # []
print(kc.get_candidates())  # {}
```

Схемы и кандидаты не загружаются при инициализации. Нужно вызывать `refresh()` вручную.

### Фикс
**Файл:** `app/knowledge/core.py:81-103`

Добавить авто-загрузку из persistent store в `__init__`:

```python
def __init__(self, ...):
    ...
    # Загружаем сохранённые данные
    self._load_persistence()
    
    # Авто-загрузка схем из persistent store
    self._load_from_store()
```

Метод `_load_from_store()` уже существует (строка 134), нужно просто вызывать его.

### Проверка
```python
kc = KnowledgeCore()
# После фикса:
assert len(kc.get_schemas()) > 0  # Схемы загружены
assert len(kc.get_candidates()) > 0  # Кандидаты сгенерированы
```

---

## P0-3: text.generate Workflow

### Проблема
Capability `text.generate` существует, но нет workflow для её выполнения.

### Решение
Создать workflow используя `OpenAICompatibleChat` + `SaveText`.

**Файлы:**
- `workflows/text_generate/manifest.json`
- `workflows/text_generate/workflow.json`

### manifest.json
```json
{
  "id": "text_generate",
  "version": "1.0.0",
  "capability": "text.generate",
  "provider": "comfyui",
  "backend": "local_comfyui",
  "inputs": {
    "prompt": {"node": "1", "field": "prompts"},
    "model": {"node": "1", "field": "model"},
    "base_url": {"node": "1", "field": "base_url"}
  },
  "asset_inputs": {},
  "outputs": {
    "result": {"node": "2", "kind": "text"}
  },
  "parameters": {
    "model": {"default": "default"},
    "base_url": {"default": "http://127.0.0.1:20130/v1"},
    "prompt": {"default": ""}
  },
  "required_models": [],
  "required_custom_nodes": ["comfyui-openai-compatible"],
  "min_comfyui_version": "0.0.0",
  "requirements": {"accelerator": "any", "xformers": false, "min_vram_gb": 0, "fp16": false},
  "limits": {
    "max_upload_bytes": 0,
    "max_asset_duration": 0,
    "max_video_width": 0,
    "max_video_height": 0,
    "max_sequence_length": 0
  }
}
```

### workflow.json
```json
{
  "1": {
    "class_type": "OpenAICompatibleChat",
    "inputs": {
      "base_url": "http://127.0.0.1:20130/v1",
      "api_key": "",
      "model": "default",
      "prompts": {"text_1": "Hello, world!"}
    }
  },
  "2": {
    "class_type": "SaveText",
    "inputs": {
      "text": ["1", 0],
      "filename_prefix": "ComfyUI",
      "format": "text"
    }
  }
}
```

### Проверка
```python
agent = Agent(store)
manifest = agent.registry.get('text_generate', '1.0.0')
assert manifest is not None
assert manifest.capability == 'text.generate'
```

---

## Порядок реализации

1. **P0-1** (5 мин) — исправить AUDIO_KEYWORDS
2. **P0-2** (10 мин) — добавить auto-refresh в KnowledgeCore
3. **P0-3** (20 мин) — создать text.generate workflow
4. **Тесты** (15 мин) — написать проверки
5. **E2E proof** (30 мин) — запустить полный цикл

---

## Критерии готовности

- [ ] P0-1: "generate audio" → audio.generate
- [ ] P0-2: KnowledgeCore.schemas > 0 после init
- [ ] P0-3: text.generate workflow существует
- [ ] Тесты: все 106 тестов проходят
- [ ] E2E: полный цикл работает с text.generate

---

## Что НЕ делаем

- ❌ Не переписываем Agent Core
- ❌ Не создаём новый Learning Framework
- ❌ Не используем comfyui-mcp
- ❌ Не возвращаемся к Gemma
- ❌ Не трогаем HttpRequestNodes
