# Cluster Gateway — Architecture Design & Audit

**Date:** 2026-09-03
**Status:** DESIGN/AUDIT (AD-42) — БЕЗ production-кода
**Decision ref:** AD-42 (engineering/DECISION_LOG.md)
**Goal:** Спроектировать Cluster Gateway как Execution Resource Layer БЕЗ написания кода.

---

## 0. Архитектурный контекст

```
                 USER
                   ↓
            ConversationAgent
                   ↓
                Planner
                   ↓
               Composer
                   ↕
          CapabilityGraph
                   ↓
            ExecutionChain
                   ↓
            WorkflowEngine
                   ↓
             Provider
                   ↓
             BackendRef
                   ↓
          ┌────────────────────┐
          │ ClusterGateway     │  ← Execution Resource Layer (ГДЕ выполнить)
          └───────┬────────────┘
             ┌────┼────┐
             ↓    ↓    ↓
          Local GPU1  GPU2
         ComfyUI ComfyUI ComfyUI
```

### Три слоя ответственности

| Layer | Вопрос | Компоненты |
|-------|--------|-----------|
| **Intelligence** | Что делать? | Planner, CapabilityGraph, Composer, AdaptivePlanner, SemanticVerifier |
| **Execution** | Как выполнить? | ExecutionChain, WorkflowEngine, Provider, Backend |
| **Resource** | Где выполнить? | ClusterGateway: health, load, compatibility, routing, failover |

---

## 1. Архитектурный дизайн-аудит — 15 вопросов

### Q1. Что именно является Backend identity?

**Ответ (Design Audit):**
- Backend identity — уникальный стабильный идентификатор физического ComfyUI instance.
- В текущей модели — это `BackendRef.backend` (например `local_comfyui`, `remote_comfyui`) + конкретный endpoint.
- **Требование для Gateway:** каждый backend-экземпляр должен иметь стабильный identity, НЕ зависящий от пересоздания объекта/подключения. Например `{backend_id, endpoint_url}`.
- Gateway должен хранить доверенную карту backend identities.

### Q2. Как определяется backend health?

**Ответ (Design Audit):**
- Health = способность backend принимать и обрабатывать задачи.
- Источники: `GET /system_stats` (HTTP), `/object_info`, WebSocket connection state.
- **Уровни health:**
  - `HEALTHY` — отвечает, принимает задачи.
  - `DEGRADED` — отвечает, но с ограничениями (очередь > N, OOM-предупреждение).
  - `UNHEALTHY` — не отвечает / не принимает.
  - `UNKNOWN` — не удалось определить (корректно -> НЕ HEALTHY, нельзя выбирать для routing).
- **Инвариант (MD-02):** `UNKNOWN ≠ HEALTHY`. Аналогично AD-18 для compatibility.

### Q3. Как получать queue depth?

**Ответ (Design Audit):**
- Источник: `GET /queue` (ComfyUI API) → `queue_running` + `queue_pending`.
- Gateway периодически опрашивает queue depth для каждого backend (async, кэширует).
- **Использование:** для load-aware routing (выбрать backend с наименьшей загрузкой).

### Q4. Как получать model catalog?

**Ответ (Design Audit):**
- Уже существует: `ModelRegistry` (M5) + `discover()` из `/object_info`.
- Каждый backend имеет свой model catalog (модели на конкретной машине).
- **Gateway НЕ заменяет ModelRegistry** — он опрашивает ModelRegistry/backend для получения каталога конкретного backend.

### Q5. Как проверять capability compatibility?

**Ответ (Design Audit):**
- Compatibility — responsibility Intelligence/Execution layers, НЕ Gateway.
- Gateway получает уже сформированный `ExecutionPlan` (capability + params) и проверяет, **какие backend'и физически могут его выполнить** (модель есть, runtime совместим, custom nodes есть).
- **Q: Может ли Gateway выбирать capability? — НЕТ.**
- **Q: Может ли Gateway создавать workflow? — НЕТ.**

### Q6. Как выбирать backend?

**Ответ (Design Audit):**
- Routing policy (см. §2 ниже) выбирает backend из **совместимых HEALTHY**-backend'ов.
- Критерии: health → compatibility → load (queue depth) → priority (пользовательский/конфиг) → модель доступна.
- **Routing** — автоматический (это безопасно, задача ещё не отправлена).

### Q7. Что происходит при disconnect после submission?

**Ответ (Design Audit):** — КРИТИЧНО
- После `POST /prompt` backend принял задачу, но WebSocket/HTTP оборвались.
- Gateway НЕ знает: задача не стартовала? выполняется? завершилась? output создан?

### Q8. Что считается retry-safe?

**Ответ (Design Audit):**
- **Только если состояние достоверно известно** (например, из `/history` подтверждено, что задача НЕ была принята / не существует).
- Если состояние UNKNOWN → retry НЕ безопасен.

### Q9. Как предотвращается duplicate execution?

**Ответ (Design Audit):** — КЛЮЧЕВОЙ РИСК
- **PRINCIPLE (MD-01): Failover НЕ автоматический при UNKNOWN state.**
- Если после disconnect state = UNKNOWN:
  - Gateway НЕ должен автоматически сабмитить на другой backend.
  - Обязателен процесс **reconcile/inspect/recover**: Gateway запрашивает `/history`, `/queue` у исходного backend (если доступен), и пытается установить реальное состояние.
  - Если state установлен как COMPLETED/документированный — возвращать результат, НЕ дублировать.
  - Если state установлен как НЕ-принят — можно безопасно retry.
  - Только если state подтверждённо не выполнен и исходный backend недоступен — Gateway МОЖЕТ (после явного решения политики) отправить на другой backend, зафиксировав это в ExecutionHistory (может быть мораторий на auto → запросить пользователя).

### Q10. Где хранится backend execution identity?

**Ответ (Design Audit):**
- Backend execution identity должен храниться в Job/ExecutionHistory (какой backend взял задачу, endpoint, prompt_id).
- Сейчас `Job` хранит `prompt_id`, но НЕ привязан явно к backend instance.
- **Требование:** добавить в ExecutionRecord/Job поле `backend_execution_identity` (кто именно выполнял).

### Q11. Как Gateway взаимодействует с ExecutionHistory?

**Ответ (Design Audit):**
- Gateway **читает** ExecutionHistory для корреляции (какой backend какой Job выполнял).
- Gateway **пишет** в ExecutionHistory факты о backend-выборе/диспетчеризации (не подменяет ExecutionChain).
- Gateway НЕ управляет ExecutionHistory — только дополняет его записями.

**(Q11) Может ли Gateway менять ExecutionPlan? — НЕТ.** (вынесено отдельно)

### Q12. Может ли Gateway менять ExecutionPlan?

**Ответ: НЕТ.** ExecutionPlan — неизменяемая спецификация задачи из Execution/Intelligence слоя. Gateway только выбирает ресурс.

### Q13. Может ли Gateway выбирать capability?

**Ответ: НЕТ.** Capability выбирает Planner/Composer.

### Q14. Может ли Gateway создавать workflow?

**Ответ: НЕТ.** Workflow создаёт/поддерживает WorkflowRegistry.

### Q15. Может ли Gateway обходить WorkflowEngine?

**Ответ: НЕТ.** Вся работа с backend (submit, track, process) — через уже существующий Provider/WorkflowEngine execution path. Gateway — слой выбора ресурса ДО отправки.

---

## 2. Routing Policy (проект)

### 2.1 Поток для NEW job

```
NEW ExecutionPlan
    ↓
1. Фильтрация HEALTHY backends
    ↓
2. Фильтрация по capability compatibility (модель/runtime/custom nodes есть)
    ↓
3. Сортировка по load (queue depth) + priority
    ↓
4. Выбор backend (детерминированный)
    ↓
5. Отправка через существующий Provider/WorkflowEngine execution path
```

### 2.2 Failover Policy (проект) — БЕЗОПАСНАЯ

```
UNKNOWN execution state (после disconnect)
    ↓
RECONCILE (не автоматический failover):
    ↓
запросить /history, /queue у исходного backend
    ↓
state понятен? ──Не понятен──▶ state = UNKNOWN → НЕ отправлять на другой backend.
    │                              Возможен мораторий на auto → запросить пользователя.
    ▼
state = COMPLETED ──▶ вернуть результат, НЕ дублировать.
    ▼
state = НЕ принят ──▶ безопасный retry (возможно, другой backend).
```

**Правило MD-03:** Failover автоматически разрешён ТОЛЬКО если state достоверно установлен как "не выполнялся". При UNKNOWN state — отказ от auto-друпликации.

---

## 3. Data Model (концепт, не код)

```
BackendSpec:
    backend_id: str          # stable identity (local_comfyui, gpu-1, ...)
    endpoint_url: str
    health: HEALTHY|DEGRADED|UNHEALTHY|UNKNOWN
    queue_depth: int
    model_catalog: ModelRegistry  # per-backend
    capabilities: tuple[str, ...] # что backend объявленно поддерживает
    priority: int

RoutingDecision:
    backend_id: str
    rationale: str            # почему выбран
    timestamp: float

ExecutionDispatchRecord:   # записывается в ExecutionHistory
    job_prompt_id: str
    backend_id: str
    endpoint_url: str
    submitted_at: float
    execution_state: UNKNOWN|QUEUED|RUNNING|COMPLETED|FAILED   # после reconcile
    recovery_action: NONE|REROUTED|RESULT_RETURNED|USER_ASKED
```

---

## 4. Границы Cluster Gateway

| Может | НЕ может |
|-------|----------|
| Выбирать backend для NEW job (routing) | Менять ExecutionPlan |
| Читать health/load/model catalog backends | Выбирать capability |
| Записывать факты dispatch в ExecutionHistory | Создавать workflow |
| Reconcile UNKNOWN state (inspect) | Обходить WorkflowEngine |
| Возвращать результат по reconcile | Сабмитить в backend напрямую (только через Provider/WorkflowEngine) |
| Фиксировать duplicate-ограничение (MD-01..03) | ... |

---

## 5. Инварианты (проект)

- **MD-01:** Failover НЕ автоматический при UNKNOWN execution state.
- **MD-02:** UNKNOWN health ≠ HEALTHY (не выбирать для routing).
- **MD-03:** Авто-retry на другой backend только если state достоверно "не выполнялся".
- **MD-04:** Gateway не имеет прямого доступа к ComfyUI HTTP (только через Provider/WorkflowEngine).
- **MD-05:** Gateway не строит node-graph / не генерирует workflow.

---

## 6. Реализация — ОТЛОЖЕНА

**Написание production-кода Cluster Gateway ЗАПРЕЩЕНО до отдельного approval (AD-42).**

Этот документ — только архитектурный дизайн/аудит.

---

## 7. Резюме Design

- Gateway решает "ГДЕ выполнить уже сформированный план".
- Routing безопасен и автоматический (new job).
- **Failover требует reconcile/inspect/recover** из-за риска duplicate execution.
- Gateway не меняет ExecutionPlan/capability/workflow и не обходит WorkflowEngine.
- Добавить явный `backend_execution_identity` в Job/ExecutionHistory.
- Backend health, queue depth, model catalog — данные из существующих источников (ComfyUI API + ModelRegistry).

*Документ является архитектурным дизайном/аудитом (AD-42). Не является production-кодом. Реализация — по отдельному approval.*