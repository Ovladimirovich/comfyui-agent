"""Research contracts — interfaces for future research.

Только контракты. Никакой реализации.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.knowledge.gaps import GapType
from app.knowledge.models import EvidenceTrustLevel, KnowledgeClaim, KnowledgeEvidence


@dataclass(frozen=True)
class ResearchRequest:
    """Запрос на research. Формируется Knowledge Core при gap detection."""

    claim: KnowledgeClaim
    gap_type: GapType
    required_evidence: tuple[EvidenceTrustLevel, ...]
    preferred_sources: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "claim": self.claim.to_dict(),
            "gap_type": self.gap_type.value,
            "required_evidence": [e.value for e in self.required_evidence],
            "preferred_sources": list(self.preferred_sources),
        }


@dataclass(frozen=True)
class ResearchResult:
    """Результат research. Возвращается research provider."""

    evidence: tuple[KnowledgeEvidence, ...] = ()
    unresolved: tuple[str, ...] = ()
    sources_checked: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "evidence": [e.to_dict() for e in self.evidence],
            "unresolved": list(self.unresolved),
            "sources_checked": list(self.sources_checked),
        }
