> Source of truth: `PROJECT_SPEC.md` v0.2 (APPROVED).
> Derivative document — не вводит новых архитектурных решений.

# 02 — Architecture

## Слои (сверху вниз)
```text
USER → MULTIMODAL INPUT → AGENT → CAPABILITY ROUTER
    → WORKFLOW REGISTRY (Candidate Workflows)
    → COMPATIBILITY FILTER (Runtime/Provider/Model/CustomNodes/Inputs)
    → WORKFLOW SELECTION POLICY
    → EXECUTION PLAN (workflow_id@version)
    → COMFYUI OPERATOR → WORKFLOW ENGINE → PROVIDER ASSET TRANSPORT
    → EXECUTION BACKEND (ComfyUI) → EXECUTION/VERIFIER → ASSET STORE → CONTEXT/UI
```

## Границы ответственности
```text
Agent                понимает задачу (через LLM/Tools)
Capability Router     определяет capability
Workflow Registry     хранит манифесты; по capability → Candidate Workflows (НЕ выбирает финальный)
Compatibility Filter применяет декларативные constraints
Workflow Selection Policy выбирает ОДИН совместимый workflow (приоритет/override)
Provider             backend + upload_asset + execute + get_job + cancel (workflow НЕ выбирает)
Execution Backend    реально выполняет граф
Workflow Engine       чистый маппинг logical→node/field
Verifier             проверяет результат по output-contract
Asset Store          хранит и связывает assets (lineage)
Job Manager          жизнь Job (state/progress/cancel)
```

## Архитектурные инварианты (запреты)
```text
LLM → ComfyUI HTTP                   ЗАПРЕЩЕНО
LLM → node-id / node-graph           ЗАПРЕЩЕНО
LLM → произвольный shell/HTTP        ЗАПРЕЩЕНО
Agent → прямой ComfyUI HTTP          ЗАПРЕЩЕНО (только через Operator)
WorkflowEngine → image/video-логика  ЗАПРЕЩЕНО
Operator → знание media-типа         ЗАПРЕЩЕНО
Provider → самостоятельный выбор workflow ЗАПРЕЩЕНО
Workflow Registry → «умный агент»    ЗАПРЕЩЕНО
UNKNOWN compatibility → AVAILABLE     ЗАПРЕЩЕНО
```

## Связанные решения
AD-01 (Provider≠Backend), AD-03 (media-agnostic), AD-22 (selection split), AD-18 (UNKNOWN≠AVAILABLE).

См. `PROJECT_SPEC.md` §4, §5, §6, §24.
