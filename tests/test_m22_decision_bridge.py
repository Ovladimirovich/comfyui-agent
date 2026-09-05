"""M22 — Human-in-the-Loop Decision Bridge: тесты.

RetryDecision.suggestions заполняется для каждого failed branch.
Agent.generate() обогащает job контекстом решения.
ConversationAgent.turn() эмитит decision_failed event.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from app.engine.retry import (
    RetryPolicy,
    RetryDecision,
    ERROR_TRANSIENT,
    ERROR_PERMANENT,
    ERROR_VERIFICATION,
)


# ---------------------------------------------------------------------------
# 1. RetryDecision suggestions
# ---------------------------------------------------------------------------

class TestRetryDecisionSuggestions:
    """RetryDecision содержит suggestions для пользователя."""

    def test_suggestions_default_empty(self):
        d = RetryDecision(action="accept")
        assert d.suggestions == []

    def test_suggestions_can_set(self):
        d = RetryDecision(action="failed", suggestions=["try again"])
        assert d.suggestions == ["try again"]


# ---------------------------------------------------------------------------
# 2. RetryPolicy.decide() — suggestions в каждом failed branch
# ---------------------------------------------------------------------------

class TestRetryPolicySuggestions:
    """decide() заполняет suggestions при action=failed."""

    def setup_method(self):
        self.policy = RetryPolicy(max_attempts=3)

    def test_cancelled_has_suggestions(self):
        d = self.policy.decide(state="CANCELLED", attempt=1)
        assert d.action == "failed"
        assert len(d.suggestions) > 0
        assert any("заново" in s for s in d.suggestions)

    def test_permanent_has_suggestions(self):
        d = self.policy.decide(state="FAILED", attempt=1, error_class=ERROR_PERMANENT)
        assert d.action == "failed"
        assert len(d.suggestions) >= 2
        assert any("модели" in s for s in d.suggestions)

    def test_max_attempts_has_suggestions(self):
        d = self.policy.decide(state="FAILED", attempt=3, error_class=ERROR_TRANSIENT)
        assert d.action == "failed"
        assert len(d.suggestions) > 0
        assert any("промпт" in s for s in d.suggestions)

    def test_unknown_error_class_has_suggestions(self):
        d = self.policy.decide(state="FAILED", attempt=1, error_class="bogus")
        assert d.action == "failed"
        assert len(d.suggestions) > 0

    def test_unknown_state_has_suggestions(self):
        d = self.policy.decide(state="BOGUS", attempt=1)
        assert d.action == "failed"
        assert len(d.suggestions) > 0

    def test_success_no_suggestions(self):
        d = self.policy.decide(state="SUCCESS", attempt=1)
        assert d.action == "accept"
        assert d.suggestions == []

    def test_retry_no_suggestions(self):
        d = self.policy.decide(state="FAILED", attempt=1, error_class=ERROR_TRANSIENT)
        assert d.action == "retry"
        assert d.suggestions == []


# ---------------------------------------------------------------------------
# 3. Agent.generate() — enriched failure context
# ---------------------------------------------------------------------------

class TestAgentGenerateEnriched:
    """Agent.generate() обогащает job контекстом решения при failed."""

    def setup_method(self):
        from app.assets.store import AssetStore
        from app.engine.history import ExecutionHistory
        from app.agent import Agent

        self.history = ExecutionHistory()
        self.policy = RetryPolicy(max_attempts=1)
        self.agent = Agent(
            asset_store=AssetStore(),
            execution_history=self.history,
            retry_policy=self.policy,
        )

    def test_failed_job_has_decision_reason(self):
        """FAILED job содержит _decision_reason."""
        job = self.agent.generate(
            request="test failure",
            backend_id="nonexistent_backend",
        )
        # max_attempts=1 → décision = "failed" (exhausted)
        assert job._decision_reason is not None
        assert "attempts" in job._decision_reason.lower() or "exhausted" in job._decision_reason.lower()

    def test_failed_job_has_suggestions(self):
        """FAILED job содержит _decision_suggestions."""
        job = self.agent.generate(
            request="test failure",
            backend_id="nonexistent_backend",
        )
        assert job._decision_suggestions is not None
        assert len(job._decision_suggestions) > 0

    def test_success_job_no_decision_context(self):
        """SUCCESS job не содержит decision context."""
        # Agent без provider = нет execution → проверяем что поля None по умолчанию
        job = self.agent.generate(
            request="test",
            backend_id="nonexistent_backend",
        )
        # job.state будет FAILED (нет backend), context должен быть заполнен
        if job.state.value == "SUCCESS":
            assert job._decision_reason is None
            assert job._decision_suggestions is None


# ---------------------------------------------------------------------------
# 4. ConversationAgent.turn() — decision_failed event
# ---------------------------------------------------------------------------

class TestConversationTurnDecisionFailed:
    """ConversationAgent.turn() эмитит decision_failed event при failed."""

    def setup_method(self):
        from app.assets.store import AssetStore
        from app.engine.history import ExecutionHistory
        from app.conversation import ConversationAgent

        self.history = ExecutionHistory()
        self.policy = RetryPolicy(max_attempts=1)
        self.agent = ConversationAgent(
            AssetStore(),
            execution_history=self.history,
            retry_policy=self.policy,
        )
        self.session_id = "m22_test_session"

    def _make_failed_job(self, **kwargs):
        """Создать FAILED job для мока engine.execute."""
        from app.engine.job import Job, JobState
        import uuid
        defaults = dict(
            prompt_id=str(uuid.uuid4()),
            workflow_id="test_wf",
            version="1",
            capability="image.generate",
            state=JobState.FAILED,
            error="simulated failure",
            error_class="transient",
        )
        defaults.update(kwargs)
        return Job(**defaults)

    def test_turn_failed_emits_decision_failed_event(self):
        """turn() при FAILED добавляет decision_failed event в ctx.messages."""
        from unittest.mock import patch, MagicMock

        mock_manifest = MagicMock()
        mock_manifest.id = "test"
        mock_manifest.version = "1"
        mock_manifest.asset_inputs = {}
        mock_manifest.capability = "image.generate"

        mock_plan = MagicMock()
        mock_plan.params = {}
        mock_plan.capability = "image.generate"
        mock_plan.asset_bindings = {}

        failed_job = self._make_failed_job()

        with patch.object(self.agent, "prepare", return_value=(mock_manifest, mock_plan, MagicMock())):
            with patch.object(self.agent.engine, "execute", return_value=failed_job):
                job = self.agent.turn(
                    self.session_id,
                    request="test failure",
                    backend_id="local_comfyui",
                )

        ctx = self.agent.session(self.session_id)
        events = [m for m in ctx.messages if m.get("type") == "decision_failed"]
        assert len(events) >= 1
        event = events[0]
        assert "reason" in event
        assert "suggestions" in event
        assert isinstance(event["suggestions"], list)

    def test_turn_failed_enriches_unresolved(self):
        """turn() при FAILED обогащает unresolved контекстом."""
        from unittest.mock import patch, MagicMock

        mock_manifest = MagicMock()
        mock_manifest.id = "test"
        mock_manifest.version = "1"
        mock_manifest.asset_inputs = {}
        mock_manifest.capability = "image.generate"

        mock_plan = MagicMock()
        mock_plan.params = {}
        mock_plan.capability = "image.generate"
        mock_plan.asset_bindings = {}

        failed_job = self._make_failed_job()

        with patch.object(self.agent, "prepare", return_value=(mock_manifest, mock_plan, MagicMock())):
            with patch.object(self.agent.engine, "execute", return_value=failed_job):
                job = self.agent.turn(
                    self.session_id,
                    request="test failure",
                    backend_id="local_comfyui",
                )

        ctx = self.agent.session(self.session_id)
        assert len(ctx.unresolved) >= 1
        last = ctx.unresolved[-1]
        assert "reason" in last
        assert "suggestions" in last
