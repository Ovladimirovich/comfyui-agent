# EXTENDED DISCOVERY — Design Document

> Статус: **DRAFT** (архитектурное проектирование, не реализация).
> Дата: 2026-09-08.
> Контекст: AD-18 fix (2026-09-07) показал, что `prepare()` при `runtime=None`
> не может подтвердить совместимость workflow, потому что `custom_nodes=set()`
> и `models={"checkpoint"}` — неполные данные. Этот документ проектирует
> Extended Discovery — набор sources фактов, которые `prepare()` собирает
> ДО вызова `_compatibility_from_known()`, чтобы status стал AVAILABLE/
> UNAVAILABLE, а не UNKNOWN.

---

## A. Current State

### A.1 Что уже существует

| Компонент | Расположение | Что делает | Что НЕ делает |
|---|---|---|---|
| `RuntimeInfo` | `app/registry/runtime.py` | Содержит `{accelerator, vram_gb, fp16, xformers, lowvram, comfyui_version}` | `fp16/xformers/comfyui_version` всегда `None` — не извлекаются из `/system_stats` |
| `discover_runtime()` | `app/registry/runtime.py:52` | Вызывает `/system_stats`, строит RuntimeInfo | Не извлекает `fp16/xformers/comfyui_version` |
| `ModelRegistry` | `app/registry/model.py` | Кэширует обнаруженные модели per-backend | `discover()` требует `client`; `kinds` по умолчанию только `CHECKPOINT` |
| `ComfyClient.discover_checkpoints()` | `app/comfy/client.py:203` | `list_model_options("CheckpointLoaderSimple", "ckpt_name")` → `/object_info` | Не открывает другие kinds (lora/vae/controlnet/embedding) в `prepare()` |
| `ComfyClient.get_object_info()` | `app/comfy/client.py:88` | Возвращает raw dict всех нод ComfyUI | Не фильтруется, не кэшируется, не используется для custom-node discovery |
| `NodeSchemaStore` | `app/knowledge/node_schema.py:197` | Persist-кэш `{class_type: NodeSchema}` из `/object_info` (уже 959 схем) | Не интегрирован в `prepare()` / `Agent`; используется только `KnowledgeCore` |
| `KnowledgeCore.refresh()` | `app/knowledge/core.py:108` | Загружает `/object_info`, строит `NodeSchema` для каждой ноды | Не возвращает inventory для compatibility |
| `evaluate_compatibility()` | `app/registry/compatibility.py` | Проверяет workflow against runtime/models/custom_nodes/assets | Принимает `custom_nodes` как `set[str]` — но nigde не заполняется |
| `Agent.prepare()` | `app/agent.py:339` | `runtime = discover_runtime(client)`; `models = {"checkpoint"}`; `custom_nodes = set()` | **Ключевой пробел**: `custom_nodes` всегда пуст, runtime может быть `None` |
| `Agent._compatibility_from_known()` | `app/agent.py:227` (AD-18 fix) | Оценивает статус кандидата из known-данных | Зависит от полноты переданных `models`/`custom_nodes`/`runtime` |

### A.2 Ключевые находки аудита

1. **`/object_info` содержит всю нужную информацию.** Каждому node сопоставлен `python_module` — полный dotted path (например, `custom_nodes.pollinations-byop`, `comfy_api_nodes.nodes_sonilo`, `comfy_extras.nodes_audio`). Из него можно извлечь **package name** custom node.

2. **NodeSchemaStore уже имеет 959 схем** в `app/data/knowledge/node_schemas.json`. Это authoritative snapshot, но он не используется в `prepare()`.

3. **`required_custom_nodes` в manifests использует node class names** (`SoniloTextToMusic`, `SaveAudio`, `CreateVideo`), но совместимость проверяет membership в `custom_nodes` set. В текущем состоянии `custom_nodes=set()` → все workflow с `required_custom_nodes` UNAVAILABLE.

4. **Runtime-dependent требования** (`fp16`, `xformers`, `comfyui_version`) не могут быть получены из HTTP API ComfyUI — только из Python-интроспекции или конфигурационных файлов. При `runtime=None` они дают `UNKNOWN` (AD-18).

5. **Модели по умолчанию**: `models={"checkpoint"}` в `prepare()` — это hard-coded fallback, а не реальная discover-данных.

### A.3 Связи с существующей архитектурой

```
prepare()
  ├── discover_runtime(client)          → RuntimeInfo  {accelerator, vram_gb}
  ├── model_registry.discover(client)   → set[str]     models
  └── [NOT EXISTS] discover_custom_nodes() → set[str]  custom_nodes
                          ↓
  _select_manifest(capability, runtime, models, custom_nodes)
                          ↓
  _compatibility_from_known(c, runtime, models, custom_nodes)
                          ↓
  WorkflowStatus: AVAILABLE / UNAVAILABLE / UNKNOWN
```

**Разрыв**: third leg (`discover_custom_nodes`) отсутствует полностью.

---

## B. Discovery Contract

### B.1 Предлагаемая структура фактов

```python
@dataclass(frozen=True)
class DiscoveryFacts:
    """Единый контракт фактов, собранных prepare() до оценки совместимости."""

    # --- Runtime layer (из /system_stats) -------------------------
    runtime: Optional[RuntimeInfo]          # None = ComfyUI недоступен

    # --- Model layer (из /object_info) ----------------------------
    models: set[str]                        # точные имена checkpoint-моделей
    all_model_kinds: dict[ModelKind, set[str]]  # все discovered kinds (опц.)

    # --- Custom node layer (из /object_info python_module) --------
    custom_nodes: set[str]                  # package-имена установленных custom nodes
    # Пример: {"pollinations-byop", "comfyui-openai-compatible", ...}
    # Для built-in extras (comfy_extras.*) — НЕ включаются.

    # --- Authority flags ------------------------------------------
    runtime_available: bool                 # True если runtime != None
    models_available: bool                  # True если models не пусто и не default
    custom_nodes_available: bool            # True если custom_nodes не пусто
```

### B.2 Источник каждого поля

| Поле | Источник | Method |
|---|---|---|
| `runtime` | `ComfyClient.get_system_stats()` | `discover_runtime()` (существует) |
| `models` | `ComfyClient.get_object_info()["CheckpointLoaderSimple"]` → options | `ModelRegistry.discover()` (существует) |
| `custom_nodes` | `ComfyClient.get_object_info()` → `python_module` field | **Новый**: `ComfyClient.discover_custom_node_packages()` |
| `all_model_kinds` | `ComfyClient.get_object_info()` → LoraLoader, VAELoader, ... | `ModelRegistry.discover(kinds=[...])` (расширение) |

### B.3 Новый метод: `ComfyClient.discover_custom_node_packages()`

```python
def discover_custom_node_packages(self) -> set[str]:
    """Извлечь package-имена всех установленных custom nodes из /object_info.

    Алгоритм:
      1. Получить /object_info.
      2. Для каждой ноды посмотреть python_module.
      3. Если python_module содержит 'custom_nodes.' или 'comfy_api_nodes.' —
         извлечь package name (последний segment dotted path).
      4. Вернуть уникальный set package names.

    Authority: authoritative — данные поступают напрямую из ComfyUI.
    Inferred: нет, это raw facts.
    """
```

**Пример извлечения** (из current NodeSchemaStore snapshot):
```
PollinationsImageGen      → module=custom_nodes.pollinations-byop   → "pollinations-byop"
SoniloTextToMusic         → module=comfy_api_nodes.nodes_sonilo     → "nodes_sonilo"
OpenAICompatibleChat      → module=custom_nodes.comfyui-openai-compatible → "comfyui-openai-compatible"
KSampler                  → module=nodes                            → skip (built-in)
CheckpointLoaderSimple    → module=nodes                            → skip (built-in)
SaveAudio                 → module=comfy_extras.nodes_audio         → skip (built-in extras)
```

### B.4 Интеграция в `Agent.prepare()`

```python
# Текущий код (строки 339-356 app/agent.py):
runtime: Optional[RuntimeInfo] = None
models: set = {"checkpoint"}
custom_nodes: set = set()
try:
    runtime = discover_runtime(provider.client)
    if self.model_registry is not None:
        self.model_registry.discover(provider.client, backend_id, kinds=[ModelKind.CHECKPOINT])
        models |= set(self.model_registry.models_for(backend_id))
except Exception:
    runtime = None

# Предлагаемый код:
facts = self._discover_facts(provider.client, backend_id)
manifest = self._select_manifest(capability, facts.runtime, facts.models, facts.custom_nodes)
```

Где `_discover_facts()` собирает все три источника с graceful degradation:

```python
def _discover_facts(self, client, backend_id) -> DiscoveryFacts:
    runtime = None
    models: set = set()
    custom_nodes: set = set()
    runtime_available = False
    models_available = False
    custom_nodes_available = False

    try:
        runtime = discover_runtime(client)
        runtime_available = True
    except Exception:
        pass  # runtime = None, unknown runtime-dependent reqs

    try:
        if self.model_registry is not None:
            self.model_registry.discover(client, backend_id, kinds=[ModelKind.CHECKPOINT])
            models = set(self.model_registry.models_for(backend_id))
            models_available = bool(models)
        else:
            # Fallback: прямой call к client
            models = set(client.discover_checkpoints())
            models_available = bool(models)
    except Exception:
        pass  # models remains empty

    try:
        custom_nodes = set(client.discover_custom_node_packages())
        custom_nodes_available = bool(custom_nodes)
    except Exception:
        pass  # custom_nodes remains empty

    return DiscoveryFacts(
        runtime=runtime,
        models=models,
        custom_nodes=custom_nodes,
        all_model_kinds={},  # future: extend ModelRegistry.discover()
        runtime_available=runtime_available,
        models_available=models_available,
        custom_nodes_available=custom_nodes_available,
    )
```

---

## C. Authority Rules

### C.1 Принципы достоверности

| Правило | Описание |
|---|---|
| **R1: Raw facts > defaults** | Значения из ComfyUI API имеют приоритет над hard-coded fallbacks (`{"checkpoint"}`). |
| **R2: Empty set ≠ All** | Пустой `models=set()` не означает «все модели доступны» — это «неизвестно, какие модели есть». |
| **R3: Partial success** | Если один источник недоступен (например, `/system_stats`), остальные продолжают работать. |
| **R4: No inference without source** | Мы НЕ выводим `fp16=True` из того, что ComfyUI запущен на GPU. `fp16=None` → UNKNOWN. |
| **R5: Package vs class** | `required_custom_nodes` в manifest указывает на **package name** (как в `/object_info` через `python_module`). Сравнение — exact match. |
| **R6: Built-in excluded** | Nodes из `nodes.*` и `comfy_extras.*` НЕ считаются custom nodes. |

### C.2 Иерархия источников

```
Level 1 (authoritative, live):
  /system_stats       → RuntimeInfo  (accelerator, vram_gb)
  /object_info        → models, custom_nodes, ALL facts

Level 2 (persistent cache):
  NodeSchemaStore     → cached /object_info (для offline тестов)

Level 3 (default / declared):
  Manifest            → required_models, required_custom_nodes (декларация намерения)
  Hard-coded fallback → models={"checkpoint"} (только если discovery failed)
```

### C.3 Что считается inferred (НЕ authoritative)

- `fp16`, `xformers`, `lowvram` из `RuntimeInfo` → **всегда None**, пока не добавлена Python-интроспекция.
- `comfyui_version` → **всегда None**, пока ComfyUI не отдаёт его в `/system_stats`.
- `models={"checkpoint"}` → inferred default, NOT authoritative. Должен быть заменён реальным discovery.

---

## D. Compatibility Matrix

### D.1 Decision logic

Каждый candidate.workflow оценивается через `_compatibility_from_known(wf, runtime, models, custom_nodes)`:

```
IF declared_only:
  → DECLARED_ONLY

IF invalid_manifest OR invalid_workflow:
  → UNAVAILABLE (existing reasons)

# --- Declarative checks (проверяемы БЕЗ runtime) ---
IF required_models not subset of models:
  → UNAVAILABLE (MISSING_MODEL)

IF required_custom_nodes not subset of custom_nodes:
  → UNAVAILABLE (MISSING_CUSTOM_NODE)

# --- Runtime-dependent checks ---
IF runtime is None:
  IF has_runtime_dependent_requirements(wf):
    → UNKNOWN (UNKNOWN_RUNTIME)
  ELSE:
    → AVAILABLE

ELSE (runtime is not None):
  run full evaluate_compatibility(wf, runtime, models, custom_nodes)
  → AVAILABLE / UNAVAILABLE / UNKNOWN (по existing logic)
```

### D.2 Матрица состояний

| runtime | models | custom_nodes | wf.req_models | wf.req_custom_nodes | wf.has_runtime_reqs | Result |
|---|---|---|---|---|---|---|
| None | {} | {} | [] | [] | False | **AVAILABLE** |
| None | {} | {} | [] | ["X"] | False | **UNAVAILABLE** (MISSING_CUSTOM_NODE) |
| None | {} | {} | ["A"] | [] | False | **UNAVAILABLE** (MISSING_MODEL) |
| None | {} | {} | [] | [] | True | **UNKNOWN** |
| None | {"A"} | {} | ["A"] | [] | False | **AVAILABLE** |
| None | {"A"} | {"X"} | ["A"] | ["X"] | False | **AVAILABLE** |
| None | {"A"} | {"X"} | ["A","B"] | ["X"] | False | **UNAVAILABLE** (MISSING_MODEL) |
| rt✅ | {"A"} | {"X"} | ["A"] | ["X"] | True | **AVAILABLE** / **UNKNOWN** / **UNAVAILABLE** (full eval) |
| rt✅ | {} | {} | ["A"] | ["X"] | True | **UNAVAILABLE** (MISSING_MODEL + MISSING_CUSTOM_NODE) |
| rt✅ | {"A"} | {"X"} | [] | [] | True | зависит от runtime field values |

**Ключевое правило AD-18:** `runtime=None + has_runtime_reqs` → **UNKNOWN**, никогда AVAILABLE.

### D.3 Частичная доступность discovery

| Сценарий | runtime | models | custom_nodes | consequence |
|---|---|---|---|---|
| ComfyUI полностью доступен | ✅ | ✅ | ✅ | полный check |
| `/system_stats` упал, `/object_info` OK | ❌ | ✅ | ✅ | runtime-dependent → UNKNOWN; models/custom → checked |
| `/object_info` упал, `/system_stats` OK | ✅ | ❌ | ❌ | models/custom → UNAVAILABLE if required; runtime → checked |
| ComfyUI недоступен | ❌ | ❌ | ❌ | всё → UNKNOWN (если есть reqs) или AVAILABLE (если reqs нет) |
| `ModelRegistry` не настроен, client OK | ✅ | ✅ (client fallback) | ✅ | полный check |
| `ModelRegistry` не настроен, client FAIL | ✅ | ❌ | ❌ | частичный |

---

## E. Production Path

### E.1 Полный pipeline `prepare()`

```
Agent.prepare(capability, ...)
  │
  ├─ 1. Выбрать provider (BackendCatalog → _build_provider)
  │
  ├─ 2. _discover_facts(provider.client, backend_id)
  │     ├─ discover_runtime(client)          → RuntimeInfo?
  │     ├─ model_registry.discover(client)   → models set
  │     └─ client.discover_custom_node_packages() → custom_nodes set
  │
  ├─ 3. _select_manifest(capability, facts.runtime, facts.models, facts.custom_nodes)
  │     ├─ registry.select(cap, runtime)     → SelectedCandidate?
  │     └─ fallback: _compatibility_from_known(c, ...) → AVAILABLE candidates
  │
  └─ 4. ExecutionPlan + WorkflowEngine.execute(manifest, plan, provider)
```

### E.2 Graceful degradation

- Если `discover_runtime()` бросает → `runtime=None`, `runtime_available=False`.
- Если `model_registry.discover()` бросает → `models=set()`, `models_available=False`.
- Если `discover_custom_node_packages()` бросает → `custom_nodes=set()`, `custom_nodes_available=False`.
- Ни один exception НЕ перехватывается «внутри» _compatibility_from_known — он работает с тем, что получил.

### E.3 Integration с KnowledgeCore / RuntimeValidator

- **KnowledgeCore** остаётся отдельным subsistem для semantic evidence и node validation. Он НЕ подменяет Extended Discovery.
- **RuntimeValidator** (S4) запускает node workflow для проверки работоспособности — это отдельный путь, не совместимость.
- **Extended Discovery** — это lightweight pre-flight fact collection, который выполняется ДО Any LLM / knowledge queries.

### E.4 NodeSchemaStore как offline fallback

При недоступности live ComfyUI (например, CI / тесты) можно загрузить `NodeSchemaStore` как источник `custom_nodes`:

```python
def discover_custom_node_packages_from_cache(cache_dir: str) -> set[str]:
    store = NodeSchemaStore(data_dir=cache_dir)
    schemas = store.load_current()
    pkgs = set()
    for s in schemas.values():
        mod = s.python_module
        if not mod: continue
        for prefix in ("custom_nodes.", "comfy_api_nodes."):
            if mod.startswith(prefix):
                pkg = mod[len(prefix):].split(".")[0]
                pkgs.add(pkg)
                break
    return pkgs
```

Это позволяет тестам использовать existing snapshot (959 схем) без live ComfyUI.

---

## F. Test Path

### F.1 Deterministic fixture для тестов

Тесты должны передавать `DiscoveryFacts` явно, не полагаясь на fake runtime:

```python
def _facts(runtime=True, models=("checkpoint",), custom_nodes=()):
    return DiscoveryFacts(
        runtime=RT_OK if runtime else None,
        models=set(models),
        custom_nodes=set(custom_nodes),
        all_model_kinds={},
        runtime_available=runtime,
        models_available=bool(models),
        custom_nodes_available=bool(custom_nodes),
    )
```

**Примеры fixtures:**

```python
# Offline, no facts at all
FACTS_OFFLINE = _facts(runtime=False, models=(), custom_nodes=())

# Offline, models known, custom nodes from cached snapshot
FACTS_OFFLINE_PARTIAL = _facts(
    runtime=False,
    models={"checkpoint"},
    custom_nodes={"pollinations-byop", "nodes_sonilo", "comfyui-openai-compatible"},
)

# Full live runtime (E2E tests)
FACTS_FULL = _facts(runtime=True, models={"checkpoint", "foo.safetensors"}, custom_nodes={"pollinations-byop"})
```

### F.2 FakeClient НЕ должен «магически» утверждать совместимость

Текущие `FakeClient` в тестах (`test_agent.py`, `test_ui_m9.py`) возвращают `RuntimeError` из `get_system_stats()` → `runtime=None`. После AD-18 fix это правильно приводит к UNKNOWN.

**Запрещено:** делать `FakeClient.get_system_stats()` возврат «фейкового» RuntimeInfo с `fp16=True`, `vram_gb=12` и т.д. — это скроет реальный gap discovery.

**Правильный подход:**
1. Тесты, которым нужен AVAILABLE status, передают `DiscoveryFacts` явно (через новый параметр в `prepare()` или через monkeypatch).
2. Тесты, проверяющие UNKNOWN behavior, оставляют `runtime=None` и `custom_nodes=set()`.
3. `test_ui_m9` — тест UI-слоя, он использует FakeProvider/FakeClient. Для его修复рования нужно либо:
   - (a) передавать `DiscoveryFacts` с known custom nodes и models;
   - (b) или добавить optional param `facts_override` в `ConversationAgent.turn()`.

### F.3 Regression tests (уже добавлены)

Файл: `tests/test_ad18_fallback_selection.py` — 13 тестовCases A-E. Они проверяют именно `_compatibility_from_known()` и `_select_manifest()` contract, БЕЗ зависимости от FakeClient.

---

## G. Backend-Scoping Boundary

### G.1 Что НЕ решается в Extended Discovery

- **Workflow.backend vs BackendSpec.kind** — поле `Workflow.backend` остаётся метаданным, НЕ используется для gating selection.
- **Provider ≠ Backend** — `ComfyUIProvider.backend_id` остаётся источником истины для dispatch.
- **Backend catalog choose()** — логика выбора backend из `BackendCatalog` остаётся без изменений.

### G.2 Extension point для будущего backend-scoping

В `_compatibility_from_known()` и `DiscoveryFacts` зарезервированы поля/структуры, которые позволят在未来 добавить check:

```python
# В DiscoveryFacts — расширение (не реализовано):
backend_context: Optional[BackendSpec] = None  # future: для backend-scoping

# В _compatibility_from_known() — расширение (не реализовано):
def _compatibility_from_known(wf, runtime, models, custom_nodes,
                               backend_context=None):  # future param
    if backend_context is not None:
        # FUTURE: check wf.backend == backend_context.backend_id or kind
        pass
```

**Документировано в коде:** TODO-заметка в `app/agent.py:277` (уже добавлена).

### G.3 Почему backend-scoping отложен

`Workflow.backend` и `BackendSpec.kind` используют разные namespaces (manifest string vs catalog id). Для корректного scoping нужно архитектурное решение, определяющее:
- какие значения `Workflow.backend` допустимы;
- как мапить `Workflow.backend` → `BackendSpec.kind`;
- что делать при mismatch (UNKNOWN? UNAVAILABLE?).

Это выходит за рамки Extended Discovery и требует отдельного AD.

---

## H. Implementation Plan

### H.1 Последовательность (без кода)

**Шаг 1: ComfyClient.expand** (`app/comfy/client.py`)
- Добавить `discover_custom_node_packages(self) -> set[str]`.
- Парсит `/object_info`, извлекает `python_module`, фильтрует по `custom_nodes.` / `comfy_api_nodes.`, возвращает set package names.
- Unit-test: mock `/object_info` → проверить set.

**Шаг 2: DiscoveryFacts dataclass** (`app/registry/discovery.py` — новый файл)
- Определить `@dataclass frozen DiscoveryFacts`.
- Определить helper `merge_facts(a, b)` для комбинирования partial results.

**Шаг 3: Agent._discover_facts()** (`app/agent.py`)
- Новый private method, собирающий runtime + models + custom_nodes.
- Graceful degradation per source.
- Возвращает `DiscoveryFacts`.

**Шаг 4: Agent.prepare() refactor** (`app/agent.py`)
- Заменить текущий block runtime/models/custom_nodes на `_discover_facts()`.
- Передача `facts.runtime`, `facts.models`, `facts.custom_nodes` в `_select_manifest()`.

**Шаг 5: Update callers** (`app/conversation.py`, UI handlers)
- `ConversationAgent.turn()` → `prepare()` теперь использует discovery facts internally, external interface unchanged.
- Про Verify что все точки входа в `agent.run()` / `agent.prepare()` работают без изменений signature.

**Шаг 6: Test updates** (отдельно, не в этом PR)
- `test_agent.py::test_agent_media_agnostic_run` — передать `DiscoveryFacts` с known custom_nodes.
- `test_ui_m9.py` — передать `DiscoveryFacts` с known models + custom_nodes.
- `test_m11_verification.py` — аналогично.
- Новые тесты на partial discovery scenarios.

**Шаг 7: NodeSchemaStore integration (future)**
- Добавить опцию: если live ComfyUI недоступен, грузить `custom_nodes` из `NodeSchemaStore` кэша.
- Это решит проблему offline-тестов без изменения FakeClient.

### H.2 Что НЕ входит в Implementation Plan

- Backend-scoping (раздел G).
- Изменение `Workflow.backend` semantics.
- Изменение `required_custom_nodes` формата в manifests.
- Изменение `NodeSchemaStore` persistence format.
- Изменение `KnowledgeCore` / `RuntimeValidator` interfaces.

### H.3 Risk Mitigation

| Risk | Mitigation |
|---|---|
| `/object_info` returns large payload (~1.6MB) | Уже обрабатывается в `ComfyClient._request()` chunked read |
| `python_module` format varies between nodes | Filter by prefix; unknown prefixes → skip |
| Custom node package name ≠ manifest `required_custom_nodes` value | See §B.4: manifests use NODE CLASS NAMES, не package names. Требуется mapping. |
| Breaking existing tests | New tests isolate the contract; existing tests need explicit facts fixture |

### H.4 Mapping Gap: manifest `required_custom_nodes` vs discovered packages

**Важное замечание:** текущие manifests используют **node class names** в `required_custom_nodes` (например, `"SoniloTextToMusic"`, `"SaveAudio"`), но `discover_custom_node_packages()` возвращает **package names** (например, `"nodes_sonilo"`, `"comfy_extras.nodes_audio"`).

Для корректной работы нужно либо:
1. **Изменить manifests** на package names — но пользователь запретил менять `pollinations_image` и «не трогать priorities».
2. **Изменить compatibility check** на fuzzy match (package name contains class name, or class name is in package's node list).
3. **Расширить discover** на возврат `{package: set[node_class_names]}` mapping, и проверять membership через этот mapping.

**Рекомендация (для future design):** option 3 — `discover_custom_node_packages()` возвращает `dict[str, set[str]]` {package: {node_class_names}}. Compatibility check тогда может проверять: «все required_custom_nodes из manifest принадлежат хотя бы одному discovered package». Это сохранит backward-compatibility с текущими manifests.

---

## Приложение: Ссылки на код

- `app/registry/runtime.py` — RuntimeInfo, discover_runtime
- `app/registry/model.py` — ModelRegistry, ModelKind
- `app/comfy/client.py` — ComfyClient, get_object_info, discover_checkpoints
- `app/registry/compatibility.py` — evaluate_compatibility
- `app/registry/workflow.py` — Workflow, WorkflowStatus, UnavailableReason, UnknownReason
- `app/agent.py:227-273` — _compatibility_from_known (AD-18 fix)
- `app/knowledge/node_schema.py` — NodeSchema, NodeSchemaStore
- `app/knowledge/core.py:108` — KnowledgeCore.refresh()
- `docs/14_RUNTIME_COMPATIBILITY.md` — RuntimeInfo spec
- `docs/06_WORKFLOW_MODEL.md` — Workflow manifest spec
- `docs/PROJECT_SPEC.md §10, AD-18` — Provider/Backend model, UNKNOWN≠AVAILABLE
