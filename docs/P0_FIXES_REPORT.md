# P0 Fixes — Отчёт об исполнении

**Дата:** 2026-09-07
**Статус:** ✅ ЗАВЕРШЕНО

---

## Результаты

### P0-1: Planner Keywords Bug ✅

**Фикс:** Добавлено "audio" в `AUDIO_KEYWORDS`

```python
# app/planner/heuristic.py:36
AUDIO_KEYWORDS = ("трек", "музыка", "звук", "аудио", "audio", "lo-fi", "beat", "sound")
```

**Проверка:**
```
[OK] generate audio -> audio.generate
[OK] chat with AI -> text.generate
[OK] write a story -> text.generate
[OK] upscale an image -> image.upscale
```

---

### P0-2: KnowledgeCore Auto-Refresh ✅

**Фикс:** Автозагрузка схем при инициализации

```python
# app/knowledge/core.py:103
self.load_from_store()  # Добавлено в __init__
```

**Проверка:**
```
Schemas: 978
Candidates: 159
Claims: 159
```

---

### P0-3: text.generate Workflow ✅

**Фикс:** Создан workflow для text.generate capability

**Файлы:**
- `workflows/text_generate/manifest.json`
- `workflows/text_generate/workflow.json`

**Ноды:** OpenAICompatibleChat → SaveText

**Проверка:**
```
text_generate@1.0.0: text.generate (VALIDATED)
```

---

## E2E Proof

```
[ROUND 1] First execution
  Execution: SUCCESS (121s)
  Validated nodes: PollinationsImageGen=true, SaveImage=true

[ROUND 2] After restart
  Loaded schemas: 978
  Loaded candidates: 159
  Loaded validated nodes: PollinationsImageGen=true, SaveImage=true
  
  Planner routing:
    [OK] generate audio -> audio.generate
    [OK] chat with AI -> text.generate
    [OK] upscale an image -> image.upscale
  
  text.generate workflow: [OK]
```

---

## Изменённые файлы

| Файл | Изменение |
|------|-----------|
| `app/planner/heuristic.py` | + "audio" в AUDIO_KEYWORDS |
| `app/knowledge/core.py` | + load_from_store() в __init__ |
| `workflows/text_generate/manifest.json` | **Новый** |
| `workflows/text_generate/workflow.json` | **Новый** |

---

## Тесты

```
91 passed, 1 skipped
```

---

## Архитектурный вывод

**Learning Loop v1 + P0 fixes = полноценный обучающийся агент:**

```
User Request
    ↓
Planner (с ключевыми словами audio/text)
    ↓
Workflow Selection (с авто-кандидатами)
    ↓
Execution (реальный ComfyUI)
    ↓
SUCCESS → KnowledgeCore.save_state()
    ↓
Persistence (JSON)
    ↓
Restart → Load from Persistence
    ↓
Planner использует validated_nodes
```

**Готово к P1:** video.upscale, image.inpaint, multi-output support.
