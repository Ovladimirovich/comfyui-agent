"""S2 — Template-Based Workflow Synthesis.

CapabilityCandidate + NodeSchema + WorkflowTemplate → synthesized ComfyUI workflow.
"""
from app.synthesis.template import WorkflowTemplate, WorkflowSynthesisResult
from app.synthesis.selector import select_template
from app.synthesis.builder import synthesize_workflow
from app.synthesis.safety import classify_safety, SafetyClass
from app.synthesis.catalog import TEMPLATE_CATALOG

__all__ = [
    "WorkflowTemplate",
    "WorkflowSynthesisResult",
    "select_template",
    "synthesize_workflow",
    "classify_safety",
    "SafetyClass",
    "TEMPLATE_CATALOG",
]
