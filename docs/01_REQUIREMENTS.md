> Source of truth: `PROJECT_SPEC.md` v0.2 (APPROVED).
> Derivative document — не вводит новых архитектурных решений.

# 01 — Requirements

## Функциональные требования (FR)
- **FR-001** Система принимает текстовые запросы.
- **FR-002** Система принимает изображения как ввод.
- **FR-003** Система принимает видео как ввод.
- **FR-004** Система принимает комбинацию нескольких assets в одном запросе.
- **FR-005** Система определяет capability задачи.
- **FR-006** Система выбирает совместимый workflow (через Capability Router + Compatibility Filter + Selection Policy).
- **FR-007** Система учитывает runtime requirements (RuntimeInfo vs manifest.requirements).
- **FR-008** Система запускает workflow в реальном ComfyUI.
- **FR-009** Система отслеживает execution (Job lifecycle + WebSocket/HTTP).
- **FR-010** Система возвращает результат как Asset.
- **FR-011** Система поддерживает многоходовый контекст (lineage активных ассетов/job).
- **FR-012** Система различает capability и workflow (одна capability → много workflow).
- **FR-013** Система фиксирует версию workflow в ExecutionPlan (`workflow_id@version`).
- **FR-014** Система помечает workflow статусом lifecycle, включая UNKNOWN.

## Нефункциональные требования
- **NFR-001** Media-agnostic core (ни один модуль ядра не ветвится по media-типу).
- **NFR-002** LLM не имеет прямого доступа к ComfyUI HTTP и не строит node-graph.
- **NFR-003** Реальный E2E на ComfyUI без mock (финальная валидация).
- **NFR-004** Расширяемость без переписывания ядра.

## Закрытые открытые вопросы (статус APPROVED)
- **OAQ-03** `required_custom_nodes` проверяются через `/object_info`; отсутствие → UNAVAILABLE; автоустановка вне v1.
- **OAQ-04** Идентификация модели — точное имя файла из runtime; без fuzzy matching; алиасы — future.
- **OAQ-05** Validation: (1) манифест, (2) структурная валидация `workflow.json`; не гарантирует успех графа (runtime — окончательно).
- **OAQ-07** Авто-retry в v1 нет; повтор — новый Job.
- **OAQ-11** Локальные файлы: только разрешённые roots, защита от traversal, MIME/ext, лимит размера, LLM без FS-доступа.

См. `PROJECT_SPEC.md` §2, §5, §24 (AD), §25.
