"""EvidenceStore — persistencия результатов локального research.

Хранит ResearchResult в JSON. Поддерживает:
  - ingest(result) — сохранить результат
  - load() — загрузить все результаты
  - merge_into_claims(claims) — обновить статусы claims на основе evidence
  - get_evidence_for(subject) — получить все evidence для node

EvidenceStore НЕ модифицирует KnowledgeCore автоматически.
Обновление claims — явная операция.
"""
from __future__ import annotations

import json
import os
import time
from typing import Optional

from app.knowledge.models import (
    ClaimStatus,
    EvidenceSource,
    EvidenceTrustLevel,
    KnowledgeClaim,
    KnowledgeEvidence,
)
from app.knowledge.research import ResearchResult


class EvidenceStore:
    """JSON-based persistence для результатов local research."""

    def __init__(self, data_dir: Optional[str] = None) -> None:
        if data_dir is None:
            data_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "data", "knowledge_evidence"
            )
        self._data_dir = data_dir
        self._store_path = os.path.join(data_dir, "evidence_store.json")
        os.makedirs(data_dir, exist_ok=True)

    # --- Public API -------------------------------------------------------

    def ingest(self, result: ResearchResult) -> None:
        """Сохранить результат research в store."""
        from app.knowledge.models import EvidenceSource, EvidenceTrustLevel
        store = self._load()
        ts = time.time()

        for evidence in result.evidence:
            src_type = evidence.source_type
            trust = evidence.trust_level
            # Handle both enum and string values
            if isinstance(src_type, str):
                src_type = EvidenceSource(src_type)
            if isinstance(trust, str):
                trust = EvidenceTrustLevel(trust)
            store.append({
                "source": evidence.source,
                "source_type": src_type.value,
                "trust_level": trust.value,
                "timestamp": evidence.timestamp,
                "claim": evidence.claim,
                "ingested_at": ts,
            })

        self._save(store)

    def load(self) -> list[dict]:
        """Загрузить все сохранённые evidence records."""
        return self._load()

    def get_evidence_for(self, subject: str) -> list[KnowledgeEvidence]:
        """Получить все evidence, релевантные указанному subject."""
        records = self._load()
        evidence_list = []
        for rec in records:
            if subject.lower() in rec["claim"].lower():
                evidence_list.append(KnowledgeEvidence(
                    source=rec["source"],
                    source_type=EvidenceSource(rec["source_type"]),
                    trust_level=EvidenceTrustLevel(rec["trust_level"]),
                    timestamp=rec["timestamp"],
                    claim=rec["claim"],
                ))
        return evidence_list

    def merge_into_claims(
        self,
        claims: list[KnowledgeClaim],
        subject: str,
    ) -> list[KnowledgeClaim]:
        """Обновить статусы claims для subject на основе evidence из store.

        Логика:
          - INFERENCE + evidence[DECLARED_PURPOSE] → SUPPORTED
          - INFERENCE + evidence[OBSERVED_SOURCE_STRUCTURE] → SUPPORTED
          - INFERENCE + evidence[SCHEMA] alone → remains INFERENCE
          - SUPPORTED + additional evidence → remains SUPPORTED (no auto-CONFIRMED)
        """
        evidence_list = self.get_evidence_for(subject)
        if not evidence_list:
            return claims

        updated = []
        for claim in claims:
            if claim.subject != subject:
                updated.append(claim)
                continue

            new_claim = self._update_claim_status(claim, evidence_list)
            updated.append(new_claim)

        return updated

    def clear(self) -> None:
        """Очистить store."""
        if os.path.exists(self._store_path):
            os.remove(self._store_path)

    # --- Private ----------------------------------------------------------

    def _update_claim_status(
        self,
        claim: KnowledgeClaim,
        evidence_list: list[KnowledgeEvidence],
    ) -> KnowledgeClaim:
        """Определить новый статус claim на основе evidence."""
        if claim.status == ClaimStatus.CONFIRMED:
            return claim  # already max

        # Check if we have non-SCHEMA evidence
        non_schema = [
            e for e in evidence_list
            if e.trust_level in (
                EvidenceTrustLevel.DECLARED_PURPOSE,
                EvidenceTrustLevel.OBSERVED_SOURCE_STRUCTURE,
            )
        ]

        if non_schema and claim.status == ClaimStatus.INFERENCE:
            # Upgrade to SUPPORTED
            return KnowledgeClaim(
                claim=claim.claim,
                subject=claim.subject,
                predicate=claim.predicate,
                object=claim.object,
                status=ClaimStatus.SUPPORTED,
                evidence=list(claim.evidence) + non_schema,
                last_verified=time.time(),
            )

        return claim

    def _load(self) -> list[dict]:
        if not os.path.exists(self._store_path):
            return []
        with open(self._store_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save(self, data: list[dict]) -> None:
        with open(self._store_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
