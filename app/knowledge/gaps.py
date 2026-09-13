"""KnowledgeGap — typed gaps between what is needed and what is known.

GapType определяет ЧТО не хватает.
GapNature определяет ПРИРОДУ gap (knowledge / execution / compatibility).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class GapType(str, Enum):
    """Тип gap. Определяет что именно не хватает."""

    UNKNOWN_CAPABILITY = "unknown_capability"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CONFLICTING_KNOWLEDGE = "conflicting_knowledge"
    STALE_KNOWLEDGE = "stale_knowledge"
    NO_WORKFLOW = "no_workflow"
    CANDIDATE_NO_WORKFLOW = "candidate_no_workflow"
    WORKFLOW_NODE_ABSENT = "workflow_node_absent"


class GapNature(str, Enum):
    """Природа gap. Определяет, что делать."""

    KNOWLEDGE = "knowledge"
    EXECUTION = "execution"
    COMPATIBILITY = "compatibility"


@dataclass
class KnowledgeGap:
    """Чего не хватает."""

    needed: str
    gap_type: GapType
    gap_nature: GapNature
    research_sources: tuple[str, ...] = ()
    priority: str = "MEDIUM"

    def to_dict(self) -> dict:
        return {
            "needed": self.needed,
            "gap_type": self.gap_type.value,
            "gap_nature": self.gap_nature.value,
            "research_sources": list(self.research_sources),
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: dict) -> KnowledgeGap:
        return cls(
            needed=data["needed"],
            gap_type=GapType(data["gap_type"]),
            gap_nature=GapNature(data["gap_nature"]),
            research_sources=tuple(data.get("research_sources", [])),
            priority=data.get("priority", "MEDIUM"),
        )
