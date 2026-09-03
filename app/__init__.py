"""Пакет app — media-agnostic ComfyUI Agent (M1–M5 движок + слой оркестрации Agent)."""

from app.agent import Agent, AgentError
from app.conversation import ConversationAgent, ConversationContext
from app.planner import HeuristicPlanner, LLMPlanner, PlanContext, PlanResult, Planner
from app.registry.backends import BackendCatalog, BackendSpec

__all__ = [
    "Agent",
    "AgentError",
    "ConversationAgent",
    "ConversationContext",
    "BackendCatalog",
    "BackendSpec",
    "HeuristicPlanner",
    "LLMPlanner",
    "PlanContext",
    "PlanResult",
    "Planner",
]
