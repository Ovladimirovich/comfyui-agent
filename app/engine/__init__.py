"""Engine package (M4+M13+M14+M18): ExecutionPlan, Job, WorkflowEngine, WebSocket, Verifier, History, Retry, SemanticVerification, Chain."""
from __future__ import annotations

from .chain import ChainContext, ChainResult, ChainState, ExecutionChain
from .engine import WorkflowEngine
from .history import ExecutionHistory, ExecutionRecord
from .job import Job, JobState
from .plan import ExecutionPlan
from .retry import RetryPolicy, RetryDecision, classify_error
from .semantic_verifier import SemanticVerificationResult, SemanticVerifier
from .verifier import VerificationError, VerificationResult, Verifier
from .websocket import ComfyUIWebSocket, ComfyUIWebSocketError

__all__ = [
    "WorkflowEngine",
    "ExecutionPlan",
    "Job",
    "JobState",
    "Verifier",
    "VerificationError",
    "VerificationResult",
    "ComfyUIWebSocket",
    "ComfyUIWebSocketError",
    # M13
    "ExecutionHistory",
    "ExecutionRecord",
    "RetryPolicy",
    "RetryDecision",
    "classify_error",
    # M14
    "SemanticVerifier",
    "SemanticVerificationResult",
    # M18
    "ExecutionChain",
    "ChainContext",
    "ChainResult",
    "ChainState",
]
