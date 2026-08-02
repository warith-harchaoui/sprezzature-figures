"""
Deterministic figure-recommendation engine (plan §6): the hard-constraint
compatibility filter and the scoring/rank on top. No LLM here.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from sprezzature_figures.core.dataset import ColumnProfile, DatasetProfile
from sprezzature_figures.studio.recommendation import (
    compatible_definitions,
    rank,
    recommend_figures,
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
    bar_tidy = dict((d.kind, s) for d, s in rank(tidy))["bar"]
    bar_sprawling = dict((d.kind, s) for d, s in rank(sprawling))["bar"]
    assert bar_sprawling < bar_tidy


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
