# TEST_PROTOCOL.md

Уровни тестирования:

<!-- id:8c1v4n -->
```text
Unit
Integration
Architecture
Real E2E
```

- **Unit** — без ComfyUI (Asset, Capability, Manifest, Router, WorkflowEngine, Job, Verifier).
- **Integration** — Agent→Operator, Operator→ComfyUI на реальном ComfyUI.
- **Architecture** — media-agnostic тест (M4): capability роутится тем же pipeline (Agent/Operator/Job/WorkflowEngine), что `txt2img`, доказывая отсутствие image-specific coupling. На этапе M4 использовался declared-only `video.generate`; в M6 `video_generate` стал исполнимым — архитектурный тест сохраняет смысл (единый путь для всех media).
- **Real E2E** — реальный ComfyUI + реальный workflow + реальная модель + реальный результат, без mock.

**Критично:** mock НЕ может считаться доказательством работоспособности ComfyUI execution chain.
Для M1–M4 обязательна реальная проверка на живом ComfyUI (`127.0.0.1:8188`) там, где указано в DoD (PROJECT_SPEC §23).
