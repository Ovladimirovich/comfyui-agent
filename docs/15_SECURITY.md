> Source of truth: `PROJECT_SPEC.md` v0.2 (APPROVED).
> Derivative document — не вводит новых архитектурных решений.

# 15 — Security

## Модель (OAQ-11 — APPROVED)
- ComfyUI слушает только `127.0.0.1` (не выставлять наружу).
- LLM не имеет произвольного shell/HTTP; только whitelist Tools (`comfy.*`).
- Workflow валидируется до исполнения (manifest + граф).
- **Локальные файлы:**
  - Asset paths только внутри разрешённых roots (`data/assets`, `static/assets`);
  - защита от path traversal;
  - MIME/extension validation;
  - лимит размера (`MAX_UPLOAD_BYTES` + per-workflow `limits`);
  - LLM не имеет произвольного filesystem access;
  - Agent работает только через Asset abstraction;
  - прямые пути ОС НЕ являются частью LLM tool interface.

## Секреты
- `LLM_API_KEY` / `GEMINI_KEY` — только в `.env`, не в репозиторий.
- localhost-вызовы без системного прокси (Hiddify блокирует localhost).

## Capability-aware limits (AD-21 / OAQ-10)
Глобальный `MAX_UPLOAD_BYTES` + per-workflow `limits` (duration/width/height/sequence); отказ > лимита с ясной ошибкой.

См. `PROJECT_SPEC.md` §20, AD-21.
