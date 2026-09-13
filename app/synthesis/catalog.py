"""Template catalog — built-in workflow templates for S2 synthesis.

Каждый шаблон = graph pattern из реальных workflow проекта.
Провенанс: derived from workflows/{txt2img,pollinations_image,upscale,...}.
"""
from __future__ import annotations

from app.synthesis.template import SafetyClass, TemplateConnection, TemplateNode, WorkflowTemplate

# ---------------------------------------------------------------------------
# text → image (head-node generator + save)
# Derived from: workflows/pollinations_image/
# ---------------------------------------------------------------------------
TEXT_TO_IMAGE = WorkflowTemplate(
    template_id="s2_text_to_image",
    version="1.0.0",
    target_capability="image.generate",
    description="Head-node text→image generator + SaveImage. "
                "For nodes with IMAGE output, no IMAGE input, has prompt/text input.",
    nodes=(
        TemplateNode(role="generator", class_type="__TARGET__"),
        TemplateNode(role="save", class_type="SaveImage",
                     default_inputs={"filename_prefix": "ComfyUI_s2"}),
    ),
    connections=(
        TemplateConnection(from_role="generator", from_slot=0,
                           to_role="save", to_field="images"),
    ),
    output_role="save",
    output_kind="image",
    required_input_types=frozenset(),
    required_model=False,
    parameter_slots={
        "prompt": "generator.prompt",
        "seed": "generator.seed",
        "width": "generator.width",
        "height": "generator.height",
    },
    provenance="Derived from workflows/pollinations_image/. "
               "Template for head-node image generators (no IMAGE input).",
    safety=SafetyClass.REQUIRES_CONFIRMATION,  # conservative: custom node
    limitations=("Only works for nodes that produce IMAGE from text params. "
                 "Does not handle model-dependent generation (txt2img via checkpoint)."),
)


# ---------------------------------------------------------------------------
# image → image (load + process + save)
# Derived from: workflows/upscale/
# ---------------------------------------------------------------------------
IMAGE_TO_IMAGE = WorkflowTemplate(
    template_id="s2_image_to_image",
    version="1.0.0",
    target_capability="image.edit",
    description="LoadImage → target processing node → SaveImage. "
                "For nodes with IMAGE input and IMAGE output.",
    nodes=(
        TemplateNode(role="load", class_type="LoadImage",
                     default_inputs={"image": ""}),
        TemplateNode(role="process", class_type="__TARGET__"),
        TemplateNode(role="save", class_type="SaveImage",
                     default_inputs={"filename_prefix": "ComfyUI_s2"}),
    ),
    connections=(
        TemplateConnection(from_role="load", from_slot=0,
                           to_role="process", to_field="image"),
        TemplateConnection(from_role="process", from_slot=0,
                           to_role="save", to_field="images"),
    ),
    output_role="save",
    output_kind="image",
    required_input_types=frozenset({"IMAGE"}),
    required_model=False,
    parameter_slots={},
    provenance="Derived from workflows/upscale/. "
               "Template for image→image processing nodes.",
    safety=SafetyClass.ALLOWED,  # deterministic media processing
    limitations=("Only works for single IMAGE input nodes. "
                 "Multi-image input (batch) not covered."),
)


# ---------------------------------------------------------------------------
# text → audio (head-node generator + save)
# Derived from: workflows/audio_generate/
# ---------------------------------------------------------------------------
TEXT_TO_AUDIO = WorkflowTemplate(
    template_id="s2_text_to_audio",
    version="1.0.0",
    target_capability="audio.generate",
    description="Head-node text→audio generator + SaveAudio. "
                "For nodes with AUDIO output, no IMAGE input, has prompt/text input.",
    nodes=(
        TemplateNode(role="generator", class_type="__TARGET__"),
        TemplateNode(role="save", class_type="SaveAudio",
                     default_inputs={"filename_prefix": "ComfyUI_s2_audio"}),
    ),
    connections=(
        TemplateConnection(from_role="generator", from_slot=0,
                           to_role="save", to_field="audio"),
    ),
    output_role="save",
    output_kind="audio",
    required_input_types=frozenset(),
    required_model=False,
    parameter_slots={
        "prompt": "generator.prompt",
        "seed": "generator.seed",
        "duration": "generator.duration",
    },
    provenance="Derived from workflows/audio_generate/. "
               "Template for head-node audio generators.",
    safety=SafetyClass.REQUIRES_CONFIRMATION,
    limitations=("Only works for nodes that produce AUDIO from text params."),
)


# ---------------------------------------------------------------------------
# text → video (head-node generator + CreateVideo + SaveVideo)
# Derived from: workflows/video_generate/ (simplified — no checkpoint path)
# ---------------------------------------------------------------------------
TEXT_TO_VIDEO = WorkflowTemplate(
    template_id="s2_text_to_video",
    version="1.0.0",
    target_capability="video.generate",
    description="Head-node text→video generator + CreateVideo + SaveVideo. "
                "For nodes with VIDEO output, no IMAGE input, has prompt.",
    nodes=(
        TemplateNode(role="generator", class_type="__TARGET__"),
        TemplateNode(role="create_video", class_type="CreateVideo",
                     default_inputs={"fps": 4}),
        TemplateNode(role="save", class_type="SaveVideo",
                     default_inputs={"filename_prefix": "ComfyUI_s2_video",
                                     "format": "mp4", "codec": "h264"}),
    ),
    connections=(
        TemplateConnection(from_role="generator", from_slot=0,
                           to_role="create_video", to_field="images"),
        TemplateConnection(from_role="create_video", from_slot=0,
                           to_role="save", to_field="video"),
    ),
    output_role="save",
    output_kind="video",
    required_input_types=frozenset(),
    required_model=False,
    parameter_slots={
        "prompt": "generator.prompt",
        "seed": "generator.seed",
        "duration": "generator.duration",
        "fps": "create_video.fps",
    },
    provenance="Derived from workflows/video_generate/ (head-node path). "
               "For generators that output VIDEO directly (e.g. AgnesVideo Text To Video). "
               "Requires CreateVideo+SaveVideo custom nodes.",
    safety=SafetyClass.REQUIRES_CONFIRMATION,
    limitations=("Requires CreateVideo and SaveVideo custom nodes installed. "
                 "Only works for nodes that produce VIDEO frames/images directly. "
                 "Model-dependent video generation (via KSampler) not covered."),
)


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------
TEMPLATE_CATALOG: list[WorkflowTemplate] = [
    TEXT_TO_IMAGE,
    IMAGE_TO_IMAGE,
    TEXT_TO_AUDIO,
    TEXT_TO_VIDEO,
]
