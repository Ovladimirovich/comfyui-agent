# Comfy Desktop Agent Audit

## Executive Summary

**Ключевой вывод:** В Comfy Desktop нет встроенного Agent. То, что пользователь видит как «вкладку Agent» — это **comfyui-agent-panel** (также `comfyui-mcp-panel`), сторонний custom node, который является **UI-фронтендом для внешнего MCP-оркестратора**. Сам оркестратор работает **вне ComfyUI** — это отдельный процесс, запущенный через `npx -y comfyui-mcp --panel-orchestrator`, который подключается к ComfyUI через loopback WebSocket-мост.

**Это НЕ часть ComfyUI/Comfy Desktop.** Это независимый проект с GitHub-репозиторием `artokun/comfyui-mcp-panel`. Он устанавливается как отдельный custom node и требует отдельного CLI-оркестратора.

**Для нашего Agent Core:** Встроенный Comfy Agent — это **только UI-интерфейс**, не мозги. Наш Agent Core может остаться главным мозгом. Встроенный Agent можно использовать как дополнительный интерфейс, но не как замену.

---

## Где реализован Comfy Agent

### Фактические пути файлов

| Компонент | Путь | Роль |
|-----------|------|------|
| **Custom node pack** | `custom_nodes/comfyui-agent-panel/` | Custom node, зарегистрированный в ComfyUI |
| **Backend (`__init__.py`)** | `custom_nodes/comfyui-agent-panel/__init__.py` | Регистрация веб-директории, API для probe состояния оркестратора, launcher proxy |
| **Python API routes** | `custom_nodes/comfyui-agent-panel/py/apps_routes.py` | API для хранения/запуска «apps» (упакованных workflow) |
| **Python API routes** | `custom_nodes/comfyui-agent-panel/py/training_routes.py` | API для training UI |
| **Python API routes** | `custom_nodes/comfyui-agent-panel/py/civitai_proxy.py` | Прокси для CivitAI |
| **Frontend (JS)** | `custom_nodes/comfyui-agent-panel/web/js/comfyui-mcp-panel.js` | Главный файл панели (~50K+ строк) |
| **Frontend (JS)** | `custom_nodes/comfyui-agent-panel/web/js/cmcp-a2ui.js` | A2UI-компоненты (карточки от агента) |
| **Frontend (JS)** | `custom_nodes/comfyui-agent-panel/web/js/cmcp-sidepanel-ui.js` | UI сайдбара |
| **Frontend (JS)** | `custom_nodes/comfyui-agent-panel/web/js/cmcp-apps.js` | Apps UI |
| **Frontend (JS)** | `custom_nodes/comfyui-agent-panel/web/js/cmcp-civitai.js` | CivitAI UI |
| **Frontend (JS)** | `custom_nodes/comfyui-agent-panel/web/js/cmcp-training.js` | Training UI |
| **Frontend (JS)** | `custom_nodes/comfyui-agent-panel/web/js/cmcp-modal.js` | Modal dialogs |
| **Frontend (JS)** | `custom_nodes/comfyui-agent-panel/web/js/cmcp-filter.js` | Фильтрация сообщений |
| **Frontend (JS)** | `custom_nodes/comfyui-agent-panel/web/js/cmcp-runpod.js` | RunPod UI |
| **Frontend (JS)** | `custom_nodes/comfyui-agent-panel/web/js/cmcp-a2ui-lit-adapter.js` | A2UI ↔ Lit адаптер |
| **Frontend (lib)** | `custom_nodes/comfyui-agent-panel/web/js/lib/*.js` | ~80+ модулей библиотек (chat history, widget manipulation, graph mutation, reconnect, etc.) |
| **Config** | `custom_nodes/comfyui-agent-panel/pyproject.toml` | package.json, pyproject.toml — зависимости, metadata |
| **Docs** | `custom_nodes/comfyui-agent-panel/docs/` | Документация панели |

### package.json ключевые данные

```json
{
  "name": "comfyui-agent-panel",
  "version": "0.15.179",
  "description": "Autonomous AI agent in the ComfyUI sidebar - local-first, bring any LLM.",
  "dependencies": ["comfyui-frontend-package>=1.20.0"],
  "Repository": "https://github.com/artokun/comfyui-mcp-panel"
}
```

### Backend (`__init__.py`) — что он реально делает

1. **Служит JS-файлы** через `WEB_DIRECTORY = "./web"`
2. **Probe orchestrator**: проверяет, запущен ли MCP-оркестратор на loopback-порту 9199 (fallback 9180)
3. **Provider detection**: проверяет наличие CLI бинарников (Claude, Codex, Gemini, Ollama, Antigravity, pi, Grok, Qwen, Kimi, etc.)
4. **Launcher proxy**: проксирует 3 команды к companion launcher (`~/.comfyui-mcp/launcher.json`)
5. **Никогда не запускает процессы** — Comfy Registry security standards запрещают
6. **Обнаруживает ComfyUI URL** из `comfy.cli_args`

### НЕТ Python-агента в ComfyUI

В `custom_nodes/comfyui-agent-panel/` **нет** Python-файлов, реализующих логику агента. Весь «интеллект» находится в **внешнем** `comfyui-mcp` оркестраторе, который:
- Запускается отдельно: `npx -y comfyui-mcp --panel-orchestrator`
- Работает на Node.js
- Подключается к LLM-провайдерам (Claude, Codex, Gemini и др.)
- Коммуницирует с ComfyUI через loopback WebSocket

---

## Архитектура

### Реальная схема

```
┌───────────────────────────────────────────────────────────────┐
│                    Comfy Desktop / ComfyUI                     │
│                                                               │
│  ┌─────────────────────────┐    ┌──────────────────────────┐  │
│  │  ComfyUI Core           │    │  comfyui-agent-panel     │  │
│  │  (LiteGraph, Execution) │    │  (custom node)           │  │
│  │                         │    │                          │  │
│  │  /prompt, /history      │◄──►│  comfyui-mcp-panel.js    │  │
│  │  /object_info           │    │  (JS frontend, ~50K строк)│ │
│  │  /queue                 │    │                          │  │
│  └───────────┬─────────────┘    │  registerExtension()     │  │
│              │                   │  registerSidebarTab()    │  │
│              │                   └──────────┬───────────────┘  │
│              │                              │                  │
│              │                   ws://127.0.0.1:9199           │
│              │                   (loopback bridge)             │
│              │                                              │
└──────────────┼──────────────────────────────────────────────┘
               │
               │
    ┌──────────▼──────────┐
    │  Внешний процесс     │
    │  comfyui-mcp         │
    │  (Node.js)           │
    │                      │
    │  ┌────────────────┐  │
    │  │ Agent SDK      │  │
    │  │ (Claude/Codex/ │  │
    │  │  Gemini session)│ │
    │  └────────────────┘  │
    │                      │
    │  Loopback bridge     │
    │  WebSocket server    │
    │  Port 9199           │
    └──────────┬───────────┘
               │
    ┌──────────▼──────────┐
    │  LLM Provider       │
    │  (Claude, Codex,    │
    │   Gemini, Ollama...) │
    └─────────────────────┘
```

### Ключевые компоненты

| Компонент | Расположение | Описание |
|-----------|-------------|----------|
| **UI** | `web/js/comfyui-mcp-panel.js` | ComfyUI Extension API (`registerExtension`, `registerSidebarTab`) |
| **Bridge** | Внешний процесс `comfyui-mcp` | Loopback WebSocket server (port 9199) |
| **Agent** | Внешний процесс `comfyui-mcp` | Agent SDK session (Claude Subscription / Codex / Gemini / Ollama) |
| **Graph mutation** | `web/js/comfyui-mcp-panel.js` | Прямая манипуляция `app.graph` / `LiteGraph` через GRAPH_TOOL_EXECUTORS |
| **Apps storage** | `py/apps_routes.py` | REST API на `folder_paths` user dir |
| **Orchestrator** | `npx -y comfyui-mcp` | Node.js процесс, запускается пользователем |

### Графические инструменты (GRAPH_TOOL_EXECUTORS)

Фронтенд содержит ~60+ executor-функций для прямой манипуляции графом:

```javascript
const GRAPH_TOOL_EXECUTORS = {
  // Image/data reads
  fetch_image(args) { ... },
  fetch_comfyui_read(args) { ... },
  
  // Node definition management
  refresh_nodes() { ... },
  
  // Graph state
  graph_serialize() { ... },
  graph_configure_app_mode(args) { ... },
  graph_get_virtual_types() { ... },
  graph_get_state() { ... },
  graph_view_selected() { ... },
  graph_view_nodes_in_viewport(args) { ... },
  graph_outline(args) { ... },
  graph_query(args) { ... },
  graph_find_nodes(args) { ... },
  graph_get_subgraph(args) { ... },
  
  // Node CRUD
  graph_remove_node(args) { ... },
  graph_clear() { ... },
  graph_connect(args) { ... },
  graph_disconnect(args) { ... },
  graph_set_widget(args) { ... },
  graph_set_node_property(args) { ... },
  graph_edit_node(args) { ... },
  graph_move_node(args) { ... },
  graph_resize_node(args) { ... },
  graph_set_title(args) { ... },
  graph_set_node_collapsed(args) { ... },
  graph_set_node_color(args) { ... },
  
  // Layout
  graph_auto_layout() { ... },
  graph_canvas(args) { ... },
  graph_select_nodes(args) { ... },
  
  // Subgraphs
  graph_create_subgraph(args) { ... },
  graph_subgraph_group(args) { ... },
  graph_expose_subgraph_output(args) { ... },
  graph_expose_subgraph_input(args) { ... },
  graph_unexpose_subgraph_output(args) { ... },
  graph_unexpose_subgraph_input(args) { ... },
  graph_copy_nodes(args) { ... },
  graph_paste_nodes(args) { ... },
  graph_list_subgraphs(args) { ... },
  graph_add_subgraph(args) { ... },
  
  // Groups
  graph_create_group(args) { ... },
  graph_move_group(args) { ... },
  graph_edit_group(args) { ... },
  graph_remove_group(args) { ... },
  
  // Node mode
  graph_set_node_mode(args) { ... },
  
  // Screenshot
  graph_screenshot(args) { ... },
  
  // Rail
  graph_move_rail(args) { ... },
  
  // Widget promotion
  graph_promote_widget(args) { ... },
  
  // App management
  workflow_live_sync(args) { ... },
  workflow_open(args) { ... },
  workflow_rename(args) { ... },
  workflow_close(args) { ... },
  
  // Execution
  graph_run(args) { ... },
  
  // System
  comfy_reboot(args) { ... },
  graph_get_errors() { ... },
  graph_update_node(args) { ... },
  graph_load(args) { ... },
};
```

### Слэш-команды (SLASH_COMMANDS)

```javascript
const SLASH_COMMANDS = [
  { cmd: "/new" },        // Новый чат
  { cmd: "/fit" },        // Fit canvas
  { cmd: "/run" },        // Запустить workflow
  { cmd: "/reload" },     // Soft reload (new code, keeps chat)
  { cmd: "/reload-ui" },  // Reload UI only
  { cmd: "/restart" },    // Restart agent backend
  { cmd: "/revert" },     // Undo последнего хода
  { cmd: "/errors" },     // Показать ошибки выполнения
  { cmd: "/record-skill" }, // Записать граф как навык
  { cmd: "/docs" },       // Открыть документацию
  { cmd: "/help" },       // Список команд
];
```

---

## Возможности (фактические, по коду)

### A. Что Agent реально умеет

| Возможность | Статус | Доказательство в коде |
|-------------|--------|----------------------|
| Принимает текстовый запрос | **ДА** | `comfyui-mcp-panel.js` — пользовательский ввод передаётся через WebSocket к bridge |
| Multi-turn dialogue | **ДА** | `chat-history-store.js` — `ChatHistoryStore` хранит историю сессий, `selectThreadForScope` |
| Clarification | **ДА** | Команда `ask_user` в executor dispatch (`msg.cmd === "ask_user"`) |
| Строит план | **НЕТ** | Планирование — во внешнем LLM-процессе, не в ComfyUI. Никакого Planner в нашем коде |
| Создаёт/изменяет workflow | **ДА** | 60+ GRAPH_TOOL_EXECUTORS — прямая манипуляция LiteGraph |
| Работает с nodes | **ДА** | `graph_add_node`, `graph_edit_node`, `graph_set_widget`, `graph_connect`, `graph_remove_node` и т.д. |
| Запускает workflow | **ДА** | `graph_run` executor + `workflow_live_sync` |
| Отслеживает execution | **ДА** | `/queue`, `/history` polling через API |
| Получает результаты | **ДА** | `graph_get_errors`, обработка outputs из `/history` |
| Работает с изображениями | **ДА** | `isAllowedImageSrc`, `fetchImageForMcp`, `graph_screenshot`, A2UI Image component |
| Работает с видео | **ЧАСТИЧНО** | `ltx-director.js` — LTX timeline manipulation |
| Работает с аудио | **НЕТ** | Нет аудио-специфичных модулей |
| Внешние tools | **НЕТ** | Нет tool registry, нет function calling |
| Вызывает LLM/VLM | **НЕТ** (в ComfyUI) | LLM вызовы — во внешнем `comfyui-mcp` процессе |
| Memory | **НЕТ** | Нет persistent memory, только chat history |
| History | **ДА** | `chat-history-store.js` — `ChatHistoryStore`, `CHART_HISTORY_MAX_IMPORT_BYTES`, threads |
| Verification | **НЕТ** | Нет semantic verifier, нет проверки результата |
| Retry/recovery | **ЧАСТИЧНО** | `reconnect-recovery.js`, `object-info-retry.js` — retry при reconnect |
| Provider/backend routing | **ДА** | `_backend_status()`, multi-provider: Claude, Codex, Gemini, Ollama, Antigravity, pi, Grok, Qwen, Kimi, Moonshot, GLM, MiniMax |

### B. A2UI (Agent-to-UI) компоненты

Agent может отправлять структурированные карточки:

```javascript
export const A2UI_CAPS = {
  maxComponents: 64,
  maxDepth: 8,
  maxGraphNodes: 30,
  maxGraphEdges: 60,
  maxChartSeries: 8,
  maxChartPoints: 256,
  maxSelectOptions: 24,
  maxImages: 4,
  maxTextLen: 2000,
  maxLabelLen: 200,
};

// Поддерживаемые типы:
// Text, Heading, Button, Row, Column, Card, Divider,
// Image, TextField, Select, Checkbox,
// comfy:graph (node graph visualization), comfy:chart (bar/line)
```

---

## MCP (Model Context Protocol)

### Критический вывод: comfyui-agent-panel = UI для comfy-mcp

**comfyui-mcp** — это **НЕ часть ComfyUI**. Это отдельный Node.js пакет:

```bash
npx -y comfyui-mcp --panel-orchestrator
npx -y comfyui-mcp@latest connect
pip install comfy-mcp && claude mcp add comfy-mcp
```

### Является ли MCP обязательным?

**ДА, для этого Agent.** Без запущенного `comfyui-mcp` процесса:
- Panel показывает статус `running: false`
- Panel показывает команду для запуска
- Никакой агентский функционал недоступен
- Это не «упрощённый режим» — это **нет агента вообще**

### Является ли MCP только способом доступа к ComfyUI?

**ДА.** MCP — это транспорт/мост между LLM-сессией (Claude/Codex/Gemini) и ComfyUI. Он:
- Предоставляет tools для работы с ComfyUI (graph manipulation, execution, etc.)
- Работает по WebSocket на loopback
- Не модифицирует ComfyUI

### Есть ли собственный MCP server?

**НЕТ.** `comfyui-mcp` — это **MCP client** (orchestrator), а не server. Он:
- Подключается к LLM (Claude/Codex/Gemini как MCP server/provider)
- Подключается к ComfyUI через WebSocket bridge
- Коммуницирует с panel через loopback WebSocket

### Какие tools он предоставляет?

Tools отражают `GRAPH_TOOL_EXECUTORS`:
- `graph_add_node`, `graph_edit_node`, `graph_set_widget`, `graph_connect`, `graph_disconnect`
- `graph_run`, `graph_clear`, `graph_get_state`, `graph_serialize`
- `graph_query`, `graph_find_nodes`, `graph_get_subgraph`
- `workflow_open`, `workflow_live_sync`, `workflow_rename`
- `graph_auto_layout`, `graph_screenshot`
- `graph_create_subgraph`, `graph_subgraph_group`
- `graph_copy_nodes`, `graph_paste_nodes`
- `graph_remove_node`, `graph_disconnect`
- `refresh_nodes`, `fetch_image`
- И многое другое

### Может ли Agent работать без MCP?

**НЕТ.** Без MCP-оркестратора:
- Panel существует, но показывает «not running»
- Все agent-команды блокируются
- Panel — только UI для MCP

### Что делает `pip install comfy-mcp && claude mcp add comfy-mcp`?

Это **внешний** сценарий: пользователь добавляет ComfyUI как MCP server в Claude Desktop. Это **не связано** с `comfyui-mcp-panel`. Это позволяет Claude Desktop напрямую управлять ComfyUI через MCP protocol.

### Отличается ли встроенный Agent от внешнего через MCP?

**ДА.** Это два разных пути:

| | Panel в ComfyUI | Claude Desktop через MCP |
|---|---|---|
| Где запущен | Внутри ComfyUI sidebar | Вне ComfyUI (Claude Desktop) |
| Transport | Loopback WebSocket (9199) | MCP JSON-RPC |
| Agent | Claude SDK session (background) | Claude Desktop (interactive) |
| Graph mutation | Прямая JS манипуляция | Через MCP tools |
| Целевой пользователь | Пользователь ComfyUI | Пользователь Claude Desktop |

---

## API / Integration Points

### Существующие HTTP API (проверено в коде)

| Endpoint | Method | Описание | Статус |
|----------|--------|----------|--------|
| `/comfyui_mcp_panel/apps` | GET | List app bundles | **Существует** |
| `/comfyui_mcp_panel/apps` | POST | Create app bundle | **Существует** |
| `/comfyui_mcp_panel/apps/{id}` | GET | Get app manifest | **Существует** |
| `/comfyui_mcp_panel/apps/{id}` | PUT | Update app | **Существует** |
| `/comfyui_mcp_panel/apps/{id}` | DELETE | Remove app | **Существует** |
| `/comfyui_mcp_panel/apps/{id}/run` | POST | Patch + queue prompt | **Существует** |
| `/comfyui_mcp_panel/apps/{id}/runs/{prompt_id}` | GET | Run status + outputs | **Существует** |
| `/comfyui_mcp_panel/apps/{id}/bundle` | GET | Full bundle (manifest+prompt+workflow) | **Существует** |
| `/comfyui_mcp_panel/apps/{id}/thumbnail` | GET | Serve thumbnail | **Существует** |
| `/comfyui_mcp_panel/launcher/status` | GET | Launcher status (origin-guarded) | **Существует** |
| `/comfyui_mcp_panel/launcher/start` | POST | Start launcher (origin-guarded) | **Существует** |
| `/comfyui_mcp_panel/launcher/handshake` | POST | Handshake complete (origin-guarded) | **Существует** |
| `/comfyui_mcp_panel/status` | GET | Orchestrator status probe | **Существует** |
| `/comfyui_mcp_panel/advertise_bridge` | POST | Store bridge URL | **Существует** |

### WebSocket Transport

| Транспорт | Описание | Статус |
|-----------|----------|--------|
| Loopback WS (9199) | Panel ↔ Orchestrator | **Существует** |
| Legacy WS (9180) | Panel ↔ Orchestrator (fallback) | **Существует** |
| Remote WSS | Tunnel (cloudflared) для удалённых подключений | **Существует** |

### Frontend Extension API

| API | Описание | Статус |
|-----|----------|--------|
| `app.registerExtension()` | Регистрация custom extension | **Существует** |
| `app.extensionManager.registerSidebarTab()` | Регистрация sidebar tab | **Существует** |
| `app.graph` | Прямой доступ к LiteGraph | **Существует** |
| `api.fetchApi()` | ComfyUI API fetch | **Существует** |
| `LiteGraph` | Прямой доступ к LiteGraph | **Существует** |

### Extension Points (что мы можем использовать)

| Точка | Статус | Комментарий |
|-------|--------|-------------|
| ComfyUI Extension API | **Существует** | `registerExtension`, `registerSidebarTab` |
| ComfyUI Frontend API | **Существует** | `app.graph`, `api.fetchApi` |
| ComfyUI Backend API | **Существует** | `/prompt`, `/queue`, `/history`, `/object_info` |
| WebSocket API | **Существует** | Стандартный ComfyUI WS |
| Custom Node Plugin API | **Существует** | `NODE_CLASS_MAPPINGS`, `WEB_DIRECTORY` |
| Agent API (встроенный) | **НЕ СУЩЕСТВУЕТ** | Встроенного Agent API нет — agent — внешний процесс |
| MCP API | **Существует** (внешний) | Только через `comfyui-mcp` |
| Hooks/Events | **НЕ СУЩЕСТВУЕТ** | Нет публичных hook-систем для агентов |
| Plugin API | **Существует** | Custom nodes + frontend extensions |

---

## UI

### Что показывает Comfy Agent Panel

1. **Chat sidebar** — multi-turn диалог с агентом
2. **A2UI Cards** — карточки от агента: текст, кнопки, изображения, поля ввода, графики, node graphs
3. **CivitAI pane** — поиск и просмотр моделей с CivitAI
4. **Training pane** — UI для training
5. **Apps pane** — управление упакованными workflow
6. **Slash commands** — `/new`, `/run`, `/fit`, `/reload`, `/restart`, `/revert`, `/errors`, `/record-skill`, `/docs`, `/help`

### Что панель НЕ показывает

- Нет internal planner state
- Нет capability graph
- Нет evidence/knowledge store
- Нет verification results
- Нет asset lineage
- Нет retry/recovery UI
- Нет backend routing UI (выбор бэкенда — в onboarding)

---

## State / Events

### State management (по коду)

| Компонент | Где хранится | Описание |
|-----------|-------------|----------|
| Chat history | `chat-history-store.js` | `ChatHistoryStore`, IndexedDB/localStorage, threads |
| Graph state | `app.graph` (LiteGraph) | Прямая манипуляция через GRAPH_TOOL_EXECUTORS |
| Workflow identity | `workflow-chat-identity.js` | UUID, path, grounding |
| Graph snapshot | `graph-revert.js` | Снимки для `/revert` |
| Session state | Orchestrator (внешний) | Agent SDK session |
| Provider state | `__init__.py` (Python) | Probe CLI + auth для каждого провайдера |

### Events

| Событие | Статус |
|---------|--------|
| `beforeChange` / `afterChange` | **Существует** — graph mutations wrapped |
| Reconnect events | **Существует** — `reconnect-recovery.js` |
| Workflow open events | **Существует** — `workflow-open-readiness` |
| Node def refresh | **Существует** — `refresh_nodes`, coalescer |
| Download completion | **Существует** — `download-refresh.js` |
| Agent message | **Существует** — `say` type messages |
| User message | **Существует** — `user_message` type |
| System events | **Существует** — `set_todo`, `show_media`, `soft_reload` |

---

## Workflow Interaction

### Как Agent взаимодействует с workflow

1. **Чтение**: `graph_serialize()`, `graph_get_state()`, `graph_outline()`, `graph_query()`
2. **Модификация**: `graph_add_node()`, `graph_edit_node()`, `graph_set_widget()`, `graph_connect()`, `graph_disconnect()`
3. **Запуск**: `graph_run()` → `api.fetchApi('/prompt', ...)`
4. **Сохранение**: `workflow_live_sync()`, `workflow_rename()`, `workflow_close()`
5. **Загрузка**: `graph_load()`
6. **Undo**: `revertGraphToLastSnapshot()` — снимки делаются перед каждым ходом
7. **Subgraphs**: `graph_create_subgraph()`, `graph_expose_subgraph_output()`, `graph_expose_subgraph_input()`
8. **Auto-layout**: `graph_auto_layout()`

### Все графические изменения обернуты в `beforeChange`/`afterChange`

```javascript
// Из всех GRAPH_TOOL_EXECUTORS — graph mutations wrapped in
// beforeChange/afterChange so ComfyUI's native Ctrl+Z undoes
// agent edits exactly like the user's own.
```

---

## Execution Interaction

### Запуск workflow

```javascript
// graph_run executor
await GRAPH_TOOL_EXECUTORS.graph_run({ ... })
```

### Отслеживание выполнения

- Poll `/queue` — `queue_running`, `queue_pending`
- Poll `/history/{prompt_id}` — результаты выполнения
- `graph_get_errors` — ошибки последнего выполнения

### Status tracking для Apps

```python
# py/apps_routes.py
status_str = (
    "done" if entry is not None else
    ("running" if running else
    ("pending" if pending else "unknown"))
)
```

---

## Comfy Agent vs Наш Agent Core

### Сравнительная таблица

| Область | Comfy Agent Panel | Наш Agent Core |
|---------|-------------------|----------------|
| **Conversation** | ✅ Multi-turn, threads, chat history | ✅ Full conversation management |
| **Planner** | ❌ Нет. Планирование — во внешнем LLM | ✅ `planner/` — adaptive, capability_graph, decomposer, composer, heuristic, LLM, plan, preferences |
| **Capability** | ❌ Нет. Зависит от LLM | ✅ `registry/capability.py`, `planner/capability_graph.py` |
| **Workflow** | ✅ Прямая манипуляция LiteGraph | ✅ `WorkflowEngine` + `provider/comfyui.py` |
| **Execution** | ✅ Запуск + отслеживание через API | ✅ `engine/job.py`, `engine/websocket.py` |
| **Verification** | ❌ Нет | ✅ `engine/verifier.py`, `engine/semantic_verifier.py` |
| **Memory** | ❌ Нет. Только chat history | ✅ `context/persistence.py`, `knowledge/` |
| **Feedback** | ❌ Нет | ✅ `context/feedback.py`, `engine/experience.py` |
| **Retry/Recovery** | Частично (reconnect) | ✅ `engine/retry.py`, `engine/chain.py` |
| **Backend routing** | ✅ Multi-provider (Claude, Codex, Gemini...) | ❌ ComfyUI only |
| **Asset/Lineage** | ❌ Нет | ✅ `app/assets/` — store, types |
| **UI** | ✅ Sidebar panel (ComfyUI built-in) | ✅ `app/ui.py` + `agent_ui/` |
| **MCP** | ✅ Ядро системы (comfyui-mcp) | ❌ Нет |
| **Knowledge** | ❌ Нет | ✅ `knowledge/` — research, node_doc, node_schema, evidence_store, claims_persistence |
| **Prompt building** | ❌ Нет | ✅ `prompt/` — builder, composite, heuristic, LLM, templates |
| **Infrastructure** | ❌ Нет | ✅ `infrastructure/comfy_cli_adapter.py` |
| **Resource management** | ❌ Нет | ✅ `resource/` — gateway, models, reconciler |
| **Registry** | ❌ Нет | ✅ `registry/` — backends, model, semver, workflow, selection |

### Пересечения и дублирование

| Элемент | Comfy Agent | Наш Core | Вывод |
|---------|-------------|----------|-------|
| Chat UI | ✅ | ✅ | **Дублирование** — но Comfy Agent — sidebar, наш — отдельный UI |
| Graph manipulation | ✅ | ✅ | **Дублирование** — но разные подходы (прямой LiteGraph vs WorkflowEngine) |
| Execution | ✅ | ✅ | **Дублирование** — оба используют `/prompt`, `/queue`, `/history` |
| Workflow management | ✅ | ✅ | **Дублирование** — Comfy Agent делает через JS, наш через Python |
| Multi-provider | ✅ | ❌ | **Уникальная фича Comfy Agent** |
| Planner | ❌ | ✅ | **Уникальная фича нашего Core** |
| Verification | ❌ | ✅ | **Уникальная фича нашего Core** |
| Knowledge | ❌ | ✅ | **Уникальная фича нашего Core** |
| Feedback | ❌ | ✅ | **Уникальная фича нашего Core** |

---

## Возможные варианты интеграции

### Вариант 1: Comfy Agent UI → Наш Agent Core → ComfyUI

```
Comfy Agent UI → [bridge?] → Наш Agent Core → WorkflowEngine → ComfyUI
```

**Статус: ЧАСТИЧНО ВОЗМОЖНО**

**Проблемы:**
- Comfy Agent UI ждёт WebSocket на loopback 9199 с MCP-протоколом
- Наш Agent Core использует собственный WebSocket (`engine/websocket.py`)
- Протоколы несовместимы
- Для интеграции нужен **adapter/bridge** между Comfy Agent WS-протоколом и нашим Core API

**Что нужно:**
1. Создать adapter, который транслирует MCP-команды в вызовы нашего Agent Core
2. Или изменить наш Core для поддержки MCP-протокола
3. Или создать proxy, который принимает команды от Comfy Agent UI и перенаправляет их в наш Core

### Вариант 2: Наш Agent Core → ComfyUI + Comfy Agent UI как доп. интерфейс

```
Наш Agent Core ↓
  ComfyUI ↑
Comfy Agent UI ↑ (только UI, без логики)
```

**Статус: ТЕХНИЧЕСКИ ВОЗМОЖНО, но с оговорками**

**Подход:**
- Наш Core остаётся главным мозгом
- Comfy Agent UI используется как **дополнительный** UI-интерфейс
- Команды от Comfy Agent UI интерпретируются и перенаправляются в наш Core
- Comfy Agent UI может работать в режиме «только просмотр» + «базовые команды»

**Ограничения:**
- Comfy Agent UI заточен под внешний LLM-агент, не под наш Core
- Многие команды (plan, clarify, verify) не имеют смысла без LLM-агента
- Нужна тонкая настройка, что Comfy Agent UI может делать, а что — нет

### Вариант 3: Полный отказ от Comfy Agent UI

```
Наш Agent Core → Наш Operator UI → ComfyUI
```

**Статус: РЕКОМЕНДУЕМО**

- Наш Core уже имеет полноценный UI (`agent_ui/`)
- Наш UI покрывает все нужные области (conversation, plan, verification, feedback, etc.)
- Comfy Agent UI — это UI для внешнего LLM, не для нашего Core
- Двойной UI создаёт путаницу и поддержку

---

## Что НЕ стоит делать

1. **НЕ использовать Comfy Agent как UI для нашего Core** — протоколы несовместимы, adapter будет слишком сложным
2. **НЕ дублировать функциональность** — Comfy Agent уже умеет basic graph manipulation, но мы не должны строить поверх него
3. **НЕ зависеть от `comfyui-mcp`** — это внешний процесс, его нет в нашей архитектуре
4. **НЕ копировать A2UI** — это специфичный формат карточек, не нужный для нашего Operator UI
5. **НЕ использовать Comfy Agent UI как основной интерфейс** — он заточен под LLM-агент, не под наш Core

---

## Архитектурные выводы

### Вывод 1: Comfy Agent — это НЕ встроенный Agent

Comfy Desktop / ComfyUI **не имеет встроенного Agent**. То, что пользователь видит как «Agent» — это:
1. **comfyui-agent-panel** — сторонний custom node (GitHub: artokun/comfyui-mcp-panel)
2. **comfyui-mcp** — внешний Node.js процесс, запускаемый пользователем
3. **LLM Provider** — Claude/Codex/Gemini/Ollama, к которому подключается comfyui-mcp

Это **три независимых компонента**, ни один из которых не является частью ComfyUI.

### Вывод 2: Comfy Agent — это UI-оболочка, не мозги

В ComfyUI:
- Нет Python-агента
- Нет Planner
- Нет Verification
- Нет Memory (кроме chat history)
- Нет Knowledge store
- Нет Feedback system

Всё это — во внешнем LLM-процессе (Claude/Codex/Gemini).

### Вывод 3: Наш Core значительно богаче

Наш Agent Core имеет:
- Полноценный Planner (adaptive, capability_graph, decomposer, composer, heuristic)
- Verification (semantic verifier)
- Knowledge system (research, node_doc, evidence_store, claims)
- Feedback system
- Asset/Lineage tracking
- Prompt building system
- Resource management
- Registry (model, semver, workflow, selection)

Comfy Agent Panel имеет:
- Chat UI
- Graph manipulation tools
- Multi-provider detection (Claude, Codex, Gemini, Ollama, etc.)
- A2UI cards
- Apps management
- CivitAI integration

### Вывод 4: Прямая интеграция невозможна без adapter

Протоколы несовместимы:
- Comfy Agent использует MCP WebSocket на loopback 9199
- Наш Core использует собственный WebSocket
- Нет общего интерфейса
- Adapter будет сложнее, чем самостоятельный UI

---

## Recommendation

### A — Использовать

1. **IDEЮ sidebar tab** — Comfy Agent показывает, что sidebar tab в ComfyUI — стандартный паттерн. Наш Operator UI может использовать тот же `registerSidebarTab()`.
2. **IDEЮ graph snapshot + revert** — механизм снимков графа перед каждым ходом и отката назад (`revertGraphToLastSnapshot`) полезен для нашего Core.
3. **IDEЮ beforeChange/afterChange wrapping** — все графические изменения должны быть undo-able через Ctrl+Z.
4. **IDEЮ multi-provider detection** — если мы захотим поддерживать несколько LLM-бэкэндов, паттерн detection CLI + auth is good.
5. **IDEЮ A2UI card system** — для структурированного вывода от агента (карточки с кнопками, графиками, изображениями).

### B — Не использовать

1. **НЕ использовать Comfy Agent UI как наш UI** — протоколы несовместимы, семантика другая
2. **НЕ использовать comfyui-mcp как часть архитектуры** — внешний процесс, не наш
3. **НЕ копировать graph manipulation напрямую** — у нас есть WorkflowEngine, который уже решает эти задачи более структурированно
4. **НЕ использовать A2UI для нашего UI** — это специфичный формат, заточенный под LLM-агент, не под наш Operator UI
5. **НЕ полагаться на Comfy Registry security standards** — они ограничивают наши возможности (нельзя запускать процессы)

### C — Требует архитектурного решения

1. **Можно ли наш Core сделать совместимым с MCP?**
   - Если да, то Comfy Agent UI может работать с нашим Core через MCP
   - Это потребует реализации MCP server в нашем Core
   - Решение: требует обсуждения с архитектором

2. **Нужен ли нам sidebar tab в ComfyUI?**
   - Или наш Operator UI полностью самостоятелен?
   - Если sidebar — то можно использовать паттерн Comfy Agent
   - Решение: требует обсуждения с дизайнером UI

3. **Можно ли использовать `registerSidebarTab()` для нашего UI?**
   - Да, технически возможно
   - Но тогда наш Core должен работать внутри ComfyUI context
   - Решение: требует обсуждения с архитектором

4. **Двойной UI — хорошо или плохо?**
   - Наш Operator UI + Comfy Agent UI — это два разных UI для одного Core
   - Риск: путаница, дублирование, сложность поддержки
   - Решение: требует обсуждения с продуктовой командой

---

## Финальные три вывода

### A — Использовать

- **Паттерн sidebar tab** в ComfyUI (`registerSidebarTab`) — это стандартный способ показать дополнительный UI
- **Механизм graph snapshot + revert** — снимки графа перед ходом, откат назад
- **Wrapping graph mutations в beforeChange/afterChange** — для Ctrl+Z совместимости
- **IDEю A2UI cards** — для структурированного вывода агента (если решим использовать)

### B — Не использовать

- **Comfy Agent UI как наш интерфейс** — протоколы несовместимы, семантика другая
- **comfyui-mcp как часть архитектуры** — внешний процесс, не наш
- **Дублирование graph manipulation** — у нас есть WorkflowEngine
- **Зависимость от LLM-провайдеров Comfy Agent** — Claude/Codex/Gemini — не наш стек

### C — Требует архитектурного решения

1. **MCP compatibility** — можно ли сделать наш Core MCP-совместимым для работы с Comfy Agent UI?
2. **Двойной UI** — нужно ли нам два UI (наш Operator UI + Comfy Agent UI)?
3. **Sidebar vs standalone** — наш UI должен быть sidebar в ComfyUI или самостоятельным?

---

*Аудит завершён. Исследованы: ComfyUI (Comfy Desktop), comfyui-agent-panel, наш Agent Core. Ничего не изменено, не установлено, не запущено.*
