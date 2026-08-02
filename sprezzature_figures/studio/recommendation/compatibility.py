"""
Deterministic hard-constraint filter (plan §6, step 1): which figure kinds can
this dataset even fill? A kind survives only if every one of its *required*
roles has at least one column whose semantic type the role accepts. No LLM
here; the model's job (`assistant.recommend.explain_recommendations`) is only
to rerank and explain the survivors this produces.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from sprezzature_figures.catalog.models import FigureDefinition, RoleDefinition
from sprezzature_figures.catalog.registry import get_figure_definition, list_kinds
from sprezzature_figures.core.dataset import ColumnProfile, DatasetProfile

# Which detected column semantic types can stand in for a role's accepted type.
# Roles are declared in terms of coarse types (numeric/categorical/datetime/
# ...); the profiler emits finer ones (currency, percentage, email, ...), so
# map the fine types onto the coarse role types a column can legitimately fill.
_ROLE_TYPE_ACCEPTS: dict[str, set[str]] = {
    "numeric": {"numeric", "percentage", "currency"},
    "categorical": {"categorical", "boolean", "text", "identifier"},
    "datetime": {"datetime"},
    "text": {"text", "categorical", "identifier", "url", "email"},
    "boolean": {"boolean"},
    "latitude": {"latitude"},
    "longitude": {"longitude"},
    "identifier": {"identifier"},
}


def column_fits_role(column: ColumnProfile, role: RoleDefinition) -> bool:
    """True if this column's semantic type satisfies any type the role accepts."""
    return any(
        column.semantic_type in _ROLE_TYPE_ACCEPTS.get(accepted, {accepted})
        for accepted in role.accepted_types
    )


def _has_distinct_assignment(role_candidates: list[list[int]]) -> bool:
    """True if each role can be given a *distinct* column (a bipartite matching
    of roles to columns), via augmenting paths. This is what stops a scatter
    (two numeric roles) from looking satisfiable on a dataset with only one
    numeric column."""
    matched: dict[int, int] = {}  # column index -> role index

    def assign(role: int, seen: set[int]) -> bool:
        for col in role_candidates[role]:
            if col in seen:
                continue
            seen.add(col)
            if col not in matched or assign(matched[col], seen):
                matched[col] = role
                return True
        return False

    return all(assign(role, set()) for role in range(len(role_candidates)))


def can_fill_required_roles(definition: FigureDefinition, profile: DatasetProfile) -> bool:
    """True if the dataset clears the figure's `min_rows` floor and its columns
    can cover every required role with a distinct column each."""
    if definition.min_rows is not None and profile.row_count < definition.min_rows:
        return False
    candidates = [
        [i for i, col in enumerate(profile.columns) if column_fits_role(col, role)]
        for role in definition.required_roles
    ]
    if any(not cols for cols in candidates):
        return False
    return _has_distinct_assignment(candidates)


def compatible_definitions(
    profile: DatasetProfile, *, status: str | None = "stable"
) -> list[FigureDefinition]:
    """Every figure of the given status whose required roles this dataset can
    fill, in registry order. Pass `status=None` to consider all kinds."""
    definitions = (get_figure_definition(kind) for kind in list_kinds(status))
    return [d for d in definitions if can_fill_required_roles(d, profile)]
