"""FeedbackStore — хранение обратной связи пользователя.

Feedback привязан к конкретным попыткам (attempt_id = prompt_id).
Используется AdaptivePlanner для определения "что пользователю нравится".
"""
from __future__ import annotations

import json
import os
import time as _time
from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass
class FeedbackRecord:
    """Одна запись обратной связи."""
    attempt_id: str  # prompt_id из ExecutionRecord
    session_id: str
    rating: int  # 1-5 (1 = плохо, 5 = отлично)
    comment: str = ""
    timestamp: float = field(default_factory=_time.time)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> FeedbackRecord:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class FeedbackStore:
    """Хранилище обратной связи (M17).

    JSONL-based persistence (один файл на сессию).
    """

    def __init__(self, data_dir: str | None = None) -> None:
        if data_dir is None:
            data_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "data", "feedback"
            )
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)

    def _session_path(self, session_id: str) -> str:
        safe_id = session_id.replace("/", "_").replace("\\", "_")
        return os.path.join(self.data_dir, f"{safe_id}.jsonl")

    def record(self, feedback: FeedbackRecord) -> None:
        """Записать обратную связь."""
        path = self._session_path(feedback.session_id)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(feedback.to_dict(), ensure_ascii=False) + "\n")

    def get_for_session(self, session_id: str) -> list[FeedbackRecord]:
        """Получить всю обратную связь для сессии."""
        path = self._session_path(session_id)
        if not os.path.exists(path):
            return []
        records = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(FeedbackRecord.from_dict(json.loads(line)))
                    except (json.JSONDecodeError, TypeError):
                        continue
        return records

    def get_for_attempt(self, attempt_id: str, session_id: str) -> Optional[FeedbackRecord]:
        """Получить обратную связь для конкретной попытки."""
        records = self.get_for_session(session_id)
        for r in records:
            if r.attempt_id == attempt_id:
                return r
        return None

    def avg_rating(self, session_id: str) -> float:
        """Средний рейтинг для сессии."""
        records = self.get_for_session(session_id)
        if not records:
            return 0.0
        return sum(r.rating for r in records) / len(records)

    def get_all(self) -> list[FeedbackRecord]:
        """Все записи обратной связи (для analytics)."""
        all_records = []
        for filename in os.listdir(self.data_dir):
            if not filename.endswith(".jsonl"):
                continue
            session_id = filename[:-6]
            all_records.extend(self.get_for_session(session_id))
        return sorted(all_records, key=lambda r: r.timestamp, reverse=True)
