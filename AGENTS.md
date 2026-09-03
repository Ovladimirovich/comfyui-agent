# AGENTS.md — ComfyUI Agent v1 (AI Engineering Entry Point)

> Это operational layer поверх `docs/PROJECT_SPEC.md`. Не заменяет спецификацию, а задаёт порядок работы нескольких ИИ-инженеров.

## Что это за проект
ComfyUI Agent v1 — **Multimodal Agent Operator** поверх ComfyUI (локальный, AMD DirectML).
Ядро media-agnostic: image/video/audio проходят через один execution-pipeline.
Не генератор картинок, не wrapper, не чат-бот, не MCP-tools.

- Рабочая директория: `C:\cd\ComfyUI_AMD\agent\`
- ComfyUI: `127.0.0.1:8188` (только localhost)
- LLM (опц., M8+): OpenAI-совместимый endpoint `fallback_proxy :20130` (конфигурируемо `LLM_BASE_URL`)

## Source of truth
Единственный источник архитектурной истины — `docs/PROJECT_SPEC.md` (v0.2, APPROVED).
Производные документы (`docs/00..18`) и этот operational layer — **НЕ** источник истины.
**Нельзя использовать код как источник архитектурной истины.**

<!-- id:4pjv7f -->
```text
PROJECT_SPEC.md
      ↓
docs/*
      ↓
engineering/*
      ↓
tasks/*
      ↓
source code
      ↓
tests
```

## Порядок чтения документации
1. `docs/AI_ENGINEER_ONBOARDING.md` — **обязательный входной чеклист** (запреты + verification protocol).
2. `docs/PROJECT_STATE_2026-09-01.md` — фактическое состояние (что существует на самом деле).
3. `docs/PROJECT_SPEC.md` — §0, §5, §24, §26 (инварианты, AD, doc hierarchy).
4. `engineering/AGENT_PROTOCOL.md` → `engineering/CHANGE_PROTOCOL.md` → `engineering/REVIEW_PROTOCOL.md` → `engineering/TEST_PROTOCOL.md`.
5. Релевантный раздел `docs/0X_*.md` для задачи.
6. `tasks/ACTIVE.md` / `tasks/BACKLOG.md` — текущая задача.
7. `engineering/HANDOFF.md` — оперативная передача от предыдущего ИИ.
8. `docs/AI_ENGINEER_HANDOFF.md` — comprehensive reference (при отсутствии других ориентиров).

## Архитектурные инварианты (кратко; полный список — PROJECT_SPEC §5)
- LLM не имеет прямого доступа к ComfyUI HTTP и не строит node-graph.
- Agent не ходит в ComfyUI напрямую (только через Operator).
- WorkflowEngine не ветвится по media-типу; Operator не знает media-тип.
- Asset ≠ файл; Capability ≠ Workflow; Provider ≠ Model; Provider ≠ Execution Backend.
- UNKNOWN compatibility ≠ AVAILABLE.
- Job никогда не ссылается на `latest` (только `workflow_id@version`).

## Что ИИ может менять самостоятельно
- Код внутри утверждённых контрактов (SAFE CHANGE, см. CHANGE_PROTOCOL).
- Тесты, заметки в `tasks/*`, инженерные логи.
- Локальный рефакторинг без смены поведения публичных contracts.

## Что ИИ НЕ имеет права менять самостоятельно
- Архитектурные инварианты (PROJECT_SPEC §5).
- Domain model, public API, Provider contract, Asset contract, Workflow Manifest, execution semantics.
- Любое решение из PROJECT_SPEC §24 (AD-01..AD-28).
Такие изменения — на архитектурное решение (CHANGE_PROTOCOL → DECISION_LOG → APPROVED → PROJECT_SPEC).

## Порядок работы с задачей
READ → UNDERSTAND → CHECK STATE → PLAN → IMPLEMENT → TEST → SELF-REVIEW → DOCUMENT → HANDOFF.
Детали: `engineering/AGENT_PROTOCOL.md`, `engineering/TASK_PROTOCOL.md`.

## Обязательность тестов
- Каждое изменение ядра покрывается тестами (Unit / Integration / Architecture / Real E2E).
- Mock НЕ считается доказательством работоспособности ComfyUI execution chain (TEST_PROTOCOL).
- M1–M4 обязательно проверяются на реальном ComfyUI там, где указано в DoD (PROJECT_SPEC §23).

## Обязательность self-review
Перед завершением — чек-лист `engineering/REVIEW_PROTOCOL.md`. Без self-review задача не завершена.

## Правила передачи работы следующему агенту
- Заполнить `engineering/HANDOFF.md` (CURRENT STATE … NEXT RECOMMENDED TASK).
- Следующий ИИ читает HANDOFF.md и продолжает, не начинает заново.
- Обновить `tasks/ACTIVE.md` → `tasks/COMPLETED.md`.

## ГЛАВНОЕ ПРАВИЛО
> **ИИ не является владельцем архитектуры.**
> ИИ является исполнителем утверждённой архитектуры.
> Если для выполнения задачи требуется изменить архитектурный контракт, ИИ обязан остановиться,
> сформулировать изменение и вынести его на архитектурное решение.

## Второе правило
> **Никогда не исправлять архитектурное противоречие молча.**
> Если код, документация и PROJECT_SPEC расходятся:

<!-- id:7v1k4m -->
```text
STOP
 ↓
IDENTIFY CONFLICT
 ↓
REPORT
 ↓
ARCHITECTURAL DECISION
 ↓
IMPLEMENT
```

## Третье правило
> **Документация описывает намерение, код и тесты подтверждают факт.**
> При конфликте — сначала зафиксировать расхождение, не изменять код автоматически.

## Четвёртое правило
> **M13–M18 — предложенное направление (DRAFT), не утверждённый план.**
> Новый ИИ не начинает M13 без отдельного approval от автора проекта.
> Рекомендуется сначала заморозить M1–M12.1 как baseline.
