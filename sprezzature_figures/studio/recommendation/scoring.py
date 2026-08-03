"""
Deterministic scoring (plan §6, step 2): rank the compatible figure kinds by
how well they suit *this* dataset, before the LLM ever sees them. The score is
a small, legible combination of readability signals and -- when the caller
knows the user's analytical goal -- an intent-match term, not a learned model,
so the ranking is reproducible and explainable. Readability alone leaves many
kinds tied at 1.0; the goal term is what breaks that tie toward the figure the
user actually asked for.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from sprezzature_figures.catalog.models import FigureDefinition, RoleDefinition
from sprezzature_figures.core.dataset import ColumnProfile, DatasetProfile

from .compatibility import column_fits_role, compatible_definitions

# Which figure `category` values serve each of UserIntent's analytical goals.
# The catalog's `intents` field is unpopulated across all kinds, but every
# figure carries a `category` (e.g. "Comparison", "Time series", "Geospatial /
# Spatial"), and that already encodes the analytical question the figure
# answers. Matching a goal against these keyword substrings (case-insensitive,
# tested against `category.lower()`) lets the score be intent-aware for all
# kinds without hand-annotating 90 `intents` lists. Keys are the non-"unknown"
# members of core.figure_plan.UserIntent.analytical_goal.
_GOAL_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "comparison": ("comparison", "ranking"),
    "trend": ("time series", "temporal", "change"),
    "distribution": ("distribution", "range"),
    "composition": ("composition", "compositional", "decomposition"),
    "relationship": ("relationship", "bivariate", "multivariate", "correlation", "regression", "dimensionality"),
    "flow": ("flow", "network", "pipeline"),
    "hierarchy": ("hierarchy",),
    "geography": ("geospatial", "spatial", "meteorolog"),
    "model_evaluation": ("model evaluation", "goodness of fit", "diagnostics", "agreement", "meta-analysis"),
}


def _best_column_for_role(role: RoleDefinition, profile: DatasetProfile) -> ColumnProfile | None:
    for col in profile.columns:
        if column_fits_role(col, role):
            return col
    return None


def _readability_score(definition: FigureDefinition, profile: DatasetProfile) -> float:
    """A 0..1 readability score for how legibly *this* dataset fills the figure.

    Starts at 1.0 and subtracts penalties (too many categories for a
    categorical role, too many rows for the figure's recommended maximum) and
    adds a small bonus for each optional role the data can also fill, so a
    richer-but-still-legible figure edges out a barer one. This is the
    intent-blind component; goal matching is layered on top in :func:`score`.
    """
    points = 1.0

    # Penalise a categorical role whose only column has more distinct values
    # than the figure can legibly show (e.g. a bar chart with 500 bars).
    if definition.max_recommended_categories is not None:
        for role in definition.required_roles:
            if "categorical" not in role.accepted_types:
                continue
            col = _best_column_for_role(role, profile)
            if col is not None and col.unique_count > definition.max_recommended_categories:
                points -= 0.3

    # Penalise a dataset far larger than the figure is meant for.
    if definition.max_recommended_rows is not None and profile.row_count > definition.max_recommended_rows:
        points -= 0.2

    # Reward optional roles the data can also fill, capped so it never
    # outweighs the readability penalties above.
    fillable_optional = sum(
        1 for role in definition.optional_roles if _best_column_for_role(role, profile) is not None
    )
    points += min(0.15, 0.05 * fillable_optional)

    return max(0.0, min(1.0, points))


def _intent_matches(definition: FigureDefinition, goal: str) -> bool:
    """True if the figure's category serves the requested analytical goal."""
    category = definition.category.lower()
    return any(keyword in category for keyword in _GOAL_CATEGORY_KEYWORDS.get(goal, ()))


def score(definition: FigureDefinition, profile: DatasetProfile, *, goal: str | None = None) -> float:
    """A 0..1 suitability score for showing *this* dataset as this figure.

    Without a `goal`, this is the readability score alone (unchanged behaviour):
    how legibly the data fills the figure. When the caller supplies the user's
    analytical goal (a non-"unknown" `UserIntent.analytical_goal`), intent
    becomes the dominant term: figures whose `category` serves that goal land in
    the top band [0.6, 1.0] and mismatched figures in [0.0, 0.4], with
    readability breaking ties *within* each band. This is what pulls the figure
    the user actually wants above the pile of kinds that merely fit the data and
    otherwise tie at 1.0. An unrecognised or "unknown" goal falls back to
    readability only, so the score never gets worse than the intent-blind case.
    """
    readability = _readability_score(definition, profile)
    if goal is None or goal not in _GOAL_CATEGORY_KEYWORDS:
        return readability
    match = 1.0 if _intent_matches(definition, goal) else 0.0
    return round(0.6 * match + 0.4 * readability, 4)


def rank(
    profile: DatasetProfile, *, status: str | None = "stable", goal: str | None = None
) -> list[tuple[FigureDefinition, float]]:
    """Compatible figures paired with their score, best first (ties keep
    registry order, so the ranking is fully deterministic). Pass `goal` (the
    user's `analytical_goal`) to rank intent-first; omit it for the
    readability-only order the headless CLI uses by default."""
    scored = [(d, score(d, profile, goal=goal)) for d in compatible_definitions(profile, status=status)]
    return sorted(scored, key=lambda pair: pair[1], reverse=True)
