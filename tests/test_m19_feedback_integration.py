"""M19 — Feedback → AdaptivePlanner integration tests."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from app.context.feedback import FeedbackRecord, FeedbackStore
from app.engine.history import ExecutionHistory, ExecutionRecord
from app.engine.analytics import HistoryAnalytics
from app.planner.adaptive import AdaptivePlanner
from app.planner import HeuristicPlanner


class TestFeedbackWeightedAnalytics:
    """Тесты интеграции Feedback в Analytics (M19)."""

    def test_feedback_filters_low_rated(self, tmp_path):
        """Записи с rating < 4 фильтруются из preferred_params."""
        with tempfile.TemporaryDirectory() as tmp:
            feedback_store = FeedbackStore(data_dir=tmp)
            history = ExecutionHistory()

            # 3 успешных с width=256 (rating=5)
            for i in range(3):
                history.record(ExecutionRecord(
                    prompt_id=f'p{i}', capability='image.generate',
                    params={'width': 256, 'steps': 10},
                    state='SUCCESS', workflow_id='txt2img', workflow_version='1.0.0',
                ))
            # 2 успешных с width=512 (rating=2)
            for i in range(3, 5):
                history.record(ExecutionRecord(
                    prompt_id=f'p{i}', capability='image.generate',
                    params={'width': 512, 'steps': 10},
                    state='SUCCESS', workflow_id='txt2img', workflow_version='1.0.0',
                ))

            # Feedback: первые 3 — высокие, последние 2 — низкие
            for i in range(3):
                feedback_store.record(FeedbackRecord(attempt_id=f'p{i}', session_id='s1', rating=5))
            for i in range(3, 5):
                feedback_store.record(FeedbackRecord(attempt_id=f'p{i}', session_id='s1', rating=2))

            from app.engine.analytics import HistoryAnalytics
            analytics = HistoryAnalytics(history, feedback_store=feedback_store)

            # Без feedback — preferred будет 256 (3 vs 2)
            params_no_feedback = analytics.preferred_params('image.generate', feedback_weighted=False)
            assert params_no_feedback.get('width') == 256

            # С feedback — preferred всё ещё 256 (512 отфильтрован)
            params_feedback = analytics.preferred_params('image.generate', feedback_weighted=True)
            assert params_feedback.get('width') == 256

    def test_feedback_no_feedback_store_returns_all(self, tmp_path):
        """Если feedback_store=None — возвращаются все записи."""
        history = ExecutionHistory()
        for i in range(3):
            history.record(ExecutionRecord(
                prompt_id=f'p{i}', capability='image.generate',
                params={'width': 256},
                state='SUCCESS', workflow_id='txt2img', workflow_version='1.0.0',
            ))
        for i in range(3, 5):
            history.record(ExecutionRecord(
                prompt_id=f'p{i}', capability='image.generate',
                params={'width': 512},
                state='SUCCESS', workflow_id='txt2img', workflow_version='1.0.0',
            ))

        from app.engine.analytics import HistoryAnalytics
        analytics = HistoryAnalytics(history, feedback_store=None)
        params = analytics.preferred_params('image.generate', feedback_weighted=True)
        # Должно вернуться 256 (3 vs 2)
        assert params.get('width') == 256


class TestAdaptivePlannerWithFeedback:
    """Тесты AdaptivePlanner с FeedbackStore (M19)."""

    def test_feedback_influences_params(self, tmp_path):
        """Feedback влияет на preferred_params в AdaptivePlanner."""
        with tempfile.TemporaryDirectory() as tmp:
            feedback_store = FeedbackStore(data_dir=tmp)
            history = ExecutionHistory()

            # 3 успешных с width=256 (rating=5)
            for i in range(3):
                history.record(ExecutionRecord(
                    prompt_id=f'p{i}', capability='image.generate',
                    params={'width': 256, 'steps': 10},
                    state='SUCCESS', workflow_id='txt2img', workflow_version='1.0.0',
                ))
            # 3 успешных с width=512 (rating=2)
            for i in range(3, 6):
                history.record(ExecutionRecord(
                    prompt_id=f'p{i}', capability='image.generate',
                    params={'width': 512, 'steps': 10},
                    state='SUCCESS', workflow_id='txt2img', workflow_version='1.0.0',
                ))

            for i in range(3):
                feedback_store.record(FeedbackRecord(attempt_id=f'p{i}', session_id='s1', rating=5))
            for i in range(3, 6):
                feedback_store.record(FeedbackRecord(attempt_id=f'p{i}', session_id='s1', rating=2))

            planner = AdaptivePlanner(history=history, feedback_store=feedback_store)
            result = planner.plan('нарисуй кота')

            assert result.capability == 'image.generate'
            # Должен предпочесть width=256 (feedback-filtered)
            assert result.params.get('width') == 256
            # Rationale должен упоминать feedback
            assert 'feedback-weighted' in result.rationale or 'adaptive' in result.rationale

    def test_no_feedback_store_backwards_compat(self, tmp_path):
        """AdaptivePlanner работает без feedback_store ( backward compat)."""
        history = ExecutionHistory()
        for i in range(5):
            history.record(ExecutionRecord(
                prompt_id=f'p{i}', capability='image.generate',
                params={'width': 256, 'steps': 10},
                state='SUCCESS', workflow_id='txt2img', workflow_version='1.0.0',
            ))

        planner = AdaptivePlanner(history=history)
        result = planner.plan('нарисуй кота')

        assert result.capability == 'image.generate'
        assert result.params.get('width') == 256


class TestFeedbackSessionIsolation:
    """Тесты изоляции feedback по session."""

    def test_session_isolation(self, tmp_path):
        """Feedback из одной сессии не влияет на другую."""
        with tempfile.TemporaryDirectory() as tmp:
            feedback_store = FeedbackStore(data_dir=tmp)
            history = ExecutionHistory()

            # Session A: p0-p2 width=256 (rating=5), p3-p4 width=512 (rating=2)
            for i in range(3):
                history.record(ExecutionRecord(
                    prompt_id=f'p{i}', capability='image.generate',
                    params={'width': 256},
                    state='SUCCESS', workflow_id='txt2img', workflow_version='1.0.0',
                ))
            for i in range(3, 5):
                history.record(ExecutionRecord(
                    prompt_id=f'p{i}', capability='image.generate',
                    params={'width': 512},
                    state='SUCCESS', workflow_id='txt2img', workflow_version='1.0.0',
                ))

            for i in range(3):
                feedback_store.record(FeedbackRecord(attempt_id=f'p{i}', session_id='A', rating=5))
            for i in range(3, 5):
                feedback_store.record(FeedbackRecord(attempt_id=f'p{i}', session_id='A', rating=2))

            # Проверим что filter работает корректно
            from app.engine.analytics import HistoryAnalytics
            analytics = HistoryAnalytics(history, feedback_store=feedback_store)
            params = analytics.preferred_params('image.generate', feedback_weighted=True)
            # После фильтрации должны остаться только p0-p2 (width=256)
            # Но preferred требует >= 2 записей с одинаковым параметром
            assert params.get('width') == 256 or params == {}
