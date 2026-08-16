"""
Deterministic figure-recommendation engine (specified in the project's
internal design plan, §6): first a hard-constraint compatibility filter
rules out chart kinds the data can't support, then a scoring pass ranks
what's left. No language model involved here: the ranking is plain,
reproducible logic.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from sprezzature_figures.catalog import get_figure_definition
from sprezzature_figures.core.dataset import ColumnProfile, DatasetProfile
from sprezzature_figures.studio.recommendation import (
    assign_columns,
    compatible_definitions,
    infer_goal,
    rank,
    recommend_figures,
    score,
)
from sprezzature_figures.studio.recommendation.compatibility import column_fits_role


def _profile(columns: list[ColumnProfile], rows: int = 20) -> DatasetProfile:
    return DatasetProfile(
        dataset_id="d", fingerprint="f", source_name="s.csv",
        row_count=rows, column_count=len(columns), columns=columns,
    )


def _num(name: str) -> ColumnProfile:
    return ColumnProfile(name=name, physical_dtype="float64", semantic_type="numeric")


def _cat(name: str, unique: int = 4) -> ColumnProfile:
    return ColumnProfile(name=name, physical_dtype="object", semantic_type="categorical", unique_count=unique)


def _dt(name: str) -> ColumnProfile:
    return ColumnProfile(name=name, physical_dtype="datetime64[ns]", semantic_type="datetime")


def test_hard_constraint_needs_a_distinct_column_per_required_role() -> None:
    # scatter needs two numeric roles: satisfiable only with two numeric columns,
    # not one numeric reused for both.
    one_numeric = _profile([_cat("region"), _num("revenue")])
    two_numeric = _profile([_num("hp"), _num("mpg")])
    assert "scatter" not in {d.kind for d in compatible_definitions(one_numeric)}
    assert "scatter" in {d.kind for d in compatible_definitions(two_numeric)}


def test_bar_is_compatible_with_a_category_and_a_measure() -> None:
    profile = _profile([_cat("region"), _num("revenue")])
    assert "bar" in {d.kind for d in compatible_definitions(profile)}


def test_data_blind_hero_generators_are_never_recommended() -> None:
    # arcdiagram/chord/binned-grid-map/circle-packing accept a `data` kwarg
    # for dispatcher parity but never thread it into the render (each
    # module's own docstring says so) -- their role signature alone would
    # otherwise pass the hard-constraint filter and produce a one-click
    # "Use" card that silently ignores the dataset it claims to bind.
    hierarchy = _profile([_cat("parent", unique=3), _cat("name", unique=8), _num("value")], rows=8)
    kinds = {d.kind for d in compatible_definitions(hierarchy)}
    assert "circle-packing" not in kinds
    assert "treemap" in kinds  # a real hierarchy figure stays recommendable


def test_column_fits_role_maps_fine_types_onto_coarse_role_types() -> None:
    # A percentage/currency column fills a numeric role; a boolean fills a
    # categorical one.
    scatter = next(d for d in compatible_definitions(_profile([_num("a"), _num("b")])) if d.kind == "scatter")
    numeric_role = scatter.required_roles[0]
    assert column_fits_role(ColumnProfile(name="p", physical_dtype="float64", semantic_type="percentage"), numeric_role)
    assert not column_fits_role(ColumnProfile(name="c", physical_dtype="object", semantic_type="categorical"), numeric_role)


def test_scoring_penalises_too_many_categories() -> None:
    # A category-limited figure (bar: max_recommended_categories=25) scores
    # lower when the categorical column has far more distinct values than it can
    # legibly show, so a tidy dataset ranks it above a sprawling one.
    tidy = _profile([_cat("region", unique=8), _num("revenue")])
    sprawling = _profile([_cat("region", unique=800), _num("revenue")])
    bar_tidy = {d.kind: s for d, s in rank(tidy)}["bar"]
    bar_sprawling = {d.kind: s for d, s in rank(sprawling)}["bar"]
    assert bar_sprawling < bar_tidy


def test_assign_columns_gives_a_distinct_binding_per_required_role() -> None:
    # scatter's two numeric roles get two different columns (what one-click
    # "Use" on a recommendation card needs to build a plan without manual
    # binding); an incompatible dataset returns None.
    scatter = get_figure_definition("scatter")
    binding = assign_columns(scatter, _profile([_num("hp"), _num("mpg")]))
    assert binding is not None
    assert len(binding) == len(scatter.required_roles)
    assert len(set(binding.values())) == len(binding)  # distinct columns
    assert assign_columns(scatter, _profile([_cat("region"), _num("only_one")])) is None


def test_rank_and_recommend_are_deterministic_and_bounded() -> None:
    profile = _profile([_cat("region"), _num("revenue")])
    ranked = rank(profile)
    scores = [s for _d, s in ranked]
    assert scores == sorted(scores, reverse=True)  # best first
    assert all(0.0 <= s <= 1.0 for s in scores)
    top = recommend_figures(profile, limit=3)
    assert len(top) <= 3
    compatible = {d.kind for d in compatible_definitions(profile)}
    assert all(d.kind in compatible for d in top)  # never recommends the incompatible


# A profile compatible with both a Comparison figure (bar: cat+num) and a
# Relationship figure (scatter: num+num), so a goal can reorder them.
def _mixed_profile() -> DatasetProfile:
    return _profile([_cat("region", unique=5), _num("a"), _num("b")])


def test_score_intent_promotes_matching_category_over_mismatch() -> None:
    # bar's category is "Comparison": the goal "comparison" puts it in the top
    # band, and any other goal it does not serve drops it to the low band.
    bar = get_figure_definition("bar")
    profile = _mixed_profile()
    matched = score(bar, profile, goal="comparison")
    mismatched = score(bar, profile, goal="relationship")
    assert matched >= 0.6 > mismatched
    # No goal is the readability-only score, unchanged and >= the mismatch.
    assert score(bar, profile) >= mismatched


def test_rank_with_goal_orders_the_matching_figure_first() -> None:
    profile = _mixed_profile()

    def position(ranked: list, kind: str) -> int:
        return next(i for i, (d, _s) in enumerate(ranked) if d.kind == kind)

    for_comparison = rank(profile, goal="comparison")
    for_relationship = rank(profile, goal="relationship")
    # bar (Comparison) beats scatter (Relationship) under the comparison goal,
    # and the ordering flips under the relationship goal.
    assert position(for_comparison, "bar") < position(for_comparison, "scatter")
    assert position(for_relationship, "scatter") < position(for_relationship, "bar")


def test_goal_scores_stay_bounded_and_unknown_goal_is_readability_only() -> None:
    profile = _mixed_profile()
    with_goal = rank(profile, goal="distribution")
    assert all(0.0 <= s <= 1.0 for _d, s in with_goal)
    # An unrecognised goal must not do worse than the intent-blind ranking.
    assert rank(profile, goal="unknown") == rank(profile)


def test_infer_goal_reads_the_analytical_goal_off_the_column_shape() -> None:
    # A category plus a measure is the plain comparison (bar) case.
    assert infer_goal(_profile([_cat("region"), _num("value")])) == "comparison"
    # A datetime plus a measure reads as a trend, even with a category present.
    assert infer_goal(_profile([_dt("day"), _num("sales")])) == "trend"
    assert infer_goal(_profile([_dt("day"), _cat("channel"), _num("sales")])) == "trend"
    # Two measures and no category is a relationship (scatter) shape.
    assert infer_goal(_profile([_num("hp"), _num("mpg")])) == "relationship"
    # Nothing to measure: no clear goal, so scoring stays readability-only.
    assert infer_goal(_profile([_cat("a"), _cat("b")])) is None


def test_infer_goal_tells_hierarchy_from_a_flat_two_way_comparison() -> None:
    # parent/name/value-shaped data (effectifs.csv): "parent" repeats (a
    # group, 3 unique values over 8 rows) while "name" is unique per row (a
    # leaf) -- that branch/leaf cardinality split is the hierarchy signature.
    hierarchy = _profile([_cat("parent", unique=3), _cat("name", unique=8), _num("value")], rows=8)
    assert infer_goal(hierarchy) == "hierarchy"

    # region/quarter/revenue (ventes-trimestrielles.csv): both categorical
    # columns repeat (4 and 2 unique values over 8 rows), so this must stay a
    # plain comparison, not get pulled toward treemap/sunburst.
    two_way = _profile([_cat("region", unique=4), _cat("quarter", unique=2), _num("revenue")], rows=8)
    assert infer_goal(two_way) == "comparison"


def test_inferred_goal_floats_the_shape_appropriate_figure_to_the_top() -> None:
    # This is what the GUI does post-import: infer the goal, then rank. A plain
    # category+measure set must lead with bar (not a stacked area that merely
    # also fits), and a datetime+measure set must lead with line.
    categorical = _profile([_cat("region"), _num("value")])
    top_categorical = rank(categorical, goal=infer_goal(categorical))[0][0].kind
    assert top_categorical == "bar"

    timeseries = _profile([_dt("day"), _num("sales")])
    top_timeseries = rank(timeseries, goal=infer_goal(timeseries))[0][0].kind
    assert top_timeseries == "line"
