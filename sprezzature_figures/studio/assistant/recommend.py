"""
LLM-assisted reranking/explanation of already-compatible figure candidates
(plan §6). This module does not decide which figures are compatible with a
dataset -- that's a deterministic step owned by whatever calls this (a
future studio.recommendation package). It only reranks, explains, titles,
and flags tradeoffs among candidates it's handed, and never introduces a
kind outside that list.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from sprezzature_figures.catalog.models import FigureDefinition
from sprezzature_figures.core.figure_plan import UserIntent

from .client import LLMClient
from .schemas import FigureRecommendation, RecommendationSet

RECOMMEND_SYSTEM = (
    "You explain and rerank a pre-filtered list of chart kinds that are already "
    "known to be compatible with the user's data and intent. You may reorder them, "
    "explain why each fits, suggest a title, and note a tradeoff. You must not "
    "recommend any kind that is not in the candidate list -- doing so is a hard error."
)


def explain_recommendations(
    client: LLMClient,
    candidates: list[FigureDefinition],
    intent: UserIntent,
) -> list[FigureRecommendation]:
    """Rerank/explain `candidates` (already deterministically filtered for
    compatibility) for the given intent. Any recommendation naming a kind
    outside `candidates` is dropped, never trusted.
    """
    if not candidates:
        return []

    candidate_kinds = {c.kind for c in candidates}
    candidate_lines = "\n".join(f"- {c.kind}: {c.description}" for c in candidates)
    prompt = (
        f"User's analytical goal: {intent.analytical_goal}\n"
        f"Message to convey: {intent.message_to_convey!r}\n\n"
        f"Compatible candidates (choose only from these, do not invent others):\n{candidate_lines}"
    )

    result = client.chat_text(prompt, system=RECOMMEND_SYSTEM, response_model=RecommendationSet, temperature=0.2)
    assert isinstance(result, RecommendationSet)

    return [r for r in result.recommendations if r.kind in candidate_kinds]
