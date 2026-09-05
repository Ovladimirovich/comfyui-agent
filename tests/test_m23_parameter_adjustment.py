"""M23 — Parameter Adjustment Strategy: тесты.

CorrectionStrategy — стратегии корректировки параметров.
RetryDecision.param_adjustments — рекомендованные изменения.
Agent.generate() — param_adjustments в retry path.
ExecutionRecord.corrections_applied — история корректировок.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from app.engine.retry import (
    RetryPolicy,
    RetryDecision,
    CorrectionStrategy,
    DEFAULT_CORRECTION_STRATEGIES,
    ERROR_TRANSIENT,
    ERROR_PERMANENT,
    ERROR_VERIFICATION,
    _adjust_steps_down,
    _adjust_steps_up,
    _adjust_timeout,
    _adjust_image_size_down,
    _adjust_cfg,
)


# ---------------------------------------------------------------------------
# 1. Встроенные функции корректировки
# ---------------------------------------------------------------------------

class TestBuiltinAdjustments:
    """Встроенные adjust_fn работают корректно."""

    def test_adjust_steps_down_low_score(self):
        result = _adjust_steps_down({"steps": 30}, semantic_score=0.2)
        assert result["steps"] < 30
        assert result["steps"] >= 5

    def test_adjust_steps_down_min_5(self):
        result = _adjust_steps_down({"steps": 3}, semantic_score=0.1)
        assert result["steps"] == 5

    def test_adjust_steps_up_medium_score(self):
        result = _adjust_steps_up({"steps": 20}, semantic_score=0.5)
        assert result["steps"] > 20
        assert result["steps"] <= 50

    def test_adjust_steps_up_max_50(self):
        result = _adjust_steps_up({"steps": 45}, semantic_score=0.5)
        assert result["steps"] == 50

    def test_adjust_timeout(self):
        result = _adjust_timeout({"timeout": 120})
        assert result["timeout"] == 180

    def test_adjust_timeout_max_300(self):
        result = _adjust_timeout({"timeout": 250})
        assert result["timeout"] == 300

    def test_adjust_image_size_down(self):
        result = _adjust_image_size_down({"width": 512, "height": 512})
        assert result["width"] == 384
        assert result["height"] == 384

    def test_adjust_image_size_min_256(self):
        result = _adjust_image_size_down({"width": 300, "height": 300})
        assert result["width"] == 256
        assert result["height"] == 256

    def test_adjust_cfg_low_score(self):
        result = _adjust_cfg({"cfg": 7.0}, semantic_score=0.2)
        assert result["cfg"] == 5.0

    def test_adjust_cfg_high_score(self):
        result = _adjust_cfg({"cfg": 7.0}, semantic_score=0.8)
        assert result["cfg"] == 8.0

    def test_preserves_other_params(self):
        result = _adjust_steps_down({"steps": 30, "prompt": "cat", "width": 512}, 0.2)
        assert result["prompt"] == "cat"
        assert result["width"] == 512


# ---------------------------------------------------------------------------
# 2. CorrectionStrategy
# ---------------------------------------------------------------------------

class TestCorrectionStrategy:
    """CorrectionStrategy корректно работает."""

    def test_strategy_stores_metadata(self):
        s = CorrectionStrategy(
            error_class=ERROR_VERIFICATION,
            adjust_fn=_adjust_steps_down,
            description="test strategy",
        )
        assert s.error_class == ERROR_VERIFICATION
        assert s.description == "test strategy"

    def test_default_strategies_exist(self):
        assert len(DEFAULT_CORRECTION_STRATEGIES) >= 2
        classes = {s.error_class for s in DEFAULT_CORRECTION_STRATEGIES}
        assert ERROR_VERIFICATION in classes
        assert ERROR_TRANSIENT in classes


# ---------------------------------------------------------------------------
# 3. RetryDecision.param_adjustments
# ---------------------------------------------------------------------------

class TestRetryDecisionParamAdjustments:
    """RetryDecision содержит param_adjustments."""

    def test_default_none(self):
        d = RetryDecision(action="accept")
        assert d.param_adjustments is None

    def test_can_set(self):
        d = RetryDecision(action="retry", param_adjustments={"steps": 30})
        assert d.param_adjustments == {"steps": 30}


# ---------------------------------------------------------------------------
# 4. RetryPolicy._compute_adjustments
# ---------------------------------------------------------------------------

class TestRetryPolicyComputeAdjustments:
    """_compute_adjustments вычисляет corrections на основе стратегий."""

    def setup_method(self):
        self.policy = RetryPolicy(max_attempts=3)

    def test_verification_low_score_reduces_steps(self):
        adjustments = self.policy._compute_adjustments(
            ERROR_VERIFICATION, {"steps": 30}, 0.2
        )
        assert adjustments is not None
        assert "steps" in adjustments
        assert adjustments["steps"] < 30

    def test_verification_medium_score_increases_steps(self):
        adjustments = self.policy._compute_adjustments(
            ERROR_VERIFICATION, {"steps": 20}, 0.5
        )
        assert adjustments is not None
        assert "steps" in adjustments
        assert adjustments["steps"] > 20

    def test_transient_increases_timeout(self):
        adjustments = self.policy._compute_adjustments(
            ERROR_TRANSIENT, {"timeout": 120}, None
        )
        assert adjustments is not None
        assert "timeout" in adjustments

    def test_permanent_no_adjustments(self):
        adjustments = self.policy._compute_adjustments(
            ERROR_PERMANENT, {"steps": 30}, None
        )
        assert adjustments is None

    def test_no_params_no_adjustments(self):
        adjustments = self.policy._compute_adjustments(
            ERROR_VERIFICATION, None, 0.2
        )
        assert adjustments is None

    def test_empty_strategies_no_adjustments(self):
        policy = RetryPolicy(correction_strategies=[])
        adjustments = policy._compute_adjustments(
            ERROR_VERIFICATION, {"steps": 30}, 0.2
        )
        assert adjustments is None

    def test_multiple_strategies_merged(self):
        """Две стратегии для verification: steps + cfg."""
        adjustments = self.policy._compute_adjustments(
            ERROR_VERIFICATION, {"steps": 30, "cfg": 7.0}, 0.2
        )
        assert adjustments is not None
        assert "steps" in adjustments
        assert "cfg" in adjustments


# ---------------------------------------------------------------------------
# 5. RetryPolicy.decide() с param_adjustments
# ---------------------------------------------------------------------------

class TestRetryPolicyDecideWithAdjustments:
    """decide() возвращает param_adjustments при retry."""

    def setup_method(self):
        self.policy = RetryPolicy(max_attempts=3)

    def test_retry_has_adjustments_for_verification(self):
        d = self.policy.decide(
            state="FAILED", attempt=1,
            error_class=ERROR_VERIFICATION,
            current_params={"steps": 30},
            semantic_score=0.2,
        )
        assert d.action == "retry"
        assert d.param_adjustments is not None
        assert "steps" in d.param_adjustments

    def test_retry_has_adjustments_for_transient(self):
        d = self.policy.decide(
            state="FAILED", attempt=1,
            error_class=ERROR_TRANSIENT,
            current_params={"timeout": 120},
        )
        assert d.action == "retry"
        assert d.param_adjustments is not None

    def test_retry_no_adjustments_without_params(self):
        d = self.policy.decide(
            state="FAILED", attempt=1,
            error_class=ERROR_VERIFICATION,
        )
        assert d.action == "retry"
        # Без current_params — нет adjustments
        assert d.param_adjustments is None

    def test_failed_no_adjustments(self):
        d = self.policy.decide(
            state="FAILED", attempt=3,
            error_class=ERROR_TRANSIENT,
            current_params={"steps": 30},
        )
        assert d.action == "failed"
        assert d.param_adjustments is None

    def test_accept_no_adjustments(self):
        d = self.policy.decide(state="SUCCESS", attempt=1)
        assert d.action == "accept"
        assert d.param_adjustments is None


# ---------------------------------------------------------------------------
# 6. ExecutionRecord.corrections_applied
# ---------------------------------------------------------------------------

class TestExecutionRecordCorrections:
    """ExecutionRecord хранит corrections_applied."""

    def test_record_has_corrections_field(self):
        from app.engine.history import ExecutionRecord
        r = ExecutionRecord(prompt_id="t", capability="c")
        assert r.corrections_applied is None

    def test_record_with_corrections(self):
        from app.engine.history import ExecutionRecord
        corrections = [{"error_class": "verification", "to_params": {"steps": 15}}]
        r = ExecutionRecord(
            prompt_id="t", capability="c",
            corrections_applied=corrections,
        )
        assert r.corrections_applied is not None
        assert r.corrections_applied[0]["error_class"] == "verification"

    def test_record_from_job_with_corrections(self):
        from app.engine.history import ExecutionRecord
        from app.engine.job import Job, JobState
        job = Job(
            prompt_id="t", workflow_id="w", version="1",
            capability="c", state=JobState.SUCCESS,
        )
        corrections = [{"error_class": "verification", "to_params": {"steps": 15}}]
        record = ExecutionRecord.from_job(job, corrections_applied=corrections)
        assert record.corrections_applied is not None

    def test_record_serialization_roundtrip(self):
        from app.engine.history import ExecutionRecord
        corrections = [{"error_class": "verification", "to_params": {"steps": 15}}]
        r = ExecutionRecord(
            prompt_id="t", capability="c",
            corrections_applied=corrections,
        )
        d = r.to_dict()
        r2 = ExecutionRecord.from_dict(d)
        assert r2.corrections_applied == corrections


# ---------------------------------------------------------------------------
# 7. Agent.generate() — param_adjustments в retry path
# ---------------------------------------------------------------------------

class TestAgentGenerateParamAdjustments:
    """Agent.generate() применяет param_adjustments при retry."""

    def setup_method(self):
        from app.assets.store import AssetStore
        from app.engine.history import ExecutionHistory
        from app.agent import Agent

        self.history = ExecutionHistory()
        self.policy = RetryPolicy(max_attempts=2)
        self.agent = Agent(
            asset_store=AssetStore(),
            execution_history=self.history,
            retry_policy=self.policy,
        )

    def test_decide_receives_current_params(self):
        """decide() вызывается с current_params."""
        original_decide = self.policy.decide
        call_kwargs = []

        def spy_decide(**kwargs):
            call_kwargs.append(kwargs)
            return original_decide(**kwargs)

        with patch.object(self.policy, "decide", side_effect=spy_decide):
            with patch.object(self.agent, "run", side_effect=RuntimeError("fail")):
                job = self.agent.generate(request="test", max_attempts=1)

        assert len(call_kwargs) >= 1
        assert "current_params" in call_kwargs[0]
        assert "semantic_score" in call_kwargs[0]

    def test_failed_job_has_corrections_tracking(self):
        """FAILED job получает _applied_corrections."""
        from app.engine.job import Job, JobState

        job = Job(
            prompt_id="t", workflow_id="w", version="1",
            capability="c", state=JobState.FAILED,
        )
        job._applied_corrections = None
        assert job._applied_corrections is None

        job._applied_corrections = [{"error_class": "verification"}]
        assert len(job._applied_corrections) == 1


# ---------------------------------------------------------------------------
# 8. Backward compatibility
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    """M23 backward compatible — decide() без новых аргументов работает."""

    def test_decide_without_new_args(self):
        policy = RetryPolicy(max_attempts=3)
        d = policy.decide(state="FAILED", attempt=1, error_class=ERROR_TRANSIENT)
        assert d.action == "retry"
        # param_adjustments может быть None (без current_params)
        assert d.param_adjustments is None

    def test_default_strategies_are_sane(self):
        for s in DEFAULT_CORRECTION_STRATEGIES:
            assert s.error_class in (ERROR_TRANSIENT, ERROR_PERMANENT, ERROR_VERIFICATION)
            assert callable(s.adjust_fn)
