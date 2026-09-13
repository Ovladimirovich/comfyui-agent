# ECOSYSTEM-FIRST & TOOL LEARNING — Architectural Audit & Design

> **Статус:** ARCHITECTURE / DESIGN AUDIT (DRAFT — НЕ реализация).
> **Дата:** 2026-09-13.
> **Основа:** только фактическое текущее состояние репозитория `C:\cd\ComfyUI_AMD\agent` (HEAD `8e96378 S7+S9: Composer connectors + multimodal asset input`), текущий код `app/`, `tests/`, `workflows/` и актуальная документация (`docs/PROJECT_SPEC.md`, `docs/…`, `engineering/HANDOFF.md`, `tasks/ACTIVE.md`).
> **Ограничения:** audit & design только; никакого production-кода, никакого commit. Соответствие общему правилу: M26 FROZEN, новые milestones — только после approval автора.

> **Легенда статусов.** Каждый пункт помечен как:
> **IMPL** — already exists (реализовано в коде);
> **REUSE** — can be reused (уже есть и переиспользуется как есть);
> **EXT** — minimal extension required (минимальное расширение контракта);
> **FUTURE** — future work (не на этом этапе);
> **N/A** — not required.
> **SPECD** — specified/planned, but not integrated (описан/спроектирован, но НЕ интегрирован в execution path; без правки кода не работает).

---

## 1. Current State

| Пункт | Факт | Статус |
|---|---|---|
| HEAD | `8e96378 S7+S9: Composer connectors + multimodal asset input`; рабочая ветка git | IMPL |
| Milestones | M1–M25 DONE/FROZEN; M26.1/26.2/26.4 ACCEPTED; M26.3 REDEFINED/DEFERRED (Video Editor — отдельный проект, AD-44 SUPERSEDED); M26 READY TO FREEZE | IMPL |
| Тесты | Regression **192 passed**, 1 skipped; 5 pre-existing INFRA fails (`test_planner_context`, AD-18) без изменений (`engineering/HANDOFF.md`) | IMPL |
| Код | `app/` — 75 файлов `.py`; `tests/` — 80 файлов `test_*.py` (~1019 `test_`-функций с учётом real-E2E и skip) | IMPL |
| Workflows | **9 исполнимых** `workflow.json`: `txt2img`, `img2img`, `upscale`, `video_generate`, `video_image_to_video`, `audio_generate`, `text_generate`, `pollinations_image`, `image_inpaint` (все с `declared_only` = false) | IMPL |
| Deferred/blocked | `audio.generate` real E2E — DEPENDENCY_BLOCKED (Sonilo 401); `image.upscale` model-based — BLOCKED (пусто `upscale_models/`); LLMPlanner → `fallback_proxy :20130` недоступен | IMPL |
| Source of truth | `docs/PROJECT_SPEC.md` v0.2 (иерархия docs → engineering → tasks); §24 хранит Architectural Decisions (AD-01..AD-44, см. `engineering/DECISION_LOG.md`) | IMPL |
| Post-M26 вывод | HANDOFF: «NO NEW MILESTONE JUSTIFIED YET» (единственный кодовый gap — LLMPlanner inert). Настоящий документ — read-only audit/design и НЕ противоречит этому выводу | IMPL |

---

## 2. Existing Architecture Strengths (для Ecosystem-First / Tool Learning)

Текущая архитектура уже содержит «скелет» обеих направлений. Сильные стороны — по слоям.

| Слой | Компонент (файл) | Что уже есть | Статус |
|---|---|---|---|
| Transport / Discovery | `ComfyClient` (`app/comfy/client.py`) — `get_object_info()`, `discover_checkpoints()`, **`discover_custom_node_packages()` → `dict{package: set[node_class_names]}`** (реализовано), `get_system_stats()`, HTTP/WS, remote-capable (AD-29) | Первичный факт-источник экосистемы из живого ComfyUI | IMPL |
| Registry layer | `DiscoveryFacts` (`app/registry/discovery.py`) + authority-флаги `runtime_available/models_available/custom_nodes_available`; `_custom_node_names()` нормализует оба формата manifests | Ключевой pre-flight контракт фактов | IMPL |
| | `CapabilityRegistry` (`app/registry/capability.py`); `WorkflowRegistry` (`app/registry/registry.py`); `ModelRegistry` (`app/registry/model.py`, `ModelKind`, `ModelInfo.identity`); `BackendCatalog` + `BackendSpec` (`app/registry/backends.py`) | Каталоги capability/workflow/model/backend | IMPL |
| | Workflow lifecycle `DISCOVERED→VALIDATED→AVAILABLE|UNAVAILABLE|UNKNOWN`; `UNKNOWN ≠ AVAILABLE` (AD-18); причины `UnavailableReason`/`UnknownReason` | Честная совместимость, безопасный ranking | IMPL |
| Knowledge | `NodeSchemaStore` (`app/knowledge/node_schema.py`, кэш-снапшоты + `diff()`), `KnowledgeCore` (`app/knowledge/core.py`), `CapabilityCandidate`+`UsageHypothesis` (inference из схем), `Claims` (`ClaimStatus` 4 уровня), `EvidenceStore`, `LocalResearchProvider`, `RuntimeValidator`, `ClaimsPersistence`, `NodeDoc` | Полный цикл «обнаружение → гипотеза → evidence → validation» | IMPL |
| Verification | `Verifier` (output-contract), `SemanticVerifier` (vision), `RuntimeValidator` (реальный запуск), temporal/sequence verification | Двухуровневая проверка результата | IMPL |
| Experience / Memory | `ExperienceStore` (`app/engine/experience.py`), `ChainExperience`, `SequenceExperience`, `ExperienceAnalytics`, `ExperienceHint`; `ExecutionHistory`+`HistoryAnalytics`; `FeedbackStore` — **wired в production** (D12 closed) | Experience = факт; ranking/preference, не prohibition | IMPL |
| Planning / Composer | `AdaptivePlanner` (history+feedback+experience soft defaults), `Composer.compose(..., experience_hint=...)` → suggestions, `TaskDecomposer`+`ExecutionChain` | Reuse-сигналы на уровне планирования | IMPL |
| Execution | `WorkflowEngine`, `ExecutionEngine`, chain execution, `RetryPolicy`, `Gateway` (M20), `Reconciler` (M21), HITL (M22), `CorrectionStrategy` (M23) | Многошаговая, fault-tolerant execution | IMPL |
| Multi-backend | `BackendCatalog.choose()` (capability-filter, priority, probe по VRAM); Provider ≠ Backend (AD-01/29); remote доказан (Colab T4, M5/M6) | Local/remote/cloud — варианты, а не иерархия | IMPL |

Проектные документы, уже задающие направление (не реализация):
- `docs/ARCHITECTURE_ECOSYSTEM_DISCOVERY.md` (2026-09-06) — онтология экосистемы (Capability/Primitive/Workflow/Provider/AccessPoint/Backend/Runtime/SpecialistOperator), граница **Agent Core vs External Ecosystem**, карта провайдеров/нод/backend.
- `docs/EXTENDED_DISCOVERY_DESIGN.md` (2026-09-08) — Extended Discovery; **шаги 1–3, H.4, Step 7 уже реализованы** (`discovery.py`, `ComfyClient.discover_custom_node_packages`).
- `docs/28_LEARNING_ARCHITECTURE_AUDIT.md` — рекомендация layered learning; FINDING 1 («feedback never wired») **закрыт** регрессией D12 (`test_m24_1_production_wiring.py`).

---

## 3. Ecosystem-First Goal

> Ответ не на вопрос «какой известный workflow запустить?», а на вопрос «какими доступными — прежде всего бесплатными — средствами решить задачу?»

Требуемая цепочка: `discover → inspect → infer capabilities → validate → rank → execute → verify → remember`.

**Как она маппится на существующую архитектуру:**

| Этап | Существующий механизм | Статус |
|---|---|---|
| discover | `ComfyClient.get_object_info()` → `NodeSchemaStore.refresh()`; `ModelRegistry.discover()`; `discover_custom_node_packages()`; `discover_runtime()`; `DiscoveryFacts` | IMPL |
| inspect | `NodeSchema` (inputs/outputs/types/options/tooltip/python_module); `NodeDocEntry` (purpose/configuration/examples); `LocalResearchProvider` (README + python source + metadata) | IMPL |
| infer capabilities | `CandidateGenerator` → `CapabilityCandidate{node_class, capability, status=INFERENCE, usage:UsageHypothesis}`; `KnowledgeCore.query()` → readiness `EXECUTABLE/CANDIDATE_ONLY/GAP/UNKNOWN`, gaps | IMPL |
| validate | `KnowledgeCore.apply_research_results()` (evidence merge: INFERENCE→SUPPORTED); `RuntimeValidator.validate_node()` (реальный запуск → `OBSERVED_BEHAVIOR` + `CONFIRMED`); `WorkflowStatus`/AD-18 совместимость | IMPL |
| rank | `_select_manifest()`: validated-score → priority → min_vram → id → version; `BackendCatalog.choose()`; `ModelRegistry.resolve/compatibility` | IMPL |
| execute | `WorkflowEngine`/`ExecutionEngine` → `ComfyUIProvider` → `ComfyClient` → Job → Verifier | IMPL |
| verify | `Verifier` + `SemanticVerifier` + temporal/sequence checks; результат → Asset (только после Verifier, AD-MODEL-BINDING-001) | IMPL |
| remember | `ClaimsPersistence`, `EvidenceStore`, `ExecutionHistory`, `ExperienceStore`, `FeedbackStore`; предпочтения → `AdaptivePlanner`/`Composer` | IMPL |

**Источники возможностей** (по требованиям задачи): установленные custom nodes — RESTRUCTURED покрыт (`discover_custom_node_packages` + candidates); built-in nodes — покрыт (`/object_info` → schemas → candidates); существующие workflow — покрыт (WorkflowRegistry); workflow из внешних источников — **НЕ покрыт** (**FUTURE**, конфиденциально: требует новый источник + безопасную ингестию, за пределами ядра); модели — покрыт (`ModelRegistry`); локальные backend — покрыт (`BackendCatalog`); удалённые ComfyUI — покрыт (AD-29, `COMFY_REMOTE_URL`); другие Provider/Backend — частично (contract существует, новых реализаций нет; **FUTURE**); бесплатные/trial-сервисы — **НЕ покрыт** (нет cost-метаданных, см. §11); будущие инструменты — есть точка расширения: `BackendCatalog` + Provider contract (+ MCP/wrapper — **FUTURE**, не в этом audit).

**Вывод по направлению:** существующая архитектура УЖЕ выполняет цепочку ecosystem-first для установленного в ComfyUI набора нод/workflow/моделей/backend. Не хватает: (1) явной cost-политики (§11 EXT), (2) внешних источников workflow/провайдеров (§14 FUTURE), (3) «explain»-контракта (§14 EXT).

---

## 4. Tool Learning Goal

> **Примечание (NG3 compliance).** «Tool Learning» здесь = «агент понимает возможности своих инструментов» (discovery→understanding→verification), НЕ autonomous self-reflection / self-modification (NG3). Цикл управляется явными процессами (discovery, research, validation, user feedback), не автономным поведением.

Сценарий: «Пользователь установил набор нод и говорит *Разберись сам*». Стадии и покрытие:

| Стадия | Требование | Существующий механизм | Статус |
|---|---|---|---|
| **DISCOVER** | Найти пакеты, node classes, workflows, ресурсы | `discover_custom_node_packages()` (package→{classes}), `NodeSchemaStore.refresh()` (added/removed/changed), `ComfyClient.get_object_info()`, WorkflowRegistry discovery | IMPL |
| **INSPECT** | Назначение, inputs/outputs, типы, зависимости, модели, источники, docs, source | `NodeSchema`+`FieldSpec` (types/required/min/max/options/tooltip); `NodeDocEntry` (purpose/configuration/examples/related/version/source_file); `LocalResearchProvider` (README/python/metadata) | IMPL |
| **UNDERSTAND** | Реальные capabilities из инструментов | `CandidateGenerator` → `CapabilityCandidate.usage:UsageHypothesis` (mode/input_mappings/cardinality); claims `subject-predicate-object`; `KnowledgeCore.query()` + gap detection | IMPL |
| **SELF-TEST** | Минимальный безопасный эксперимент; schema ≠ работоспособность | `RuntimeValidator.validate_node()` → `ValidationResult{SUCCESS/FAILURE/ERROR/TIMEOUT}`, `timeout_seconds=120`; `KnowledgeCore.validate_runtime()`; `validated_nodes` persisted | IMPL + **EXT** (безопасные границы, см. §13 G5) |
| **VERIFY** | Разделять documented/discovered/inspected/self-tested/user-confirmed/proven | `EvidenceTrustLevel` (schema/declared/observed/observed_source); `ClaimStatus` (UNKNOWN/INFERENCE/SUPPORTED/CONFIRMED); `last_verified`; authority-флаги `DiscoveryFacts`; `FeedbackRecord.rating` (вне knowledge) | IMPL (кроме «user_confirmed» внутри knowledge — см. §10, §13 G2) |
| **EXPLAIN** | Объяснить пользователю что/когда/как/какие модели/ограничения/что проверено | Нет готового выходного контракта; данные есть (claims+evidence+NodeDoc), но нет NL/структурированной сборки для UI | **EXT** |
| **CO-USE** | объяснить → предложить → уточнить → собрать workflow → запустить → проверить | `Agent.generate()` + `ConversationAgent.turn()` + `Composer` (chain построение) + HITL bridge (M22); experience→suggestions (M26.4); candidate→workflow synthesis (S2 templates) | IMPL (сборка workflow для НОВЫХ нод — через `Composer`/манифест + **S2 template synthesis (4 паттерна)**; model-dependent/multi-asset templates — deferred, см. §13 G4) |
| **REMEMBER** | рабочие workflow/параметры/ограничения/нерабочие комбинации/подтверждения | `ClaimsPersistence` (confirmed claims + validated nodes), `EvidenceStore`, `ExperienceStore` (chains: params/workflow/state/error/corrections), `ExecutionHistory` (error_class), `FeedbackStore` | IMPL (без структурированных «limitation/failure» ноды как знания -> §13 G4) |
| **REUSE** | Сначала проверить подтверждённое, не исследовать заново | `_calculate_validation_score()` → validated nodes влияют на ranking workflow*; `AdaptivePlanner` preferred params; `Composer` experience suggestions | IMPL (*производственный источник validated nodes для Agent — SPECD, см. §8.0) |

**Вывод по направлению:** архитектура построена так, что полный цикл Tool Learning **выражается через существующие контракты** (компоненты существуют). Пробелы — точечные: ~~Agent pre-flight wiring (Slice 2 — SPECD)~~ **реализовано S0.5 (FROZEN)**; user_confirmed внутри claims, explain-контракт, безопасный self-test, структурированные limitation/usage-паттерны, ~~cost-tier~~ **реализовано S1 (FROZEN)**. Явная «новая Memory/Experience система» **НЕ требуется** — требуется расширение существующих.

---

## 5. Current Discovery Architecture

- **Live-источник:** `ComfyClient` (HTTP/WS к `127.0.0.1:8188`, remote-capable) отдаёт `/system_stats`, `/object_info` (953+ ноды), `/queue`, `/history`. Proxy для localhost исключён (`http.client`, без `urllib`). Отражено в `app/registry/runtime.py`, `app/comfy/client.py`.
- **Extended Discovery (реализован):** `Agent._discover_facts()` → `DiscoveryFacts{runtime, models, custom_nodes:{package:{classes}}, *_available}`; `discover_custom_node_packages()` извлекает пакеты из `python_module`, фильтрует built-in (`nodes.*`, `comfy_extras.*`). График анализа `docs/EXTENDED_DISCOVERY_DESIGN.md` §A.1–A.3, §B, §E — реализован.
- **Offline/knowledge-источник:** `NodeSchemaStore` — JSON-снапшоты (`app/data/knowledge/node_schemas.json`, ~959 схем) + `diff()` (added/removed/changed). Step 7: кэш используется как fallback при недоступности live ComfyUI, при этом `custom_nodes_available=False` (cache ≠ live, AD-18).
- **Authority-правила:** R1 raw-facts > defaults; R2 empty-set ≠ all; R3 partial success; R4 no inference without source (`fp16/xformers/comfyui_version` остаются `None` → UNKNOWN); R5/R6 package-vs-class exact match, built-in excluded.

**Модели/backend/ноды:** `ModelRegistry` (per-backend, `ModelKind{CHECKPOINT,LORA,VAE,CONTROLNET,EMBEDDING,UNKNOWN}`, `ModelInfo.identity`, `resolve/compatibility`), `BackendCatalog` (`BackendSpec{backend_id, base_url, kind, priority, capabilities, disabled, description}`), `RuntimeInfo{accelerator, vram_gb, fp16=None, xformers=None, lowvram, comfyui_version=None}`.

**Статус:** IMPL. Точек расширения для «других источников возможностей» достаточно (`BackendCatalog` + Provider contract + `DiscoveryFacts.extend`).

---

## 6. Current Capability / Workflow Architecture

- **Capability** ≠ Workflow (аксиома). `CapabilityRegistry` — плоский декларативный каталог (`image.generate`, `image.edit`, `image.inpaint`, `image.upscale`, `video.generate`, `video.image_to_video`, `video.video_to_video`, `audio.generate`, `text.generate`, `custom.execute`).
- **Workflow** = `workflow.json` (ComfyUI-граф) + `manifest.json`: inputs/asset_inputs/outputs/parameters/required_models/required_custom_nodes/min_comfyui_version/requirements/limits/declared_only, version semver, `workflow_id@version` pinning (AD-17), `latest` только на этапе selection (AD-24).
- **Lifecycle:** DISCOVERED → VALIDATED → AVAILABLE/UNAVAILABLE/UNKNOWN; причины диагностируемы; **UNKNOWN ≠ AVAILABLE** (AD-18, enforced).
- **Compatibility filter:** `evaluate_compatibility()` — runtime/models/custom_nodes/assets/inputs (AD-23 input compatibility по доступным ассетам).
- **Selection:** `_select_manifest()` — только AVAILABLE; ranking: `_calculate_validation_score` (validated nodes, S4) → priority → min_vram → id → version.
- **`required_custom_nodes` в manifests — смешанный формат:** package-имена (`pollinations-byop`, `comfyui-openai-compatible`) и node class names (`SoniloTextToMusic`, `SaveAudio`, `CreateVideo`, `SaveVideo`). `_custom_node_names()` нормализует оба → current discovery поддерживает оба без изменений manifests.

**Статус:** IMPL. Capability-Candidate inference (`CapabilityCandidate.status=INFERENCE`, «ГИПОТЕЗА, НЕ production capability») — правильный разделитель декларативных и выведенных capability (именно это нужно для Tool Learning: кандидаты из новых нод живут как гипотезы, в реестр попадают только подтверждённые).

---

## 7. Current Provider / Backend Architecture

- **Provider ≠ Execution Backend** (AD-01/AD-29). `ComfyUIProvider` (`app/provider/comfyui.py`) — `upload_asset→BackendRef`, `execute→prompt_id`, `get_job`, `cancel`, `view`, `discover_checkpoints`. Provider НЕ выбирает workflow (AD-22).
- **BackendRef** = `{provider, backend, reference, metadata}`; ComfyUI-специфичный `reference={filename,subfolder,type}` (AD-26).
- **BackendCatalog** (`app/registry/backends.py`): `from_env()` (`COMFY_BACKENDS` / `COMFY_REMOTE_URL` / `COMFY_URL`; дефолт `local_comfyui@127.0.0.1:8188`); `choose(capability, probe)` — eligibility: not disabled + capability разрешён; сортировка по priority; probe — по `vram_total`. Remote доказан (Colab T4, M5/M6).
- Физическое расположение backend = «не concern» верхних слоёв; запрет `if remote:/if localhost:` в domain-логике (инварианты AD-29).

**Статус:** IMPL. Free/local/cloud = варианты backend/provider (соответствует требованию «не жёсткая иерархия»). **Отсутствует cost-атрибут** → см. §11 (EXT).

---

## 8. Current Knowledge / Experience Architecture

Это критический раздел — здесь лежит то, что Tool Learning в основном УЖЕ может переиспользовать.

> **RECONCILIATION NOTE (2026-09-13, docs↔code audit).** Knowledge Core Slice 2 («pre-flight query в `Agent.generate()`/`ConversationAgent.turn()`», «readiness на Job») в коде НЕ реализован. Фактически по HEAD:
>
> **Already implemented (IMPL)**
> * Knowledge Core Slice 1 — весь пакет `app/knowledge/` (NodeSchema/NodeSchemaStore, candidates, claims+evidence, gaps, Core=query/readiness/research_requests, LocalResearchProvider, EvidenceStore, RuntimeValidator, ClaimsPersistence, NodeDoc);
> * evidence / candidates / gaps / validation как механизмы — существуют и покрыты тестами;
> * существующие Experience/Feedback-механизмы (M25/M26, FeedbackStore wired) — реализованы.
>
> **Specified but not integrated (SPECD)**
> * Knowledge Core Slice 2 / Agent pre-flight: `Agent`/`ConversationAgent` НЕ имеют `knowledge_core`-параметра (`agent.py:150`), `_plan_result_to_query` отсутствует, полей `_knowledge_readiness`/`_knowledge_gaps` в `Job` (`app/engine/job.py`) нет. Тест `tests/test_knowledge_integration_s2.py` падает: `TypeError: Agent.__init__() got an unexpected keyword argument 'knowledge_core'`.
> * RuntimeValidator hook: `_validate_capability_nodes_background` (`agent.py:411`) — dead code (нет production-вызовов) и сигнатурно несовместим (`validate_node(node_type)` без `workflow`, `runtime_validator.py:56` → TypeError). В production `Agent._validated_nodes` пуст → `_calculate_validation_score` всегда 0.
>
> **Future extension (FUTURE)**
> * использование Knowledge Core перед discovery/self-test/execution (pre-flight) — только после approved implementation milestone.
>
> Все упоминания «Slice 2 pre-flight» / «KnowledgeCore pre-flight» в этом документе трактуются как SPECD. См. §4 REUSE, §8 KnowledgeCore.query, §12.
>
> **STATUS UPDATE (2026-09-13, после S0.5/S2):** Slice 2 / Agent pre-flight **РЕАЛИЗОВАН как milestone S0.5** (FROZEN/VERIFIED): `knowledge_core` param, `_plan_result_to_query`, `Job._knowledge_readiness/_knowledge_gaps` — в production path (advisory). Пункт «RuntimeValidator hook dead» остаётся верным (deferred S6). Ниже по документу «pre-flight SPECD» читать как «SPECD → реализовано S0.5». См. §16.

### Knowledge (app/knowledge)

| Контракт | Содержимое | Статус |
|---|---|---|
| `NodeSchema` + `FieldSpec` | class_type, display_name, category, input_required/optional (name/type/required/default/min/max/options/tooltip), output_types/names, python_module, discovered_at, source («runtime:/object_info»). **Нет version/description** | IMPL |
| `NodeDocEntry` + `NodeDocStore` | human-доки: purpose, inputs/outputs_documented, configuration, examples, related_nodes, source_file, version, comfyui_version; `ingest_from_file/text`, `get_doc_for`, `search` | IMPL |
| `CapabilityCandidate` + `CandidateGenerator` | node_class, capability, status=INFERENCE, evidence[SCHEMA/RUNTIME], **usage: UsageHypothesis{mode, input_mappings, cardinality}**, claims | IMPL |
| `KnowledgeClaim` | claim, subject, predicate, object, **status: ClaimStatus**, evidence[], **last_verified** | IMPL |
| `ClaimStatus` | 4 уровня без числового confidence (намеренно, `models.py:32`): UNKNOWN → INFERENCE → SUPPORTED → CONFIRMED | IMPL |
| `EvidenceTrustLevel` | schema / declared / observed / observed_source | IMPL |
| `EvidenceSource` | runtime / local_source / project_metadata / execution | IMPL |
| `EvidenceStore` | ingest ResearchResult; `merge_into_claims`: INFERENCE+declared/observed_source→SUPPORTED; SUPPORTED+evidence→SUPPORTED (без auto-CONFIRMED); CONFIRMED — max | IMPL |
| `LocalResearchProvider` | `research(request)` по README + Python source + metadata; ResearchSource{path, kind(readme/python_source/metadata), content_preview}; **без web/LLM/remote** | IMPL |
| `RuntimeValidator` | `validate_node` → ValidationResult{SUCCESS/FAILURE/ERROR/TIMEOUT}; upgrade → CONFIRMED + OBSERVED_BEHAVIOR + predicate `validated_by_execution` | IMPL |
| `KnowledgeGap`/`GapType`/`GapNature` | UNKNOWN_CAPABILITY, INSUFFICIENT_EVIDENCE, CONFLICTING_KNOWLEDGE, STALE_KNOWLEDGE, NO_WORKFLOW, CANDIDATE_NO_WORKFLOW, WORKFLOW_NODE_ABSENT; nature KNOWLEDGE/EXECUTION/COMPATIBILITY | IMPL |
| `KnowledgeCore.query()` | KnowledgeQuery → KnowledgeResponse{candidates, claims, gaps, readiness(EXECUTABLE/CANDIDATE_ONLY/GAP/UNKNOWN), research_requests} — API реализован | IMPL (API); pre-flight в `Agent`/`ConversationAgent` — **IMPL via S0.5** (advisory; см. §8.0 STATUS UPDATE) |
| `ClaimsPersistence` | `validated_nodes.json` + `confirmed_claims.json` (JSON, дедуп по (subject,predicate,object)) | IMPL |

### Experience / Memory (app/engine, app/context)

| Контракт | Содержимое | Статус |
|---|---|---|
| `ExecutionRecord` | prompt_id, capability, params, workflow_id@version, state, duration, error_message/error_class, attempt, **corrections_applied (M23)**, chain_id (M25), output_assets | IMPL |
| `ExecutionHistory` | JSONL append-only; get_successful/failed, success_rate, dispatch tracking (M21) | IMPL |
| `ChainExperience`/`ChainStepExperience` | chain_id, steps (capability, params, workflow_id@version, state, error_class, corrections), sequence_assets, temporal_consistency; «факт, не правило» | IMPL |
| `ExperienceStore` | JSONL per chain (`data/experience/chains/`); record/get_by_chain/list_chains | IMPL |
| `SequenceExperience` | computed view: image_assets→video_asset, params, temporal_consistency | IMPL |
| `ExperienceAnalytics` | temporal_stats, preferred_params (ranking, `EXPERIENCE_MIN_SAMPLES_FOR_PREFERENCE=2`, scalar-only, БЕЗ prohibition) | IMPL |
| `ExperienceHint` | capability, preferred_params, avg_temporal_consistency, sample_count → передаётся в `Composer.compose()` (M26.4) | IMPL |
| `FeedbackStore` | rating 1–5 (JSONL); **wired** в `AdaptivePlanner` + `RetryPolicy` (D12 closed) | IMPL |
| `AdaptivePlanner` | preferred params из history+feedback+experience; порог ≥3 SUCCESS по capability; soft default (explicit перезаписывает) | IMPL |

### Ответы на вопросы аудита (раздел 5 задания)

1. **Что сохраняется?** Schema-снапшоты, candidates, claims+evidence, validated_nodes, confirmed_claims, node docs, execution history, experience chains, feedback, preferences.
2. **Что извлекается?** KnowledgeQuery (candidates/claims/gaps/readiness/requests), EvidenceStore.get_evidence_for, validated/confirmed выдачи, preferred_params (ExperienceAnalytics/HistoryAnalytics), chain summary.
3. **Provenance?** Частично: `source` + `source_type` + `trust_level` + `timestamp` + `last_verified` (детерминированный источник есть, но нет поля-идентификатора «кто/каким процессом» — см. G2/G6).
4. **Confidence?** Отсутствует числовой (намеренно). Дискретный `ClaimStatus` 4 уровня — рабочий аналог.
5. **Verification status?** Есть: `ClaimStatus` + `last_verified` + `ValidationResult` + `SemanticVerifier` + `error_class="verification"` + `temporal_consistency`.
6. **Различение documented/discovered/inspected/self-tested/user-confirmed/proven?** Маппится эвристически: `SCHEMA`≈discovered; `DECLARED_PURPOSE`/`OBSERVED_SOURCE_STRUCTURE`≈inspected; `OBSERVED_BEHAVIOR`+`CONFIRMED`+`validated_by_execution`≈self-tested/proven. **«user_confirmed» внутри knowledge отсутствует** (rating живёт в FeedbackStore, не связан с Claim) — главный пробел стадии (G2).
7. **Практический способ использования capability?** Частично: `UsageHypothesis` (гипотеза), `ChainStepExperience.params/workflow_id`, `preferred_params`. Структурированного «рецепта» нода→параметры→ограничения нет (G4).
8. **Failure/limitation?** Фиксируются (RuntimeEvidence.error_message, ValidationResult.FAILURE, ExecutionRecord.error_class, ChainStepExperience.error) — но НЕ как knowledge-сущность «нода имеет известное ограничение»; не агрегируются в claims (G4).
9. **Переиспользование проверенного workflow/config?** Частично: `_calculate_validation_score` (ranking workflow — но его источник validated nodes в Agent = SPECD, §8.0; deferred S6), `AdaptivePlanner` (preferred params), `Composer` (suggestions из experience). KnowledgeCore pre-flight — **IMPL via S0.5** (advisory metadata на Job).
10. **Покрыто существующими контрактами?** Основной контур — да. Пробелы точечные: G2 (user_confirmed), G4 (usage/limitation как знание), см. §13.

---

## 9. Learning Lifecycle (сквозной)

Как одна новая нода проходит сквозь архитектуру (фактический контур, без нового кода):

```text
/object_info ──► NodeSchemaStore.refresh() (snapshot+diff)        [DISCOVER]
     │
     ├─► CandidateGenerator ──► CapabilityCandidate(INFERENCE,
     │        usage: UsageHypothesis, evidence: SCHEMA/RUNTIME)   [UNDERSTAND]
     │
     ├─► LocalResearchProvider ──► Evidence(DECLARED_PURPOSE/
     │        OBSERVED_SOURCE_STRUCTURE)                          [INSPECT]
     │
     ├─► EvidenceStore.merge ──► Claim SUPPORTED                  [VERIFY: documented/inspected]
     │
     ├─► RuntimeValidator.validate_node ──► OBSERVED_BEHAVIOR +
     │        CONFIRMED (validated_by_execution)                  [VERIFY: self-tested/proven]
     │
     ├─► [пользователь] FeedbackStore.rating                     [VERIFY: user-confirmed — вне claims]
     │
     ├─► ClaimsPersistence (confirmed_claims.json,
     │        validated_nodes.json)                               [REMEMBER: node-level]
     │
     ├─► ExecutionRecord / ExperienceStore (params/workflow/
     │        state/error/corrections)                            [REMEMBER: usage-level]
     │
     └─► _calculate_validation_score → ranking workflow [*SPECD: source empty in production];
             AdaptivePlanner preferred_params;
             Composer experience suggestions                      [REUSE]
```

Экспортируемые точки, где цикл ОБРЫВАЕТСЯ (для нового нода, ещё без manifest/workflow):
- **CANDIDATE_NO_WORKFLOW** — кандидат есть, но нет workflow → «проверено как нода, не как capability».
- **EXPLAIN** — нет выходного контракта представления claims для пользователя.
- **user_confirmed** не участвует в жизненном цикле claims.
- Безопасная граница self-test (какие ноды разрешены к авто-запуску).

---

## 10. Verification / Provenance Model

### Существующий (IMPL)

| Аспект | Механизм |
|---|---|
| Уровень достоверности | `EvidenceTrustLevel`: schema → declared → observed_source → observed (строкий порядок роста) |
| Статус знания | `ClaimStatus`: UNKNOWN → INFERENCE → SUPPORTED → CONFIRMED (upgrade до CONFIRMED только через реальный запуск) |
| Время проверки | `last_verified` (на claim, обновляется при merge) |
| Авторитет источника | `DiscoveryFacts.*_available` (runtime/models/custom_nodes) |
| Проверка результата | `Verifier` (output-contract), `SemanticVerifier` (vision score), `RuntimeValidator` (runtime), temporal/sequence |
| self-test ≠ schema | `RuntimeValidator` + `test_*`: schema есть НЕ доказательство (явное требование в требованиях задачи соблюдено и в дизайне S4) |

### Чего нет (EXT/частично)

- **Числовой confidence** — НЕ добавлять (намеренный отказ, `models.py:32`; дискретный ClaimStatus достаточен).
- **Явные стадии** `discovered→inspected→self_tested→user_confirmed→proven` как value-lifecycle — минимальное расширение: явный `user_confirmed: bool`/`user_rating` на `KnowledgeClaim` (связь с FeedbackStore), либо метка-маппинг остаётся эвристикой. Рекомендация: EXT, небольшой.

---

## 11. Free-First Routing

**Факт:** в коде нет ни одного cost/free/trial/paid-атрибута: `app/` содержит только `free_memory` (VRAM-диагностика ComfyCLIAdapter) и tooltip-тексты. `BackendSpec` имеет `capabilities/priority/disabled/description` — **нет cost-поля**. `Workflow`/`ModelInfo` тоже. Grep по `cost|price|free|paid|trial` → 0 бизнес-совпадений.

**Требование:** различать FREE/TRIAL/PAID/UNKNOWN; PAID не запускается автоматически; free/local/cloud — варианты, не иерархия.

**Оценка текущего:** политика «PAID не автоматически» в текущем виде **невыразима** — нет данных для отличия. При этом структурно требование «варианты, а не иерархия» уже соблюдено (§7). UNKNOWN как честное «не определено» уже является паттерном архитектуры (AD-18) → применим к cost.

**Минимальное расширение (EXT):**
1. Enum `CostTier{FREE, TRIAL, PAID, UNKNOWN}` (+ дефолт `UNKNOWN`, правило «UNKNOWN ≠ FREE», аналогично AD-18).
2. Опциональное поле `cost_tier` на `BackendSpec` (и, при необходимости, на `ModelInfo` / workflow manifest) — декларативно, без изменения ядра.
3. Guard в policy-слое: авто-selection допускает только `FREE` (+ `TRIAL` с явной политикой); `PAID` — только по явному подтверждению пользователя; `UNKNOWN` требует подтверждения либо трактуется как не-авто.
4. Free-first маршрутизация = **дополнительный критерий ranking** (не hard-gate) поверх существующего `_select_manifest`/`BackendCatalog.choose` — не новая иерархия.

**N/A:** billing, marketplace, hosting-платформа, оплата — не требуется (задание §7).

---

## 12. Reuse / Experience Model

**Что уже переиспользуется (IMPL):**
- `_calculate_validation_score(workflow)` → validated nodes влияют на ранжирование workflow в `_select_manifest()` (S4). **Reconciliation 2026-09-13:** в production `Agent._validated_nodes` заполняется только мёртвым hook `_validate_capability_nodes_background` (`agent.py:411`, нет production-вызовов; несовместимая сигнатура `validate_node` без `workflow`) → score всегда 0 (SPECD, §8.0).
- `AdaptivePlanner` → preferred params из history/feedback/experience (soft default, explicit priority).
- `Composer.compose(experience_hint=...)` → suggestions к цепочке (M26.4).
- `KnowledgeCore` pre-flight → candidates/claims/readiness пишутся на Job как advisory metadata — **IMPL via S0.5** (readiness ≠ execution eligibility; execution check — `_select_manifest`/compatibility/S1 cost guard).
- `S2 synthesis` → `KnowledgeCore.synthesize_candidates()`: CANDIDATE_NO_WORKFLOW + template → synthesized manifest/workflow (advisory, без auto-registration) — IMPL via S2.
- `FeedbackStore` → фильтрация low-rated (rating<4) из пула предпочтений; `RetryPolicy` → ask_user (rating≤2).

**Правила корректности (уже в коде, сохранять):** Experience = факт, а не правило; никаких prohibition; ranking только по непрерывным признакам; explicit пользователя перезаписывает preference; `UNKNOWN≠AVAILABLE`.

**EXT для полного reuse цикла:** связка «выбранный workflow/параметры ⇄ появившаяся подтверждённая нода» и «user_confirmed»-обратная связь в решение (см. §13 G2/G4); стоимость/доступность как дополнительный критерий (см. §11).

---

## 13. Current Gaps

Каждый gap: контракт → где → чего не хватает → почему недостаточно → минимальное расширение.

### G1. Нет cost-tier (Free-First невыразим)
- **Контракт:** `BackendSpec` / `ModelInfo` / workflow manifest (provider selector).
- **Где:** `app/registry/backends.py:BackendSpec`; `app/registry/model.py:ModelInfo`.
- **Чего нет:** поля `cost_tier` (FREE/TRIAL/PAID/UNKNOWN) и guard «PAID не авто».
- **Почему недостаточно:** без данных о стоимости нельзя отличить free от paid, следовательно политика §11 нереализуема.
- **Минимальное расширение:** enum `CostTier` + опциональное поле на `BackendSpec` (и опц. `ModelInfo`/manifest); guard в selection policy. Никакой иерархии backend.
- **Статус: РЕШЕНО S1 (FROZEN 2026-09-13).** Реализовано: `app/registry/cost.py`, `BackendSpec.cost_tier` (local→FREE/remote→UNKNOWN), `Workflow.cost_tier` override, filter→ranking. Решено по Q1: cost = backend+workflow, **per-node cost НЕ введён**. Deferred: `ModelInfo.cost_tier` (не потребовался).

### G2. Нет «user_confirmed» как стадии знания
- **Контракт:** `KnowledgeClaim` / `ClaimStatus`.
- **Где:** `app/knowledge/models.py`.
- **Чего нет:** явного поля подтверждения пользователем; `FeedbackStore.rating` не связан с `subject/predicate/object`.
- **Почему недостаточно:** требование «что подтвердил пользователь» (VERIFY-стадия) невыразимо в knowledge-жизненном цикле; «proven» и «user-confirmed» смешаны.
- **Минимальное расширение:** `user_confirmed: bool = False` (или `user_rating: Optional[int]`) на `KnowledgeClaim`; опциональная связка feedback→claim storage. НЕ трогать ClaimStatus-семантику.
- **Статус: EXT (малое).**

### G3. Нет EXPLAIN-контракта
- **Контракт:** отсутствует.
- **Где:** — (KnowledgeResponse отдаёт данные, но нет представления для UI).
- **Чего нет:** структурированного/NL «что это, когда использовать, какие inputs/модели, какие ограничения, что проверено».
- **Почему недостаточно:** стадия EXPLAIN в Tool Learning не имеет выходной точки в UI; данные есть (claims+evidence+NodeDoc).
- **Минимальное расширение:** сервис-слой «explain» поверх `KnowledgeResponse` (template/heuristic; LLM — FUTURE). Не менять ядро query.
- **Статус: EXT; NL-генерация — FUTURE.**

### G4. Нет структурированных «usage pattern» / «limitation» как знания ноды
- **Контракт:** `CapabilityCandidate.usage` (только гипотеза input-mapping); `Experience` (params/state workflow-уровня, не ноды).
- **Где:** `app/knowledge/candidates.py`; `app/engine/experience.py`.
- **Чего нет:** знания вида «нода X работает с параметрами Y в workflow Z», «нода X имеет ограничение/несработала комбинация».
- **Почему недостаточно:** REUSE «сначала проверенное, затем исследование» требует привязать практический опыт к ноде; сейчас опыт закреплён за цепочкой/capability.
- **Минимальное расширение:** дополнительные claim-predicate'ы (`usable_with`, `parameter_preference`, `limitation`) с evidence из ExecutionRecord/Experience; либо расширение `ExperienceHint` привязкой к node_class. Не новая система памяти.
- **Статус: ЧАСТИЧНО — S2 закрыл «workflow для кандидата» (4 template-паттерна, FROZEN-pending-gap); usage/limitation claims = EXT (S7/FUTURE).**

### G5. Нет безопасной границы SELF-TEST
- **Контракт:** `RuntimeValidator`.
- **Где:** `app/knowledge/runtime_validator.py`.
- **Чего нет:** классификации «безопасных для авто-запуска» нод (network/FS/side-effects egress), песочницы.
- **Почему недостаточно:** самотест на живом ComfyUI — это реальный execution; без whitelist риск нежелательного egress/side-effects.
- **Минимальное расширение:** конфигурируемый whitelist node-категорий для авто-self-test + существующий `timeout_seconds`; строгая гарантия sandboxing — FUTURE (иная задача, близко к принципам NG3/безопасности §20 PROJECT_SPEC).
- **Статус: EXT (минимальный) / FUTURE (sandbox).**

### G6. NodeSchema без version/description; provenance без идентичности процесса
- **Контракт:** `NodeSchema`, `KnowledgeEvidence`.
- **Где:** `app/knowledge/node_schema.py`, `app/knowledge/models.py`.
- **Чего нет:** `description` на schema (есть только `tooltip`/`NodeDoc`), `version`; идентификатор «кто/какой процесс получил факт».
- **Почему недостаточно:** для UNDERSTAND/EXPLAIN удобнее объединить schema+NodeDoc; для полной provenance не хватает `evidence.process_id/fetched_by`.
- **Минимальное расширение:** использование `NodeDoc` как источника explain; опционально `version` на `NodeSchema` (но снапшот-diff уже закрывает отслеживание изменений ComfyUI). Provenance-процесс — опционально.
- **Статус: EXT (минимальный, в основном опционально).**

### G7. «Кажущиеся gaps» (НЕ gaps — только недостаток документации)
- Candidate/claims/knowledge закрывают DISCOVER→UNDERSTAND→VERIFY полным контуром; `RuntimeValidator` даёт «self-test ≠ schema»; `_calculate_validation_score` реализует REUSE на workflow-уровне; authority-флаги дают «откуда данные». Эти пункты часто переоткрываются как gaps из-за отсутствия ссылок в docs — зафиксировано в §8/§9. **Reconciliation 2026-09-13:** производственный Agent-источник validated_nodes для `_calculate_validation_score` отсутствует (SPECD, §8.0) — REUSE-механизм существует, но его данные не заполняются.

---

## 14. Minimal Required Extensions

Сводка (только минимальные расширения существующих контрактов; без новых сущностей без необходимости):

| Расширение | Место | Суть | Статус |
|---|---|---|---|
| E1. `CostTier` + поле | `app/registry/backends.py` (BackendSpec), опц. `ModelInfo`/manifest | FREE/TRIAL/PAID/UNKNOWN; guard «PAID не авто» в selection policy | **РЕШЕНО — S1 FROZEN** |
| E2. `user_confirmed` | `app/knowledge/models.py` (KnowledgeClaim) | связь подтверждения пользователя с знанием | EXT (требует AD-решение по Q2) |
| E3. Explain-слой | сервис поверх `KnowledgeCore.query()` | структурированный/NL-вывод для UI (LLM — FUTURE) | EXT / FUTURE (LLM) |
| E4. Usage/limitation claims | `app/knowledge/*` (+ опыт из `app/engine/experience.py`) | predicate `usable_with`/`parameter_preference`/`limitation` с evidence | EXT (консервативно) |
| E5. Self-test boundary | `app/knowledge/runtime_validator.py` | whitelist безопасных node-категорий для авто-запуска | EXT (S6 — после S3) |
| (E6. version/description на NodeSchema) | `app/knowledge/node_schema.py` | опционально; NodeDoc уже даёт description | ОПЦИОНАЛЬНО |

**НЕ требуется (N/A):** новая Memory/Experience система (G4 закрывается расширением claims); новые БД; Temporal; marketplace; billing; hosting; LLM/multi-agent; hardcoded catalog; local-only архитектура (см. §15).

---

## 15. What Must NOT Be Changed

Инварианты архитектуры (PROJECT_SPEC §5, §27; AD-01..AD-44). Ecosystem-First/Tool Learning **не должны** их нарушать:

- LLM не имеет прямого доступа к ComfyUI HTTP, не строит node-graph, никакого произвольного shell/HTTP.
- Agent → ComfyUI только через Operator/Provider; Job/ExecutionPlan фиксируют `workflow_id@version`; никогда `latest`.
- Media-agnostic ядро (AD-03): ни один модуль не ветвится по media-типу; Operator не знает media-тип.
- Capability ≠ Workflow; Provider ≠ Model; Provider ≠ Backend; Asset ≠ File; UNKNOWN ≠ AVAILABLE (AD-18).
- Workflow Registry — не «умный агент»; Provider не выбирает workflow (AD-22).
- Никакого второго execution engine / второй registry / второго ComfyUI runtime (AGENTS.md, Agent UI rules).
- Не добавлять второй Memory/Experience system — расширять существующую.
- **M25/M26/AD-41/AD-44 и post-M26-замороженные контракты** (PlanContext, ExecutionRecord, JobState, ExperienceStore формат персистентности и пр.) — не менять в этом audit.
- «PAID не автоматически» — guard, не запрет; free/local/cloud — варианты.
- Замороженные workflow/приоритеты/пользовательские manifests (`pollinations_image`, priorities) — не менять.

---

## 16. Migration / Evolution Path

Все шаги — отдельные утверждённые milestones (не автоматически):

| Шаг | Содержимое | Статус |
|---|---|---|
| **S0 (current)** | Настоящий audit/design; зафиксировать документ как DRAFT → APPROVED | COMPLETE (документ APPROVED) |
| **S0.5** | Slice 2 Agent pre-flight: `knowledge_core` optional param, `_plan_result_to_query()`, knowledge metadata на Job — advisory, не gate | **FROZEN/VERIFIED (2026-09-13)**, `docs/ECOSYSTEM_FIRST_S0_5_DESIGN.md` |
| **S1** | E1 cost-tier: enum + поля BackendSpec/Workflow + guard (filter→ranking, PAID/UNKNOWN вне auto-selection) | **FROZEN/VERIFIED (2026-09-13)**, `docs/ECOSYSTEM_FIRST_S1_DESIGN.md` |
| **S2** | Template-Based Workflow Synthesis (MODIFIED от «Slice-2/one-node» гипотезы: one-node отвергнут feasibility gate'ом) — Candidate+NodeSchema+Template → synthesized workflow; без auto-registration | **ACCEPTED W/ RUNTIME GAP (2026-09-13)**, `docs/ECOSYSTEM_FIRST_S2_DESIGN.md` |
| **S3** | Ecosystem Facts & Provenance Queries: read-only query слой над существующим `app/knowledge/` + GAP-реестр; provenance = существующие `EvidenceTrustLevel`/`ClaimStatus` (без нового enum); self-test — design-only | Кандидат (audit не начат) |
| **S4 (ex E3)** | Explain-слой поверх S3-запросов (template/heuristic; LLM — FUTURE) | FUTURE |
| **S5 (ex E2/G2)** | `user_confirmed` + связка feedback→claim — **только после отдельного AD-решения по Q2** (риск auto-CONFIRMED) | FUTURE (blocked on AD) |
| **S6 (ex E5/S4-partial)** | RuntimeValidator activation + self-test whitelist (замкнёт `_calculate_validation_score`=0) — требует S3 safety data | FUTURE |
| **S7 (ex E4)** | Usage/limitation claims — после накопления executions (S6) | FUTURE |
| **S8 (дальнее)** | Внешние источники workflow (безопасный импорт), дополнительные Provider/backend, MCP/специализированные операторы | FUTURE |

**Примечание о нумерации:** фактическая нумерация S0.5/S1/S2 закрепилась за pre-flight/cost-tier/synthesis; исходные E-шаги §14 переименованы (explain→S4, user_confirmed→S5 с AD-gate, self-test→S6). Cost живёт на Backend/Workflow (решение S1 по Q1) — **per-node cost не вводится**. Числовой confidence не вводится намеренно (§10).

Каждый шаг = отдельный milestone с DoD на реальном ComfyUI (TEST_PROTOCOL), без mock на финальной валидации. Никакой реализации до approval автора (правило проекта: новые milestones — только после approval).

---

## 17. Open Architectural Questions

1. **Q1 (cost binding).** Где живёт `cost_tier`: `BackendSpec`, `ModelInfo`, workflow manifest, или комбинация? Какое правило победы при конфликте (backend FREE + workflow PAID)? Требует AD.
2. **Q2 (user_confirmed).** Связь `FeedbackRecord.rating` с `KnowledgeClaim`: идентификация по (subject, predicate, object)? Не превратит ли это feedback в «auto-CONFIRMED» (запрещено)? Как отличить подтверждение законченного использования от простой оценки?
3. **Q3 (usage/limitation).** Где агрегировать «рабочие параметры/нерабочие комбинации» ноды: дополнительные claim-predicate'ы с evidence из ExecutionRecord, или расширение `ExperienceHint` привязкой к node_class? Какие метрики (count, success_rate) пороговые?
4. **Q4 (self-test boundary).** Какой whitelist node-категорий допустим к авто-запуску без пользователя? (comfy_extras vs custom; network-ноды — запрет?). Нужен ли вообще авто-запуск без явной команды пользователя «self-test»?
5. **Q5 (explain).** Explain — template/heuristic (сейчас) или LLM (FUTURE)? Какие поля обязательны: purpose, inputs, models, limitations, verified-status?
6. **Q6 (reuse trigger).** Когда кандидат/подтверждённая нода влияет на выбор workflow: только через `validated_nodes` (сейчас) или дополнительные триггеры (user_confirmed/rating)? Как избежать «переобучения» selection?
7. **Q7 (free-first policy).** CostTier — критерий ranking или hard-gate для PAID? Что с TRIAL (лимит запусков)? Как применить к `BackendCatalog.choose` (cost-vs-VRAM-probe приоритет)?

Эти вопросы решаются на этапе architecture decision (CHANGE_PROTOCOL → DECISION_LOG → APPROVED), не в этом документе.

---

## 18. Conclusion

**Ключевой критерий (раздел 9 задания):** может ли существующая архитектура постепенно превратить Agent из исполнителя заранее известных возможностей в Agent, который сам исследует неизвестный инструмент, безопасно проверяет, объясняет, совместно использует, запоминает и переиспользует?

**Ответ: ДА — в основном уже на существующих механизмах.**

- **discover/inspect/understand** — `ComfyClient.discover_custom_node_packages()` + `NodeSchemaStore` + `CandidateGenerator` + `NodeDoc` + `LocalResearchProvider`: реализовано.
- **self-test/verify** — `RuntimeValidator` (реальный запуск, `OBSERVED_BEHAVIOR` → `CONFIRMED`), `EvidenceStore.merge`, `ClaimStatus`, `last_verified`, authority-флаги `DiscoveryFacts`: реализовано; остаётся уточнить безопасную границу self-test (G5).
- **remember/reuse** — `ClaimsPersistence`, `ExperienceStore`, `ExecutionHistory`, `FeedbackStore` (wired), `_calculate_validation_score` → ranking, `AdaptivePlanner`/`Composer` preferences: реализовано.
- **Недостающие звенья — точечные, минимальные:** ~~Agent pre-flight wiring~~ **S0.5 FROZEN**, ~~cost-tier/Free-First~~ **S1 FROZEN**, candidate→workflow bridge **S2 (accepted w/ runtime gap)**; остаётся: user_confirmed в знаниях (G2, требует AD по Q2), explain-контракт (G3), usage/limitation как знание (G4), whitelist self-test + RuntimeValidator activation (G5, S6). Ни одно из них не требует новой архитектуры и тем более переписывания ядра.
- **Не требуется:** новая Memory/Experience система, новая БД, billing, marketplace, hosting, multi-agent, hardcoded catalog, local-only. «PAID не авто» — guard поверх существующего ranking, не новая иерархия.

**Конфликт с M26/post-M26:** отсутствует. Документ — read-only архитектурный аудит в духе уже выполненного пост-M26 аудита; новые шаги только после approval автора.

*Конец документа. Status: DRAFT — ARCHITECTURE / DESIGN AUDIT. Production code не изменялся; commit не выполнялся.*