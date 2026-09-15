# DOCS INDEX — навигатор по документации

> Source of truth — `docs/PROJECT_SPEC.md`. Остальное — производные документы.

## Обязательный порядок чтения (новому инженеру / ИИ)
1. `AGENTS.md` (корень) — правила работы
2. `engineering/HANDOFF.md` — текущее состояние проекта
3. `docs/PROJECT_STATE_2026-09-01.md` — аудированный срез состояния
4. `docs/PROJECT_SPEC.md` — §0, §5, §21, §22, §24 (инварианты, контракты, AD)
5. `engineering/AGENT_PROTOCOL.md` → `CHANGE_PROTOCOL.md` → `REVIEW_PROTOCOL.md` → `TEST_PROTOCOL.md`
6. `tasks/ACTIVE.md` / `tasks/BACKLOG.md`

## Архитектура / спецификация
| Файл | О чём |
|------|-------|
| `PROJECT_SPEC.md` | **Source of truth.** Инварианты, домен, milestones, AD-решения |
| `00_PROJECT_VISION.md` … `18_DEFINITION_OF_DONE.md` | Базовые спецификации (vision → требования → архитектура → домен → DoD) |
| `19_CONVERSATION_CONTEXT.md`, `20_PROMPT_BUILDER.md`, `20_UI.md` | Спецификации подсистем |
| `MASTER_DEVELOPMENT_ROADMAP.md`, `17_ROADMAP.md` | Roadmap |
| `FUTURE_ROADMAP_ARCHITECTURE.md`, `DEVELOPMENT_PLAN_M13_M18.md` | Планы развития |

## Ecosystem-First (S0.5–S6, M25–M26)
| Файл | О чём |
|------|-------|
| `ECOSYSTEM_FIRST_ARCHITECTURE.md` | Общая архитектура направления |
| `ECOSYSTEM_FIRST_S0_5_DESIGN.md` … `S6_DESIGN.md` | Дизайны этапов |
| `ECOSYSTEM_FIRST_S6_IMPLEMENTATION_REPORT.md` | Отчёт S6 |
| `M25_*.md`, `M26_*.md` | Аудиты/отчёты M25/M26 |
| `AD-MODEL-BINDING-001.md` | Решение по биндингу моделей |

## Agent UI
| Файл | О чём |
|------|-------|
| `AGENT_UI_ARCHITECTURE.md` | Архитектура Operator UI |
| `AGENT_UI_IMPLEMENTATION_PLAN.md` | План реализации |
| `AGENT_UI_UI3_DESIGN.md` | Дизайн UI3 |

## Knowledge Core / ноды
| Файл | О чём |
|------|-------|
| `COMFYUI_NODE_REFERENCE.md` | Автогенерируемый справочник нод (~978) |
| `node_docs/*.md` | Ручная документация пакетов нод |

## Аудиты / отчёты (исторические)
`ARCHITECTURAL_AUDIT_v1.md`, `ARCHITECTURE_AUDIT_2026-09-01.md`, `ARCHITECTURE_VERIFICATION_M13_M18.md`, `FORENSIC_M24_M25_AUDIT.md`, `PROJECT_STATE_2026-09-01.md`, `P0_FIXES_REPORT.md`, `P1_CAPABILITY_AUDIT.md`, `23_*`–`28_*.md`, `ECOSYSTEM_FIRST_S3_AUDIT.md` и др. — читаются при необходимости понять историю решений.

## Research / discovery
`22_INTENT_CAPABILITY_PLANNING_RESEARCH.md`, `ARCHITECTURE_ECOSYSTEM_DISCOVERY.md`, `ECOSYSTEM_FIRST_*`, `EXTENDED_DISCOVERY_DESIGN.md`, `GEMMA_E2B_OPERATOR_EVALUATION.md`