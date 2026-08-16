"""
Tests for the deterministic transformation executor in
core/transformations.py, deterministic meaning the same input rows always
produce the same output rows, with no hidden randomness: each Transform
type applied to plain rows, plus the ordering between them, the tolerance
for comparing strings and numbers, and the safeguard against a missing
column.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import pytest

from sprezzature_figures.core.operations import (
    AggregateTransform,
    CalculateDerived,
    FilterByRange,
    FilterByValue,
    FilterTemporal,
    GroupOthers,
    RenameDisplay,
    SortTransform,
    TopN,
)
from sprezzature_figures.core.transformations import apply_transformations


def _rows() -> list[dict]:
    return [
        {"region": "North", "value": 42, "date": "2023-05-01"},
        {"region": "South", "value": 28, "date": "2021-03-01"},
        {"region": "East", "value": 91, "date": "2022-07-01"},
        {"region": "West", "value": 15, "date": "2024-01-01"},
    ]


@pytest.mark.parametrize(
    "rows, transform, expected_regions",
    [
        # membership keeps only the listed values
        (_rows(), FilterByValue(column="region", op="in", values=["North", "East"]), {"North", "East"}),
        # not_in excludes the listed values
        (_rows(), FilterByValue(column="region", op="not_in", values=["North"]), {"South", "East", "West"}),
        # range drops out-of-bounds AND non-numeric cells (the "n/a" row vanishes)
        (
            _rows() + [{"region": "NaNland", "value": "n/a"}],
            FilterByRange(column="value", minimum=20, maximum=50),
            {"North", "South"},
        ),
        # temporal keeps only rows inside the window
        (_rows(), FilterTemporal(column="date", start="2022-01-01", end="2023-12-31"), {"North", "East"}),
    ],
)
def test_filters_select_expected_rows(rows, transform, expected_regions) -> None:
    out, notes = apply_transformations(rows, [transform])
    assert {r["region"] for r in out} == expected_regions
    assert notes == []


def test_filter_by_value_tolerates_string_number_drift() -> None:
    # Regression pin: CSV cells load numbers as strings; a filter value of 3
    # must still match the cell "3".
    rows = [{"n": "3"}, {"n": 4}, {"n": "5"}]
    out, _ = apply_transformations(rows, [FilterByValue(column="n", op="eq", values=[3])])
    assert out == [{"n": "3"}]


@pytest.mark.parametrize(
    "rows, column, ascending, expected",
    [
        # plain descending sort by number
        (_rows(), "value", False, [91, 42, 28, 15]),
        # edge case: numbers first (ascending), then non-numeric text, then None last
        ([{"v": 3}, {"v": None}, {"v": "x"}, {"v": 1}], "v", True, [1, 3, "x", None]),
    ],
)
def test_sort_orders_numbers_and_tolerates_mixed(rows, column, ascending, expected) -> None:
    out, _ = apply_transformations(rows, [SortTransform(column=column, ascending=ascending)])
    assert [r[column] for r in out] == expected


@pytest.mark.parametrize(
    "agg, output_column, expected",
    [
        # sum, with an explicit output column name and two groups
        ("sum", "total", [{"cat": "a", "total": 17}, {"cat": "b", "total": 5}]),
        # remaining aggregations reuse the value column name by default
        ("mean", None, [{"cat": "a", "amt": 8.5}, {"cat": "b", "amt": 5.0}]),
        ("median", None, [{"cat": "a", "amt": 8.5}, {"cat": "b", "amt": 5.0}]),
        ("min", None, [{"cat": "a", "amt": 7.0}, {"cat": "b", "amt": 5.0}]),
        ("max", None, [{"cat": "a", "amt": 10.0}, {"cat": "b", "amt": 5.0}]),
        # count names its own output column
        ("count", None, [{"cat": "a", "count": 2}, {"cat": "b", "count": 1}]),
    ],
)
def test_aggregate_groups_and_computes(agg, output_column, expected) -> None:
    rows = [{"cat": "a", "amt": 10}, {"cat": "b", "amt": 5}, {"cat": "a", "amt": 7}]
    out, _ = apply_transformations(
        rows,
        [AggregateTransform(group_by=["cat"], value_column="amt", agg=agg, output_column=output_column)],
    )
    assert out == expected


@pytest.mark.parametrize(
    "by, expected",
    [
        # by="value": East(91) and North(42) are the top 2, returned in original order
        ("value", ["North", "East"]),
        # no ranking column: take the first n in place
        (None, ["North", "South"]),
    ],
)
def test_top_n_selection(by, expected) -> None:
    out, _ = apply_transformations(_rows(), [TopN(column="region", n=2, by=by)])
    assert [r["region"] for r in out] == expected


def test_calculate_difference_and_ratio() -> None:
    rows = [{"a": 10, "b": 4}, {"a": 6, "b": 0}]
    diff, _ = apply_transformations(rows, [CalculateDerived(calc="difference", left="a", right="b", output_column="d")])
    assert [r["d"] for r in diff] == [6.0, 6.0]
    ratio, _ = apply_transformations(rows, [CalculateDerived(calc="ratio", left="a", right="b", output_column="r")])
    assert ratio[0]["r"] == 2.5
    assert ratio[1]["r"] is None  # divide-by-zero -> None, never raises


def test_executor_contract_invariants() -> None:
    rows = _rows()
    snapshot = [dict(r) for r in rows]

    # empty transform list is the identity
    out, notes = apply_transformations(rows, [])
    assert out == rows
    assert notes == []

    # RenameDisplay is a data no-op (labelling, not a data change)
    out, notes = apply_transformations(rows, [RenameDisplay(column="region", display_name="Zone")])
    assert out == rows
    assert notes == []

    # transforms apply in list order: filter, then the order-dependent sort
    out, _ = apply_transformations(
        rows,
        [FilterByRange(column="value", minimum=20), SortTransform(column="value", ascending=True)],
    )
    assert [r["value"] for r in out] == [28, 42, 91]

    # a filter on an absent column is skipped (can't empty the figure) and noted
    out, notes = apply_transformations(rows, [FilterByValue(column="nope", op="eq", values=["x"])])
    assert out == rows
    assert len(notes) == 1
    assert "nope" in notes[0]

    # GroupOthers relabels non-kept values -- without mutating the input rows
    out, _ = apply_transformations(rows, [GroupOthers(column="region", keep=["North"], other_label="Rest")])
    assert [r["region"] for r in out] == ["North", "Rest", "Rest", "Rest"]
    assert rows == snapshot  # every step returns fresh dicts; inputs untouched
