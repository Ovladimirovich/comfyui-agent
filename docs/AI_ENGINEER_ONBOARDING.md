# AI_ENGINEER_ONBOARDING.md

**Статус:** BASELINE  
**Дата:** 2026-09-01  
**Назначение:** Входной чеклист для любого нового ИИ-инженера

---

## ⛔ ЗАПРЕЩЕНО ДО ПОДТВЕРЖДЕНИЯ СОСТОЯНИЯ

- Считать документацию доказательством существования кода
- Менять M1–M12 без read-only аудита
- Нарушать архитектурные инварианты (`PROJECT_SPEC.md §5`)
- Создавать новые модули только потому, что они есть в плане
- Начинать реализацию M13+ до проверки фактического состояния
- Писать код без запуска тестов после каждого изменения

---

## ✅ ОБЯЗАТЕЛЬНЫЙ ПОРЯДОК ВХОДА

```
STEP 1  →  Прочитать PROJECT_STATE_2026-09-01.md
           (что реально существует, проверено по коду)

STEP 2  →  Прочитать PROJECT_SPEC.md §0, §5, §24, §26
           (архитектурные инварианты и запреты)

STEP 3  →  Запустить: python -m pytest tests/ -q
           (фактическое состояние тестов)

STEP 4  →  Сравнить результат с PROJECT_STATE
           (если расхождения — STOP и зафиксировать)

STEP 5  →  Прочитать FUTURE_ROADMAP_ARCHITECTURE.md
           (где мы хотим оказаться)

STEP 6  →  Прочитать DEVELOPMENT_PLAN_M13_M18.md
           (конкретный план реализации)

STEP 7  →  Прочитать HANDOFF.md (последняя секция)
           (оперативная передача от предыдущего ИИ)

STEP 8  →  Заполнить VERIFICATION BLOCK в HANDOFF.md
           (подтвердить состояние)

STEP 9  →  Только после подтверждения — переходить к задаче
```

---

## 📋 PROHIBITIONS (жесткие запреты)

```text
1. Не переписывать M1–M12
   M1–M12 заморожены. Любое изменение = архитектурное решение
   через CHANGE_PROTOCOL → DECISION_LOG → APPROVED.

2. Не нарушать media-agnostic invariant (AD-03)
   Запрещено: if kind == "image" / elif kind == "video" в engine/provider/agent.
   Допустимо: обработка в manifest/registry (декларативно).

3. Не давать LLM доступ к FS/ComfyUI (AD-08)
   PromptBuilder не имеет доступа к файлам и ComfyUI HTTP.
   Только строки и идентификаторы.

4. Не смешивать Provider и Backend (AD-01)
   Provider — абстракция доступа. Backend — то, что исполняет.
   Они разделены в модели, даже если v1 = 1:1.

5. Не использовать UNKNOWN как AVAILABLE (AD-18)
   Если совместимость невозможно определить → UNKNOWN.
   UNKNOWN ≠ AVAILABLE. Только явный override оператора.

6. Не нарушать Doc Hierarchy (AD-28)
   PROJECT_SPEC.md выше всего.
   Код НЕ является источником истины.
   При конфликте: STOP → REPORT → ARCHITECTURAL DECISION → IMPLEMENT.

7. Не создавать autonomous learning system (NG3)
   Learning = aggregate statistics из истории.
   Не "самообучение" и не "адаптация без участия пользователя".

8. Не внедрять RAG / vector DB (NG2)
   Контекст = ConversationContext (in-memory или JSONL).
   Без векторных баз данных.

9. Не строить multi-agent (NG1)
   Один Agent. Один Planner. Один execution path.

10. Не начинать M13 автоматически
    DEVELOPMENT_PLAN_M13_M18.md = DRAFT FOR APPROVAL.
    M13–M18 — предложенное направление, не утверждённые задачи.
    Новый ИИ НЕ начинает M13 без отдельного approval от автора.
    Сначала заморозить M1–M12.1 как baseline.
```

---

## 🔍 PROTOCOL: ПЕРЕД ЛЮБОЙ РЕАЛИЗАЦИЕЙ

```
READ-ONLY AUDIT
  ↓
Сравнить: код vs тесты vs документация
  ↓
Результат → reconciliation report (в HANDOFF.md)
  ↓
Проблемы? → STOP → Architectural Decision
  ↓
Всё сходится? → APPROVAL → IMPLEMENT
```

---

## 📁 КАРТА ДОКУМЕНТОВ

| Документ | Зачем читать | Когда |
|----------|-------------|-------|
| `PROJECT_STATE_2026-09-01.md` | Фактическое состояние | STEP 1 — обязательно |
| `PROJECT_SPEC.md` | Архитектурные инварианты | STEP 2 — обязательно |
| `FUTURE_ROADMAP_ARCHITECTURE.md` | Куда идем | STEP 5 — опционально |
| `DEVELOPMENT_PLAN_M13_M18.md` | Что делать (DRAFT) | STEP 6 — опционально, статус DRAFT FOR APPROVAL |
| `HANDOFF.md` | Текущий контекст | STEP 7 — обязательно |
| `AI_ENGINEER_HANDOFF.md` | Аварийный entry point | При отсутствии других ориентиров |

---

## 🧪 СТАНДАРТНЫЕ КОМАНДЫ ПРОВЕРКИ

```powershell
# Основная проверка
python -m pytest tests/ -q

# M11 verification script
python tests/test_m11_verification.py

# Проверка конкретных M-тестов (collect 0 из-за Python 3.14)
python tests/test_prompt_builder_composite_m11.py
python tests/test_prompt_builder_llm_m11.py
python tests/test_prompt_builder_integration_m11.py
python tests/test_ui_m12.py

# Проверка структуры каталогов
ls app/comfy/lifecycle.py          # M12 ComfyUIProcessManager
ls app/infrastructure/comfy_cli_adapter.py  # M12.1 ComfyCLIAdapter
```

---

## 🚨 КОГДА ОСТАНАВЛИВАТЬСЯ

```text
STOP, если:
  - Расхождение между кодом и PROJECT_STATE > 5%
  - pytest показывает regressions ( падения в M1–M12 тестах)
  - Обнаружено media-ветвление в engine/provider/agent
  - Код нарушает AD-03/AD-08/AD-18/AD-28
  - Планируется изменение M1–M12 без архитектурного решения
  - Новый модуль не описан в DEVELOPMENT_PLAN

REPORT, если:
  - Конфликт между документацией и кодом
  - Невозможно определить фактическое состояние без прямого аудита
  - Обнаружены скрытые зависимости или размытые boundary'ы
```

---

## 📝 ШАБЛОН VERIFICATION BLOCK (заполнить после STEP 4)

```markdown
## VERIFICATION — YYYY-MM-DD

### Фактическое состояние
- pytest: [X] passed, [Y] failed, [Z] skipped
- Расхождения с PROJECT_STATE: [есть / нет]

### Подтверждено
- [ ] M1–M12 код существует
- [ ] Архитектурные инварианты не нарушены
- [ ] Media-agnostic invariant сохранён
- [ ] PromptBuilder boundary соблюдён
- [ ] ExecutionHistory отсутствует (ожидаемо, M13+)

### Действия
[Описать, что было сделано после подтверждения]
```

---

## 🎯 КРАТКАЯ ВЕРСИЯ (для быстрого входа)

> **Прочитать `PROJECT_STATE_2026-09-01.md` → запустить `pytest` → сравнить → если сходится, читать `FUTURE_ROADMAP_ARCHITECTURE.md` и `DEVELOPMENT_PLAN_M13_M18.md` → заполнить verification block → начинать работу.**

**Не начинать писать код, пока состояние не подтверждено.**
