# S6 Design — Runtime Validation Activation (SELF-TEST → CONFIRMED → REUSE)

> **Статус:** DESIGN ONLY — не реализация.
> **Дата:** 2026-09-13.
> **Forensic baseline:** S6 forensic audit (отчёт сессии 2026-09-13, file/line evidence включён в §2).
> **Base:** S0.5/S1/S2(CLOSED)/S3 FROZEN; S3 design §7 (self-test contract, утверждён как design-only); ECOSYSTEM §16 S6.
> **Scope-lock:** §15. ZERO code/test/UI/enum/cost-изменений в этой фазе.

---

## 1. Status / Scope

S6 активирует **уже существующий и доказанный** механизм:

```
workflow dict
  → RuntimeValidator.validate_node(node_class, workflow)
  → SUCCESS / FAILURE / ERROR / TIMEOUT
  → KnowledgeCore.validate_runtime() → merge_runtime_evidence → CONFIRMED claim
  → ClaimsPersistence (validated_nodes.json + confirmed_claims.json)
  →derived view → REUSE/ranking (_calculate_validation_score)
```

через ОДИН production-контур, соответствующий S3 §7 (policy gate) и NG3 (только user-initiated).

S6 НЕ добавляет: security-фреймворк, graph-builder, execution-движок, хранилища, enum'ы, cost-семантику.

## 2. Current forensic baseline (из аудита, с evidence)

| Факт | Evidence |
|---|---|
| `RuntimeValidator.validate_node(node_class: str, workflow: dict)` — 2 обязательных аргумента | `runtime_validator.py:56` |
| CONFIRMED-upgrade только при SUCCESS; FAILURE/ERROR/TIMEOUT → claims не трогаются | `runtime_validator.py:144-145,174-175,197,211` |
| `KnowledgeCore.validate_runtime` → validate_node(2-arg, корректно) → merge → persistence (`validated_nodes` + `confirmed_claims`) | `core.py:239,252,255-258,263-270` |
| Research-путь не даёт auto-CONFIRMED | `evidence_store.py:98,128-129` |
| Production-callers `validate_runtime` = НОЛЬ (только тесты) | grep app/ : определение без вызовов |
| Agent→validator: параметр есть, единственный консюмер — мёртвый daemon-hook; вызов `validate_node(node_type)` (1 arg) → TypeError, глотается except → False; маскируется MagicMock | `agent.py:165,173,425-466` vs `runtime_validator.py:56` |
| Хук не имеет production-callers; вызывается только тестами | `test_agent_runtime_validation.py:78`, `test_workflow_validation_priority.py:242` |
| Два несвязанных кэша: `Agent._validated_nodes` (пуст в production) vs `KnowledgeCore._validated_nodes`←ClaimsPersistence (реальные данные: Get Request Node=false, PollinationsImageGen=true, SaveImage=true) | `agent.py:175,464-466`; `core.py:100,255,283`; prod json |
| `_calculate_validation_score` читает ТОЛЬКО Agent-кэш → вечно 0 | `agent.py:325-343`, единственный caller `:400` |
| `get_validated_for_capability(capability)` — предусмотренный мост, 0 callers | `core.py:315-341` |
| Whitelist-механизма нет; предикаты есть: `classify_safety`, `classify_role`, S1 cost-gate | grep пусто; `synthesis/safety.py`; `queries.py`; `registry/cost.py` |
| PlanContext валидированных полей НЕ имеет (legacy-красные тесты ждут несуществующий API) | `planner/plan.py:13-22` |
| Прямые записи в локальный dict есть в green-тестах (наследие, обязано остаться зелёным) | `test_http_request_real_e2e.py:256`, `test_workflow_validation_priority.py:215` |

## 3. S6 invariants

1. **SELF-TEST никогда не auto:** единственный вход — явная команда пользователя (см. §4). Никаких потоков/демонов/фоновых прогонов; NG3 сохранён (PROJECT_SPEC `:87,110-113`).
2. **Ни один граф не исполняется до прохождения policy gate.**
3. **CONFIRMED — только из SUCCESS runtime evidence** через существующие `merge_runtime_evidence`/`upgrade_claims`. Ничего нового в ClaimStatus/EvidenceTrustLevel не добавляется.
4. **Synthesis ≠ validation ≠ registration ≠ execution eligibility** — границы AD-45/46/47 неизменны. SELF-TEST не влияет на выбор capability/workflow, кроме штатного REUSE-ранжирования.
5. **Единый источник истины evidence:** `ClaimsPersistence`/`KnowledgeCore`. S6 не создаёт хранилищ/кэшей.
6. S0.5/S1/S2/S3 контракты, engine/registry/planner/UI/M25-M26 — не изменяются.
7. Реализация обязана сохранить ВСЕ существующие зелёные тесты без правок (проверено в §7/§8: direct-write и mock-hook тесты остаются зелёными).

## 4. SELF-TEST lifecycle (единственная production-точка входа)

```text
USER INTENT           «протестируй/проверь ноду X» — явная команда (CLI/MCP/явный метод)
   ↓
Agent.run_self_test(node_class, backend_id=…)        ← ЕДИНСТВЕННАЯ точка (новый метод на Agent)
   ↓
S6 POLICY GATE (§5)   refuse-fast, ничего не исполняется при любом false/unknown
   ↓
WORKFLOW SOURCE (§6)  существующий registry workflow ∪ S2 synthesize_workflow → workflow dict
   ↓
RuntimeValidator.validate_node(node_class, workflow)  (существующий API; client = provider-клиент выбранного backend)
   ↓
RuntimeEvidence SUCCESS/FAILURE/ERROR/TIMEOUT
   ↓
KnowledgeCore.validate_runtime(...)                   (существующий: merge + persistence)
   ↓
RESULT → SelfTestResult{status, evidence, claim_status, reasons}   (пользователю; без auto-registration)
```

**Decision.** Entry point = метод `Agent`, НЕ фоновый поток, НЕ ветка `generate/turn`.
**Existing mechanism reused:** `validate_runtime` (core), `RuntimeValidator`, S2 `synthesize_workflow`, S3 queries (для отчёта gate-предикатов), S1 cost (BackendSpec/manifest), `ComfyUIProvider`/`ComfyClient` для transport — валидация идёт тем же ComfyUI, что и execution (AD-29).
**Why minimal:** одна точка = одна проверка «кто вообще может запустить ComfyUI-граф» (сейчас таких мест ровно два: engine.execute и validator; S6 добавляет третий с gate).
**What is explicitly NOT changed:** `ConversationAgent.turn` НЕ получает авто-самотест; keyword-детекция намерений в planner НЕ вводится (намерение подаёт пользователь/агент-команда, а не LLM-угадывание); UI не трогаем.
CLI/MCP: команда (например `agent-selftest --node …`) — тонкая обёртка над методом; конкретная поверхность — OQ3.

## 5. Policy gate (S3 §7 enforcement — существующие предикаты)

Gate = чистая функция `_self_test_gate(node_class) -> GateDecision(allowed: bool, reasons: list[str])`, все проверки — только существующие механизмы:

| # | Условие (S3 §7) | Механизм | Если false / unknown |
|---|---|---|---|
| 1 | safety == ALLOWED | `classify_safety(python_module, category, class_type)` (s2) | REQUIRES_CONFIRMATION → **refuse** с reason=`requires_confirmation` (ветка подтверждения — OQ2); FORBIDDEN → **refuse** `forbidden` |
| 2 | role ∈ {head, processor, sink} | `queries.classify_role(schema)` (S3) | fragment/loader → refuse `not_standalone` (граф-фрагмент нельзя валидировать изолированно — loader'ам нужен downstream, fragment — upstream) |
| 3 | backend cost ∈ {FREE,TRIAL} | S1: выбранный `BackendSpec.cost_tier` (+override из `Workflow.cost_tier`) | PAID/UNKNOWN → refuse `cost_not_free` (AD-46 semantics без изменений) |
| 4 | workflow source exists (template ∨ registry) | §6 | нет → refuse `no_workflow_source` |
| 5 | workflow исполним без внешних входов | §6 guard | required IMAGE/VIDEO/AUDIO/CLIP/LATENT-без-связки → refuse `needs_input_asset` |
| 6 | явная команда | факт вызова метода (user-initiated) | n/a — авто-вызовов не существует по построению |

- **UNKNOWN/неполные данные** (нет схемы, нет safety-входа, registry недоступен) → **refuse** (консервативно, UNKNOWN ≠ ALLOWED — паттерн AD-18).
- **Reason for refusal** — машиночитаемый список; refusal НЕ пишет никаких записей в ClaimsPersistence.
- Ничего не исполняется до полного прохождения gates 1–5.
**Decision:** gate существует в ОДНОЙ функции; предикаты импортируются, не копируются и не расширяются.
**Why minimal:** `classify_safety`/`classify_role`/S1 уже утверждены; новая логика — только их конъюнкция + refuse-reasons.
**NOT changed:** classify_safety не расширяется; новых enum'ов/категорий нет; `allow_paid` (S1) в self-test НЕ используется (self-test ≠ explicit override selection).

## 6. Workflow source (без нового graph builder)

Приоритет источника `workflow: dict` для `validate_node`:

1. **Существующий registry workflow, содержащий ноду** (`WorkflowRegistry.workflows` → `workflow.json` граф) — для нод из уже зарегистрированных пайплайнов (пример: SaveImage ∈ txt2img/upscale).
2. **Иначе S2 `synthesize_workflow(candidate, schema, template)`** → `result.workflow` — dict уже готов к валидации. **ВАЖНО:** синтез остаётся незарегистрированным (AD-47: synthesis ≠ registration ≠ validation). SELF-TEST синтезированного графа — только доказательство работоспособности ноды; регистрация — OQ1.
3. **Ни то, ни другое → refuse** (`no_workflow_source`) — gate §5.4.

**Executability guard (решение из аудита):** `synthesize`-графы head-нод без required media-входов исполнимы как есть; графы с required IMAGE (processor/sink из registry, напр. upscale) требуют input asset → **S6-минимальный scope: refuse с `needs_input_asset`** (asset-binding через существующий engine — усложнение, не обязательное для замыкания цикла; S6.1/FUTURE).

**Candidate → workflow → validation:** для CANDIDATE_NO_WORKFLOW (S3 gap-тип) путь = (2); для known-capability нод = (1).

## 7. Agent/Core integration (source of truth, §1)

**Decision (дублирующий кэш — явное решение):**
- Владелец evidence = `KnowledgeCore`/`ClaimsPersistence` (единственный persistent source).
- `Agent._validated_nodes` **не устраняется** (наследие: green-тесты пишут в него напрямую — `test_http_request_real_e2e.py:256`, `test_workflow_validation_priority.py:215`), но **демпотируется до legacy-fallback**: источник истины для ранжирования — core-derived view, локальный dict — только override-наследие.
- `_calculate_validation_score(workflow)` — минимальное изменение источника чтения (псевдокод, НЕ код):

```text
validated = (self.knowledge_core.get_validated_nodes()   # ← S0.5-параметр уже есть; persistence-derived
             if self.knowledge_core is not None
             else self._validated_nodes)                   # legacy fallback (сохраняет green-тесты)
```

Плюс capability-scoped точность: при наличии registry у core — `get_validated_for_capability(capability)` (существующая, 0 callers → становится первым caller'ом). Назначение функции (count validated nodes workflow → ranking) НЕ меняется.
**Why minimal:** 2-3 строки в существующем методе; ноль новых структур; мост = ровно та функция, что была спроектирована под это (`core.py:315`).
**Explicitly NOT changed:** `PlanContext` (заморожен; `validated_nodes` в него НЕ добавляется); `ExecutionRecord`/`JobState`/persistence форматы; `KnowledgeCore.__init__` (параметр `runtime_validator` + `validate_runtime` уже есть).

**SELF-TEST запись в core-кэш:** `validate_runtime` сам обновляет `core._validated_nodes` (`core.py:255`) + persistence (`:258`) — Agent-кэш в production больше не является источником.

## 8. Dead hook decision (G2) — ЯВНОЕ решение: **вариант C-гибрид**

`Agent._validate_capability_nodes_background` (`agent.py:425-466`):
- **Decision:** удалить **threading/daemon-семантику** (это и есть NG3/§7-конфликт: background-выполнение реальных графов недопустимо), сигнатуру исправить на `validate_node(node_class, workflow_dict)`; метод сохраняется как **deprecated synchronous shim** (никаких потоков, без production-вызовов, docstring с пометкой `deprecated: superseded by run_self_test (§4)`).
- Почему не чистое удаление (A): 3 зелёных теста вызывают хук (`test_agent_runtime_validation.py:78` — mock, узлы из registry; `test_workflow_validation_priority.py:242` — пустой список нод; + ассерты `assert_called` на mock) → удаление сломало бы зелёное без правки тестов, что запрещено инвариантом §3.7.
- Почему не B (переписать в user-initiated production path): production-путь уже определён в §4 (`run_self_test`); хук остаётся только legacy shim, не путь.
- Shim пишет тот же legacy-кэш → семантика для наследия не меняется; в новом контуре не участвует.
- **Future cleanup milestone (зафиксировано):** удаление shim + его 3 хук-тестов — одним отдельным hygiene-коммитом после S6, не в S6.
**What is explicitly NOT changed:** поведение mock-тестов, public API `Agent.__init__`.

## 9. Validation evidence lifecycle (CONFIRMED semantics — §7)

Без изменений семантики. Отвечающие существующие функции:

```text
SUCCESS → merge_runtime_evidence (runtime_validator.py:174-213; predicate validated_by_execution,
          trust OBSERVED_BEHAVIOR, ClaimStatus.CONFIRMED :197/:211)
        → core.validate_runtime: _validated_nodes=True (:255), add_validated_node (:258),
          add_confirmed_claim (:267-270), merge в core._claims (:263)
FAILURE/ERROR/TIMEOUT → validated=False (core.py:255), claims НЕ трогаются (guard :174-175),
          CONFIRMED не появляется никогда
Research-путь → максимум SUPPORTED (evidence_store.py:98,128-129) — без изменений
USER_CONFIRMED — не вводится (S5/OQ)
```

## 10. REUSE / ranking integration (lifecycle)

```text
SELF-TEST SUCCESS → ClaimsPersistence (+ core._validated_nodes, CONFIRMED claims)
→ следующий _select_manifest: _calculate_validation_score читает core-derived (§7)
→ workflows, чьи ноды validated=True, получают score>0
→ ранжирование: score desc → cost desc → priority… (S1-контур без изменений)
→ REUSE: проверенное переиспользуется раньше непроверенного — без повторного SELF-TEST
```

**Честный boundary-gap (фиксируем, не скрываем):** score влияет только на **зарегистрированные** в registry workflows. SELF-TEST синтезированного (нерегистрированного) графа даёт CONFIRMED-evidence (объяснимость через S3 explain/gap_report уже работает: `queries.py:379,437`), но НЕ повышает ranking, пока workflow не зарегистрирован. Регистрация синтезированного workflow = **OQ1** (нужен явный consent-контур; без него S6 loop полностью замыкается для registry-нод и evidence-уровне для new-nodes).
**Запрещено и не делается:** PlanContext.validated_nodes; новый кэш; auto-registration.

## 11. Positive / negative proof scenarios

**Negative (уже факт):** `Get Request Node` — `validated_nodes.json = false` (исторический live E2E, пережил перезапуск).
- Как S6 его сохраняет: повторный SELF-TEST с FAILURE перезаписывает false (add_validated_node upsert, `claims_persistence.py:53`); CONFIRMED не возникает (guards §9).
- Как использует: §5 — network/API-ноды = REQUIRES_CONFIRMATION по safety-классификации, то есть gate и так не даёт auto-run; score-правило `is True` (agent.py:343/345) исключает false из ранжирования автоматически.
- Критерий: тест-демо доказывает `validated=False → score не растёт → claim INFERENCE остаётся`.

**Positive:** `PollinationsImageGen` (role=head, safety=REQUIRES_CONFIRMATION, историческая запись validated=True).
- Путь S6: gate §5.1 → REQUIRES_CONFIRMATION ≠ ALLOWED → **авто-отказ**; исполнение — только после явного подтверждения (OQ2-механизм). CONFIRMED claim: subject=PollinationsImageGen, predicate=validated_by_execution.
- Если подтверждение не реализовано в S6-минимуме (решение OQ2) — положительный e2e-демо берёт **чистую ALLOWED head-ноду** (проверяется на живом ComfyUI в acceptance-прогоне; конкретный кандидат определяется evidence-демо-тестом, не домысливается).
- **Не считается доказанным из одной записи:** acceptance требует воспроизведённого запуска в S6-демо (fresh SUCCESS → CONFIRMED timestamp обновился), а не чтения старого JSON.

## 12. Legacy S4 tests disposition (решение)

**Decision: остаются pre-existing documented debt в S6.**
- 8 fail (`test_knowledge_s4_planner_integration.py`) + 6 fail (`TestPlannerIntegration`/`TestFullChain` s4_full/real) — ожидания несуществующего API (`PlanContext.validated_nodes`, rationale-маркер).
- **Запрет:** восстанавливать `PlanContext.validated_nodes` ради зелёного pytest (PlanContext frozen; M26.2; audit H).
- Контракт, который делает старые ожидания obsolete: **§7 (Agent читает core-derived validation state) + §10 (REUSE через `_select_manifest`)** — приоритизация валидированного реализуется на уровне workflow-ranking, НЕ через planner-контекст. Будущая миграция (S4-redesign milestone) перепишет/удалит эти тесты с этой ссылкой.
- S6 implementation не трогает ни один из этих файлов (инвариант §3.7).

## 13. Minimal implementation plan (для следующего approval; НЕ сейчас)

| # | Файл | Изменение | Оценка |
|---|---|---|---|
| 1 | `app/agent.py` | `run_self_test(node_class, backend_id=…)` (§4): gate → workflow source → validate_runtime → result | ~70 строк |
| 2 | `app/agent.py` | `_self_test_gate` (§5) — чистые предикаты, refuse-reasons | ~30 |
| 3 | `app/agent.py` | `_calculate_validation_score` — смена источника чтения (§7) | ~4 |
| 4 | `app/agent.py` | хук: убрать thread, фикс сигнатуры, deprecated-shim (§8) | ~-10 |
| 5 | `comfyui_api.py` (CLI) | команда `agent-selftest` (§4 surface) | ~15 |
| 6 | `tests/test_knowledge_s6_selftest.py` | NEW — матрица §14 | ~200 |
| 7 | docs | S3_AUDIT/S6_DESIGN статусные строки, ACTIVE/HANDOFF | small |

**Ноль правок в:** app/engine, app/registry, app/planner, app/synthesis, app/knowledge/* (ядро готово: `validate_runtime`, `get_validated_for_capability`, `merge_runtime_evidence`), UI, legacy-S4, S0.5/S1/S2/S3-контракты.
Оценка: ~130 строк production (все в agent.py + CLI), ~200 тестов.

## 14. Tests / acceptance criteria (матрица будущей реализации)

| # | Тест |
|---|---|
| A1 | Gate refuse: safety=REQUIRES_CONFIRMATION без подтверждения → refuse, ноль вызовов валидатора (spy), ноль записей |
| A2 | Gate refuse: FORBIDDEN → refuse `forbidden` |
| A3 | Gate refuse: role=fragment/loader → `not_standalone` |
| A4 | Gate refuse: backend cost=UNKNOWN/PAID → `cost_not_free` (S1 semantics не расширены) |
| A5 | Gate refuse: нет workflow source → `no_workflow_source` |
| A6 | Gate refuse: required IMAGE без asset → `needs_input_asset` |
| A7 | Gate pass ALLOWED+head+FREE+template+explicit → validate_node вызван с **2** аргументами (реальный validator с mock client — сигнатурный контракт) |
| A8 | SUCCESS → CONFIRMED claim (validated_by_execution, OBSERVED_BEHAVIOR) + persistence (tmp data_dir — P1) |
| A9 | FAILURE → validated=False, claim НЕ upgrade, CONFIRMED отсутствует |
| A10 | Score integration: core c validated node → `_calculate_validation_score`>0 → _select_manifest ранжирует выше; Agent без core → legacy fallback (green-совместимость) |
| A11 | Refusal не пишет ничего (mtime/dir-snapshot guard) |
| A12 | Hook-shim: синхронный, корректная сигнатура, legacy-тесты зелёные БЕЗ правок |
| A13 | NG3: ни одного Thread/daemon/threading.Thread в S6-коде (grep-тест или inspect) |
| A14 | Readiness/execution eligibility не изменились (AD-45) |
| A15 | Live demo-прогон (evidence-демо): положительный сценарий §11 на живом ComfyUI при свободной очереди, фиксация fresh-CONFIRMED-timestamps |
| A16 | Полная регрессия: 282+ green, 14 pre-existing S4 red — неизменны |

## 15. Explicit non-goals (scope-lock)

S4 planner redesign; S5 USER_CONFIRMED; S7 usage/limitation claims; S8 external sources; UI/агент-автономия; LLM в gate/workflow-source; OQ4; новые enum'ы (GapType/ClaimStatus/EvidenceTrustLevel/CostTier); новые stores; новый execution engine; новый security framework; per-node cost; audio/video expansion; изменения S0.5/S1/S2/S3 контрактов; `allow_paid` в self-test; auto-registration synthesized workflows; активация `PlanContext`.

## 16. Open questions

| OQ | Вопрос | Дефолт S6 |
|---|---|---|
| OQ1 | Регистрация SELF-TEST-прошедшего синтезированного workflow (consent-контур) | NO — evidence остаётся, ranking-boost отложен |
| OQ2 | Механизм подтверждения для REQUIRES_CONFIRMATION (флаг параметра vs HITL `ask_user`-мост M22) | вне минимума: refuse; ветка — следующий микро-шаг |
| OQ3 | Поверхность явной команды: CLI `agent-selftest` vs MCP-tool vs метод API | CLI (тонкая обёртка) |
| OQ4 | SELF-TEST processor-нод с asset-input (engine-путь) | refuse `needs_input_asset` |
| OQ5 | Удаление deprecated-shim + 3 hook-тестов | отдельный hygiene-коммит после S6 |

---

## S6 Acceptance Criteria (порог перед реализацией)

1. Дизайн-документ принят автором; все 16 разделов закрыты решениями с Decision/Reused/Why-minimal/Not-changed.
2. Единственный production-entry (§4) + gate (§5) + source (§6) + integration (§7) + hook-решение (§8) не имеют скрытых ветвлений и не добавляют storage/enum/cost-семантики.
3. Все green-тесты (282) обязаны остаться зелёными **без правок** при реализации; 14 pre-existing red — не трогаются.
4. Реализация вводится только после approval этого design (ритуал: approval → implementation → forensic verification → freeze).

---

*Конец документа. Статус: S6 DESIGN — DRAFT (ждёт approval). Production code НЕ изменялся; tests НЕ изменялись; commit НЕ выполнялся.*
