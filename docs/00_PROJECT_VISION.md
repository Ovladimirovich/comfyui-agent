> Source of truth: `PROJECT_SPEC.md` v0.2 (APPROVED).
> Derivative document — не вводит новых архитектурных решений.

# 00 — Project Vision

## Главный принцип
ComfyUI Agent — **Multimodal Agent Operator для ComfyUI**, а не агент генерации изображений.
Image / Video / Audio и другие media types проходят через одну media-agnostic execution-архитектуру.

## Ключевая формула
```text
User → Multimodal Input → Agent → Intent/Context → Capability
     → Provider → Workflow → Execution Backend → Execution
     → Verification → Asset → Context/UI
```

## Является
- Multimodal Agent Operator поверх ComfyUI.
- Media-agnostic execution-слоем (image/video/audio/…).
- Контекстным (многоходовым) оператором с lineage ассетов.

## Не является
- image generator;
- wrapper над ComfyUI;
- универсальный чат-бот;
- набор MCP tools;
- копия существующего агента (в т.ч. AI Video Operator);
- «цифровой организм» / autonomous learning system.

## Недопустимые отождествления (аксиомы)
```text
Capability ≠ Workflow
Provider  ≠ Model
Provider  ≠ Execution Backend
Asset     ≠ File
Workflow  ≠ Node Graph для LLM
ComfyUI   ≠ Agent
```

См. `PROJECT_SPEC.md` §0, §1.
