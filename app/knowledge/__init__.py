"""Knowledge Core — изолированная прослойка между Task Requirements и Planner.

Хранит NodeSchema snapshots (текущее runtime состояние),
KnowledgeClaims + Evidence (историческое semantic knowledge),
CapabilityCandidates (гипотезы использования nodes),
NodeDocEntry (документация нод из markdown).

НЕ планирует. НЕ выполняет. НЕ исследует.
"""
from app.knowledge.candidates import (
    CapabilityCandidate,
    CandidateGenerator,
    InputMapping,
    UsageHypothesis,
)
from app.knowledge.core import KnowledgeCore, KnowledgeQuery, KnowledgeResponse, Readiness
from app.knowledge.evidence_store import EvidenceStore
from app.knowledge.gaps import GapNature, GapType, KnowledgeGap
from app.knowledge.local_research import LocalResearchProvider, ResearchSource
from app.knowledge.models import (
    ClaimStatus,
    KnowledgeClaim,
    KnowledgeEvidence,
    EvidenceSource,
    EvidenceTrustLevel,
)
from app.knowledge.node_doc import NodeDocEntry, NodeDocStore
from app.knowledge.node_doc_parser import NodeDocParser, format_node_explanation
from app.knowledge.node_schema import FieldSpec, NodeSchema, NodeSchemaStore
from app.knowledge.research import ResearchRequest, ResearchResult
from app.knowledge.runtime_validator import RuntimeValidator, ValidationResult, RuntimeEvidence
from app.knowledge.claims_persistence import ClaimsPersistence

__all__ = [
    "NodeSchema",
    "FieldSpec",
    "NodeSchemaStore",
    "KnowledgeEvidence",
    "EvidenceSource",
    "EvidenceTrustLevel",
    "KnowledgeClaim",
    "ClaimStatus",
    "CapabilityCandidate",
    "CandidateGenerator",
    "InputMapping",
    "UsageHypothesis",
    "KnowledgeGap",
    "GapType",
    "GapNature",
    "KnowledgeQuery",
    "KnowledgeResponse",
    "Readiness",
    "KnowledgeCore",
    "ResearchRequest",
    "ResearchResult",
    "LocalResearchProvider",
    "ResearchSource",
    "EvidenceStore",
    "NodeDocEntry",
    "NodeDocStore",
    "NodeDocParser",
    "format_node_explanation",
    "RuntimeValidator",
    "ValidationResult",
    "RuntimeEvidence",
    "ClaimsPersistence",
]
