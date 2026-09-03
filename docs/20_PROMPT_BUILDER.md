# 20 — Prompt Builder + Dynamic Prompt Suggestions

**Version:** 1.4 (M11 ARCHITECTURAL FREEZE)
**Status:** M11.3-M11.6 FULLY IMPLEMENTED + FROZEN (2026-09-01). Архитектурный слой стабилизирован.
**Source of Truth:** `PROJECT_SPEC.md` (v0.2)

---

## 1. Цель

Создать интеллектуальный модуль **PromptBuilder**, который помогает пользователю создавать точные, полные и пригодные для исполнения промпты без необходимости писать идеальный prompt вручную.

Модуль должен обеспечивать:
- **Prompt Completion** — дополнение частично написанного текста
- **Dynamic Prompt Suggestions** — итеративная генерация вариантов улучшения при каждом нажатии кнопки
- **Context-aware** — учёт capability, active_asset, предыдущих промптов
- **Offline/LLM режимы** — работа без LLM через heuristic/template механизм
- **Deterministic fallback** — предсказуемое поведение при недоступности LLM

---

## 2. Пользовательские сценарии

### Сценарий 1: Dynamic Prompt Suggestions (основной)
```
Пользователь: "кот"
[Нажатие 1 ✨ Подсказка]
→ "realistic orange tabby cat sitting near a window, natural daylight, detailed fur"

[Нажатие 2 ✨ Подсказка]
→ "cinematic portrait of a majestic cat, dramatic lighting, shallow depth of field, highly detailed fur"

[Нажатие 3 ✨ Подсказка]
→ "cozy domestic cat curled up on a soft blanket, warm morning light, photorealistic"

Пользователь выбирает вариант → отправка в Planner → execution
```

### Сценарий 2: Prompt Completion
```
Пользователь начинает: "cyberpunk..."
[Автocomplete]
→ "cyberpunk city at night, neon lights, rain reflections, futuristic architecture"
```

### Сценарий 3: Context-aware suggestions
```
Контекст: active_asset = image_001 (type=image)
Пользователь: "улучши"
[✨ Подсказка]
→ "enhance image quality, add more detail, improve lighting, photorealistic finish"
(учитывает capability=image.edit)
```

### Сценарий 4: Offline режим
```
LLM недоступен → PromptBuilder использует heuristic/template механизм
"кот" → "detailed cat, high quality, professional photography"
```

---

## 3. Архитектурное место модуля

### Анализ вариантов

**Вариант A: UI → PromptBuilder → Planner**
- Плюсы: чистое разделение, UI вызывает PromptBuilder до Planner
- Минусы: добавляет лишний шаг в UI flow, усложняет ConversationAgent.turn

**Вариант B: UI → Planner → PromptBuilder**
- Плюсы: Planner сначала решает capability, затем PromptBuilder улучшает prompt
- Минусы: Planner уже извлекает prompt из request; требует рефакторинга

**Вариант C: ConversationAgent → PromptBuilder → Planner**
- Плюсы: централизованно в conversation flow, может использовать ConversationContext
- Минусы: усложняет ConversationAgent.turn

**Вариант D: Отдельный Prompt Service, используемый UI/Agent/Planner**
- Плюсы: максимальная гибкость, можно вызывать откуда угодно
- Минусы: добавляет новый service layer, может быть over-engineering

**Вариант E: PromptBuilder как utility модуль внутри Planner**
- Плюсы: минимальные изменения, Planner уже обрабатывает prompt
- Минусы: размывает ответственность между Planner и PromptBuilder

### РЕШЕНИЕ: Вариант D (Prompt Service) — для MVP только UI integration

**Обоснование:**
1. **Гибкость:** PromptBuilder может использоваться UI напрямую (для кнопки ✨), в будущем — Agent/ConversationAgent/Planner
2. **Чистая архитектура:** PromptBuilder — отдельный модуль с чётким контрактом, не привязан к конкретному месту вызова
3. **Соответствие существующим паттернам:** аналогично тому, как Planner — отдельный модуль, используемый Agent и ConversationAgent
4. **Минимальное влияние на существующий код:** MVP требует только изменения UI, не Planner/Agent/ConversationContext
5. **MVP-first:** интеграция с Planner/ConversationAgent отложена до будущих этапов

### Архитектурная диаграмма (MVP)

```text
UI
  │
  ├─► POST /api/prompt/suggest {text, context}
  │       │
  │       ▼
  │   PromptBuilder (service)
  │       │
  │       ├─► HeuristicPromptBuilder (offline, MVP)
  │       └─► LLMPromptBuilder (online, future)
  │
  └─► POST /turn {request, params}
          │
          ▼
      ConversationAgent
          │
          ├─► Planner (capability + params)
          │
          └─► Agent → WorkflowEngine → Execution
```

**Примечание:** Интеграция PromptBuilder с Planner/ConversationAgent — future scope (M11.4+), не часть MVP.

---

## 4. Контракты входа/выхода

### PromptContext (вход)

```python
@dataclass
class PromptContext:
    """Декларативный контекст для PromptBuilder.
    
    Содержит ТОЛЬКО строки и идентификаторы — без bytes/paths/FS.
    """
    original_text: str                    # исходный текст пользователя
    mode: Literal["completion", "suggestion"]  # режим работы
    capability: Optional[str] = None      # для context-aware (image.generate, image.edit, ...)
    active_asset_type: Optional[str] = None  # из ConversationContext
    previous_prompt: Optional[str] = None  # для итеративного улучшения
    suggestion_index: int = 0             # индекс варианта (для suggestion)
    style: Optional[str] = None           # желаемый стиль (photorealistic, cinematic, ...)
    parameters: Optional[dict] = None      # параметры генерации (width, height, ...)
```

### PromptResult (выход)

```python
@dataclass
class PromptResult:
    """Результат работы PromptBuilder."""
    enhanced_prompt: str                   # улучшенный промпт
    original_preserved: bool              # сохранено ли исходное намерение
    mode: Literal["completion", "suggestion"]
    variant_index: int                    # индекс варианта
    source: Literal["heuristic", "llm", "fallback"]  # источник
    rationale: Optional[str] = None       # объяснение (для отладки)
```

### PromptBuilder Protocol

```python
@runtime_checkable
class PromptBuilder(Protocol):
    def build(self, context: PromptContext) -> PromptResult: ...
```

---

## 5. Связь с Planner

### Чёткое разделение ответственности

**Planner отвечает за:**
- `user intent → capability/workflow`
- Выбор capability (image.generate, image.edit, video.generate, ...)
- Извлечение параметров из request

**PromptBuilder отвечает за:**
- `user text → quality prompt`
- Улучшение текста промпта (дополнение, расширение, стилизация)
- НЕ выбирает capability
- НЕ решает "image.generate или image.edit?"

### Точка интеграции (FUTURE SCOPE - M11.4+)

Интеграция PromptBuilder с Planner — future scope, не часть MVP. В будущем Planner может опционально использовать PromptBuilder для улучшения prompt:

```python
# В LLMPlanner (future, M11.4+)
def plan(self, request: str, context: PlanContext | None = None) -> PlanResult:
    # ... определение capability ...
    
    # Опционально: улучшить prompt через PromptBuilder
    if self.prompt_builder:
        prompt_ctx = PromptContext(
            original_text=request,
            mode="suggestion",
            capability=capability,
            active_asset_type=context.active_asset_type if context else None,
        )
        prompt_result = self.prompt_builder.build(prompt_ctx)
        request = prompt_result.enhanced_prompt
    
    return PlanResult(capability=capability, params={"prompt": request})
```

**ВАЖНО (MVP):** В MVP PromptBuilder используется только UI напрямую через `/api/prompt/suggest`. Интеграция с Planner/ConversationAgent — future scope (M11.4+).

---

## 6. Связь с ConversationContext (FUTURE SCOPE - M11.4+)

### Данные, которые PromptBuilder получает из ConversationContext

Интеграция с ConversationContext — future scope, не часть MVP. В будущем PromptBuilder может использовать ConversationContext для context-aware улучшения:

```python
# В ConversationAgent.turn (future, M11.4+)
ctx = self.session(session_id)

if ctx.active_asset:
    active = self.store.get(ctx.active_asset)
    prompt_ctx = PromptContext(
        original_text=request,
        mode="suggestion",
        capability=ctx.active_task,
        active_asset_type=active.type if active else None,
        previous_prompt=ctx.parameters.get("prompt"),
    )
```

### Данные, которые PromptBuilder НЕ получает

- **bytes** (никаких бинарных данных)
- **файлы** (никаких file paths или file handles)
- **абсолютные пути** (только относительные или идентификаторы)
- **внутренние объекты ComfyUI** (nodes, workflows, etc.)
- **секреты** (API keys, tokens)

Только декларативный контекст: строки и идентификаторы.

---

## 7. Связь с UI

### Минимальные изменения UI

**Добавить в `app/ui.py`:**

1. **Новый endpoint:**
```python
# POST /api/prompt/suggest
def do_POST(self):
    if parsed.path == "/api/prompt/suggest":
        body = json.loads(raw)
        prompt_ctx = PromptContext(
            original_text=body.get("text"),
            mode="suggestion",
            suggestion_index=body.get("index", 0),
        )
        result = self.prompt_builder.build(prompt_ctx)
        self._send_json({
            "enhanced_prompt": result.enhanced_prompt,
            "variant_index": result.variant_index,
            "source": result.source,
        })
```

2. **Изменения в HTML (_INDEX_HTML):**
```html
<div id="controls">
  <input id="text" placeholder="например: сгенерируй фото кота" autofocus>
  <button id="suggest">✨ Подсказка</button>
  <button id="send">Отправить</button>
</div>
```

3. **JavaScript:**
```javascript
let suggestIndex = 0;
document.getElementById('suggest').addEventListener('click', async () => {
  const text = document.getElementById('text').value.trim();
  if (!text) return;
  const res = await fetch('/api/prompt/suggest', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, index: suggestIndex }),
  });
  const data = await res.json();
  document.getElementById('text').value = data.enhanced_prompt;
  suggestIndex = data.variant_index + 1;
});
```

### UX flow

1. Пользователь вводит текст в поле
2. Нажимает "✨ Подсказка"
3. Система возвращает новый вариант (заменяет содержимое поля)
4. Пользователь может:
   - Принять вариант (нажать "Отправить")
   - Получить следующий вариант (снова нажать "✨ Подсказка")
   - Вернуть исходный текст (отмена или ручное редактирование)
   - Продолжить редактирование (вручную изменить вариант)
5. **НИКОГДА автоматически не уничтожать пользовательский текст**

### Разделение: Prompt Enhancement vs Dynamic Suggestions

**Prompt Enhancement:**
- Улучшение уже введённого текста
- Сохраняет исходное намерение
- Может быть автоматическим (future scope)

**Dynamic Suggestions:**
- Генерация альтернативных вариантов по нажатию кнопки
- Каждое нажатие даёт новый вариант
- Циклический перебор вариантов
- Пользователь явно выбирает вариант

**MVP scope:** только Dynamic Suggestions через кнопку ✨. Prompt Enhancement — future scope.

---

## 8. Offline/LLM режимы

### HeuristicPromptBuilder (офлайн, MVP)

```python
class HeuristicPromptBuilder:
    """Офлайн-улучшитель промптов на основе шаблонов и правил (MVP)."""

    TEMPLATES = {
        "cat": [
            "detailed {subject}, high quality, professional photography",
            "realistic {subject}, natural lighting, sharp focus",
            "cinematic {subject}, dramatic lighting, shallow depth of field",
        ],
        # ...更多 шаблоны
    }

    def build(self, ctx: PromptContext) -> PromptResult:
        # Поиск по ключевым словам
        # Применение шаблонов
        # Детерминированный выбор по suggestion_index
        return PromptResult(...)
```

### LLMPromptBuilder (онлайн, FUTURE SCOPE - M11.5)

```python
class LLMPromptBuilder:
    """Улучшитель промптов на базе LLM (OpenAI-совместимый)."""

    def __init__(self, api_key: str, base_url: str = "..."):
        self.api_key = api_key
        self.base_url = base_url

    def build(self, ctx: PromptContext) -> PromptResult:
        # Формирование system prompt с декларативным контекстом
        # Вызов LLM API
        # Парсинг результата
        return PromptResult(...)
```

### Fallback стратегия (FUTURE SCOPE - M11.5)

**MVP:** только HeuristicPromptBuilder (без LLM, без fallback).

**Future (M11.5):** CompositePromptBuilder с fallback на heuristic при недоступности LLM.

---

## 9. Fallback (FUTURE SCOPE - M11.5)

### Deterministic fallback (future)

- При недоступности LLM → HeuristicPromptBuilder
- При ошибке LLM → HeuristicPromptBuilder
- HeuristicPromptBuilder всегда детерминирован для одинаковых входов
- suggestion_index гарантирует разные варианты

**MVP:** Fallback не требуется (только HeuristicPromptBuilder).

### Защита от изменения исходного намерения (MVP)

```python
# В HeuristicPromptBuilder.build() (MVP)
def build(self, ctx: PromptContext) -> PromptResult:
    enhanced = self._enhance(ctx.original_text, ctx)

    # Проверка: исходное намерение сохранено?
    original_preserved = self._check_intent_preserved(
        ctx.original_text,
        enhanced
    )

    return PromptResult(
        enhanced_prompt=enhanced,
        original_preserved=original_preserved,
        ...
    )
```

---

## 10. Безопасность

### Инварианты безопасности

1. **LLM не имеет доступа к FS**
   - PromptBuilder передает только декларативный контекст (строки)
   - Никаких путей к файлам, байтов, Asset.path

2. **Никаких секретов в промптах**
   - API keys не передаются в LLM
   - Секреты только в .env

3. **Path confinement**
   - PromptBuilder не работает с путями
   - Только идентификаторы (asset_id, session_id)

4. **Deterministic fallback**
   - При недоступности LLM — предсказуемое поведение
   - Нет случайных сбоев

---

## 11. Какие существующие файлы изменятся (MVP)

### Минимальные изменения (MVP)

1. **`app/ui.py`**
   - Добавить endpoint `POST /api/prompt/suggest`
   - Добавить кнопку "✨ Подсказка" в HTML
   - Добавить JavaScript для кнопки

### M11.3 Implementation Plan (Dynamic Suggestions UI)

**Backend changes (app/ui.py):**
- Добавить `HeuristicPromptBuilder` в `ComfyUIServer.__init__`
- Добавить endpoint `POST /api/prompt/suggest` в `do_POST`
  - Request: `{text: str, suggestion_index?: int, mode?: str, style?: str}`
  - Response: `{enhanced_prompt: str, original_preserved: bool, variant_index: int, source: str, rationale?: str}`

**Frontend changes (_INDEX_HTML):**
- Добавить кнопку "✨ Подсказка" рядом с полем ввода
- Добавить элемент `#suggestion` для отображения подсказки
- Добавить кнопку "Принять" для принятия подсказки (опционально)

**Frontend JavaScript:**
- Переменная `suggestion_index = 0` (per session)
- Функция `suggest()`: POST `/api/prompt/suggest` → отображает в `#suggestion`
- Кнопка ✨: вызывает `suggest()`, увеличивает `suggestion_index`
- Кнопка "Принять": копирует suggestion в поле ввода, сбрасывает `suggestion_index`
- **Критически:** suggestion НЕ заменяет поле ввода автоматически (AD-32)

**UX flow:**
1. Пользователь вводит: "кот на крыше ночью"
2. Нажимает ✨ → suggestion появляется в отдельном элементе
3. Пользователь может:
   - Нажать "Принять" → suggestion копируется в поле ввода
   - Нажать ✨ ещё раз → новый вариант (suggestion_index++)
   - Продолжить редактировать поле ввода вручную
4. Исходный текст НИКОГДА не уничтожается автоматически

### НЕ изменяются (MVP)

- **`app/conversation.py`** — интеграция future scope (M11.4+)
- **`app/planner.py`** — интеграция future scope (M11.4+)
- **`app/agent.py`** — execution core не трогаем
- **`app/engine/`** — WorkflowEngine, Job, Verifier не трогаем
- **`app/registry/`** — WorkflowRegistry не трогаем
- **`app/provider/`** — Provider не трогаем
- **`app/assets/`** — AssetStore не трогаем
- **`workflows/`** — manifest.json не трогаем

---

## 12. Какие новые файлы появятся (MVP)

### Основные файлы (MVP)

1. **`app/prompt/__init__.py`**
   - Экспорт PromptBuilder, PromptContext, PromptResult

2. **`app/prompt/builder.py`**
   - PromptBuilder protocol
   - PromptContext, PromptResult dataclasses
   - CompositePromptBuilder (future scope, M11.5)

3. **`app/prompt/heuristic.py`**
   - HeuristicPromptBuilder
   - Шаблоны и правила
   - Детерминированная логика

4. **`app/prompt/templates.py`**
   - База шаблонов для heuristic mode
   - Категории по предметам (cat, portrait, landscape, ...)

### Future scope (M11.5+)

5. **`app/prompt/llm.py`**
   - LLMPromptBuilder
   - OpenAI-совместимый клиент
   - System prompt с контекстом

### Тесты (MVP)

6. **`tests/test_prompt_builder.py`**
   - Тесты HeuristicPromptBuilder
   - Тесты PromptContext/PromptResult
   - Тесты original_preserved

7. **`tests/test_prompt_ui.py`**
   - Тесты endpoint `/api/prompt/suggest`
   - Интеграционные тесты с UI

### Future scope tests (M11.5+)

8. **`tests/test_prompt_llm.py`**
   - Тесты LLMPromptBuilder (mock)
   - Тесты CompositePromptBuilder fallback

---

## 13. Какие тесты нужны

### Unit тесты

1. **HeuristicPromptBuilder**
   - Тест шаблонов по ключевым словам
   - Тест детерминированности (одинаковый вход → одинаковый выход)
   - Тест suggestion_index (разные индексы → разные варианты)
   - Тест context-aware (capability влияет на результат)

2. **LLMPromptBuilder**
   - Тест с mock LLM API
   - Тест обработки ошибок (timeout, 500, etc.)
   - Тест парсинга ответа

3. **CompositePromptBuilder**
   - Тест fallback (LLM ошибка → heuristic)
   - Тест без LLM (только heuristic)

### Интеграционные тесты

4. **UI endpoint**
   - Тест `POST /api/prompt/suggest`
   - Тест с валидным/невалидным JSON
   - Тест с пустым текстом

5. **ConversationAgent интеграция**
   - Тест опционального использования PromptBuilder в turn()
   - Тест сохранения original_preserved

### E2E тесты

6. **UI flow**
   - Тест: пользователь вводит "кот" → нажимает ✨ → получает вариант → отправляет
   - Тест: несколько нажатий ✨ → разные варианты

---

## 14. Какие архитектурные инварианты затрагиваются

### Соблюдаемые инварианты

- **AD-03 Media-agnostic core** — PromptBuilder работает только с текстом, не ветвится по media-типу
- **AD-04 Manifest-маппинг** — PromptBuilder не трогает manifest/workflow
- **AD-08 LLM через OpenAI-совместимый endpoint** — LLMPromptBuilder использует тот же паттерн
- **AD-14 No-LLM-first** — HeuristicPromptBuilder работает без LLM

### Новые инварианты (AD-30)

**AD-30: PromptBuilder не имеет доступа к FS/ComfyUI**
- PromptBuilder получает только декларативный контекст (строки, идентификаторы)
- Никаких bytes, файлов, путей, внутренних объектов ComfyUI

**AD-31: PromptBuilder не выбирает capability**
- PromptBuilder улучшает prompt, но не решает "image.generate или image.edit?"
- Это ответственность Planner

**AD-32: PromptBuilder сохраняет исходное намерение**
- Улучшенный prompt должен содержать исходное намерение пользователя
- original_preserved flag проверяется

---

## 15. Что НЕ должно измениться

### Execution core

- **WorkflowEngine** — не трогаем
- **Job** — не трогаем
- **Verifier** — не трогаем
- **Provider** — не трогаем
- **AssetStore** — не трогаем

### Planning core

- **Planner protocol** — не трогаем (опциональная интеграция)
- **PlanContext** — не трогаем (используем как есть)
- **HeuristicPlanner** — не трогаем
- **LLMPlanner** — не трогаем (опциональная интеграция)

### Conversation core

- **ConversationContext** — не трогаем (используем как есть)
- **ConversationAgent** — минимальные изменения (опциональная интеграция)

### Registry

- **WorkflowRegistry** — не трогаем
- **Capability Registry** — не трогаем
- **Model Registry** — не трогаем

### Workflows

- **manifest.json** — не трогаем
- **workflow.json** — не трогаем

---

## 16. Definition of Done

Модуль считается готовым, когда:

- [ ] Реализован HeuristicPromptBuilder с шаблонами
- [ ] Реализован LLMPromptBuilder с OpenAI-совместимым API
- [ ] Реализован CompositePromptBuilder с fallback
- [ ] Добавлен endpoint `POST /api/prompt/suggest` в UI
- [ ] Добавлена кнопка "✨ Подсказка" в UI
- [ ] Написаны unit тесты для всех билдеров
- [ ] Написаны интеграционные тесты для UI endpoint
- [ ] Написан E2E тест для UI flow
- [ ] PromptBuilder не имеет доступа к FS/ComfyUI (проверено)
- [ ] PromptBuilder не выбирает capability (проверено)
- [ ] original_preserved работает корректно
- [ ] Fallback на heuristic работает при недоступности LLM
- [ ] suggestion_index генерирует разные варианты
- [ ] Context-aware работает (учитывает capability, active_asset_type)
- [ ] Документация обновлена (PROJECT_SPEC, ROADMAP, этот документ)
- [ ] Реальный E2E тест: пользователь → ✨ → вариант → execution

---

## 17. Риски и альтернативы

### Риски

1. **LLM недоступен**
   - Митигация: deterministic fallback на HeuristicPromptBuilder
   - Статус: низкий риск (fallback реализован)

2. **PromptBuilder меняет исходное намерение**
   - Митигация: original_preserved check + эвристики
   - Статус: средний риск (требует тестирования)

3. **Шаблоны heuristic mode недостаточно качественные**
   - Митигация: расширяемая база шаблонов
   - Статус: средний риск (можно улучшать итеративно)

4. **Интеграция с UI усложняет код**
   - Митигация: минимальные изменения, отдельный endpoint
   - Статус: низкий риск (изолированный endpoint)

### Альтернативы

**Альтернатива 1: PromptBuilder внутри Planner**
- Плюсы: меньше файлов
- Минусы: размывает ответственность Planner
- Решение: не выбрано (вариант D лучше)

**Альтернатива 2: Только LLM, без heuristic**
- Плюсы: проще код
- Минусы: не работает офлайн
- Решение: не выбрано (нарушает offline requirement)

**Альтернатива 3: Только heuristic, без LLM**
- Плюсы: работает офлайн
- Минусы: ограниченное качество
- Решение: не выбрано (LLM нужен для качества)

---

## 18. Порядок реализации по этапам

### Этап 1: Core PromptBuilder (без UI)
- [ ] Создать `app/prompt/` модуль
- [ ] Реализовать PromptContext, PromptResult
- [ ] Реализовать PromptBuilder protocol
- [ ] Реализовать HeuristicPromptBuilder с базовыми шаблонами
- [ ] Реализовать LLMPromptBuilder (mock для тестов)
- [ ] Реализовать CompositePromptBuilder с fallback
- [ ] Написать unit тесты

### Этап 2: UI Integration
- [ ] Добавить endpoint `POST /api/prompt/suggest` в `app/ui.py`
- [ ] Добавить кнопку "✨ Подсказка" в HTML
- [ ] Добавить JavaScript для кнопки
- [ ] Написать интеграционные тесты для endpoint

### Этап 3: Context-aware enhancement
- [ ] Добавить учет capability в PromptBuilder
- [ ] Добавить учет active_asset_type
- [ ] Добавить учет previous_prompt
- [ ] Написать тесты context-aware логики

### Этап 4: LLM Integration (опционально)
- [ ] Реализовать реальный LLMPromptBuilder с OpenAI API
- [ ] Добавить конфигурацию (env vars)
- [ ] Написать тесты с реальным API (или mock)

### Этап 5: Planner Integration (опционально)
- [ ] Добавить опциональное использование PromptBuilder в LLMPlanner
- [ ] Написать тесты интеграции

### Этап 6: Documentation & Validation
- [ ] Обновить PROJECT_SPEC.md (добавить AD-30/31/32)
- [ ] Обновить ROADMAP.md (добавить milestone M11)
- [ ] Провести E2E тест
- [ ] Code review

---

## 19. Связь с существующей документацией

### Документы для обновления

1. **`docs/PROJECT_SPEC.md`**
   - Добавить AD-30: PromptBuilder не имеет доступа к FS/ComfyUI
   - Добавить AD-31: PromptBuilder не выбирает capability
   - Добавить AD-32: PromptBuilder сохраняет исходное намерение
   - Обновить §6 (System Architecture) — добавить PromptBuilder в диаграмму
   - Обновить §21 (API/UI Boundaries) — добавить `/api/prompt/suggest`

2. **`docs/17_ROADMAP.md`**
   - Добавить M11: Prompt Builder + Dynamic Prompt Suggestions
   - Обновить связи с PROJECT_SPEC

3. **Этот документ (`docs/20_PROMPT_BUILDER.md`)**
   - Создать как спецификацию нового модуля
   - Source of truth для реализации

### Документы, которые НЕ обновляются

- `docs/00..18_*.md` — производные документы обновляются после PROJECT_SPEC
- `engineering/*` — обновляются после спецификации
- `tasks/*` — обновляются после спецификации

---

## 20. Заключение

Prompt Builder + Dynamic Prompt Suggestions — отдельный интеллектуальный модуль, который улучшает пользовательский путь:

```
текст → хороший prompt → planner → workflow → результат
```

не разрушая существующую архитектуру.

**Ключевые решения:**
1. **Архитектурное место:** отдельный Prompt Service (вариант D)
2. **Разделение ответственности:** Planner → capability, PromptBuilder → prompt quality
3. **Контракт:** декларативный PromptContext (без bytes/paths/FS)
4. **Режимы:** heuristic (offline) + LLM (online) + deterministic fallback
5. **UI:** минимальные изменения, кнопка ✨, endpoint `/api/prompt/suggest`
6. **Безопасность:** AD-30/31/32, LLM без FS доступа

**Следующий шаг:** утверждение плана → реализация по этапам.
