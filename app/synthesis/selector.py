"""Template selector — match CapabilityCandidate + NodeSchema to a WorkflowTemplate (S2)."""
from __future__ import annotations

from typing import Optional

from app.knowledge.candidates import CapabilityCandidate
from app.knowledge.node_schema import NodeSchema
from app.synthesis.catalog import TEMPLATE_CATALOG
from app.synthesis.template import WorkflowTemplate


def select_template(
    candidate: CapabilityCandidate,
    schema: NodeSchema,
    catalog: Optional[list[WorkflowTemplate]] = None,
) -> Optional[WorkflowTemplate]:
    """Select best matching template for candidate + schema.

    Matching criteria (deterministic, no LLM):
    1. Output type compatibility
    2. Input type compatibility (IMAGE input presence)
    3. Capability family match
    4. Required model presence

    Returns None if no compatible template (CANDIDATE_NO_TEMPLATE).
    """
    templates = catalog if catalog is not None else TEMPLATE_CATALOG

    output_types = set(o for o in schema.output_types if isinstance(o, str))
    all_input_fields = list(schema.input_required) + list(schema.input_optional)
    required_input_fields = list(schema.input_required)
    has_image_input = any(f.type == "IMAGE" for f in required_input_fields)
    has_prompt = any(f.name in ("prompt", "text") for f in required_input_fields)
    has_model_input = any(f.type == "MODEL" for f in all_input_fields)

    # Capability family from candidate
    cap = candidate.capability  # e.g. "image.generate", "video.image_to_video"

    best: Optional[WorkflowTemplate] = None
    best_score = -1

    for tmpl in templates:
        score = _score_template(
            tmpl, cap, output_types, has_image_input, has_prompt, has_model_input
        )
        if score > best_score:
            best_score = score
            best = tmpl

    return best if best_score > 0 else None


def _score_template(
    tmpl: WorkflowTemplate,
    capability: str,
    output_types: set[str],
    has_image_input: bool,
    has_prompt: bool,
    has_model_input: bool,
) -> int:
    """Score template compatibility. Higher = better match. 0 = incompatible."""
    score = 0

    # 1. Output type must match (case-insensitive)
    if tmpl.output_kind.upper() not in {t.upper() for t in output_types}:
        return 0

    # 2. Input type compatibility
    if tmpl.required_input_types:
        # Template requires IMAGE input — schema must have it
        if "IMAGE" in tmpl.required_input_types and not has_image_input:
            return 0
    else:
        # Template does NOT require IMAGE input — schema must NOT have it
        if has_image_input:
            return 0

    # 3. Capability match (exact > family)
    if capability == tmpl.target_capability:
        score += 10
    elif capability.split(".")[0] == tmpl.target_capability.split(".")[0]:
        score += 5  # same family (e.g. video.generate vs video.image_to_video)

    # 4. Prompt requirement
    if has_prompt:
        score += 2

    # 5. Model requirement alignment
    if tmpl.required_model == has_model_input:
        score += 1

    return score
