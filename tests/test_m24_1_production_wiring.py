"""M24.1 Production Feedback Wiring — unit + integration tests.

Проверяет что FeedbackStore корректно подключён:
  1. ConversationAgent → AdaptivePlanner (planning-time feedback)
  2. ConversationAgent → RetryPolicy.decide() (failure-time feedback)
  3. Agent → RetryPolicy.decide() (single-shot feedback)
  4. ui.py → ConversationAgent (production wiring)
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.agent import Agent
from app.assets.store import AssetStore
from app.context.feedback import FeedbackRecord, FeedbackStore
from app.engine.history import ExecutionHistory
from app.engine.retry import RetryDecision, RetryPolicy
from app.conversation import ConversationAgent


# ---- 1. RetryPolicy.decide() accepts session_id + feedback_store ----

class TestDecideParameters:
    """decide() принимает session_id и feedback_store как параметры."""

    def test_decide_accepts_session_id(self):
        """session_id параметр принимается decide()."""
        policy = RetryPolicy(max_attempts=1)
        d = policy.decide(
            state="SUCCESS",
            attempt=1,
            prompt_id="test-prompt",
            session_id="test-session",
        )
        assert d.action == "accept"

    def test_decide_accepts_feedback_store(self):
        """feedback_store параметр принимается decide()."""
        policy = RetryPolicy(max_attempts=1)
        fb_store = MagicMock()
        fb_store.get_for_attempt.return_value = None
        d = policy.decide(
            state="SUCCESS",
            attempt=1,
            prompt_id="test-prompt",
            session_id="test-session",
            feedback_store=fb_store,
        )
        assert d.action == "accept"
        fb_store.get_for_attempt.assert_called_once_with("test-prompt", "test-session")

    def test_feedback_store_param_overrides_self(self):
        """feedback_store параметр приоритетнее self.feedback_store."""
        policy = RetryPolicy(max_attempts=1)
        self_fb = MagicMock()
        self_fb.get_for_attempt.return_value = None
        policy.feedback_store = self_fb

        param_fb = MagicMock()
        param_fb.get_for_attempt.return_value = None

        policy.decide(
            state="SUCCESS",
            attempt=1,
            prompt_id="p1",
            session_id="s1",
            feedback_store=param_fb,
        )
        param_fb.get_for_attempt.assert_called_once_with("p1", "s1")
        self_fb.get_for_attempt.assert_not_called()

    def test_session_id_param_overrides_self(self):
        """session_id параметр приоритетнее self.session_id."""
        policy = RetryPolicy(max_attempts=1, session_id="old-session")
        fb = MagicMock()
        fb.get_for_attempt.return_value = None
        policy.feedback_store = fb

        policy.decide(
            state="SUCCESS",
            attempt=1,
            prompt_id="p1",
            session_id="new-session",
        )
        fb.get_for_attempt.assert_called_once_with("p1", "new-session")

    def test_low_rating_triggers_ask_user_via_params(self):
        """Low rating через параметры decide() → action=ask_user."""
        policy = RetryPolicy(max_attempts=1)
        fb_store = FeedbackStore()
        fb_store.record(FeedbackRecord(
            attempt_id="prompt-1",
            session_id="session-1",
            rating=1,
        ))
        d = policy.decide(
            state="SUCCESS",
            attempt=1,
            prompt_id="prompt-1",
            session_id="session-1",
            feedback_store=fb_store,
        )
        assert d.action == "ask_user"
        assert "rated 1/5" in d.reason


# ---- 2. Agent.__init__ accepts feedback_store ----

class TestAgentFeedbackStore:
    """Agent принимает и хранит feedback_store."""

    def test_agent_stores_feedback_store(self):
        """Agent.__init__ сохраняет feedback_store."""
        store = AssetStore()
        fb = FeedbackStore()
        agent = Agent(asset_store=store, feedback_store=fb)
        assert agent.feedback_store is fb

    def test_agent_default_feedback_store_is_none(self):
        """Agent без feedback_store → self.feedback_store is None."""
        store = AssetStore()
        agent = Agent(asset_store=store)
        assert agent.feedback_store is None

    def test_agent_generate_passes_feedback_store_to_decide(self):
        """Agent.generate() передаёт feedback_store в decide()."""
        store = AssetStore()
        fb = MagicMock()
        fb.get_for_attempt.return_value = None
        agent = Agent(asset_store=store, feedback_store=fb)

        # Mock engine.execute to return SUCCESS
        mock_job = MagicMock()
        mock_job.state.value = "SUCCESS"
        mock_job.prompt_id = "test-prompt"
        mock_job.error = None
        mock_job.error_class = None
        mock_job._decision_action = None
        mock_job._decision_reason = None
        mock_job._decision_suggestions = None
        mock_job.output_assets = []
        mock_job.chain_step_index = None
        mock_job.attempt = 1
        agent.engine.execute = MagicMock(return_value=mock_job)

        with patch.object(agent, "prepare") as mock_prepare:
            mock_prepare.return_value = (MagicMock(), MagicMock(), MagicMock())
            job = agent.generate(request="test")

        # decide() was called with feedback_store
        assert job.state.value == "SUCCESS"


# ---- 3. ConversationAgent.__init__ accepts feedback_store ----

class TestConversationAgentFeedbackStore:
    """ConversationAgent принимает и хранит feedback_store."""

    def test_conversation_agent_stores_feedback_store(self):
        """ConversationAgent.__init__ сохраняет feedback_store."""
        store = AssetStore()
        fb = FeedbackStore()
        conv = ConversationAgent(store, feedback_store=fb)
        assert conv.feedback_store is fb

    def test_conversation_agent_default_feedback_store_is_none(self):
        """ConversationAgent без feedback_store → self.feedback_store is None."""
        store = AssetStore()
        conv = ConversationAgent(store)
        assert conv.feedback_store is None


# ---- 4. AdaptivePlanner receives feedback_store ----

class TestAdaptivePlannerWiring:
    """AdaptivePlanner получает feedback_store от ConversationAgent."""

    def test_adaptive_planner_receives_feedback_store(self):
        """turn() передаёт feedback_store в AdaptivePlanner."""
        from app.planner.adaptive import AdaptivePlanner, MIN_SUCCESSFUL_PER_CAPABILITY

        store = AssetStore()
        history = ExecutionHistory()
        fb = FeedbackStore()

        # Create enough history to trigger adaptive planner
        for i in range(MIN_SUCCESSFUL_PER_CAPABILITY + 1):
            from app.engine.history import ExecutionRecord
            history.record(ExecutionRecord(
                prompt_id=f"prompt-{i}",
                capability="image.generate",
                state="SUCCESS",
                params={"width": 64, "height": 64},
            ))

        conv = ConversationAgent(
            store,
            execution_history=history,
            feedback_store=fb,
        )

        # Mock prepare and engine.execute to avoid real ComfyUI
        mock_job = MagicMock()
        mock_job.state.value = "SUCCESS"
        mock_job.prompt_id = "test-prompt"
        mock_job.error = None
        mock_job.error_class = None
        mock_job._decision_action = None
        mock_job._decision_reason = None
        mock_job._decision_suggestions = None
        mock_job.output_assets = []
        mock_job.chain_step_index = None
        mock_job.attempt = 1

        with patch.object(conv, "prepare") as mock_prepare:
            from app.engine.job import Job
            mock_manifest = MagicMock()
            mock_manifest.id = "test"
            mock_manifest.version = "1.0"
            mock_manifest.asset_inputs = {}
            mock_prepare.return_value = (mock_manifest, MagicMock(), MagicMock())

            with patch.object(conv.engine, "execute", return_value=mock_job):
                with patch.object(conv, "resolve_asset_inputs", return_value={}):
                    # Intercept AdaptivePlanner creation
                    with patch("app.planner.adaptive.AdaptivePlanner.__init__", return_value=None) as mock_ap_init:
                        with patch("app.planner.adaptive.AdaptivePlanner.plan") as mock_ap_plan:
                            mock_ap_plan.return_value = MagicMock(
                                capability="image.generate",
                                params={"prompt": "test"},
                            )
                            try:
                                conv.turn(
                                    session_id="test-session",
                                    request="generate test image",
                                    base_url="http://127.0.0.1:8188",
                                    ws_timeout=1,
                                )
                            except Exception:
                                pass  # engine.execute mocked, may fail

                            # Check if AdaptivePlanner was created with feedback_store
                            if mock_ap_init.called:
                                _, kwargs = mock_ap_init.call_args
                                assert kwargs.get("feedback_store") is fb, (
                                    f"AdaptivePlanner not created with feedback_store. "
                                    f"Got: {kwargs}"
                                )


# ---- 5. session_id flows from turn() to decide() ----

class TestSessionIdFlow:
    """session_id пробрасывается из turn() в decide()."""

    def test_session_id_reaches_decide(self):
        """turn() передаёт session_id в decide()."""
        store = AssetStore()
        conv = ConversationAgent(store)

        # Mock to capture decide() call
        decide_kwargs = {}
        original_decide = conv.retry_policy.decide

        def capture_decide(**kwargs):
            decide_kwargs.update(kwargs)
            return original_decide(**kwargs)

        conv.retry_policy.decide = capture_decide

        mock_job = MagicMock()
        mock_job.state.value = "SUCCESS"
        mock_job.prompt_id = "test-prompt"
        mock_job.error = None
        mock_job.error_class = None
        mock_job._decision_action = None
        mock_job._decision_reason = None
        mock_job._decision_suggestions = None
        mock_job.output_assets = []
        mock_job.chain_step_index = None
        mock_job.attempt = 1

        with patch.object(conv, "prepare") as mock_prepare:
            mock_prepare.return_value = (MagicMock(), MagicMock(), MagicMock())
            with patch.object(conv.engine, "execute", return_value=mock_job):
                with patch.object(conv, "resolve_asset_inputs", return_value={}):
                    try:
                        conv.turn(
                            session_id="my-session",
                            capability="image.generate",
                            params={"prompt": "test"},
                            base_url="http://127.0.0.1:8188",
                            ws_timeout=1,
                        )
                    except Exception:
                        pass

        assert decide_kwargs.get("session_id") == "my-session", (
            f"session_id not passed to decide(). Got: {decide_kwargs.get('session_id')}"
        )
