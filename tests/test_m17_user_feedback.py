"""M17 Tests — User Feedback Loop.

Тестирует:
- FeedbackStore: record, get_for_session, get_for_attempt, avg_rating, get_all
- FeedbackRecord: dataclass, to_dict, from_dict
- Integration: UI feedback endpoints
"""
from __future__ import annotations

import tempfile

import pytest

from app.context.feedback import FeedbackRecord, FeedbackStore


# --- FeedbackRecord tests ---

class TestFeedbackRecord:
    def test_create_record(self):
        record = FeedbackRecord(
            attempt_id="p1",
            session_id="s1",
            rating=5,
            comment="great!",
        )
        assert record.attempt_id == "p1"
        assert record.session_id == "s1"
        assert record.rating == 5
        assert record.comment == "great!"

    def test_to_dict(self):
        record = FeedbackRecord(
            attempt_id="p1",
            session_id="s1",
            rating=4,
            comment="good",
        )
        d = record.to_dict()
        assert d["attempt_id"] == "p1"
        assert d["rating"] == 4

    def test_from_dict(self):
        d = {
            "attempt_id": "p1",
            "session_id": "s1",
            "rating": 3,
            "comment": "ok",
            "timestamp": 1234567890.0,
        }
        record = FeedbackRecord.from_dict(d)
        assert record.attempt_id == "p1"
        assert record.rating == 3


# --- FeedbackStore tests ---

class TestFeedbackStore:
    def test_record_and_get(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FeedbackStore(data_dir=tmpdir)
            record = FeedbackRecord(
                attempt_id="p1",
                session_id="s1",
                rating=5,
                comment="excellent!",
            )
            store.record(record)
            records = store.get_for_session("s1")
            assert len(records) == 1
            assert records[0].rating == 5

    def test_get_for_attempt(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FeedbackStore(data_dir=tmpdir)
            store.record(FeedbackRecord(attempt_id="p1", session_id="s1", rating=5))
            store.record(FeedbackRecord(attempt_id="p2", session_id="s1", rating=3))
            record = store.get_for_attempt("p2", "s1")
            assert record is not None
            assert record.rating == 3

    def test_get_for_nonexistent_attempt(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FeedbackStore(data_dir=tmpdir)
            store.record(FeedbackRecord(attempt_id="p1", session_id="s1", rating=5))
            record = store.get_for_attempt("p999", "s1")
            assert record is None

    def test_avg_rating(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FeedbackStore(data_dir=tmpdir)
            store.record(FeedbackRecord(attempt_id="p1", session_id="s1", rating=5))
            store.record(FeedbackRecord(attempt_id="p2", session_id="s1", rating=3))
            assert store.avg_rating("s1") == 4.0

    def test_avg_rating_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FeedbackStore(data_dir=tmpdir)
            assert store.avg_rating("s1") == 0.0

    def test_get_all(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FeedbackStore(data_dir=tmpdir)
            store.record(FeedbackRecord(attempt_id="p1", session_id="s1", rating=5))
            store.record(FeedbackRecord(attempt_id="p2", session_id="s2", rating=4))
            all_records = store.get_all()
            assert len(all_records) == 2

    def test_session_isolation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FeedbackStore(data_dir=tmpdir)
            store.record(FeedbackRecord(attempt_id="p1", session_id="s1", rating=5))
            store.record(FeedbackRecord(attempt_id="p2", session_id="s2", rating=3))
            s1_records = store.get_for_session("s1")
            s2_records = store.get_for_session("s2")
            assert len(s1_records) == 1
            assert len(s2_records) == 1
            assert s1_records[0].rating == 5
            assert s2_records[0].rating == 3

    def test_multiple_feedback_per_attempt(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FeedbackStore(data_dir=tmpdir)
            store.record(FeedbackRecord(attempt_id="p1", session_id="s1", rating=5))
            store.record(FeedbackRecord(attempt_id="p1", session_id="s1", rating=4))
            records = store.get_for_attempt("p1", "s1")
            assert records is not None
            # get_for_attempt возвращает первую запись
            assert records.rating == 5
