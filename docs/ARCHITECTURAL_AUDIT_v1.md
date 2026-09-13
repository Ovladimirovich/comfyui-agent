# Архитектурный Аудит Agent Core v1

**Дата:** 2026-09-06
**Статус:** Learning Loop v1 принят ✅

---

## Текущее состояние

### Компоненты

| Компонент | Статус | Примечания |
|-----------|--------|------------|
| Capability Registry | ✅ 10 capabilities | image/video/audio/text + custom |
| Workflow Registry | ⚠️ 7 workflows | audio_generate требует API ключ |
| Provider/Backend | ✅ Local ComfyUI | Works |
| Knowledge Core | ⚠️ Claims only | Схемы/кандидаты не авто-загружаются |
| Planner | ⚠️ Heuristic | Пропуски в маршрутизации |
| Learning Loop | ✅ Работает | Execution → Knowledge → Persistence |

### Workflows by Capability

```
image.generate:     txt2img, pollinations_image     (2 workflows) ✅
image.edit:         img2img                          (1 workflow)  ✅
image.upscale:      upscale                          (1 workflow)  ✅
video.generate:     video_generate                   (1 workflow)  ⚠️ Требуется модель
video.image_to_video: video_image_to_video           (1 workflow)  ⚠️ Требуется модель
audio.generate:     audio_generate                   (1 workflow)  ❌ Требует API ключ
text.generate:      (NONE)                           (0 workflows) ❌
video.upscale:      (NONE)                           (0 workflows) ❌
image.inpaint:      (NONE)                           (0 workflows) ❌
```

---

## Найденные разрывы

### 1. Planner Keyword Gaps

| Запрос | Ожидаемо | Получено | Причина |
|--------|----------|----------|---------|
| "generate audio" | audio.generate | image.generate | Нет AUDIO_KEYWORDS |
| "chat with AI" | text.generate | image.generate | text генерируется через image.default |
| "write a story" | text.generate | image.generate | Нет TEXT_KEYWORDS |
| "create video from image" | video.image_to_video | video.generate | Нет "from image" сигнала |

**Фикс:** Расширить KEYWORDS в HeuristicPlanner

### 2. KnowledgeCore Auto-Refresh Gap

```python
# Текущее поведение:
kc = KnowledgeCore()  # Схемы = 0, Кандидаты = 0

# Нужно:
kc = KnowledgeCore()
kc.refresh(comfy_client)  # Авто-загрузка при инициализации
```

**Фикс:** Добавит auto-refresh в Agent.__init__

### 3. Workflow Composition Gap

**Текущее состояние:**
- Каждый workflow → один output
- Нет ability соединять output одного workflow с input другого
- Нет multi-step chains beyond M18

**Пример что нельзя:**
```
User: "Generate an image, then upscale it, then add text"
→ Agent может только: generate → upscale (M18 chain)
→ Agent НЕ может: generate → upscale → add_text (3+ шагов)
```

**Фикс:** Расширить ExecutionChain для N-шаговых цепочек

### 4. Multi-Output Nodes Gap

**Ноды с множественными выходами:**
- AgnesVideo: VIDEO, IMAGE, IMAGE, AUDIO
- OpenAICompatibleChat: STRING (text)
- ReActor: IMAGE, FACE_MODEL, IMAGE

**Текущее состояние:** WorkflowEngine поддерживает только один output на workflow

**Фикс:** Расширить OutputSpec для multi-output

### 5. Missing Capabilities Workflows

| Capability | Статус | Причина |
|------------|--------|---------|
| text.generate | ❌ Нет workflow | Нужно создать text-to-text workflow |
| video.upscale | ❌ Нет workflow | Нужно создать upscale workflow для видео |
| image.inpaint | ⚠️ Capability есть | Нет workflow (нужны mask inputs) |

---

## План исправлений (приоритеты)

### P0: Критические (ломают базовый UX)

1. **Planner Keywords** — добавить аудио/текст ключевые слова
2. **KnowledgeCore Auto-Refresh** — автозагрузка схем при старте
3. **text.generate Workflow** — создать простой workflow для LLM chat

### P1: Важные (расширяют возможности)

4. **video.upscale Workflow** — workflow для upscale видео
5. **image.inpaint Workflow** — workflow для inpainting
6. **Multi-Output Support** — расширение Engine для multi-output нод

### P2: Будущее (composition)

7. **N-Step Chains** — расширение ExecutionChain для 3+ шагов
8. **Auto-Discovery** — автоматическое создание candidates из нод
9. **Dynamic Workflow Assembly** — сборка workflow из нод на лету

---

## Оценка сложности

| Фикс | Сложность | Время | Зависимости |
|------|-----------|-------|-------------|
| Planner Keywords | Низкая | 30 мин | None |
| KnowledgeCore Auto-Refresh | Низкая | 1 час | ComfyClient |
| text.generate Workflow | Низкая | 2 часа | OpenAICompatibleChat node |
| video.upscale Workflow | Средняя | 4 часа | Video upscale nodes |
| image.inpaint Workflow | Средняя | 4 часа | Mask nodes |
| Multi-Output Support | Высокая | 1 день | Engine redesign |
| N-Step Chains | Высокая | 2 дня | Chain redesign |
| Auto-Discovery | Средняя | 1 день | CandidateGenerator fix |
| Dynamic Assembly | Очень высокая | 1 неделя | Новый компонент |

---

## Рекомендации

### Немедленно (следующая сессия)

1. **Исправить Planner Keywords** — 30 минут, даёт немедленный UX improvement
2. **Добавить KnowledgeCore Auto-Refresh** — 1 час, закрывает gap в инициализации
3. **Создать text.generate Workflow** — 2 часа, закрывает critical gap

### Краткосрочно (1-2 сессии)

4. **video.upscale + image.inpaint workflows** — 8 часов
5. **Multi-Output Support** — 1 день

### Долгосрочно

6. **N-Step Chains + Auto-Discovery** — 3 дня
7. **Dynamic Workflow Assembly** — отдельный milestone

---

## Что НЕ делать сейчас

- ❌ Не переписывать Agent Core
- ❌ Не создавать новый Learning Framework
- ❌ Не использовать comfyui-mcp
- ❌ Не возвращаться к Gemma
- ❌ Не делать универсальный конструктор workflow'ов

---

## Следующий вопрос для пользователя

**Какой фикс делаем первым?**

Варианты:
1. **Planner Keywords** (30 мин) — быстро, даёт immediate UX improvement
2. **KnowledgeCore Auto-Refresh** (1 час) — закрывает architectural gap
3. **text.generate Workflow** (2 часа) — закрывает critical capability gap
4. **Всё подряд** — последовательная реализация P0 фиксов
