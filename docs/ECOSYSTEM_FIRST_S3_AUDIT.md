# S3 Forensic Audit — Ecosystem Facts & Provenance

> **Статус:** READ-ONLY AUDIT (нет production-кода).
> **Дата:** 2026-09-13.
> **Base:** S0.5/S1 FROZEN, S2 ACCEPTED WITH RUNTIME GAP, M1–M26 FROZEN.
> **Метод:** live `/object_info` (ComfyUI Desktop 0.34.5 @ 127.0.0.1:8188), persisted stores, инспекция кода.
> **Probe-скрипт:** `scripts/s3_audit_probe.py` (воспроизводимо).

---

## 1. Фактическое состояние экосистемы (live, 2026-09-13)

| Метрика | Значение |
|---|---|
| Node classes в live `/object_info` | **1040** |
| Built-in (`nodes`/`comfy_extras`) | 639 |
| Custom packages | **53** (≈401 классов) |
| Persisted snapshot (`node_schemas.json`) | 1040, **diff с live = 0** (актуален) |
| NodeDoc записей | 63 |
| `validated_nodes.json` | 6 записей (из них **3 — тестовый мусор**) |
| `confirmed_claims.json` | 2 записи |

### Категории custom-пакетов (по природе side-effects)

| Класс пакетов | Примеры | Nature | Safety (classify_safety) |
|---|---|---|---|
| `comfy_api_nodes.nodes_*` (~30 пакетов) | Kling, Recraft, ByteDance, Tripo, Wan, Luma, BFL, Vidu, OpenAI, Sora, Gemini, ElevenLabs, Runway, MiniMax, Veo3 | **внешние платные API** (billing через Comfy.org key) | REQUIRES_CONFIRMATION |
| Прочие custom | ComfyUI-Agnes-AI, pollinations-byop, HttpRequestNodes, reactor, ollamagemini, QwenVL | внешние/локальные гибриды | REQUIRES_CONFIRMATION |
| Инфраструктурные | websocket_image_save | локальный websocket | REQUIRES_CONFIRMATION (module не nodes*) |

**Agnes-AI (3 ноды: AgnesImage/AgnesText/AgnesVideo):** присутствуют live, схемы подтверждены (mode-enum с 'Text To Video', выходы VIDEO/IMAGE/AUDIO). **Что НЕ доказано:** тарификация сервиса, фактическая работоспособность, формат VIDEO-выхода для CreateVideo-цепочки → INFERENCE-level, REQUIRES_CONFIRMATION. Никаких утверждений «работает/бесплатно».

---

## 2. Существующие механизмы (переиспользовать, НЕ дублировать)

| Потребность S3 | Уже существует | Статус |
|---|---|---|
| node class/schema/inputs/outputs | `NodeSchema`+`FieldSpec`+`NodeSchemaStore`(snapshot/diff) | IMPL, актуален |
| package → classes | `discover_custom_node_packages()` (live, per-call) + `python_module` в каждой схеме | IMPL; **не persist-ится** как отдельная карта |
| документация ноды | `NodeDocStore` + `NodeDocParser` (63 md) | IMPL |
| semantic evidence (README/source/metadata) | `LocalResearchProvider` + `EvidenceStore` | IMPL |
| claims lifecycle | `ClaimStatus` UNKNOWN→INFERENCE→SUPPORTED→CONFIRMED | IMPL |
| provenance | `EvidenceTrustLevel{SCHEMA,DECLARED_PURPOSE,OBSERVED_SOURCE_STRUCTURE,OBSERVED_BEHAVIOR}` + `EvidenceSource{RUNTIME,LOCAL_SOURCE,PROJECT_METADATA,EXECUTION}` + `source`/`timestamp`/`last_verified` | IMPL — **полный нужный словарь, новый enum НЕ нужен** |
| gaps | `KnowledgeGap`/`GapType`(7)/`GapNature`(3) — in-memory в query-ответе | IMPL; **нет персистентного GAP-реестра** |
| candidate → capability | `CandidateGenerator` (детерминированный) | IMPL |
| candidate → workflow | S2 `app/synthesis/` (4 шаблона) | IMPL |
| readiness | `KnowledgeCore.query()` → Readiness | IMPL (advisory, S0.5) |
| queries find_node/nodes_by_io/explain | **НЕТ** — только query по capability | **GAP (ядро S3)** |
| classification head/processor/fragment | **НЕТ** (есть эвристика в S2 selector) | **GAP (деривация — легко)** |
| USER_CONFIRMED | **НЕТ** | **GAP — требует AD (Q2), вне S3** |

## 3. Representative nodes — discovered → understood → provenance

| Node | Discovery | Inputs (required) | Outputs | Класс | Safety | Что доказано | Что НЕ доказано |
|---|---|---|---|---|---|---|---|
| ImageInvert | snapshot+live | image:IMAGE | IMAGE | processor | ALLOWED | схема из /object_info; синтез S2 принят сервером | полный файл-output proof (queue) |
| CheckpointLoaderSimple | snapshot+live | ckpt_name:ENUM(3 варианта из live) | MODEL,CLIP,VAE | loader/head | ALLOWED | схема | — (используется в замороженных workflow, косвенно доказан) |
| PollinationsImageGen | snapshot+live | prompt:STRING, model:ENUM, w/h, seed | IMAGE,STRING | head (генератор) | REQUIRES_CONFIRMATION | схема; validated_node=True (истор. запись) | тариф/лимиты BYOP |
| KSampler | snapshot+live | MODEL,CONDITIONING×2,LATENT,... | LATENT | **fragment** (неисполним сам) | ALLOWED | схема | — (не candidate: нет media-выхода) |
| AgnesVideo | snapshot+live | mode:ENUM+6 | VIDEO,IMAGE×2,AUDIO | head (T2V mode) | REQUIRES_CONFIRMATION | схема+README-доки (NodeDoc) | работоспособность, тариф, VIDEO→SaveVideo совместимость |

**Head/processor/fragment критерий (деривируется из существующих данных):**
- `head/loader`: required ⊆ {STRING,INT,FLOAT,ENUM,BOOLEAN} (или пусто), outputs включают media (IMAGE/VIDEO/AUDIO) или model-типы;
- `processor`: required включает IMAGE/AUDIO/VIDEO, output media;
- `fragment`: required включает MODEL/LATENT/CONDITIONING/CLIP — неисполним без upstream.
Это чистая функция от NodeSchema — без новой онтологии.

---

## 4. Найденные проблемы (входят в S3 scope или фиксируются как долг)

### P1. Тестовое загрязнение persistence (найдено live)
`app/data/knowledge/validated_nodes.json` содержит `TestNode/FailNode/RestartTestNode` — тесты пишут в **production-дир** (`ClaimsPersistence(data_dir="app/data/knowledge")` дефолт). Реальные записи: `PollinationsImageGen=True`, `Get Request Node=False`.
→ S3: изолировать тестовые data_dir (fixture tmp_path), clean-up запись в отчёте. **Не молча чистить данные** — показать список на удаление автору.

### P2. Snapshot без package-level индекса
`node_schemas.json` — плоский `{class: schema}`. Package→classes выводится из `python_module`, но пересчитывается и не аннотируется (сколько классов, safety-профиль пакета).
→ S3: derived-запрос (кэш необязателен), без новой сущности.

### P3. Нет персистентного GAP-реестра
Gap'ы живут только в ответах `query()`. Нет ответа «что всего не знает агент» одним вызовом.
→ S3: `KnowledgeCore.gap_report()` — агрегация по текущим candidates/schemas (read-only derived).

### P4. Нет find/explain query API
→ Ядро S3: тонкие методы на `KnowledgeCore` (см. §5 design preview). Никакого нового хранилища.

### P5. Cost-моделирование node'ов (зафиксированное напряжение)
`comfy_api_nodes.*` — по факту платные сервисы; но AD-46 сознательно **не ввёл per-node cost** (cost = backend+workflow). S2 safety (REQUIRES_CONFIRMATION) сейчас — единственная линия защиты для таких нод в synthesis.
→ S3: задокулировать в GAP-реестре как **known modeling gap**; НЕ вводить per-node CostTier без AD. Для synthesis-политики: нода из `comfy_api_nodes.*` → НЕ ALLOWED (уже так).

### P6. Старый S2 runtime gap — открыт
`815e9fc2` (ImageInvert proof) в очереди за пользовательскими KSampler. Перезапуск `scripts/s2_proof.py`.

---

## 5. S3 Design preview (для отдельного approval)

Scope: **read-only query/aggregation слой** поверх существующего + hygiene P1.

```python
# Новые методы на KnowledgeCore (все — чистые производные, без storage-изменений):
def find_node(class_type) -> Optional[NodeFacts]         # schema+docs+claims+evidence+classification+safety
def find_package(package_id) -> PackageFacts              # classes[], provenance per class
def nodes_by_io(input_types, output_type) -> list         # фильтры по схемам
def nodes_for_capability(capability) -> list              # candidates ∪ built-in
def explain_node(class_type) -> NodeExplanation           # template/heuristic: что, входы/выходы,
                                                          #   что доказано (ClaimStatus max), чего нет (gaps),
                                                          #   safety, classification. БЕЗ LLM, БЕЗ выдумывания semantics.
def gap_report() -> list[KnowledgeGap]                    # агрегированный реестр неизвестного
```

`NodeFacts/NodeExplanation` — **плоские dataclass'ы-представления** над существующими объектами (не новые сущности хранения). Provenance = существующие `EvidenceTrustLevel`/`ClaimStatus` (никакого нового enum; USER_CONFIRMED отсутствует и остаётся отдельным AD-вопросом). Classification — деривация из required-input типов. Safety — существующий `classify_safety` + S2 provenance.

Non-goals (жёсткие): LLM; graph solver; per-node CostTier; USER_CONFIRMED; изменения `ExecutionRecord`/`JobState`/`ExperienceStore`; изменения execution eligibility; background discovery; self-test **реализация** (только design-контракт в документации: политика = ALLOWED ∧ FREE-backend ∧ явная команда пользователя → кандидат self-test; всё остальное — confirmation/GAP).

Tests (будущие, matrix): find/find_package/nodes_by_io/explain (с доказанным и недоказанным), gap_report, unknown→GAP (не positive), P1 изоляция тестовых data_dir, S1/S2 non-regression, no-side-effect (query не трогает ComfyUI), readiness неизменен, registry неизменен.

Объём оценки: ~150 строк query-слой + ~200 строк тестов, без правок `app/engine`, `app/registry`, `app/synthesis`, `app/agent.py`.

---

## 6. Вывод аудита

Экосистема **фактически известна на уровне схемы** (1040/1040 snapshot, provenance-словарь полный, docs на 63 ноды). Чего не хватает — **вопросительного слоя** (find/explain/gap-реестр) и **гигиены** (P1). Ни одна из потребностей не требует новой архитектуры; все пять — деривация из существующих структур. S3 в узкой формулировке (query-слой + GAP-реестр + P1) **архитектурно обоснован и минимален**.

**S3 AUDIT STATUS: COMPLETE — design требует отдельного approval.**

**STOP / WAIT.**
