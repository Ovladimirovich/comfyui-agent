# M25 Implementation Plan

**Статус:** APPROVED — готов к реализации
**Дата:** 2026-09-04
**Основа:** `M25_ARCHITECTURE_PROPOSAL.md` + `M25_ARCHITECTURE_REVIEW.md`

---

## Phase 1 — Chain Identity

### Цель
Добавить persistent `chain_id` в `ExecutionRecord` для группировки записей по цепочкам.

### Изменения

#### 1.1 `app/engine/job.py` — добавить `chain_id`

```python
# Добавить после строки 38 (chain_step_index):
chain_id: str | None = None  # M25: group identifier for multi-step chains
```

**Обратная совместимость:** `None` по умолчанию. Существующие single-step jobs продолжают работать.

#### 1.2 `app/engine/history.py` — добавить `chain_id` в ExecutionRecord + методы

**ExecutionRecord (строка 50, после corrections_applied):**
```python
chain_id: str | None = None  # M25: group identifier for multi-step chains
```

**ExecutionRecord.from_job() (строка 77, после corrections_applied):**
```python
chain_id=getattr(job, 'chain_id', None),
```

**ExecutionHistory — добавить методы (после count(), ~строка 161):**

```python
def get_by_chain(self, chain_id: str) -> list[ExecutionRecord]:
    """Все записи одной цепочки, упорядоченные по chain_step_index."""
    return sorted(
        [r for r in self._records if r.chain_id == chain_id],
        key=lambda r: (r.chain_step_index or 0, r.timestamp),
    )

def get_chain_summary(self, chain_id: str) -> dict:
    """Агрегированная статистика по цепочке."""
    records = self.get_by_chain(chain_id)
    if not records:
        return {"chain_id": chain_id, "total_steps": 0}
    successful = [r for r in records if r.state == "SUCCESS"]
    return {
        "chain_id": chain_id,
        "total_steps": len(records),
        "completed_steps": len(successful),
        "failed_steps": len(records) - len(successful),
        "capabilities": list({r.capability for r in records}),
        "total_duration": sum(r.duration for r in records),
        "workflows": list({f"{r.workflow_id}@{r.workflow_version}" for r in records if r.workflow_id}),
    }
```

#### 1.3 `app/engine/chain.py` — генерировать chain_id

**ExecutionChain.execute() (строка 95, после start_time):**
```python
import uuid
chain_id = str(uuid.uuid4())[:12]
```

**ExecutionChain._execute_step() (строка 158, после job.chain_step_index = index):**
```python
job.chain_id = chain_id  # stamp chain_id на каждый Job
```

**Конструктор ExecutionChain — сохранить chain_id:**
```python
def __init__(self, ...):
    ...
    self._chain_id: str | None = None  # set in execute()
```

#### 1.4 `app/conversation.py` — записать chain_id в messages

**_on_chain_step_complete() (строка 686, в message dict):**
```python
ctx.messages.append({
    "type": "chain_step",
    "chain_id": chain_ctx.chain_id,  # M25
    "step": index,
    "capability": step.subtask.capability,
    "job": step.job.prompt_id,
    "outputs": list(step.job.output_assets),
    "state": step.state.value,
})
```

**ChainContext — добавить chain_id:**
```python
@dataclass
class ChainContext:
    session_id: str
    chain_id: str | None = None  # M25: group identifier
    active_asset: str | None = None
    workflows_used: list[str] = field(default_factory=list)
```

**_execute_chain() (строка 514, после создания ChainContext):**
```python
chain_ctx = ChainContext(session_id=session_id, chain_id=str(uuid.uuid4())[:12])
```

### Тесты — `tests/test_chain_tracking.py`

```python
# Тесты:
1. test_chain_id_stamped_on_job — ExecutionChain stamps chain_id on each Job
2. test_chain_id_in_execution_record — ExecutionRecord.from_job copies chain_id
3. test_chain_id_grouping — ExecutionHistory.get_by_chain groups correctly
4. test_chain_summary — get_chain_summary aggregates correctly
5. test_single_step_backward_compat — chain_id=None for single-step jobs
6. test_chain_id_in_conversation_messages — _on_chain_step_complete writes chain_id
7. test_chain_id_persistence — chain_id survives JSONL round-trip
8. test_multiple_chains_different_ids — different chains get different IDs
```

---

## Phase 2 — Multi-Asset Workflow Input

### Цель
Расширить `asset_inputs` для batch input. Создать `video.image_to_video` workflow.

### Изменения

#### 2.1 `app/registry/workflow.py` — расширить AssetInput

**AssetInput dataclass (строка 68-71):**
```python
@dataclass
class AssetInput:
    node: str
    field: str
    kind: str
    # M25: batch support
    multi: bool = False
    max_count: int = 1
    load_node_template: str | None = None  # node ID template for each LoadImage
    batch_node: str | None = None           # ImageBatch node ID
    batch_field: str | None = None          # field name in batch node
```

#### 2.2 `app/registry/workflow.py` — validate_manifest()

**В validate_manifest() (~строка 160, после asset_inputs validation):**
```python
for name, val in asset_inputs.items():
    _check_node_binding(val, f"asset_inputs.{name}", require_kind=True)
    # M25: validate multi fields if present
    if val.get("multi"):
        if not val.get("batch_node"):
            raise ManifestError(
                f"asset_inputs.{name}: multi=true требует batch_node",
                [UnavailableReason.INVALID_MANIFEST],
            )
        if not val.get("batch_field"):
            raise ManifestError(
                f"asset_inputs.{name}: multi=true требует batch_field",
                [UnavailableReason.INVALID_MANIFEST],
            )
```

#### 2.3 `app/registry/workflow.py` — load_workflow()

**В load_workflow() (~строка 282, при парсинге asset_inputs):**
```python
asset_inputs={
    k: AssetInput(
        node=str(v["node"]),
        field=v["field"],
        kind=v["kind"],
        multi=v.get("multi", False),
        max_count=v.get("max_count", 1),
        load_node_template=v.get("load_node_template"),
        batch_node=v.get("batch_node"),
        batch_field=v.get("batch_field"),
    )
    for k, v in data.get("asset_inputs", {}).items()
},
```

#### 2.4 `app/engine/engine.py` — build_prompt() multi logic

**build_prompt() (строка 96-99, замена текущего loop):**
```python
# входные ассеты (через Provider/Backend boundary, уже загружены)
for role, bind in manifest.asset_inputs.items():
    ref = asset_refs.get(role)
    if ref is None:
        continue

    if bind.multi and isinstance(ref, list):
        # M25: multi-asset — создаём N LoadImage nodes + ImageBatch connection
        _build_multi_asset_input(prompt, bind, ref)
    else:
        # single-asset — существующее поведение
        single_ref = ref[0] if isinstance(ref, list) else ref
        _set_field(prompt, bind.node, bind.field, single_ref.reference["filename"])
```

**Новая функция _build_multi_asset_input():**
```python
def _build_multi_asset_input(prompt: dict, bind, refs: list) -> None:
    """Собрать multi-asset input: N LoadImage → ImageBatch."""
    import copy

    # Находим template node (LoadImage) для копирования
    template_node = prompt.get(str(bind.load_node_template)) or prompt.get(bind.load_node_template)
    if template_node is None:
        raise ValueError(f"load_node_template '{bind.load_node_template}' не найден в prompt")

    # Для каждого ref создаём отдельный LoadImage node
    load_node_ids = []
    for i, ref in enumerate(refs):
        node_id = f"{bind.load_node_template}_m25_{i}"
        new_node = copy.deepcopy(template_node)
        new_node["inputs"]["image"] = ref.reference["filename"]
        prompt[node_id] = new_node
        load_node_ids.append(node_id)

    # Подключаем все LoadImage к ImageBatch node
    batch_node = prompt.get(str(bind.batch_node)) or prompt.get(bind.batch_node)
    if batch_node is not None:
        batch_node.setdefault("inputs", {})[bind.batch_field] = [
            [nid, 0] for nid in load_node_ids
        ]
```

#### 2.5 `app/engine/engine.py` — execute() multi upload

**execute() (строка 183-190, замена upload loop):**
```python
asset_refs: dict = {}
source_asset_ids: list = []
for role, asset_id in plan.asset_bindings.items():
    # M25: поддержка list[str] для multi-asset
    if isinstance(asset_id, list):
        refs = []
        for aid in asset_id:
            asset = self.store.get(aid)
            if asset is None:
                raise ValueError(f"asset {aid} не найден для binding '{role}'")
            refs.append(provider.upload_asset(asset))
            source_asset_ids.append(aid)
        asset_refs[role] = refs
    else:
        asset = self.store.get(asset_id)
        if asset is None:
            raise ValueError(f"asset {asset_id} не найден для binding '{role}'")
        asset_refs[role] = provider.upload_asset(asset)
        source_asset_ids.append(asset_id)
```

#### 2.6 `app/agent.py` — resolve_asset_inputs() list support

**resolve_asset_inputs() (строка 420-441, добавить list handling):**
```python
# M25: list support для multi-asset roles
for role, spec in assets.items():
    if role in out:
        continue
    if isinstance(spec, list):
        # multi-asset: список asset specs
        resolved = []
        for item in spec:
            resolved.append(_resolve_one(item, role, required_roles.get(role), store, as_ids))
        out[role] = resolved
    else:
        out[role] = _resolve_one(spec, role, required_roles.get(role), store, as_ids)
```

#### 2.7 `app/conversation.py` — _execute_chain_step() multi-asset

**_execute_chain_step() (строка 637-651):**
```python
# M25: multi-asset handoff
input_assets = {}
if chain_ctx.active_asset:
    required_roles = {role: ain.kind for role, ain in manifest.asset_inputs.items()}
    for role, ain in manifest.asset_inputs.items():
        if ain.multi:
            # Multi-asset: собираем все доступные assets этого типа
            matching = [
                aid for aid in ctx.assets
                if store.get(aid) and store.get(aid).type == ain.kind
            ]
            if matching:
                input_assets[role] = [{"asset_id": aid} for aid in matching[-ain.max_count:]]
        elif chain_ctx.active_asset:
            active_obj = store.get(chain_ctx.active_asset)
            if active_obj and active_obj.type == ain.kind:
                input_assets[role] = {"asset_id": chain_ctx.active_asset}
```

#### 2.8 `workflows/video_image_to_video/manifest.json`

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
      "max_count": 16,
      "load_node_template": "10",
      "batch_node": "11",
      "batch_field": "images"
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
  "min_comfyui_version": "0.0.0",
  "requirements": {"accelerator": "any", "xformers": false, "min_vram_gb": 4, "fp16": true},
  "limits": {
    "max_upload_bytes": 209715200,
    "max_sequence_length": 16
  }
}
```

#### 2.9 `workflows/video_image_to_video/workflow.json`

ComfyUI graph: LoadImage × N → ImageBatch → VAEEncode → KSampler → VAEDecode → CreateVideo → SaveVideo.

Создать на основе существующего `video_generate/workflow.json` с добавлением LoadImage × N + ImageBatch nodes.

### Тесты — `tests/test_multi_asset.py`

```python
# Тесты:
1. test_asset_input_multi_fields — AssetInput с multi, max_count, batch fields
2. test_validate_manifest_multi — validate_manifest проходит с multi
3. test_validate_manifest_multi_requires_batch_node — ошибка без batch_node
4. test_load_workflow_multi — load_workflow парсит multi fields
5. test_single_asset_backward_compat — существующие single-asset workflows работают
6. test_build_prompt_multi — build_prompt создаёт N load nodes + batch
7. test_build_prompt_single — build_prompt single unchanged
8. test_resolve_multi_assets — resolve_asset_inputs с list
9. test_video_i2v_manifest_load — video_image_to_video manifest валиден
10. test_video_i2v_workflow_discover — workflow discover находит video_i2v
```

---

## Phase 3 — ChainExperience

### Цель
Создать одну модель `ChainExperience` с JSONL persistence.

### Новые файлы

#### 3.1 `app/engine/experience.py`

```python
"""M25 — ChainExperience: факт о выполненном media workflow.

ChainExperience = one chain execution, aggregated from ExecutionRecords.
Append-only JSONL persistence.

Usage:
    store = ExperienceStore("data/experience")
    exp = build_chain_experience(chain_id, history, context)
    store.record(exp)
    loaded = store.get_by_chain(chain_id)
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass
class ChainStepExperience:
    """Опыт одного шага цепочки."""
    step_index: int
    capability: str
    input_assets: list[str] = field(default_factory=list)
    output_assets: list[str] = field(default_factory=list)
    params: dict = field(default_factory=dict)
    workflow_id: str = ""
    workflow_version: str = ""
    duration: float = 0.0
    state: str = "QUEUED"
    attempt: int = 1
    error: str | None = None
    error_class: str | None = None
    corrections: list[dict] | None = None


@dataclass
class ChainExperience:
    """Опыт выполнения цепочки media workflow."""
    chain_id: str
    session_id: str
    intent: str = ""
    timestamp: float = field(default_factory=time.time)
    steps: list[ChainStepExperience] = field(default_factory=list)
    # Summary
    total_duration: float = 0.0
    overall_state: str = "PENDING"
    completed_steps: int = 0
    failed_steps: int = 0
    # Sequence-specific (computed, not separate persistence)
    sequence_assets: list[str] | None = None
    temporal_consistency: float | None = None
    animation_quality: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> ChainExperience:
        steps_data = data.pop("steps", [])
        steps = [ChainStepExperience(**s) for s in steps_data]
        return cls(steps=steps, **{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class ExperienceStore:
    """Append-only JSONL persistence для ChainExperience."""

    def __init__(self, base_dir: str = "data/experience") -> None:
        self._base_dir = base_dir
        self._chains_dir = os.path.join(base_dir, "chains")
        os.makedirs(self._chains_dir, exist_ok=True)

    def record(self, exp: ChainExperience) -> None:
        """Записать experience в JSONL."""
        path = os.path.join(self._chains_dir, f"{exp.chain_id}.jsonl")
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(exp.to_dict(), ensure_ascii=False) + "\n")

    def get_by_chain(self, chain_id: str) -> ChainExperience | None:
        """Загрузить experience по chain_id (последняя запись)."""
        path = os.path.join(self._chains_dir, f"{chain_id}.jsonl")
        if not os.path.exists(path):
            return None
        last_line = None
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    last_line = line
        if last_line is None:
            return None
        return ChainExperience.from_dict(json.loads(last_line))

    def list_chains(self) -> list[str]:
        """Список chain_id файлов."""
        return [
            f.replace(".jsonl", "")
            for f in os.listdir(self._chains_dir)
            if f.endswith(".jsonl")
        ]


def build_chain_experience(
    chain_id: str,
    session_id: str,
    history,  # ExecutionHistory
    context=None,  # ConversationContext (optional)
    intent: str = "",
) -> ChainExperience:
    """Построить ChainExperience из ExecutionHistory + ConversationContext."""
    records = history.get_by_chain(chain_id) if hasattr(history, 'get_by_chain') else []

    steps = []
    for i, rec in enumerate(records):
        steps.append(ChainStepExperience(
            step_index=rec.chain_step_index or i,
            capability=rec.capability,
            output_assets=rec.output_assets,
            params=rec.params,
            workflow_id=rec.workflow_id,
            workflow_version=rec.workflow_version,
            duration=rec.duration,
            state=rec.state,
            attempt=rec.attempt,
            error=rec.error_message,
            error_class=rec.error_class,
            corrections=rec.corrections_applied,
        ))

    completed = sum(1 for s in steps if s.state == "SUCCESS")
    failed = sum(1 for s in steps if s.state == "FAILED")

    # Sequence detection: если chain содержит image→image→...→video
    sequence_assets = None
    if steps and any(s.capability.startswith("video.") for s in steps):
        # Собираем все image outputs до видео шага
        img_assets = []
        for s in steps:
            if s.capability.startswith("image."):
                img_assets.extend(s.output_assets)
        if img_assets:
            sequence_assets = img_assets

    return ChainExperience(
        chain_id=chain_id,
        session_id=session_id,
        intent=intent,
        steps=steps,
        total_duration=sum(s.duration for s in steps),
        overall_state="COMPLETED" if completed == len(steps) else "FAILED",
        completed_steps=completed,
        failed_steps=failed,
        sequence_assets=sequence_assets,
    )
```

#### 3.2 `app/engine/__init__.py` — добавить exports

```python
from app.engine.experience import ChainExperience, ChainStepExperience, ExperienceStore, build_chain_experience
```

#### 3.3 `app/conversation.py` — auto-record experience

**_on_chain_step_complete() (после обновления messages, ~строка 693):**
```python
# M25: auto-record experience после завершения chain
if self.experience_store is not None and hasattr(self, '_current_chain_id'):
    from app.engine.experience import build_chain_experience
    exp = build_chain_experience(
        chain_id=self._current_chain_id,
        session_id=session_id,
        history=self.execution_history,
        context=ctx,
        intent=ctx.messages[0].get("turn", "") if ctx.messages else "",
    )
    self.experience_store.record(exp)
```

**ConversationAgent.__init__ — добавить experience_store:**
```python
def __init__(self, ..., experience_store=None):
    ...
    self.experience_store = experience_store  # M25
```

### Тесты — `tests/test_experience.py`

```python
# Тесты:
1. test_chain_step_experience_creation
2. test_chain_experience_creation
3. test_chain_experience_from_history — build_chain_experience из ExecutionRecords
4. test_experience_store_record — ExperienceStore.record() создаёт JSONL
5. test_experience_store_get — ExperienceStore.get_by_chain() загружает
6. test_experience_store_list — ExperienceStore.list_chains()
7. test_experience_persistence — restart/load
8. test_sequence_detection — auto-detect sequence_assets
9. test_experience_to_dict_roundtrip — serialization
10. test_experience_backward_compat — chain_id=None для single-step
```

---

## Phase 4 — Deterministic Sequence Verification

### Цель
Deterministic checks для sequence ordering и completeness.

### Изменения

#### 4.1 `app/engine/verifier.py` — добавить sequence verification

```python
def verify_sequence(
    self,
    sequence_assets: list[str],
    expected_count: int | None = None,
) -> VerificationResult:
    """Детерминированная проверка sequence."""
    diagnostics = []

    # 1. Sequence не пуста
    if not sequence_assets:
        diagnostics.append(VerificationDiagnostic(
            output_name="sequence",
            ok=False,
            error_message="sequence is empty",
            error_class="verification",
        ))
        return VerificationResult(ok=False, diagnostics=diagnostics)

    # 2. Количество кадров
    if expected_count is not None and len(sequence_assets) != expected_count:
        diagnostics.append(VerificationDiagnostic(
            output_name="sequence",
            ok=False,
            error_message=f"expected {expected_count} assets, got {len(sequence_assets)}",
            error_class="verification",
        ))

    # 3. Все Asset IDs существуют
    missing = []
    for aid in sequence_assets:
        if self.store.get(aid) is None:
            missing.append(aid)

    if missing:
        diagnostics.append(VerificationDiagnostic(
            output_name="sequence",
            ok=False,
            error_message=f"missing assets: {missing}",
            error_class="verification",
        ))

    # 4. Нет дубликатов
    if len(sequence_assets) != len(set(sequence_assets)):
        diagnostics.append(VerificationDiagnostic(
            output_name="sequence",
            ok=False,
            error_message="duplicate assets in sequence",
            error_class="verification",
        ))

    ok = all(d.ok for d in diagnostics) if diagnostics else True
    return VerificationResult(ok=ok, diagnostics=diagnostics)
```

### Тесты — `tests/test_sequence_verification.py`

```python
# Тесты:
1. test_verify_sequence_empty — empty sequence = FAIL
2. test_verify_sequence_valid — all assets exist = PASS
3. test_verify_sequence_missing_asset — missing asset = FAIL
4. test_verify_sequence_wrong_count — count mismatch = FAIL
5. test_verify_sequence_duplicates — duplicates = FAIL
6. test_verify_sequence_order_preserved — order is as provided
7. test_verify_single_asset_backward_compat — existing verify() unchanged
```

---

## Implementation Order

1. **Phase 1** (Chain Identity) — 1-2 дня
   - job.py, history.py, chain.py, conversation.py
   - tests/test_chain_tracking.py

2. **Phase 2** (Multi-Asset) — 3-5 дней
   - workflow.py (AssetInput, validate, load)
   - engine.py (build_prompt, execute)
   - agent.py (resolve_asset_inputs)
   - conversation.py (_execute_chain_step)
   - workflows/video_image_to_video/
   - tests/test_multi_asset.py

3. **Phase 3** (ChainExperience) — 2-3 дня
   - NEW app/engine/experience.py
   - conversation.py (auto-record)
   - tests/test_experience.py

4. **Phase 4** (Sequence Verification) — 1-2 дня
   - verifier.py (verify_sequence)
   - tests/test_sequence_verification.py

5. **Regression** — 1 день
   - `python -m pytest tests/ -q`
   - Fix any M1-M24 regressions

6. **E2E** — 1-2 дня
   - Real ComfyUI test (requires live ComfyUI)
   - Image → Sequence → Video

**Итого:** 9-15 дней

---

## File Change Summary

| File | Phase | Change Type |
|------|-------|-------------|
| `app/engine/job.py` | 1 | Add `chain_id` field |
| `app/engine/history.py` | 1 | Add `chain_id` field + `get_by_chain()` + `get_chain_summary()` |
| `app/engine/chain.py` | 1 | Generate `chain_id`, stamp on Jobs |
| `app/conversation.py` | 1,2,3 | ChainContext.chain_id, multi-asset handoff, experience auto-record |
| `app/registry/workflow.py` | 2 | AssetInput multi fields, validation, loading |
| `app/engine/engine.py` | 2 | `build_prompt()` multi logic, `execute()` multi upload |
| `app/agent.py` | 2 | `resolve_asset_inputs()` list support |
| `app/engine/experience.py` | 3 | **NEW** — ChainExperience + ExperienceStore |
| `app/engine/__init__.py` | 3 | Export experience classes |
| `app/engine/verifier.py` | 4 | `verify_sequence()` method |
| `workflows/video_image_to_video/` | 2 | **NEW** — manifest.json + workflow.json |
| `tests/test_chain_tracking.py` | 1 | **NEW** |
| `tests/test_multi_asset.py` | 2 | **NEW** |
| `tests/test_experience.py` | 3 | **NEW** |
| `tests/test_sequence_verification.py` | 4 | **NEW** |

---

## M1-M24 Regression Check

После каждой фазы запускать:
```powershell
python -m pytest tests/ -q
```

Ожидаемый результат: 136 passed, 6 failed (test defects), 2 skipped — без изменений.

---

## E2E Proof Target

```
1. User: "сгенерируй кота"
   → image.generate → Asset₁

2. User: "добавь шляпу"
   → image.edit (input=Asset₁) → Asset₂

3. User: "сделай видео из этих картинок"
   → sequence_complete message → [Asset₁, Asset₂]
   → video.image_to_video (multi input) → Video Asset

4. Verify:
   - Asset₂.source_asset = Asset₁.id (lineage)
   - Video Asset.source_asset = Asset₂.id
   - ConversationContext.messages contains sequence_complete
   - ChainExperience saved to data/experience/chains/
   - Sequence verification passes
```
