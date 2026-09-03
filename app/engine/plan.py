"""ExecutionPlan (M4) — воспроизводимый план запуска.

Источник истины: docs/03_DOMAIN_MODEL.md, docs/08_EXECUTION_MODEL.md (AD-17).
Фиксирует конкретную версию workflow (workflow_id@version) + параметры + bindings.
Не содержит исполнимой логики.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ExecutionPlan:
    capability: str
    workflow_id: str
    version: str
    provider: str = "comfyui"
    backend: str = "local_comfyui"
    params: dict = field(default_factory=dict)          # логич. параметры (prompt, steps, …)
    asset_bindings: dict = field(default_factory=dict)  # role -> asset_id (входные ассеты)
    original_prompt: Optional[str] = None                # исходный текст пользователя (M11.6)
    enhanced_prompt: Optional[str] = None                # улучшенный промпт (M11.6)
    prompt_source: Optional[str] = None                  # источник enhancement: heuristic/llm/fallback (M11.6)
