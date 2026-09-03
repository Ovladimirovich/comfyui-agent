# M18 Multi-Step Decomposition — Integration Architecture

**Статус:** VERIFIED (Phase 2, 2026-09-02) — Real E2E validated
**Дата:** 2026-09-02
**Автор:** AI Engineer
**На основе:** PROJECT_SPEC.md, M13_M18_ARCHITECTURAL_DECISION.md (AD-35–AD-39), Phase 1 audit report

---

## 0. Назначение документа

Определить архитектуру интеграции M18 (TaskDecomposer + ExecutionChain) в существующий execution path (`ConversationAgent.turn()`). Документ является **DRAFT FOR APPROVAL** — реализация начинается только после утверждения.

**Ключевое правило:** M18 — additive. Существующий single-step path M1–M12 не меняется.

---

## 1. Decompose → Chain bridge

### 1.1. Когда запрос является multi-step

`ConversationAgent.turn()` определяет multi-step запрос через `TaskDecomposer.decompose()`:

```python
# Внутри turn(), ПЕРЕД выбором planner:
if capability is None and request:
    decomposer = TaskDecomposer()
    subtasks = decomposer.decompose(request)

    if len(subtasks) > 1:
        # MULTI-STEP PATH (M18)
        return self._execute_chain(session_id, subtasks, ...)
    else:
        # SINGLE-STEP PATH (M1–M12, без изменений)
        ...  # существующий код planner → prepare → execute
```

### 1.2. Когда остаётся single-step path

Single-step path сохраняется когда:
- `capability` задан явно (пользователь указал `capability="image.generate"`)
- `request` не содержит conjunctions ("и", "and", ",")
- `decomposer.decompose(request)` возвращает один SubTask

**Гарантия backward compatibility:** обычный запрос `сгенерируй изображение` → `decompose()` → `[SubTask(image.generate)]` → len == 1 → single-step path.

### 1.3. Исключение изменения поведения single-step

```python
# Текущий flow (без изменений):
if capability is None and request:
    ...  # planner → plan_ctx → AdaptivePlanner → result
if capability is None:
    raise AgentError(...)
# ... prepare → execute → return job

# Новый flow (additive):
if capability is None and request:
    decomposer = TaskDecomposer()
    subtasks = decomposer.decompose(request)
    if len(subtasks) > 1:
        return self._execute_chain(...)
    # else: fall through to existing single-step code
```

Ключевой принцип: **new code ПЕРЕД existing, с early return**. Существующий код НЕ обрамляется `else` — он остаётся как fallback.

---

## 2. Asset handoff

### 2.1. Проблема

`ExecutionChain.execute_fn: Callable[[SubTask], Job]` — не передаёт output assets предыдущего step как input следующего.

### 2.2. Решение: `ChainContext`

```python
@dataclass
class ChainContext:
    """Контекст цепочки: хранит промежуточные assets между шагами."""
    session_id: str
    assets: dict[str, str] = field(default_factory=dict)  # role → asset_id
    active_asset: str | None = None  # последний успешный output asset
    capabilities: list[str] = field(default_factory=list)
    workflows_used: list[str] = field(default_factory=list)
```

### 2.3. Как работает handoff

```python
def _execute_chain_step(self, subtask: SubTask, chain_ctx: ChainContext) -> Job:
    """Выполнить один шаг цепочки с asset handoff."""

    # 1) Определяем входные assets для шага
    input_assets = {}
    if subtask.needs_input and chain_ctx.active_asset:
        # Predetermined input role (например, "image" для upscale/edit)
        input_assets["image"] = chain_ctx.active_asset

    # 2) PlanContext с учётом текущего состояния цепочки
    plan_ctx = PlanContext(
        active_asset_type=self._detect_asset_type(chain_ctx.active_asset),
        capabilities=tuple(self.capabilities()),
        active_workflow=chain_ctx.workflows_used[-1] if chain_ctx.workflows_used else None,
    )

    # 3) Planner для этого шага
    if self._adaptive_planner_enabled and self.execution_history is not None:
        from app.planner.adaptive import AdaptivePlanner, MIN_SUCCESSFUL_PER_CAPABILITY
        base_planner = self.planner or _default_planner()
        base_result = base_planner.plan(subtask.description, context=plan_ctx)
        success_count = len(self.execution_history.get_successful(base_result.capability))
        if success_count >= MIN_SUCCESSFUL_PER_CAPABILITY:
            planner = AdaptivePlanner(history=self.execution_history, fallback=base_planner)
        else:
            planner = base_planner
    else:
        planner = self.planner or _default_planner()

    result = planner.plan(subtask.description, context=plan_ctx)

    # 4) Подготовка и выполнение
    manifest, plan, provider = self.prepare(
        result.capability, params={**subtask.params, **result.params},
        provider=None, backend_id="local_comfyui",
    )

    # 5) Резолюция входных assets (AD-23)
    required_roles = {role: ain.kind for role, ain in manifest.asset_inputs.items()}
    bindings = self.resolve_asset_inputs(
        input_assets, context=None, store=self.store, as_ids=True,
        required_roles=required_roles,
    )
    plan.asset_bindings = bindings

    # 6) Execute
    job = self.engine.execute(manifest, plan, provider=provider)
    return job
```

### 2.4. Обновление ChainContext после шага

```python
# В _execute_chain(), после успешного шага:
if job.state.value == "SUCCESS" and job.output_assets:
    chain_ctx.active_asset = job.output_assets[0]  # primary output
    for aid in job.output_assets:
        self.context(session_id).assets.add(aid)
    chain_ctx.workflows_used.append(f"{manifest.id}@{manifest.version}")
```

### 2.5. Существующий Asset/AssetStore/lineage контракт

- Output assets шага N автоматически попадают в `AssetStore` через `WorkflowEngine.execute()` ✅
- `AssetStore.lineage()` работает для всех assets (шаг 0 и шаг 1) ✅
- Новый параллельный механизм хранения **не создаётся** — используется `ChainContext` как transient state в пределах цепочки ✅
- После завершения цепочки `ChainContext` уничтожается, assets остаются в `AssetStore` ✅

---

## 3. Job.chain_step_index

### 3.1. Где устанавливается

В `ExecutionChain._execute_step()` (chain.py:134) — **после** получения Job из `execute_fn`:

```python
def _execute_step(self, subtask: SubTask, index: int) -> ChainStep:
    step = ChainStep(subtask=subtask)
    for attempt in range(1, self.max_attempts_per_step + 1):
        try:
            job = self.execute_fn(subtask)
            job.chain_step_index = index  # ← УСТАНАВЛИВАЕТСЯ ЗДЕСЬ
            step.job = job
            ...
```

### 3.2. Какие значения получает

- Step 0 → `chain_step_index = 0`
- Step 1 → `chain_step_index = 1`
- Step N → `chain_step_index = N`
- Single-step (не chain) → `chain_step_index = None` (default)

### 3.3. Как отражается в ExecutionHistory

`ExecutionRecord.from_job()` уже записывает `prompt_id`, `capability`, `params`, `workflow_id`, `state`. Добавляется:

```python
@dataclass
class ExecutionRecord:
    ...
    chain_step_index: int | None = None  # M18: индекс шага в цепочки

    @classmethod
    def from_job(cls, job, ...):
        return cls(
            ...
            chain_step_index=getattr(job, 'chain_step_index', None),
        )
```

Это позволяет фильтровать history по шагам цепочки:
```python
history.get_attempts(capability="image.generate")  # все генерации
history.get_attempts(chain_step_index=0)            # только первые шаги цепочек
```

---

## 4. PlanContext propagation

### 4.1. Каждый subtask получает актуальный context

```python
def _execute_chain(self, session_id, subtasks, ...):
    chain_ctx = ChainContext(session_id=session_id)

    for i, subtask in enumerate(subtasks):
        # PlanContext обновляется на каждом шаге
        plan_ctx = PlanContext(
            active_asset_type=self._detect_asset_type(chain_ctx.active_asset),
            capabilities=tuple(self.capabilities()),
            active_workflow=chain_ctx.workflows_used[-1] if chain_ctx.workflows_used else None,
        )
        # ...
```

### 4.2. active_asset после каждого успешного шага

```python
# После успешного step:
if job.state.value == "SUCCESS" and job.output_assets:
    chain_ctx.active_asset = job.output_assets[0]
    # Следующий шаг увидит этот asset через chain_ctx.active_asset
```

### 4.3. Diagnostic: _detect_asset_type

```python
def _detect_asset_type(self, asset_id: str | None) -> str | None:
    """Определить тип asset по ID (image/video/audio)."""
    if asset_id is None:
        return None
    asset = self.store.get(asset_id)
    return asset.type if asset else None
```

---

## 5. Planner integration

### 5.1. Каждый step через существующий Planner/AdaptivePlanner

Каждый шаг цепочки проходит через:
1. `HeuristicPlanner.plan()` — определяет capability + базовые params
2. `AdaptivePlanner.plan()` (если история ≥ 3 для capability) — корректирует params
3. `PlanContext` с `active_asset_type` — влияет на edit/upscale routing

### 5.2. Capability НЕ определяется только keyword heuristics

**Важно:** `TaskDecomposer` определяет capability через keywords ("улучши" → image.edit, "увеличь" → image.upscale). Но финальное решение принимает `HeuristicPlanner`, который учитывает:
- `PlanContext.active_asset_type` — если нет active image → image.edit невозможен
- `ctx.capabilities` — если image.edit не в registry → fallback на image.generate
- Registry information — через `Agent.prepare()` → `_select_manifest()`

**Гарантия:**即使 TaskDecomposer определил "image.edit", если active_asset не image или capability не доступен — HeuristicPlanner выполнит fallback.

### 5.3. Fallback в chain context

Если шаг цепочки не может быть выполнен (capability не найден, missing assets):
- `Agent.prepare()` выбрасывает `AgentError`
- `ExecutionChain._execute_step()` ловит исключение → step.state = FAILED
- Цепочка останавливается (шаг N+1 НЕ выполняется)

---

## 6. Error semantics

### 6.1. Step N FAILED → step N+1 НЕ выполняется

**В `ExecutionChain.execute()` (chain.py:109):**
```python
if step.state == ChainState.FAILED:
    break  # останавливаем цепочку
```

**В `ConversationAgent._execute_chain()`:**
```python
for i, subtask in enumerate(subtasks):
    step = self._execute_step_with_retry(subtask, i, chain_ctx)
    if step.state == ChainState.FAILED:
        # Цепочка остановлена
        ctx.unresolved.append({
            "chain_step": i,
            "subtask": subtask.description,
            "error": step.error,
        })
        ctx.dialog_state = "error"
        break
```

### 6.2. ChainResult state

| Условие | ChainResult.state |
|---------|-------------------|
| Все шаги выполнены успешно | `COMPLETED` |
| Хотя бы один шаг FAILED | `FAILED` |
| Вызвана `cancel()` | `CANCELLED` |
| Пустой список subtasks | `COMPLETED` (0 steps) |

### 6.3. Связь retry M13 и chain-level execution

**Per-step retry (внутри chain):**
- `max_attempts_per_step` (по умолчанию 3) — количество попыток на один шаг
- `RetryPolicy.decide()` используется для каждого step отдельно
- Если step succeeded на attempt 2 — это засчитывается как success

**Chain-level retry (повтор всей цепочки):**
- **НЕ реализуется в Phase 2** — если цепочка failed, возвращается ChainResult с failed_steps
- Пользователь может повторить запрос вручную
- При необходимости — добавить в Phase 3

---

## 7. Cancellation

### 7.1. Отмена chain

```python
# В ConversationAgent._execute_chain():
chain = ExecutionChain(
    execute_fn=self._execute_chain_step,
    history=self.execution_history,
    max_attempts_per_step=3,
    on_step_complete=lambda i, step: self._on_chain_step_complete(session_id, i, step),
)

# Запуск
result = chain.execute(subtasks)

# Отмена (из SSE/UI):
chain.cancel()  # → _cancelled = True → текущий step завершается, следующие пропускаются
```

### 7.2. Assets после отмены

- Уже созданные assets (шаги 0..N-1) остаются в `AssetStore` ✅
- `ctx.active_asset` = последний успешный output ✅
- Частично выполненные assets НЕ удаляются ✅
- `ChainResult.state = CANCELLED`, `completed_steps = N` ✅

---

## 8. Session isolation

### 8.1. Chain одной session не влияет на другую

- `ChainContext` создаётся per-chain (per `turn()` вызов) ✅
- `ConversationContext` изолирован по `session_id` ✅
- `ExecutionHistory` общий ( глобальный для агента), но фильтруется по `capability` и `chain_step_index` ✅
- `AssetStore` глобальный, но assets изолированы по `id` ✅

### 8.2. Параллельные цепочки

Две параллельные цепочки (из разных sessions) НЕ конфликтуют:
- У каждого свой `ChainContext`
- У каждого свой `ConversationContext`
- `ExecutionHistory` append-only (нет гонки)
- `AssetStore` append-only (нет гонки)

---

## 9. Lineage

### 9.1. Восстановление цепочки

```
request: "сгенерируй кота и увеличь разрешение"
  │
  ├─ Step 0: image.generate → Job(prompt_id="abc", chain_step_index=0)
  │   → Asset A (id="a1", type="image", source_asset=None)
  │
  └─ Step 1: image.upscale → Job(prompt_id="def", chain_step_index=1)
      → Asset B (id="b1", type="image", source_asset="a1")
```

**Восстановление:**
```python
# Из ExecutionHistory:
records = history.get_attempts()
chain_records = [r for r in records if r.chain_step_index is not None]
# → [{prompt_id="abc", capability="image.generate", chain_step_index=0},
#    {prompt_id="def", capability="image.upscale", chain_step_index=1}]

# Из AssetStore:
store.lineage("b1")  # → [Asset B, Asset A] (B.source_asset = A.id)
```

### 9.2. Существующий Asset lineage не ломается

- `Asset.source_asset` устанавливается `WorkflowEngine` при создании output asset ✅
- M18 НЕ меняет логику `AssetStore` или `WorkflowEngine` ✅
- Lineage цепочки = цепочка source_asset'ов, что уже работает ✅

---

## 10. Backward compatibility

### 10.1. Single-step path unchanged

| Запрос | Путь | Результат |
|--------|------|-----------|
| `сгенерируй кота` | decompose → [1 subtask] → single-step | HeuristicPlanner → execute → Job |
| `увеличь разрешение` (с active_asset) | decompose → [1 subtask] → single-step | HeuristicPlanner (upscale) → execute → Job |
| `image.generate` (explicit capability) | skip decompose → single-step | HeuristicPlanner → execute → Job |

### 10.2. M18 additive

- `ConversationAgent.turn()` получает новый `_execute_chain()` метод ✅
- Существующий код turn() НЕ меняется (только добавляется `if len(subtasks) > 1: return self._execute_chain(...)`) ✅
- `TaskDecomposer` и `ExecutionChain` — новые модули, не заменяющие существующие ✅
- `Job.chain_step_index` — optional field (default=None), не ломает существующие Job ✅
- `ExecutionRecord.chain_step_index` — optional field, не ломает существующие records ✅

---

## 11. Integration tests

### 11.1. Unit tests (существующие, расширенные)

| Тест | Что проверяет | Файл |
|------|---------------|------|
| `test_simple_request` | decompose возвращает 1 SubTask | `test_m18_multi_step.py` ✅ |
| `test_two_part_request` | decompose возвращает 2 SubTask | `test_m18_multi_step.py` ✅ |
| `test_single_step_success` | ExecutionChain с 1 step | `test_m18_multi_step.py` ✅ |
| `test_multi_step_success` | ExecutionChain с 2 steps | `test_m18_multi_step.py` ✅ |
| `test_step_failure_stops_chain` | FAILED step → остановка | `test_m18_multi_step.py` ✅ |
| `test_retry_on_failure` | Per-step retry | `test_m18_multi_step.py` ✅ |
| `test_cancel_chain` | Отмена цепочки | `test_m18_multi_step.py` ✅ |

### 11.2. Integration tests (НОВЫЕ, требуют реализации)

| Тест | Что проверяет | Метод |
|------|---------------|-------|
| `test_single_step_regression` | Обычный запрос идёт по single-step path | `ConversationAgent.turn()` + FakeProvider |
| `test_two_step_generate_upscale` | generate → upscale с asset handoff | `ConversationAgent._execute_chain()` + FakeProvider |
| `test_two_step_generate_edit` | generate → edit с asset handoff | `ConversationAgent._execute_chain()` + FakeProvider |
| `test_failed_step_stops_chain` | Step 1 FAILED → step 2 НЕ выполняется | `ExecutionChain.execute()` |
| `test_retry_inside_chain` | Step 0 failed attempt 1 → retry → success | `ExecutionChain._execute_step()` |
| `test_cancellation` | `chain.cancel()` → remaining steps cancelled | `ExecutionChain.cancel()` |
| `test_asset_handoff` | Output step 0 = input step 1 | `_execute_chain_step()` + AssetStore |
| `test_chain_step_index` | Job.chain_step_index = 0, 1 | `ExecutionChain._execute_step()` |
| `test_session_isolation` | Две цепочки в разных sessions | `ConversationAgent.turn()` × 2 sessions |
| `test_history_recording` | Каждый шаг записан в ExecutionHistory | `ExecutionHistory.get_attempts()` |
| `test_final_active_asset` | ctx.active_asset = output последнего шага | `ConversationContext.active_asset` |
| `test_lineage_preserved` | Asset B.source_asset = Asset A | `AssetStore.lineage()` |
| `test_adaptive_planner_in_chain` | AdaptivePlanner используется если история ≥ 3 | `_execute_chain_step()` |

### 11.3. E2E tests (требуют реального ComfyUI)

| Тест | Что проверяет | Требование |
|------|---------------|------------|
| `test_e2e_generate_upscale` | generate → output.png → upscale → output_2x.png | `COMFY_REMOTE_URL` |
| `test_e2e_generate_edit` | generate → output.png → edit → output_edited.png | `COMFY_REMOTE_URL` |
| `test_e2e_chain_lineage` | Восстановление lineage через AssetStore | `COMFY_REMOTE_URL` |

---

## 12. E2E с реальным ComfyUI

### 12.1. Доказательная цепочка

```
1. curl -X POST /turn -d '{"session_id":"test","request":"сгенерируй кота 512x512"}'
   → Job(success), Asset A (512x512), ctx.active_asset = A

2. curl -X POST /turn -d '{"session_id":"test","request":"увеличь разрешение в 2 раза"}'
   → Job(success), Asset B (1024x1024), ctx.active_asset = B

3. Проверка:
   - store.lineage(B.id) == [B, A]
   - history.get_attempts() содержит 2 записи с chain_step_index=0 и chain_step_index=1
   - B.path существует и является валидным PNG
```

### 12.2. Требования к ComfyUI

- Доступен по `COMFY_REMOTE_URL`
- Установлены модели: SDXL checkpoint (для generate), upscale model (для upscale)
- Workflow манифесты: `image.generate`, `image.upscale` (или `img2img`)

---

## 13. Implementation scope (Phase 2)

### 13.1. Новые файлы

| Файл | Описание |
|------|----------|
| `docs/M18_INTEGRATION_ARCHITECTURE.md` | Этот документ |
| `tests/test_m18_integration.py` | Integration tests для chain wiring |

### 13.2. Изменённые файлы

| Файл | Изменение | Строк |
|------|-----------|-------|
| `app/conversation.py` | Добавить `_execute_chain()`, `_execute_chain_step()`, `_on_chain_step_complete()` | ~80 |
| `app/engine/chain.py` | `chain_step_index` установка в `_execute_step()` | ~5 |
| `app/engine/history.py` | `chain_step_index` в `ExecutionRecord` | ~5 |
| `tests/test_m18_multi_step.py` | Расширить существующие тесты | ~50 |

### 13.3. НЕ изменяется

| Файл | Почему |
|------|--------|
| `app/agent.py` | Agent.generate() — single-step path, не трогать |
| `app/planner/heuristic.py` | HeuristicPlanner — fallback, не трогать |
| `app/planner/adaptive.py` | AdaptivePlanner — уже интегрирован |
| `app/engine/engine.py` | WorkflowEngine — core execution, не трогать |
| `app/assets/store.py` | AssetStore — storage layer, не трогать |
| `app/planner/decomposer.py` | TaskDecomposer — уже реализован |
| `app/engine/chain.py` | ExecutionChain — уже реализован (небольшие addition) |

---

## 14. Risks

### HIGH

1. **Asset handoff через keyword detection** — `SubTask` НЕ хранит info о том, нужен ли input asset. Если decomposer определил "image.upscale", но active_asset не image — шаг failed.
   - **Mitigation:** `_detect_asset_type()` проверяет тип перед execution. Если тип не совпадает — step failed с понятным error message.

2. **Context propagation между шагами** — если шаг 0 создал video asset, а шаг 1 ожидает image — конфликт типов.
   - **Mitigation:** `_detect_asset_type()` + `HeuristicPlanner` с context-aware routing. Если тип не совпадает — planner выберет другую capability.

### MEDIUM

3. **AdaptivePlanner в chain context** — каждый шаг может использовать AdaptivePlanner, но история может быть неполной для нового capability.
   - **Mitigation:** `_has_enough_history(capability)` проверяет per-capability порог. Если история < 3 — fallback на HeuristicPlanner.

4. **Performance** — `TaskDecomposer.decompose()` вызывается на каждый `turn()`, даже для single-step.
   - **Mitigation:** `decompose()` — быстрый keyword-based метод (<1ms). Альтернатива: кеширование результата.

### LOW

5. **ExecutionHistory体积** — chain из 3 шагов создаёт 3 записи вместо 1.
   - **Mitigation:** ExecutionHistory append-only, JSONL persistence. Volume растёт линейно.

---

## 15. Approval checklist

- [ ] Decompose → Chain bridge определён
- [ ] Asset handoff через ChainContext определён
- [ ] Job.chain_step_index где устанавливается — определено
- [ ] PlanContext propagation между шагами — определено
- [ ] Planner integration (каждый шаг через HeuristicPlanner/AdaptivePlanner) — определено
- [ ] Error semantics (step failed → chain stops) — определено
- [ ] Cancellation (chain.cancel() + assets preserved) — определено
- [ ] Session isolation — определена
- [ ] Lineage preservation — определена
- [ ] Backward compatibility (single-step unchanged) — определена
- [ ] Integration tests спроектированы
- [ ] E2E tests определены
- [ ] Risks identified and mitigated
- [ ] Implementation scope (files, lines) определён

---

*Документ является DRAFT FOR APPROVAL. Реализация M18 начинается только после утверждения автором проекта.*
