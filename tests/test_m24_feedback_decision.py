"""M24 — Feedback-Driven Decision: тесты.

RetryPolicy.feedback_store — интеграция с FeedbackStore.
RetryDecision.action="ask_user" — запрос уточнения у пользователя.
RetryPolicy._check_feedback_after_success() — проверка rating.
Agent.generate() + ConversationAgent.turn() — ask_user handling.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass

from app.engine.retry import (
    RetryPolicy,
    RetryDecision,
    ERROR_TRANSIENT,
    ERROR_VERIFICATION,
)


# ---------------------------------------------------------------------------
# Мок FeedbackStore для тестов
# ---------------------------------------------------------------------------

@dataclass
class MockFeedbackRecord:
    attempt_id: str
    session_id: str
    rating: int
    comment: str = ""


class MockFeedbackStore:
    """Минимальный мок FeedbackStore для тестов M24."""

    def __init__(self):
        self.records: dict[str, MockFeedbackRecord] = {}

    def record(self, feedback: MockFeedbackRecord) -> None:
        self.records[feedback.attempt_id] = feedback

    def get_for_attempt(self, attempt_id: str, session_id: str):
        fb = self.records.get(attempt_id)
        if fb and fb.session_id == session_id:
            return fb
        return None


# ---------------------------------------------------------------------------
# 1. RetryDecision — action=ask_user
# ---------------------------------------------------------------------------

class TestRetryDecisionAskUser:
    """RetryDecision поддерживает action=ask_user."""

    def test_ask_user_action(self):
        d = RetryDecision(
            action="ask_user",
            reason="user rated 1/5",
            suggestions=["уточните запрос"],
        )
        assert d.action == "ask_user"

    def test_ask_user_with_suggestions(self):
        d = RetryDecision(
            action="ask_user",
            suggestions=["попробуйте другой промпт", "измените параметры"],
        )
        assert len(d.suggestions) == 2


# ---------------------------------------------------------------------------
# 2. RetryPolicy — feedback_store parameter
# ---------------------------------------------------------------------------

class TestRetryPolicyFeedbackStore:
    """RetryPolicy принимает feedback_store."""

    def test_default_no_feedback(self):
        p = RetryPolicy()
        assert p.feedback_store is None
        assert p.session_id is None

    def test_with_feedback_store(self):
        store = MockFeedbackStore()
        p = RetryPolicy(feedback_store=store, session_id="s1")
        assert p.feedback_store is store
        assert p.session_id == "s1"

    def test_low_rating_threshold_default(self):
        p = RetryPolicy()
        assert p.low_rating_threshold == 2


# ---------------------------------------------------------------------------
# 3. _check_feedback_after_success
# ---------------------------------------------------------------------------

class TestCheckFeedbackAfterSuccess:
    """_check_feedback_after_success() проверяет feedback."""

    def setup_method(self):
        self.store = MockFeedbackStore()
        self.policy = RetryPolicy(
            feedback_store=self.store,
            session_id="s1",
            low_rating_threshold=2,
        )

    def test_no_feedback_returns_none(self):
        result = self.policy._check_feedback_after_success("prompt_999")
        assert result is None

    def test_high_rating_returns_none(self):
        self.store.record(MockFeedbackRecord(
            attempt_id="prompt_1", session_id="s1", rating=5,
        ))
        result = self.policy._check_feedback_after_success("prompt_1")
        assert result is None

    def test_neutral_rating_returns_none(self):
        self.store.record(MockFeedbackRecord(
            attempt_id="prompt_1", session_id="s1", rating=3,
        ))
        result = self.policy._check_feedback_after_success("prompt_1")
        assert result is None

    def test_low_rating_returns_ask_user(self):
        self.store.record(MockFeedbackRecord(
            attempt_id="prompt_1", session_id="s1", rating=1,
        ))
        result = self.policy._check_feedback_after_success("prompt_1")
        assert result is not None
        assert result.action == "ask_user"
        assert "1/5" in result.reason

    def test_rating_2_returns_ask_user(self):
        self.store.record(MockFeedbackRecord(
            attempt_id="prompt_1", session_id="s1", rating=2,
        ))
        result = self.policy._check_feedback_after_success("prompt_1")
        assert result is not None
        assert result.action == "ask_user"

    def test_no_prompt_id_returns_none(self):
        result = self.policy._check_feedback_after_success(None)
        assert result is None

    def test_no_session_id_returns_none(self):
        policy = RetryPolicy(feedback_store=self.store)
        result = policy._check_feedback_after_success("prompt_1")
        assert result is None

    def test_no_store_returns_none(self):
        policy = RetryPolicy(session_id="s1")
        result = policy._check_feedback_after_success("prompt_1")
        assert result is None


# ---------------------------------------------------------------------------
# 4. RetryPolicy.decide() — feedback-driven logic
# ---------------------------------------------------------------------------

class TestRetryPolicyDecideWithFeedback:
    """decide() учитывает feedback при SUCCESS."""

    def setup_method(self):
        self.store = MockFeedbackStore()
        self.policy = RetryPolicy(
            feedback_store=self.store,
            session_id="s1",
            max_attempts=3,
        )

    def test_success_high_rating_returns_accept(self):
        self.store.record(MockFeedbackRecord(
            attempt_id="p1", session_id="s1", rating=5,
        ))
        d = self.policy.decide(state="SUCCESS", attempt=1, prompt_id="p1")
        assert d.action == "accept"

    def test_success_low_rating_returns_ask_user(self):
        self.store.record(MockFeedbackRecord(
            attempt_id="p1", session_id="s1", rating=1,
        ))
        d = self.policy.decide(state="SUCCESS", attempt=1, prompt_id="p1")
        assert d.action == "ask_user"
        assert "1/5" in d.reason

    def test_success_no_feedback_returns_accept(self):
        d = self.policy.decide(state="SUCCESS", attempt=1, prompt_id="p_unknown")
        assert d.action == "accept"

    def test_failed_low_rating_still_returns_retry(self):
        """FAILED + low rating → retry (feedback не влияет на failed path)."""
        self.store.record(MockFeedbackRecord(
            attempt_id="p1", session_id="s1", rating=1,
        ))
        d = self.policy.decide(
            state="FAILED", attempt=1,
            error_class=ERROR_TRANSIENT,
            prompt_id="p1",
        )
        assert d.action == "retry"

    def test_backward_compat_no_feedback(self):
        """RetryPolicy без feedback_store работает как раньше."""
        policy = RetryPolicy(max_attempts=3)
        d = policy.decide(state="SUCCESS", attempt=1)
        assert d.action == "accept"

    def test_backward_compat_no_prompt_id(self):
        """decide() без prompt_id работает как раньше."""
        d = self.policy.decide(state="SUCCESS", attempt=1)
        assert d.action == "accept"


# ---------------------------------------------------------------------------
# 5. Agent.generate() — ask_user handling
# ---------------------------------------------------------------------------

class TestAgentGenerateAskUser:
    """Agent.generate() обрабатывает ask_user决策."""

    def setup_method(self):
        from app.assets.store import AssetStore
        from app.engine.history import ExecutionHistory
        from app.agent import Agent

        self.store = MockFeedbackStore()
        self.history = ExecutionHistory()
        self.policy = RetryPolicy(
            max_attempts=1,
            feedback_store=self.store,
            session_id="s1",
        )
        self.agent = Agent(
            asset_store=AssetStore(),
            execution_history=self.history,
            retry_policy=self.policy,
        )

    def test_ask_user_sets_job_fields(self):
        """ask_user → job._decision_action, _decision_reason, _decision_suggestions."""
        self.store.record(MockFeedbackRecord(
            attempt_id="any", session_id="s1", rating=1,
        ))

        # Мокаем run чтобы вернуть SUCCESS (feedback потом trigger ask_user)
        from app.engine.job import Job, JobState
        import uuid

        fake_job = Job(
            prompt_id="feedback_test_1",
            workflow_id="w", version="1",
            capability="image.generate",
            state=JobState.SUCCESS,
        )

        with patch.object(self.agent, "run", return_value=fake_job):
            # Must trigger feedback lookup — set prompt_id on the record
            self.store.records.clear()
            self.store.record(MockFeedbackRecord(
                attempt_id="feedback_test_1", session_id="s1", rating=1,
            ))
            job = self.agent.generate(request="test", max_attempts=1)

        assert job._decision_action == "ask_user"
        assert job._decision_reason is not None
        assert job._decision_suggestions is not None
        assert len(job._decision_suggestions) > 0


# ---------------------------------------------------------------------------
# 6. ConversationAgent.turn() — ask_user event
# ---------------------------------------------------------------------------

class TestConversationTurnAskUser:
    """ConversationAgent.turn() эмитит feedback_request при ask_user."""

    def setup_method(self):
        from app.assets.store import AssetStore
        from app.engine.history import ExecutionHistory
        from app.conversation import ConversationAgent

        self.fb_store = MockFeedbackStore()
        self.history = ExecutionHistory()
        self.policy = RetryPolicy(
            max_attempts=1,
            feedback_store=self.fb_store,
            session_id="s1",
        )
        self.agent = ConversationAgent(
            AssetStore(),
            execution_history=self.history,
            retry_policy=self.policy,
            feedback_store=self.fb_store,  # M24.1: wire feedback_store to agent
        )
        self.session_id = "m24_test_session"

    def test_turn_ask_user_emits_feedback_request(self):
        """turn() при ask_user добавляет feedback_request event."""
        from unittest.mock import patch, MagicMock
        from app.engine.job import Job, JobState
        import uuid

        fake_job = Job(
            prompt_id="fb_test_1",
            workflow_id="w", version="1",
            capability="image.generate",
            state=JobState.SUCCESS,
        )

        self.fb_store.record(MockFeedbackRecord(
            attempt_id="fb_test_1", session_id="m24_test_session", rating=1,
        ))

        mock_manifest = MagicMock()
        mock_manifest.id = "test"
        mock_manifest.version = "1"
        mock_manifest.asset_inputs = {}
        mock_manifest.capability = "image.generate"

        mock_plan = MagicMock()
        mock_plan.params = {}
        mock_plan.capability = "image.generate"
        mock_plan.asset_bindings = {}

        with patch.object(self.agent, "prepare", return_value=(mock_manifest, mock_plan, MagicMock())):
            with patch.object(self.agent.engine, "execute", return_value=fake_job):
                job = self.agent.turn(
                    self.session_id,
                    request="test",
                    backend_id="local_comfyui",
                )

        ctx = self.agent.session(self.session_id)
        events = [m for m in ctx.messages if m.get("type") == "feedback_request"]
        assert len(events) >= 1
        event = events[0]
        assert "reason" in event
        assert "suggestions" in event
        assert ctx.dialog_state == "awaiting_feedback"
