# AGENT_PROTOCOL.md

Жизненный цикл ИИ-инженера. ИИ обязан сначала прочитать релевантные документы и существующий код,
а не сразу писать решение.

<!-- id:c5xk7d -->
```text
READ
 ↓
UNDERSTAND
 ↓
CHECK CURRENT STATE
 ↓
PLAN
 ↓
IMPLEMENT
 ↓
TEST
 ↓
SELF-REVIEW
 ↓
DOCUMENT
 ↓
HANDOFF
```

- **READ** — PROJECT_SPEC.md + релевантный docs/0X + engineering/* + существующий код.
- **UNDERSTAND** — убедись, что понял контракты и invariants.
- **CHECK CURRENT STATE** — tasks/ACTIVE.md, engineering/HANDOFF.md, статус ComfyUI.
- **PLAN** — оформи Task по TASK_PROTOCOL.md.
- **IMPLEMENT** — только в рамках SAFE CHANGE (CHANGE_PROTOCOL).
- **TEST** — по TEST_PROTOCOL.md (real E2E где требуется).
- **SELF-REVIEW** — чек-лист REVIEW_PROTOCOL.md.
- **DOCUMENT** — обнови tasks/*, при необходимости DECISION_LOG / CHANGELOG.
- **HANDOFF** — заполни HANDOFF.md для следующего агента.
