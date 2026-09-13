"""KnowledgeCore — central query interface for knowledge.

Orchestrates NodeSchemaStore, CandidateGenerator, GapDetector.
Read-only queries. No modification of existing registries.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from app.knowledge.candidates import CapabilityCandidate, CandidateGenerator
from app.knowledge.gaps import GapNature, GapType, KnowledgeGap
from app.knowledge.models import ClaimStatus, KnowledgeClaim, KnowledgeEvidence, EvidenceSource, EvidenceTrustLevel
from app.knowledge.node_schema import NodeSchema, NodeSchemaStore, node_schema_from_object_info
from app.knowledge.research import ResearchRequest
from app.knowledge.runtime_validator import RuntimeValidator, ValidationResult
from app.knowledge.claims_persistence import ClaimsPersistence


class Readiness(str, Enum):
    """Итоговая оценка readiness для задачи."""

    EXECUTABLE = "EXECUTABLE"
    CANDIDATE_ONLY = "CANDIDATE_ONLY"
    GAP = "GAP"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class KnowledgeQuery:
    """Запрос к Knowledge Core. Requirements уже сформированы Intent/Task layer."""

    required_operation: str
    required_media_input: tuple[str, ...]
    required_media_output: str
    input_cardinality: int = 1
    task_description: str = ""


@dataclass
class KnowledgeResponse:
    """Ответ Knowledge Core на запрос."""

    known_capabilities: list[str] = field(default_factory=list)
    candidate_nodes: list[CapabilityCandidate] = field(default_factory=list)
    claims: list[KnowledgeClaim] = field(default_factory=list)
    gaps: list[KnowledgeGap] = field(default_factory=list)
    readiness: Readiness = Readiness.UNKNOWN
    research_requests: list[ResearchRequest] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "known_capabilities": self.known_capabilities,
            "candidate_nodes": [c.to_dict() for c in self.candidate_nodes],
            "claims": [c.to_dict() for c in self.claims],
            "gaps": [g.to_dict() for g in self.gaps],
            "readiness": self.readiness.value,
            "research_requests": [r.to_dict() for r in self.research_requests],
        }


class KnowledgeCore:
    """Central knowledge store. Read-only queries. No planner modification.

    Usage:
        core = KnowledgeCore()
        core.refresh(comfy_client)  # snapshot /object_info
        response = core.query(task_requirements)

    S3: optional EvidenceStore для persistence research results:
        store = EvidenceStore()
        core = KnowledgeCore(evidence_store=store)
        result = provider.research(request)
        store.ingest(result)
        core.apply_research_results()  # update claims
        response = core.query(query)   # now sees SUPPORTED claims
    """

    def __init__(
        self,
        capability_registry=None,
        workflow_registry=None,
        data_dir: str | None = None,
        evidence_store=None,  # S3: optional EvidenceStore
        runtime_validator=None,  # S4: optional RuntimeValidator
        claims_persistence=None,  # S4: optional ClaimsPersistence
    ) -> None:
        self._capability_registry = capability_registry
        self._workflow_registry = workflow_registry
        self._store = NodeSchemaStore(data_dir=data_dir)
        self._generator = CandidateGenerator()
        self._schemas: dict[str, NodeSchema] = {}
        self._candidates: dict[str, list[CapabilityCandidate]] = {}
        self._claims: list[KnowledgeClaim] = []
        self._evidence_store = evidence_store
        self._runtime_validator = runtime_validator
        self._claims_persistence = claims_persistence or ClaimsPersistence(data_dir=data_dir or "app/data/knowledge")
        self._validated_nodes: dict[str, bool] = {}
        
        # Загружаем сохранённые данные
        self._load_persistence()  # node_class -> validated_success
        
        # Авто-загрузка схем из persistent store
        self.load_from_store()

    def refresh(self, comfy_client) -> dict[str, list[str]]:
        """Refresh from live ComfyUI. Returns diff: {added, removed, changed}."""
        old_schemas = dict(self._schemas)

        object_info = comfy_client.get_object_info()
        new_schemas: dict[str, NodeSchema] = {}
        for class_type, node_data in object_info.items():
            if isinstance(node_data, dict) and "input" in node_data:
                new_schemas[class_type] = node_schema_from_object_info(class_type, node_data)

        diff = self._store.diff(old_schemas, new_schemas)
        self._schemas = new_schemas
        self._store.save_snapshot(self._schemas)

        # Regenerate candidates
        self._candidates.clear()
        for class_type, schema in self._schemas.items():
            candidates = self._generator.generate(schema)
            if candidates:
                self._candidates[class_type] = candidates

        # Regenerate claims from all candidates
        self._claims.clear()
        for class_type, candidates in self._candidates.items():
            for cand in candidates:
                self._claims.extend(cand.claims)

        return diff

    def load_from_store(self) -> None:
        """Load schemas from persistent store (without live ComfyUI)."""
        self._schemas = self._store.load_current()
        self._candidates.clear()
        for class_type, schema in self._schemas.items():
            candidates = self._generator.generate(schema)
            if candidates:
                self._candidates[class_type] = candidates
        self._claims.clear()
        for candidates in self._candidates.values():
            for cand in candidates:
                self._claims.extend(cand.claims)

    def query(self, query: KnowledgeQuery) -> KnowledgeResponse:
        """Answer a knowledge query based on current state."""
        response = KnowledgeResponse()

        # Known capabilities from CapabilityRegistry (read-only)
        if self._capability_registry is not None:
            for cap in self._capability_registry.all():
                if self._capability_matches(cap, query):
                    response.known_capabilities.append(cap.id)

        # Candidates matching the query
        for class_type, candidates in self._candidates.items():
            for cand in candidates:
                if self._candidate_matches(cand, query):
                    response.candidate_nodes.append(cand)

        # All relevant claims
        for claim in self._claims:
            if self._claim_matches(claim, query):
                response.claims.append(claim)

        # Detect gaps
        response.gaps = self._detect_gaps(query, response)

        # Generate research requests for KNOWLEDGE gaps
        for gap in response.gaps:
            if gap.gap_nature == GapNature.KNOWLEDGE:
                # Generate ResearchRequest for each relevant claim
                claims_for_gap = [c for c in response.claims
                    if c.status in (ClaimStatus.UNKNOWN, ClaimStatus.INFERENCE)]
                for claim in claims_for_gap:
                    response.research_requests.append(ResearchRequest(
                        claim=claim,
                        gap_type=gap.gap_type,
                        required_evidence=(
                            EvidenceTrustLevel.DECLARED_PURPOSE,
                            EvidenceTrustLevel.OBSERVED_BEHAVIOR,
                        ),
                    ))
                # If no claims exist but gap is UNKNOWN_CAPABILITY, create a synthetic request
                if not claims_for_gap and gap.gap_type == GapType.UNKNOWN_CAPABILITY:
                    synthetic_claim = KnowledgeClaim(
                        claim=f"Unknown capability: {query.required_operation}",
                        subject="unknown",
                        predicate="may_implement",
                        object=query.required_operation,
                        status=ClaimStatus.UNKNOWN,
                    )
                    response.research_requests.append(ResearchRequest(
                        claim=synthetic_claim,
                        gap_type=gap.gap_type,
                        required_evidence=(
                            EvidenceTrustLevel.DECLARED_PURPOSE,
                            EvidenceTrustLevel.OBSERVED_BEHAVIOR,
                        ),
                    ))

        # Determine readiness
        response.readiness = self._assess_readiness(query, response)

        return response

    def apply_research_results(self) -> int:
        """Применить результаты research из EvidenceStore к claims.

        Returns count of upgraded claims.
        """
        if self._evidence_store is None:
            return 0

        upgraded = 0
        new_claims = []
        for claim in self._claims:
            updated = self._evidence_store.merge_into_claims([claim], claim.subject)
            if updated and updated[0].status != claim.status:
                upgraded += 1
            new_claims.extend(updated if updated else [claim])

        # Deduplicate
        seen = set()
        unique_claims = []
        for c in new_claims:
            key = (c.subject, c.predicate, c.object)
            if key not in seen:
                seen.add(key)
                unique_claims.append(c)
        self._claims = unique_claims
        return upgraded

    def validate_runtime(self, node_class: str, workflow: dict) -> dict:
        """Runtime validation S4: execute node on live ComfyUI.

        Args:
            node_class: Name of the node to validate
            workflow: Workflow dict containing the node

        Returns:
            dict with validation_result, execution_time_ms, error_message
        """
        if self._runtime_validator is None:
            return {"error": "RuntimeValidator not configured"}

        evidence = self._runtime_validator.validate_node(node_class, workflow)

        # Update internal state
        self._validated_nodes[node_class] = evidence.validation_result == ValidationResult.SUCCESS
        
        # Save to persistence
        self._claims_persistence.add_validated_node(node_class, evidence.validation_result == ValidationResult.SUCCESS)

        # Upgrade claims if successful
        if evidence.validation_result == ValidationResult.SUCCESS:
            # Merge with existing claims
            self._claims = self._runtime_validator.merge_runtime_evidence(
                evidence, self._claims
            )
            
            # Save confirmed claims to persistence
            for claim in self._claims:
                if claim.status == ClaimStatus.CONFIRMED:
                    self._claims_persistence.add_confirmed_claim(claim.to_dict())

        return {
            "node_class": node_class,
            "validation_result": evidence.validation_result.value,
            "execution_time_ms": round(evidence.execution_time_ms, 2),
            "error_message": evidence.error_message,
            "output_summary": evidence.output_summary,
        }

    def _load_persistence(self):
        """Загружает сохранённые данные из persistence."""
        if self._claims_persistence:
            self._validated_nodes = self._claims_persistence.get_validated_nodes()
            # Load confirmed claims
            for claim_data in self._claims_persistence.get_confirmed_claims():
                from app.knowledge.models import KnowledgeClaim
                claim = KnowledgeClaim(
                    claim=claim_data["claim"],
                    subject=claim_data["subject"],
                    predicate=claim_data["predicate"],
                    object=claim_data.get("object"),
                    status=ClaimStatus(claim_data.get("status", "UNKNOWN")),
                    evidence=[],
                    last_verified=claim_data.get("last_verified", 0.0),
                )
                self._claims.append(claim)

    def save_state(self):
        """Сохраняет текущее состояние в persistence."""
        if self._claims_persistence:
            for node_class, success in self._validated_nodes.items():
                self._claims_persistence.add_validated_node(node_class, success)
            for claim in self._claims:
                if claim.status == ClaimStatus.CONFIRMED:
                    self._claims_persistence.add_confirmed_claim(claim.to_dict())

    def get_confirmed_claims(self) -> list:
        """Return claims with CONFIRMED status."""
        return [c for c in self._claims if c.status == ClaimStatus.CONFIRMED]

    def get_validated_nodes(self) -> dict[str, bool]:
        """Return dict of validated nodes."""
        return dict(self._validated_nodes)

    def get_validated_for_capability(self, capability: str) -> dict[str, bool]:
        """Return validated nodes relevant to a capability.
        
        Returns dict of {node_class: is_validated} for nodes used in workflows
        matching the given capability.
        """
        if not self._validated_nodes:
            return {}
        
        # Get workflows for this capability
        workflows = []
        if self._workflow_registry is not None:
            workflows = self._workflow_registry.by_capability(capability)
        
        if not workflows:
            return dict(self._validated_nodes)
        
        # Filter to nodes used in these workflows
        validated_node_types = set()
        for wf in workflows:
            wf_data = wf.workflow if hasattr(wf, 'workflow') else {}
            for node in wf_data.get("nodes", []):
                node_type = node.get("type")
                if node_type and node_type in self._validated_nodes:
                    validated_node_types.add(node_type)
        
        return {k: v for k, v in self._validated_nodes.items() if k in validated_node_types}

    def get_schemas(self) -> dict[str, NodeSchema]:
        """Return all current schemas (read-only)."""
        return dict(self._schemas)

    def get_candidates(self) -> dict[str, list[CapabilityCandidate]]:
        """Return all current candidates (read-only)."""
        return dict(self._candidates)

    def get_claims(self) -> list[KnowledgeClaim]:
        """Return all current claims (read-only)."""
        return list(self._claims)

    def diff_snapshots(self) -> dict[str, list[str]]:
        """Diff current vs previous snapshot."""
        return self._store.diff(
            self._store.load_previous(),
            self._store.load_current(),
        )

    # --- Private helpers ---

    def _capability_matches(self, cap, query: KnowledgeQuery) -> bool:
        """Check if a builtin capability matches the query."""
        if cap.media_output and cap.media_output != query.required_media_output:
            return False
        if query.required_media_input:
            if not set(query.required_media_input).issubset(set(cap.media_input)):
                return False
        return True

    def _candidate_matches(self, cand: CapabilityCandidate, query: KnowledgeQuery) -> bool:
        """Check if a candidate matches the query."""
        if cand.capability != query.required_operation:
            return False
        # Check cardinality if usage has it
        if query.input_cardinality > 0 and cand.usage.cardinality > 0:
            if cand.usage.cardinality != query.input_cardinality:
                return False
        return True

    def _claim_matches(self, claim: KnowledgeClaim, query: KnowledgeQuery) -> bool:
        """Check if a claim is relevant to the query."""
        if claim.object and query.required_operation in claim.object:
            return True
        if query.required_operation in claim.predicate:
            return True
        return False

    def _detect_gaps(
        self, query: KnowledgeQuery, response: KnowledgeResponse
    ) -> list[KnowledgeGap]:
        """Detect gaps based on query and current response."""
        gaps: list[KnowledgeGap] = []

        # Check if operation is completely unknown
        has_candidates = len(response.candidate_nodes) > 0
        has_builtin = len(response.known_capabilities) > 0

        if not has_builtin and not has_candidates:
            gaps.append(KnowledgeGap(
                needed=f"capability or candidate for operation={query.required_operation}",
                gap_type=GapType.UNKNOWN_CAPABILITY,
                gap_nature=GapNature.KNOWLEDGE,
                research_sources=("runtime:/object_info", "local:/custom_nodes"),
                priority="HIGH",
            ))
            return gaps

        # Check if candidates exist but need more evidence
        for cand in response.candidate_nodes:
            if cand.status == ClaimStatus.INFERENCE:
                gaps.append(KnowledgeGap(
                    needed=f"evidence confirming {cand.node_class} -> {cand.capability}",
                    gap_type=GapType.INSUFFICIENT_EVIDENCE,
                    gap_nature=GapNature.KNOWLEDGE,
                    research_sources=(
                        "local:/README.md",
                        "local:/custom_nodes/*/__init__.py",
                    ),
                    priority="MEDIUM",
                ))

        # Check workflow availability (read-only from WorkflowRegistry)
        if self._workflow_registry is not None and has_builtin:
            workflows = self._workflow_registry.by_capability(query.required_operation)
            if not workflows:
                gaps.append(KnowledgeGap(
                    needed=f"workflow for capability={query.required_operation}",
                    gap_type=GapType.NO_WORKFLOW,
                    gap_nature=GapNature.EXECUTION,
                    priority="MEDIUM",
                ))

        # Check candidate-compatible workflow availability
        if has_candidates and not has_builtin:
            gaps.append(KnowledgeGap(
                needed=f"workflow for candidates of {query.required_operation}",
                gap_type=GapType.CANDIDATE_NO_WORKFLOW,
                gap_nature=GapNature.EXECUTION,
                priority="MEDIUM",
            ))

        # Also report candidate-specific gap when builtin exists but candidates also exist
        if has_candidates and has_builtin and self._workflow_registry is None:
            gaps.append(KnowledgeGap(
                needed=f"workflow validation for candidates of {query.required_operation}",
                gap_type=GapType.CANDIDATE_NO_WORKFLOW,
                gap_nature=GapNature.EXECUTION,
                priority="LOW",
            ))

        return gaps

    def _assess_readiness(
        self, query: KnowledgeQuery, response: KnowledgeResponse
    ) -> Readiness:
        """Assess overall readiness."""
        has_candidates = bool(response.candidate_nodes)
        has_known = bool(response.known_capabilities)

        if not has_candidates and not has_known:
            # No candidates, no builtins → UNKNOWN
            return Readiness.UNKNOWN

        if response.gaps:
            has_knowledge_gaps = any(
                g.gap_nature == GapNature.KNOWLEDGE
                for g in response.gaps
            )
            if has_knowledge_gaps:
                return Readiness.GAP
            return Readiness.CANDIDATE_ONLY

        if has_candidates and not has_known:
            return Readiness.CANDIDATE_ONLY

        return Readiness.EXECUTABLE
