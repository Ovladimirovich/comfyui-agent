# ARCHITECTURE DECISION PROPOSAL

**Дата:** 2026-09-06
**Основа:** ARCHITECTURE_ECOSYSTEM_DISCOVERY.md v2
**Цель:** Определить неизменяемое ядро Agent и границу внешней capability ecosystem.
**Статус:** PROPOSAL (архитектурный проект, не реализация).

---

## 1. Executive Summary

**Ключевой вопрос:** Что является неизменяемым ядром Agent, а что является подключаемой внешней ecosystem?

**Ответ:** Agent Core — это **оркестратор с памятью**, который понимает задачи, выбирает capabilities, вызывает execution, проверяет результат и запоминает опыт. Внешняя ecosystem — это **всё, что выполняет работу**: ComfyUI workflows, cloud APIs, local runtimes, specialist operators.

**Рекомендация:** Гибридная архитектура: Agent Core (код-оркестрация) + Access Layer (адаптеры к ecosystem) + Specialist Operators (опционально, как внешние агенты).

---

## 2. Current Architecture

### 2.1 Существующий Agent (v1, M1-M24)

```text
User
  ↓
ConversationAgent (M7)
  ↓
TaskDecomposer (M18) → [SubTask]
  ↓
AdaptivePlanner (M16) → HeuristicPlanner / LLMPlanner → PlanResult
  ↓
WorkflowRegistry (M3) → SelectedCandidate
  ↓
WorkflowEngine (M4) → ComfyUIProvider → ComfyClient → ComfyUI
  ↓
Verifier / SemanticVerifier (M14)
  ↓
AssetStore (M2) + ExperienceStore + ExecutionHistory
  ↓
User
```

### 2.2 Проблемы текущей архитектуры

| Проблема | Описание |
|----------|----------|
| Tight coupling к ComfyUI | WorkflowEngine строит ComfyUI-specific prompt |
| Нет Access Layer | Agent напрямую зависит от ComfyClient |
| LLMPlanner → fallback_proxy | Не интегрирован с рабочим llama.cpp |
| KnowledgeCore дублирует ModelRegistry | Два компонента делают discovery |
| Нет cross-provider routing | BackendCatalog знает о backends, но не выбирает по capability |
| Нет specialist operators | Нет LLM, который управляет ComfyUI через MCP tools |

---

## 3. Proposed Agent Core Boundary

### 3.1 Mapping: 19 компонентов → архитектурный слой

| # | Компонент | Слой | Почему |
|---|-----------|------|--------|
| 1 | **ConversationAgent** | **AGENT CORE** | Оркестрация: session, turn, retry, chain. Незаменимый центральный координатор. |
| 2 | **LLMPlanner** | **AGENT CORE (adapter)** | Планирование через LLM. Protocol `Planner` позволяет заменить backend. |
| 3 | **AdaptivePlanner** | **AGENT CORE** | History-aware parameter optimization. Декоратор поверх fallback planner. |
| 4 | **TaskDecomposer** | **AGENT CORE** | Multi-intent splitting. Чистая логика, без внешних зависимостей. |
| 5 | **HeuristicPlanner** | **AGENT CORE** | Offline fallback. Всегда доступен, детерминирован. |
| 6 | **CapabilityRegistry** | **AGENT CORE (domain model)** | Определение capability. Чистая доменная модель. |
| 7 | **WorkflowRegistry** | **AGENT CORE** | Discovery + selection workflow. Определяет "что доступно". |
| 8 | **WorkflowEngine** | **AGENT CORE (execution)** | Prompt assembly + execution + verification. НО: строит ComfyUI-specific prompt → должен стать generic. |
| 9 | **ComfyUIProvider** | **ADAPTER (backend boundary)** | Тонкая обёртка над ComfyUI HTTP API. Infrastructure, не core. |
| 10 | **BackendCatalog** | **AGENT CORE (routing)** | Multi-backend routing. Определяет "где выполнять". |
| 11 | **ModelRegistry** | **AGENT CORE (catalog)** | Per-backend model catalog. Определяет "какой моделью". |
| 12 | **KnowledgeCore** | **AGENT CORE (knowledge)** | Runtime discovery + claims. Определяет "что возможно". |
| 13 | **SemanticVerifier** | **AGENT CORE (verification)** | Vision-based output check. Protocol-based, заменяемый. |
| 14 | **ExperienceStore** | **AGENT CORE (persistence)** | Execution history (JSONL). Память для learning. |
| 15 | **AssetStore** | **INFRASTRUCTURE** | Asset management + lineage. Cross-cutting concern. |
| 16 | **MCP Server** | **DEPRECATED** | Используется только внешними AI. Заменён ComfyClient. |
| 17 | **ComfyClient** | **ADAPTER (transport)** | HTTP/WS transport к ComfyUI. Infrastructure. |
| 18 | **Verifier** | **AGENT CORE (verification)** | Basic sequence verification. Core. |
| 19 | **ExecutionHistory** | **AGENT CORE (persistence)** | Persistent execution records. Core. |

### 3.2 Дополнительные компоненты

| Компонент | Слой | Почему |
|-----------|------|--------|
| FeedbackStore | **AGENT CORE (persistence)** | User feedback loop. Core. |
| UserPreferences | **AGENT CORE (knowledge)** | Per-capability learned params. Core. |
| Planner protocol | **AGENT CORE (contract)** | Type contract для planners. Core. |

### 3.3 Итоговая классификация

```
AGENT CORE (14 компонентов):
  ├── Orchestration
  │   └── ConversationAgent
  ├── Planning
  │   ├── LLMPlanner (adapter)
  │   ├── HeuristicPlanner (fallback)
  │   ├── AdaptivePlanner (decorator)
  │   └── TaskDecomposer
  ├── Registry
  │   ├── CapabilityRegistry (domain model)
  │   ├── WorkflowRegistry
  │   ├── ModelRegistry
  │   └── BackendCatalog
  ├── Execution
  │   └── WorkflowEngine
  ├── Verification
  │   ├── Verifier (basic)
  │   └── SemanticVerifier (vision)
  ├── Knowledge
  │   ├── KnowledgeCore
  │   ├── ExperienceStore
  │   ├── ExecutionHistory
  │   ├── FeedbackStore
  │   └── UserPreferences
  └── Contracts
      ├── Planner protocol
      └── PlanResult / PlanContext

ADAPTERS (2 компонента):
  ├── ComfyUIProvider (backend boundary)
  └── ComfyClient (transport)

INFRASTRUCTURE (1 компонент):
  └── AssetStore

DEPRECATED (1 компонент):
  └── MCP Server
```

---

## 4. Agent Core Responsibilities

### 4.1 Предлагаемая модель ядра

```text
AGENT CORE

Understand (session + context)
   ↓
Decompose (multi-intent → subtasks)
   ↓
Plan (capability + params)
   ↓
Select (workflow + provider + backend + model)
   ↓
Invoke (execute + track + fetch)
   ↓
Verify (basic + semantic)
   ↓
Correct / Retry (error classification → retry)
   ↓
Learn (experience + preferences)
   ↓
Reuse (knowledge + lineage)
```

### 4.2 Сквозные механизмы Core

| Механизм | Описание | Компонент |
|----------|----------|-----------|
| **Session / Context** | Multi-turn state, active assets, dialog state | ConversationAgent + ConversationContext |
| **Lineage** | Трассировка: request → plan → workflow → output → asset | AssetStore |
| **Feedback** | User ratings → learning | FeedbackStore |
| **Resource awareness** | VRAM, latency, cost | BackendCatalog + ModelRegistry |
| **Policy** | Retry limits, timeout, capability constraints | RetryPolicy + Planner |

### 4.3 Проверка гипотезы

**Гипотеза:**
```
Understand → Decompose → Plan → Select → Invoke → Verify → Correct → Learn → Reuse
```

**Оценка:**

| Шаг | Реализован? | Компонент | Соответствие |
|-----|-------------|-----------|--------------|
| Understand | ✅ | ConversationAgent (session + context) | ✅ Точное |
| Decompose | ✅ | TaskDecomposer | ✅ Точное |
| Plan | ✅ | LLMPlanner / HeuristicPlanner / AdaptivePlanner | ✅ Точное |
| Select | ✅ | WorkflowRegistry + BackendCatalog + ModelRegistry | ✅ Точное |
| Invoke | ✅ | WorkflowEngine → ComfyUIProvider → ComfyClient | ✅ Точное |
| Verify | ✅ | Verifier + SemanticVerifier | ✅ Точное |
| Correct/Retry | ✅ | RetryPolicy + classify_error | ✅ Точное |
| Learn | ✅ | ExperienceStore + UserPreferences | ✅ Точное |
| Reuse | ⚠️ | KnowledgeCore (частично) | ⚠️ Требует усиления |

**Вывод:** Гипотеза **подтверждена**. Текущий код уже реализует эту модель. Дополнительные сквозные механизмы (Session, Lineage, Feedback, Resource awareness, Policy) уже присутствуют.

### 4.4 Что НЕ входит в Core

| Функция | Почему не в Core |
|---------|-----------------|
| Внутренний код ComfyUI | External backend |
| Отдельные ComfyUI nodes | Primitives ecosystem |
| Реализации Agnes | Cloud provider |
| Внутренности LLM | Runtime ecosystem |
| Алгоритмы генерации | Backend responsibility |
| Конкретные specialist operators | External agents |

---

## 5. External Capability Ecosystem

### 5.1 Модель

```text
                    USER
                      ↓
                 AGENT CORE
                      │
          ┌───────────┼───────────┐
          ↓           ↓           ↓
       SELECT       INVOKE      VERIFY
          │           │           │
          └───────────┼───────────┘
                      ↓
              ACCESS LAYER
                      ↓
        ┌─────────────┼─────────────┐
        ↓             ↓             ↓
     ComfyUI        Agnes        llama.cpp
        ↓             ↓             ↓
     workflows      API         local runtime
        │
        ↓
   execution backends
```

### 5.2 External Ecosystem Map

| Элемент | Тип | Роль | Access Point | Backend | Нужен Agent adapter? |
|---------|-----|------|-------------|---------|---------------------|
| **ComfyUI** | Execution Backend | Image/video/audio generation | HTTP API | Local CPU / Remote GPU | ✅ ComfyUIProvider (есть) |
| **ComfyUI nodes** | Primitives | Стройки workflows | HTTP (/object_info) | Local CPU | ❌ Через WorkflowRegistry |
| **ComfyUI workflows** | Recipes | Готовые capability | HTTP (/prompt) | Local CPU | ❌ Через WorkflowEngine |
| **Agnes** | Cloud Provider | Free image/video gen | HTTP (custom nodes) | Cloud | ⚠️ Только через ComfyUI workflow |
| **OpenRouter** | Cloud LLM/VLM | Planning + verification | HTTP API | Cloud | ✅ LLMPlanner + SemanticVerifier (есть) |
| **llama.cpp** | Local LLM/VLM Runtime | Text + vision | OpenAI-compatible API | Local GPU (Vulkan) | ❌ НЕ интегрирован |
| **Qwen2.5-3B** | Model (text) | Text generation | через llama.cpp | Local GPU | ❌ НЕ интегрирован |
| **Qwen2.5-VL-3B** | Model (vision) | Vision understanding | через llama.cpp | Local GPU | ❌ НЕ интегрирован |
| **Gemma 4 E4B** | Specialist Operator | ComfyUI control via MCP | MCP protocol | Local GPU | ❌ НЕ установлен |
| **comfyui-mcp** | MCP Tools (178) | ComfyUI control surface | MCP protocol | Local | ❌ НЕ установлен |
| **MCP Fetch** | Utility | Web fetch | SSE :9001 | Local | ❌ НЕ интегрирован |
| **MCP Filesystem** | Utility | File read/search | SSE :9002 | Local | ❌ НЕ интегрирован |
| **MCP Memory** | Utility | Fact storage | SSE :9003 | Local (SQLite) | ❌ НЕ интегрирован |
| **Colab T4** | Remote GPU | GPU compute | HTTP (remote) | Remote GPU | ✅ BackendCatalog (есть) |

### 5.3 Access Layer

```text
ACCESS LAYER (Adapters):
  │
  ├── ComfyUIProvider    ←── ComfyClient (HTTP/WS)
  ├── OpenRouterAdapter   ←── LLMPlanner / SemanticVerifier
  ├── llama.cpp Adapter   ←── (NOT INTEGRATED)
  ├── MCP Adapter         ←── (NOT INTEGRATED)
  ├── Agnes Adapter       ←── (ONLY VIA ComfyUI workflow)
  └── Colab Adapter       ←── BackendCatalog (exists)
```

**Ключевой принцип:** Access Layer — это **thin adapters**. Agent Core не знает деталей протоколов. Core общается через protocols (Planner, Provider, Verifier).

---

## 6. Ontology

```
CAPABILITY         — логическая способность (image.generate)
    │
    ├── PRIMITIVE   — технический механизм (KSampler, CLIPTextEncode)
    ├── WORKFLOW    — recipe (связка primitives в manifest.json)
    ├── PROVIDER    — кто предоставляет (ComfyUI, Agnes, OpenRouter)
    ├── ACCESS POINT — как обращаться (HTTP, MCP, SSE)
    ├── BACKEND     — где считает (Local CPU, Remote GPU, Cloud)
    ├── RUNTIME     — модель/engine (Qwen2.5-3B, SD 1.x)
    └── SPECIALIST OPERATOR — обученный AI (Gemma 4 E4B)

Ключевые принципы:
  Node ≠ Capability
  Workflow ≠ Capability
  Provider ≠ Backend
  Operator ≠ Backend
```

---

## 7. Existing Components Mapping

### 7.1 Agent Core → отвечает за

| Обязанность | Компонент | Статус |
|------------|-----------|--------|
| Multi-turn dialog | ConversationAgent | ✅ Core |
| Decomposition | TaskDecomposer | ✅ Core |
| Planning (online) | LLMPlanner | ✅ Core (adapter) |
| Planning (fallback) | HeuristicPlanner | ✅ Core |
| Planning (adaptive) | AdaptivePlanner | ✅ Core (decorator) |
| Capability catalog | CapabilityRegistry | ✅ Core (domain model) |
| Workflow discovery | WorkflowRegistry | ✅ Core |
| Execution | WorkflowEngine | ✅ Core |
| Backend routing | BackendCatalog | ✅ Core |
| Model catalog | ModelRegistry | ✅ Core |
| Verification (basic) | Verifier | ✅ Core |
| Verification (vision) | SemanticVerifier | ✅ Core |
| Knowledge | KnowledgeCore | ✅ Core |
| Experience | ExperienceStore | ✅ Core |
| History | ExecutionHistory | ✅ Core |
| Feedback | FeedbackStore | ✅ Core |
| Preferences | UserPreferences | ✅ Core |
| Assets + Lineage | AssetStore | ✅ Infrastructure |

### 7.2 Adapters → подключают external ecosystem

| Adapter | Подключает | Статус |
|---------|-----------|--------|
| ComfyUIProvider | ComfyUI HTTP API | ✅ Adapter |
| ComfyClient | HTTP/WS transport | ✅ Adapter |
| LLMPlanner | OpenAI-compatible LLM | ✅ Adapter |
| SemanticVerifier | OpenRouter VLM | ✅ Adapter |

### 7.3 External Ecosystem → выполняет работу

| Элемент | Что делает | Доступен через |
|---------|-----------|---------------|
| ComfyUI (953 nodes) | Execution | ComfyUIProvider |
| ComfyUI workflows (6) | Recipes | WorkflowRegistry |
| OpenRouter | LLM/VLM | LLMPlanner / SemanticVerifier |
| llama.cpp (text) | Local LLM | NOT INTEGRATED |
| llama.cpp (vision) | Local VLM | NOT INTEGRATED |
| MCP servers | Utilities | NOT INTEGRATED |
| Agnes Cloud | Cloud gen | ONLY VIA ComfyUI |
| Gemma + comfyui-mcp | Specialist operator | NOT INSTALLED |

---

## 8. Discovery Model

### 8.1 Цепочка discovery

```text
Provider
   ↓
Access Point
   ↓
Discovery (/object_info, manifests, API)
   ↓
Available primitives / workflows / capabilities
   ↓
Normalization (→ Capability model)
   ↓
Selection (WorkflowRegistry + BackendCatalog + ModelRegistry)
   ↓
Invocation (WorkflowEngine → Provider → Backend)
   ↓
Verification (Verifier + SemanticVerifier)
   ↓
Experience (ExperienceStore → UserPreferences)
```

### 8.2 Что уже реализовано

| Шаг | Компонент | Статус |
|-----|-----------|--------|
| Provider | ComfyUIProvider | ✅ Adapter |
| Access Point | ComfyClient | ✅ Adapter |
| Discovery | KnowledgeCore + ModelRegistry | ✅ Core (частично дублируются) |
| Normalization | CapabilityRegistry | ✅ Core |
| Selection | WorkflowRegistry | ✅ Core |
| Invocation | WorkflowEngine | ✅ Core |
| Verification | Verifier + SemanticVerifier | ✅ Core |
| Experience | ExperienceStore + UserPreferences | ✅ Core |

### 8.3 GAP: Dynamic Capability Discovery

**FACT:** Agent обнаруживает capabilities ТОЛЬКО из manifest файлов. ComfyUI имеет 953 ноды, каждая из которых — потенциальная primitive.

**HYPOTHESIS:** Dynamic capability discovery из /object_info может расширить capabilities без ручного создания manifests.

**НО:** 953 nodes ≠ 953 capabilities. Нужна **normalization** — из 953 primitives нужно построить handful of capabilities. KnowledgeCore уже делает это частично (candidates + claims).

---

## 9. Specialist Operator Model

### 9.1 Gemma 4 E4B + comfyui-mcp

| Параметр | Значение |
|----------|----------|
| Тип | Fine-tuned Gemma 4 для ComfyUI MCP |
| Tools | 178 (113 server + 65 panel) |
| Статус | ❌ NOT INSTALLED |
| VRAM | ~3.5 GB (e4b) |
| Arena score | 14/20 |

### 9.2 Возможные роли

| Роль | Описание | Подходит ли Gemma? |
|------|----------|-------------------|
| **Planner** | Выбор capability + params | ✅ LLM по определению |
| **Workflow Builder** | Построение ComfyUI графа | ✅ Основная функция |
| **Tool Caller** | Вызов MCP tools | ✅ Native tool-call format |
| **Specialist Executor** | Полная оркестрация ComfyUI | ✅ 178 tools |
| **Fallback** | Резервный planner/executor | ⚠️ Требует VRAM |
| **Experimental** | Эксперименты с workflow | ✅ Подходит |

### 9.3 Рекомендуемая роль: **Specialist Executor (optional)**

**Почему не planner:** Agent Core уже имеет планирование (LLMPlanner + HeuristicPlanner). Gemma может быть **replacement** для ComfyUI-specific planning, но не для general planning.

**Почему specialist executor:** Gemma может выполнять роль **внешнего агента**, который:
- Получает от Agent Core: "выполни image.generate с параметрами X"
- Самостоятельно строит workflow через MCP tools
- Возвращает результат

**Ключевой принцип:** Gemma — это **внешний capability provider**, а не часть Agent Core.

### 9.4 Модель взаимодействия

```text
AGENT CORE
    │
    │ (capability + params)
    ↓
SPECIALIST OPERATOR (Gemma)
    │
    │ (MCP tools → ComfyUI)
    ↓
COMFYUI (execution)
    │
    │ (output)
    ↓
AGENT CORE (verification)
```

---

## 10. LLM/VLM Model

### 10.1 Архитектурная позиция

```text
LLM/VLM Runtime (llama.cpp, OpenRouter, и др.)
      ↓
Model Access Adapter (protocol-based)
      ↓
Agent Core (Planner, Verifier)
```

### 10.2 Текущая реальность

| Runtime | Тип | Compute | Endpoint | Статус |
|---------|-----|---------|----------|--------|
| llama.cpp (текст) | Local LLM | GPU (Vulkan) | `127.0.0.1:8080` | ✅ установлен, НЕ интегрирован |
| llama.cpp (vision) | Local VLM | GPU (Vulkan) | `127.0.0.1:8086` | ✅ установлен, НЕ интегрирован |
| OpenRouter | Cloud LLM/VLM | Cloud | `openrouter.ai/api/v1` | ✅ интегрирован |
| ComfyUI CPU | Local compute | CPU (APU) | `127.0.0.1:8188` | ✅ интегрирован |

### 10.3 Ключевой принцип

**НЕ пытаться искусственно объединять compute-пути:**

- ComfyUI = image/video/audio generation (CPU, workflows)
- llama.cpp = text + vision understanding (GPU, OpenAI-compatible API)
- OpenRouter = cloud LLM/VLM (API)
- Colab = remote GPU compute (workflows)

Это **разные compute domains** с разными access points. Agent Core общается с ними через **protocols**, не через единый backend.

### 10.4 Требуемые adapters

| Adapter | Подключает | Текущий статус |
|---------|-----------|---------------|
| LLMAdapter (OpenAI-compatible) | llama.cpp:8080 | ❌ НЕ интегрирован |
| VLMAdapter (OpenAI-compatible) | llama.cpp:8086 | ❌ НЕ интегрирован |
| CloudLLMAdapter | OpenRouter | ✅ LLMPlanner |
| CloudVLMAdapter | OpenRouter | ✅ SemanticVerifier |

---

## 11. Multi-provider Model

### 11.1 Текущая модель

```text
BackendCatalog
    ├── local_comfyui (CPU)
    ├── remote_colab (GPU)
    └── agnes_cloud (free)
```

### 11.2 Проблема

BackendCatalog знает о backends, но **не выбирает по capability**. Выбор происходит в WorkflowRegistry (по manifest), а не по backend properties.

### 11.3 Предлагаемая модель

```text
Agent Core
    │
    ├── CapabilityRouter
    │   ├── capability → provider → backend → runtime
    │   └── filters: VRAM, latency, cost, availability
    │
    ├── Access Layer
    │   ├── ComfyUIAdapter (HTTP)
    │   ├── OpenRouterAdapter (HTTP)
    │   ├── llama.cppAdapter (HTTP)
    │   └── MCPAdapter (SSE)
    │
    └── Backends
        ├── Local CPU (ComfyUI)
        ├── Local GPU (llama.cpp)
        ├── Remote GPU (Colab)
        └── Cloud (OpenRouter, Agnes)
```

---

## 12. Architecture Decisions

### AD-NEW-01: Agent Core Boundary

**Decision:** Что является стабильным ядром Agent vs внешняя ecosystem?

**Options:**
1. **Agent = orchestration only** — Rules + WorkflowEngine + Verifier
2. **Agent = intelligence + orchestration + ecosystem management** — Understand + Plan + Select + Invoke + Verify + Learn + Discovery
3. **Agent = thin wrapper** — Minimal routing + Specialist Operators

**Recommended:** Option 2

**Why:**
- Option 1 слишком примитивен — нет learning, no knowledge, no multi-turn
- Option 3 слишком зависим от external operators — нет fallback
- Option 2 даёт баланс: стабильное ядро + подключаемая ecosystem

**Consequences:**
- Agent Core остаётся стабильным при замене backends
- Новые capabilities добавляются через adapters, не через изменение Core
- Specialist operators подключаются как optional components

**What becomes unnecessary:**
- Жёсткая привязка к ComfyUI в WorkflowEngine (должен стать generic)

**What new abstraction is required:**
- ExecutionAdapter protocol (для generic execution)

---

### AD-NEW-02: Local LLM/VLM Integration

**Decision:** Интегрировать ли llama.cpp как primary/fallback LLM/VLM backend?

**Options:**
1. **llama.cpp как primary** — текст + vision через `127.0.0.1:8080/8086`
2. **OpenRouter как primary, llama.cpp как fallback** — cloud first, local backup
3. **Оба параллельно** — текст → llama.cpp, vision → OpenRouter

**Recommended:** Option 2

**Why:**
- OpenRouter уже интегрирован и работает
- llama.cpp требует отдельной интеграции
- Fallback на local LLM обеспечивает availability без cloud
- Option 3 избыточен — vision тоже доступен через llama.cpp

**Consequences:**
- LLMPlanner получает fallback на local LLM
- SemanticVerifier получает fallback на local VLM
- Убирает зависимость от external API key для базовых задач

**What becomes unnecessary:**
- fallback_proxy :20130 (заменяется на llama.cpp:8080)

**What new abstraction is required:**
- LLMAdapter protocol (OpenAI-compatible wrapper)
- VLMAdapter protocol (OpenAI-compatible wrapper)

---

### AD-NEW-03: Capability Discovery Strategy

**Decision:** Dynamic (из /object_info) vs declared (manifests) vs hybrid?

**Options:**
1. **Declared only** — capabilities заданы в коде/manifests
2. **Dynamic only** — автоматическое построение из /object_info
3. **Hybrid** — declared core + dynamic expansion

**Recommended:** Option 3

**Why:**
- Option 1 не масштабируется — новые capabilities требуют кода
- Option 2 ненадёжно — 953 nodes ≠ 953 capabilities
- Option 3 даёт стабильный core + расширяемость

**Consequences:**
- Core capabilities остаются declared (image.generate, video.generate, etc.)
- Dynamic discovery расширяет catalog через KnowledgeCore
- Normalization layer строит capabilities из primitives

**What becomes unnecessary:**
- Manual manifest creation для новых capabilities (partial)

**What new abstraction is required:**
- CapabilityNormalizer (primitives → capabilities)

---

### AD-NEW-04: Specialist Operators Role

**Decision:** Использовать ли Gemma/comfyui-mcp как part of ecosystem?

**Options:**
1. **Operator как replacement** — Gemma заменяет Agent Core
2. **Operator как specialist executor** — Gemma выполняет ComfyUI-specific tasks
3. **Operator как planner** — Gemma планирует workflows
4. **Operator как optional** — подключается по необходимости

**Recommended:** Option 4

**Why:**
- Option 1 слишком рискованно — нет fallback
- Option 2 и 3too specific — Gemma может и планировать, и выполнять
- Option 4 даёт гибкость: Gemma = optional specialist, не замена Agent

**Consequences:**
- Agent Core остаётся primary orchestrator
- Gemma подключается как optional tool для ComfyUI-specific tasks
- При отсутствии Gemma — Agent работает через WorkflowEngine

**What becomes unnecessary:**
- Ничего не становится лишним — Gemma = addition, not replacement

**What new abstraction is required:**
- SpecialistOperator protocol (optional interface)

---

### AD-NEW-05: Multi-provider Routing

**Decision:** Как выбирать между local ComfyUI, cloud Agnes, llama.cpp, OpenRouter?

**Options:**
1. **Manual selection** — пользователь/код выбирает provider
2. **Capability-based routing** — capability → provider mapping
3. **Cost/latency-aware routing** — выбор по VRAM, latency, cost
4. **Hybrid** — capability-based + cost/latency fallback

**Recommended:** Option 4

**Why:**
- Option 1 не масштабируется
- Option 2 не учитывает cost/latency
- Option 3 слишком сложен для старта
- Option 4 даёт баланс: capability mapping + optimization

**Consequences:**
- BackendCatalog расширяется capability-based routing
- Добавляется cost/latency metadata для backends
- Routing policy становится configurable

**What becomes unnecessary:**
- Hardcoded backend selection в WorkflowRegistry

**What new abstraction is required:**
- CapabilityRouter (capability → backend + cost/latency metadata)

---

## 13. Consequences Summary

### 13.1 Что остаётся стабильным

| Компонент | Статус | Причина |
|-----------|--------|---------|
| ConversationAgent | ✅ Core | Оркестрация — незаменима |
| CapabilityRegistry | ✅ Core | Domain model — стабилен |
| Planner protocol | ✅ Core | Contract — стабилен |
| Planner implementations | ✅ Core | Planning — незаменим |
| TaskDecomposer | ✅ Core | Decomposition — чистая логика |
| WorkflowRegistry | ✅ Core | Selection — незаменим |
| WorkflowEngine | ✅ Core | Execution — незаменим (НО требует generic) |
| Verifier + SemanticVerifier | ✅ Core | Verification — незаменим |
| ExperienceStore + UserPreferences | ✅ Core | Learning — незаменим |
| AssetStore | ✅ Infrastructure | Lineage — незаменим |

### 13.2 Что адаптируется

| Компонент | Изменение |
|-----------|----------|
| ComfyUIProvider | Становится одним из many adapters |
| LLMPlanner | Добавляет fallback на llama.cpp |
| SemanticVerifier | Добавляет fallback на local VLM |
| BackendCatalog | Расширяется capability routing |

### 13.3 Что добавляется

| Компонент | Назначение |
|-----------|-----------|
| LLMAdapter | OpenAI-compatible wrapper для local LLM |
| VLMAdapter | OpenAI-compatible wrapper для local VLM |
| CapabilityRouter | Capability → backend routing |
| SpecialistOperator protocol | Optional interface для external agents |
| CapabilityNormalizer | Primitives → capabilities |

### 13.4 Что становится Deprecated

| Компонент | Причина |
|-----------|---------|
| MCP Server | Используется только внешними AI |
| fallback_proxy :20130 | Заменяется на llama.cpp:8080 |

---

## 14. Open Questions

| # | Вопрос | Приоритет |
|---|--------|-----------|
| 1 | Должен ли WorkflowEngine стать generic (не ComfyUI-specific)? | HIGH |
| 2 | Нужен ли CapabilityNormalizer для dynamic discovery? | MEDIUM |
| 3 | Какой adapter pattern использовать для local LLM? | HIGH |
| 4 | Как интегрировать Gemma как optional specialist? | MEDIUM |
| 5 | Достаточна ли текущая Verification для dynamic capabilities? | LOW |

---

## 15. Proposed Next Implementation Phase

### 15.1 Не реализовать сейчас

| Задача | Статус | Причина |
|--------|--------|---------|
| M25 new capabilities | PAUSED | Сначала — архитектурное решение |
| Gemma installation | PAUSED | Сначала — определить роль |
| comfyui-mcp installation | PAUSED | Сначала — определить роль |
| llama.cpp integration | PAUSED | Сначала — определить adapter pattern |
| Dynamic discovery | PAUSED | Сначала — определить normalization |

### 15.2 Что делать перед реализацией

| Шаг | Описание | Priority |
|-----|----------|----------|
| 1 | Принять AD-NEW-01 (Agent Core boundary) | CRITICAL |
| 2 | Принять AD-NEW-02 (Local LLM/VLM integration) | HIGH |
| 3 | Принять AD-NEW-03 (Capability discovery) | HIGH |
| 4 | Принять AD-NEW-04 (Specialist Operators) | MEDIUM |
| 5 | Принять AD-NEW-05 (Multi-provider routing) | MEDIUM |
| 6 | Определить ExecutionAdapter protocol | HIGH |
| 7 | Определить LLMAdapter/VLMAdapter protocols | HIGH |
| 8 | спроектировать CapabilityRouter | MEDIUM |

---

# RECOMMENDATION

## Какую архитектуру рекомендуется строить дальше

**Рекомендация: Гибридная архитектура "Agent Core + Access Layer + Optional Specialists".**

### Почему

1. **Agent Core остаётся стабильным.** ConversationAgent, planners, registries, engine, verifiers, knowledge — это неизменяемое ядро, которое НЕ зависит от конкретных backends.

2. **Access Layer подключает ecosystem.** ComfyUIProvider, LLMPlanner, SemanticVerifier — это thin adapters, которые можно заменить/расширить без изменения Core.

3. **Specialist Operators — optional.** Gemma + comfyui-mcp может подключаться как external agent для ComfyUI-specific tasks, но НЕ заменяет Agent Core.

4. **Local LLM/VLM — fallback, не primary.** llama.cpp + Vulkan обеспечивает offline availability, но не заменяет cloud LLM/VLM для complex tasks.

5. **Discovery — hybrid.** Declared core capabilities + dynamic expansion через KnowledgeCore.

### Конкретные шаги

1. **Принять AD-NEW-01:** Agent Core = orchestration + planning + selection + execution + verification + knowledge
2. **Принять AD-NEW-02:** llama.cpp как fallback LLM/VLM (adapter pattern)
3. **Принять AD-NEW-03:** Hybrid capability discovery (declared + dynamic)
4. **Принять AD-NEW-04:** Gemma как optional specialist operator
5. **Принять AD-NEW-05:** Capability-based routing с cost/latency metadata

### Чего НЕ делать

- **НЕ строить Agent как wrapper вокруг Gemma** — Gemma = external specialist
- **НЕ делать Agent ComfyUI-specific** — ComfyUI = one of many backends
- **НЕ пытаться объединить все compute-пути** — разные domains, разные access points
- **НЕ отказываться от существующего кода** — M1-M24 = стабильный foundation

---

*Документ создан как архитектурный проект. Production code НЕ изменяется. Gemma НЕ устанавливается. llama.cpp НЕ подключается. Новые сервисы НЕ создаются.*
