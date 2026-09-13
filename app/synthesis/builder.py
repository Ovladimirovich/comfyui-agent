"""WorkflowBuilder — synthesize manifest + workflow from template + candidate + schema (S2).

Template-Based Synthesis: instantiate a WorkflowTemplate with concrete
node class, parameters, and bindings from a CapabilityCandidate + NodeSchema.
"""
from __future__ import annotations

import copy
import uuid as _uuid
from typing import Any, Optional

from app.knowledge.candidates import CapabilityCandidate
from app.knowledge.node_schema import NodeSchema
from app.synthesis.template import SafetyClass, WorkflowSynthesisResult, WorkflowTemplate


def synthesize_workflow(
    candidate: CapabilityCandidate,
    schema: NodeSchema,
    template: WorkflowTemplate,
    safety: SafetyClass = SafetyClass.REQUIRES_CONFIRMATION,
) -> WorkflowSynthesisResult:
    """Synthesize a concrete ComfyUI workflow from template + candidate + schema.

    Steps:
    1. Materialize graph skeleton with concrete node IDs
    2. Replace __TARGET__ with actual class_type
    3. Bind candidate parameters to node inputs
    4. Set defaults from NodeSchema
    5. Wire connections between nodes
    6. Generate manifest.json + workflow.json

    Does NOT validate against live ComfyUI (that's RuntimeValidator's job).
    """
    warnings: list[str] = []

    # --- 1. Materialize node IDs ---
    role_to_id: dict[str, str] = {}
    workflow_dict: dict[str, Any] = {}

    for i, node in enumerate(template.nodes):
        node_id = str(i + 1)
        role_to_id[node.role] = node_id

        class_type = node.class_type
        if class_type == "__TARGET__":
            class_type = candidate.node_class

        inputs: dict[str, Any] = dict(node.default_inputs)

        # Set defaults from NodeSchema for the target node
        if node.role in ("generator", "process"):
            _apply_schema_defaults(inputs, schema)

        workflow_dict[node_id] = {
            "class_type": class_type,
            "inputs": inputs,
        }

    # --- 2. Wire connections ---
    for conn in template.connections:
        from_id = role_to_id[conn.from_role]
        to_id = role_to_id[conn.to_role]
        to_node = workflow_dict[to_id]
        to_node["inputs"][conn.to_field] = [from_id, conn.from_slot]

    # --- 3. Bind candidate parameters ---
    bound_params: dict[str, dict[str, Any]] = {}
    for param_name, slot in template.parameter_slots.items():
        parts = slot.split(".", 1)
        if len(parts) != 2:
            continue
        role, field_name = parts
        node_id = role_to_id.get(role)
        if node_id is None:
            continue
        # Get default from schema
        schema_default = _get_schema_default(schema, param_name)
        if schema_default is not None:
            workflow_dict[node_id]["inputs"][field_name] = schema_default
            bound_params[param_name] = {
                "node": node_id,
                "field": field_name,
                "default": schema_default,
            }

    # --- 4. Build manifest ---
    output_node_id = role_to_id.get(template.output_role, "1")
    wf_id = f"s2_{candidate.node_class}_{template.template_id}"

    # Collect required_custom_nodes from candidate node class
    required_custom_nodes = []
    if schema.python_module and not schema.python_module.startswith("nodes"):
        # Custom node — the target class is a required custom node
        required_custom_nodes.append(candidate.node_class)

    # If template uses CreateVideo/SaveVideo/etc.
    for node in template.nodes:
        if node.class_type in ("CreateVideo", "SaveVideo", "SaveAudio"):
            if node.class_type not in required_custom_nodes:
                required_custom_nodes.append(node.class_type)

    # Collect required model bindings
    required_models = []
    model_requirements = []
    has_model_input = any(f.type == "MODEL" for f in
                          list(schema.input_required) + list(schema.input_optional))
    if has_model_input or template.required_model:
        required_models.append("checkpoint")
        model_requirements.append({"kind": "checkpoint"})

    # Build inputs for manifest (parameters that map to node fields)
    manifest_inputs: dict[str, dict[str, str]] = {}
    manifest_parameters: dict[str, dict[str, Any]] = {}
    for param_name, binding in bound_params.items():
        manifest_inputs[param_name] = {
            "node": binding["node"],
            "field": binding["field"],
        }
        # Build parameter metadata from schema
        schema_field = _find_schema_field(schema, param_name)
        if schema_field:
            param_meta: dict[str, Any] = {}
            if schema_field.default is not None:
                param_meta["default"] = schema_field.default
            if schema_field.min_val is not None:
                param_meta["min"] = schema_field.min_val
            if schema_field.max_val is not None:
                param_meta["max"] = schema_field.max_val
            if schema_field.options:
                param_meta["options"] = list(schema_field.options)
            if param_meta:
                manifest_parameters[param_name] = param_meta

    # Asset inputs — check if template requires IMAGE input
    has_image_input = any(f.type == "IMAGE" for f in schema.input_required)
    asset_inputs: dict[str, dict[str, str]] = {}
    if has_image_input:
        load_node_id = role_to_id.get("load")
        if load_node_id:
            asset_inputs["image"] = {
                "node": load_node_id,
                "field": "image",
                "kind": "image",
            }

    manifest = {
        "id": wf_id,
        "version": "1.0.0",
        "capability": template.target_capability,
        "provider": "comfyui",
        "backend": "local_comfyui",
        "source": "synthesized",
        "synthesized_from": {
            "candidate": candidate.node_class,
            "template": template.template_id,
            "template_version": template.version,
        },
        "safety_class": safety.value,
        "inputs": manifest_inputs,
        "asset_inputs": asset_inputs,
        "outputs": {
            "result": {
                "node": output_node_id,
                "kind": template.output_kind,
            }
        },
        "parameters": manifest_parameters,
        "required_models": required_models,
        "required_custom_nodes": required_custom_nodes,
        "min_comfyui_version": "0.0.0",
        "requirements": {"accelerator": "any", "xformers": False,
                         "min_vram_gb": 0, "fp16": False},
        "limits": {"max_upload_bytes": 209715200, "max_asset_duration": 0,
                   "max_video_width": 0, "max_video_height": 0,
                   "max_sequence_length": 0},
    }

    if model_requirements:
        manifest["model_requirements"] = model_requirements
        manifest["contract_version"] = 2

    return WorkflowSynthesisResult(
        manifest=manifest,
        workflow=workflow_dict,
        capability=template.target_capability,
        template_id=template.template_id,
        warnings=warnings,
        safety=safety,
    )


def _apply_schema_defaults(inputs: dict[str, Any], schema: NodeSchema) -> None:
    """Apply defaults from NodeSchema to node inputs."""
    for field in list(schema.input_required) + list(schema.input_optional):
        if field.name in inputs:
            continue  # already set by template
        if field.default is not None:
            inputs[field.name] = field.default
        elif field.options:
            inputs[field.name] = field.options[0]  # first option as default


def _get_schema_default(schema: NodeSchema, param_name: str) -> Any:
    """Get default value for a parameter from NodeSchema."""
    for field in list(schema.input_required) + list(schema.input_optional):
        if field.name == param_name:
            if field.default is not None:
                return field.default
            if field.options:
                return field.options[0]
            # Type-based defaults
            if field.type == "INT":
                return 0
            if field.type == "FLOAT":
                return 0.0
            if field.type == "STRING":
                return ""
            if field.type == "BOOLEAN":
                return False
    return None


def _find_schema_field(schema: NodeSchema, param_name: str):
    """Find FieldSpec for a parameter name."""
    for field in list(schema.input_required) + list(schema.input_optional):
        if field.name == param_name:
            return field
    return None
