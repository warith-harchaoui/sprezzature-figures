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


def _match_roles_to_columns(role_candidates: list[list[int]]) -> dict[int, int] | None:
    """Assign each role a *distinct* column (a bipartite matching of roles to
    columns) via augmenting paths, or None if no full assignment exists. This
    is what stops a scatter (two numeric roles) from looking satisfiable on a
    dataset with only one numeric column. Returns column index -> role index."""
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

    for role in range(len(role_candidates)):
        if not assign(role, set()):
            return None
    return matched


def _name_affinity(role_name: str, column_name: str) -> int:
    """Rank a candidate column against a role by name closeness (0 = best).

    Two roles that both accept the same coarse type (e.g. sunburst's
    ``parent`` and ``name``, both ``categorical``) are otherwise
    indistinguishable to the type-only matcher below, which then picks
    whichever augmenting path it finds first -- for a CSV with literal
    ``parent``/``name`` columns this silently swapped the two. Sorting each
    role's candidates by name affinity first (exact match, then substring,
    then no relation) makes the matcher prefer the obviously-intended
    column whenever one exists, while still falling back to the type-only
    behaviour when no column name hints at its role.
    """
    role_l, col_l = role_name.lower(), column_name.lower()
    if role_l == col_l:
        return 0
    if role_l in col_l or col_l in role_l:
        return 1
    return 2


def _required_role_candidates(
    definition: FigureDefinition, profile: DatasetProfile
) -> list[list[int]] | None:
    """Column indices that fit each required role, or None if any required role
    has no candidate at all (so the figure can't apply). Each role's
    candidates are ordered by name affinity (see :func:`_name_affinity`) so
    the bipartite matcher in :func:`_match_roles_to_columns` prefers a
    name-matched column over an equally type-valid but unrelated one."""
    candidates = [
        sorted(
            (i for i, col in enumerate(profile.columns) if column_fits_role(col, role)),
            key=lambda i: _name_affinity(role.name, profile.columns[i].name),
        )
        for role in definition.required_roles
    ]
    return None if any(not cols for cols in candidates) else candidates


def can_fill_required_roles(definition: FigureDefinition, profile: DatasetProfile) -> bool:
    """True if the dataset clears the figure's `min_rows` floor and its columns
    can cover every required role with a distinct column each."""
    if definition.min_rows is not None and profile.row_count < definition.min_rows:
        return False
    candidates = _required_role_candidates(definition, profile)
    return candidates is not None and _match_roles_to_columns(candidates) is not None


def assign_columns(definition: FigureDefinition, profile: DatasetProfile) -> dict[str, str] | None:
    """A concrete `{required_role_name: column_name}` binding using distinct
    columns, or None if the figure can't be filled. This is what lets a
    "recommended figure" be built with one click, no manual role binding."""
    candidates = _required_role_candidates(definition, profile)
    if candidates is None:
        return None
    matched = _match_roles_to_columns(candidates)
    if matched is None:
        return None
    return {
        definition.required_roles[role_i].name: profile.columns[col_i].name
        for col_i, role_i in matched.items()
    }


# A subset of "hero" generators accept a `data` argument for dispatcher
# parity but never thread it into the render -- their layout (arc order,
# ring angles, merge tree, hero call-out, outside labels, ...) is hand-tuned
# to one fixed illustrative dataset, and every one of them documents this in
# its own docstring with the same idiom: `_ = data, title  # accepted for
# dispatcher parity; see docstring`. `can_fill_required_roles` can't see
# that -- it only checks whether column *types* satisfy the role signature,
# which these pass just fine -- so without this exclusion a recommendation
# card would confidently claim "Uses Path -> parent, Lines -> value" and
# then silently render the fixed illustration instead. Found by grepping
# every scripts/make_*.py for that idiom (`_ = data` / "not threaded into" /
# "baked into" the render) -- keep this set in sync if a generator's data
# handling changes either way. Kept out of the ranked/one-click
# recommendation pool for both the CLI's `recommend` and Studio's cards;
# still fully renderable via `make_figure()` directly or the "Or choose
# manually" picker for someone who wants the fixed illustration on purpose.
_DATA_BLIND_HERO_KINDS = frozenset(
    {
        "arcdiagram",
        "binned-grid-map",
        "chord",
        "circle-packing",
        "convex-hull",
        "cycle",
        "dendrogram",
        "dependency-wheel",
        "edge-bundling",
        "elbow",
        "embedding_projector",
    }
)


def compatible_definitions(
    profile: DatasetProfile, *, status: str | None = "stable"
) -> list[FigureDefinition]:
    """Every figure of the given status whose required roles this dataset can
    fill, in registry order. Pass `status=None` to consider all kinds."""
    definitions = (
        get_figure_definition(kind)
        for kind in list_kinds(status)
        if kind not in _DATA_BLIND_HERO_KINDS
    )
    return [d for d in definitions if can_fill_required_roles(d, profile)]
