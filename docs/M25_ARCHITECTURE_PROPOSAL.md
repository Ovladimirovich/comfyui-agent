# M25 Architecture Proposal — Experience-Based Media Learning

**Версия:** 1.0 (DRAFT FOR APPROVAL)
**Дата:** 2026-09-04
**Статус:** READ-ONLY PROPOSAL — никаких изменений production-кода
**Основа:** `docs/AUDIT_NEXT_LEARNING_ARCHITECTURE.md` (2026-09-04)

---

## 1. Problem

Система сегодня генерирует изображения и видео, но **не извлекает опыт** из выполнения media workflow. Невозможно ответить на вопросы:

- Какие изображения хорошо переходят в последовательность?
- Какие параметры сохраняют визуальную идентичность?
- Где возникает temporal inconsistency?
- Какие изменения между кадрами работают?
- Какие workflow/model/parameters использовались для успешных цепочек?
- Какие исправления потребовались и почему?
- Какие характеристики изображения помогают последующей анимации?
- Какие характеристики мешают?

**Ключевой принцип:** Не "это плохо", а "в таком контексте это сработало / не сработало". Сегодняшний неудачный результат не должен превращаться в вечный запрет.

### 1.1 Исходные решения (зафиксированы)

- M24.1 Production Feedback Wiring — VERIFIED
- M24.1 rating-based Learning E2E — STOPPED / SUPERSEDED
- Rating-based learning не является целевой моделью обучения
- Новый `LearningEngine` создавать НЕ нужно
- Существующие компоненты переиспользовать

---

## 2. Current Foundation

### 2.1 Что уже работает (из аудита)

| Компонент | Файл | Что делает | Persistence |
|-----------|------|------------|-------------|
| `Asset` + lineage | `app/assets/types.py:41-54` | `source_asset` chain, `created_from` Job ID | JSONL |
| `AssetStore.lineage()` | `app/assets/store.py:144-153` | Traverses chain backward | In-memory from JSONL |
| `ConversationContext` | `app/conversation.py:38-72` | Turn history, `active_asset`, `messages[]` | JSONL per session |
| `ExecutionHistory` | `app/engine/history.py:90-251` | Per-execution audit trail | JSONL (optional) |
| `ExecutionRecord` | `app/engine/history.py:25-78` | params, workflow, state, corrections, chain_step_index | JSONL |
| `PromptBuilder` | `app/prompt/composite.py` | Heuristic/LLM prompt evolution | Stateless |
| `AdaptivePlanner` | `app/planner/adaptive.py` | Learns from history ≥3 successful | Stateless (reads History) |
| `HistoryAnalytics` | `app/engine/analytics.py` | preferred_params, workflow_success_rates | Stateless |
| `Composer` | `app/planner/composer.py` | BFS path through CapabilityGraph | Stateless |
| `CapabilityGraph` | `app/planner/capability_graph.py` | Composability edges | Stateless |
| `RetryPolicy` | `app/engine/retry.py:160` | Auto-corrections via CorrectionStrategy | Stateless |
| `FeedbackStore` | `app/context/feedback.py:32-95` | User ratings per attempt | JSONL per session |
| `Verifier` | `app/engine/verifier.py` | Output contract check | Stateless |
| `SemanticVerifier` | `app/engine/semantic_verifier.py` | Vision-based intent check | Stateless |
| `ExecutionChain` | `app/engine/chain.py:70-194` | Multi-step SubTask execution | In-memory |
| `ChainContext` | `app/engine/chain.py:30-39` | Transient chain state | **Transient** |

### 2.2 Что отсутствует

| Gap | Влияние на целевой сценарий |
|-----|---------------------------|
| Нет ImageSequence concept | Невозможно представить "3 images = sequence" |
| Нет batch asset input | `asset_inputs` =单一 role →单一 node |
| Нет video.image_to_video workflow | Capability declared, не executable |
| ChainContext transient | Chain history не persist-ится отдельно |
| Asset.metadata пуст `{}` | Нет image params в Asset |
| Prompt evolution не записывается | Нельзя "какой prompt → какой результат" |
| History per-session | Cross-session analytics невозможны |

---

## 3. Target Workflow

```text
User Intent: "сделай анимацию кота на подоконнике"
  │
  ▼
Intent₁ → Prompt₁ → Image₁ (image.generate)
  │
  ▼
Intent₂ → Prompt₂ → Image₂ (image.edit, input=Image₁)
  │
  ▼
Intent₃ → Prompt₃ → Image₃ (image.edit, input=Image₂)
  │
  ▼
ImageSequence = [Image₁, Image₂, Image₃]
  │
  ▼
Video (video.image_to_video, input=ImageSequence)
  │
  ▼
Experience:
  chain: [Image₁ → Image₂ → Image₃ → Video]
  params: {prompt, steps, cfg, denoise, fps, ...}
  workflow: txt2img@1.0.0 → img2img@1.0.0 → img2img@1.0.0 → video_i2v@1.0.0
  corrections: [attempt2: steps 20→15 (semantic_score=0.3)]
  temporal_consistency: 0.72
  result_quality: success
```

### 3.1 Два типа цепочек

**Type A — Sequential Chain (существует сегодня):**
```
Image₁ → Image₂ → Image₃
```
Каждый шаг берёт ОДИН предыдущий output как input. ChainContext.active_asset переключается.

**Type B — Batch Sequence → Video (НЕ существует):**
```
[Image₁, Image₂, Image₃] → Video
```
Несколько images как batch input для одного видео workflow. Требует расширения.

---

## 4. Image Sequence Model

### 4.1 Решение: Asset group через metadata, НЕ новый тип

**Не нужно:**
- Новый `ImageSequence` класс
- Новый Asset type `type="sequence"` (объявлен, но не используется)
- Отдельная persistence система

**Решение:**
Sequence = ordered list of Asset IDs, сохраняемый в:
1. `ConversationContext.messages[]` — как `"sequence_assets": [id1, id2, id3]`
2. `Asset.metadata` — как `"sequence_order": 0` (порядок в sequence)

### 4.2 Модель

```python
# В ConversationContext.messages[] (per turn):
{
    "type": "sequence_complete",
    "capability": "video.image_to_video",
    "sequence_assets": ["asset_1", "asset_2", "asset_3"],  # ordered
    "job": "prompt_id_video",
    "outputs": ["video_asset_id"],
    "video_asset": "video_asset_id",
}

# В Asset.metadata (каждый image в sequence):
{
    "sequence_id": "conv_session_123_turn_3",  # group identifier
    "sequence_order": 0,  # 0-based index
    "sequence_total": 3,  # total count
}
```

### 4.3 Связь с существующими компонентами

| Что | Как используется | Изменение |
|-----|-----------------|-----------|
| `Asset.metadata` | Хранит `sequence_id`, `sequence_order`, `sequence_total` | **Extend** — добавить поля при ingest |
| `ConversationContext.messages` | Хранит `"sequence_assets": [ordered ids]` | **Extend** — добавить поле в message dict |
| `AssetStore.lineage()` | Traverses chain для ОДНОГО asset | **Reuse as-is** — каждый image в sequence имеет own lineage |
| `ExecutionRecord` | Записывает каждую image generation | **Reuse as-is** — 3 records для 3 images |
| `ExecutionHistory` | Хранит все попытки | **Reuse as-is** — можно query по chain_step_index |

### 4.4 Где persistence-ится

```
Sequence = [
    ConversationContext.messages[type=sequence_complete].sequence_assets,  ← JSONL session
    Asset.metadata[sequence_id, sequence_order, sequence_total],          ← JSONL assets
]
```

Оба источника уже persistence-ятся в JSONL. Новых файлов не нужно.

---

## 5. Multi-Asset Input

### 5.1 Текущий manifest schema

```json
"asset_inputs": {
    "image": {"node": "10", "field": "image", "kind": "image"}
}
```

Один role → один (node, field, kind). **Нет batch support.**

### 5.2 Расширение: `multi` flag

```json
"asset_inputs": {
    "images": {
        "node": "10",
        "field": "image",
        "kind": "image",
        "multi": true,
        "max_count": 16
    }
}
```

### 5.3 Изменения в коде

| Файл | Что менять | Обоснование |
|------|-----------|-------------|
| `app/registry/workflow.py` | `AssetInput` dataclass — добавить `multi: bool = False`, `max_count: int = 1` | Schema extension |
| `app/registry/workflow.py` | `validate_manifest()` — поддержка `multi` в asset_inputs | Validation |
| `app/engine/engine.py:83` | `build_prompt()` — если `multi`, обработать list asset_refs | Batch binding |
| `app/engine/engine.py:173` | `execute()` — загрузить N assets через Provider | Multi-upload |
| `app/agent.py:400` | `resolve_asset_inputs()` — поддержка lists в assets dict | Resolution |
| `app/conversation.py:637` | `_execute_chain_step()` — multi-asset handoff | Chain step |

### 5.4 Media-agnostic invariant сохраняется

```
build_prompt() для multi:
  for role, bind in manifest.asset_inputs.items():
      if bind.multi:
          refs = asset_refs.get(role, [])  # list of BackendRef
          for i, ref in enumerate(refs):
              _set_field(prompt, bind.node, bind.field, ref.reference["filename"], index=i)
      else:
          ref = asset_refs.get(role)
          if ref:
              _set_field(prompt, bind.node, bind.field, ref.reference["filename"])
```

**Нет ветвления по media-типу.** Логика определяется флагом `multi` в manifest, не типом media.

---

## 6. Image-to-Video Capability

### 6.1 Текущий статус

- `Capability("video.image_to_video", media_input=("image", "video"), media_output="video")` — REGISTERED
- `workflows/video_image_to_video/` — **NOT EXISTS**
- `video.generate` — работает, но `asset_inputs={}` (text-only)

### 6.2 Путь реализации

**M25.2: Создать `workflows/video_image_to_video/`**

```
workflows/video_image_to_video/
├── manifest.json
└── workflow.json
```

**manifest.json:**
```json
{
  "id": "video_image_to_video",
  "version": "1.0.0",
  "capability": "video.image_to_video",
  "provider": "comfyui",
  "backend": "local_comfyui",
  "inputs": {
    "prompt": {"node": "2", "field": "text"},
    "negative_prompt": {"node": "4", "field": "text"},
    "fps": {"node": "7", "field": "fps"},
    "steps": {"node": "5", "field": "steps"},
    "seed": {"node": "5", "field": "seed"}
  },
  "asset_inputs": {
    "images": {
      "node": "10",
      "field": "image",
      "kind": "image",
      "multi": true,
      "max_count": 16
    }
  },
  "outputs": {
    "result": {"node": "8", "kind": "video"}
  },
  "parameters": {
    "fps": {"default": 4, "min": 1, "max": 30},
    "steps": {"default": 20, "min": 1, "max": 60},
    "seed": {"default": 0, "min": 0, "max": 4294967295}
  },
  "required_models": ["checkpoint"],
  "required_custom_nodes": ["CreateVideo", "SaveVideo", "LoadImageBatch"],
  "limits": {
    "max_sequence_length": 16
  }
}
```

**workflow.json:**
```
LoadImageBatch(paths) → VAEEncode(batch) → KSampler → VAEDecode → CreateVideo(fps) → SaveVideo
```

### 6.3 ComfyUI nodes

- `LoadImageBatch` (VHS — Video Helper Suite) — загружает N images по путям
- Или `LoadImagePath` + `ImageBatch` — загружает images по одному и батчит

### 6.4 Единственный execution path

```
Agent.prepare("video.image_to_video", params={fps: 4, steps: 20})
  → WorkflowRegistry.select("video.image_to_video")
  → WorkflowEngine.execute(manifest, plan)
  → Provider.upload_asset(image_1), upload_asset(image_2), ...
  → build_prompt() → multi asset binding
  → POST /prompt → Job → Video Asset
```

**Тот же WorkflowEngine. Тот же Provider. Тот же Job. Нет второго execution path.**

---

## 7. Experience Model

### 7.1 Принцип

**Experience ≠ permanent rule.**
**Experience = факт о выполненном media workflow, сохранённый для последующего анализа.**

Не ML/fine-tuning/vector-RAG. Сначала — **какие факты сохранять**.

### 7.2 Что сохранять (Experience Data Model)

```python
@dataclass
class ChainExperience:
    """Опыт выполнения цепочки media workflow."""
    chain_id: str                          # unique ID
    session_id: str                        # ConversationContext session
    intent: str                            # исходный request пользователя
    timestamp: float                       # время начала

    # Steps
    steps: list[ChainStepExperience]       # ordered steps

    # Summary
    total_duration: float
    overall_state: str                     # COMPLETED / FAILED / PARTIAL
    completed_steps: int
    failed_steps: int

    # Video-specific (заполняется если последний шаг = video)
    temporal_consistency: float | None     # 0.0-1.0
    animation_quality: str | None          # success / poor / inconsistent


@dataclass
class ChainStepExperience:
    """Опыт одного шага цепочки."""
    step_index: int
    capability: str                        # image.generate / image.edit / video.image_to_video
    input_assets: list[str]               # входные asset IDs (для multi = list)
    output_asset: str                      # выходной asset ID
    params: dict                           # prompt, steps, cfg, denoise, ...
    workflow_id: str                       # txt2img / img2img / video_i2v
    workflow_version: str
    duration: float
    state: str                             # SUCCESS / FAILED
    attempt: int                           # номер попытки
    error: str | None
    error_class: str | None                # transient / permanent / verification
    corrections: list[dict] | None         # [{strategy, from_params, to_params}]
    prompt_original: str | None            # AD-32: исходный prompt
    prompt_enhanced: str | None            # после PromptBuilder
    prompt_source: str | None              # heuristic / llm / heuristic_fallback


@dataclass
class SequenceExperience:
    """Опыт создания image sequence → video."""
    sequence_id: str
    image_assets: list[str]                # ordered: [Image₁, Image₂, Image₃]
    video_asset: str | None
    image_params: list[dict]               # params для каждого image
    video_params: dict | None              # params для video
    temporal_consistency: float | None
    image_to_video_transition: str | None  # success / poor / inconsistent
```

### 7.3 Где сохранять

| Data | Источник | Persistence | Новый модуль? |
|------|----------|-------------|---------------|
| `ChainExperience` | ExecutionHistory records + ConversationContext | **New**: `app/engine/experience.py` | ✅ Да |
| `ChainStepExperience` | ExecutionRecord (каждый record = step) | **Extend**: ExecutionRecord | ❌ Нет |
| `SequenceExperience` | ConversationContext.messages + Asset.metadata | **New**: `app/engine/experience.py` | ✅ Да |

### 7.4 Persistence

```
data/experience/
├── chains/
│   ├── {chain_id}.jsonl        # append-only chain experience
│   └── ...
└── sequences/
    ├── {sequence_id}.jsonl     # append-only sequence experience
    └── ...
```

**Append-only JSONL** — тот же паттерн что и `data/assets.jsonl`, `data/sessions/`, `data/feedback/`.

### 7.5 Связь с существующими компонентами

| Experience поле | Существующий источник | Изменение |
|----------------|---------------------|-----------|
| `steps[].params` | `ExecutionRecord.params` | **Reuse** |
| `steps[].corrections` | `ExecutionRecord.corrections_applied` | **Reuse** |
| `steps[].prompt_original` | `Job._original_prompt` | **Extend** — записать в ExecutionRecord |
| `steps[].prompt_enhanced` | `Job._enhanced_prompt` | **Extend** — записать в ExecutionRecord |
| `steps[].workflow_id` | `ExecutionRecord.workflow_id` | **Reuse** |
| `steps[].duration` | `ExecutionRecord.duration` | **Reuse** |
| `steps[].error` | `ExecutionRecord.error_message` | **Reuse** |
| `steps[].state` | `ExecutionRecord.state` | **Reuse** |
| `steps[].attempt` | `ExecutionRecord.attempt` | **Reuse** |
| `image_assets` | `ConversationContext.messages[sequence_assets]` | **Extend** |
| `video_asset` | `ConversationContext.active_asset` (после video step) | **Reuse** |
| `total_duration` | Sum of step durations | **Compute** |

---

## 8. Learning Loop

### 8.1 Три границы

```
┌─────────────────────────────────────────────────────────┐
│                    EXECUTION LAYER                       │
│  WorkflowEngine → Job → Asset → ConversationContext     │
│                                                         │
│  Задача: выполнить media workflow, сохранить результат  │
└────────────────────────────┬────────────────────────────┘
                             │ данные (records, assets, context)
                             ▼
┌─────────────────────────────────────────────────────────┐
│                   EXPERIENCE LAYER                       │
│  ChainExperience / SequenceExperience                    │
│                                                         │
│  Задача: сохранить факт о выполненном workflow           │
│  Что: chain steps, params, corrections, outcome         │
│  Persistence: JSONL                                      │
└────────────────────────────┬────────────────────────────┘
                             │ facts (aggregated queries)
                             ▼
┌─────────────────────────────────────────────────────────┐
│                    PLANNING LAYER                        │
│  AdaptivePlanner → HistoryAnalytics → UserPreferences    │
│                                                         │
│  Задача: использовать опыт для планирования              │
│  Как: preferred_params, workflow_success_rates           │
│  Модель: context + inputs + params + outcome → выбор    │
└─────────────────────────────────────────────────────────┘
```

### 8.2 Как Experience влияет на Planning (M26+)

**Сегодня (без M25):**
```
AdaptivePlanner.plan("a cat")
  →_history.get_successful("image.generate") → preferred_params
  → {"steps": 20, "width": 512}  (statistical average)
```

**После M25 (с Experience):**
```
AdaptivePlanner.plan("a cat")
  → history.get_successful("image.generate")
  → filter by: chain context (images → video?)
  → filter by: temporal_consistency > 0.7
  → preferred_params: {"steps": 15, "width": 512}  (context-aware)
```

**Ключевой сдвиг:**
- Сегодня: `preferred_params(capability)` — статистика по capability
- M25: `preferred_params(capability, chain_context=temporal_optimized)` — контекстный опыт

### 8.3 Не смешивать

| Слой | Ответственность | Не делать |
|------|----------------|-----------|
| Execution | Выполнить workflow, сохранить Asset | Анализировать опыт |
| Experience | Сохранить факт о workflow | Влиять на execution |
| Planning | Использовать опыт для выбора params | Выполнять workflows |

---

## 9. Component Reuse Matrix

| Компонент | Reuse/Extend/New | Что меняется |
|-----------|------------------|--------------|
| `Asset` | **Extend** | `metadata` — добавить sequence_id, sequence_order |
| `AssetStore` | **Reuse** | Ingest, lineage — as-is |
| `AssetStore.ingest()` | **Extend** | Принимать `metadata` param для sequence fields |
| `ConversationContext` | **Extend** | `messages[]` — добавить `sequence_assets`, `chain_id` |
| `ExecutionHistory` | **Reuse** | Query, filter, aggregate — as-is |
| `ExecutionRecord` | **Extend** | Добавить `chain_id`, `prompt_original`, `prompt_enhanced`, `prompt_source` |
| `ExecutionChain` | **Reuse** | Per-step retry, verification — as-is |
| `ChainContext` | **Reuse** | Transient — as-is (handoff в ConversationContext) |
| `ChainStep` | **Reuse** | SubTask, job, state — as-is |
| `PromptBuilder` | **Reuse** | Stateless — as-is |
| `AdaptivePlanner` | **Extend** | Чтение ChainExperience для context-aware params |
| `HistoryAnalytics` | **Extend** | Новые queries: chain-aware, sequence-aware |
| `Composer` | **Reuse** | BFS path — as-is |
| `CapabilityGraph` | **Reuse** | Composability edges — as-is |
| `RetryPolicy` | **Reuse** | CorrectionStrategy — as-is |
| `CorrectionStrategy` | **Reuse** | adjust_fn — as-is |
| `FeedbackStore` | **Reuse** | Ratings — as-is |
| `Verifier` | **Reuse** | Contract check — as-is |
| `SemanticVerifier` | **Extend** | Temporal consistency prompt |
| `WorkflowEngine` | **Extend** | Multi-asset upload + binding |
| `Agent` | **Extend** | resolve_asset_inputs() — list support |
| `TaskDecomposer` | **Extend** | Video keyword detection |
| `WorkflowRegistry` | **Reuse** | Discover, select — as-is |
| `CapabilityRegistry` | **Reuse** | video.image_to_video already registered |
| `NodeBinding` | **Reuse** | As-is |
| `AssetInput` | **Extend** | Добавить `multi: bool`, `max_count: int` |
| `OutputSpec` | **Reuse** | As-is |
| `SubTask` | **Reuse** | As-is |
| `Job` | **Reuse** | As-is |

---

## 10. Minimal Changes

### M25.1 — Chain Tracking (Foundation)

**Цель:** Группировка ExecutionRecords по chains, reconstruction chain history.

| # | Файл | Изменение | LOC |
|---|------|-----------|-----|
| 1 | `app/engine/history.py` | `ExecutionRecord` — добавить `chain_id: str | None = None` | 1 |
| 2 | `app/engine/history.py` | `ExecutionHistory.get_by_chain(chain_id)` — фильтр по chain_id | 8 |
| 3 | `app/engine/history.py` | `ExecutionHistory.get_chain_summary(chain_id)` — агрегация | 15 |
| 4 | `app/conversation.py` | `_on_chain_step_complete()` — генерировать `chain_id` и записывать в records | 5 |
| 5 | `app/engine/chain.py` | `ExecutionChain.execute()` — проставлять `chain_id` в Job | 3 |
| 6 | Tests | `test_chain_tracking.py` | ~60 |

**Итого:** ~92 LOC + tests

### M25.2 — Sequence Support (Image → Video)

**Цель:** Batch asset input, video.image_to_video workflow, sequence metadata.

| # | Файл | Изменение | LOC |
|---|------|-----------|-----|
| 1 | `app/registry/workflow.py` | `AssetInput` — `multi: bool = False`, `max_count: int = 1` | 2 |
| 2 | `app/registry/workflow.py` | `validate_manifest()` — multi validation | 10 |
| 3 | `app/engine/engine.py:83` | `build_prompt()` — multi asset binding | 12 |
| 4 | `app/engine/engine.py:173` | `execute()` — multi upload | 10 |
| 5 | `app/agent.py:400` | `resolve_asset_inputs()` — list support | 15 |
| 6 | `app/conversation.py` | `_execute_chain_step()` — multi-asset handoff | 10 |
| 7 | `workflows/video_image_to_video/manifest.json` | Новый manifest | 35 |
| 8 | `workflows/video_image_to_video/workflow.json` | Новый ComfyUI graph | ~80 |
| 9 | `app/assets/types.py` | `Asset.metadata` — sequence fields (при ingest) | 3 |
| 10 | `app/assets/store.py` | `ingest()` — принимать `metadata` param | 5 |
| 11 | Tests | `test_sequence_asset.py`, `test_video_image_to_video.py` | ~100 |

**Итого:** ~282 LOC + tests + workflow files

### M25.3 — Temporal Verification

**Цель:** Проверка temporal consistency image sequence.

| # | Файл | Изменение | LOC |
|---|------|-----------|-----|
| 1 | `app/engine/semantic_verifier.py` | `verify_temporal_consistency(sequence_assets)` — vision model prompt | 40 |
| 2 | `app/engine/semantic_verifier.py` | `SemanticVerificationResult` — `temporal_score: float | None` | 2 |
| 3 | Tests | `test_temporal_verification.py` | ~40 |

**Итого:** ~82 LOC + tests

### M25.4 — Experience Model

**Цель:** Сохранение и запрос опыта.

| # | Файл | Изменение | LOC |
|---|------|-----------|-----|
| 1 | `app/engine/experience.py` | `ChainExperience`, `ChainStepExperience`, `SequenceExperience` dataclasses | 60 |
| 2 | `app/engine/experience.py` | `ExperienceStore` — JSONL persistence | 50 |
| 3 | `app/engine/experience.py` | `build_chain_experience()` — из ExecutionHistory + ConversationContext | 40 |
| 4 | `app/engine/experience.py` | `build_sequence_experience()` — из ConversationContext | 30 |
| 5 | `app/conversation.py` | `_on_chain_step_complete()` — вызвать `build_chain_experience()` | 10 |
| 6 | Tests | `test_experience.py` | ~80 |

**Итого:** ~270 LOC + tests

---

## 11. Architectural Invariants (сохраняются)

| ID | Инвариант | Статус M25 |
|----|-----------|------------|
| P1 | Media-agnostic core | ✅ `multi` flag определяется manifest, не media-тип |
| P2 | Declarative workflow | ✅ Batch inputs в manifest, не в коде |
| P3 | Layered responsibility | ✅ Execution ≠ Experience ≠ Planning |
| P4 | Provider ≠ Backend | ✅ Provider.upload_asset() — as-is |
| P5 | Asset-first | ✅ Sequence = Asset group, не отдельная сущность |
| P6 | No-LLM-first verification | ✅ SemanticVerifier — optional, после execution |
| P7 | Real E2E only | ✅ Тесты на реальном ComfyUI |
| P8 | Extensibility without rewrite | ✅ manifest extension, не core rewrite |
| P9 | Reproducibility | ✅ ExecutionRecord фиксирует всё |
| P10 | UNKNOWN ≠ AVAILABLE | ✅ video.image_to_video → UNKNOWN до создания workflow |
| AD-03 | Нет media-ветвления в engine | ✅ `multi` flag — declarative |
| AD-08 | LLM не имеет доступа к FS | ✅ Experience = JSONL, не FS access |
| AD-18 | UNKNOWN ≠ AVAILABLE | ✅ Workflow required |
| AD-28 | Doc Hierarchy | ✅ PROJECT_SPEC > код |
| NG1 | Нет multi-agent | ✅ One Agent, One Planner |
| NG2 | Нет RAG / vector DB | ✅ JSONL + in-memory analytics |
| NG3 | Нет autonomous learning | ✅ Aggregate statistics, не self-modification |

---

## 12. Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| `LoadImageBatch` node не установлен в ComfyUI | video_i2v workflow не executable | Fallback: чекнуть required_custom_nodes при discover |
| Multi-asset upload превышает VRAM | ComfyUI OOM | `limits.max_count` в manifest, проверка при select |
| Sequence ordering丢失 | Неправильный порядок кадров | `sequence_order` в metadata, strict ordering |
| Experience JSONL растёт бесконечно | Disk usage | Не в v1 — future: archival/cleanup |
| Temporal verification неточный | False positives/negatives | Threshold tuning, human review fallback |

---

## 13. M25 Implementation Plan

### Phase 1: M25.1 Chain Tracking (1-2 дня)
1. Добавить `chain_id` в ExecutionRecord
2. Реализовать `get_by_chain()`, `get_chain_summary()`
3. Генерировать chain_id в _on_chain_step_complete
4. Тесты: group records, reconstruct chain

### Phase 2: M25.2 Sequence Support (3-5 дней)
1. `AssetInput.multi` + manifest validation
2. `build_prompt()` multi binding
3. `execute()` multi upload
4. `resolve_asset_inputs()` list support
5. Создать `workflows/video_image_to_video/`
6. Тесты: sequence → video E2E

### Phase 3: M25.3 Temporal Verification (1-2 дня)
1. `verify_temporal_consistency()` в SemanticVerifier
2. Temporal score в VerificationResult
3. Тесты: temporal checks

### Phase 4: M25.4 Experience Model (2-3 дня)
1. Experience dataclasses
2. ExperienceStore JSONL persistence
3. `build_chain_experience()`, `build_sequence_experience()`
4. Интеграция с ConversationAgent
5. Тесты: experience creation + query

### Итого: 7-12 дней

---

## 14. Tests / E2E Proof

### Unit Tests

| Тест | Что проверяет |
|------|--------------|
| `test_chain_tracking.py` | chain_id grouping, get_by_chain, get_chain_summary |
| `test_sequence_asset.py` | Multi-asset ingest, sequence metadata, ordering |
| `test_video_image_to_video.py` | Manifest validation, workflow discovery |
| `test_temporal_verification.py` | Temporal consistency scoring |
| `test_experience.py` | ChainExperience creation, SequenceExperience, JSONL persistence |
| `test_multi_asset_binding.py` | build_prompt with multi assets |
| `test_resolve_multi.py` | resolve_asset_inputs with lists |

### Integration Tests

| Тест | Что проверяет |
|------|--------------|
| `test_image_to_video_chain.py` | E2E: 3 images → video with lineage |
| `test_experience_reconstruction.py` | Full experience query from history |
| `test_chain_experience_e2e.py` | Chain execution → experience → query |

### E2E (Real ComfyUI)

| Тест | Что проверяет |
|------|--------------|
| `test_video_i2v_real_e2e.py` | Real ComfyUI: images → video via video_i2v workflow |

---

## 15. DoD

### M25.1 Chain Tracking
- [ ] `chain_id` field в `ExecutionRecord` + JSONL
- [ ] `ExecutionHistory.get_by_chain(chain_id)` → list of records
- [ ] `ExecutionHistory.get_chain_summary(chain_id)` → aggregated stats
- [ ] `ConversationContext.messages[]` содержит `chain_id`
- [ ] Тесты: group records by chain, reconstruct chain history

### M25.2 Sequence Support
- [ ] `AssetInput` поддерживает `multi: bool`, `max_count: int`
- [ ] `validate_manifest()` проверяет multi constraints
- [ ] `build_prompt()` обрабатывает list asset_refs
- [ ] `execute()` загружает N assets через Provider
- [ ] `resolve_asset_inputs()` принимает lists
- [ ] `workflows/video_image_to_video/manifest.json` + `workflow.json` существуют
- [ ] Capability `video.image_to_video` → AVAILABLE (не UNKNOWN)
- [ ] `Asset.metadata` содержит sequence fields при ingest
- [ ] Тесты: 3 images → video with lineage

### M25.3 Temporal Verification
- [ ] `SemanticVerifier.verify_temporal_consistency(sequence_assets)` → SemanticVerificationResult
- [ ] `SemanticVerificationResult.temporal_score: float | None`
- [ ] Temporal prompt проверяет visual continuity
- [ ] Тесты: temporal consistency scoring

### M25.4 Experience Model
- [ ] `ChainExperience` dataclass + JSONL persistence
- [ ] `SequenceExperience` dataclass + JSONL persistence
- [ ] `ExperienceStore.record()` / `get_by_chain()` / `get_by_sequence()`
- [ ] `build_chain_experience()` из ExecutionHistory + ConversationContext
- [ ] `build_sequence_experience()` из ConversationContext
- [ ] Интеграция с ConversationAgent (auto-record on chain complete)
- [ ] Тесты: experience creation, persistence, query

---

## 16. Explicit Non-Goals

| Что НЕ входит в M25 | Почему |
|---------------------|--------|
| `LearningEngine` класс | Learning = aggregate statistics, не отдельный модуль |
| ML / fine-tuning | NG3 — autonomous learning запрещён |
| Vector DB / RAG | NG2 — запрещено |
| Multi-agent | NG1 — запрещено |
| Cross-session analytics | Требует shared ExecutionHistory (future) |
| Temporal consistency improvement | Только verification, не correction |
| Animation quality optimization | Only measurement, not optimization |
| Automatic parameter tuning | AdaptivePlanner уже делает это |
| New persistence layer | JSONL sufficiency |
| Changes to M1–M12 | Frozen |
| Production code changes | DRAFT FOR APPROVAL |

---

## 17. Architectural Decisions (для фиксации)

### AD-37: Experience as Data, Not Engine

**Решение:** Experience = JSONL files + in-memory analytics. Не отдельный LearningEngine.
**Обоснование:** Существующие ExecutionHistory + AdaptivePlanner + HistoryAnalytics покрывают 70% потребности. Остальные 30% — расширения существующих модулей.
**Альтернативы отклонены:**
- LearningEngine class — over-engineering для single-user v1
- PostgreSQL/Redis — NG5
- Event stream — двойная запись (ExecutionHistory уже есть)

### AD-38: Sequence as Metadata, Not Type

**Решение:** Image sequence = ordered list of Asset IDs в metadata + ConversationContext. Не новый Asset type.
**Обоснование:** `SEQUENCE = "sequence"` объявлен но не используется. Asset lineage уже поддерживает chains. Sequence = additional metadata поверх существующего lineage.
**Альтернативы отклонены:**
- Новый ImageSequence class — parallel system, не нужен
- `type="sequence"` на Asset — не поддерживает batch input для workflows

### AD-39: Multi-Asset via Manifest Flag

**Решение:** Batch inputs через `multi: true` в `asset_inputs` manifest schema. Не через отдельный execution path.
**Обоснование:** Media-agnostic invariant. `multi` flag — declarative, определяется manifest, не кодом.
**Альтернативы отклонены:**
- Отдельный `execute_batch()` method — second execution path
- `SequenceExecutor` класс — нарушение media-agnostic

### AD-40: Experience Persistence via JSONL

**Решение:** Experience files в `data/experience/chains/` и `data/experience/sequences/`. JSONL append-only.
**Обоснование:** Единый паттерн с `data/assets.jsonl`, `data/sessions/`, `data/feedback/`. Простота, reliability, отсутствие external dependencies.
**Альтернативы отклонены:**
- SQLite — overkill для append-only logs
- PostgreSQL — NG5

---

*Этот документ является DRAFT FOR APPROVAL. Никаких изменений production-кода не производилось.*
