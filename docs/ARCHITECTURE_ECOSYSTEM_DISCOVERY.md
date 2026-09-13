# ARCHITECTURE ECOSYSTEM DISCOVERY

**Дата:** 2026-09-06 (v2)
**Цель:** Архитектурная разведка экосистемы для определения стабильного ядра Agent и границ внешней capability ecosystem.
**Статус:** FACT + INFERENCE + HYPOTHESIS. Архитектурное исследование, не реализация.

---

## 0. Status Legend

| Статус | Определение |
|--------|-------------|
| **FACT** | Непосредственно проверено в текущем окружении через API/файлы/тесты |
| **INFERENCE** | Логический вывод из проверенных фактов |
| **HYPOTHESIS** | Архитектурная гипотеза, требующая проверки |
| **UNKNOWN** | Пока не проверено |

---

## 1. Ontology — Категории экосистемы

### 1.1 Определения

| Категория | Определение | Пример |
|-----------|-------------|--------|
| **Capability** | Логическая способность системы (что система умеет делать для пользователя) | image.generate, video.generate, knowledge.query |
| **Primitive** | Отдельный технический механизм (нода, функция, API call), из которого capability может состоять | KSampler, CLIPTextEncode, upload_image |
| **Workflow / Recipe** | Конкретный способ выполнить capability (связка primitives в правильном порядке) | txt2img workflow (manifest.json) |
| **Provider** | Кто предоставляет capability (сервис, API, backend) | ComfyUI local, Agnes Cloud, OpenRouter |
| **Access Point / Interface** | Каким способом Agent обращается к provider | HTTP API, MCP protocol, Python import |
| **Execution Backend** | Где реально выполняется работа (compute) | Local CPU (ComfyUI), Remote GPU (Colab), Cloud (Agnes) |
| **Runtime / Model** | Конкретная модель или runtime engine | Qwen2.5-3B, SD 1.x, Qwen2.5-VL-3B |
| **Specialist Operator** | Специализированный AI, который умеет пользоваться инструментами экосистемы | Gemma 4 E4B + comfyui-mcp |

### 1.2 Ключевые принципы

```
Node ≠ Capability       (нода — это primitive, capability — логическая способность)
Workflow ≠ Capability   (workflow — это recipe, capability — цель)
Provider ≠ Backend      (provider — кто предоставляет, backend — где считает)
Operator ≠ Backend      (operator — кто решает, backend — где считает)
```

---

## 2. Ecosystem Map — Вся обнаруженная экосистема

### 2.1 Execution Backends

| Backend | Тип | Compute | Статус | FACT/INFERENCE |
|---------|-----|---------|--------|----------------|
| ComfyUI Local | Local | CPU (AMD APU, 31.9 GB shared) | ✅ запущен на `127.0.0.1:8188` | FACT |
| Colab T4 | Remote GPU | NVIDIA Tesla T4, 16 GB | ✅ tested (M5/M6) | FACT |
| Agnes Cloud | Cloud | Неизвестно | ✅ доступен (free API) | FACT |

### 2.2 LLM/VLM Runtimes

| Runtime | Тип | Model | Endpoint | Статус | FACT/INFERENCE |
|---------|-----|-------|----------|--------|----------------|
| llama.cpp + Vulkan (текст) | Local | **Qwen2.5-3B-Instruct-Q4_K_M** | `http://127.0.0.1:8080` | ✅ установлен, 5 профилей | FACT |
| llama.cpp + Vulkan (vision) | Local | Qwen2.5-VL-3B-Instruct-Q4_K_M + mmproj | `http://127.0.0.1:8086` | ✅ установлен, профиль vision | FACT |
| OpenRouter | Cloud | gpt-4o-mini (и др.) | `https://openrouter.ai/api/v1` | ✅ через API key | FACT |
| ComfyUI built-in | Internal | Qwen2.5-3B, Gemma2-2B, Gemma3-4B (энкодеры) | Внутри pipeline | ✅ НЕ внешний сервис | FACT |
| fallback_proxy | Local | неизвестно | `http://127.0.0.1:20130` | ❌ NOT REACHABLE | FACT |

### 2.3 Cloud/API Providers

| Provider | API | Capabilities | Доступ через Agent | FACT/INFERENCE |
|----------|-----|-------------|-------------------|----------------|
| Agnes Cloud | `https://apihub.agnes-ai.com/v1` | image.generate, video.generate, text enhance | ⚠️ Только через ComfyUI workflow (custom nodes) | FACT |
| OpenRouter | `https://openrouter.ai/api/v1` | LLM planning, vision verification | ✅ LLMPlanner + SemanticVerifier | FACT |
| SoniloTextToMusic | Cloud API | audio.generate | ⚠️ Через workflow (объявлен, не протестирован) | INFERENCE |

### 2.4 ComfyUI Primitives (Nodes)

**FACT:** Рабочая установка: `C:\Users\1\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI (2)\ComfyUI\`

**FACT:** `/object_info` возвращает **953 типа нод** (APSHOT ver 0.34.5)

| Категория нод | Количество | Назначение |
|---------------|-----------|-----------|
| Text encoding | ~50 | CLIP, T5, LLM-энкодеры |
| Sampling | ~30 | KSampler, Euler, DDIM |
| Conditioning | ~40 | ControlNet, IPAdapter |
| Image processing | ~100 | Resize, Crop, composite |
| Video processing | ~20 | AnimateDiff, video encode |
| Audio processing | ~10 | Audio encode/decode |
| Model management | ~30 | CheckpointLoader, LoRALoader |
| Utility | ~200+ | Mathematics, routing, switch |
| Остальные | ~483 | Разное |

**CUSTOM NODES (УСТАНОВЛЕНЫ):**

| Нода | Primitive/Tool | Назначение |
|------|---------------|-----------|
| ComfyUI-Agnes-AI | Access Point | Cloud generation (image/video/text) |
| openrouter_node | Access Point | External LLM via OpenRouter |
| comfyui-openai-compatible | Access Point | OpenAI-compatible LLM (llama.cpp, Ollama) |
| ComfyUI-Qwen-VL-API | Access Point | Qwen-VL via API |
| QwenVL-F | Access Point | Local Qwen VL models (GGUF) |
| qwen3vl_api | Access Point | Qwen3 VL API |
| comfyui-reactor | Primitive | Face swap/restore |

### 2.5 MCP Servers (installed)

| Сервер | Endpoint | Tools | Статус | FACT/INFERENCE |
|--------|----------|-------|--------|----------------|
| MCP Fetch | `http://127.0.0.1:9001/sse` | fetch | ✅ установлен | FACT |
| MCP Filesystem | `http://127.0.0.1:9002/sse` | read_file, list_directory, search_files | ✅ установлен | FACT |
| MCP Memory | `http://127.0.0.1:9003/sse` | remember, recall, forget, list_facts | ✅ установлен (SQLite FTS5) | FACT |
| Agent MCP Server | stdio | comfy_status, comfy_node_types, comfy_node_info, comfy_queue, comfy_history, comfy_download_outputs | ✅ DEPRECATED (для внешних AI) | FACT |
| comfyui-mcp (artokun) | НЕ установлен | 178 tools (113 server + 65 panel) | ❌ NOT INSTALLED | FACT |

### 2.6 Checkpoints / Models

| Модель | Тип | Backend | Статус |
|--------|-----|---------|--------|
| cyberrealistic_v80.safetensors | SD 1.x | local_comfyui | ✅ |
| majicmixRealistic_v7.safetensors | SD 1.x | local_comfyui | ✅ |
| Qwen2.5-3B-Instruct-Q4_K_M | LLM | llama.cpp | ✅ |
| Qwen2.5-VL-3B-Instruct-Q4_K_M | VLM | llama.cpp | ✅ |

**FACT:** Только 2 SD 1.x чекпоинта. Нет SDXL, Flux.

---

## 3. Gemma 4 E4B (Heretic) — Отдельное исследование

### 3.1 Что это

| Параметр | Значение | FACT/INFERENCE |
|----------|----------|----------------|
| HuggingFace | `artokun/gemma4-comfyui-mcp` | FACT (из README) |
| Тип | Fine-tuned Gemma 4 для ComfyUI MCP | FACT |
| Доступные кванти | :e2b (~2GB), :e4b (~3.5GB), :12b (~8GB) | FACT (из README) |
| Установка | `ollama pull artokun/gemma4-comfyui-mcp:e4b` | FACT (из README) |
| Требование | Ollama + ~3.5 GB VRAM (или CPU offload) | INFERENCE |
| Назначение | Управление ComfyUI через 178 MCP tools | FACT |
| Статус в окружении | ❌ НЕ установлен | FACT |
| Arena score | 14/20 (лучший локальный для ComfyUI) | FACT (из README) |

### 3.2 Что он умеет

**FACT (из README):** "Local, offline LLMs fine-tuned to be ComfyUI experts that drive the full comfyui-mcp tool surface"

- Управлять ComfyUI графом (создавать/редактировать/запускать workflows)
- Использовать 178 инструментов для image/video/audio generation
- Работать через MCP протокол
- Native tool-call format (finish_reason=tool_calls)

### 3.3 Tool Surface (comfyui-mcp)

| Категория | Количество | Примеры |
|-----------|-----------|---------|
| Server tools | 113 | comfy_status, comfy_node_types, comfy_node_info, comfy_queue, comfy_history, comfy_download_outputs |
| Panel tools (live-canvas) | 65 | UI interaction tools |
| **Всего** | **178** | |

### 3.4 Кем является Gemma 4 E4B + comfyui-mcp

| Вопрос | Ответ | FACT/INFERENCE |
|--------|-------|----------------|
| Это LLM? | Да, fine-tuned Gemma 4 | FACT |
| Это Specialist Operator? | **Да** — обучен управлять инструментами экосистемы | INFERENCE |
| Это готовый ComfyUI control plane? | **Частично** — может выполнять функции планировщика + executor для ComfyUI | INFERENCE |
| Заменяет ли Agent? | **НЕТ** — см. анализ ниже | INFERENCE |

### 3.5 Что Gemma может выполнять из текущей архитектуры Agent

| Функция Agent | Может ли Gemma | Комментарий |
|---------------|---------------|-------------|
| Понимание пользовательской задачи | ✅ | LLM по определению |
| Decomposition | ✅ | LLM |
| Selection capability | ✅ | Через MCP tools |
| Планирование workflow | ✅ | **Основная функция** — строит ComfyUI граф |
| Invocation | ✅ | MCP tools → ComfyUI |
| Verification | ⚠️ | Только если vision model встроена в pipeline |
| Knowledge/experience | ❌ | Нет памяти между сессиями |
| Multi-turn context | ⚠️ | Базовый, без session management |
| Resource/cost awareness | ❌ | Не знает о VRAM/latency/cost |
| Lineage tracking | ❌ | Нет AssetStore |

### 3.6 Что Gemма принципиально НЕ заменяет

| Функция | Почему не заменяет |
|---------|-------------------|
| Asset management | Нет AssetStore, UUID-based lineage |
| Knowledge/experience persistence | Нет JSONL persistence между сессиями |
| Multi-backend routing | Не знает о BackendCatalog |
| Verification loop | Нет automated retry с feedback |
| Human-in-the-loop | Нет session management для принятия решений пользователем |
| Cross-provider orchestration | Работает только с ComfyUI через MCP |

### 3.7 Gemma в контексте архитектуры

**INFERENCE:** Gemma 4 E4B + comfyui-mcp — это **Specialist Operator**, который может выполнять роль "ComfyUI-aware planner/executor". Он НЕ заменяет Agent целиком, но может заменить часть `WorkflowEngine` + `WorkflowRegistry` для ComfyUI-specific capabilities.

**HYPOTHESIS:** Гибридный подход: Agent Core (planning, knowledge, verification, multi-backend) + Specialist Operators (Gemma для ComfyUI, другие для других backends).

---

## 4. Provider Map — Провайдеры и access points

### 4.1 Capability → Provider → Access Point → Backend

| Capability | Provider | Access Point | Backend | Runtime/Model | FACT/INFERENCE |
|------------|----------|-------------|---------|---------------|----------------|
| image.generate | ComfyUI | HTTP API (`ComfyClient`) | Local CPU | SD 1.x checkpoints | FACT |
| image.edit | ComfyUI | HTTP API (`ComfyClient`) | Local CPU | SD 1.x + ControlNet/IPAdapter | FACT |
| image.upscale | ComfyUI | HTTP API (`ComfyClient`) | Local CPU | Upscale models | FACT |
| video.generate | ComfyUI | HTTP API (`ComfyClient`) | Local CPU / Remote Colab | AnimateDiff | FACT |
| video.image_to_video | ComfyUI | HTTP API (`ComfyClient`) | Local CPU | — | FACT |
| audio.generate | Agnes Cloud | ComfyUI workflow (AgnesText) | Cloud | SoniloTextToMusic | INFERENCE |
| LLM planning | OpenRouter | HTTP API (`LLMPlanner`) | Cloud | gpt-4o-mini | FACT |
| LLM planning | llama.cpp | HTTP API (OpenAI-compatible) | Local | Qwen2.5-3B | FACT |
| VLM verification | OpenRouter | HTTP API (`SemanticVerifier`) | Cloud | gpt-4o-mini (vision) | FACT |
| VLM verification | llama.cpp | HTTP API (OpenAI-compatible) | Local | Qwen2.5-VL-3B | FACT |
| MCP Fetch | MCP Fetch | SSE (`http://127.0.0.1:9001`) | Local | — | FACT |
| MCP Filesystem | MCP Filesystem | SSE (`http://127.0.0.1:9002`) | Local | — | FACT |
| MCP Memory | MCP Memory | SSE (`http://127.0.0.1:9003`) | Local | SQLite FTS5 | FACT |
| ComfyUI control | comfyui-mcp (artokun) | MCP protocol | Local | Gemma 4 E4B | NOT INSTALLED |

### 4.2 Access Point Types

| Access Point | Протокол | Используется Agent | Примечание |
|-------------|----------|-------------------|-----------|
| ComfyUI HTTP API | HTTP/WS | ✅ ComfyClient | Главный access point |
| OpenAI-compatible API | HTTP | ❌ НЕ интегрирован | llama.cpp:8080/8086 |
| MCP SSE | SSE | ❌ НЕ интегрирован | Fetch:9001, FS:9002, Memory:9003 |
| OpenRouter API | HTTP | ✅ LLMPlanner + SemanticVerifier | Через API key |
| Agnes API Hub | HTTP | ❌ Через ComfyUI workflow | custom nodes |

---

## 5. Agent Map — Существующий Agent

### 5.1 Mapping: Существующий компонент → Архитектурная ответственность

| Компонент | Файл | Ответственность | Архитектурный слой |
|-----------|------|-----------------|-------------------|
| **ConversationAgent** | `app/conversation.py` | Multi-turn dialog, orchestration, retry, chain execution | **Orchestration Core** |
| **LLMPlanner** | `app/planner/llm.py` | LLM-based planning (capability + params из natural language) | **Planner (online adapter)** |
| **AdaptivePlanner** | `app/planner/adaptive.py` | History-aware parameter optimization | **Planner (decorator)** |
| **TaskDecomposer** | `app/planner/decomposer.py` | Multi-intent request splitting | **Pre-planner** |
| **HeuristicPlanner** | `app/planner/heuristic.py` | Keyword-based capability matching | **Planner (fallback)** |
| **WorkflowRegistry** | `app/registry/registry.py` | Workflow discovery, validation, compatibility, selection | **Registry (capability→workflow)** |
| **CapabilityRegistry** | `app/registry/capability.py` | Logical capability catalog (domain model) | **Domain model** |
| **WorkflowEngine** | `app/engine/engine.py` | Prompt assembly, execution, output validation | **Execution engine** |
| **ComfyUIProvider** | `app/provider/comfyui.py` | ComfyUI HTTP API adapter (upload, queue, track, fetch) | **Adapter (backend boundary)** |
| **BackendCatalog** | `app/registry/backends.py` | Multi-backend routing (local/remote/cloud) | **Infrastructure catalog** |
| **ModelRegistry** | `app/registry/model.py` | Per-backend model catalog (discovery, resolution) | **Infrastructure catalog** |
| **KnowledgeCore** | `app/knowledge/core.py` | Runtime discovery (/object_info), capability candidates, gap detection | **Knowledge (runtime discovery)** |
| **SemanticVerifier** | `app/engine/semantic_verifier.py` | Vision-based output quality check | **Verification** |
| **ExperienceStore** | `app/engine/experience.py` | Execution history (JSONL) | **Knowledge (experience)** |
| **AssetStore** | `app/assets/store.py` | Asset management, lineage, UUID-based storage | **Infrastructure (assets)** |
| **MCP Server** | `comfyui_mcp_server.py` | MCP tools для внешних AI (DEPRECATED) | **Legacy adapter** |
| **ComfyClient** | `app/comfy/client.py` | HTTP/WS transport к ComfyUI | **Transport** |
| **Verifier** | `app/engine/verifier.py` | Sequence verification (file existence + type) | **Verification (basic)** |
| **ExecutionHistory** | `app/engine/history.py` | Persistent execution records | **Knowledge (history)** |
| **FeedbackStore** | `app/context/feedback.py` | User ratings (JSONL) | **Knowledge (feedback)** |
| **UserPreferences** | `app/planner/preferences.py` | Per-capability learned preferences | **Knowledge (preferences)** |

### 5.2 Архитектурные слои существующего Agent

```text
┌─────────────────────────────────────────────────────────┐
│                    ORCHESTRATION CORE                    │
│  ConversationAgent + TaskDecomposer + AdaptivePlanner   │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────┼──────────────────────────────────┐
│                    PLANNING LAYER                        │
│  LLMPlanner / HeuristicPlanner → PlanResult             │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────┼──────────────────────────────────┐
│                    REGISTRY LAYER                        │
│  CapabilityRegistry + WorkflowRegistry + ModelRegistry   │
│  BackendCatalog + RuntimeInfo                            │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────┼──────────────────────────────────┐
│                    EXECUTION LAYER                       │
│  WorkflowEngine → ComfyUIProvider → ComfyClient → API   │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────┼──────────────────────────────────┐
│                    VERIFICATION LAYER                    │
│  Verifier (basic) + SemanticVerifier (vision)            │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────┼──────────────────────────────────┐
│                    KNOWLEDGE LAYER                       │
│  KnowledgeCore + ExperienceStore + ExecutionHistory      │
│  FeedbackStore + UserPreferences                         │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────┼──────────────────────────────────┐
│                 INFRASTRUCTURE LAYER                     │
│  AssetStore + ComfyClient + MCP Server (deprecated)      │
└─────────────────────────────────────────────────────────┘
```

### 5.3 Что уже является частью будущего ядра

| Функция | Уже реализована | Компонент |
|---------|----------------|-----------|
| Multi-turn dialog | ✅ | ConversationAgent |
| Decomposition | ✅ | TaskDecomposer |
| LLM planning | ✅ | LLMPlanner |
| History-aware planning | ✅ | AdaptivePlanner |
| Capability catalog | ✅ | CapabilityRegistry |
| Workflow discovery | ✅ | WorkflowRegistry |
| Execution | ✅ | WorkflowEngine |
| Multi-backend | ✅ | BackendCatalog |
| Model discovery | ✅ | ModelRegistry |
| Verification | ✅ | SemanticVerifier |
| Knowledge | ✅ | KnowledgeCore |
| Experience | ✅ | ExperienceStore |
| Asset management | ✅ | AssetStore |
| Feedback | ✅ | FeedbackStore |

### 5.4 Что является историческим/временным слоем

| Компонент | Статус | Причина |
|-----------|--------|---------|
| MCP Server (`comfyui_mcp_server.py`) | DEPRECATED | Используется только внешними AI |
| `HeuristicPlanner` | FALLBACK | Используется когда LLM недоступен |
| `WorkflowEngine.build_prompt()` | WORKING | Specific to ComfyUI prompt format |

---

## 6. FACT vs HYPOTHESIS — Перепроверка

### 6.1 FACT (проверено)

| # | Факт | Проверка |
|---|------|----------|
| F1 | ComfyUI запущен на `127.0.0.1:8188`, версия 0.34.5 | `GET /system_stats` |
| F2 | 953 типа нод в `/object_info` | `GET /object_info` |
| F3 | 6 workflows (txt2img, img2img, upscale, video_generate, video_image_to_video, audio_generate) | manifests + tests |
| F4 | 7 custom nodes установлены | `ls custom_nodes/` |
| F5 | llama.cpp + Vulkan: текст `127.0.0.1:8080` (Qwen2.5-3B), vision `127.0.0.1:8086` (Qwen2.5-VL-3B) | файлы в `C:\llama.cpp_Vulkan\` |
| F6 | MCP servers: Fetch:9001, Filesystem:9002, Memory:9003 | файлы в `C:\llama.cpp_Vulkan\my-profiles\_shared\mcp-servers\` |
| F7 | Agent code: M1-M24 fully implemented | `tests/` pass (36 tests) |
| F8 | LLMPlanner настроен на `fallback_proxy :20130` (НЕДОСТУПЕН) | `app/planner/llm.py` |
| F9 | SemanticVerifier использует OpenRouter (cloud) | `app/engine/semantic_verifier.py` |
| F10 | 2 SD 1.x чекпоинта (нет SDXL/Flux) | `models/checkpoints/` |

### 6.2 INFERENCE (логический вывод)

| # | Вывод | Основа |
|---|-------|--------|
| I1 | Agent НЕ интегрирован с llama.cpp + Vulkan | F5 + F8 + F9 |
| I2 | ComfyUI-internal LLM/VLM ноды установлены, но Agent их не использует | F4 + код |
| I3 | KnowledgeCore дублирует runtime discovery с ModelRegistry | код обоих компонентов |
| I4 | Agnes доступен ТОЛЬКО через ComfyUI workflow (single point of failure) | custom nodes |
| I5 | Gemma 4 E4B может быть specialist operator для ComfyUI | F5 + README |

### 6.3 HYPOTHESIS (архитектурные гипотезы)

| # | Гипотеза | Требует проверки |
|---|---------|-----------------|
| H1 | llama.cpp + Vulkan может заменить OpenRouter для planning/verification | Интеграция + тесты |
| H2 | Dynamic capability discovery из /object_info может расширить capabilities | Реализация |
| H3 | Gemma 4 E4B + comfyui-mcp может заменить WorkflowEngine для ComfyUI | Установка + тесты |
| H4 | Hybrid architecture (код + LLM оркестрация) оптимальна | Аналитический comparison |

### 6.4 UNKNOWN (не проверено)

| # | Вопрос | Приоритет |
|---|--------|-----------|
| U1 | Работает ли Gemma 4 E4B на CPU (offload)? | HIGH |
| U2 | Какой VRAM нужен для Qwen2.5-VL-3B? | MEDIUM |
| U3 | Какой latency у Agnes Cloud API? | LOW |

---

## 7. Boundary: Agent Core vs External Capability Ecosystem

### 7.1 Agent Core — Стабильное ядро

**Функции, которые ДОЛЖНЫ оставаться ответственностью Agent:**

| Функция | Описание | Статус в коде |
|---------|----------|---------------|
| **Understand** | Понимание пользовательской задачи, multi-turn context | ✅ ConversationAgent |
| **Decompose** | Разбиение сложных задач на простые | ✅ TaskDecomposer |
| **Plan** | Выбор capability + параметров | ✅ LLMPlanner / HeuristicPlanner |
| **Select** | Выбор workflow/provider/backend | ✅ WorkflowRegistry + BackendCatalog |
| **Invoke** | Вызов execution | ✅ WorkflowEngine |
| **Verify** | Проверка результата | ✅ SemanticVerifier |
| **Retry/Correct** | Повтор при ошибке | ✅ RetryPolicy |
| **Learn** | Запоминание опыта | ✅ ExperienceStore |
| **Feedback** | Обратная связь пользователя | ✅ FeedbackStore |
| **Lineage** | Трассировка результата | ✅ AssetStore |
| **Resource awareness** | Осведомлённость о VRAM/cost/latency | ⚠️ Частично (BackendCatalog) |

### 7.2 External Capability Ecosystem — Внешние capabilities

**Что Agent НЕ должен владеть:**

| Компонент | Почему не должен владеть |
|-----------|------------------------|
| Внутренний код ComfyUI | Внешний execution backend |
| Отдельные ComfyUI nodes | Primitives, не capabilities |
| Реализации Agnes | Cloud provider |
| Внутренности внешних API | Не контролируется |
| Внутренности LLM | Runtime, не core |
| Алгоритмы генерации | Принадлежат backend |
| Конкретные specialist operators | Внешние агенты (Gemma, и др.) |

### 7.3 Граница

```text
                    USER
                      │
                      ▼
              ┌───────────────┐
              │  AGENT CORE   │
              │               │
              │  Understand   │
              │  Decompose    │
              │  Plan         │
              │  Select       │
              │  Invoke       │
              │  Verify       │
              │  Learn        │
              │               │
              └───────┬───────┘
                      │
         ┌────────────┼────────────┐
         │            │            │
         ▼            ▼            ▼
    ┌─────────┐  ┌─────────┐  ┌─────────┐
    │ ComfyUI │  │  Agnes  │  │  Other  │
    │ (local) │  │ (cloud) │  │providers│
    └────┬────┘  └─────────┘  └─────────┘
         │
    ┌────┴────────────────────┐
    │  EXTERNAL ECOSYSTEM     │
    │                         │
    │  nodes/workflows        │
    │  specialist operators   │
    │  MCP tools              │
    │  models/runtimes        │
    └─────────────────────────┘
```

---

## 8. What Agent Can and Cannot Use

### 8.1 Доступно и интегрировано

| Capability | Provider | Access Point | Verification |
|------------|----------|-------------|--------------|
| image.generate | ComfyUI | ComfyClient → WorkflowEngine | SemanticVerifier |
| image.edit | ComfyUI | ComfyClient → WorkflowEngine | SemanticVerifier |
| image.upscale | ComfyUI | ComfyClient → WorkflowEngine | SemanticVerifier |
| video.generate | ComfyUI | ComfyClient → WorkflowEngine | SemanticVerifier |
| video.image_to_video | ComfyUI | ComfyClient → WorkflowEngine | SemanticVerifier |
| LLM planning | OpenRouter | LLMPlanner (HTTP) | fallback to heuristic |
| VLM verification | OpenRouter | SemanticVerifier (HTTP) | score threshold |

### 8.2 Доступно, НО НЕ интегрировано в Agent

| Capability | Provider | Access Point | Статус |
|------------|----------|-------------|--------|
| Local LLM (текст) | llama.cpp | `127.0.0.1:8080` (OpenAI-compatible) | ❌ НЕ интегрирован |
| Local VLM (vision) | llama.cpp | `127.0.0.1:8086` (OpenAI-compatible) | ❌ НЕ интегрирован |
| MCP Fetch | MCP Fetch | `127.0.0.1:9001` (SSE) | ❌ НЕ интегрирован |
| MCP Filesystem | MCP Filesystem | `127.0.0.1:9002` (SSE) | ❌ НЕ интегрирован |
| MCP Memory | MCP Memory | `127.0.0.1:9003` (SSE) | ❌ НЕ интегрирован |
| Cloud image gen | Agnes | ComfyUI workflow | ❌ Через workflow |
| Cloud video gen | Agnes | ComfyUI workflow | ❌ Через workflow |

### 8.3 НЕ установлено / НЕ доступно

| Capability | Причина |
|-----------|---------|
| comfyui-mcp (178 tools) | ❌ NOT INSTALLED |
| Gemma 4 E4B (specialist operator) | ❌ NOT INSTALLED, requires ~3.5 GB VRAM |
| SDXL / Flux checkpoints | ❌ NOT INSTALLED |

---

## 9. Open Architectural Decisions

### AD-NEW-01: What is the stable Agent core vs external capability ecosystem?

**Вопрос:** Что является стабильным ядром Agent, а что является внешней capability ecosystem, которую Agent должен уметь обнаруживать, выбирать, подключать, вызывать, проверять и запоминать?

**Варианты:**
1. **Agent = orchestration only** (текущий): Agent = Rules + WorkflowEngine + Verifier
2. **Agent = intelligence + orchestration + ecosystem management**: Agent = Understand + Plan + Select + Invoke + Verify + Learn + Discovery
3. **Agent как thin wrapper**: Agent = Minimal routing + Specialist Operators (Gemma и др.)

### AD-NEW-02: Local LLM/VLM integration

**FACT:** llama.cpp + Vulkan установлен, работает, OpenAI-compatible API.

**FACT:** Agent НЕ интегрирован. LLMPlanner настроен на недоступный fallback_proxy.

**Вопрос:** Интегрировать llama.cpp как primary LLM/VLM backend?

### AD-NEW-03: Capability discovery vs declaration

**FACT:** Текущие capabilities заданы в коде.

**Вопрос:** Автоматически обнаруживать capabilities из /object_info?

### AD-NEW-04: Specialist Operators

**FACT:** Gemma 4 E4B + comfyui-mcp может управлять ComfyUI через 178 tools.

**Вопрос:** Использовать specialist operators как part of ecosystem?

### AD-NEW-05: Verification depth

**FACT:** SemanticVerifier проверяет через OpenRouter vision.

**Вопрос:** Достаточна ли текущая верификация?

---

## 10. Impact on Existing M1–M24 Roadmap

### 10.1 Что реализовано (без изменений)

| Milestone | Компонент | Архитектурная ценность |
|-----------|----------|----------------------|
| M1 | ComfyClient | Transport |
| M2 | AssetStore | Infrastructure (assets) |
| M3 | CapabilityRegistry + WorkflowRegistry | Registry layer |
| M4 | WorkflowEngine + Verifier | Execution engine |
| M5 | Provider + ModelRegistry + BackendCatalog | Infrastructure catalog |
| M6 | Video E2E | Capability proof |
| M7 | ConversationContext | Orchestration core |
| M9 | UI (SSE + preview) | User interaction |
| M11 | Prompt Builder | Prompt enhancement |
| M13 | ExecutionHistory + Retry | Knowledge (history) |
| M14 | SemanticVerifier | Verification |
| M16 | AdaptivePlanner | Knowledge (adaptive) |
| M18 | TaskDecomposer + Chain | Orchestration (decomposition) |
| M21 | Reconciliation + Recovery | Fault tolerance |
| M22 | Human-in-the-Loop | User decision bridge |
| M24 | Feedback-Driven | Knowledge (feedback) |
| Knowledge S1 | KnowledgeCore | Knowledge (runtime discovery); Slice 2 (Agent pre-flight) — SPECD, не интегрирован |

### 10.2 Что требует архитектурного решения (PAUSED)

| Задача | Статус | Причина PAUSED |
|--------|--------|----------------|
| Persistence (S3+) | PAUSED | JSONL-based persistence достаточна, архитектурное решение не принято |
| S4 Knowledge Core (full) | PAUSED | Slice 1 реализован; Slice 2 (Agent integration) — SPECD, не интегрирован (reconciliation 2026-09-13); полный RAG не нужен до принятия решения |
| Metadata/Probe | PAUSED | Runtime discovery через /object_info работает; динамическое обнаружение — отдельное решение |
| SSE timeout fix | PAUSED | Текущая реализация достаточна |
| GPU migration | PAUSED | CPU-only для текущей задачи |
| New capabilities | PAUSED | Использовать существующие ComfyUI nodes до решения по discovery |

### 10.3 Что нужно исследовать перед реализацией

| Исследование | Вопрос | Приоритет |
|-------------|--------|-----------|
| llama.cpp integration | Интегрировать как primary LLM/VLM backend? | HIGH |
| comfyui-mcp installation | Установить 178 инструментов? | HIGH |
| Gemma 4 E4B | Работает ли на CPU? | HIGH |
| Dynamic capability discovery | Автоматическое построение capabilities? | MEDIUM |
| Cloud Provider | Прямой доступ к Agnes API? | MEDIUM |

---

## ARCHITECTURAL MODEL — DRAFT

### A1. Ontology экосистемы

```
CAPABILITY         — логическая способность (image.generate)
    │
    ├── PRIMITIVE   — технический механизм (KSampler, CLIPTextEncode)
    ├── WORKFLOW    — recipe (связка primitives)
    ├── PROVIDER    — кто предоставляет (ComfyUI, Agnes, OpenRouter)
    ├── ACCESS POINT — как обращаться (HTTP, MCP, Python)
    ├── BACKEND     — где считает (Local CPU, Remote GPU, Cloud)
    ├── RUNTIME     — модель/engine (Qwen2.5-3B, SD 1.x)
    └── SPECIALIST OPERATOR — обученный AI (Gemma 4 E4B)
```

### A2. Карта экосистемы

```
┌─────────────────────────────────────────────────────────────┐
│                    CAPABILITY LAYER                          │
│                                                             │
│  image.generate    video.generate    audio.generate          │
│  image.edit        video.i2v         LLM planning            │
│  image.upscale                       VLM verification        │
│                                                             │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────┼──────────────────────────────────┐
│                    PROVIDER LAYER                            │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ ComfyUI  │  │  Agnes   │  │ OpenRouter│  │llama.cpp │  │
│  │ (local)  │  │ (cloud)  │  │  (cloud)  │  │ (local)  │  │
│  └────┬─────┘  └──────────┘  └──────────┘  └──────────┘  │
│       │                                                     │
│  ┌────┴────────────────────────────┐                       │
│  │ ACCESS POINTS                   │                       │
│  │ HTTP API / MCP / OpenAI-compat  │                       │
│  └────┬────────────────────────────┘                       │
│       │                                                     │
│  ┌────┴────────────────────────────┐                       │
│  │ BACKENDS                        │                       │
│  │ Local CPU / Remote GPU / Cloud  │                       │
│  └─────────────────────────────────┘                       │
│                                                             │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────┼──────────────────────────────────┐
│                    AGENT CORE                                │
│                                                             │
│  Understand → Decompose → Plan → Select → Invoke            │
│       │              │            │           │              │
│       └──────────────┴────────────┴───────────┘              │
│                      │                                       │
│              Verify → Learn → Feedback                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### A3. Карта существующего Agent → Архитектурные ответственности

| Архитектурная ответственность | Существующий компонент | Статус |
|------------------------------|----------------------|--------|
| **Understand** | ConversationAgent (multi-turn context) | ✅ Core |
| **Decompose** | TaskDecomposer | ✅ Core |
| **Plan (online)** | LLMPlanner | ✅ Core (adapter) |
| **Plan (fallback)** | HeuristicPlanner | ✅ Core (fallback) |
| **Plan (adaptive)** | AdaptivePlanner | ✅ Core (decorator) |
| **Select (capability)** | CapabilityRegistry | ✅ Core (domain model) |
| **Select (workflow)** | WorkflowRegistry | ✅ Core |
| **Select (backend)** | BackendCatalog | ✅ Core |
| **Select (model)** | ModelRegistry | ✅ Core |
| **Invoke** | WorkflowEngine → ComfyUIProvider → ComfyClient | ✅ Core (execution) |
| **Verify (basic)** | Verifier | ✅ Core |
| **Verify (vision)** | SemanticVerifier | ✅ Core |
| **Learn** | ExperienceStore | ✅ Core |
| **Feedback** | FeedbackStore | ✅ Core |
| **Lineage** | AssetStore | ✅ Core |
| **Runtime discovery** | KnowledgeCore | ⚠️ Partial (duplicates ModelRegistry) |
| **LLM/VLM integration** | — | ❌ NOT INTEGRATED (llama.cpp) |
| **MCP tools** | — | ❌ NOT INTEGRATED (Fetch/FS/Memory) |
| **Specialist operators** | — | ❌ NOT INSTALLED (Gemma) |

### A4. Граница: Agent Core vs External Ecosystem

```
AGENT CORE (стабильное ядро):
  ├── Orchestration: ConversationAgent, TaskDecomposer
  ├── Planning: LLMPlanner, HeuristicPlanner, AdaptivePlanner
  ├── Registry: CapabilityRegistry, WorkflowRegistry, ModelRegistry, BackendCatalog
  ├── Execution: WorkflowEngine, ComfyUIProvider
  ├── Verification: Verifier, SemanticVerifier
  ├── Knowledge: ExperienceStore, ExecutionHistory, FeedbackStore, UserPreferences
  └── Infrastructure: AssetStore, ComfyClient

EXTERNAL ECOSYSTEM (внешние capabilities):
  ├── ComfyUI nodes (953 primitives)
  ├── ComfyUI workflows (6 recipes)
  ├── Cloud providers (Agnes, OpenRouter)
  ├── Local runtimes (llama.cpp, MCP servers)
  └── Specialist operators (Gemma 4 E4B + comfyui-mcp)
```

### A5. Таблица capabilities

| Capability | Provider | Access Point | Backend | Runtime/Model | Current Agent access | Verification | Potential reuse |
|------------|----------|-------------|---------|---------------|---------------------|--------------|----------------|
| image.generate | ComfyUI | HTTP | Local CPU | SD 1.x | ✅ ComfyClient | SemanticVerifier | Full |
| image.edit | ComfyUI | HTTP | Local CPU | SD 1.x + ControlNet | ✅ ComfyClient | SemanticVerifier | Full |
| image.upscale | ComfyUI | HTTP | Local CPU | Upscale models | ✅ ComfyClient | SemanticVerifier | Full |
| video.generate | ComfyUI | HTTP | Local/Remote | AnimateDiff | ✅ ComfyClient | SemanticVerifier | Full |
| video.image_to_video | ComfyUI | HTTP | Local CPU | — | ✅ ComfyClient | SemanticVerifier | Full |
| audio.generate | Agnes | ComfyUI workflow | Cloud | SoniloTextToMusic | ⚠️ Indirect | — | Low |
| LLM planning | OpenRouter | HTTP | Cloud | gpt-4o-mini | ✅ LLMPlanner | fallback | Partial |
| LLM planning | llama.cpp | HTTP | Local | Qwen2.5-3B | ❌ Not integrated | — | High |
| VLM verification | OpenRouter | HTTP | Cloud | gpt-4o-mini (v) | ✅ SemanticVerifier | — | Partial |
| VLM verification | llama.cpp | HTTP | Local | Qwen2.5-VL-3B | ❌ Not integrated | — | High |
| MCP Fetch | MCP Fetch | SSE | Local | — | ❌ Not integrated | — | Medium |
| MCP Filesystem | MCP Filesystem | SSE | Local | — | ❌ Not integrated | — | Medium |
| MCP Memory | MCP Memory | SSE | Local | SQLite FTS5 | ❌ Not integrated | — | Medium |
| ComfyUI control | comfyui-mcp | MCP | Local | Gemma 4 E4B | ❌ Not installed | — | High |

### A6. FACTS / INFERENCES / HYPOTHESES / OPEN DECISIONS

#### FACTS
1. ComfyUI 0.34.5 запущен, 953 ноды, 6 workflows, 7 custom nodes
2. llama.cpp + Vulkan: Qwen2.5-3B (текст, :8080), Qwen2.5-VL-3B (vision, :8086)
3. MCP servers: Fetch:9001, Filesystem:9002, Memory:9003
4. Agent M1-M24 fully implemented, 36 tests pass
5. LLMPlanner → fallback_proxy (недоступен), SemanticVerifier → OpenRouter (cloud)
6. Gemma 4 E4B + comfyui-mcp: 178 tools, NOT INSTALLED
7. 2 SD 1.x checkpoints, no SDXL/Flux

#### INFERENCES
1. Agent NOT integrated with local LLM/VLM (llama.cpp)
2. ComfyUI-internal LLM/VLM nodes installed but unused by Agent
3. KnowledgeCore duplicates runtime discovery with ModelRegistry
4. Agnes accessible only through ComfyUI workflow (single point of failure)
5. Gemma 4 E4B can be specialist operator for ComfyUI

#### HYPOTHESES
1. llama.cpp can replace OpenRouter for planning/verification
2. Dynamic capability discovery from /object_info
3. Gemma 4 E4B + comfyui-mcp can replace WorkflowEngine for ComfyUI
4. Hybrid architecture (code + LLM orchestration) is optimal

#### OPEN DECISIONS
1. **AD-NEW-01:** What is stable Agent core vs external ecosystem?
2. **AD-NEW-02:** Local LLM/VLM integration (llama.cpp)
3. **AD-NEW-03:** Capability discovery vs declaration
4. **AD-NEW-04:** Specialist operators (Gemma)
5. **AD-NEW-05:** Verification depth

---

### A7. Архитектурные решения, необходимые перед следующей реализацией

| # | Решение | Описание | Impact |
|---|---------|----------|--------|
| **1** | **Agent Core boundary** | Определить, что является стабильным ядром Agent, а что — внешней ecosystem | Определяет всю дальнейшую архитектуру |
| **2** | **Local LLM/VLM integration** | Интегрировать llama.cpp как primary/fallback backend для planning и verification | Убирает зависимость от cloud API |
| **3** | **Capability discovery strategy** | Dynamic (из /object_info) vs declared (manifests) vs hybrid | Определяет расширяемость |
| **4** | **Specialist Operators role** | Использовать ли Gemma/comfyui-mcp как part of ecosystem | Определяет boundary Agent vs external |
| **5** | **Multi-provider routing** | Как выбирать между local ComfyUI, cloud Agnes, llama.cpp, OpenRouter | Определяет гибкость |

---

*Документ создан как архитектурное исследование. Production code НЕ изменяется. Gemma НЕ устанавливается. llama.cpp НЕ подключается. Новые сервисы НЕ создаются.*
