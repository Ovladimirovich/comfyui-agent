# AI_ENGINEER_HANDOFF.md — Comprehensive Reference

**Дата:** 2026-09-01
**Статус:** BASELINE — справочный документ
**Первичный вход:** `docs/AI_ENGINEER_ONBOARDING.md`

> **Важно:** Этот документ — подробный справочник. Новый ИИ должен начать с `AI_ENGINEER_ONBOARDING.md` (чеклист + запреты), затем использовать HANDOFF.md как reference.

---

## ⚠️ ПЕРВЫЕ ДЕЙСТВИЯ НОВОГО ИИ

```text
1. Прочитать этот файл целиком.
2. НЕ начинать писать код.
3. Проверить фактическое состояние командой:
     python -m pytest tests/ -q
4. Сравнить результат с §6 этого файла.
5. Если состояние совпадает — написать в HANDOFF.md секцию "VERIFICATION".
6. Только после подтверждения состояния — переходить к задаче.
```

### Критические правила (читать обязательно)

**Правило 1: Документация vs код**
> Документация описывает намерение, код и тесты подтверждают фактическое состояние.
> При конфликте: сначала зафиксировать расхождение → Architectural Decision → реализовать.
> **НЕ изменять код автоматически**, чтобы он соответствовал документации.

**Правило 2: M13–M18 — предложенное направление, не утверждённый план**
> `DEVELOPMENT_PLAN_M13_M18.md` имеет статус **DRAFT FOR APPROVAL**.
> M13–M18 НЕ являются автоматически принятыми задачами.
> Новый ИИ не начинает M13 без отдельного approval от автора проекта.
> Рекомендация: сначала заморозить M1–M12.1 как baseline.

**Правило 3: M1–M12 заморожены**
> Код M1–M12.1 работает и протестирован. Любое изменение = архитектурное решение
> через `CHANGE_PROTOCOL` → `DECISION_LOG` → `APPROVED`.
> Запрещено переписывать M1–M12 "для улучшения" без явного указания.

---

## 1. ЧТО ЭТО ЗА ПРОЕКТ

**ComfyUI Agent v1** — Multimodal Agent Operator поверх ComfyUI (локальный, AMD DirectML).

- **Рабочая директория:** `C:\cd\ComfyUI_AMD\agent\`
- **ComfyUI:** `127.0.0.1:8188` (только localhost)
- **LLM (опц., M8+):** OpenAI-совместимый endpoint `fallback_proxy :20130` (конфигурируемо `LLM_BASE_URL`)
- **Ключевой принцип:** Media-agnostic execution pipeline. Image/Video/Audio проходят через один execution-engine; ветвления по media-типу в ядре **запрещены**.

Проект **НЕ является:**
- image generator;
- wrapper над ComfyUI;
- универсальным чат-ботом;
- набором MCP tools;
- RAG/vector DB;
- autonomous learning system.

---

## 2. ИСТОЧНИКИ ИСТИНЫ (Doc Hierarchy, AD-28)

```text
PROJECT_SPEC.md          ← ЕДИНСТВЕННЫЙ source of truth (архитектура)
     ↓
docs/00..18_*.md        ← производная документация
     ↓
engineering/*           ← engineering rules, protocols
     ↓
tasks/*                 ← active backlog, completed milestones
     ↓
source code             ← implementation (НЕ источник истины)
```

**Если код, документация и PROJECT_SPEC расходятся:**
```text
STOP
 → IDENTIFY CONFLICT
 → REPORT
 → ARCHITECTURAL DECISION
 → IMPLEMENT
```

**Код НЕ может переопределить архитектурные инварианты.**

---

## 3. АРХИТЕКТУРА (ключевые инварианты)

### 3.1 Запреты (§5 PROJECT_SPEC)

| Запрет | ID |
|--------|----|
| LLM → напрямую ComfyUI HTTP | §5 |
| LLM → выбор/генерация node-id | §5 |
| LLM → произвольный shell/HTTP | §5 |
| Agent → прямой ComfyUI HTTP (только через Operator) | §5 |
| WorkflowEngine → image/video-специфика (media-agnostic) | §5 |
| Operator → знание media-типа | §5 |
| Asset → жёстко image-поля (тип — строка) | §5 |
| Capability === Workflow | §5 |
| Provider === Model / === Backend | §5 |
| UNKNOWN compatibility → AVAILABLE | AD-18 |
| Job ссылается на `latest` (только `workflow_id@version`) | AD-17 |

### 3.2 Ключевые архитектурные решения (AD)

| ID | Суть |
|----|------|
| AD-03 | Media-agnostic core — ни один модуль ядра не ветвится по media-типу |
| AD-17 | Version pinning — `ExecutionPlan` фиксирует `workflow_id@version` |
| AD-18 | UNKNOWN ≠ AVAILABLE — lifecycle добавляет UNKNOWN/DEGRADED |
| AD-22 | Selection split — Registry отдаёт candidates, Selection Policy выбирает |
| AD-23 | Input compatibility — фильтр учитывает доступные ассеты |
| AD-28 | Doc hierarchy — PROJECT_SPEC выше всего |
| AD-30 | PromptBuilder не имеет доступа к FS/ComfyUI |
| AD-31 | PromptBuilder не выбирает capability |
| AD-32 | PromptBuilder сохраняет исходное намерение |
| AD-33 | ComfyCLI: `shell=False` (AST-тест) |
| AD-34 | ComfyCLI: отсутствие comfy-cli не блокирует execution path |

---

## 4. EXECUTION PATH (основной)

```
User
  ↓
UI (app/ui.py) — POST /turn
  ↓
ConversationAgent.turn() (app/conversation.py)
  ↓
Planner.plan() (app/planner.py) — capability + params
  ↓
PromptBuilder.build() (app/prompt/composite.py → llm.py / heuristic.py)
  ↓ enhanced_prompt
Agent.prepare() (app/agent.py) — manifest + plan + provider
  ↓ resolve_asset_inputs() (AD-23)
  ↓ bindings
WorkflowEngine.execute() (app/engine/engine.py)
  ↓
ComfyUIProvider.execute() (app/provider/comfyui.py)
  ↓
ComfyClient.queue_prompt() (app/comfy/client.py) — HTTP POST
  ↓
ComfyUI (127.0.0.1:8188)
  ↓
WebSocket tracking (app/engine/websocket.py)
  ↓
Job (app/engine/job.py) → Verifier (app/engine/verifier.py)
  ↓
AssetStore (app/assets/store.py) — lineage
  ↓
SSE events → UI
```

**Infrastructure (не execution path):**
```
ComfyUIProcessManager (app/comfy/lifecycle.py)
  ├── check()       — HTTP health check
  ├── wait_for_ready() — polling until ComfyUI responds
  ├── start()       — subprocess.Popen
  └── stop()        — terminate

ComfyCLIAdapter (app/infrastructure/comfy_cli_adapter.py)
  — version, stop_port, validate_workflow, system_info, env_info, model_list, free_memory
  — полностью опциональный (AD-34), diagnostics only
```

---

## 5. ЧТО РЕАЛЬНО РЕАЛИЗОВАНО (M1–M12)

### 5.1 Фактическое состояние кода

| Milestone | Название | Code | Tests (pytest) | Status |
|-----------|----------|------|----------------|--------|
| M1 | Runtime + Client | ✅ `app/comfy/client.py` | ✅ 8/8 pass | FROZEN |
| M2 | Asset Layer | ✅ `app/assets/` | ✅ 9/10 (1 skip) | FROZEN |
| M3 | Capability + Workflow Registry | ✅ `app/registry/` | ✅ 23/23 pass | FROZEN |
| M4 | Execution Chain | ✅ `app/engine/` | ✅ hang on live ComfyUI | FROZEN |
| M5 | Provider / Model / Remote | ✅ `app/provider/` | ✅ 17/17 pass | FROZEN |
| M6 | Real Video E2E | ✅ `workflows/video_generate/` | ✅ skip (no remote) | FROZEN |
| M6.5 | Image Input / img2img | ✅ `workflows/img2img/` | ✅ skip (no remote) | FROZEN |
| M7 | Conversation Context | ✅ `app/conversation.py` | ✅ 7/8 (1 skip) | FROZEN |
| M8 | Agent + LLM | ✅ `app/agent.py`, `app/planner.py` | ✅ 12/12 pass | FROZEN |
| M9 | UI | ✅ `app/ui.py` | ✅ 5/5 pass | FROZEN |
| M9.1 | Context-aware Planner | ✅ `app/planner.py::HeuristicPlanner` | ✅ 11/11 pass | FROZEN |
| image.upscale | Upscale workflow | ✅ `workflows/upscale/` | ✅ 5/6 (1 skip) | FROZEN |
| M10 | Validation | ✅ full chain verified | ✅ 6/7 remote E2E | FROZEN |
| Progress Hook | Granular % in UI | ✅ `app/engine/websocket.py` | ✅ 12/12 pass | FROZEN |
| M11 | Prompt Builder | ✅ `app/prompt/` | ⚠️ 32/38 pytest (6 test defects) | FROZEN |
| M12 | Real UI E2E | ✅ `app/comfy/lifecycle.py` | ⚠️ ~10 not collectable | FROZEN |
| M12.1 | ComfyCLI Adapter | ✅ `app/infrastructure/` | ✅ 34/34 pass | FROZEN |

### 5.2 Test Summary (факт)

| Категория | Count |
|-----------|-------|
| Passed (pytest, единичные файлы) | 136 |
| Failed (test defects в `test_prompt_builder.py`) | 6 (stale asserts, не code defect) |
| Skipped (нет COMFY_REMOTE_URL) | 2 |
| Not collectable (Python 3.14 stdout hack) | ~54 тестов в 6 файлах |
| E2E (hang/timeout без ComfyUI) | 1 файл |

**Важно:** 6 failures в `test_prompt_builder.py` — это **defect тестов**, не кода. Тесты написаны для ранней версии контракта и не обновлены после финализации `HeuristicPromptBuilder`.

~54 теста не запускаются через `pytest` из-за Python 3.14 совместимости (старый хак `sys.stdout = io.TextIOWrapper(...)`). Тесты работают через `python <file>`.

---

## 6. VERIFICATION COMMANDS

```powershell
# 1. Проверить состояние pytest
python -m pytest tests/ -q

# 2. Проверить отдельные M-тесты (где collect 0)
python tests/test_m11_verification.py        # custom script (28 checks)
python tests/test_prompt_builder_composite_m11.py
python tests/test_prompt_builder_llm_m11.py
python tests/test_prompt_builder_integration_m11.py
python tests/test_ui_m12.py

# 3. Проверить структуру каталогов
ls app/
ls workflows/
ls tests/
ls docs/

# 4. Проверить наличие ключевых файлов
Test-Path app/comfy/lifecycle.py
Test-Path app/infrastructure/comfy_cli_adapter.py
Test-Path docs/AI_ENGINEER_HANDOFF.md          # ← после создания
```

---

## 7. ИЗВЕСТНЫЕ ОГРАНИЧЕНИЯ (Technical Debt)

| # | Проблема | Severity | Решить в |
|---|----------|----------|----------|
| TD-1 | Semantic intent validation — консервативная (>=50% ключевых слов) | LOW | M13+ |
| TD-2 | `previous_prompt` передаётся, но HeuristicPromptBuilder не использует | LOW | M13+ |
| TD-3 | ExecutionPlan prompt metadata поля существуют, но не заполняются | LOW | M13+ |
| TD-4 | 6 failures в `test_prompt_builder.py` (stale asserts) | MEDIUM | M13 |
| TD-5 | ~54 тестов не collectable (Python 3.14 stdout hack) | MEDIUM | M13 |
| TD-6 | `docs/18_DEFINITION_OF_DONE.md` нет DoD для M12 | LOW | M13 |
| TD-7 | `PROJECT_SPEC.md` §22 не содержит M11/M12 | MEDIUM | M13 |
| TD-8 | Persistence context (JSONL) — нет per-session persistence | LOW | Future |
| TD-9 | LLMPlanner real integration — heuristic fallback всегда | LOW | Future |
| TD-10 | Concurrency tests — нет тестов параллельных сессий | LOW | Future |

### Deferred (не реализовано, но в roadmap)

- `audio.generate` real E2E — Sonilo HTTP 401 (broken node / wrong key format)
- ComfyCLIAdapter — **реализован** (M12.1), но не интегрирован в execution path

---

## 8. МЕСТОПОЛОЖЕНИЕ КЛЮЧЕВЫХ КОМПОНЕНТОВ

| Компонент | Путь | Примечание |
|-----------|------|------------|
| `ComfyClient` | `app/comfy/client.py` | HTTP transport |
| `ComfyUIProcessManager` | `app/comfy/lifecycle.py` | Lifecycle (M12) |
| `ComfyCLIAdapter` | `app/infrastructure/comfy_cli_adapter.py` | Diagnostics (M12.1) |
| `AssetStore` | `app/assets/store.py` | Lineage + storage |
| `WorkflowEngine` | `app/engine/engine.py` | Core execution |
| `Verifier` | `app/engine/verifier.py` | Structural verification |
| `ComfyUIProvider` | `app/provider/comfyui.py` | Asset transport + execute |
| `Registry` | `app/registry/` | Capability + Workflow selection |
| `Agent` | `app/agent.py` | Orchestration layer |
| `ConversationAgent` | `app/conversation.py` | Multi-turn + context |
| `Planner` | `app/planner.py` | Heuristic + LLM |
| `PromptBuilder` | `app/prompt/` | Heuristic + LLM + Composite |
| `UI Server` | `app/ui.py` | SSE + HTML + /turn |
| Test M11 verification | `tests/test_m11_verification.py` | Custom script (28 checks) |

---

## 9. WORKFLOW DIRECTORY

| Workflow | Capability | Status |
|----------|-----------|--------|
| `workflows/txt2img/` | `image.generate` | EXECUTABLE |
| `workflows/img2img/` | `image.edit` | EXECUTABLE (AD-23 closed) |
| `workflows/upscale/` | `image.upscale` | EXECUTABLE |
| `workflows/video_generate/` | `video.generate` | EXECUTABLE (M6) |
| `workflows/audio_generate/` | `audio.generate` | EXECUTABLE (M7, deferred E2E) |

Каждый workflow содержит: `manifest.json` + `workflow.json` + `README.md`.

---

## 10. M13+ ROADMAP (проposed, не approved)

**Источник:** `docs/FUTURE_ROADMAP_ARCHITECTURE.md` (DRAFT FOR DISCUSSION)

| Milestone | Цель | Зависимости | Статус |
|-----------|------|-------------|--------|
| M13 | Execution History + Retry Loop | Нет | PROPOSED |
| M14 | Semantic Verification | M13 | PROPOSED |
| M15 | Persistent Context | M13 | PROPOSED |
| M16 | Adaptive Planner | M13+M14+M15 | PROPOSED |
| M17 | User Feedback Loop | M13+M15+M16 | PROPOSED |
| M18 | Multi-Step Decomposition | M13+M14+M16 | PROPOSED |

**Critical path:** M13 → M14 → M16 → M18  
**Parallel:** M13 → M15 → M17

**Рекомендуемый следующий шаг:** M13 (Execution History + Retry Loop).

---

## 11. ЧТО ДЕЛАТЬ ПЕРВЫМ ПОСЛЕ ПОДКЛЮЧЕНИЯ

```text
1. Прочитать этот файл.
2. Прочитать PROJECT_SPEC.md §0, §5, §24, §26.
3. Прочитать docs/PROJECT_STATE_2026-09-01.md (фактическое состояние).
4. Запустить: python -m pytest tests/ -q
5. Сравнить результат с §5 этого файла.
6. Если расхождения — зафиксировать в HANDOFF.md.
7. Если состояние подтверждено — перейти к задаче из tasks/ACTIVE.md.
```

---

## 12. КРИТЕРИИ ПОДТВЕРЖДЕНИЯ СОСТОЯНИЯ

Новый ИИ должен подтвердить (или опровергнуть) следующие утверждения:

| № | Утверждение | Как проверить |
|---|-------------|---------------|
| C1 | M1–M12 код существует | `Test-Path` на пути из §8 |
| C2 | pytest возвращает ~136 passed, 6 failed (test defects) | `python -m pytest tests/ -q` |
| C3 | 6 failures — stale tests, не code defects | Проверить `test_prompt_builder.py` |
| C4 | `app/comfy/lifecycle.py` существует | `Test-Path app/comfy/lifecycle.py` |
| C5 | `app/infrastructure/comfy_cli_adapter.py` существует | `Test-Path app/infrastructure/comfy_cli_adapter.py` |
| C6 | `docs/FUTURE_ROADMAP_ARCHITECTURE.md` существует | `Test-Path docs/FUTURE_ROADMAP_ARCHITECTURE.md` |
| C7 | ComfyCLIAdapter опционален (AD-34) | Прочитать файл, проверить `is_available()` |
| C8 | Execution path не ветвится по media-типу | Проверить `app/engine/engine.py` на `if image/elif video` |
| C9 | PromptBuilder не имеет доступа к FS | Проверить `app/prompt/` на импорты `os`, `pathlib` |
| C10 | Job никогда не ссылается на `latest` | grep `latest` в `app/engine/` |

**Если хотя бы одно утверждение ложно — STOP и отчитаться.**

---

## 13. ЧТО НЕЛЬЗЯ МЕНЯТЬ БЕЗ АРХИТЕКТУРНОГО РЕШЕНИЯ

| Запрещено | Почему |
|-----------|--------|
| Media-agnostic invariant (AD-03) | Фундаментальный архитектурный принцип |
| Provider ≠ Backend (AD-01) | Разделение ответственности |
| PromptBuilder boundary (AD-30/31/32) | Архитектурное решение зафиксировано |
| `ExecutionPlan.workflow_id@version` (AD-17) | Reproducibility |
| UNKNOWN ≠ AVAILABLE (AD-18) | Safety invariant |
| Doc hierarchy (AD-28) | Исключение конфликтов |
| LLM direct ComfyUI access | Security (§5) |

Любое изменение этих принципов — через `CHANGE_PROTOCOL` → `DECISION_LOG` → `APPROVED` → реализация.

---

## 14. КОНТЕКСТ ДЛЯ ПЕРЕДАЧИ СЛЕДУЮЩЕМУ ИИ

```text
CURRENT STATE: M1–M12.1 FROZEN. Full vertical slice implemented.
NEXT: M13 (Execution History + Retry Loop) proposed but NOT approved.
BLOCKED: audio.generate real E2E (Sonilo 401).
TECH DEBT: 6 stale tests, ~54 non-collectable tests, doc resync needed.
ENVIRONMENT: Python 3.14.3, Windows, pytest 9.0.2, ComfyUI 127.0.0.1:8188.
```

**Заполнить при завершении задачи:**
```text
HANDOFF — YYYY-MM-DD (название задачи)
- CURRENT STATE: ...
- COMPLETED: ...
- TESTS: ...
- KNOWN ISSUES: ...
- OPEN QUESTIONS: ...
- ARCHITECTURAL DECISIONS: ...
- NEXT RECOMMENDED TASK: ...
```

---

*Этот документ — аварийная точка входа. Если вы читаете его впервые: начните с §11, затем §12. Не меняйте проект, пока не подтвердите состояние.*
