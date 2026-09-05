# M25 Architecture Review

**Дата:** 2026-09-04
**Статус:** CRITICAL REVIEW — перед принятием решения
**Основа:** `docs/M25_ARCHITECTURE_PROPOSAL.md` (DRAFT FOR APPROVAL)
**Режим:** READ-ONLY — production-код не менять

---

## 1. Проверка `chain_id`

### 1.1 Существующие идентификаторы

| Идентификатор | Файл | Scope | Persistence |
|---------------|------|-------|-------------|
| `session_id` | `ConversationContext` | Вся сессия (multi-turn, multi-chain) | JSONL |
| `prompt_id` | `Job` / `ExecutionRecord` | Одна ComfyUI POST /prompt | JSONL |
| `chain_step_index` | `Job` / `ExecutionRecord` | Порядковый номер шага в цепочке | JSONL |
| `capability` | `ExecutionRecord` | Тип операции (cross-chain) | JSONL |

### 1.2 Проблема `chain_step_index`

`chain_step_index` — это **orphan ordinal**. Он говорит "это шаг 1", но НЕ говорит "шаг 1 **цепочки X**."

```python
# Две разные цепочки, обе с chain_step_index=1:
ExecutionRecord(prompt_id="aaa", chain_step_index=1, capability="image.edit")  # Цепочка A
ExecutionRecord(prompt_id="bbb", chain_step_index=1, capability="image.edit")  # Цепочка B
# Невозможно отличить chain_step_index=1 цепочки A от chain_step_index=1 цепочки B
```

`ExecutionHistory.get_attempts(chain_step_index=0)` возвращает **ВСЕ** step-0 записи из **ВСЕХ** цепочек.

### 1.3 Дублирует ли `chain_id`?

| Идентификатор | Отличается от `chain_id`? | Почему |
|---------------|--------------------------|--------|
| `session_id` | Да | Сессия содержит несколько цепочек (multi-turn) |
| `prompt_id` | Да | Каждый шаг = отдельный prompt_id |
| `chain_step_index` | Да | Только ordinal, без grouping key |
| `capability` | Да | Cross-chain aggregation, не chain scope |

### 1.4 Что теряется без `chain_id`

| Операция | Без chain_id | С chain_id |
|----------|-------------|------------|
| "Покажи все шаги цепочки X" | Невозможно | `get_by_chain(chain_id)` |
| "Успешность цепочки X" | Невозможно | Агрегация по chain_id |
| "Длительность цепочки X" | Невозможно | Sum step durations |
| "Повторно выполнить цепочку X" | Невозможно | Идентификация failed chain |
| "Experience для цепочки X" | Невозможно | chain_id = primary key |

### 1.5 Решение

**KEEP** — `chain_id: str | None = None` в `ExecutionRecord` и `Job`.

**Обоснование:** `chain_step_index` orphan ordinal не решает проблему группировки. `chain_id` — это foreign key, который anchored `chain_step_index` values к конкретной цепочке. Нулевое семантическое дублирование с существующими identifiers.

**Единственный source of truth:** `ExecutionChain.execute()` генерирует `chain_id` (UUID) в начале, проставляет в каждый `Job` и `ExecutionRecord`.

---

## 2. Проверка модели Sequence

### 2.1 Четыре варианта

| Вариант | Описание |
|---------|----------|
| A | Отдельная domain entity (`ImageSequence` class) |
| B | Структура внутри `ChainContext` |
| C | Relation между Asset через `source_asset` |
| D | Metadata на существующих entities |

### 2.2 Анализ каждого

**Option A: Отдельная entity**
- Требует новый класс + persistence (JSONL) + store
- Дублирует `ConversationContext.assets` (set всех output IDs)
- Дублирует `ConversationContext.messages[].outputs` (per-turn outputs)
- Нарушает P5 (Asset-first): "Sequence = Asset group, не separate entity"
- **Вердикт: REJECT**

**Option B: Внутри ChainContext**
- `ChainContext` — transient по design (chain.py:36: "transient state, not persistent")
- `ChainContext.active_asset` — single string, перезаписывается каждый шаг
- Нарушает layered responsibility: Execution layer не должен own Context data
- **Вердикт: REJECT**

**Option C: Через `source_asset` chain**
- `source_asset` = single parent pointer (один parent на asset)
- Моделирует derivation (A → B → C), НЕ grouping (A, B, C)
- Если 3 images загружены пользователем — `source_asset=None` для всех
- Невозможно представить "эти 3 images — batch для видео"
- **Вердикт: REJECT**

**Option D: Metadata на существующих entities**
- `Asset.metadata` — уже есть, уже persistence-ится в JSONL
- `ConversationContext.messages[]` — уже append-only, уже persistence-ится
- `AssetStore.ingest()` уже принимает `metadata=dict`
- Zero new persistence файлов
- Полная reconstructability
- **Вердикт: BEST OPTION**

### 2.3 Единственный source of truth для Sequence

**Source of truth: `ConversationContext.messages[]`** с полем `sequence_assets: list[str]`.

`Asset.metadata` — дополнительные данные (frame ordering), но НЕ primary source.

Почему:
- `messages[]` уже содержит ordered turn history
- `messages[]` уже persistence-ится через SessionManager
- `sequence_assets` — естественное расширение существующей структуры
- `Asset.metadata` — redundant supplementary data, не primary

### 2.4 Решение

**MODIFY** — принять Option D, но уточнить source of truth:

- **Primary:** `ConversationContext.messages[type=sequence_complete].sequence_assets`
- **Supplementary:** `Asset.metadata[sequence_id, sequence_order, sequence_total]`
- **NEVER:** Отдельный `ImageSequence` class или `sequences.jsonl`

---

## 3. Проверка `SequenceExperience + ChainExperience`

### 3.1 Реальные отличия

| Аспект | ChainExperience | SequenceExperience |
|--------|----------------|-------------------|
| Scope | Одна цепочка execution | Группа images → video |
| Steps | Ordered SubTasks | Ordered Assets |
| Persistence | Per-chain JSONL | Per-sequence JSONL |
| Данные | Params, workflow, corrections, state | Image params, video params, temporal |

### 3.2 Два разных жизненных цикла?

**ChainExperience:** Цепочка SubTasks (generate → edit → upscale). Каждый шаг = ExecutionRecord. Lifespan = время выполнения chain.

**SequenceExperience:** Группа images (Image₁, Image₂, Image₃) → video. Это **cross-chain** concept: images могут быть сгенерированы в разных turns/chains. Lifespan = время от первого image до video.

### 3.3 Можно ли объединить?

**Да.** SequenceExperience — это частный случай ChainExperience, где:
- Все шаги = `image.generate` или `image.edit`
- Последний шаг = `video.image_to_video`
- Assets = ordered list из chain steps

НоSequenceExperience содержит **дополнительные поля** которых нет в ChainExperience:
- `temporal_consistency` (from SemanticVerifier)
- `image_to_video_transition` (quality assessment)
- `video_params` (отдельно от image params)

### 3.4 Решение

**ONE ENTITY** — `ChainExperience` как primary. `SequenceExperience` как **computed view** (не отдельная persistence модель).

```python
@dataclass
class ChainExperience:
    chain_id: str
    session_id: str
    intent: str
    timestamp: float
    steps: list[ChainStepExperience]
    # Summary
    total_duration: float
    overall_state: str
    # Sequence-specific (computed, not separate persistence)
    sequence_assets: list[str] | None = None  # ordered image IDs (if applicable)
    temporal_consistency: float | None = None
    animation_quality: str | None = None
```

**Persistence:** Один JSONL файл `data/experience/{chain_id}.jsonl`. Sequence-specific поля = `None` если chain не является sequence→video.

**Чего НЕ нужно:**
- Отдельный `SequenceExperience` class
- Отдельный `data/experience/sequences/` directory
- Вторая persistence модель

---

## 4. Проверка Temporal Verification

### 4.1 Deterministic checks (без AI)

| Проверка | Статус сегодня | Нужен новый код? |
|----------|---------------|-----------------|
| Порядок кадров | Нет | Да, но trivial (sequence_order metadata) |
| Количество кадров | Нет | Да, trivial (len(sequence_assets)) |
| Наличие assets | **Да** (Verifier.verify()) | Нет |
| Dimensions | Нет | Требует Pillow (не в проекте) |
| Format | **Частично** (_validate_output_bytes) | Расширить |
| Continuity metadata | Нет | Trivial (metadata check) |
| Missing frames | Нет | Trivial (len check) |

**Вывод:** Most deterministic checks trivial. Dimensions требует Pillow — новый dependency.

### 4.2 Semantic/visual checks (с AI)

**Текущий SemanticVerifier:**
- Отправляет **ОДНО** изображение в vision model
- `previous_output_path` в сигнатуре, но **НИКОГДА не передаётся** вызывающим кодом
- Даже при передаче — только **filename** в тексте, НЕ изображение
- Промпт: "оценка качества" — temporal концепций нет

**Что нужно для temporal:**
- Отправить **2+ изображения** в vision model
- Новый промпт для temporal consistency
- Wiring `previous_output_path` в callers
- Новые поля в `SemanticVerificationResult`

### 4.3 Вывод

| Уровень | Что можно | Сложность |
|---------|-----------|-----------|
| Deterministic | Порядок, количество, existence | Trivial |
| Semi-deterministic | Dimensions, histogram | Требует Pillow |
| Semantic | Identity, scene, drift, coherence | Требует multi-image + new prompt + caller changes |

**Решение:** M25.3 должен включать **только deterministic checks**. Semantic temporal verification — отдельный milestone (M26+), требующий:
1. Multi-image input в SemanticVerifier
2. Новый temporal prompt
3. Wiring в callers
4. Тестирование на реальных sequence→video

**Не делать в M25:** Fake "temporal AI verifier" формально выдающий score без реального multi-image анализа.

---

## 5. Проверка `multi: true`

### 5.1 Полный путь asset input

```
Manifest (asset_inputs)
  → validate_manifest()          # валидация schema
  → load_workflow()              # парсинг в AssetInput dataclass
  → validate_workflow_structure() # проверка node existence
  → Agent.resolve_asset_inputs() # resolution: role → asset_id
  → ExecutionPlan.asset_bindings # role → asset_id
  → WorkflowEngine.execute()     # upload + build_prompt
  → Provider.upload_asset()      # single file upload
  → build_prompt()               # _set_field(node, field, filename)
```

### 5.2 Где происходит mapping

| Шаг | Формат на входе | Формат на выходе | Single/Multi |
|-----|-----------------|------------------|-------------|
| `AssetInput` | `{node, field, kind}` | `AssetInput(node, field, kind)` | Single |
| `resolve_asset_inputs()` | `{role: spec}` | `{role: asset_id}` | Single |
| `plan.asset_bindings` | `dict[str, str]` | `role → asset_id` | Single |
| `execute()` upload | `plan.asset_bindings.items()` | `role → BackendRef` | Single |
| `build_prompt()` | `asset_refs[role]` | `node.field = filename` | Single |
| `Provider.upload_asset()` | `Asset` | `BackendRef` | Single |
| `ComfyClient.upload_image()` | `file_path: str` | `{name, subfolder, type}` | Single |

**Каждый шаг предполагает single asset per role.**

### 5.3 Критическая проблема с `_set_field()`

```python
def _set_field(prompt, node, field, value) -> None:
    node_obj.setdefault("inputs", {})[field] = value
```

Если `value` = `["file1.png", "file2.png"]`, ComfyUI интерпретирует это как **node link** `["node_id", output_index]`, а НЕ как batch filenames. Это **SLUSTAET** ComfyUI prompt format.

### 5.4 Правильный подход для multi-image в ComfyUI

**Нельзя:** Set one field to a list of filenames.

**Нужно:**
1. Upload N файлов
2. Каждый файл → отдельный `LoadImage` node
3. Все `LoadImage` nodes → `ImageBatch` node
4. `ImageBatch` → `KSampler`

**Манифест должен описывать:**
```json
{
  "asset_inputs": {
    "images": {
      "multi": true,
      "load_node_template": "10",
      "batch_node": "20",
      "batch_field": "image",
      "kind": "image",
      "max_count": 16
    }
  }
}
```

Где:
- `load_node_template` — ID node-шаблона для каждого LoadImage
- `batch_node` — ID ImageBatch node
- `batch_field` — field в batch node для подключения

### 5.5 Решение

**MODIFY** — `multi: true` необходим, но подход к ComfyUI integration требует уточнения:

1. **`AssetInput.multi: bool`** — ✅ KEEP
2. **`AssetInput.max_count: int`** — ✅ KEEP
3. **Новые поля для batch node mapping** — ADD:
   - `load_node_template: str | None` — node ID template для каждого LoadImage
   - `batch_node: str | None` — ImageBatch node ID
   - `batch_field: str | None` — field name в batch node
4. **`build_prompt()` multi logic** — должен создавать N LoadImage nodes + ImageBatch connections, НЕ пытаться set list в one field
5. **Обратная совместимость** — `multi=false` (default) → текущее поведение без изменений

---

## 6. Проверка Image → Video

### 6.1 Архитектурный контракт

```
video.image_to_video
  → CapabilityRegistry: media_input=("image", "video"), media_output="video"
  → WorkflowRegistry: select → video_image_to_video workflow
  → Manifest: asset_inputs.images (multi, batch)
  → WorkflowEngine: upload N images → build prompt with batch nodes
  → Provider: upload_asset() × N
  → ComfyUI: LoadImage×N → ImageBatch → KSampler → VAEDecode → CreateVideo → SaveVideo
  → Output: video Asset
```

### 6.2 Какие входы реально нужны

| Input | Тип | Источник |
|-------|-----|----------|
| `images` | list[Asset] (ordered) | ConversationContext.sequence_assets |
| `prompt` | str | PromptBuilder |
| `fps` | int | params |
| `steps` | int | params |
| `seed` | int | params |

### 6.3 Нужен ли sequence как input type?

**Нет.** Sequence — это **metadata**, не input type. Workflow принимает `images: list[Asset]`. Sequence ordering определяется через `Asset.metadata.sequence_order`.

### 6.4 Mapping sequence → workflow input

```python
# ConversationAgent._execute_chain_step():
sequence_assets = get_sequence_assets(chain_ctx)  # ordered list of asset IDs
input_assets = {"images": [{"asset_id": aid} for aid in sequence_assets]}
```

### 6.5 Какие данные возвращаются

```python
# Video Asset
Asset(
    id="...",
    type="video",
    path="...",
    source_asset=sequence_assets[-1],  # last image
    metadata={
        "sequence_id": "...",
        "fps": 4,
        "frame_count": 3,
        "temporal_consistency": None,  # filled after verification
    }
)
```

### 6.6 Решение

**APPROVE** — контракт корректен. Key implementation detail: `build_prompt()` должен создавать batch nodes, не пытаться set list в one field.

---

## 7. Проверка Experience → Planner

### 7.1 Текущий интерфейс AdaptivePlanner

```python
class AdaptivePlanner:
    def plan(self, request: str, context: PlanContext) -> PlanResult:
        # Читает из ExecutionHistory:
        #   - get_successful(capability) → list[ExecutionRecord]
        #   - record.params → frequency analysis
        #   - record.workflow_id@version == context.active_workflow
        #   - FeedbackStore ratings >= 4
```

**PlanContext (M9.1 FROZEN):**
```python
@dataclass
class PlanContext:
    active_asset_type: Optional[str] = None
    capabilities: tuple[str, ...] = ()
    active_workflow: Optional[str] = None
    previous_prompt: Optional[str] = None
```

### 7.2 Нужны ли изменения PlanContext?

**НЕТ.** PlanContext — frozen M9.1. Любое изменение = arch decision.

**Альтернатива:** Experience потребляется через расширения ExecutionHistory, не через PlanContext.

### 7.3 Как Experience reaches Planner

```
ExecutionRecord (extended: chain_id, input_assets, prompt_original)
  ↓
ExecutionHistory.get_successful(capability, chain_id=...)
  ↓
HistoryAnalytics.preferred_params_for_chain(capability, chain_id)
  ↓
AdaptivePlanner._context_aware_preferred_params(capability, context)
  └─ chain_id可以从最近них ExecutionRecords извлечь, без PlanContext
```

**Или:** `AdaptivePlanner.__init__` принимает optional `ExperienceStore` (аналог FeedbackStore).

### 7.4 Как избежать permanent rules

| Механизм | Сегодня | С Experience |
|----------|---------|-------------|
| Threshold gating | ≥3 successful attempts | Остаётся |
| Frequency threshold | count ≥ 2 | Остаётся |
| Override precedence | explicit params > preferred | Остаётся |
| Recency blindness | No temporal weighting | Может ухудшиться |

**Риск:** Experience может ampl biases. Если chain A с images→video показала "steps=15 хорошо", это НЕ означает "steps=15 всегда хорошо".

**Mitigation:** Experience фильтруется по chain context, не используется глобально. `preferred_params_for_chain(chain_id)` — контекстно-специфично.

### 7.5 Решение

**APPROVE** — Experience → Planner через ExecutionHistory extensions + optional ExperienceStore dependency. **НЕ через PlanContext changes.**

---

## 8. Главный Lifecycle

### Intent → Prompt₁ → Asset₁ → Prompt₂ → Asset₂ → ... → Sequence → Video → Result → Experience

| Transition | Existing Mechanism | Proposed Extension | Missing |
|------------|-------------------|-------------------|---------|
| **Intent → Prompt** | `PromptBuilder.build(PromptContext)` | — | — |
| **Prompt → Asset** | `WorkflowEngine.execute()` → `AssetStore.ingest()` | — | — |
| **Asset → Next Prompt** | `ConversationContext.active_asset` + `resolve_asset_inputs()` | — | — |
| **Asset → Asset (lineage)** | `Asset.source_asset` + `AssetStore.lineage()` | — | — |
| **Assets → Sequence** | **НЕТ** | `ConversationContext.messages[].sequence_assets` | Sequence grouping logic |
| **Sequence → Video** | **НЕТ** | `video.image_to_video` workflow + `multi` batch input | Workflow + batch support |
| **Video → Result** | `Job.output_assets` → `AssetStore.ingest()` | — | — |
| **Result → Experience** | **НЕТ** | `ChainExperience` from ExecutionHistory | Experience builder |
| **Experience → Planning** | **НЕТ** | `AdaptivePlanner` reads chain-filtered history | Chain-aware analytics |

### Пропущенные переходы

1. **Assets → Sequence** — нужна логика группировки (M25.2)
2. **Sequence → Video** — нужен workflow + batch input (M25.2)
3. **Result → Experience** — нужен builder (M25.4)
4. **Experience → Planning** — нужен chain-aware analytics (M25.4)

---

## 9. Проверка минимальности M25

| Proposal Item | Existing Mechanism | Necessary? | Decision |
|---------------|-------------------|------------|----------|
| `chain_id` в ExecutionRecord | `chain_step_index` (orphan ordinal) | **YES** | **KEEP** — grouping key, не дублирует |
| Sequence model | `Asset.metadata` + `ConversationContext.messages` | **YES** | **MODIFY** — Option D (metadata), primary = messages |
| `multi: true` в asset_inputs | Single `AssetInput(node, field, kind)` | **YES** | **MODIFY** — добавить batch node mapping |
| ChainExperience | `ExecutionHistory` (per-step) | **YES** | **MODIFY** — one entity, sequence as computed view |
| SequenceExperience | **Нет** | **NO** | **REMOVE** — merged into ChainExperience |
| Temporal verification (deterministic) | `Verifier.verify()` (existence/type) | **YES** | **KEEP** — trivial checks |
| Temporal verification (semantic) | `SemanticVerifier` (single-image) | **NO** | **REMOVE** — requires multi-image, defer to M26 |
| video.image_to_video workflow | `video.generate` (text-only) | **YES** | **KEEP** — new workflow, same engine |
| Experience persistence | `ExecutionHistory` (per-step) | **YES** | **MODIFY** — chain-level JSONL |
| Experience → Planner | `AdaptivePlanner` reads history | **YES** | **MODIFY** — chain-aware analytics |
| PlanContext changes | M9.1 FROZEN | **NO** | **REMOVE** — use ExecutionHistory path |
| Pillow dependency | **Нет** | **NO** | **REMOVE** — no image processing in M25 |
| New persistence files | JSONL pattern | **YES** | **MODIFY** — one dir `data/experience/`, not two |

---

## 10. Итог

### APPROVED (из proposal)

1. **`chain_id` в ExecutionRecord** — grouping key, zero duplication, necessary for chain-level analytics
2. **Option D для Sequence** — metadata on existing entities, no new persistence
3. **`multi: true` для asset_inputs** — batch support with proper ComfyUI node mapping
4. **video.image_to_video workflow** — new workflow, same execution engine
5. **ChainExperience** — one entity with sequence fields, not two
6. **Deterministic temporal checks** — trivial, no AI needed
7. **Experience → Planner via ExecutionHistory extensions** — no PlanContext changes

### MODIFIED (изменить в proposal)

1. **Sequence model** — уточнить: primary source of truth = `ConversationContext.messages[]`, not `Asset.metadata`
2. **`multi: true`** — добавить batch node mapping fields (`load_node_template`, `batch_node`, `batch_field`), не просто flag
3. **ChainExperience** — объединить с SequenceExperience, sequence as computed view
4. **Temporal verification** — только deterministic checks, semantic defer to M26
5. **Experience persistence** — один `data/experience/` directory, не два
6. **PlanContext** — НЕ трогать (M9.1 frozen), интеграция через ExecutionHistory

### REMOVED (убрать из proposal)

1. **SequenceExperience как отдельная entity** — merged into ChainExperience
2. **Semantic temporal verification** — requires multi-image SemanticVerifier, defer to M26
3. **PlanContext changes** — M9.1 frozen, use ExecutionHistory path
4. **Pillow dependency** — no image processing in M25
5. **`data/experience/sequences/` directory** — one directory, not two

### M25 MINIMAL SCOPE

**M25.1 — Chain Tracking:**
- `chain_id: str | None` в `ExecutionRecord` + `Job`
- `ExecutionHistory.get_by_chain(chain_id)`
- `ExecutionHistory.get_chain_summary(chain_id)`
- `_on_chain_step_complete()` generates + stamps chain_id
- Tests

**M25.2 — Sequence + Batch:**
- `AssetInput` extensions: `multi`, `max_count`, `load_node_template`, `batch_node`, `batch_field`
- `build_prompt()` multi logic: N LoadImage nodes + ImageBatch
- `resolve_asset_inputs()` list support
- `workflows/video_image_to_video/manifest.json` + `workflow.json`
- Sequence metadata in `ConversationContext.messages[]`
- Tests

**M25.3 — Deterministic Temporal Checks:**
- Sequence ordering validation
- Frame count validation
- Asset existence in sequence
- Integration with Verifier
- Tests

**M25.4 — Experience:**
- `ChainExperience` dataclass (with sequence fields)
- `ExperienceStore` JSONL persistence
- `build_chain_experience()` from ExecutionHistory
- Chain-aware analytics in `HistoryAnalytics`
- Optional `ExperienceStore` dependency in `AdaptivePlanner`
- Tests

### M25 NON-GOALS

| Что НЕ делаем | Почему |
|---------------|--------|
| Semantic temporal verification | Требует multi-image SemanticVerifier, M26+ |
| PlanContext changes | M9.1 frozen |
| Pillow dependency | Нет image processing в M25 |
| SequenceExperience as separate entity | Merged into ChainExperience |
| `data/experience/sequences/` | One directory |
| Experience → Planner automatic parameter changes | Only statistics, not rules |
| Cross-session analytics | Требует shared ExecutionHistory |
| Temporal consistency correction | Only verification, not correction |
| ML / fine-tuning / RAG | NG2/NG3 |

### OPEN QUESTIONS

| Вопрос | Почему нельзя решить сейчас |
|--------|---------------------------|
| Какой именно ComfyUI batch node использовать? | Требует проверки на реальном ComfyUI (VHS ImageBatch vs LoadImageBatch) |
| Какой temporal prompt эффективен? | Требует multi-image SemanticVerifier + тестирования |
|跨-session experience aggregation? | Требует shared ExecutionHistory (design decision) |
| Temporal consistency threshold? | Требует empirical data на реальных sequences |
| Sequence ordering:strict vs loose? | Требует E2E testing с реальными workflows |

### FINAL RECOMMENDATION

**READY FOR IMPLEMENTATION** — с модификациями выше.

Proposal в целом корректен. Ключевые изменения:
1. Убрать SequenceExperience как отдельную entity (merged)
2. Убрать semantic temporal verification (M26)
3. Убрать PlanContext changes (frozen)
4. Уточнить batch node mapping для ComfyUI
5. Один persistence directory

M25 MINIMAL SCOPE: 4 phases, ~700 LOC + tests + 1 workflow.

---

*Review завершён. Production-код не изменён. Ожидается решение по M25.*
