# TASK_PROTOCOL.md

Формат выполнения задачи. Каждая задача — чёткий scope.

<!-- id:1a8r6q -->
```text
Task
 → Scope
 → Relevant contracts
 → Files affected
 → Implementation
 → Tests
 → Validation
 → Risks
 → Handoff
```

- **Scope** — что входит и что НЕ входит (явно).
- **Relevant contracts** — ссылки на PROJECT_SPEC § + docs/0X.
- **Files affected** — список.
- **Implementation** — подход (без дублирования).
- **Tests** — unit / integration / architecture / real E2E.
- **Validation** — как докажешь, что работает (реальный ComfyUI для M1–M4).
- **Risks** — влияние на contracts, зависимости.
- **Handoff** — что оставить следующему агенту.
