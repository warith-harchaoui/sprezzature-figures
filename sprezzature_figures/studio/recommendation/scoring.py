"""
Deterministic scoring (plan §6, step 2): rank the compatible figure kinds by
how well they suit *this* dataset, before the LLM ever sees them. The score is
a small, legible sum of readability signals, not a learned model, so the
ranking is reproducible and explainable.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from sprezzature_figures.catalog.models import FigureDefinition, RoleDefinition
from sprezzature_figures.core.dataset import ColumnProfile, DatasetProfile

from .compatibility import column_fits_role, compatible_definitions


def _best_column_for_role(role: RoleDefinition, profile: DatasetProfile) -> ColumnProfile | None:
    for col in profile.columns:
        if column_fits_role(col, role):
            return col
    return None


def score(definition: FigureDefinition, profile: DatasetProfile) -> float:
    """A 0..1 suitability score. Starts at 1.0 and subtracts readability
    penalties (too many categories for a categorical role, too many rows for
    the figure's recommended maximum) and adds a small bonus for each optional
    role the data can also fill, so a richer-but-still-legible figure edges out
    a barer one."""
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


def rank(profile: DatasetProfile, *, status: str | None = "stable") -> list[tuple[FigureDefinition, float]]:
    """Compatible figures paired with their score, best first (ties keep
    registry order, so the ranking is fully deterministic)."""
    scored = [(d, score(d, profile)) for d in compatible_definitions(profile, status=status)]
    return sorted(scored, key=lambda pair: pair[1], reverse=True)
