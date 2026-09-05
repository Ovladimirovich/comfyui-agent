# M21 — Reconciliation & Recovery

**Статус:** DESIGN / AUDIT (AD-43) — БЕЗ production-кода
**Date:** 2026-09-03
**Decision ref:** AD-42 (Cluster Gateway), M20-STATUS
**На основе:** docs/24_CLUSTER_GATEWAY_DESIGN_AUDIT.md, DECISION_LOG.md

---

## 0. Контекст

M20 реализовал `ClusterGateway` как Resource Layer — слой "ГДЕ выполнить". Gateway умеет:
- Routing для NEW job (health → load → priority)
- `record_dispatch(prompt_id, backend_id)` — записывает кто принял задачу
- `reconcile(prompt_id, probe_fn)` — определяет состояние задачи
- `can_auto_retry(prompt_id)` — решает, можно ли safe retry

**Проблема:** Gateway НЕ интегрирован в execution path. `backend_execution_identity` существует в Job/ExecutionRecord но НIGDE SET. Reconcile логики нет вызовов из production-кода.

M21 — связать Gateway с существующим execution path и реализовать safe recovery после потери связи.

---

## 1. Фактическое состояние кода (AUDIT)

### 1.1 Что существует

| Компонент | Файл | Статус | Примечание |
|-----------|------|--------|------------|
| `ClusterGateway` | `app/resource/gateway.py` | ✅ EXISTS | Methods: route, record_dispatch, reconcile, can_auto_retry |
| `ReconcileState` | `app/resource/models.py:33` | ✅ EXISTS | UNKNOWN, COMPLETED, NOT_ACCEPTED, QUEUED, RUNNING, FAILED |
| `RecoveryAction` | `app/resource/models.py:44` | ✅ EXISTS | NONE, RESULT_RETURNED, REROUTED, USER_ASKED |
| `ExecutionDispatchRecord` | `app/resource/models.py:91` | ✅ EXISTS | job_prompt_id, backend_id, endpoint_url, submitted_at, execution_state, recovery_action |
| `Job.backend_execution_identity` | `app/engine/job.py:40` | ✅ EXISTS | **НЕ SET в production** |
| `ExecutionRecord.backend_execution_identity` | `app/engine/history.py:44` | ✅ EXISTS | Копируется из Job при record() |
| `RetryPolicy` | `app/engine/retry.py` | ✅ EXISTS | decide() — transient/permanent/verification |
| `WorkflowEngine.execute()` | `app/engine/engine.py:173` | ✅ EXISTS | **НЕ вызывает Gateway** |
| `Agent.generate()` | `app/agent.py` | ✅ EXISTS | **НЕ передаёт Gateway** |
| `ConversationAgent.turn()` | `app/conversation.py` | ✅ EXISTS | **НЕ передаёт Gateway** |

### 1.2 Что НЕ существует (gaps для M21)

| Компонент | Статус | Требование |
|-----------|--------|------------|
| Gateway integration в execution path | ❌ | WorkflowEngine должен вызывать gateway.record_dispatch() |
| backend_execution_identity setting | ❌ | Job.backend_execution_identity = selected_backend_id |
| Gateway в Agent/ConversationAgent | ❌ | Optional parameter + wiring |
| Reconciler class | ❌ | Отдельный component для resolve state |
| History dispatch tracking | ❌ | ExecutionHistory не хранит dispatch records |
| M21 tests | ❌ | test_m21_reconciliation.py |
| `docs/25_M21_RECONCILIATION_RECOVERY.md` | ❌ | Этот документ |

### 1.3 Критические находки

1. **Gateway изолирован от execution path.** `WorkflowEngine.execute()` не знает о Gateway. Dispatch не записывается.
2. **`backend_execution_identity` dead field.** Поле существует в моделях но nunca заполняется.
3. **RetryPolicy не учитывает Gateway.** `RetryPolicy.decide()` решает на основе error_class, не зная какой backend выполнял задачу.
4. **`ExecutionHistory` не хранит dispatch records.** Gateway._dispatch_records — in-memory dict, теряется при рестарте.

---

## 2. Архитектурная граница M21

```text
                 INTELLIGENCE
      Planner → Composer → CapabilityGraph
                       │
                       ▼
                   EXECUTION
       ExecutionChain → WorkflowEngine → Provider
                                            │
                                            ▼
                                        ComfyUI
                                            │
                                            ▼
                                   RESULT / ERROR
                                            │
                                            ▼
                               RECONCILIATION (M21)
                                    ClusterGateway
                                   Reconciler (NEW)
                                            │
                                            ▼
                                   RESOLUTION
                            accept / retry / stop / reroute
```

**Ключевой инвариант:** `Reconciler` определяет Состояние, но НЕ запускает выполнение.

```
Reconciler может сказать:
  ✅ "state = COMPLETED" → вернуть результат
  ✅ "state = NOT_ACCEPTED" → safe retry разрешён
  ✅ "state = UNKNOWN" → STOP (мораторий на auto)

Reconciler НЕ может:
  ❌ Запустить WorkflowEngine.execute()
  ❌ Изменить ExecutionPlan
  ❌ Выбрать capability
  ❌ Создать workflow
```

---

## 3. State Machine Reconciler

### 3.1 Входные данные

```python
# После disconnect / timeout / error
class ReconcileInput:
    prompt_id: str                    # ID задачи
    backend_id: str | None            # Кто исполнял (из backend_execution_identity)
    connection_lost: bool             # Была ли потеря связи
    error: str | None                 # Ошибка (если есть)
    history: ExecutionHistory         # История для корреляции
```

### 3.2 Состояния (после probe)

```
                    connection_lost
                         │
                         ▼
                  ┌──────────────┐
                  │   UNKNOWN    │ ← probe_fn вернул None / timeout
                  └──────┬───────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
   ┌──────────┐   ┌──────────┐   ┌──────────────┐
   │COMPLETED │   │ RUNNING  │   │NOT_ACCEPTED  │
   └────┬─────┘   └────┬─────┘   └──────┬───────┘
        │              │                 │
        ▼              ▼                 ▼
  RESULT_RETURNED  OBSERVE/WAIT    SAFE_RETRY
  (не дублировать) (наблюдать)     (на другой backend)
```

### 3.3 Переходы

| Текущее | Событие | Следующее | Action |
|---------|---------|-----------|--------|
| ANY | connection_lost + probe=COMPLETED | — | RESULT_RETURNED |
| ANY | connection_lost + probe=RUNNING | — | OBSERVE (ждать) |
| ANY | connection_lost + probe=FAILED | — | RECORD + retry? |
| ANY | connection_lost + probe=NOT_ACCEPTED | — | REROUTED (safe retry) |
| ANY | connection_lost + probe=UNKNOWN | — | STOP (мораторий) |
| ANY | no_connection_lost | — | NONE (норма) |

### 3.4 MD-01 enforcement

```python
def can_auto_retry(self, prompt_id: str) -> bool:
    """MD-01: UNKNOWN ≠ auto-retry."""
    record = self._dispatch_records.get(prompt_id)
    if record is None:
        return False  # Неизвестно кто принимал
    if record.execution_state == ReconcileState.UNKNOWN:
        return False  # MD-01: UNKNOWN state = STOP
    return record.execution_state == ReconcileState.NOT_ACCEPTED
```

---

## 4. Контракт Reconciler

### 4.1 Новый компонент

```python
# app/resource/reconciler.py (NEW, только после approval)

class Reconciler:
    """Определяет состояние execution после потери связи.
    
    ВЛАДЕЛЕЦ state transitions: ONLY reads Gateway + History.
    НЕ запускает execution. НЕ обходит WorkflowEngine.
    """
    
    def __init__(self, gateway: ClusterGateway, history: ExecutionHistory):
        self.gateway = gateway
        self.history = history
    
    def reconcile(
        self,
        prompt_id: str,
        probe_fn: Callable[[str], ReconcileState] | None = None,
    ) -> ReconcileResult:
        """Определить состояние и решение.
        
        Returns ReconcileResult с:
          - state: ReconcileState
          - action: RecoveryAction
          - rationale: str
        """
        ...
    
    def get_resolution(self, prompt_id: str) -> Resolution:
        """Получить финальное решение для prompt_id.
        
        Resolution = {
            "action": "accept" | "retry" | "stop",
            "backend_id": str | None,
            "rationale": str,
        }
        """
        ...
```

### 4.2 ReconcileResult

```python
@dataclass
class ReconcileResult:
    state: ReconcileState
    action: RecoveryAction
    rationale: str
    target_backend_id: str | None = None  # Для REROUTED
```

### 4.3 Инварианты Reconciler

```text
1. Reconciler НЕ имеет доступа к WorkflowEngine
2. Reconciler НЕ вызывает provider.execute()
3. Reconciler НЕ создаёт Job / ExecutionRecord
4. Reconciler ТОЛЬКО читает Gateway + History + probe_fn
5. Решение Reconciler → external handler (Agent/ConversationAgent)
```

---

## 5. Интеграция в execution path

### 5.1 Точки входа (NO CHANGE to frozen code)

```
WorkflowEngine.execute()          — ФРОЗЕН (M4)
  ↓ returns Job with backend_execution_identity
Agent.generate()                  — МОДИФИЦИРОВАТЬ (add optional gateway)
  ↓ passes gateway to WorkflowEngine
ConversationAgent.turn()           — МОДИФИЦИРОВАТЬ (add optional gateway)
  ↓ passes gateway to Agent
```

### 5.2 Модификации (backward compatible)

#### 5.2.1 WorkflowEngine.execute() — minimal change

```python
def execute(self, manifest, plan, provider, ws_timeout=None,
            on_progress=None,
            backend_id: str | None = None) -> Job:  # NEW optional
    ...
    job = Job(
        ...
        backend_execution_identity=backend_id,  # NEW: set from provider
    )
    return job
```

**Инвариант:** backend_id defaults to None → existing tests pass unchanged.

#### 5.2.2 Agent.generate() — add gateway

```python
def generate(self, request, ...,
             gateway: Optional[ClusterGateway] = None):  # NEW optional
    ...
    # После execute:
    if gateway and job.backend_execution_identity:
        gateway.record_dispatch(job.prompt_id, job.backend_execution_identity)
    return job
```

**Инвариант:** gateway=None → no change in behavior.

#### 5.2.3 ConversationAgent.turn() — pass gateway

```python
def turn(self, ...,
         gateway: Optional[ClusterGateway] = None):  # NEW optional
    ...
    job = self.agent.generate(..., gateway=gateway)
    ...
```

### 5.3 Reconciliation trigger

```python
# Где вызывать reconcile?
# Вариант A: После WS timeout в WorkflowEngine
# Вариант B: В Agent.generate() после catch timeout exception
# Вариант C: Отдельный background task (future)

# RECOMMENDED: Вариант B — в Agent.generate() retry loop
if decision.action == "retry" and gateway:
    state = gateway.reconcile(job.prompt_id, probe_fn=probe_history)
    if state == ReconcileState.UNKNOWN:
        # MD-01: STOP, don't retry
        return Job(..., state=JobState.FAILED, error="reconciliation UNKNOWN")
    elif state == ReconcileState.NOT_ACCEPTED:
        # Safe to retry on different backend
        # Gateway выберет новый backend через route()
        ...
```

---

## 6. ExecutionHistory — dispatch tracking

### 6.1 Проблема

`ExecutionHistory` не хранит dispatch records. Gateway._dispatch_records — in-memory dict, теряется при рестарте.

### 6.2 Решение (backward compatible)

Добавить optional persistence для dispatch records:

```python
# app/engine/history.py — NEW method
class ExecutionHistory:
    def record_dispatch(
        self,
        prompt_id: str,
        backend_id: str,
        endpoint_url: str,
    ) -> None:
        """Записать dispatch fact (для Gateway reconciliation)."""
        # Сохраняем в отдельный JSONL файл или в существующий
        ...
    
    def get_dispatch(self, prompt_id: str) -> Optional[ExecutionDispatchRecord]:
        """Получить запись о диспетчеризации."""
        ...
```

**Инвариант:** Методы optional, не влияют на существующий record() API.

---

## 7. Testing Strategy

### 7.1 Unit tests (test_m21_reconciliation.py)

| Test | Coverage |
|------|----------|
| reconcile_UNKNOWN_returns_STOP | MD-01 enforcement |
| reconcile_COMPLETED_returns_RESULT | No duplicate |
| reconcile_NOT_ACCEPTED_allows_retry | MD-03 enforcement |
| reconcile_RUNNING_returns_OBSERVE | Wait for completion |
| reconcile_no_record_returns_UNKNOWN | Missing dispatch |
| can_auto_retry_false_for_UNKNOWN | MD-01 |
| can_auto_retry_true_for_NOT_ACCEPTED | MD-03 |
| backend_execution_identity_in_record | History tracking |

### 7.2 Integration tests

| Test | Coverage |
|------|----------|
| Agent.generate with gateway | Full path integration |
| Gateway dispatch recorded | record_dispatch flows |
| Reconcile after mock disconnect | End-to-end reconcile |
| Retry on NOT_ACCEPTED | Safe reroute |
| STOP on UNKNOWN | No duplicate execution |

### 7.3 Regression

```bash
# Все существующие тесты должны проходить без изменений
pytest tests/test_m13_history_retry.py
pytest tests/test_m14_semantic_verification.py
pytest tests/test_m15_persistent_context.py
pytest tests/test_m16_adaptive_planner.py
pytest tests/test_m17_user_feedback.py
pytest tests/test_m18_multi_step.py
pytest tests/test_m19_feedback_integration.py
pytest tests/test_m20_cluster_gateway.py
```

---

## 8. ЧТО НЕ СЛЕДУЕТ МЕНЯТЬ

```
❌ WorkflowEngine.execute() core logic (M4 frozen)
❌ Provider interface (M5 frozen)
❌ CapabilityRegistry / WorkflowRegistry (M3 frozen)
❌ Composer / CapabilityGraph (M19 frozen)
❌ ExecutionChain (M18 frozen)
❌ HeuristicPlanner / AdaptivePlanner (M16 frozen)
❌ AssetStore / Asset model (M2 frozen)
❌ ConversationContext (M7 frozen)
❌ UI / SSE events (M9 frozen)
```

**Модифицировать ТОЛЬКО:**
- `WorkflowEngine.execute()` — добавить optional `backend_id` param
- `Agent.generate()` — добавить optional `gateway` param
- `ConversationAgent.turn()` — добавить optional `gateway` param
- `ExecutionHistory` — добавить optional `record_dispatch()` / `get_dispatch()`
- `app/resource/reconciler.py` — NEW (после approval)
- `tests/test_m21_reconciliation.py` — NEW (после approval)

---

## 9. Ответ на ключевой вопрос

### Может ли M21 быть реализован без изменения frozen execution path M1–M20?

**ДА, 100%.**

Обоснование:
1. Gateway уже существует и не зависит от execution path
2. `backend_execution_identity` уже добавлен в Job/ExecutionRecord (M20)
3. Интеграция через OPTIONAL параметры (gateway=None по умолчанию)
4. Существующие тесты не требуют изменений (backward compatible)
5. Reconciler — read-only component (не запускает execution)
6. Все модификации — additive, не меняют semantics M1–M20

**Condition:** Модификации `WorkflowEngine.execute()`, `Agent.generate()`, `ConversationAgent.turn()` должны добавить optional параметры с default=None, чтобы существующий код продолжал работать без изменений.

---

## 10. Implementation Plan (после approval)

### Step 1: ExecutionHistory dispatch tracking
- Добавить `record_dispatch()` и `get_dispatch()` в `ExecutionHistory`
- JSONL persistence для dispatch records
- Tests: 4 new

### Step 2: Gateway integration
- `WorkflowEngine.execute()` — optional `backend_id`, set `job.backend_execution_identity`
- `Agent.generate()` — optional `gateway`, call `gateway.record_dispatch()` after execute
- `ConversationAgent.turn()` — optional `gateway`, pass through
- Tests: 6 new

### Step 3: Reconciler
- Создать `app/resource/reconciler.py`
- Implement `Reconciler.reconcile()` with state machine
- Implement `Reconciler.get_resolution()`
- Tests: 8 new

### Step 4: Integration
- Wire reconcile into retry loop (Agent.generate)
- Handle UNKNOWN → STOP, NOT_ACCEPTED → reroute
- Tests: 4 integration

**Total new tests:** ~22
**Total modified files:** 6 (all backward compatible)
**Frozen code changes:** 0 (only optional params added)

---

## 11. Риски

| Риск | Severity | Mitigation |
|------|----------|------------|
| Gateway integration breaks existing tests | LOW | Optional params, default=None |
| Dispatch record persistence loss | MEDIUM | JSONL append-only, non-critical |
| Reconciler state machine complexity | MEDIUM | Unit tests for each transition |
| Probe_fn reliability | LOW | Fallback to UNKNOWN → STOP |

---

*Документ является архитектурным дизайном (AD-43). Production code — после отдельного approval.*
