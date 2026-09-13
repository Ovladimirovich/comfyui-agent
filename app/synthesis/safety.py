"""Safety classification for synthesized workflows (S2)."""
from __future__ import annotations

from app.synthesis.template import SafetyClass

# Known-safe python_module prefixes (built-in ComfyUI)
_SAFE_MODULE_PREFIXES = ("nodes", "comfy_extras")

# Known-dangerous keywords in module/category
_FORBIDDEN_KEYWORDS = ("shell", "system", "exec", "subprocess", "os.system", "eval(")

# Keywords suggesting external API / network
_NETWORK_KEYWORDS = ("api", "http", "cloud", "remote", "fetch", "request", "openai",
                      "anthropic", "gemini", "replicate", "huggingface", "pollinations")


def classify_safety(python_module: str, category: str, node_class: str) -> SafetyClass:
    """Classify node for auto-test safety.

    Returns:
        ALLOWED: built-in deterministic media processing.
        REQUIRES_CONFIRMATION: custom node, unknown side effects.
        FORBIDDEN: shell/system/destructive.
    """
    module_lower = python_module.lower()
    category_lower = category.lower()
    class_lower = node_class.lower()

    # FORBIDDEN: known dangerous
    for kw in _FORBIDDEN_KEYWORDS:
        if kw in module_lower or kw in category_lower or kw in class_lower:
            return SafetyClass.FORBIDDEN

    # REQUIRES_CONFIRMATION: external API / network
    for kw in _NETWORK_KEYWORDS:
        if kw in module_lower or kw in category_lower:
            return SafetyClass.REQUIRES_CONFIRMATION

    # ALLOWED: built-in or known-safe
    if any(module_lower.startswith(p) for p in _SAFE_MODULE_PREFIXES):
        return SafetyClass.ALLOWED

    # Unknown custom node → REQUIRES_CONFIRMATION (conservative)
    return SafetyClass.REQUIRES_CONFIRMATION
