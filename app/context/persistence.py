"""ContextPersistence — JSONL-based persistence для ConversationContext.

Хранит состояние сессий в JSONL файлах (один файл на сессию).
Файлы в data/sessions/{session_id}.jsonl.
"""
from __future__ import annotations

import json
import os
from typing import Any, Optional


DEFAULT_SESSIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "sessions"
)


class ContextPersistence:
    """JSONL-based persistence для ConversationContext.

    Каждая сессия = один JSONL файл с snapshots.
    Последняя строка = текущее состояние.
    """

    def __init__(self, sessions_dir: str = DEFAULT_SESSIONS_DIR) -> None:
        self.sessions_dir = sessions_dir
        os.makedirs(sessions_dir, exist_ok=True)

    def _session_path(self, session_id: str) -> str:
        safe_id = session_id.replace("/", "_").replace("\\", "_")
        return os.path.join(self.sessions_dir, f"{safe_id}.jsonl")

    def save(self, session_id: str, context_dict: dict) -> None:
        """Сохранить snapshot контекста в JSONL файл."""
        path = self._session_path(session_id)
        snapshot = {
            "session_id": session_id,
            **context_dict,
        }
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(snapshot, ensure_ascii=False, default=str) + "\n")

    def load(self, session_id: str) -> Optional[dict]:
        """Загрузить последний snapshot контекста из JSONL файла."""
        path = self._session_path(session_id)
        if not os.path.exists(path):
            return None
        last_snapshot = None
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    last_snapshot = json.loads(line)
        return last_snapshot

    def list_sessions(self) -> list[dict]:
        """Список всех сессий (метаданные из последних snapshots)."""
        sessions = []
        for filename in os.listdir(self.sessions_dir):
            if not filename.endswith(".jsonl"):
                continue
            session_id = filename[:-6]  # убрать .jsonl
            path = os.path.join(self.sessions_dir, filename)
            last_snapshot = None
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        last_snapshot = json.loads(line)
            if last_snapshot:
                sessions.append({
                    "session_id": session_id,
                    "dialog_state": last_snapshot.get("dialog_state", "unknown"),
                    "active_task": last_snapshot.get("active_task"),
                    "active_asset": last_snapshot.get("active_asset"),
                    "messages_count": len(last_snapshot.get("messages", [])),
                    "assets_count": len(last_snapshot.get("assets", [])),
                })
        return sorted(sessions, key=lambda s: s["session_id"])

    def delete(self, session_id: str) -> bool:
        """Удалить файл сессии."""
        path = self._session_path(session_id)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False
