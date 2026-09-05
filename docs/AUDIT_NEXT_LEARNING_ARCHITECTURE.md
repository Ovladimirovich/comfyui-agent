# AUDIT — Next Learning Architecture

**Дата аудита:** 2026-09-04
**Цель:** Определить фактическое состояние архитектуры для поддержки цепочки Image Sequence → Video и извлечения опыта
**Статус:** READ-ONLY AUDIT — никаких изменений production-кода

---

## 1. Current Architecture

### 1.1 Execution Pipeline (фактический)

```
User Request
  ↓
HeuristicPlanner.plan() / LLMPlanner.plan()
  ↓ PlanResult(capability, params)
PromptBuilder.build()  →  CompositePromptBuilder  →  HeuristicPromptBuilder / LLMPromptBuilder
  ↓ PromptResult(enhanced_prompt, source, original_preserved)
Agent.prepare()  →  ExecutionPlan(workflow_id, version, params, asset_bindings)
  ↓
WorkflowEngine.execute()
  ├─ Provider.upload_asset()        → BackendRef
  ├─ build_prompt(manifest, plan)   → ComfyUI prompt dict
  ├─ _bind_models()                 → resolved checkpoint
  ├─ ComfyClient.queue_prompt()     → prompt_id
  ├─ ComfyUIWebSocket.track()       → node outputs
  ├─ _validate_output_bytes()       → magic signature check
  ├─ AssetStore.ingest()            → Asset (with lineage)
  └─ Verifier.verify()              → VerificationResult
  ↓
Job(output_assets=[asset_id])
  ↓
ConversationContext.active_asset = asset_id
```

### 1.2 Ключевые компоненты — статус реализации

| Компонент | Файл | Статус | Persistence |
|-----------|------|--------|-------------|
| `Asset` | `app/assets/types.py:41-54` | ✅ EXISTS | JSONL (`data/assets.jsonl`) |
| `AssetStore` | `app/assets/store.py:34-153` | ✅ EXISTS | JSONL + filesystem |
| `AssetStore.lineage()` | `app/assets/store.py:144-153` | ✅ EXISTS | In-memory traversal |
| `ChainContext` | `app/engine/chain.py:30-39` | ✅ EXISTS | **Transient** (destroyed after chain) |
| `ExecutionChain` | `app/engine/chain.py:70-194` | ✅ EXISTS | In-memory |
| `ConversationContext` | `app/conversation.py:38-72` | ✅ EXISTS | JSONL (`data/sessions/`) |
| `ExecutionHistory` | `app/engine/history.py:90-251` | ✅ EXISTS | JSONL (optional) |
| `ExecutionRecord` | `app/engine/history.py:25-78` | ✅ EXISTS | JSONL |
| `PromptBuilder` | `app/prompt/builder.py` | ✅ EXISTS | Stateless |
| `HeuristicPromptBuilder` | `app/prompt/heuristic.py` | ✅ EXISTS | Stateless |
| `LLMPromptBuilder` | `app/prompt/llm.py` | ✅ EXISTS | Stateless |
| `CompositePromptBuilder` | `app/prompt/composite.py` | ✅ EXISTS | Stateless |
| `ExecutionPlan` | `app/engine/plan.py` | ✅ EXISTS | **Transient** (per-turn) |
| `Job` | `app/engine/job.py` | ✅ EXISTS | **Transient** (per-turn) |
| `Verifier` | `app/engine/verifier.py` | ✅ EXISTS | Stateless |
| `SemanticVerifier` | `app/engine/semantic_verifier.py` | ✅ EXISTS | Stateless |
| `RetryPolicy` | `app/engine/retry.py:160` | ✅ EXISTS | Stateless |
| `CorrectionStrategy` | `app/engine/retry.py:69` | ✅ EXISTS | Stateless |
| `FeedbackStore` | `app/context/feedback.py:32-95` | ✅ EXISTS | JSONL per session |
| `AdaptivePlanner` | `app/planner/adaptive.py` | ✅ EXISTS | Stateless (reads History) |
| `Composer` | `app/planner/composer.py` | ✅ EXISTS | Stateless |
| `CapabilityGraph` | `app/planner/capability_graph.py` | ✅ EXISTS | Stateless |
| `WorkflowRegistry` | `app/registry/registry.py` | ✅ EXISTS | In-memory |
| `CapabilityRegistry` | `app/registry/capability.py` | ✅ EXISTS | In-memory |
| `HistoryAnalytics` | `app/engine/analytics.py` | ✅ EXISTS | Stateless |
| `UserPreferences` | `app/planner/preferences.py` | ✅ EXISTS | Stateless |
| `SubTask` | `app/planner/decomposer.py:13-18` | ✅ EXISTS | Transient |

---

## 2. What Already Works

### 2.1 Asset + Lineage (ПОЛНОСТЬЮ РАБОТАЕТ)

**Что реально существует:**
- `Asset` dataclass с полями `source_asset` (parent ID) и `created_from` (Job prompt_id)
- `AssetStore.ingest()` — копирует файл, создаёт Asset с lineage
- `AssetStore.link()` — создаёт derived Asset с explicit lineage edge
- `AssetStore.lineage()` — traverses `source_asset` chain backward

**Какие данные реально записываются:**
```json
{
  "op": "upsert",
  "asset": {
    "id": "a1b2c3...",
    "type": "image",
    "path": "C:\\...\\data\\assets\\a1b2c3\\output.png",
    "mime": "image/png",
    "role": "output",
    "created_from": "prompt_id_xyz",
    "source_asset": "parent_asset_id",
    "created_at": "2026-09-04T..."
  }
}
```

**Где сохраняются:** `data/assets.jsonl` (append-only) + файлы в `data/assets/<uuid>/`

**Восстановление lineage:** `AssetStore.lineage(asset_id)` → `[asset, parent, grandparent, ...]`

### 2.2 ConversationContext (ПОЛНОСТЬЮ РАБОТАЕТ)

**Что реально существует:**
- `messages: list[dict]` — append-only история всех turns
- `assets: set[str]` — все output asset IDs
- `active_asset: str` — последний успешный output
- `parameters: dict` — параметры последнего turn
- `workflows: set[str]` — все использованные workflow@version

**Какие данные записываются per turn:**
```python
{
    "turn": "request text or capability",
    "capability": "image.generate",
    "workflow": "txt2img@1.0.0",
    "job": "prompt_id_xyz",
    "outputs": ["asset_id_1", "asset_id_2"],
    "active_asset": "asset_id_1",
    "attempt": 1,
}
```

**Где сохраняется:** JSONL файл `data/sessions/{session_id}.jsonl`

**Между-turn links:** `active_asset` turn N → input для turn N+1

### 2.3 ExecutionHistory (РАБОТАЕТ, NO PERSISTENCE BY DEFAULT)

**Что реально существует:**
- `ExecutionRecord` — полный audit trail: prompt_id, capability, params, workflow, state, duration, error, attempt, output_assets, chain_step_index, corrections_applied
- `ExecutionHistory` — append-only коллекция с JSONL persistence (optional)
- Фильтры: get_attempts, get_successful, get_failed, get_by_prompt_id
- Агрегация: success_rate, avg_duration, count

**Какие данные записываются per execution:**
```python
{
    "prompt_id": "xyz",
    "capability": "image.generate",
    "params": {"prompt": "a cat", "steps": 20, "width": 512},
    "workflow_id": "txt2img",
    "workflow_version": "1.0.0",
    "state": "SUCCESS",
    "duration": 3.2,
    "output_assets": ["asset_id"],
    "attempt": 1,
    "chain_step_index": null,
    "corrections_applied": null,
    "timestamp": 1725446400.0
}
```

**Где сохраняется:** In-memory + optional JSONL

### 2.4 Prompt Evolution (РАБОТАЕТ, BUT LIMITED)

**Что реально существует:**
- `PromptContext.original_text` → `PromptResult.enhanced_prompt`
- `PromptResult.source` (heuristic / llm / heuristic_fallback)
- `PromptResult.original_preserved` (AD-32 intent preservation)
- `PromptResult.original_prompt` (preserved original)
- `previous_prompt` передаётся между turns

**Чего НЕ хватает:**
- Prompt evolution **не записывается** в ExecutionHistory
- PromptResult не persist-ится отдельно
- Нельзя восстановить "какой prompt привёл к какому результату"

### 2.5 AdaptivePlanner + Analytics (РАБОТАЕТ, LIMITED BY HISTORY)

**Что реально существует:**
- `AdaptivePlanner` учится из ExecutionHistory (≥3 successful attempts per capability)
- `HistoryAnalytics.preferred_params()` — агрегирует параметры успешных попыток
- `HistoryAnalytics.workflow_success_rates()` — успешность по workflow
- `FeedbackStore` + feedback-weighted analytics
- `UserPreferences` — context-aware preferred params (фильтрует по capability + workflow)

**Чего НЕ хватает:**
- History per-session, не cross-session
- History in-memory by default (optional JSONL)
- Нет анализа «какие изображения хорошо переходят в видео»

### 2.6 Composer + CapabilityGraph (РАБОТАЕТ)

**Что реально существует:**
- `CapabilityGraph` — BFS search от available_types к target capability
- `Composer.compose()` — находит shortest path через capabilities
- `CompositionResult` — chain of SubTasks + alternatives
- `MAX_CHAIN_LENGTH = 5`

**Пример paths:**
```
image.generate → image.edit       (output=image ∈ input=image) ✅
image.generate → image.upscale    (output=image ∈ input=image) ✅
image.generate → video.image_to_video (output=image ∈ input=(image,video)) ✅
video.generate → video.upscale    (output=video ∈ input=video) ✅
```

### 2.7 RetryPolicy + CorrectionStrategy (РАБОТАЕТ)

**Что реально существует:**
- `CorrectionStrategy.adjust_fn(params, semantic_score) → adjusted_params`
- Встроенные стратегии: adjust_steps_down, adjust_steps_up, adjust_timeout, adjust_image_size_down, adjust_cfg
- `RetryDecision` с action/delay/suggestions/param_adjustments
- `RetryPolicy.decide()` —Decision logic с учётом error_class, attempt, feedback

---

## 3. What Data Is Already Captured

### 3.1 Per Execution (ExecutionRecord)
| Поле | Что записывается | Где |
|------|-----------------|-----|
| `prompt_id` | Уникальный ID попытки | JSONL |
| `capability` | image.generate / video.generate / ... | JSONL |
| `params` | prompt, steps, width, height, cfg, ... | JSONL |
| `workflow_id` | txt2img / img2img / video_generate / ... | JSONL |
| `workflow_version` | 1.0.0 | JSONL |
| `state` | SUCCESS / FAILED / CANCELLED | JSONL |
| `duration` | Секунды | JSONL |
| `error_message` | Текст ошибки | JSONL |
| `error_class` | transient / permanent / verification | JSONL |
| `attempt` | Номер попытки | JSONL |
| `output_assets` | Список asset IDs | JSONL |
| `chain_step_index` | Индекс в цепочке (M18) | JSONL |
| `corrections_applied` | Какие стратегии применялись (M23) | JSONL |
| `backend_execution_identity` | Кто выполнял (M20) | JSONL |

### 3.2 Per Asset (Asset)
| Поле | Что записывается | Где |
|------|-----------------|-----|
| `id` | UUID hex | JSONL |
| `type` | image / video / audio / sequence / ... | JSONL |
| `path` | Абсолютный путь к файлу | JSONL |
| `mime` | MIME тип | JSONL |
| `metadata` | **Пустой `{}`** — ничего не записывается | JSONL |
| `role` | input / output / reference | JSONL |
| `created_from` | prompt_id Job | JSONL |
| `source_asset` | ID parent asset (lineage edge) | JSONL |
| `created_at` | ISO timestamp | JSONL |

### 3.3 Per Conversation Turn (ConversationContext.messages)
| Поле | Что записывается | Где |
|------|-----------------|-----|
| `turn` | Request text или capability | JSONL session |
| `capability` | Выбранная capability | JSONL session |
| `workflow` | workflow@version | JSONL session |
| `job` | prompt_id | JSONL session |
| `outputs` | List of asset IDs | JSONL session |
| `active_asset` | Последний успешный asset | JSONL session |
| `attempt` | Номер финальной попытки | JSONL session |

---

## 4. Actual Image → Image Sequence → Video Flow

### 4.1 Что СЕГОДНЯ возможно

**Сценарий A: Генерация одного изображения**
```
User: "a cat on a windowsill"
  → Planner: image.generate
  → PromptBuilder: "a cat on a windowsill, photorealistic, detailed"
  → WorkflowEngine → ComfyUI → output.png
  → Asset(type="image", source_asset=None)
  → ConversationContext.active_asset = asset_id
```
✅ Работает. Lineage: one-to-one.

**Сценарий B: Цепочка image.generate → image.edit → image.upscale**
```
Turn 1: "a cat" → image.generate → Asset₁
Turn 2: "add a hat" → image.edit (input=Asset₁) → Asset₂ (source_asset=Asset₁)
Turn 3: "upscale" → image.upscale (input=Asset₂) → Asset₃ (source_asset=Asset₂)
```
✅ Работает. Lineage: Asset₃ → Asset₂ → Asset₁.

**Сценарий C: Цепочка через ExecutionChain (M18)**
```
Composer.compose("image.upscale", params, available_types={"image"})
  → [SubTask("image.generate"), SubTask("image.upscale")]
  → ExecutionChain.execute([SubTask1, SubTask2])
  → ChainContext.active_asset переключается на каждом шаге
```
✅ Работает. Chain tracking через ChainStep + ExecutionRecord.

### 4.2 Что НЕ возможно сегодня

**Сценарий D: Image Sequence → Video**
```
User: "make a video from these 3 images"
  → ??? НЕТ capability для batch image input
  → video.image_to_video: declared, но НЕТ workflow
  → video.generate: НЕ принимает image input (asset_inputs={})
```
❌ **Невозможно.** Три блокера:

1. **Нет batch asset input:** `asset_inputs` маппит role →单一 (node, field, kind). Нет机制 для "this role expects N images"
2. **Нет workflow для video.image_to_video:** Capability зарегистрирована, но `workflows/video_image_to_video/` не существует
3. **Нет sequence metadata на Asset:** `metadata` dict пуст — нет frame_index, sequence_order, fps, duration

### 4.3 Что можно восстановить сегодня

Из **существующих данных** можно восстановить:

| Что | Как | Через что |
|-----|-----|-----------|
| Какой prompt привёл к какому asset | `Asset.created_from` → `ExecutionRecord.params["prompt"]` | AssetStore + ExecutionHistory |
| Какой workflow использовался | `Asset.created_from` → `ExecutionRecord.workflow_id` | AssetStore + ExecutionHistory |
| Какие параметры были | `ExecutionRecord.params` | ExecutionHistory |
| Какие ошибки возникали | `ExecutionRecord.error_message/error_class` | ExecutionHistory |
| Какие коррекции применялись | `ExecutionRecord.corrections_applied` | ExecutionHistory |
| Цепочка lineage | `AssetStore.lineage(asset_id)` → `[asset, parent, grandparent]` | AssetStore |
| История.turn() | `ConversationContext.messages` | ContextPersistence |
| Успешность по capability | `HistoryAnalytics.success_rate(capability)` | ExecutionHistory |
| Preferred params | `HistoryAnalytics.preferred_params(capability)` | ExecutionHistory |

**Что НЕ можно восстановить:**

| Что | Почему |
|-----|--------|
| "Какие изображения хорошо переходят в видео" | Нет данных о.sequence.images → video результатах |
| "Temporal consistency между кадрами" | Нет temporal metadata, нет сравнения |
| "Какие параметры image.generate → video" | History фильтруется по capability, не по chain |
| "Какие corrections нужны были для video" | video.image_to_video не существует |

---

## 5. Existing Lineage / History / Context

### 5.1 Связи между данными

```
ConversationContext
  ├─ messages[] ← каждый turn = {capability, workflow, job, outputs}
  ├─ active_asset ← последний успешный output
  ├─ assets{} ← все output IDs
  └─ parameters ← параметры последнего turn
        │
        ↓ (job → ExecutionRecord)
ExecutionHistory
  ├─ ExecutionRecord(prompt_id, capability, params, workflow, state, duration, ...)
  │     │
  │     ↓ (output_assets → Asset IDs)
  └─ AssetStore
        ├─ Asset(id, type, path, source_asset, created_from)
        └─ lineage() → [Asset, parent, grandparent, ...]
```

### 5.2 ChainContext vs ConversationContext

**ChainContext** (transient):
- Создаётся на время выполнения цепочки SubTasks
- `active_asset` переключается на каждом шаге
- `workflows_used` накапливает workflow@version
- **Уничтожается после цепочки** — данные переносятся в ConversationContext через `_on_chain_step_complete`

**ConversationContext** (persistent):
- Хранит полную историю всех turns
- `messages` — append-only list of dicts
- `active_asset` — интер-turn link
- **Persist-ится в JSONL** через SessionManager

### 5.3 ExecutionChain → ConversationContext handoff

```python
# conversation.py, _on_chain_step_complete:
ctx.active_task = step.subtask.capability
ctx.active_workflow = f"{manifest.id}@{manifest.version}"
ctx.active_job = step.job.prompt_id
ctx.active_asset = step.job.output_assets[0] if step.job.output_assets else ctx.active_asset
ctx.assets.update(step.job.output_assets)
ctx.jobs.add(step.job.prompt_id)
ctx.workflows.add(f"{manifest.id}@{manifest.version}")
ctx.messages.append({
    "type": "chain_step",
    "chain_index": index,
    "capability": step.subtask.capability,
    "workflow": f"{manifest.id}@{manifest.version}",
    "job": step.job.prompt_id,
    "outputs": list(step.job.output_assets),
    "state": step.state.value,
})
```

---

## 6. Missing Information

### 6.1 Для анализа последовательности изображений

| Недостающее | Почему важно | Как补える |
|-------------|-------------|----------|
| **Image sequence concept** | Нужно知道 "image1 + image2 + image3 = sequence" | Новый Asset type или metadata.frames[] |
| **Batch asset input** | asset_inputs не поддерживает N images | Расширить manifest schema |
| **Frame ordering metadata** | Нужен порядок images в sequence | Asset.metadata.frame_index |
| **Sequence → Video workflow** | video.image_to_video declared, не executable | Создать workflows/video_image_to_video/ |
| **Cross-turn chain history** | ExecutionHistory фильтруется по capability, не по chain | Добавить chain_id в ExecutionRecord |

### 6.2 Для последующего видео

| Недостающее | Почему важно | Как补える |
|-------------|-------------|----------|
| **Temporal consistency data** | Нет данных о temporal quality | SemanticVerifier с temporal prompt |
| **Frame-level verification** | Verifier проверяет только existence/type | Расширить verify() для sequences |
| **Animation quality metrics** | Нет feedback о video quality | Расширить FeedbackStore для video |
| **Image params → Video result** | Нет correlation между image params и video quality | New analytics dimension |

---

## 7. M24.1 STOP / SUPERSEDED Decision

**Статус:** M24.1 (Test Maintenance + Doc Resync) из PROJECT_STATE.md — это **unit/integration level** задача, не связанная с Learning Architecture.

**Для M25+ Learning Architecture:**
- M24.1 не является prerequisite
- Learning Architecture может строиться поверх существующих компонентов
- Не требует изменения M1–M12

---

## 8. Proposed Experience Model

### 8.1 Архитектурная модель (без реализации)

**Ключевой принцип:** Experience = данные + события + связи. Не отдельный LearningEngine.

```text
Experience Layer (поверх существующих компонентов)
  │
  ├─ ChainExperience
  │    chain_id: str
  │    session_id: str
  │    steps: list[ChainStepExperience]
  │    intent: str (original request)
  │    final_result: str (asset_id)
  │    total_duration: float
  │    overall_state: str
  │
  ├─ ChainStepExperience
  │    step_index: int
  │    capability: str
  │    input_asset: str
  │    output_asset: str
  │    params: dict
  │    workflow_id: str
  │    duration: float
  │    state: str
  │    error: str | None
  │    corrections: list[dict]
  │
  ├─ SequenceExperience
  │    sequence_id: str
  │    assets: list[str] (ordered)
  │    video_asset: str | None
  │    temporal_consistency: float | None
  │    animation_quality: float | None
  │    image_params_used: dict
  │    video_params_used: dict
  │
  └─ LearningQuery
       "given intent X, what params/workflow worked?"
       "given images [A,B,C], what video params worked?"
       "what corrections were needed for video.generate after image.generate?"
```

### 8.2 Связь с существующими компонентами

| Experience Component | Существующий источник | Gap |
|---------------------|----------------------|-----|
| `ChainExperience.steps` | `ExecutionRecord.chain_step_index` + `ExecutionHistory` | Нужно group records by chain |
| `ChainStepExperience.params` | `ExecutionRecord.params` | ✅ Уже есть |
| `ChainStepExperience.corrections` | `ExecutionRecord.corrections_applied` | ✅ Уже есть |
| `SequenceExperience.assets` | `ConversationContext.messages[].outputs` | Нужно group by sequence |
| `SequenceExperience.temporal_consistency` | **Отсутствует** | Новый SemanticVerifier prompt |
| `SequenceExperience.video_asset` | `AssetStore.lineage()` | ✅ Уже есть |
| `LearningQuery` | `HistoryAnalytics.preferred_params()` | Нужно расширить维度 |

---

## 9. Minimal Architectural Changes

### 9.1 Что НЕ нужно менять

| Что | Почему |
|-----|--------|
| M1–M12 execution chain | Заморожен, работает |
| Asset / AssetStore / Lineage | Поддерживает lineage, JSONL persistence |
| ConversationContext | Поддерживает turn history, active_asset |
| ExecutionHistory | Поддерживает per-execution audit trail |
| PromptBuilder (Heuristic/LLM/Composite) | Работает, stateless |
| WorkflowEngine | Media-agnostic, работает |
| Verifier / SemanticVerifier | Проверяет контракты |
| RetryPolicy / CorrectionStrategy | Автоматические коррекции |

### 9.2 Минимальные изменения (M25)

| # | Изменение | Файл | Обоснование |
|---|-----------|------|-------------|
| 1 | **Расширить Asset.metadata** | `app/assets/types.py` | Записывать `width`, `height`, `fps`, `frame_count` при ingest |
| 2 | **Chain tracking в ExecutionHistory** | `app/engine/history.py` | Добавить `chain_id` в ExecutionRecord для группировки |
| 3 | **Sequence support в asset_inputs** | `workflows/*/manifest.json` | Поле `multi: true` + `max_count` для batch inputs |
| 4 | **Sequence-aware WorkflowEngine** | `app/engine/engine.py` | Обработка lists в asset_bindings |
| 5 | **Temporal SemanticVerifier** | `app/engine/semantic_verifier.py` | Prompt для проверки temporal consistency |
| 6 | **SequenceExperience aggregator** | Новый модуль `app/engine/sequence_analytics.py` | Группировка ExecutionRecords по chain/sequence |

### 9.3 Что НЕ нужно (anti-patterns)

| Что | Почему НЕ нужно |
|-----|-----------------|
| Отдельный `LearningEngine` класс | Learning = aggregate statistics из существующих данных |
| Vector DB / RAG | NG2 — запрещено |
| Autonomous learning | NG3 — запрещено |
| Multi-agent | NG1 — запрещено |
| Новая persistence layer | Существующие JSONL sufficiency |
| Изменение M1–M12 | Frozen |

---

## 10. What Must NOT Be Added

Из PROJECT_SPEC §5 (инварианты) и AI_ENGINEER_ONBOARDING:

1. **NG1:** Multi-agent system — запрещено
2. **NG2:** RAG / vector DB — запрещено
3. **NG3:** Autonomous learning / self-reflection — запрещено
4. **AD-03:** Media-ветвление в engine/provider/agent — запрещено
5. **AD-08:** LLM доступ к FS/ComfyUI — запрещено
6. **AD-18:** UNKNOWN → AVAILABLE — запрещено
7. **M1–M12:** Изменение frozen milestones — запрещено без arch decision

---

## 11. M25+ Development Options

### Option A: Minimal Experience Layer (рекомендуется)

**Суть:** Расширить существующие компоненты, не создавая новые абстракции.

**Этапы:**
1. **M25.1:** Chain tracking — `chain_id` в ExecutionRecord, группировка по chains
2. **M25.2:** Sequence support — batch asset inputs, video.image_to_video workflow
3. **M25.3:** Temporal verification — SemanticVerifier с temporal prompt
4. **M25.4:** Experience analytics — расширить HistoryAnalytics для cross-chain queries

**Преимущества:**
- Минимальные изменения существующего кода
- Поверх M1–M12 без их изменения
- Каждый этап независим и тестируем
- Не нарушает инварианты

### Option B: Experience as Event Stream

**Суть:** Каждое действие → event → event store → analytics.

**Преимущества:**
- Полная трассируемость
- Легко расширять

**Недостатки:**
- Двойная запись (ExecutionHistory уже есть)
- Сложнее для single-user v1

### Option C: ExperienceDB (отдельная БД)

**Суть:** PostgreSQL/Redis для experiences.

**Недостатки:**
- NG5 (PostgreSQL/Redis — non-goals)
- Over-engineering для v1

---

## 12. Proposed DoD

### M25.1 Chain Tracking
- [ ] `chain_id` field в `ExecutionRecord`
- [ ] `ExecutionHistory.get_by_chain(chain_id)` method
- [ ] `ConversationContext` сохраняет `chain_id` при chain execution
- [ ] Тесты: group records by chain, reconstruct chain history

### M25.2 Sequence Support
- [ ] `asset_inputs` поддерживает `multi: true`
- [ ] `WorkflowEngine` обрабатывает lists в asset_bindings
- [ ] `workflows/video_image_to_video/manifest.json` + `workflow.json`
- [ ] Capability `video.image_to_video` → AVAILABLE (не UNKNOWN)
- [ ] Тесты: sequence of 3 images → video, lineage check

### M25.3 Temporal Verification
- [ ] `SemanticVerifier` поддерживает temporal consistency check
- [ ] `VerificationResult` включает temporal_score
- [ ] Тесты: verify temporal consistency of image sequence

### M25.4 Experience Analytics
- [ ] `HistoryAnalytics` поддерживает cross-chain queries
- [ ] `preferred_params` фильтрует по chain context
- [ ] Sequence experience aggregation
- [ ] Тесты: query experience across chains

---

## 13. Required Tests

### Unit Tests
- `test_chain_tracking.py` — chain_id grouping, history reconstruction
- `test_sequence_asset.py` — batch asset inputs, sequence metadata
- `test_temporal_verification.py` — temporal consistency checks
- `test_experience_analytics.py` — cross-chain queries

### Integration Tests
- `test_image_to_video_chain.py` — E2E: 3 images → video with lineage
- `test_experience_reconstruction.py` — full experience query

### Architecture Tests
- No changes to M1–M12 frozen components
- No media-branching in engine/provider
- No LLM access to FS/ComfyUI

---

## 14. Ответ на главный архитектурный вопрос

### Вопрос:
> Может ли существующая система уже сохранить и связать историю вида
> `Intent → Prompt₁ → Asset₁ → Prompt₂ → Asset₂ → ... → ImageSequence → Video → Result`
> так, чтобы на следующем запуске эта история могла использоваться для планирования новых изображений?

### Ответ: **ЧАСТИЧНО ДА, С КЛЮЧЕВЫМИ GAP**

**Что УЖЕ работает:**

| Цепочка | Как восстанавливается | Через что |
|---------|----------------------|-----------|
| Intent → Prompt₁ | `ConversationContext.messages[0]["turn"]` + `ExecutionRecord.params["prompt"]` | ContextPersistence + ExecutionHistory |
| Prompt₁ → Asset₁ | `ExecutionRecord.output_assets` + `Asset(created_from=prompt_id)` | ExecutionHistory + AssetStore |
| Asset₁ → Prompt₂ | `ConversationContext.messages[1]["turn"]` | ContextPersistence |
| Prompt₂ → Asset₂ | Same as above | ExecutionHistory + AssetStore |
| Asset₂ → Asset₃ (lineage) | `AssetStore.lineage(asset_id)` → `[asset₃, asset₂, asset₁]` | AssetStore |
| Params that worked | `HistoryAnalytics.preferred_params(capability)` | ExecutionHistory |
| Workflow success rates | `HistoryAnalytics.workflow_success_rates(capability)` | ExecutionHistory |
| What corrections needed | `ExecutionRecord.corrections_applied` | ExecutionHistory |

**Конкретные классы/поля/связи:**
```python
# Восстановление всей цепочки для session:
session_ctx = session_manager.resume(session_id)
for msg in session_ctx.messages:
    if "job" in msg:
        record = history.get_by_prompt_id(msg["job"])
        # record.params = какой prompt/params
        # record.output_assets = какие assets созданы
        # record.workflow_id = какой workflow
        # record.corrections_applied = какие corrections

# Lineage для конкретного asset:
chain = asset_store.lineage(asset_id)
# chain = [asset₃, asset₂, asset₁]
```

**Ключевые GAP:**

| Gap | Влияние | Минимальный fix |
|-----|---------|-----------------|
| **Нет ImageSequence concept** | Невозможно представить "3 images = sequence" | Новый Asset type или metadata.frames[] |
| **Нет batch asset input** | Невозможно подать N images в video workflow | Расширить asset_inputs schema |
| **Нет video.image_to_video workflow** | Capability declared, не executable | Создать workflows/video_image_to_video/ |
| **ChainContext transient** | Chain history не persist-ится отдельно | chain_id в ExecutionRecord + group by |
| **History per-session** | Cross-session analytics невозможны | Shared ExecutionHistory across sessions |
| **Asset.metadata пуст** | Нет image params (width/height) в Asset | Записывать params при ingest |
| **Prompt evolution не записывается** | Нельзя восстановить "какой prompt к какому результату" | PromptResult → ExecutionRecord |

### Минимальный gap для "Image Sequence → Video" с experience:

**Сегодня:** 5 из 8 components работают. Gap = 3 components:
1. Sequence support (batch inputs + metadata)
2. video.image_to_video workflow
3. Chain/sequence tracking в history

**Можно построить поверх:** Asset + Lineage + ConversationContext + ExecutionHistory + ExecutionChain + Composer + AdaptivePlanner + FeedbackStore + SemanticVerifier + RetryPolicy + CorrectionStrategy.

**Не нужно:** Отдельный LearningEngine. Существующие компоненты покрывают 70% потребности. Остальные 30% — расширения существующих модулей.

---

*Этот документ является результатом read-only аудита. Никаких изменений production-кода не производилось.*
