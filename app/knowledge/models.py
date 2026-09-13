"""Domain models: KnowledgeEvidence, KnowledgeClaim, ClaimStatus.

Evidence хранит факт + его источник + тип.
Claim связывает утверждение с evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class EvidenceSource(str, Enum):
    """Откуда пришло доказательство."""

    RUNTIME = "runtime"
    LOCAL_SOURCE = "local_source"
    PROJECT_METADATA = "project_metadata"
    EXECUTION = "execution"


class EvidenceTrustLevel(str, Enum):
    """Что подтверждает этот тип evidence."""

    SCHEMA = "schema"
    DECLARED_PURPOSE = "declared"
    OBSERVED_BEHAVIOR = "observed"
    OBSERVED_SOURCE_STRUCTURE = "observed_source"


class ClaimStatus(str, Enum):
    """Статус знания. Четыре уровня, без числовых confidence."""

    UNKNOWN = "UNKNOWN"
    INFERENCE = "INFERENCE"
    SUPPORTED = "SUPPORTED"
    CONFIRMED = "CONFIRMED"


@dataclass(frozen=True)
class KnowledgeEvidence:
    """Одно доказательство. Каждое evidence знает, ЧТО оно подтверждает."""

    source: str
    source_type: EvidenceSource
    trust_level: EvidenceTrustLevel
    timestamp: float
    claim: str

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "source_type": self.source_type.value,
            "trust_level": self.trust_level.value,
            "timestamp": self.timestamp,
            "claim": self.claim,
        }

    @classmethod
    def from_dict(cls, data: dict) -> KnowledgeEvidence:
        return cls(
            source=data["source"],
            source_type=EvidenceSource(data["source_type"]),
            trust_level=EvidenceTrustLevel(data["trust_level"]),
            timestamp=data["timestamp"],
            claim=data["claim"],
        )


@dataclass
class KnowledgeClaim:
    """Семантическое утверждение о мире. Центральная единица Knowledge."""

    claim: str
    subject: str
    predicate: str
    object: Optional[str] = None
    status: ClaimStatus = ClaimStatus.UNKNOWN
    evidence: list[KnowledgeEvidence] = field(default_factory=list)
    last_verified: float = 0.0

    def to_dict(self) -> dict:
        return {
            "claim": self.claim,
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.object,
            "status": self.status.value,
            "evidence": [e.to_dict() for e in self.evidence],
            "last_verified": self.last_verified,
        }

    @classmethod
    def from_dict(cls, data: dict) -> KnowledgeClaim:
        evidence = [KnowledgeEvidence.from_dict(e) for e in data.get("evidence", [])]
        return cls(
            claim=data["claim"],
            subject=data["subject"],
            predicate=data["predicate"],
            object=data.get("object"),
            status=ClaimStatus(data.get("status", "UNKNOWN")),
            evidence=evidence,
            last_verified=data.get("last_verified", 0.0),
        )
