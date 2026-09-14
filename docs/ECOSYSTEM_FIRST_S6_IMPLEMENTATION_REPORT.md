# ECOSYSTEM-FIRST S6 — Implementation Report

**Milestone:** S6 — Explicit Self-Test Runtime Validation
**Status:** ✅ ACCEPTED / FROZEN
**Date:** 2026-09-14
**Design:** `docs/ECOSYSTEM_FIRST_S6_DESIGN.md` (16 разделов; §5 gate, §6 transport, §7 source of truth)
**Base:** S0.5 FROZEN / S1 FROZEN / S2 ACCEPTED (runtime-gap CLOSED) / M1–M26 FROZEN
**Production entry (единственный):** `Agent.run_self_test(node_class, backend_id=None, base_url=None, provider=None)` (AD-47)

---

## 1. Scope (что вошло в реализацию)

| Файл | Изменение |
|---|---|
| `app/agent.py` | `run_self_test()` + `_self_test_gate()` + helpers (`_self_test_refusal/_role/_backend/_backend_id/_cost_allowed/_resolve_client/_workflow_source/_synthesized/_registry_graph/_needs_input_asset/_claim_status`), константы `SELF_TEST_ALLOWED_ROLES/COST/NEEDS_INPUT_TYPES`. `_calculate_validation_score` — core-derived validated-источник. deprecated shim `_validate_capability_nodes_background` (синхронный, без `threading`). `_load_workflow_graph` + `_workflow_node_types` + `_is_api_format` |
| `app/knowledge/runtime_validator.py` | Transport S6 §6: `queue_prompt`/`get_history` (публичный API ComfyClient) + legacy fallback `queue`/`history` |
| `tests/test_self_test_gate.py` | **NEW** — 25 тестов S6-приёмки |
| `tests/test_runtime_validator.py` | Моки переведены на реальный транспортный API (см. §7 — документированное исключение) |
| `scripts/s6_acceptance_check.py` | **NEW** — acceptance-скрипт на реальных схемах (read-only) |

**Scope OUT (не менялись):** S4/S5/S7 ядро, UI, LLM, media-ветки, storage, framework. `knowledge_core.validate_runtime`, `persistence` (ClaimsPersistence/NodeSchemaStore) — без изменений. Новые enum/storage/строки cost-семантики НЕ вводились.

## 2. Архитектурная привязка

- **Gate (S6 §5):** needs_knowledge → unknown_node → `classify_safety` (FORBIDDEN = жёсткий отказ; REQUIRES_CONFIRMATION) → роль из `query.classify_role` ∈ {head, processor, sink} → S1 cost (FREE/TRIAL) → `workflow_source` (template-синтез > registry api-граф) → `needs_input_asset` (обязательный media/GRAPH вход — S6-минимальный scope) → `no_comfy_client`.
- **Консерватизм (AD-47):** UNKNOWN/неполные данные → отказ. Отказ кэшируется (`_selftest_refusals`) — повтор возвращает тот же отказ без повторной оценки и без исполнения.
- **BLOCK:** отказ НЕ пишет validated/claims (persistence нетронута).
- **Единственный executive-путь:** `knowledge_core.validate_runtime` → `RuntimeValidator` → ComfyUI → CONFIRMED-claim.
- **NG:** в изменённых файлах отсутствуют `threading`, `asyncio`, `async def`; `run_self_test()` встречается только в `app/agent.py`; CLI-инфраструктура НЕ создавалась (запрет автора).
- `_validate_capability_nodes_background` — deprecated-обёртка (синхронный shim для тестовой совместимости), production-вызовов нет.

## 3. Test results

### 3.1 S6-набор (новые + затронутые)

- `tests/test_self_test_gate.py`: 25 passed
  - **Gate-отказы:** needs_knowledge, unknown_node, forbidden, requires_confirmation, not_standalone, cost_not_free, unknown_backend_cost_not_free, no_comfy_client, no_workflow_source, needs_input_asset — 10 случаев.
  - **Повтор/кэш:** `refusal_is_cached_and_repeat_is_empty`, `refusal_requires_no_transport` — повтор без повторной оценки.
  - **BLOCK:** `refusal_blocks_writes` (persistence add_validated_node/add_confirmed_claim не вызываются).
  - **Success-path:** `success_synthesized_and_confirmed`, `validate_node_called_with_two_args`, `failure_path_reports_failure_without_claim`.
  - **Score:** core-derived / legacy fallback / zero-when-not-validated.
  - **Shim:** 2 аргумента, синхронно, без потоков.
  - **Transport:** real-client API success/failure, legacy fallback, отсутствие методов → error.
  - **Single-entry / NG:** `run_self_test` единственный public entry; нет `threading` в S6-исходниках.
- `tests/test_agent_runtime_validation.py`: 8 passed (S4-совместимость shim + trigger + validated-nodes).
- `tests/test_workflow_validation_priority.py`: 7 passed (score/priority/интеграция с core).
- `tests/test_runtime_validator.py`: 16 passed / 1 skipped (E2E-тест ручной, требует живого ComfyUI).
- **Итого S6-набор: 54 passed / 1 skipped.**

### 3.2 Regression-подмножество (S0.5/S1/S2/S3/S4 + S6)

`test_knowledge_s05.py test_cost_tier.py test_s2_synthesis.py test_knowledge_s3_queries.py test_knowledge_s4_claims.py` + S6-набор:
**178 passed / 1 skipped** (6.81s). Без правок в этих тестах — все существующие зелёные остались зелёными.

### 3.3 Полный suite

Полный прогон не выполняется целиком (E2E требуют живой ComfyUI и занимают > timeout). Задокументированный pre-existing failure — §6.

## 4. Runtime evidence (реальные ComfyUI-схемы)

Источник: `app/data/knowledge/node_schemas.json` (1040 реальных схем, снятых с ComfyUI). Прогон: `scripts/s6_acceptance_check.py` (PYTHONPATH=корень репозитория).

```
[schema] store loaded: 1040 schemas; targets present: ['Get Request Node', 'PollinationsImageGen']
[schema] Get Request Node: module='custom_nodes.ComfyUI-HttpRequestNodes' category='RequestNode/Get Request' safety=REQUIRES_CONFIRMATION role=other
[schema] PollinationsImageGen: module='custom_nodes.pollinations-byop' category='Pollinations/Image' safety=REQUIRES_CONFIRMATION role=head
[gate]  Get Request Node: status=refused reasons=['no_workflow_source', 'not_standalone', 'requires_confirmation'] claim_status=None => PASS
[gate]  PollinationsImageGen: status=refused reasons=['requires_confirmation'] claim_status=None => PASS
[noexec/nowrite] queue_prompt=0 get_history=0 writes={'validated': 0, 'claims': 0} validated 3->3 claims 0->0
[realschema-positive] узлов реальных, проходящих gate без отказа: 2 -> ['LoadImage', 'BatchImagesNode']
S6 REAL-SCHEMA ACCEPTANCE: OK
```

### 4.1 Negative evidence (real schemas)

| Node | module (реальная схема) | класс. | Отказ | Интерпретация |
|---|---|---|---|---|
| `Get Request Node` | `custom_nodes.ComfyUI-HttpRequestNodes` | REQUIRES_CONFIRMATION; role=other | `requires_confirmation` + `not_standalone` + `no_workflow_source` | Network-узел; верно отказан (сеть не может исполняться в self-test). Избыток reasons не мешает — отказ конвективный |
| `PollinationsImageGen` | `custom_nodes.pollinations-byop` | REQUIRES_CONFIRMATION; role=head | `requires_confirmation` (только) | Чистый подтверждённый требует_подтверждения — роль head, но внешний генератор |

- **Исполнение:** `queue_prompt=0`, `get_history=0` — транспорt вообще не вызывался при отказе.
- **Записи:** persistence `add_validated_node`/`add_confirmed_claim` — 0 вызовов; `validated_nodes.json` 3→3, claims 0→0 (состояние неизменно).
- **Кэш-повтор:** повторный `run_self_test` вернул те же reasons и `claim_status=None`.

### 4.2 Positive evidence (исключая реальное исполнение)

- **Unit/sample (не реальная схема):** синтезированный образец ноды с обязательным `prompt` (STRING), выходом IMAGE, ALLOWED, роль head, FREE backend → SUCCESS + CONFIRMED claim (gate/исполнительный путь/claim proven офлайн, `test_self_test_gate.py::TestSelfTestSuccessPath`).
- **Real schemas:** из 1040 реальных схем gate без отказа проходят только 2: `LoadImage` и `BatchImagesNode` (оба — head-ноды; LoadImage = обязательный вход STRING-путь → не `needs_input_asset`, т.к. тип не media/GRAPH). Полное позитивное реально-исполняемое доказательство требует живой ComfyUI + файла-входа — покрыто существующим реальным E2E-тестом (`TestRuntimeValidatorE2E`, skip без живого ComfyUI).
- **Честный gap (без обходов):** реальная позитивная ветка на живом ComfyUI не была прогоняема в данной сессии (ComfyUI не запущен; пользовательская очередь останавливает headless-исполнение вне интерактива). Зафиксирован как known-limitation, НЕ как дефект S6; инструмент готов (`scripts/s6_acceptance_check.py` → после старта ComfyUI прогнать 2 позитивных ноды с валидным входным файлом).

## 5. Positive / negative evidence (сводка)

**Положительные:**
1. Единственный entry-point без скрытых ветвлений; gate детерминирован (все предикаты из registry-модели).
2. Отказ кэшируется; повтор — без повторной оценки и без исполнения.
3. BLOCK-инвариант: отказ не создаёт validated-записи и claims (подтверждено и юнит-тестом, и на реальных схемах).
4. Transport использует реальный публичный API ComfyClient (`queue_prompt`/`get_history`), legacy fallback сохранён.
5. `_calculate_validation_score` стал core-derived (валидные ноды из `knowledge_core`) с legacy fallback.
6. No-threading / no-async в S6-коде; `run_self_test` — единственное вхождение имени во всех `.py`.
7. Все существующие зелёные тесты (S0.5/S1/S2/S3/S4 + regression) остались зелёными, за исключением задокументированного обновления моков в `test_runtime_validator.py` (см. §7.1).

**Отрицательные (чего НЕ появилось):**
1. Нет энфорсмента "background validation" — единственный путь исполнения явный, user-initiated.
2. Нет параллелизма/потоков в S6-пути.
3. Нет новых enum (провайдер/модель/стоимость), новых storage, новых framework.
4. Нет CLI-инфраструктуры (запрет автора).
5. Нет UI/LLM/media-веток; ядро media-agnostic не тронуто.

## 6. Known pre-existing failures (не из-за S6)

- `tests/test_m11_verification.py` — **collection error**:
  `app.agent.AgentError: нет workflow с подтверждённой совместимостью`
  (модульный уровень строит Agent и требует рабочий capability с AVAILABLE-совместимостью; в текущей среде кандидатов нет).
  Подтверждено на чистом HEAD: работа через `git worktree add … HEAD` (commit `89e230a` до изменений S6) даёт тот же 1 collection error. S6-commit НЕ трогает `_select_manifest`/планирование.
- Реальные E2E-тесты (известные skip, требуют запущенного ComfyUI): `TestRuntimeValidatorE2E`, M4, S2 e2e и т.п.

## 7. Deviations (документированные исключения)

### 7.1 «Green tests без правок» (design §243-248, п.3)
Исключение ровно одно и **санкционировано планом**: `tests/test_runtime_validator.py` — моки использовали НЕсуществующий транспортный API (`client.queue()`, `client.history()`). Это и был транспортный баг S6 §6: протестированный контракт не соответствовал реальному `ComfyClient`. Моки приведены к реальному API (`queue_prompt`/`get_history`). Все остальные green-tests не редактировались.

### 7.2 CLI-обёртка
Не создавалась; production-entry — только метод `Agent.run_self_test()` (по явному решению автора).

### 7.3 Реальные позитивные схемы (исполнение)
`LoadImage`/`BatchImagesNode` проходят gate, но их реальное исполнение требует живого ComfyUI и входного файла — вынесено за scope (E2E-тест с skip). Инструмент для допрогона готов.

## 8. Acceptance checklist (design §243-248)

1. ✅ Все 16 разделов design закрыты; автор дал approval на реализацию; реализация после approval.
2. ✅ Единственный production-entry + gate + source + integration — без скрытых ветвлений; без новых storage/enum/cost-семантики.
3. ⚠️ Green-существующие остались зелёными, кроме задокументированного обновления моков транспортного API (п.7.1 — транспортный баг S6).
4. ✅ Предреализационный порог соблюдён: design был утверждён до написания production-кода.

Дополнительно (из постановки S6 §16):
- ✅ Отказ-повтор = пусто/тот же отказ без повторной оценки.
- ✅ FORBIDDEN / REQUIRES_CONFIRMATION / не-regular роль → отказ.
- ✅ Роль из registry-модели (`query.classify_role`).
- ✅ BLOCK-незапись при отказе.
- ✅ Транспорт на реальном ComfyClient API + fallback.
- ✅ Один вход `run_self_test` объявлен в `.py`-файлах (NG-grep).
- ✅ Только internal (нет public server/flags/CLI).
- ✅ TH только в executor — в S6-коде потоков нет.
- ✅ Реальные схемы: `requires_confirmation` подтверждён для обоих целевых узлов без новой инфраструктуры.

## 9. Commands

```powershell
$env:PYTHONPATH="C:\cd\ComfyUI_AMD\agent"
python -X utf8 -m pytest tests/test_self_test_gate.py tests/test_agent_runtime_validation.py tests/test_workflow_validation_priority.py tests/test_runtime_validator.py -q
# → 54 passed, 1 skipped

python -X utf8 -m pytest tests/test_self_test_gate.py tests/test_agent_runtime_validation.py tests/test_workflow_validation_priority.py tests/test_runtime_validator.py tests/test_knowledge_s05.py tests/test_cost_tier.py tests/test_s2_synthesis.py tests/test_knowledge_s3_queries.py tests/test_knowledge_s4_claims.py -q
# → 178 passed, 1 skipped

python -X utf8 scripts/s6_acceptance_check.py   # реальные схемы, read-only
git diff --check                                 # чист (только LF/CRLF warnings)
```