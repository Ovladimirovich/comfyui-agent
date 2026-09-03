# CHANGE_PROTOCOL.md

Для работы нескольких ИИ. Разделяй типы изменений.

<!-- id:b6f3qk -->
```text
SAFE CHANGE
ARCHITECTURAL CHANGE
BREAKING CHANGE
```

## SAFE CHANGE (ИИ делает сам)
- Правки внутри утверждённых контрактов.
- Багфиксы без смены поведения публичных contracts.
- Добавление / обновление тестов.
- Локальный рефакторинг без смены contracts.

## ARCHITECTURAL CHANGE (на решение)
Изменение ниже требует архитектурного решения (DECISION_LOG → AD-ID → APPROVED → PROJECT_SPEC §24 → derived docs):
- domain model;
- public API;
- architectural invariant (PROJECT_SPEC §5);
- Provider contract;
- Asset contract;
- Workflow Manifest;
- execution semantics.

## BREAKING CHANGE (на явное APPROVED + CHANGELOG + обновление docs)
- Ломает публичный contract / обратную совместимость.
- Требует записи в CHANGELOG.md и обновления всех затронутых derived docs.

ИИ самостоятельно делает только SAFE CHANGE. Остальное — остановись, вынеси, получи решение.
