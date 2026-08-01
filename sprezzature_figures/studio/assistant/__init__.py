"""
sprezzature_figures.studio.assistant — the LLM-facing layer.

The model never generates or executes code (plan §1.1): every call site
here is scoped to one Pydantic schema (schemas.py) and validated by
repair.py before anything downstream sees it. client.py wraps
best_engine_ai_helper.llm.chat() as the only path to a model; nothing else
in this package talks to Ollama or any backend directly.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from .client import BestEngineLLMClient, LLMClient, default_client
from .edit import propose_edit
from .fake_client import FakeLLMClient, FakeLLMTimeout
from .intent import analyze_intent
from .recommend import explain_recommendations
from .repair import LLMResponseError, validate_or_repair
from .schemas import (
    EditorialSuggestion,
    EditProposal,
    FigureRecommendation,
    RecommendationSet,
    VisualCritique,
    VisualIssue,
)

__all__ = [
    "BestEngineLLMClient",
    "EditProposal",
    "EditorialSuggestion",
    "FakeLLMClient",
    "FakeLLMTimeout",
    "FigureRecommendation",
    "LLMClient",
    "LLMResponseError",
    "RecommendationSet",
    "VisualCritique",
    "VisualIssue",
    "analyze_intent",
    "default_client",
    "explain_recommendations",
    "propose_edit",
    "validate_or_repair",
]
