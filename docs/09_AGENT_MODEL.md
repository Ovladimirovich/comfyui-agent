> Source of truth: `PROJECT_SPEC.md` v0.2 (APPROVED).
> Derivative document — не вводит новых архитектурных решений.

# 09 — Agent Model

## Где появляется LLM
Только здесь. LLM не касается ComfyUI напрямую.

```text
User → Agent → Intent → Context → Planner → ExecutionPlan → Tools → Operator
```

## Зоны Agent
- **Intent** — намерение (capability + params + assets).
- **Context** — ConversationContext (см. 11_CONVERSATION_MODEL).
- **Planner** — LLM → ExecutionPlan (capability + workflow + bindings). Не исполняет.
- **Tools** — `comfy.get_status / list_capabilities / list_workflows / generate / edit / upscale / inpaint / get_job / cancel_job / get_result`. LLM видит только логич. параметры.

## Запреты для LLM (инварианты)
```text
LLM → ComfyUI HTTP             ЗАПРЕЩЕНО
LLM → создание node-graph     ЗАПРЕЩЕНО
LLM → несуществующие модели   ЗАПРЕЩЕНО (выбор только из доступных)
LLM → игнор runtime reqs      ЗАПРЕЩЕНО
LLM → произвольный shell/HTTP  ЗАПРЕЩЕНО
```

## LLM endpoint (AD-08)
OpenAI-совместимый, конфигурируемый (`LLM_BASE_URL`/`LLM_API_KEY`); дефолт `fallback_proxy :20130`. Не хардкод.

## Без LLM (M1–M4)
Ядро исполнения проверяется ДО подключения LLM: Planner/Tools не нужны для M1–M4 (AD-14).

См. `PROJECT_SPEC.md` §6, §9 (AGENT слой), §5, AD-08.
