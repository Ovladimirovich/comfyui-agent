"""LLMPlanner — OpenAI-compatible API planner (M8).

Online planner that sends the request to an LLM and parses the JSON response.
Falls back to HeuristicPlanner if API key is missing or request fails.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Optional

from app.planner.plan import PlanContext, PlanResult, Planner


DEFAULT_BASE_URL = os.environ.get("LLM_BASE_URL", "http://127.0.0.1:20130")
DEFAULT_MODEL = os.environ.get("LLM_MODEL", "default")
API_KEY_ENV = "OPENROUTER_API_KEY"
TIMEOUT = 30

SYSTEM_PROMPT = (
    "You are a media-task router. Given a user request, output a JSON object "
    "with keys: capability (one of image.generate, image.edit, image.upscale, "
    "video.generate, audio.generate), params (dict with at least 'prompt'). "
    "Keep output valid JSON only, no explanation."
)


class LLMPlannerError(RuntimeError):
    pass


class LLMPlanner(Planner):
    """LLM-based planner. Requires OPENROUTER_API_KEY."""

    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout: int = TIMEOUT) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.api_key = os.environ.get(API_KEY_ENV, "")
        if not self.api_key:
            raise LLMPlannerError(
                f"{API_KEY_ENV} not set. Set it or use HeuristicPlanner fallback."
            )

    def plan(self, request: str, context: Optional[PlanContext] = None) -> PlanResult:
        if not (request or "").strip():
            return PlanResult(capability="image.generate", params={"prompt": ""})

        user_prompt = f"Request: {request.strip()}"
        if context and context.active_asset_type:
            user_prompt += f"\nActive asset type: {context.active_asset_type}"
        if context and context.capabilities:
            user_prompt += f"\nAvailable capabilities: {', '.join(context.capabilities)}"

        body = json.dumps({
            "model": DEFAULT_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.0,
        }).encode("utf-8")

        url = f"{self.base_url}/v1/chat/completions"
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"].strip()
            # Extract JSON from possible markdown code block
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()
            result = json.loads(content)
            return PlanResult(
                capability=result["capability"],
                params=result.get("params", {"prompt": request.strip()}),
                rationale="llm",
            )
        except (KeyError, json.JSONDecodeError, urllib.error.URLError) as e:
            raise LLMPlannerError(f"LLM planner error: {e}") from e
