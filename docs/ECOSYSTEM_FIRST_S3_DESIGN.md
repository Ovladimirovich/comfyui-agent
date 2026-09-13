# S3 Design — Ecosystem Facts & Provenance Queries

> **Статус:** DESIGN ONLY — не реализация.
> **Дата:** 2026-09-13.
> **Forensic source of truth:** `docs/ECOSYSTEM_FIRST_S3_AUDIT.md` (read-only, 2026-09-13, воспроизводим через `scripts/s3_audit_probe.py`).
> **Base:** S0.5/S1 FROZEN, S2 ACCEPTED W/ RUNTIME GAP, M1–M26 FROZEN, baseline 4-х коммитов `373ffd0..086019d`.
> **Repos:** `docs/ECOSYSTEM_FIRST_ARCHITECTURE.md` §16 (S3 строка), `engineering/DECISION_LOG.md` AD-45..47.

---

## 1. Problem

Экосистема **фактически известна на уровне схемы** (live 1040 нод = snapshot 1040, diff 0; provenance-словарь `EvidenceTrustLevel×4`+`EvidenceSource×4`+`ClaimStatus×4` полон; docs на 63 ноды), но:

1. **Нет вопросительного слоя.** `KnowledgeCore.query()` отвечает только по capability-запросу. Нельзя спросить: «что известно про `AgnesVideo`?», «какие head-ноды производят VIDEO?», «что вообще ещё неизвестно?» (audit §2).
2. **Нет классификации роли ноды** (head/loader/processor/fragment) — она уже выводима из `NodeSchema.input_required` (audit §3), но нигде не материализована; S2 selector использует её как приватную эвристику.
3. **GAP'ы несут в себе только внутри `query()`-ответов** — нет единого агрегированного реестра неизвестного (audit P3).
4. **P1 — тестовое загрязнение persistence:** `validated_nodes.json` содержит `TestNode/FailNode/RestartTestNode` (audit P1) — контракт изоляции данных не зафиксирован.

## 2. Evidence (только из аудита, ничего не додумано)

| Факт | Источник |
|---|---|
| 1040 live / 639 built-in / 53 custom-пакета (~401 классов) | s3_audit_probe §1–2 |
| Snapshot == live (diff 0) | §3 |
| `comfy_api_nodes.*` (~30 пакетов) = внешние API-ноды (Kling/OpenAI/Sora/Veo3…) | §2 |
| Head/fragment различимы по required-input типам (ImageInvert=processor, KSampler=fragment, AgnesVideo-T2V=head) | §4 |
| Agnes: схема live доказана; тариф/работоспособность/VIDEO-совместимость — **НЕ доказаны** | §4 |
| `classify_safety` даёт REQUIRES_CONFIRMATION всем `comfy_api_nodes.*` и custom-нодам | §4 |
| Тесты пишут в production `app/data/knowledge/` | §4/P1 |
| Пользовательские jobs в ComfyUI queue — S2 E2E proof не форсировать | S2 acceptance |

## 3. S3 Scope (строго)

### 3.1 Query layer (thin, read-only, без нового хранения)

Новый модуль **`app/knowledge/queries.py`** + тонкие делегирующие методы-фасад на `KnowledgeCore` (`find_node`, `find_package`, `nodes_by_io`, `explain_node`, `gap_report`). Никакого нового top-level пакета, никаких новых хранилищ.

**Presentation dataclasses (плоские view-объекты, НЕ сущности хранения):**

```python
@dataclass(frozen=True)
class NodeFacts:
    class_type: str
    display_name: str
    category: str
    python_module: str
    package: str | None              # выводится из python_module (group-by, без нового индекса)
    role: str                        # "head" | "loader" | "processor" | "fragment" | "sink"
    inputs: tuple[FieldSpec, ...]
    outputs: tuple[str, ...]
    safety: str                      # из существующего classify_safety
    best_claim_status: str           # max ClaimStatus среди evidence claims (UNKNOWN/INFERENCE/SUPPORTED/CONFIRMED)
    claims: tuple[KnowledgeClaim, ...]
    docs: NodeDocEntry | None
    templates_available: tuple[str, ...]  # S2 select_template(...) без сайд-эффектов (чистая функция)
    in_workflow_registry: bool       # есть ли capability ноды в существующих workflow
    cost: str                        # ВЕЧНО "N/A (per-node cost не введён — AD-46)"; см. §6

@dataclass(frozen=True)
class PackageFacts:
    package_id: str
    classes: tuple[str, ...]
    is_custom: bool                  # python_module.startswith("custom_nodes.")
    api_family: bool                 # module начинается с "comfy_api_nodes." (факт пути, не стоимость)
    safety_profile: str              # доминирующий classify_safety по классам
    doc_coverage: int                # из NodeDocStore
    provenance: str                  # всегда "derived:live-or-snapshot /object_info"

@dataclass(frozen=True)
class GapEntry:
    subject: str                     # node class / package / capability / "persistence"
    gap_type: str                    # существующие GapType + "PERSISTENCE_HYGIENE" (только в отчёте, НЕ в enum)
    description: str
    priority: str

@dataclass(frozen=True)
class NodeExplanation:
    facts: NodeFacts
    what_is_known: tuple[str, ...]   # только из claims/evidence/docs — без выдумывания semantics
    what_is_not_proven: tuple[str, ...]  # из gap_report-подмножества по subject
    template_hint: str               # что скажет S2-селектор (available|no-template)
    provenance_sections: dict[str, str]  # {"schema": "SCHEMA/RUNTIME", "docs": ..., "claims": ...}
```

**Контракты методов (все — чистые функции от текущего состояния KnowledgeCore):**

| Метод | Вход | Выход | Правило |
|---|---|---|---|
| `find_node(class_type)` | str | `NodeFacts \| None` | None если нет ни в snapshot, ни в live-переданном info. Никогда не выдумывает поля. |
| `find_package(package_id)` | str | `PackageFacts \| None` | Группировка по выведенному package. `api_family` — путь модуля, не стоимость. |
| `nodes_by_io(output_type=…, required_inputs_contain=…)` | фильтр | `list[NodeFacts]` | Фильтр по существующим полям схем. |
| `explain_node(class_type)` | str | `NodeExplanation \| None` | См. §3.4. |
| `gap_report()` | — | `list[GapEntry]` | См. §3.3. |

> **Scope-заметка (self-review):** в audit §5 присутствовал 6-й метод `nodes_for_capability`. Утверждённый scope строго ограничен пятью query-методами, поэтому capability-связь подаётся как производная: `NodeFacts.templates_available` + `in_workflow_registry` уже отвечают «связан ли с capability»; отдельный метод — см. OQ4, вне базового S3.

### 3.2 Classification rule (детерминированная функция, единственное определение)

```
required = {f.type for f in schema.input_required}
GRAPH_TYPES = {"MODEL","CLIP","VAE","LATENT","CONDITIONING","CONTROL_NET"} (расширяемый набор)
MEDIA_TYPES = {"IMAGE","VIDEO","AUDIO"}
LOADERS     = классы с outputs ∩ GRAPH_TYPES ≠ ∅ и required ⊆ {ENUM,STRING}

rule:
  outputs ∩ GRAPH_TYPES ≠ ∅ и required ⊆ {ENUM,STRING} → "loader"
  outputs ∩ MEDIA_TYPES ≠ ∅ и (required ∩ GRAPH_TYPES = ∅) и (required ∩ MEDIA_TYPES = ∅) → "head"
  required ∩ MEDIA_TYPES ≠ ∅ и outputs ∩ MEDIA_TYPES ≠ ∅ → "processor"
  required ∩ GRAPH_TYPES ≠ ∅ → "fragment"
  иначе → "sink"/"other"
```

Приоритет сверху вниз (fragment перехватывается раньше generic). Набор GRAPH_TYPES — константа в `queries.py`, не эвристика в нескольких местах; S2 selector остаётся **без изменений** (свой `required_input_types` достаточен; переиспользовать константу — можно, но не обязательно).

### 3.3 GAP registry (derived, НЕ персистентный)

`gap_report()` агрегирует без сайд-эффектов:
1. CANDIDATE_NO_WORKFLOW по всем кандидатам (`query()`-механика);
2. CANDIDATE_NO_TEMPLATE — кандидат, у которого `select_template()==None` (новая категория на существующем факте — НЕ новый GapType в enum, только в GapEntry.description как "candidate_no_template");
3. DOC_GAP — кастомные пакеты без ни одной NodeDoc-записи;
4. PERSISTENCE_HYGIENE — если в `ClaimsPersistence` найдены записи вне known-schemas (сигнатура P1) — **реестр показывает проблему, но НЕ чистит её**;
5. STALE_SNAPSHOT — если вызывающий передал live `object_info`-множество и оно расходится со snapshot (diff через существующий `NodeSchemaStore.diff`).

**Нет отдельной персистентной GAP-БД** (audit P3: агрегация on-demand достаточна; «новая persistence без доказанной необходимости» запрещена).

### 3.4 Explain — template/heuristic только

`explain_node` собирает: identity (schema-факты), IO, role, safety, claims (max ClaimStatus), docs (NodeDoc если есть), templates_available, «what is not proven» (gap-подмножество). **Запрещено:** генерировать семантику из названия класса; оценивать без claim; LLM.

### 3.5 P1 hygiene contract (решение + обязательства)

**Contract (фиксируется, чистка данных — ОТДЕЛЬНОЕ решение автора):**
1. Любой код, создающий `ClaimsPersistence`/`NodeSchemaStore`/`EvidenceStore` **в тестах**, обязан передавать явный `data_dir` (tmp_path fixture). Дефолт `app/data/knowledge` = production-дир.
2. Regression-страховка: S3 тест проверяет, что вызовы `gap_report()/find_node()` не пишут файлов (mtime-снимок директории данных).
3. Cleanup: `TestNode/FailNode/RestartTestNode` в `app/data/knowledge/validated_nodes.json` — список зафиксирован (audit P1); **удаление — за автором**, S3 данные не трогает.

## 4. Provenance (переиспользование, НЕ новый enum)

| Запрошенная категория | Существующий эквивалент |
|---|---|
| INTROSPECTED | `EvidenceTrustLevel.SCHEMA` + `EvidenceSource.RUNTIME` |
| DOCUMENTED | `DECLARED_PURPOSE` (+ `EvidenceSource.PROJECT_METADATA`) |
| SOURCE_INSPECTED | `OBSERVED_SOURCE_STRUCTURE` (+ `LOCAL_SOURCE`) |
| SELF_TESTED | `OBSERVED_BEHAVIOR` + `EvidenceSource.EXECUTION` + `ClaimStatus.CONFIRMED` |
| USER_CONFIRMED | **ОТСУТСТВУЕТ — вне S3** (G2/AD-Q2; feedback→claim неразрешён молча) |

`NodeFacts.best_claim_status` + `provenance_sections` — только проекция существующих данных. **Никакого нового `Provenance`-enum; никакого числового confidence.**

## 5. Инварианты и границы

1. **Advisory-only:** все методы — чистые чтения. `gap_report`/`find_*` не пишут, не региструют, не меняют `Readiness`, не трогают execution eligibility (AD-45 сохранён).
2. **`/object_info` ≠ доказательство работоспособности** (AD-18): `find_node` возвращает факты схемы; `CONFIRMED` — только из существующих claims (validated только RuntimeValidator-путём, сейчас deferred S6).
3. **Per-node cost НЕ вводится** (AD-46): `NodeFacts.cost` = константная строка-маркер `N/A (AD-46)`; `api_family: bool` — путь модуля, не стоимость. `comfy_api_nodes.*` остаются **API/cost boundary**: их безопасность при синтезе обеспечивает существующий S2 `REQUIRES_CONFIRMATION` + S1 backend/manifest cost-guard. Никакого нового cost-механизма.
4. **S2 не ломается:** catalog/selector/builder/safety не изменяются; `explain_node.templates_available` вызывает `select_template` (чистая). `synthesize_candidates` не трогается.
5. **Zero изменения** в: `app/engine/**`, `app/registry/**`, `app/synthesis/**`, `app/agent.py`, `app/conversation.py`, `app/ui.py`, PlanContext/ExecutionRecord/JobState/ExperienceStore (M25/M26), `app/knowledge/gaps.py` (enum не расширяется), `models.py`, `runtime_validator.py`.
6. **Нет background discovery/execution, нет LLM, нет graph solver.**
7. Реализация (будущая): только `app/knowledge/queries.py` (+~150 строк) + делегаты в `core.py` (+~30 строк) + тесты.

## 6. S3 сознательно НЕ делает (явный список)

| Не делает | Почему / куда отложено |
|---|---|
| Реализует self-test (исполнение нод) | Только design-контракт §7; активация = S6 (после safety-данных S3) |
| USER_CONFIRMED | G2 требует отдельного AD (Q2: auto-CONFIRMED risk) |
| Per-node CostTier | Решение S1 (AD-46): cost = backend+workflow |
| Числовой confidence | Намеренный отказ baseline (§10 ECOSYSTEM) |
| Новый provenance-enum | Существующий словарь полон |
| Персистентный GAP registry | Derived on-demand достаточно (audit P3) |
| Миграция/чистка `validated_nodes.json` | P1 contract §3.5; удаление — отдельное решение автора |
| Auto-registration synthesized workflows | S2 accepted: synthesis ≠ validation (AD-47) |
| Изменения Agent/ConversationAgent/Engine/Registry | Вне scope; S0.5 advisory-контур достаточен |
| UI/API endpoints | S4+ (explain поверх этого design) |
| Live-comparison-обязаловка | `gap_report(live_info=None)` — live передаётся вызывающим, сам S3 не ходит в сеть (advisory, без скрытых I/O) |

## 7. Self-test design contract (только контракт, без реализации)

Для будущего S6 (RuntimeValidator activation), S3 предоставляет данные и правила:

```
self_test_candidate(node) ⇔
    safety == ALLOWED(queries.classify_safety)
    AND role in {"head","processor","sink"} (fragment/loader сами по себе не исполнимы)
    AND backend_cost ∈ {FREE, TRIAL}  (S1 authoritative; UNKNOWN/PAID → не авто)
    AND template_available OR capability уже в workflow-registry
    AND явная команда пользователя (NG3: без background/mass)
Результат исполнения → существующий путь RuntimeValidator.validate_node(class_type, workflow)
→ CONFIRMED + OBSERVED_BEHAVIOR (существующая семантика, не новая)
```

S3 НЕ вызывает ComfyUI, НЕ создаёт Job, НЕ трогает `_calculate_validation_score`.

## 8. Backward compatibility

- Все методы — новые, аддитивные; существующие вызывающие коды не меняются.
- `KnowledgeCore.__init__` — без новых параметров.
- Форматы JSON-хранилищ (node_schemas/validated_nodes/confirmed_claims) — неизменны.
- S0.5 preflight / S1 filter / S2 synthesis — не затронуты; их тесты обязаны остаться зелёными без правок.

## 9. Test matrix (для будущей реализации)

| # | Тест | Ожидание |
|---|---|---|
| Q1 | find_node(built-in ImageInvert из snapshot-fixture) | processor, SCHEMA provenance, INFERENCE-level |
| Q2 | find_node(unknown) → None | без выдумки |
| Q3 | find_package(pollinations-byop) | 5 классов, api_family=False, safety=REQUIRES_CONFIRMATION |
| Q4 | find_package(comfy_api_nodes.nodes_openai) | api_family=True, cost=N/A-маркер |
| Q5 | nodes_by_io(VIDEO) | включает head-видеоноды, исключает fragment |
| Q5b | capability-relation fields: для injected candidate с шаблоном `templates_available≠∅`, `in_workflow_registry` корректно для built-in | capability-связь через fields (OQ4) |
| Q6 | classification: KSampler=fragment, CheckpointLoader=loader | правила §3.2 |
| Q7 | explain_node без docs и без CONFIRMED-claims | «not proven» непустой; без выдуманной семантики |
| Q8 | gap_report содержит CANDIDATE_NO_WORKFLOW для injected candidate без workflow | derived |
| Q9 | gap_report doc_gap для пакета без NodeDoc | derived |
| Q10 | gap_report persistence_hygiene при TestNode-подобных записях | показывает, не чистит |
| Q11 | No-side-effect: mtime snapshot каталога данных не меняется после всех вызовов | invariant |
| Q12 | Readiness неизменен: до/после query-API вызовов одинаковый KnowledgeResponse | advisory |
| Q13 | Registry неизменен: WorkflowRegistry/CapabilityRegistry без правок | frozen |
| Q14 | S1: gap_report/find не обходят cost-guard (нет новых selection-путей) | frozen |
| Q15 | S2 regression: test_s2_synthesis без изменений зелёные | compatibility |
| Q16 | M-регрессия: full core-suite зелёный | no-regression |

## 10. Acceptance criteria (для реализации S3)

1. `queries.py` + делегаты; 0 изменений в engine/registry/synthesis/agent/conversation/ui.
2. Все §9 тесты зелёные; полная регрессия без правок существующих тестов.
3. `explain_node` для 6 representative nodes (audit §4) даёт отчёт, где каждая строка прослеживается к существующему источнику (schema/docs/claim/none).
4. GapReport не содержит ни одного «доказано»-утверждения без claim/CONFIRMED.
5. P1 contract зафиксирован тестом-страховкой; чистка данных НЕ выполнена.
6. Self-review A–L (из задачи gate) PASS с file/test evidence.
7. Forensic verification (8-point, как S0.5/S1) после реализации.

## 11. Open questions (не блокируют approval этого design)

1. **OQ1:** включить ли `nodes_by_io` фильтр по optional-inputs тоже, или только required? (Дефолт: required; optional — параметром.)
2. **OQ2:** `api_family` для `websocket_image_save` (не comfy_api_nodes, но сетевой) — оставить False (факт пути) или добавить отдельный сетевой флаг? (Дефолт: оставить False; safety-классификация уже даёт REQUIRES_CONFIRMATION.)
3. **OQ3:** нужна ли кэш-карта package→classes между вызовами? (Дефолт: не кэшировать; 1040 итераций — копейки.)
4. **OQ4:** добавлять ли `nodes_for_capability` 6-м методом, когда появится потребитель за пределами explain/s2 (пока покрыто полями `templates_available`/`in_workflow_registry`)? Вне базового S3-объёма.

---

**S3 DESIGN STATUS: READY (scope строго по audit)**

**IMPLEMENTATION APPROVAL: NOT REQUESTED**

**STOP / WAIT FOR APPROVAL.**
