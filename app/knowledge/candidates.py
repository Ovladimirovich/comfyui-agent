"""CapabilityCandidate, UsageHypothesis, InputMapping, CandidateGenerator.

CapabilityCandidate описывает ГИПОТЕЗУ: node может удовлетворить capability
определённым способом. НЕ является production capability.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from app.knowledge.models import ClaimStatus, EvidenceSource, EvidenceTrustLevel, KnowledgeClaim, KnowledgeEvidence
from app.knowledge.node_schema import NodeSchema


@dataclass(frozen=True)
class InputMapping:
    """Как node input mapped к capability input."""

    node_input: str
    capability_role: str
    cardinality: int = 1

    def to_dict(self) -> dict:
        return {
            "node_input": self.node_input,
            "capability_role": self.capability_role,
            "cardinality": self.cardinality,
        }

    @classmethod
    def from_dict(cls, data: dict) -> InputMapping:
        return cls(
            node_input=data["node_input"],
            capability_role=data["capability_role"],
            cardinality=data.get("cardinality", 1),
        )


@dataclass(frozen=True)
class UsageHypothesis:
    """Гипотеза использования node для конкретной capability."""

    mode: Optional[str] = None
    input_mappings: tuple[InputMapping, ...] = ()
    cardinality: int = 0
    description: str = ""

    def to_dict(self) -> dict:
        d: dict = {"cardinality": self.cardinality, "description": self.description}
        if self.mode is not None:
            d["mode"] = self.mode
        d["input_mappings"] = [m.to_dict() for m in self.input_mappings]
        return d

    @classmethod
    def from_dict(cls, data: dict) -> UsageHypothesis:
        mappings = tuple(InputMapping.from_dict(m) for m in data.get("input_mappings", []))
        return cls(
            mode=data.get("mode"),
            input_mappings=mappings,
            cardinality=data.get("cardinality", 0),
            description=data.get("description", ""),
        )


@dataclass
class CapabilityCandidate:
    """Гипотеза: node может удовлетворить capability определённым способом."""

    node_class: str
    capability: str
    status: ClaimStatus = ClaimStatus.INFERENCE
    evidence: list[KnowledgeEvidence] = field(default_factory=list)
    usage: UsageHypothesis = field(default_factory=UsageHypothesis)
    claims: list[KnowledgeClaim] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "node_class": self.node_class,
            "capability": self.capability,
            "status": self.status.value,
            "evidence": [e.to_dict() for e in self.evidence],
            "usage": self.usage.to_dict(),
            "claims": [c.to_dict() for c in self.claims],
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> CapabilityCandidate:
        evidence = [KnowledgeEvidence.from_dict(e) for e in data.get("evidence", [])]
        claims = [KnowledgeClaim.from_dict(c) for c in data.get("claims", [])]
        return cls(
            node_class=data["node_class"],
            capability=data["capability"],
            status=ClaimStatus(data.get("status", "INFERENCE")),
            evidence=evidence,
            usage=UsageHypothesis.from_dict(data.get("usage", {})),
            claims=claims,
            created_at=data.get("created_at", 0.0),
        )


class CandidateGenerator:
    """Генерирует CapabilityCandidates из NodeSchema.

    Правила inference:
      - output VIDEO + mode enum с image-related values → image-to-video candidate
      - output VIDEO + prompt input → text-to-video candidate (weak)
      - output IMAGE → image generation candidate (weak)
      - output AUDIO → audio generation candidate (weak)

    Каждый candidate:
      - status = INFERENCE (никогда не автоматически SUPPORTED/CONFIRMED)
      - evidence = только runtime schema
    """

    # Semantic signals in mode enum values
    _IMAGE_TO_VIDEO_SIGNALS = ("image to video", "img2video", "first and last frame")
    _TEXT_TO_VIDEO_SIGNALS = ("text to video", "txt2video")

    def generate(self, schema: NodeSchema) -> list[CapabilityCandidate]:
        """Generate candidates from a single NodeSchema."""
        candidates: list[CapabilityCandidate] = []

        output_types = set(o for o in schema.output_types if isinstance(o, str))
        input_names = {f.name for f in schema.input_required}
        input_names.update(f.name for f in schema.input_optional)

        now = time.time()
        evidence = KnowledgeEvidence(
            source="runtime:/object_info",
            source_type=EvidenceSource.RUNTIME,
            trust_level=EvidenceTrustLevel.SCHEMA,
            timestamp=now,
            claim=f"runtime schema for {schema.class_type}",
        )

        has_video_output = "VIDEO" in output_types
        has_image_output = "IMAGE" in output_types
        has_audio_output = "AUDIO" in output_types

        # Find mode-related enum fields
        mode_field = None
        for f in schema.input_required:
            if f.name == "mode" and f.type == "ENUM":
                mode_field = f
                break

        if has_video_output and mode_field is not None:
            candidates.extend(self._generate_from_mode(schema, mode_field, evidence, now))

        if has_video_output and mode_field is None:
            # Simple video output without mode — weak text-to-video signal
            has_prompt = "prompt" in input_names
            if has_prompt:
                candidates.append(self._make_candidate(
                    schema.class_type,
                    "video.generate",
                    evidence,
                    now,
                    UsageHypothesis(
                        description="video output + prompt input (weak signal)",
                        cardinality=0,
                    ),
                ))

        if has_image_output and not has_video_output:
            # Image-only output — weak image generation signal
            has_prompt = "prompt" in input_names
            if has_prompt:
                candidates.append(self._make_candidate(
                    schema.class_type,
                    "image.generate",
                    evidence,
                    now,
                    UsageHypothesis(
                        description="image output + prompt input (weak signal)",
                        cardinality=0,
                    ),
                ))

        if has_audio_output and not has_video_output and not has_image_output:
            has_prompt = "prompt" in input_names
            if has_prompt:
                candidates.append(self._make_candidate(
                    schema.class_type,
                    "audio.generate",
                    evidence,
                    now,
                    UsageHypothesis(
                        description="audio output + prompt input (weak signal)",
                        cardinality=0,
                    ),
                ))

        # STRING output → text generation candidate
        has_string_output = "STRING" in output_types
        if has_string_output and not has_video_output and not has_image_output and not has_audio_output:
            has_prompt = "prompt" in input_names or "text" in input_names or "prompts" in input_names
            if has_prompt:
                candidates.append(self._make_candidate(
                    schema.class_type,
                    "text.generate",
                    evidence,
                    now,
                    UsageHypothesis(
                        description="string output + text input (weak signal)",
                        cardinality=0,
                    ),
                ))

        return candidates

    def _generate_from_mode(
        self,
        schema: NodeSchema,
        mode_field,
        evidence: KnowledgeEvidence,
        now: float,
    ) -> list[CapabilityCandidate]:
        """Generate candidates from mode enum field."""
        candidates = []
        options_lower = {opt.lower(): opt for opt in mode_field.options}

        # Check for image-to-video signals
        for signal in self._IMAGE_TO_VIDEO_SIGNALS:
            for opt_lower, opt_original in options_lower.items():
                if signal in opt_lower:
                    usage = self._infer_usage_for_mode(schema, opt_original)
                    candidates.append(self._make_candidate(
                        schema.class_type,
                        "video.image_to_video",
                        evidence,
                        now,
                        usage,
                    ))
                    break

        # Check for text-to-video signals
        for signal in self._TEXT_TO_VIDEO_SIGNALS:
            for opt_lower, opt_original in options_lower.items():
                if signal in opt_lower:
                    usage = self._infer_usage_for_mode(schema, opt_original)
                    candidates.append(self._make_candidate(
                        schema.class_type,
                        "video.generate",
                        evidence,
                        now,
                        usage,
                    ))
                    break

        return candidates

    def _infer_usage_for_mode(self, schema: NodeSchema, mode_value: str) -> UsageHypothesis:
        """Infer usage hypothesis for a specific mode value."""
        input_optional_names = {f.name for f in schema.input_optional}
        input_required_names = {f.name for f in schema.input_required}

        # Determine which image inputs are relevant for this mode
        mode_lower = mode_value.lower()
        is_first_last = "first and last" in mode_lower or "two" in mode_lower

        mappings = []
        if "image" in input_optional_names or "image" in input_required_names:
            mappings.append(InputMapping(
                node_input="image",
                capability_role="start_frame" if not is_first_last else "first_frame",
                cardinality=1,
            ))
        if is_first_last and ("end_frame" in input_optional_names or "end_frame" in input_required_names):
            mappings.append(InputMapping(
                node_input="end_frame",
                capability_role="end_frame",
                cardinality=1,
            ))

        # Cardinality = number of image inputs for this specific mode
        cardinality = len(mappings) if mappings else 0

        return UsageHypothesis(
            mode=mode_value,
            input_mappings=tuple(mappings),
            cardinality=cardinality,
            description=f"inferred from mode={mode_value}",
        )

    @staticmethod
    def _make_candidate(
        node_class: str,
        capability: str,
        evidence: KnowledgeEvidence,
        now: float,
        usage: UsageHypothesis,
    ) -> CapabilityCandidate:
        claim = KnowledgeClaim(
            claim=f"{node_class} implements {capability}",
            subject=node_class,
            predicate="implements",
            object=capability,
            status=ClaimStatus.INFERENCE,
            evidence=[evidence],
            last_verified=now,
        )
        return CapabilityCandidate(
            node_class=node_class,
            capability=capability,
            status=ClaimStatus.INFERENCE,
            evidence=[evidence],
            usage=usage,
            claims=[claim],
            created_at=now,
        )
