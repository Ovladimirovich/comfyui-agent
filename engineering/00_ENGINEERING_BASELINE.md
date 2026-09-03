# Engineering Baseline — ComfyUI Agent v1

> Индекс-консолидатор documentation baseline. Авторитетные архитектурные решения —
> в `docs/PROJECT_SPEC.md` §24 (AD-01..AD-28); операционный журнал — `engineering/DECISION_LOG.md`,
> `CHANGELOG.md`, `HANDOFF.md`. Этот файл восстановлен, т.к. он входит в цепочку baseline,
> указанную автором (создан поверх нового engineering-слоя, не дублирует истину).

## Статус
- `docs/PROJECT_SPEC.md` v0.2 — APPROVED.
- `docs/00..18_*.md` — APPROVED.
- `AGENTS.md` + `engineering/*` (ENGINEERING_RULES, AGENT_PROTOCOL, TASK_PROTOCOL,
  CHANGE_PROTOCOL, REVIEW_PROTOCOL, TEST_PROTOCOL, DECISION_LOG, CHANGELOG, HANDOFF) — APPROVED.
- **M1 — в работе** (см. `engineering/HANDOFF.md`).

## Решения после ревью документации (AD-24..AD-28)
- **AD-24** latest = max VALIDATED/AVAILABLE semver; Job не ссылается на `latest`.
- **AD-25** limits: null=unlimited, 0=forbidden, positive=limit.
- **AD-26** BackendRef{provider, backend, reference, metadata}; ComfyUI reference backend-specific.
- **AD-27** DECLARED_ONLY — механизм для capability без исполнимого workflow. Исторически применялся к `video_generate` (M4); в M6 `video_generate`/`audio_generate` стали исполнимыми (DECLARED_ONLY снят).
- **AD-28** doc hierarchy + conflict procedure (PROJECT_SPEC §26).

См. `AGENTS.md`, `docs/PROJECT_SPEC.md` §26.
