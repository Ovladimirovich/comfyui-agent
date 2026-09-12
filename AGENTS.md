# AGENTS.md — ComfyUI Agent v1 (AI Engineering Entry Point)

> Это operational layer поверх `docs/PROJECT_SPEC.md`. Не заменяет спецификацию, а задаёт порядок работы нескольких ИИ-инженеров.

## Что это за проект
ComfyUI Agent v1 — **Multimodal Agent Operator** поверх ComfyUI (локальный, CPU).

> **Runtime (2026-09-06):** ComfyUI 0.34.5 + Python 3.13.12 + Torch 2.12.1+cpu. Миграция с DirectML на CPU DirectML (Desktop).
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

## Agent UI правила (архитектурные; проектирование — `docs/AGENT_UI_ARCHITECTURE.md`)
> Agent UI — отдельный **Operator UI**, а НЕ вторая система управления агентом.
> Он отображает и инициирует операции существующего Agent Core; архитектурные решения агента принимает только Agent Core.

1. Agent UI является отдельным Operator UI (не интерактивом внутри ComfyUI).
2. ComfyUI является execution environment; Agent UI НЕ заменяет и НЕ копирует его.
3. UI не должен дублировать Agent Core (не хранит собственную государственную машину агента как истину).
4. UI не должен самостоятельно принимать архитектурные решения агента (выбор capability/workflow/planner/plan).
5. UI не должен содержать собственную Planner/WorkflowEngine/CapabilityRegistry/WorkflowRegistry/execution logic.
6. UI использует существующие backend-контракты (`/turn`, `/events`, `/api/session`, `/asset/<id>`) и только одобренные новые.
7. Source of truth для состояния агента — Agent Core/backend (ConversationContext / Job / Execution / Verifier / AssetStore / ExecutionHistory / Gateway). UI — лишь кэш отображения.
8. Не создавать второй execution engine (никакого второго пути в ComfyUI).
9. Не создавать второй registry.
10. Не возвращать старое `C:\cd\ComfyUI_AMD\ComfyUI` в проект и не создавать скрытый второй ComfyUI runtime.
11. Не использовать Gemma/comfyui-mcp как альтернативный Agent Core.
12. Не добавлять media-specific архитектурные ветки в Agent Core из-за UI (AD-03); UI сам media-agnostic (preview по asset.type).
13. Не реализовывать UI-заглушки, выдающие себя за реальные события (fake progress/states/execution). Любая новая UI-функция привязывается к существующему архитектурному контракту или одобренному новому (см. `docs/AGENT_UI_IMPLEMENTATION_PLAN.md`, раздел D).

## Управление границами сессий OpenCode (Session Boundary Management)

Это **механизм рекомендаций, а не жёсткий запрет**. OpenCode не создаёт новые пользовательские сессии автоматически (техническое ограничение OpenCode) — он ВЫВОДИТ рекомендацию начать новую сессию при логической границе работы.

### Порядок начала каждой новой сессии
Новая сессия восстанавливает состояние из репозитория, а не из истории чата:
1. Read `AGENTS.md`.
2. Read `engineering/HANDOFF.md` (в т.ч. блок «ТЕКУЩЕЕ СОСТОЯНИЕ»).
3. Read `tasks/ACTIVE.md` → `tasks/COMPLETED.md`.
4. Read релевантные source-of-truth документы (roadmap / PROJECT_SPEC / DECISION_LOG).
5. Определить текущий milestone и фазу.
6. Определить: сессия продолжает существующую фазу ИЛИ начинает новую.
7. Не выводить состояние из предыдущего чата, когда состояние есть в репозитории.

### Продолжать текущую сессию (CONTINUE), если
- выполняется одна конкретная задача;
- milestone ещё не завершён;
- идёт цепочка `implementation → tests → verification → self-review`;
- исправляется ошибка, относящаяся к текущему milestone;
- текущий scope не изменился.

### Рекомендовать новую сессию (START NEW SESSION), если
1. milestone принят / frozen;
2. read-only forensic audit завершён;
3. architecture / design завершён;
4. начинается implementation после отдельного audit / design;
5. implementation завершена и начинается независимая verification / review;
6. существенно изменился тип работы;
7. существенно изменился scope;
8. текущая задача закрыта и следующая — отдельный логический этап;
9. контекст сильно compacted и продолжение теряет ясность;
10. инженер смешивает текущую работу с ранее закрытыми milestones;
11. обнаружен scope creep;
12. следующий этап требует другого набора source-of-truth документов.

### Context compaction ≠ Session boundary
- **Compaction** — техническое управление размером контекста. Если задачу можно продолжить после compaction — продолжаем.
- **Session boundary** — логическое разделение работы. Даже если контекст помещается, рекомендуем новую сессию при завершении самостоятельного этапа.
- `large context ≠ mandatory new session`; `logical phase completed = appropriate new session`.

### Формат рекомендации
При логическом завершении сессии OpenCode выводит:
```
SESSION BOUNDARY RECOMMENDATION
Current phase: [...]
Status: COMPLETE / READY TO HAND OFF
Recommendation: START NEW SESSION
Reason:
- [...]
- [...]
Repository handoff: [файлы/документы с состоянием]
Next session should begin with: [...]
STOP AND WAIT.
```
Если новая сессия НЕ нужна — никаких навязчивых предупреждений.

### Рекомендация, не запрет
OpenCode не прекращает работу только потому, что milestone закончился, если пользователь явно велел продолжать в той же сессии. По умолчанию при естественной границе — рекомендовать новую сессию.

### Milestone lifecycle
`AUDIT → DESIGN/DECISION → IMPLEMENTATION → TEST/VERIFICATION → SELF-REVIEW → ACCEPTANCE → FROZEN → SESSION BOUNDARY`. Отдельная сессия между каждым пунктом НЕ обязательна; граница определяется по смыслу работы.

### Особое правило для forensic audit
- audit завершён + report сформирован → НЕ переходить к implementation автоматически → рекомендовать `NEW SESSION → architecture decision / implementation`;
- architecture / design завершён → `NEW SESSION → implementation`;
- implementation завершена → `NEW SESSION → independent verification`;
- verification завершена → `NEW SESSION → next milestone`.

### Защита от scope creep
Если во время текущей задачи обнаружен отдельный потенциальный gap, который (а) не нужен для выполнения текущей задачи; (б) относится к другому milestone; (в) требует отдельного architectural decision; (г) меняет scope:
1. зафиксировать его;
2. не реализовывать автоматически;
3. сообщить о нём;
4. при необходимости рекомендовать новую сессию для отдельного этапа.

## Четвёртое правило
> **M13–M18 — предложенное направление (DRAFT), не утверждённый план.**
> Новый ИИ не начинает M13 без отдельного approval от автора проекта.
> Рекомендуется сначала заморозить M1–M12.1 как baseline.
