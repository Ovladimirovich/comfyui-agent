"""
Runtime Validator — валидация кандидатов через реальное выполнение.

Upgrade claims: INFERENCE → SUPPORTED → CONFIRMED
CONFIRMED = executed successfully on live ComfyUI.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from app.knowledge.models import (
    ClaimStatus,
    EvidenceSource,
    EvidenceTrustLevel,
    KnowledgeClaim,
    KnowledgeEvidence,
)


class ValidationResult(str, Enum):
    """Итог runtime валидации."""
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    ERROR = "ERROR"
    TIMEOUT = "TIMEOUT"


@dataclass(frozen=True)
class RuntimeEvidence:
    """Результат runtime валидации ноды."""
    node_class: str
    validation_result: ValidationResult
    execution_time_ms: float
    error_message: str = ""
    output_summary: str = ""
    validated_at: float = field(default_factory=time.time)


@dataclass
class RuntimeValidator:
    """Валидатор кандидатов через реальное выполнение на ComfyUI."""

    comfy_client: Optional[object] = None  # ComfyClient instance
    max_wait_seconds: int = 300
    timeout_seconds: int = 120

    def __init__(self, comfy_client=None, max_wait_seconds=300, timeout_seconds=120):
        self.comfy_client = comfy_client
        self.max_wait_seconds = max_wait_seconds
        self.timeout_seconds = timeout_seconds

    def validate_node(self, node_class: str, workflow: dict) -> RuntimeEvidence:
        """Выполняет workflow с нодой и возвращает результат."""
        if self.comfy_client is None:
            return RuntimeEvidence(
                node_class=node_class,
                validation_result=ValidationResult.ERROR,
                execution_time_ms=0,
                error_message="No ComfyClient provided",
            )

        start_time = time.time()
        try:
            # Queue the workflow
            prompt = self.comfy_client.workflow_to_prompt(workflow) if hasattr(self.comfy_client, 'workflow_to_prompt') else workflow
            # Transport (S6): предпочитаем публичный API ComfyClient (queue_prompt),
            # fallback на legacy queue() для моков/старых клиентов.
            queue_fn = getattr(self.comfy_client, "queue_prompt", None)
            if queue_fn is None:
                queue_fn = getattr(self.comfy_client, "queue", None)
            if queue_fn is None:
                raise AttributeError(
                    "ComfyClient: нет queue_prompt()/queue() для постановки workflow в очередь"
                )
            result = queue_fn(prompt)
            prompt_id = result.get("prompt_id")
            if not prompt_id:
                return RuntimeEvidence(
                    node_class=node_class,
                    validation_result=ValidationResult.ERROR,
                    execution_time_ms=(time.time() - start_time) * 1000,
                    error_message=f"Failed to queue: {result}",
                )

            # Wait for completion
            elapsed = 0
            while elapsed < self.max_wait_seconds:
                # Transport (S6): предпочитаем get_history() (публичный API),
                # fallback на legacy history() для моков/старых клиентов.
                history_fn = getattr(self.comfy_client, "get_history", None)
                if history_fn is None:
                    history_fn = getattr(self.comfy_client, "history", None)
                if history_fn is None:
                    raise AttributeError(
                        "ComfyClient: нет get_history()/history() для опроса результата"
                    )
                history = history_fn(prompt_id)
                item = history.get(prompt_id)
                if item is not None:
                    execution_time = (time.time() - start_time) * 1000
                    outputs = item.get("outputs", {})
                    output_summary = self._summarize_outputs(outputs)
                    
                    # Check for errors
                    if item.get("status", {}).get("status_str") == "error":
                        error_msg = item.get("status", {}).get("messages", [])
                        return RuntimeEvidence(
                            node_class=node_class,
                            validation_result=ValidationResult.FAILURE,
                            execution_time_ms=execution_time,
                            error_message=str(error_msg),
                            output_summary=output_summary,
                        )
                    
                    return RuntimeEvidence(
                        node_class=node_class,
                        validation_result=ValidationResult.SUCCESS,
                        execution_time_ms=execution_time,
                        output_summary=output_summary,
                    )
                
                time.sleep(2)
                elapsed += 2

            return RuntimeEvidence(
                node_class=node_class,
                validation_result=ValidationResult.TIMEOUT,
                execution_time_ms=(time.time() - start_time) * 1000,
                error_message=f"Timeout after {self.max_wait_seconds}s",
            )

        except Exception as e:
            return RuntimeEvidence(
                node_class=node_class,
                validation_result=ValidationResult.ERROR,
                execution_time_ms=(time.time() - start_time) * 1000,
                error_message=str(e),
            )

    def _summarize_outputs(self, outputs: dict) -> str:
        """Суммирует выходы workflow."""
        parts = []
        for node_id, node_output in outputs.items():
            for key in ("images", "gifs", "videos", "audio"):
                if node_output.get(key):
                    parts.append(f"{key}: {len(node_output[key])}")
        return "; ".join(parts) if parts else "no standard outputs"

    def validate_candidate(self, candidate, workflow: dict) -> RuntimeEvidence:
        """Валидирует CapabilityCandidate."""
        return self.validate_node(candidate.node_class, workflow)

    def upgrade_claims(self, evidence: RuntimeEvidence) -> list[KnowledgeClaim]:
        """Обновляет claims на основе runtime evidence.
        
        Возвращает новый claim с CONFIRMED статусом.
        """
        if evidence.validation_result != ValidationResult.SUCCESS:
            return []

        evidence_record = KnowledgeEvidence(
            source=EvidenceSource.RUNTIME.value,
            source_type=EvidenceSource.RUNTIME,
            trust_level=EvidenceTrustLevel.OBSERVED_BEHAVIOR,
            timestamp=evidence.validated_at,
            claim=f"{evidence.node_class} executed successfully in {evidence.execution_time_ms:.0f}ms",
        )

        return [KnowledgeClaim(
            claim=f"{evidence.node_class} executed successfully",
            subject=evidence.node_class,
            predicate="validated_by_execution",
            object="true",
            status=ClaimStatus.CONFIRMED,
            evidence=[evidence_record],
        )]

    def merge_runtime_evidence(self, evidence: RuntimeEvidence, existing_claims: list) -> list:
        """Merge runtime evidence with existing claims.
        
        Args:
            evidence: Runtime validation result
            existing_claims: List of existing KnowledgeClaim objects
            
        Returns:
            Updated list of claims with merged evidence
        """
        if evidence.validation_result != ValidationResult.SUCCESS:
            return existing_claims

        # Create new evidence record
        new_evidence = KnowledgeEvidence(
            source=EvidenceSource.RUNTIME.value,
            source_type=EvidenceSource.RUNTIME,
            trust_level=EvidenceTrustLevel.OBSERVED_BEHAVIOR,
            timestamp=evidence.validated_at,
            claim=f"{evidence.node_class} executed successfully",
        )

        # Find and update matching claims
        updated_claims = []
        for claim in existing_claims:
            if claim.subject == evidence.node_class:
                # Add runtime evidence to existing claim
                updated_evidence = claim.evidence + [new_evidence]
                updated_claims.append(KnowledgeClaim(
                    claim=claim.claim,
                    subject=claim.subject,
                    predicate=claim.predicate,
                    object=claim.object,
                    status=ClaimStatus.CONFIRMED,  # Upgrade to CONFIRMED
                    evidence=updated_evidence,
                    last_verified=evidence.validated_at,
                ))
            else:
                updated_claims.append(claim)

        # If no matching claim found, create new one
        if not any(c.subject == evidence.node_class for c in updated_claims):
            updated_claims.append(KnowledgeClaim(
                claim=f"{evidence.node_class} executed successfully",
                subject=evidence.node_class,
                predicate="validated_by_execution",
                object="true",
                status=ClaimStatus.CONFIRMED,
                evidence=[new_evidence],
                last_verified=evidence.validated_at,
            ))

        return updated_claims
