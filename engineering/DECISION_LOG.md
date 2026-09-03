# DECISION_LOG.md

Журнал решений. НЕ заменяет Architectural Decisions внутри PROJECT_SPEC (§24) — дополняет их операционным контекстом.

<!-- id:n7k2pz -->
Формат:
```text
Date
Decision ID
Context
Decision
Reason
Affected components
Author/Agent
```

Новые архитектурные решения сначала получают ID (например, `AD-29`) и только после утверждения
становятся частью baseline (PROJECT_SPEC §24 + derived docs).

## История (уже APPROVED, перенесено в PROJECT_SPEC §24)
- **AD-24** (NQ-01) latest = max VALIDATED/AVAILABLE semver; Job не ссылается на latest. Author: architect-review.
- **AD-25** (NQ-02) limits: null=unlimited, 0=forbidden, positive=limit. Author: architect-review.
- **AD-26** (NQ-03) BackendRef{provider, backend, reference, metadata}; ComfyUI reference backend-specific. Author: architect-review.
- **AD-27** (S-01) DECLARED_ONLY — механизм для capability без исполнимого workflow. Исторически `video_generate` был DECLARED_ONLY на этапе M4; в M6 `video_generate`/`audio_generate` стали исполнимыми (DECLARED_ONLY снят, решение 2026-08-30). Author: architect-review.
- **AD-28** (doc hierarchy) PROJECT_SPEC > docs > engineering > tasks > code; конфликт → STOP→REPORT→DECISION→IMPLEMENT. Author: architect-review.

## Шаблон для новых
```text
Date:
Decision ID: AD-xx
Context:
Decision:
Reason:
Affected components:
Author/Agent:
Status: PROPOSED | APPROVED
```

## 2026-09-01 — AD-30, AD-31, AD-32 (Prompt Builder architectural decisions)
- **Decision ID:** AD-30, AD-31, AD-32
- **Context:** Архитектурное планирование M11 Prompt Builder + Dynamic Prompt Suggestions. Необходимо зафиксировать границы модуля и разделение ответственности с существующим Planner.
- **Decision:**
  - **AD-30:** PromptBuilder — отдельный модуль для улучшения промптов (`user text → quality prompt`), НЕ заменяет Planner (`user intent → capability/workflow`). PromptBuilder не имеет доступа к FS или ComfyUI; получает только декларативный контекст (строки и идентификаторы). Никаких bytes, файлов, путей, внутренних объектов ComfyUI.
  - **AD-31:** PromptBuilder улучшает текст промпта, но НЕ решает "image.generate или image.edit?". Выбор capability — исключительная ответственность Planner. PromptBuilder может использоваться UI напрямую через `/api/prompt/suggest` (MVP) или опционально интегрироваться в Planner/ConversationAgent (future scope).
  - **AD-32:** Улучшенный prompt должен содержать исходное намерение пользователя. `original_preserved` flag проверяется. Исходный пользовательский текст НИКОГДА не уничтожается автоматически без явного выбора пользователя.
- **Reason:** Чёткое разделение ответственности между Planner (capability selection) и PromptBuilder (prompt quality). Безопасность: PromptBuilder не имеет доступа к FS/ComfyUI. UX: пользователь сохраняет контроль над своим текстом.
- **Affected components:** `app/prompt/` (новый модуль), `app/ui.py` (endpoint `/api/prompt/suggest`), `docs/PROJECT_SPEC.md`, `docs/17_ROADMAP.md`, `docs/18_DEFINITION_OF_DONE.md`, `docs/20_PROMPT_BUILDER.md`.
- **Author/Agent:** architect-review
- **Status:** APPROVED (зафиксировано в PROJECT_SPEC §24)

## 2026-09-01 — AD-33, AD-34 (ComfyCLI Optional Infrastructure Adapter)

- **Decision ID:** AD-33, AD-34
- **Context:** Реализация M12.1 — опциональный infrastructure adapter для comfy-cli (diagnostics, валидация, управление процессами). Необходимо зафиксировать безопасность (shell=True запрещён) и опциональность (отсутствие CLI не блокирует Agent).
- **Decision:**
  - **AD-33:** Все subprocess-вызовы через `ComfyCLIAdapter` обязаны использовать `shell=False`. Тест `test_no_shell_true` проверяет это на уровне кода через AST-анализ импортов и вызовов `subprocess.run`. Никаких исключений.
  - **AD-34:** `ComfyCLIAdapter` полностью опциональный. `is_available()` возвращает `False` при отсутствии comfy-cli; все методы возвращают `ComfyCLIResult(ok=False, error="comfy-cli not available")`. Основной execution path (`ComfyClient` + `WorkflowEngine`) не зависит от CLI. Adapter не используется в `Agent`, `ConversationAgent`, `WorkflowEngine`, `Provider`, `AssetStore`. Отсутствие/ошибка CLI никогда не блокирует генерацию или execution.
- **Reason:** Безопасность (shell=True = command injection risk) + надёжность (comfy-cli не обязателен для работы Agent; infrastructure adapter = diagnostics/optional tooling).
- **Affected components:** `app/infrastructure/` (новый модуль), `tests/test_comfy_cli_adapter.py`, `docs/PROJECT_SPEC.md` (§24).
- **Author/Agent:** OpenCode (auto-implemented)
- **Status:** APPROVED (зафиксировано в PROJECT_SPEC §24)
