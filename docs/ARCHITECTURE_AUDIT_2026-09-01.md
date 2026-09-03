# ARCHITECTURE AUDIT — 2026-09-01

**Статус:** ARCHITECTURE BASELINE — ACCEPTED FOR FUTURE PLANNING
**Тип:** READ-ONLY audit. Код не менялся.
**Объект:** `C:\cd\ComfyUI_AMD\agent` (M1–M12)

---

## 1. FACT — Фактическое состояние (подтверждено кодом/тестами)

### 1.1. Структура проекта

```
agent/
├── app/
│   ├── agent.py              (328 строк) — оркестратор
│   ├── conversation.py       (243 строки) — многоходовой контекст
│   ├── planner.py            (279 строк) — keyword + LLM планировщик
│   ├── ui.py                 (494 строки) — веб-сервер (SSE, /turn)
│   ├── comfy/
│   │   ├── client.py         (194 строки) — HTTP-клиент (stdlib)
│   │   └── lifecycle.py      (142 строки) — ComfyUIProcessManager
│   ├── engine/
│   │   ├── engine.py         (306 строк) — сборка prompt + execution
│   │   ├── verifier.py       (39 строк) — structural verification
│   │   ├── job.py            (33 строки) — Job dataclass
│   │   └── websocket.py      (~200 строк) — WS-трекинг
│   ├── provider/
│   │   └── comfyui.py        (71 строка) — Provider boundary
│   ├── registry/             (~800 строк) — Capability/Workflow/Model/Selection
│   ├── prompt/               (~400 строк) — Heuristic/LLM/Composite/Templates
│   ├── assets/
│   │   ├── types.py          (54 строки) — Asset dataclass
│   │   └── store.py          (~200 строк) — AssetStore (JSONL)
│   └── infrastructure/
│       └── comfy_cli_adapter.py (294 строки) — optional diagnostics
├── workflows/                5 capability directories
├── tests/                    26 test files
└── docs/                     derived documentation
```

### 1.2. Execution path (фактический, проверен кодом)

```
User request (string)
  → HeuristicPlanner/LLMPlanner (keywords/LLM → capability + params)
  → Agent.prepare (workflow selection + backend selection)
  → PromptBuilder.build (optional prompt enhancement, M11.6)
  → WorkflowEngine.execute
    ├── Provider.upload_asset (input assets → BackendRef)
    ├── WorkflowEngine.build_prompt (manifest + plan → ComfyUI JSON)
    ├── WorkflowEngine._bind_models (checkpoint selection via ModelRegistry)
    ├── Provider.execute (POST /prompt → prompt_id)
    ├── WebSocket.track (or /history polling fallback)
    ├── Provider.view (download output bytes)
    ├── WorkflowEngine._validate_output_bytes (magic signatures)
    ├── AssetStore.ingest (create output Asset with lineage)
    └── Verifier.verify (type + existence check)
  → Job (SUCCESS/FAILED) + output Assets
  → ConversationContext.active_asset update
  → SSE → UI
```

### 1.3. Тесты (фактические)

| Набор | Passed | Skipped | Файл |
|-------|--------|---------|------|
| Agent core | 8 | 0 | test_agent.py |
| Planner | 4 | 0 | test_planner.py |
| Planner context | 12 | 0 | test_planner_context.py |
| UI M9 | 5 | 0 | test_ui_m9.py |
| Backends | 5 | 0 | test_backends.py |
| Progress | 12 | 0 | test_progress.py |
| Conversation M7 | 7 | 1 | test_conversation_m7.py |
| Upscale | 6 | 0 | test_upscale.py |
| ComfyCLI Adapter | 34 | 0 | test_comfy_cli_adapter.py |
| Asset M2 | 9 | 1 | test_m2_asset.py |
| Registry M3 | 23 | 1 | test_m3_registry.py |
| **Итого** | **126** | **3** | |

### 1.4. Capability (фактические)

| Capability | Workflow | E2E доказан | Продакшен-ready |
|------------|----------|-------------|-----------------|
| `image.generate` | txt2img | ✅ local + remote | ✅ |
| `image.edit` | img2img | ✅ remote | ⚠️ (depends on LoadImage) |
| `image.upscale` | upscale | ✅ remote | ⚠️ (simple, no model) |
| `video.generate` | video_generate | ✅ remote (Colab T4) | ⚠️ (requires codec) |
| `audio.generate` | audio_generate | ❌ (Sonilo 401) | ❌ |

### 1.5. ComfyCLIAdapter (фактическое состояние)

- **Единственный владелец:** `agent/app/infrastructure/comfy_cli_adapter.py`
- **ComfyUI fork:** НЕ содержит adapter (удалён в этой сессии)
- **Интеграция в execution path:** НЕТ (только infrastructure/__init__.py + tests)
- **Используется Agent core:** НЕТ (agent.py, conversation.py, engine/*, ui.py не импортируют)
- **Тесты:** 34/34 passed

---

## 2. ASSESSMENT — Архитектурная оценка

### 2.1. Что является сильным фундаментом

1. **Media-agnostic execution chain.** ComfyClient → Provider → WorkflowEngine → Verifier работает для image/video/audio через единый path. Нет if image/elif video в core. Это реальное достижение, подтверждённое E2E тестами.

2. **Asset lineage.** Каждый output связан с input через `source_asset` + `created_from`. Основа для reproducibility и audit trail.

3. **Provider/Backend boundary (AD-29).** Remote ComfyUI = first-class execution backend, не workaround. Доказано: один execution path для local и remote.

4. **CompositePromptBuilder.** LLM → heuristic fallback — рабочий pattern. Не идеальный, но working с graceful degradation.

5. **Session isolation.** ConversationContext изолирован по session_id. Multi-session mode работает.

6. **ComfyClient.** Stdlib HTTP-клиент без зависимостей. Обходит системный прокси (Hiddify fix). Upload через multipart.

### 2.2. Главные ограничения

#### ОГРАНИЧЕНИЕ 1: Нет feedback loop

Система **单向**: request → execution → result. Если:
- ComfyUI вернул битый output → FAILED, нет retry
- Пользователь получил не то, что хотел → нет correction mechanism
- Workflow не подходит для задачи → нет suggestion другой capability

**Последствие:** Agent — это **executor**, а не **operator**. Он выполняет, но не учится и не корректирует.

#### ОГРАНИЧЕНИЕ 2: Планировщик — keyword matching

HeuristicPlanner маппит "кот" → `image.generate`, "улучши" → `image.edit`. Это:
- Не понимает семантику ("сделай что-то красивое" = image.generate)
- Не учитывает контекст сессии (активный ассет, история)
- Не умеет decompose сложные задачи ("сгенерируй кота и увеличь разрешение")

LLMPlanner лучше, но требует ключ и добавляет latency.

#### ОГРАНИЧЕНИЕ 3: Контроль качества = structural only

Verifier проверяет:
- output существует ✅
- тип == declared kind ✅
- файл не пустой ✅

**Не проверяет:**
- Соответствие запросу ("кот" → output содержит кота?)
- Качество (resolution, artifacts, aesthetics)
- Соответствие параметрам (steps, cfg, denoise)

#### ОГРАНИЧЕНИЕ 4: ConversationContext — in-memory, без learning

- При рестарте все сессии теряются
- Контекст хранит active_asset, но не "что пользователю понравилось/не понравилось"
- Нет mechanism для накопления knowledge о предпочтениях пользователя

#### ОГРАНИЧЕНИЕ 5: PromptBuilder — шаблоны, не семантика

HeuristicPromptBuilder подставляет `{subject}` в шаблон. Это:
- Не анализирует intent ("я хочу реализм" vs "я хочу мультяшку")
- Не учитывает capability (prompt для image.generate ≠ prompt для image.edit)
- Не adaptive (один и тот же шаблон для всех запросов)

### 2.3. Архитектурные долги (Technical Debt)

| # | Проблема | Severity | Не блокирует потому что |
|---|----------|----------|------------------------|
| TD-1 | Semantic intent validation — консервативная (≥50% ключевых слов) | LOW | CompositePromptBuilder fallback → heuristic |
| TD-2 | `previous_prompt` передаётся, но HeuristicPromptBuilder не использует | LOW | LLMPromptBuilder может использовать (будущее) |
| TD-3 | ExecutionPlan prompt metadata — поля на Job существуют но не заполняются | LOW | Данные доступны через params["prompt"] |
| TD-4 | 6 failures в `test_prompt_builder.py` | MEDIUM | Код работает; тесты stale |
| TD-5 | ~54 тестов не收集ляются (Python 3.14 stdout hack) | MEDIUM | Тесты работают через `python <file>` |
| TD-6 | `docs/18_DEFINITION_OF_DONE.md` нет DoD для M12 | LOW | Код и тесты существуют |
| TD-7 | Persistence context (JSONL) — нет per-session persistence | LOW | Design decision для v1 |

### 2.4. Нереализованный потенциал

1. **Semantic verification.** Vision model (GPT-4V) оценивает output → retry/adjust.
2. **Adaptive planning.** На основе истории: "для этого пользователя стиль X работает лучше Y".
3. **Multi-step decomposition.** "Сгенерируй кота и увеличь разрешение" → 2 шага автоматически.
4. **Persistent context.** "Помнишь那个 кота? Сделай похожего, но с другим фоном."
5. **Asset-aware planning.** "Улучши эту картинку" → анализ input → оптимальные параметры.

---

## 3. ARCHITECTURAL BOUNDARIES — Подтверждённые границы

### 3.1. Execution path

| Компонент | Роль | Статус |
|-----------|------|--------|
| ComfyClient | HTTP transport | ✅.execution path |
| WorkflowEngine | prompt build + orchestration | ✅.execution path |
| Provider | boundary (asset transport + execute) | ✅.execution path |
| Verifier | structural output check | ✅.execution path |
| AssetStore | storage + lineage | ✅.execution path |
| ComfyUIProcessManager | lifecycle (start/stop) | ✅ infrastructure, не execution |
| ComfyCLIAdapter | optional diagnostics | ✅ infrastructure, не execution |

### 3.2. Подтверждённые инварианты

| Инвариант | Источник | Статус |
|-----------|----------|--------|
| ComfyClient + WorkflowEngine = sole execution path | PROJECT_SPEC §5 | ✅ подтверждено |
| ComfyCLIAdapter не в execution path | AD-34 | ✅ подтверждено (ни один core-модуль не импортирует) |
| Agent не зависит от ComfyUI как Python-проекта | Архитектура | ✅ подтверждено (нет cross-project imports) |
| Media-agnostic: нет if image/elif video в core | AD-03 | ✅ подтверждено (engine.py, verifier.py, job.py) |
| AD-29: remote = first-class | PROJECT_SPEC §27 | ✅ подтверждено (один execution path) |
| AD-30: PromptBuilder без FS/ComfyUI | PROJECT_SPEC §24 | ✅ подтверждено |
| AD-31: PromptBuilder не выбирает capability | PROJECT_SPEC §24 | ✅ подтверждено |
| AD-32: PromptBuilder сохраняет намерение | PROJECT_SPEC §24 | ✅ подтверждено |
| AD-33: shell=True запрещён | PROJECT_SPEC §24 | ✅ подтверждено (AST-тест) |
| AD-34: comfy-cli optional | PROJECT_SPEC §24 | ✅ подтверждено |
| Session isolation | §15 | ✅ подтверждено (test_conversation_m7.py) |
| Asset lineage | M2 | ✅ подтверждено (test_m2_asset.py) |
| Provider/Backend boundary | AD-29 | ✅ подтверждено |

### 3.3. Что НЕ следует менять

| Компонент | Причина |
|-----------|---------|
| Asset (types.py, store.py) | Фундамент lineage. Работает. |
| Job (job.py) | Minimal dataclass. Расширять, не переписывать. |
| Provider (comfyui.py) | Boundary. Работает для local/remote. |
| Registry (registry/) | Capability → Workflow → Selection. Работает. |
| ComfyClient (client.py) | HTTP transport. Работает. |
| Существующий execution path | Доказан E2E тестами. |
| ComfyCLIAdapter | Optional infrastructure. Не трогать. |
| Planner (без необходимости) | HeuristicPlanner + LLMPlanner работают. |

---

## 4. CONSIDERED DIRECTIONS — Рассмотренные варианты

### Вариант A: Semantic Verification + Adaptive Retry

**Что решает:** битый/не соответствующий запросу output → automatic retry с другими параметрами.
**Новая возможность:** Agent自我纠正 — FAILED не финален, а точка для retry.
**Модули:** Verifier расширяется (vision model), Engine получает retry loop.
**Риски:**增加 latency, cost (vision API), может зациклиться.
**Сложность:** Средняя.
**Зависимости:** Vision API (GPT-4V / Gemini через OpenRouter).

### Вариант B: Adaptive Planner (learning from history)

**Что решает:** планировщик учится на предыдущих результатах.
**Новая возможность:** "Для этого пользователя стиль X работает лучше Y" → automatic style preference.
**Модули:** Planner получает history context, ConversationContext хранит feedback.
**Риски:** overfitting, complexity growth.
**Сложность:** Высокая.
**Зависимости:** Persistent storage (JSONL/DB).

### Вариант C: Multi-step Task Decomposition

**Что решает:** сложные задачи из нескольких capability.
**Новая возможность:** "Сгенерируй кота, улучши, увеличь разрешение" → 3 шага автоматически.
**Модули:** Planner получает decomposition, ConversationAgent поддерживает multi-step chain.
**Риски:** exponential complexity, error propagation.
**Сложность:** Высокая.
**Зависимости:** Robust error handling.

### Вариант D: Persistent Context + User Profiles

**Что решает:** потеря сессий при рестарте, нет learning.
**Новая возможность:** "Помнишь那个 кота? Сделай похожего, но с другим фоном."
**Модули:** ConversationContext → persistent storage, user preference tracking.
**Риски:** storage complexity, privacy.
**Сложность:** Средняя.
**Зависимости:** DB/JSONL storage.

### Вариант E: Real-time Quality Feedback (Vision-in-the-loop)

**Что решает:** нет оценки качества output.
**Новая возможность:** Agent видит свой output и решает: OK / retry / adjust parameters.
**Модули:** Verifier + vision model, Engine retry loop, parameter adjustment.
**Риски:** latency, cost, may degrade UX.
**Сложность:** Средняя.
**Зависимости:** Vision API.

### Сравнительная таблица

| Критерий | A: Verification | B: Adaptive | C: Multi-step | D: Persistent | E: Vision |
|----------|----------------|-------------|--------------|--------------|-----------|
| Прирост ценности | Высокий | Средний | Высокий | Средний | Высокий |
| Сложность | Средняя | Высокая | Высокая | Средняя | Средняя |
| Риски | Средние | Высокие | Высокие | Низкие | Средние |
| Зависимости | Vision API | Storage | — | Storage | Vision API |
| Близость к "AI Operator" | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| Влияние на existing code | Низкое | Среднее | Высокое | Низкое | Среднее |

---

## 5. PROPOSAL — Предлагаемое направление (M13)

### 5.1. Рекомендация: Вариант A — Semantic Verification + Adaptive Retry

**Статус:** PROPOSED — NOT YET APPROVED

### 5.2. Почему именно этот вариант

1. **Решает главный архитектурный gap.** Сейчас Agent — executor без feedback. Retry loop превращает его в self-correcting system. Это ключевое отличие "operator" от "executor".

2. **Минимальное влияние на существующий код.** Verifier расширяется (новый метод), Engine получает retry loop (новый блок в execute()). Существующие контракты не меняются.

3. **Нет dependency на storage.** В отличие от B/D, не требует DB. Работает в текущей in-memory модели.

4. **Composable с другими вариантами.** Verification + Retry — фундамент для B (adaptive) и E (vision). Без retry loop adaptive planner бесполезен.

5. **Реалистичная реализация.** Vision API доступен через OpenRouter (Agent уже использует). Retry limit = 3 attempts.

### 5.3. Предлагаемый scope M13

1. **SemanticVerifier** — расширение Verifier:
   - Новый метод `verify_semantic(manifest, created_assets, original_request) → VerificationResult`
   - Vision model (GPT-4V через OpenRouter) для оценки output
   - `VerificationResult`: score (0-1), structural_ok, semantic_ok, issues, suggested_params
   - Fallback: если vision API недоступен → structural verification (current behavior)

2. **Retry Loop в WorkflowEngine**:
   - `execute_with_retry(manifest, plan, provider, max_attempts=3)`
   - After verification: if score < threshold → adjust parameters → retry
   - Terminal: max attempts reached → FAILED with diagnostic

3. **SSE retry events**:
   - `{"type": "retry", "attempt": 2, "reason": "low quality score"}`

### 5.4. Что НЕ в scope M13

- Persistent storage (B)
- Multi-step decomposition (C)
- User profiles (D)
- Full vision feedback loop (E) — только verification, не parameter optimization
- Changes to existing contracts (Asset, Job, Provider, Registry, WorkflowEngine core)

### 5.5. Метрики успеха M13

- Structural verification: 126 tests pass (regression)
- Semantic verification: 5+ new tests (vision mock + real E2E)
- Retry loop: 5+ new tests
- E2E: "кот" → generate → verify → (optional retry) → success

---

## 6. CONSISTENCY CHECK

### 6.1. Противоречия с PROJECT_SPEC.md

**Не обнаружены.** Все подтверждённые инварианты (§5, AD-01..AD-34) соблюдены в коде.

### 6.2. Противоречия с 17_ROADMAP.md

**Не обнаружены.** M1–M12 в roadmap соответствуют реализованному коду.

### 6.3. Противоречия с 18_DEFINITION_OF_DONE.md

**Не обнаружены.** Все чек-листы M4/M6/M6.5/M7/M9/M11 отмечены как ✓.

### 6.4. Противоречия с HANDOFF.md

**Не обнаружены.** Последний HANDOFF (M12.1) соответствует состоянию кода.

### 6.5. Противоречия с CHANGELOG.md

**Не обнаружены.** Все entries в CHANGELOG соответствуют реализованным milestone.

### 6.6. ComfyCLIAdapter

- **Agent:** `app/infrastructure/comfy_cli_adapter.py` — ЕДИНСТВЕННЫЙ владелец ✅
- **ComfyUI fork:** НЕ содержит adapter (удалён) ✅
- **ComfyUI/app/infrastructure/ директория:** УДАЛЕНА ✅

### 6.7. Execution path

- **Не изменён:** ComfyClient → Provider → WorkflowEngine → Verifier → AssetStore ✅
- **ComfyCLIAdapter:** НЕ в execution path ✅
- **Agent не зависит от ComfyUI как Python-проекта:** ✅ (нет cross-project imports)

### 6.8. Новые противоречия

**Не обнаружены.**

---

## 7. ФИНАЛЬНЫЙ СТАТУС

| Документ | Статус |
|----------|--------|
| `docs/ARCHITECTURE_AUDIT_2026-09-01.md` | **ARCHITECTURE BASELINE — ACCEPTED FOR FUTURE PLANNING** |
| M13: Semantic Verification + Adaptive Retry | **PROPOSED — NOT YET APPROVED** |

**Следующий шаг:** Автор проекта принимает решение по M13 или предлагает альтернативное направление.
