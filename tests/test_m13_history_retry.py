"""M13 Tests — Execution History + Retry Loop.

Тестирует:
- ExecutionRecord: creation, serialization, deserialization
- ExecutionHistory: record, retrieval, filtering, persistence, analytics
- RetryPolicy: decision logic, backoff, error classification
- VerificationResult: diagnostics, error classes
"""
from __future__ import annotations

import json
import os
import tempfile
import time

import pytest

from app.engine.history import ExecutionHistory, ExecutionRecord
from app.engine.job import Job, JobState
from app.engine.retry import (
    ERROR_PERMANENT,
    ERROR_TRANSIENT,
    ERROR_VERIFICATION,
    RetryPolicy,
    classify_error,
)
from app.engine.verifier import VerificationResult, Verifier


# --- ExecutionRecord tests ---

class TestExecutionRecord:
    def test_create_from_job(self):
        job = Job(
            prompt_id="test-123",
            workflow_id="txt2img",
            version="1.0.0",
            capability="image.generate",
            state=JobState.SUCCESS,
            output_assets=["asset-1"],
        )
        rec = ExecutionRecord.from_job(job, params={"prompt": "cat"}, duration=1.5)
        assert rec.prompt_id == "test-123"
        assert rec.capability == "image.generate"
        assert rec.state == "SUCCESS"
        assert rec.duration == 1.5
        assert rec.params == {"prompt": "cat"}
        assert rec.attempt == 1

    def test_create_from_failed_job(self):
        job = Job(
            prompt_id="fail-1",
            workflow_id="txt2img",
            version="1.0.0",
            capability="image.generate",
            state=JobState.FAILED,
            error="timeout",
            error_class="transient",
        )
        rec = ExecutionRecord.from_job(job, error_class="transient", attempt=2)
        assert rec.state == "FAILED"
        assert rec.error_class == "transient"
        assert rec.attempt == 2

    def test_serialization_roundtrip(self):
        rec = ExecutionRecord(
            prompt_id="p1",
            capability="image.generate",
            params={"prompt": "test"},
            workflow_id="txt2img",
            workflow_version="1.0.0",
            state="SUCCESS",
            duration=2.0,
            attempt=1,
            output_assets=["a1"],
        )
        d = rec.to_dict()
        rec2 = ExecutionRecord.from_dict(d)
        assert rec2.prompt_id == "p1"
        assert rec2.capability == "image.generate"
        assert rec2.state == "SUCCESS"
        assert rec2.duration == 2.0

    def test_to_dict_contains_all_fields(self):
        rec = ExecutionRecord(prompt_id="p1", capability="image.generate")
        d = rec.to_dict()
        assert "prompt_id" in d
        assert "capability" in d
        assert "params" in d
        assert "state" in d
        assert "duration" in d
        assert "attempt" in d
        assert "timestamp" in d


# --- ExecutionHistory tests ---

class TestExecutionHistory:
    def test_record_and_retrieve(self):
        history = ExecutionHistory()
        rec = ExecutionRecord(prompt_id="p1", capability="image.generate", state="SUCCESS")
        history.record(rec)
        assert history.count() == 1
        assert history.get_by_prompt_id("p1") is not None

    def test_get_attempts_filter(self):
        history = ExecutionHistory()
        history.record(ExecutionRecord(prompt_id="p1", capability="image.generate", state="SUCCESS"))
        history.record(ExecutionRecord(prompt_id="p2", capability="video.generate", state="FAILED"))
        history.record(ExecutionRecord(prompt_id="p3", capability="image.generate", state="FAILED"))
        
        img_attempts = history.get_attempts(capability="image.generate")
        assert len(img_attempts) == 2
        
        vid_attempts = history.get_attempts(capability="video.generate")
        assert len(vid_attempts) == 1

    def test_get_recent(self):
        history = ExecutionHistory()
        for i in range(5):
            history.record(ExecutionRecord(prompt_id=f"p{i}", capability="image.generate"))
        recent = history.get_recent(n=3)
        assert len(recent) == 3
        assert recent[0].prompt_id == "p2"

    def test_success_rate(self):
        history = ExecutionHistory()
        history.record(ExecutionRecord(prompt_id="p1", capability="image.generate", state="SUCCESS"))
        history.record(ExecutionRecord(prompt_id="p2", capability="image.generate", state="SUCCESS"))
        history.record(ExecutionRecord(prompt_id="p3", capability="image.generate", state="FAILED"))
        assert history.success_rate("image.generate") == pytest.approx(2 / 3)

    def test_success_rate_empty(self):
        history = ExecutionHistory()
        assert history.success_rate() == 0.0

    def test_avg_duration(self):
        history = ExecutionHistory()
        history.record(ExecutionRecord(prompt_id="p1", capability="image.generate", state="SUCCESS", duration=1.0))
        history.record(ExecutionRecord(prompt_id="p2", capability="image.generate", state="SUCCESS", duration=3.0))
        history.record(ExecutionRecord(prompt_id="p3", capability="image.generate", state="FAILED", duration=5.0))
        assert history.avg_duration("image.generate") == pytest.approx(2.0)

    def test_get_successful_and_failed(self):
        history = ExecutionHistory()
        history.record(ExecutionRecord(prompt_id="p1", capability="image.generate", state="SUCCESS"))
        history.record(ExecutionRecord(prompt_id="p2", capability="image.generate", state="FAILED"))
        assert len(history.get_successful("image.generate")) == 1
        assert len(history.get_failed("image.generate")) == 1

    def test_clear(self):
        history = ExecutionHistory()
        history.record(ExecutionRecord(prompt_id="p1", capability="image.generate"))
        history.clear()
        assert history.count() == 0

    def test_jsonl_persistence(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            # Записываем
            history1 = ExecutionHistory(persist_path=path)
            history1.record(ExecutionRecord(prompt_id="p1", capability="image.generate", state="SUCCESS"))
            history1.record(ExecutionRecord(prompt_id="p2", capability="video.generate", state="FAILED"))
            
            # Загружаем
            history2 = ExecutionHistory(persist_path=path)
            assert history2.count() == 2
            assert history2.get_by_prompt_id("p1") is not None
            assert history2.get_by_prompt_id("p2") is not None
        finally:
            os.unlink(path)

    def test_jsonl_append(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            history1 = ExecutionHistory(persist_path=path)
            history1.record(ExecutionRecord(prompt_id="p1", capability="image.generate"))
            
            history2 = ExecutionHistory(persist_path=path)
            history2.record(ExecutionRecord(prompt_id="p2", capability="image.generate"))
            
            assert history2.count() == 2
        finally:
            os.unlink(path)


# --- RetryPolicy tests ---

class TestRetryPolicy:
    def test_accept_on_success(self):
        policy = RetryPolicy(max_attempts=3)
        decision = policy.decide(state="SUCCESS", attempt=1)
        assert decision.action == "accept"

    def test_failed_on_cancelled(self):
        policy = RetryPolicy(max_attempts=3)
        decision = policy.decide(state="CANCELLED", attempt=1)
        assert decision.action == "failed"

    def test_retry_on_transient_error(self):
        policy = RetryPolicy(max_attempts=3)
        decision = policy.decide(state="FAILED", attempt=1, error_class="transient")
        assert decision.action == "retry"
        assert decision.delay > 0

    def test_retry_on_verification_error(self):
        policy = RetryPolicy(max_attempts=3)
        decision = policy.decide(state="FAILED", attempt=1, error_class="verification")
        assert decision.action == "retry"

    def test_failed_on_permanent_error(self):
        policy = RetryPolicy(max_attempts=3)
        decision = policy.decide(state="FAILED", attempt=1, error_class="permanent")
        assert decision.action == "failed"

    def test_failed_on_max_attempts(self):
        policy = RetryPolicy(max_attempts=3)
        decision = policy.decide(state="FAILED", attempt=3, error_class="transient")
        assert decision.action == "failed"
        assert "max attempts" in decision.reason

    def test_backoff_exponential(self):
        policy = RetryPolicy(max_attempts=5, backoff_base=1.0)
        d1 = policy.decide(state="FAILED", attempt=1, error_class="transient")
        d2 = policy.decide(state="FAILED", attempt=2, error_class="transient")
        d3 = policy.decide(state="FAILED", attempt=3, error_class="transient")
        assert d1.delay == 1.0
        assert d2.delay == 2.0
        assert d3.delay == 4.0

    def test_backoff_max_cap(self):
        policy = RetryPolicy(max_attempts=10, backoff_base=1.0, backoff_max=5.0)
        decision = policy.decide(state="FAILED", attempt=10, error_class="transient")
        assert decision.delay <= 5.0


# --- classify_error tests ---

class TestClassifyError:
    def test_transient_timeout(self):
        assert classify_error("connection timeout") == ERROR_TRANSIENT

    def test_transient_connection(self):
        assert classify_error("connection refused") == ERROR_TRANSIENT

    def test_transient_websocket(self):
        assert classify_error("websocket disconnected") == ERROR_TRANSIENT

    def test_permanent_not_found(self):
        assert classify_error("model not found") == ERROR_PERMANENT

    def test_permanent_invalid(self):
        assert classify_error("invalid workflow") == ERROR_PERMANENT

    def test_verification_signature(self):
        assert classify_error("несовпадение сигнатуры") == ERROR_VERIFICATION

    def test_verification_empty(self):
        assert classify_error("пустой файл") == ERROR_VERIFICATION

    def test_unknown_defaults_to_transient(self):
        assert classify_error("some random error") == ERROR_TRANSIENT


# --- VerificationResult tests ---

class TestVerificationResult:
    def test_ok_result(self):
        result = VerificationResult(ok=True)
        assert result.ok is True
        assert result.error_message is None

    def test_error_result(self):
        result = VerificationResult(
            ok=False,
            error_class="verification",
        )
        assert result.ok is False
        assert result.error_class == "verification"
