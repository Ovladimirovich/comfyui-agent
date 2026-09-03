"""SessionManager — управление сессиями (create, list, resume, archive).

Обеспечивает:
- Создание новых сессий
- Восстановление существующих сессий
- Список всех сессий
- Архивирование (пометка как archived)
"""
from __future__ import annotations

import time as _time
from typing import TYPE_CHECKING, Optional

from app.context.persistence import ContextPersistence

if TYPE_CHECKING:
    from app.conversation import ConversationContext


class SessionManager:
    """Менеджер сессий с persistence (M15).

    Управляет ConversationContext через ContextPersistence.
    """

    def __init__(self, persistence: Optional[ContextPersistence] = None) -> None:
        self.persistence = persistence or ContextPersistence()

    def create(self, session_id: Optional[str] = None) -> str:
        """Создать новую сессию. Возвращает session_id."""
        import uuid as _uuid
        from app.conversation import ConversationContext
        sid = session_id or str(_uuid.uuid4())
        ctx = ConversationContext(session_id=sid)
        self.persistence.save(sid, ctx.as_dict())
        return sid

    def resume(self, session_id: str) -> Optional[ConversationContext]:
        """Восстановить сессию из persistence. Возвращает ConversationContext или None."""
        from app.conversation import ConversationContext
        data = self.persistence.load(session_id)
        if data is None:
            return None
        # Восстанавливаем ConversationContext из dict
        ctx = ConversationContext(
            session_id=data["session_id"],
            messages=data.get("messages", []),
            assets=set(data.get("assets", [])),
            jobs=set(data.get("jobs", [])),
            workflows=set(data.get("workflows", [])),
            parameters=data.get("parameters", {}),
            active_task=data.get("active_task"),
            active_workflow=data.get("active_workflow"),
            active_job=data.get("active_job"),
            active_asset=data.get("active_asset"),
            unresolved=data.get("unresolved", []),
            dialog_state=data.get("dialog_state", "idle"),
        )
        return ctx

    def list_sessions(self) -> list[dict]:
        """Список всех сессий (метаданные)."""
        return self.persistence.list_sessions()

    def save(self, session_id: str, context: ConversationContext) -> None:
        """Сохранить текущее состояние контекста."""
        self.persistence.save(session_id, context.as_dict())

    def delete(self, session_id: str) -> bool:
        """Удалить сессию."""
        return self.persistence.delete(session_id)
