"""
sprezzature_figures.studio.recommendation — the deterministic half of figure
recommendation (plan §6).

Two steps, both pure Python and reproducible:

1. hard constraints (`compatibility.compatible_definitions`): drop any figure
   whose required roles the dataset can't fill;
2. scoring (`scoring.rank`): order the survivors by readability signals.

`recommend_figures` runs both and returns the top definitions. An LLM never
enters here; `assistant.recommend.explain_recommendations` is the optional
rerank/explain layer that sits *on top* of this candidate list, and can never
introduce a kind this module didn't already pass.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from sprezzature_figures.catalog.models import FigureDefinition
from sprezzature_figures.core.dataset import DatasetProfile

from .compatibility import (
    assign_columns,
    can_fill_required_roles,
    column_fits_role,
    compatible_definitions,
)
from .scoring import infer_goal, rank, score


def recommend_figures(
    profile: DatasetProfile,
    *,
    limit: int = 3,
    status: str | None = "stable",
    goal: str | None = None,
) -> list[FigureDefinition]:
    """The top `limit` figure kinds this dataset can fill, best first. Feed the
    result to `assistant.recommend.explain_recommendations` for LLM titles and
    tradeoffs, or show it directly when no model is available.

    Pass `goal` (the user's `UserIntent.analytical_goal`, or the output of
    `infer_goal(profile)` when no LLM intent is available yet) so `rank()`
    breaks the readability tie *before* truncating to `limit` -- omitting it
    here silently drops well-fitting kinds whose readability score ties at
    1.0 with everything else once the list is cut to `limit` (bug found in
    api-bureautique's chart route: a datetime+measure trend request lost
    "line" to alphabetically-earlier "ecdf"/"histogram" every time, because
    the caller learned the goal via an LLM call made *after* this truncation
    already happened).
    """
    return [definition for definition, _score in rank(profile, status=status, goal=goal)[:limit]]


__all__ = [
    "assign_columns",
    "can_fill_required_roles",
    "column_fits_role",
    "compatible_definitions",
    "infer_goal",
    "rank",
    "recommend_figures",
    "score",
]
