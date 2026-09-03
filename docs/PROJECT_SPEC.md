# ComfyUI Agent v1 — Project Specification

**Version:** v0.2 (APPROVED — поправки после ревью документации: C-01, NQ-01..03, S-01/02)
**Status:** Documentation baseline APPROVED. Код не начат (M1 — по отдельной команде).
**Owner:** Multimodal Agent Operator project
**Single Source of Truth:** This document. All `docs/00..18_*.md` are derived from it.

---

## 0. Key Architectural Formula

```text
User
  ↓
Multimodal Input
  ↓
Agent
  ↓
Intent / Context
  ↓
Capability
  ↓
Provider
  ↓
Workflow
  ↓
Execution Backend
  ↓
Execution
  ↓
Verification
  ↓
Asset
  ↓
Context / UI
```

### Non-negotiable distinctions (зафиксированы как аксиомы)

```text
Capability ≠ Workflow
Provider  ≠ Model
Provider  ≠ Execution Backend
Asset     ≠ File
Workflow  ≠ Node Graph для LLM
ComfyUI   ≠ Agent
```

**Главный принцип:** ComfyUI Agent — это **Multimodal Agent Operator для ComfyUI**, а не агент генерации изображений. Image/Video/Audio и другие media types проходят через одну media-agnostic execution-архитектуру. Image-workflows — первый реальный validation target, но **не архитектурная основа**.

---

## 1. Project Vision

ComfyUI Agent — самостоятельный мультимодальный агент-оператор, использующий ComfyUI как универсальный execution engine для media-задач (изображения, видео, аудио и расширяемые типы).

Агент принимает текст и медиа-ассеты, понимает задачу, выбирает capability → provider → workflow, формирует plan, запускает workflow в реальном ComfyUI, отслеживает выполнение, возвращает результат как Asset и связывает его с контекстом диалога.

### Является
- Multimodal Agent Operator поверх ComfyUI.
- Media-agnostic execution-слоем (image/video/audio/…).
- Контекстным (многоходовым) оператором с lineage ассетов.

### Не является
- image generator;
- wrapper над ComfyUI;
- универсальным чат-ботом;
- набором MCP tools;
- копией существующего агента (в т.ч. AI Video Operator);
- «цифровым организмом» / autonomous learning system.

---

## 2. Goals / Non-goals

### Goals
- G1. Управлять ComfyUI как execution engine через единый media-agnostic pipeline.
- G2. Поддерживать мультимодальный ввод (text/image/video/audio) и комбинации ассетов.
- G3. Декларативно описывать workflow через manifest (без node-id у LLM).
- G4. Работать на реальном локальном ComfyUI (AMD DirectML) без mock на финальной валидации.
- G5. Сохранять lineage между ассетами для многоходового диалога.
- G6. Быть расширяемым: новый provider/model/workflow/capability не требует переписывания ядра.

### Non-goals (v1)
- NG1. multi-agent system.
- NG2. RAG / vector database / сложная долгосрочная память.
- NG3. self-reflection / autonomous learning.
- NG4. X-Ray / HEALER / distributed execution.
- NG5. PostgreSQL / Redis / Docker orchestration.
- NG6. Полноценная реализация video/audio E2E (capability/workflow описываются, но реальный video-E2E — отдельный milestone, не M1–M4).

---

## 3. System Boundaries

**Внутри системы:**
- Agent (Intent/Context/Planner/Tools).
- Registries (Capability / Provider / Workflow).
- Workflow Engine, ComfyUI Operator, Provider Asset Transport.
- Execution Backend (ComfyUI).
- Job Manager, Verifier, Asset Store.

**Внешние границы:**
- ComfyUI HTTP API (`/prompt`, `/queue`, `/history`, `/view`, `/interrupt`, `/object_info`, `/system_stats`) + WebSocket (`/ws`).
- LLM через OpenAI-совместимый endpoint (`fallback_proxy`, `127.0.0.1:20130`) — конфигурируемый.
- Модели/чекпоинты/LoRA/VAE — физически в `ComfyUI/models`.
- Локальная ФС — `data/assets`, `static/assets`.
- Пользователь — через UI (чат + attachments + preview).

**Жёсткие границы:**
- LLM не имеет прямого доступа к ComfyUI HTTP и не строит node-graph.
- Агент не выполняет произвольный shell/HTTP по указке LLM.
- ComfyUI слушает только `127.0.0.1`.

---

## 4. Core Architectural Principles

- **P1. Media-agnostic core.** Ни один модуль ядра (Agent/Operator/Job/WorkflowEngine/Verifier) не ветвится по типу медиа. Image и video — разные capability/workflow, но один execution engine.
- **P2. Declarative workflow.** Логические параметры маппятся в node/field через manifest; LLM видит только логику.
- **P3. Layered responsibility.** Каждый слой имеет одну зону ответственности (см. §6).
- **P4. Provider ≠ Backend.** Провайдер — абстракция доступа; backend — то, что реально исполняет.
- **P5. Asset-first.** Результат и ввод — это Asset-объекты, а не файлы-вложения.
- **P6. No-LLM-first verification.** Исполняющая цепь проверяется на реальном ComfyUI ДО подключения LLM (M1–M4 без LLM).
- **P7. Real E2E only.** «Готово» = реальный ComfyUI + реальный workflow + реальная модель + реальный результат, без mock (video-E2E — отдельный milestone).
- **P8. Extensibility without rewrite.** Добавление capability/workflow/provider — конфигурация/новый модуль, не правка ядра.
- **P9. Reproducibility.** ExecutionPlan фиксирует конкретную версию workflow (см. AD-17).
- **P10. Explicit over implicit.** UNKNOWN-состояния совместимости не трактуются как AVAILABLE (см. AD-18).

---

## 5. Architectural Invariants / Запреты

```text
LLM → напрямую ComfyUI HTTP              ЗАПРЕЩЕНО
LLM → выбор/генерация node-id            ЗАПРЕЩЕНО
LLM → произвольный shell execution       ЗАПРЕЩЕНО
LLM → произвольный HTTP                  ЗАПРЕЩЕНО
Agent → прямой ComfyUI HTTP              ЗАПРЕЩЕНО (только через Operator)
WorkflowEngine → image/video-специфика   ЗАПРЕЩЕНО
Operator → знание media-типа             ЗАПРЕЩЕНО (для него это execution)
Asset → жёстко image-поля                ЗАПРЕЩЕНО (тип — строка)
Capability === Workflow                  ЗАПРЕЩЕНО
Provider === Model                       ЗАПРЕЩЕНО
Provider === Execution Backend           ЗАПРЕЩЕНО
Provider → самостоятельный выбор workflow ЗАПРЕЩЕНО (см. AD-22)
Workflow Registry → «умный агент»        ЗАПРЕЩЕНО (только хранение+фильтр)
UNKNOWN compatibility → AVAILABLE        ЗАПРЕЩЕНО (см. AD-18)
```

---

## 6. System Architecture

```text
                         USER
                           │
                           ▼
                   MULTIMODAL INPUT
                           │
                           ▼
                    ┌─────────────┐
                    │    AGENT    │  Intent / Context / Planner / Tools
                    └──────┬──────┘
                           │
                           ▼
                  CAPABILITY ROUTER
                           │  capability
                           ▼
                  WORKFLOW REGISTRY
                           │  Candidate Workflows (все манифесты capability)
                           ▼
                  COMPATIBILITY FILTER
                           │  × Runtime / Provider / Model / CustomNodes / INPUTS
                           ▼
                  WORKFLOW SELECTION POLICY
                           │  один workflow (приоритет / override)
                           ▼
                  EXECUTION PLAN  (workflow_id@version зафиксирован)
                           │
                           ▼
                  COMFYUI OPERATOR
                           │
                           ▼
                   WORKFLOW ENGINE (чистый маппинг logical→node/field)
                           │
                           ▼
              PROVIDER ASSET TRANSPORT (upload_asset → backend_ref)
                           │
                           ▼
                   EXECUTION BACKEND (ComfyUI)
                           │
                           ▼
                  EXECUTION / VERIFIER
                           │
                           ▼
                      ASSET STORE
                           │
                           ▼
                      CONTEXT / UI
```

### Границы ответственности (не допускать размытия)
```text
Agent                понимает задачу (через LLM/Tools)
Capability Router     определяет capability по запросу+контексту
Workflow Registry     хранит манифесты; по capability → Candidate Workflows (НЕ выбирает финальный)
Compatibility Filter применяет декларативные constraints (Runtime/Provider/Model/CustomNodes/Inputs)
Workflow Selection Policy выбирает ОДИН совместимый workflow (приоритет/override)
Provider             отвечает за взаимодействие с backend (upload asset, execute, job) — workflow НЕ выбирает
Execution Backend    реально выполняет граф
Workflow Engine      превращает logical plan в executable workflow (чистый маппинг)
Verifier             проверяет результат по output-contract
Asset Store          хранит и связывает assets (lineage)
Job Manager          управляет жизнью Job (state/progress/cancel)
```

### Уточнение зон (во избежание blur — AD-22 / OAQ-13)
- **Capability Router** не выбирает workflow и не знает backend. Только: `request+context → capability`.
- **Workflow Registry** НЕ «умный агент»: только хранит манифесты и по capability отдаёт кандидатов; фильтрацию делает Compatibility Filter.
- **Provider** не выбирает workflow. Только: предоставляет backend, каталог моделей, `upload_asset`, `execute`, `get_job`, `cancel`.
- **Workflow Selection Policy** — единственный, кто финально выбирает workflow из совместимых (приоритет + явный override пользователя/Planner).

### Input compatibility (AD-23 / OAQ-14)
Compatibility Filter обязательно учитывает **доступные ассеты**:
```text
Capability: video.image_to_video
Available:  asset_001=image, asset_002=video
Workflow A requires {image}  → совместим (есть image)
Workflow B requires {video}  → НЕсовместим (нет свободного video как вход)
```
То есть выбор workflow зависит от `capability + runtime + model + custom nodes + доступных assets/типов/обязательных inputs`.

---

## 7. Domain Model

### Сущности
```text
Asset              — медиа-объект системы (не файл)
Capability          — логич. способность (image.generate, video.generate, …)
Provider            — абстракция доступа к execution (comfyui)
ExecutionBackend    — то, что реально исполняет (local_comfyui)
Model               — конкретная модель/чекпоинт внутри provider
Workflow            — исполняемый граф + manifest (с version)
WorkflowManifest    — декларативное описание workflow
RuntimeInfo         — реальные возможности железа/рантайма
Intent              — намерение агента (capability + params + assets)
ExecutionPlan       — capability + workflow_id@version + provider + bindings + params  (версия зафиксирована)
Job                 — единица исполнения (один POST /prompt)
Result              — верифицированные выходные ассеты
ConversationContext — сообщения + активные assets/jobs/workflows
```

### Связи
```text
Capability → Workflow → Provider → Model
Asset → ExecutionPlan → Job → Asset (lineage)
Intent → Capability → Provider → Workflow → ExecutionPlan
ConversationContext → (Assets, Jobs, Workflows, Parameters, active_asset, active_job)
```

---

## 8. Asset Model + Lineage

### Asset (объект, не файл)
```text
Asset:
  id            — уникальный
  type          — image|video|audio|mask|sequence|document|other (расширяемо)
  mime          — MIME-тип
  path          — путь к файлу на диске (в разрешённом root)
  metadata      — открытый словарь (width,height,duration,fps,…)
  role          — input|output|reference
  source_asset  — id входного ассета (lineage)
  created_from  — id Job, породившего ассет
  created_at    — timestamp
```

### Lineage
```text
image_001 ──(Job J1)──▶ video_001 ──(Job J2)──▶ video_002
```
- `Asset.source_asset` + `Asset.created_from` задают рёбра lineage-графа.
- `Job.input_assets` / `Job.output_assets` фиксируют связку.
- `AssetStore.lineage(asset_id)` обходит цепочку по `source_asset`.
- Lineage — основа многоходового контекста: «сделай камеру медленнее» резолвится в `active_asset`.

---

## 9. Capability Model

`Capability` — НЕ workflow. Одна capability может иметь много workflow.

```text
Capability:
  id            — "image.generate" | "image.edit" | "image.inpaint" | "image.upscale"
                  | "video.generate" | "video.image_to_video" | "video.video_to_video"
                  | "video.upscale" | "audio.generate" | "custom.execute"
  media_input   — допустимые типы входных ассетов (для input compatibility)
  media_output  — тип выходного ассета
  operation     — семантика
  parameters    — логич. параметры (prompt, model, width, height, duration, fps, seed, …)
  requirements  — общие требования (accelerator, vram, …)
  constraints   — ограничения
```

- Capability-список плоский и расширяемый.
- Конкретная модель (WAN/SD/…) — свойство workflow/provider-конфигурации, НЕ capability и НЕ архитектуры.
- `media_input` используется Compatibility Filter для input compatibility (§6, AD-23).

---

## 10. Provider / Execution Backend Model

### Разделение (концептуально, не смешивать)
```text
Capability → Provider → Workflow → Execution Backend
```

```text
Provider (comfyui):
  id            — "comfyui"
  backend       — ExecutionBackend.id  ("local_comfyui")
  capabilities  — какие capability обслуживает
  models        — каталог доступных моделей (из /object_info)
  upload_asset(asset) → backend_ref   — транспорт ассета в backend
  execute(prompt) → prompt_id
  get_job(prompt_id) → JobStatus
  cancel(prompt_id)

ExecutionBackend (local_comfyui):
  id            — "local_comfyui"
  kind          — comfyui-local
  (реально выполняет граф на GPU)
```

### BackendRef (абстракция, AD-26 / NQ-03)
`Provider.upload_asset(asset) → BackendRef`:
```text
BackendRef:
  provider   — id провайдера ("comfyui")
  backend    — id backend ("local_comfyui")
  reference  — backend-specific ссылка (для ComfyUI: {filename, subfolder, type})
  metadata   — открытый словарь (опц.)
```
ComfyUI-specific форма `reference` (`{filename, subfolder, type}`) находится **внутри** provider/backend-specific части, НЕ делается универсальным контрактом. Другой backend использует собственную форму `reference`.

- v1: ровно один `Provider(comfyui)` поверх `Backend(local_comfyui)`. Это 1:1, но понятия разделены в модели.
- Будущий внешний provider = новый класс за тем же интерфейсом; ядро не меняется.
- ComfyUI сам хостит много моделей/custom nodes — это **модели внутри** провайдера, не отдельные провайдеры.
- **Provider НЕ выбирает workflow** (AD-22).

---

## 11. Workflow Model + Manifest

Workflow = `workflow.json` (ComfyUI API-формат графа) + `manifest.json` (декларативное описание).

Пример манифеста — `txt2img` (без входных ассетов):

```json
{
  "id": "txt2img",
  "version": "1.0.0",
  "capability": "image.generate",
  "provider": "comfyui",
  "backend": "local_comfyui",
  "inputs": {
    "prompt":    {"node":"6","field":"text"},
    "negative":  {"node":"7","field":"text"},
    "width":     {"node":"5","field":"width"},
    "height":    {"node":"5","field":"height"},
    "seed":      {"node":"3","field":"noise_seed"},
    "model":     {"node":"4","field":"ckpt_name"}
  },
  "outputs": {
    "result": {"node":"9","kind":"image"}
  },
  "parameters": {
    "steps": {"default":20,"min":1,"max":60},
    "cfg":   {"default":8}
  },
  "required_models": ["checkpoint"],
  "required_custom_nodes": [],
  "min_comfyui_version": "0.0.0",
  "requirements": {"accelerator":"any","xformers":false,"min_vram_gb":4,"fp16":true},
  "limits": {
    "max_upload_bytes": 209715200,
    "max_asset_duration": 0,
    "max_video_width": 0,
    "max_video_height": 0,
    "max_sequence_length": 0
  }
}
```

`txt2img` **не имеет** `asset_inputs` — это text-to-image без входного медиа.

Пример манифеста — `img2img` (входной ассет через реальный `LoadImage`):

```json
{
  "id": "img2img",
  "version": "1.0.0",
  "capability": "image.edit",
  "provider": "comfyui",
  "backend": "local_comfyui",
  "inputs": {
    "prompt":   {"node":"6","field":"text"},
    "negative": {"node":"7","field":"text"},
    "denoise":  {"node":"15","field":"denoise"},
    "seed":     {"node":"3","field":"noise_seed"}
  },
  "asset_inputs": {
    "image": {"node":"10","field":"image","kind":"image"}
  },
  "outputs": {
    "result": {"node":"9","kind":"image"}
  },
  "parameters": {
    "steps": {"default":20,"min":1,"max":60},
    "cfg":   {"default":8}
  },
  "required_models": ["checkpoint"],
  "required_custom_nodes": [],
  "min_comfyui_version": "0.0.0",
  "requirements": {"accelerator":"any","xformers":false,"min_vram_gb":4,"fp16":true},
  "limits": {
    "max_upload_bytes": 209715200
  }
}
```

- `manifest.inputs` — логич. параметры → node/field.
- `manifest.asset_inputs` — роли входных ассетов → node/field/kind (для input compatibility). Показан на `img2img` с реальным `LoadImage` (node "10", field "image").
- `manifest.outputs` — контракт результата (kind для верификации).
- Manifest НЕ содержит image-specific логики; поля универсальны.
- `version` — semver. **latest selection (AD-24 / NQ-01):** Registry может отдавать `latest` = максимальная доступная VALIDATED/AVAILABLE semver-версия `workflow_id`; `latest` используется только на этапе candidate/selection. **ExecutionPlan всегда фиксирует конкретные `workflow_id@version`** (AD-17); Job никогда не ссылается на `latest`.
- `limits` — capability/workflow-aware ограничения (AD-21 / OAQ-10). **Семантика (AD-25 / NQ-02):** `null`/отсутствие значения = unlimited; `0` = запрещено; положительное значение = соответствующий max-лимит. `0` НЕ используется как скрытый alias для unlimited (в примере `txt2img` video-лимиты = 0 означают «видео на входе запрещено»).
- `declared_only` (AD-27 / S-01): манифест с `"declared_only": true` объявляет capability без исполняемого `workflow.json`. Такой workflow НЕ попадает в AVAILABLE и используется только архитектурными тестами (media-agnostic тест M4). Никакого fake/stub `workflow.json` не создаётся.

---

## 12. Workflow Lifecycle

Наличие файла ≠ возможность использовать.

```text
DISCOVERED
   ↓ (валидация схемы манифеста + структуры workflow.json)
VALIDATED
   ↓ (Compatibility Filter: runtime + provider + model + custom nodes + inputs)
AVAILABLE ───────┐
                 │
UNAVAILABLE ─────┤
                 │
UNKNOWN ─────────┘   (совместимость невозможно определить, напр. версия ComfyUI)
```

### Причины (диагностируемы)
```text
missing_model        — нет требуемого чекпоинта/LoRA
missing_custom_node  — нет требуемого custom node (по /object_info)
incompatible_runtime — требует CUDA/xformers при AMD DirectML
insufficient_vram    — min_vram_gb > доступно
invalid_manifest     — манифест не прошёл схему
invalid_workflow     — workflow.json некорректен
input_incompatible   — предоставленные ассеты не покрывают требуемые asset_inputs workflow
unknown_version      — не удалось определить версию ComfyUI (AD-18)
unknown_runtime      — поля RuntimeInfo (vram/accelerator/fp16/xformers) не определены, совместимость недостоверна
```

### Правило совместимости (AD-18 / OAQ-02)
```text
KNOWN  + compatible   → AVAILABLE
KNOWN  + incompatible → UNAVAILABLE(reason)
UNKNOWN              → UNKNOWN (DEGRADED) — НЕ AVAILABLE
```
- `UNKNOWN` **нельзя** автоматически считать AVAILABLE.
- v1: оператор может принудительно запустить UNKNOWN-workflow (осознанный override, явно), но по умолчанию routing его не выбирает.

---

## 13. Runtime Compatibility

`RuntimeInfo` (реальные возможности):
```text
accelerator  — directml | cuda | cpu   (v1: directml)
vram_gb      — доступный объём VRAM
fp16         — поддержка fp16 (v1: true, --force-fp16)
xformers     — (v1: false, --disable-xformers)
lowvram      — (v1: true, --lowvram)
comfyui_version — фактическая версия (может быть UNKNOWN)
```

Правило:
```text
workflow.requirements + workflow.min_comfyui_version → RuntimeInfo → AVAILABLE | UNAVAILABLE | UNKNOWN
```

- AMD DirectML + lowvram + fp16: медленная первая генерация (10–30с загрузка VRAM), очередь последовательная, ноды на xformers/CUDA несовместимы.
- `min_comfyui_version` сверяется с фактической версией; если версия ComfyUI не определена → `UNKNOWN` (не AVAILABLE).
- `unknown_version` можно переопределить явным override оператора.

---

## 14. Multimodal Input Model

Входные modalities: Text, Image, Video, Audio (+ комбинации).

```text
Agent
  ↓
Asset ingestion (файл → Asset с metadata)
  ↓
Metadata extraction (тип/размер/длительность)
  ↓
[опц.] Vision/Audio understanding → текст (для Intent)
  ↓
Intent
```

- **Передача файла в ComfyUI** (asset wiring) и **понимание файла** (vision) — РАЗНЫЕ операции.
- Asset ingestion: любой файл → Asset (роль input).
- Vision/Audio understanding — опционально, deferred (M6+), через тот же OpenAI-совместимый endpoint; для видео — семпл кадров. Интерфейс `VisionUnderstand(asset)→text` pluggable. Не используется в M1–M4.
- Ingestion применяет capability-aware limits (§11 `limits`, §20).

---

## 15. Conversation / Context Model

```text
ConversationContext:
  messages      — история сообщений
  assets        — известные ассеты сессии
  jobs          — известные Job'ы
  workflows     — использованные workflow (id@version)
  parameters    — последние параметры
  active_task   — текущая capability
  active_workflow
  active_job    — последний Job
  active_asset  — последний выходной Asset (для «её/теперь/ещё»)
  unresolved    — открытые уточнения
```

Пример:
```text
User: [image] Сделай из неё видео.
 → image_001 → video.generate → workflow_X → video_001

User: Сделай камеру медленнее.
 → active_asset = video_001 → modify/re-generate → video_002
```

Context хранит не только текст, но и активные assets/jobs/workflows.

---

## 16. Execution Model

Единица исполнения — **один** `Job` = **один** `POST /prompt` (один граф) → один `prompt_id`.

- Многостадийный pipeline **внутри** ComfyUI — один граф (ноды цепляются) = один Job.
- Pipeline **через несколько запусков** — несколько Job, связанных lineage (output Asset Job1 = input Asset Job2).
- `ExecutionPlan` фиксирует `workflow_id@version` (AD-17) для воспроизводимости.
- Поток: `ExecutionPlan → Operator.upload_assets → WorkflowEngine.build → Operator.execute(prompt) → prompt_id → WS-мониторинг → history → Verifier → Asset`.

---

## 17. Job Lifecycle

```text
CREATED
  ↓
VALIDATED
  ↓
QUEUED
  ↓
RUNNING
  ↓
COMPLETED
  ↓
VERIFIED
```
Альтернативы:
```text
FAILED | CANCELLED | TIMEOUT
```

Поля Job:
```text
id, prompt_id, workflow_id, workflow_version, capability,
status, progress, current_node,
input_assets[], output_assets[], error
```
- Мониторинг: HTTP (`/queue`,`/history`) + WebSocket (`/ws`: executing/progress/executed/execution_success).
- Cancel: `POST /interrupt` по текущему prompt_id (per-job cancel).

### Cancellation semantics (AD-19 / OAQ-06)
- `Job = CANCELLED` по запросу `cancel(job)` → `interrupt(prompt_id)`.
- ComfyUI **может физически успеть создать partial output** до interrupt.
- v1-политика: **discard** — частичные backend-outputs НЕ возвращаются агенту и не становятся Asset.
- НЕ утверждается, что ComfyUI гарантированно ничего не создал; статус CANCELLED отражает намерение, а не факт отсутствия файлов.
- Опционально: retained orphan/temp outputs помечаются для cleanup (см. §19).

---

## 18. Verification Model

Verifier проверяет результат **по output-contract** манифеста (не по хардкоду «это картинка»).

```text
✓ Job COMPLETED
✓ Для каждого manifest.outputs[kind]:
    - Asset создан
    - asset.type == kind
    - файл читается
    - metadata осмыслены (image: width/height>0; video: duration/fps)
✓ В history нет error-ноды ComfyUI
```
- Не прошёл → Job FAILED с описанием причины.
- CANCELLED-джобы верификацию не проходят (discard, см. §17).

---

## 19. Storage Model

Два класса файлов — разные владельцы:

```text
AssetStore.persistent   — результаты/вводы (data/assets, static/assets)
Execution temp          — временные копии для транспорта в backend
```

- **Asset files:** `data/assets/` (или `static/assets/`), отдаются через `GET /api/assets/{id}` (range/streaming). В памяти не держим, стримим.
- **Asset index:** `data/assets.jsonl` (Append-only): `Asset`-записи для lineage/query.
- **Temp ownership lifecycle (AD-20 / OAQ-08/09):** после `upload_asset()` провайдер возвращает `backend_ref`, НО это НЕ означает, что backend завершил чтение файла. Контракт:
  ```text
  upload → backend confirms ownership/reference → safe to cleanup
  ```
  Provider явно сигнализирует момент, когда temp больше не нужен (подтверждение referenca или завершение Job). Удаление temp сразу по возврату `backend_ref` **запрещено**, если backend ещё может читать файл (критично для видео).
- **Retention:** политика `MAX_ASSETS` / до конца сессии (конфигурируемо) — НЕ фиксируется жёстко в v1 (решение отложено, OAQ-08). Temp чистится по сигналу Provider/после Job.
- **Path confinement:** Asset-пути только в разрешённых roots (`data/assets`, `static/assets`); path-traversal запрещён.

---

## 20. Security Model

- ComfyUI слушает только `127.0.0.1` (не выставлять наружу).
- LLM не имеет произвольного shell/HTTP; только whitelist Tools (`comfy.*`).
- Workflow валидируется до исполнения (manifest + граф).
- **Capability-aware limits (AD-21 / OAQ-10):** глобально `MAX_UPLOAD_BYTES` + per-capability/per-workflow ограничения из манифеста `limits`:
  - `MAX_UPLOAD_BYTES` (глобальный + переопределение в workflow)
  - `MAX_ASSET_DURATION` — для video/audio
  - `MAX_VIDEO_WIDTH` / `MAX_VIDEO_HEIGHT` — для video
  - `MAX_SEQUENCE_LENGTH` — для sequence
  - Ограничения применяются на ingestion; отказ > лимита с ясной ошибкой.
- Секреты (`LLM_API_KEY`/`GEMINI_KEY`) — только в `.env`, не в репозиторий.
- localhost-вызовы без системного прокси (Hiddify блокирует localhost).
- Загрузки: валидация mime/ext, запрет произвольного доступа к локальным файлам (path confinement).

---

## 21. API / UI Boundaries

### API (бэкенд)
```text
POST /api/chat                  — сообщение + опц. attachments
POST /api/assets                — загрузка ассета
GET  /api/assets/{id}           — отдача ассета (range)
GET  /api/jobs/{id}             — статус Job (+progress, outputs)
POST /api/jobs/{id}/cancel      — отмена
GET  /api/capabilities          — список capabilities
GET  /api/workflows             — список workflow (со статусом lifecycle, включая UNKNOWN)
GET  /api/runtime               — RuntimeInfo
```
- Поток ответов агента: SSE (или WebSocket) от `/api/chat`.
- Фронтенд и бэкенд НЕ придумывают свой API — контракт зафиксирован здесь.

### UI (v1, минимальный — НЕ Control Center)
```text
┌───────────────────────────────┐
│          CHAT                 │
│ user message                  │
│ image/video attachment         │
│ agent status                  │
│ [generated image/video]        │
├───────────────────────────────┤
│ Attach │ message         Send │
└───────────────────────────────┘
```
- Чат + preview ассетов + progress-bar. Без сложного редактора.

---

## 22. M1–M10 Roadmap

- **M1 Runtime + Client** — ComfyClient (HTTP API) + RuntimeInfo. Тест: `/system_stats`,`/object_info`,`/queue` живого ComfyUI.
- **M2 Asset Layer** — AssetStore + Asset. Тест: файл → Asset.
- **M3 Capability + Workflow Registry** — manifest+workflow; фильтр по capability+runtime+inputs. Тест: resolve `image.generate` → AVAILABLE workflow.
- **M4 Execution chain (ядро, БЕЗ LLM)** — WorkflowEngine + Operator + WS + JobManager + Verifier. **Реальный txt2img E2E** + **архитектурный media-agnostic тест** (declared-only `video.generate` роутится тем же pipeline без изменения ядра).
- **M5 Provider / Model** — Provider Registry + Model catalog (`/object_info`), бинд model slot → чекпоинт (дефолт `cyberrealistic_v80`).
- **M6 Real Video E2E** — `video.generate` исполнимый workflow; реальный video-E2E доказан на remote ComfyUI (Colab, Tesla T4) → локальный AssetStore.
- **M6.5 Image Input / img2img** — `image.edit` исполнимый workflow (`workflows/img2img`, реальный ComfyUI graph: LoadImage → VAEEncode → KSampler → VAEDecode → SaveImage). Закрыт gap AD-23: `asset_inputs.image` (kind=image) декларативно связывает Asset → ComfyUI input; video Asset → INPUT_INCOMPATIBLE. Media-agnostic (тот же WorkflowEngine/Job/Verifier/Asset).
- **M7 Conversation Context (скрипт, без LLM)** — многоходовой контекст поверх Agent/Asset/Execution: `ConversationContext` (media-agnostic: только id/строки) + `ConversationAgent` (session-scoped). `active_asset` резолвит «её/теперь/ещё» в предыдущий результат; `asset_inputs` резолвятся по приоритету explicit > active_asset > reference (AD-23, без транскодинга). `lineage(B)==[B,A]` доказан chain-тестом (generate → image.edit на active_asset). ✓
- **M8 Agent + LLM** — реализован: `Agent` + `HeuristicPlanner` + `LLMPlanner` (OpenRouter), multi-backend catalog, asset inputs.
- **M9 UI** — минимальный чат + preview + progress (SSE) — `app/ui.py` (stdlib http.server, без новых зависимостей): `GET /` (чат+preview), `POST /turn` → `ConversationAgent.turn` (фоновый поток), `GET /events` (SSE: start→status→result/error), `GET /asset/<id>` (preview), `GET /api/session` (контекст). Честный progress = переходы состояния Job (без fake-процентов). ✓
- **M10 Validation** — реальный ComfyUI + реальный workflow + реальная модель + реальный результат, цепь §6, **без mock**.
- **M11 Prompt Builder + Dynamic Prompt Suggestions** — триуровневая архитектура: `HeuristicPromptBuilder` (offline) + `LLMPromptBuilder` (online, OpenAI-compatible) + `CompositePromptBuilder` (fallback orchestration). Интеграция с Planner (Agent.generate + ConversationAgent.turn). AD-30/31/32 соблюдены. Архитектурный freeze.
- **M12 Real UI E2E** — `ComfyUIProcessManager` (lifecycle) + UI использует `CompositePromptBuilder` по умолчанию + реальный `/turn` execution + SSE progress + Browser E2E + multi-turn context + session isolation. Архитектурный freeze.
- **M12.1 ComfyCLI Optional Infrastructure Adapter** — `ComfyCLIAdapter` (version, stop_port, validate_workflow, system_info, env_info, model_list, free_memory) + `ComfyCLIResult`. Полностью опциональный (AD-34): отсутствие comfy-cli не блокирует execution path. shell=True запрещён (AD-33). Не интегрирован в Agent/ConversationAgent/WorkflowEngine (diagnostics only).
- **M13 Execution History + Retry** — `ExecutionHistory` (JSONL persistence per capability) + `RetryPolicy` (max_attempts, backoff) + `classify_error` (transient vs permanent). Job retry loop in Agent.generate + ConversationAgent.turn. SSE events: retry_started, retry_completed.
- **M14 Semantic Verification** — `SemanticVerifier` (vision model via OpenAI-compatible API, score-based pass/fail with configurable threshold). Integrates into WorkflowEngine.execute post-output.
- **M15 Persistent Context** — `SessionManager` (JSONL per session) + auto-save after each turn. Session restoration on reconnect. Cross-turn context survival.
- **M16 Adaptive Planner** — `AdaptivePlanner` learns from ExecutionHistory: preferred params per capability (AD-36: per-capability threshold ≥3, cross-capability isolation). Fallback to HeuristicPlanner when history insufficient.
- **M17 User Feedback** — `FeedbackStore` (rating 1-5, JSONL) + feedback-aware planning (AdaptivePlanner uses ratings to weight preferences). UI endpoint POST /api/feedback.
- **M18 Multi-Step Chain** — `TaskDecomposer` (keyword-based, no LLM) + `ExecutionChain` (callback-based, sequential). Complex request → subtasks → sequential execution with per-step retry. Cancel support.
- **Mx (future)** — audio real E2E (deferred, external Sonilo 401).

---

## 23. Definition of Done

M4 считается готовым только если:
```text
[✓] реальный ComfyUI (127.0.0.1:8188)
[✓] реальный workflow (txt2img@версия)
[✓] реальная модель (cyberrealistic_v80)
[✓] POST /prompt → prompt_id
[✓] WebSocket-мониторинг (progress/executed)
[✓] completion через history
[✓] output скачан (/view)
[✓] Asset создан (role=output)
[✓] Verifier прошёл
[✓] media-agnostic тест (video.generate@версия) зелёный — ядро не трогалось
    (этот тест ДОКАЗЫВАЕТ отсутствие image-specific coupling; он НЕ доказывает реальную генерацию видео)
[✓] тест зелёный (без mock)
[✗] реальный video E2E — НЕ входит в M4 (отдельный milestone Mx)
```

Каждый M* имеет свой чек-лист DoD в производных документах.

---

## 24. Architectural Decisions (принятые)

> Решения, предложенные инженером и принятые как baseline (см. историю проектирования) + уточнения по ревью v0.2.

- **AD-01 Provider ≠ Execution Backend.** Модель разделяет `Provider` и `ExecutionBackend`; v1 — `comfyui` → `local_comfyui` (1:1, но концептуально разделены).
- **AD-02 Asset Transport вынесен из WorkflowEngine.** WorkflowEngine чистый (logical→node/field); загрузку ассета делает `Provider.upload_asset`, возвращая `backend_ref`. WorkflowEngine не знает про `/upload/image|video`.
- **AD-03 Media-agnostic core.** Ни Agent/Operator/Job/WorkflowEngine/Verifier не ветвятся по media-типу.
- **AD-04 Manifest-маппинг.** Логич. параметры/ассеты маппятся в node/field через manifest; LLM видит только логику.
- **AD-05 Workflow Lifecycle.** `DISCOVERED→VALIDATED→AVAILABLE|UNAVAILABLE` (+ `UNKNOWN`) с диагностируемыми причинами.
- **AD-06 (пересмотрено, AD-19) v1 формулировка.** «v1 валидируется на image-workflows, но ядро media-agnostic с самого начала; video capability/workflow укладываются в те же контракты без изменения ядра.»
- **AD-07 No-WAN coupling.** `capability=video.generate`; конкретная модель — свойство workflow/provider-конфигурации, не архитектуры.
- **AD-08 LLM через OpenAI-совместимый endpoint, конфигурируемый** (`LLM_BASE_URL`/`LLM_API_KEY`, дефолт `fallback_proxy :20130`). Не хардкод.
- **AD-09 Model = свойство Provider.** Модели перечисляются из `/object_info`; слот `required_models` биндится к доступному чекпоинту. Дефолт `cyberrealistic_v80`.
- **AD-10 Multi-stage = цепь Job.** Один `Job` = один `POST /prompt`. Pipeline через несколько запусков = несколько Job с lineage.
- **AD-11 Selection policy.** Compatibility Filter → Workflow Selection Policy (приоритет + явный оверрайд `workflow`).
- **AD-12 Custom-node фильтр.** `required_custom_nodes` сверяется с `/object_info`; отсутствует → UNAVAILABLE, Agent сообщает.
- **AD-13 Lineage хранится на Asset+Job.** `source_asset`/`created_from` + `AssetStore.lineage()`.
- **AD-14 No-LLM-first.** M1–M4 реализуются и проверяются БЕЗ LLM.
- **AD-15 Storage.** `data/assets` + `data/assets.jsonl` + `static/assets`; path confinement.
- **AD-16 Real E2E only.** Финальная валидация (M10) — только на реальном ComfyUI, без mock (video-E2E — отдельный milestone).
- **AD-17 (OAQ-01) Version pinning.** `ExecutionPlan` фиксирует `workflow_id@version`. Registry может знать `latest`, но план — всегда конкретная версия для воспроизводимости старых Job.
- **AD-18 (OAQ-02) UNKNOWN ≠ AVAILABLE.** Lifecycle добавляет `UNKNOWN/DEGRADED`; KNOWN+compatible→AVAILABLE, KNOWN+incompatible→UNAVAILABLE, UNKNOWN→не AVAILABLE (только осознанный override оператора).
- **AD-19 (OAQ-06) Cancellation.** `CANCELLED`: partial backend-outputs могут существовать; v1 discard без гарантии «ComfyUI ничего не создал».
- **AD-20 (OAQ-08/09) Temp ownership.** Cleanup temp только после подтверждения backend-ом (signal safe-to-cleanup); не удалять по возврату `backend_ref`, пока backend может читать.
- **AD-21 (OAQ-10) Capability-aware limits.** Глобальный `MAX_UPLOAD_BYTES` + per-workflow `limits` (duration/width/height/sequence).
- **AD-22 (OAQ-13) Selection split.** Candidate Selection (Workflow Registry) отделён от Workflow Selection Policy (финальный выбор); Provider НЕ выбирает workflow; Workflow Registry НЕ «умный агент».
- **AD-23 (OAQ-14) Input compatibility.** Compatibility Filter учитывает доступные ассеты + типы + обязательные inputs.
- **AD-24 (NQ-01) latest-selection.** `latest` = максимальная доступная VALIDATED/AVAILABLE semver-версия `workflow_id`; используется только на candidate/selection. ExecutionPlan всегда фиксирует `workflow_id@version`; Job никогда не ссылается на `latest`.
- **AD-25 (NQ-02) limits semantics.** `null`/отсутствие = unlimited; `0` = запрещено; positive = max-лимит. `0` не является alias для unlimited.
- **AD-26 (NQ-03) BackendRef abstraction.** `BackendRef{provider, backend, reference, metadata}`; ComfyUI-specific `reference={filename,subfolder,type}` внутри backend-specific, не универсальный контракт. Другой backend — своя форма `reference`.
- **AD-27 (S-01) DECLARED_ONLY.** Манифест с `declared_only:true` объявляет capability без исполняемого `workflow.json`; НЕ в AVAILABLE; только для архитектурных тестов (media-agnostic M4). Никакого fake/stub `workflow.json`. **Уточнение (M6, 2026-08-30):** механизм сохранён, но `video.generate` и `audio.generate` больше НЕ DECLARED_ONLY — их исполнимые `workflow.json` реализованы; Video E2E доказан реально (M6). **Уточнение (M6.5, 2026-08-30):** `image.edit` (img2img) также исполним (реальный ComfyUI graph с LoadImage/VAEEncode), AD-23 закрыт декларативным `asset_inputs.image`. DECLARED_ONLY применяется только для будущих capability, ещё не имеющих workflow (напр. `image.upscale`).
- **AD-28 (doc hierarchy)** См. §26. Производные доки не меняют архитектуру; конфликт → STOP→REPORT→DECISION→UPDATE SOURCE→UPDATE DERIVED→IMPLEMENT. Код не источник истины.
- **AD-30 PromptBuilder boundary/security.** PromptBuilder — отдельный модуль для улучшения промптов (`user text → quality prompt`), НЕ заменяет Planner (`user intent → capability/workflow`). PromptBuilder не имеет доступа к FS или ComfyUI; получает только декларативный контекст (строки и идентификаторы). Никаких bytes, файлов, путей, внутренних объектов ComfyUI.
- **AD-31 PromptBuilder не выбирает capability.** PromptBuilder улучшает текст промпта, но НЕ решает "image.generate или image.edit?". Выбор capability — исключительная ответственность Planner. PromptBuilder может использоваться UI напрямую через `/api/prompt/suggest` (MVP) или опционально интегрироваться в Planner/ConversationAgent (future scope).
- **AD-32 PromptBuilder сохраняет исходное намерение.** Улучшенный prompt должен содержать исходное намерение пользователя. `original_preserved` flag проверяется. Исходный пользовательский текст НИКОГДА не уничтожается автоматически без явного выбора пользователя.
- **AD-33 ComfyCLI: shell=True запрещён.** Все subprocess-вызовы через `ComfyCLIAdapter` обязаны использовать `shell=False`. Тест `test_no_shell_true` проверяет это на уровне кода через AST-анализ.
- **AD-34 ComfyCLI: отсутствие comfy-cli не блокирует execution path.** `ComfyCLIAdapter` полностью опциональный. `is_available()` возвращает `False` при отсутствии comfy-cli; все методы возвращают `ComfyCLIResult(ok=False, ...)` с ошибкой. Основной execution path (`ComfyClient` + `WorkflowEngine`) не зависит от CLI. Не используется в `Agent`, `ConversationAgent`, `WorkflowEngine`, `Provider`, `AssetStore`.

---

## 25. Open Architectural Questions

> Подняты ДО кода. Все вопросы закрыты (решения — в AD). Нерешённых архитектурных вопросов, блокирующих M1: **0**.

### Решено в v0.2 (перешли в AD)
- **OAQ-01 → AD-17** version pinning (`workflow_id@version` в ExecutionPlan).
- **OAQ-02 → AD-18** UNKNOWN ≠ AVAILABLE (lifecycle UNKNOWN/DEGRADED).
- **OAQ-06 → AD-19** cancellation semantics (discard без гарантии).
- **OAQ-08/09 → AD-20** temp ownership lifecycle (cleanup по сигналу backend).
- **OAQ-10 → AD-21** capability-aware limits.
- **OAQ-13 → AD-22** selection split (Candidate vs Selection Policy).
- **OAQ-14 → AD-23** input compatibility (assets/types/inputs).
- **OAQ-12** (media-agnostic тест) — согласован; зафиксирован в DoD M4.

### Решено после ревью документации (APPROVED как stances)
- **OAQ-03. Custom nodes** → сверка `required_custom_nodes` с `/object_info`; отсутствие → UNAVAILABLE; автоустановка вне v1 (AD-12).
- **OAQ-04. Идентификация модели** → точное имя файла из runtime; без fuzzy matching; алиасы/semantic — future scope (AD-09).
- **OAQ-05. Workflow validation** → два уровня: (1) validation манифеста, (2) структурная валидация `workflow.json`; не гарантирует успех графа (окончательно — runtime).
- **OAQ-07. Retry** → авто-retry в v1 нет; повтор — новый Job.
- **OAQ-11. Безопасность лок. файлов** → path confinement + mime/ext + traversal-запрет + лимит размера + LLM без FS-доступа (§20).
- **NQ-01 → AD-24** latest = max VALIDATED/AVAILABLE semver; Job не ссылается на latest.
- **NQ-02 → AD-25** limits semantics (null=unlimited, 0=forbidden, positive=limit).
- **NQ-03 → AD-26** BackendRef abstraction.
- **S-01 → AD-27** DECLARED_ONLY — механизм для capability без исполнимого workflow. Исторически применялся к `video_generate` на этапе M4; в M6 `video_generate`/`audio_generate` стали исполнимыми (DECLARED_ONLY снят).
- **S-02** `models.json`/aliases — future scope (архитектурно допустимо, в v1 не реализуется).

### Открытые (не блокируют M1)
нет.

---

## 26. Documentation Hierarchy & Conflict Resolution (AD-28)

Иерархия источников истины:
```text
PROJECT_SPEC.md
    >
docs/00..18_*.md
    >
engineering/*
    >
tasks/*
    >
implementation/code
```

- Производные документы (`docs/00..18`, `engineering/*`, `tasks/*`) **НЕ могут самостоятельно менять архитектурные решения**. Любое решение живёт в `PROJECT_SPEC.md`.
- Код (`implementation/*`) **НЕ является источником истины**. Если код противоречит спеке — правится код, не спека.
- При обнаружении конфликта (в т.ч. в коде):
  ```text
  STOP
  → REPORT DISCREPANCY (поднять вопрос на ревью)
  → ARCHITECTURAL DECISION (зафиксировать AD в PROJECT_SPEC.md)
  → UPDATE SOURCE OF TRUTH (PROJECT_SPEC.md)
  → UPDATE DERIVED DOCS (docs/00..18, engineering/*, tasks/*)
  → IMPLEMENT
  ```
- Не исправлять противоречие молча; не выбирать самостоятельно; не писать код поверх конфликта.

---

## 27. Execution Backend Physical Location (AD-29)

**Решение (2026-08-29): Physical location of ExecutionBackend is not an Agent concern.**

- Удалённый ComfyUI — **штатной Execution Backend**, а не future workaround / костыль для слабого ПК. Локальный и удалённый ComfyUI используют один и тот же `WorkflowEngine`, `Job`, `Verifier`, `Asset`, `ExecutionPlan`.
- `Provider` = логический поставщик capability (напр. `comfyui`); `Backend` = конкретное место/механизм исполнения (`local_comfyui`, `remote_comfyui`, будущий `cloud_comfyui`).
- `ComfyUIProvider` делегирует исполнение конкретному backend-объекту; различия local/remote находятся **ниже Provider/Backend boundary** (transport layer), а не в Engine/Job/Workflow/Asset.
- **Запрещено** `if remote:` / `if localhost:` в domain/execution логике. Физическое расположение backend не влияет на верхние слои.
- Топология: `Agent → Provider → ExecutionBackend`. `ExecutionBackend ∈ {local_comfyui, remote_comfyui, future_cloud_comfyui}`.
- Инварианты (audit M1–M4, 2026-08-29):
  1. `COMFY_URL` — параметр `ComfyClient`, не архитектурное предположение о localhost.
  2. `Provider` работает с local и remote endpoint (один код).
  3. HTTP и WebSocket поддерживают remote endpoint (`ws→wss` для `https` — минимальное исправление в transport layer).
  4. `client_id` коррелирует Job независимо от физического backend.
  5. Job не считается потерянным при временном разрыве WS — восстановление через `/history` (reconnect-safe).
  6. `/history` восстанавливает состояние remote Job после reconnect.
  7. Asset upload/download — через HTTP, без предположения о локальной ФС ComfyUI; поддержка больших файлов.
  8. `Asset.path` — путь Agent/AssetStore, не путь на удалённом ComfyUI.
  9. `BackendRef.reference` — backend-local reference, никогда не глобальный Asset identity.
  10. `RuntimeInfo` описывает конкретный ExecutionBackend, а не глобальную машину Agent.
  11. Workflow compatibility вычисляется для конкретного backend (его ComfyUI version/accelerator/VRAM/models/custom nodes).
  12. Один Agent в будущем выбирает между несколькими ExecutionBackend (defer до multi-backend).
  13. Никаких `if remote:` / `if localhost:` в domain/execution.

---

## Appendix A — Real-World Scenarios

### Scenario 1 — Text → Image
```text
Текст: "киберпанк девушка"
 → Capability: image.generate
 → Provider: comfyui / Backend: local_comfyui
 → Workflow: txt2img@1.0.0
 → Execution → Verification → image Asset (image_001)
```

### Scenario 2 — Image edit
```text
Image (image_001) + Text: "сделай блондинкой"
 → Capability: image.edit
 → Workflow: img2img@x.y.z (input asset = image_001)
 → image Asset (image_002, source_asset=image_001)
```

### Scenario 3 — Image → Video
```text
Image (image_001) + Text: "оживи как видео"
 → Capability: video.image_to_video
 → Workflow: image_to_video@x.y.z (input asset = image_001)
 → video Asset (video_001)
```

### Scenario 4 — Video → Video
```text
Video (video_001) + Text: "камера медленнее"
 → Capability: video.video_to_video
 → Workflow: video_to_video@x.y.z (input asset = video_001)
 → video Asset (video_002, source_asset=video_001)
```

### Scenario 5 — Multi-asset + Text (input compatibility, AD-23)
```text
Image A + Image B + Text: "совмести в одной сцене"
 → Capability: image.generate (или custom.execute)
 → Workflow с двумя asset_inputs (A, B) — выбран потому что оба image доступны
 → Output Asset (image_003)
```

### Scenario 6 — Lineage chain (Job → Asset → Job → Asset)
```text
Asset (image_001)
 → Job J1 (image.generate) → image_002
 → Job J2 (video.image_to_video, input=image_002) → video_001
 → Job J3 (video.upscale, input=video_001) → video_002
```
Lineage: `image_001 → image_002 → video_001 → video_002` (через `source_asset`/`created_from`).

---

*Конец спецификации v0.2 (APPROVED, обновлено 2026-09-01: M1–M18 все реализованы и заморожены. Audio real E2E deferred (Sonilo 401). Hardening pass completed: TD-1..TD-4 closed, 374 tests collected, 81+ prompt builder passed, core tests green. PermissionError from pytest tmp_path sandbox is environment limitation, not code defect). Documentation baseline: PROJECT_SPEC.md + docs/00..20 + engineering/* + workflows/{txt2img,video_generate,img2img,upscale,audio_generate}. M1–M18 frozen; next step — M19 Production Hardening & Execution Observability (pending author approval).*
