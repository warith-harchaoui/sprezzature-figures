"""
Tests for the deterministic transformation executor (core/transformations.py):
each Transform type applied to plain rows, plus the ordering, the string/number
tolerance, and the missing-column safeguard.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

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


def test_filter_by_value_membership() -> None:
    out, notes = apply_transformations(
        _rows(), [FilterByValue(column="region", op="in", values=["North", "East"])]
    )
    assert {r["region"] for r in out} == {"North", "East"}
    assert notes == []


def test_filter_by_value_not_in_excludes() -> None:
    out, _ = apply_transformations(
        _rows(), [FilterByValue(column="region", op="not_in", values=["North"])]
    )
    assert "North" not in {r["region"] for r in out}
    assert len(out) == 3


def test_filter_by_value_tolerates_string_number_drift() -> None:
    rows = [{"n": "3"}, {"n": 4}, {"n": "5"}]
    out, _ = apply_transformations(rows, [FilterByValue(column="n", op="eq", values=[3])])
    assert out == [{"n": "3"}]


def test_filter_by_range_drops_out_of_bounds_and_non_numeric() -> None:
    rows = _rows() + [{"region": "NaNland", "value": "n/a"}]
    out, _ = apply_transformations(rows, [FilterByRange(column="value", minimum=20, maximum=50)])
    assert sorted(r["value"] for r in out) == [28, 42]


def test_filter_temporal_keeps_window() -> None:
    out, _ = apply_transformations(
        _rows(), [FilterTemporal(column="date", start="2022-01-01", end="2023-12-31")]
    )
    assert {r["region"] for r in out} == {"North", "East"}


def test_sort_descending_by_number() -> None:
    out, _ = apply_transformations(_rows(), [SortTransform(column="value", ascending=False)])
    assert [r["value"] for r in out] == [91, 42, 28, 15]


def test_sort_handles_none_and_mixed_without_raising() -> None:
    rows = [{"v": 3}, {"v": None}, {"v": "x"}, {"v": 1}]
    out, _ = apply_transformations(rows, [SortTransform(column="v", ascending=True)])
    # numbers first (ascending), then non-numeric text, then None last.
    assert [r["v"] for r in out] == [1, 3, "x", None]


def test_aggregate_sum_groups_and_names_output() -> None:
    rows = [
        {"cat": "a", "amt": 10},
        {"cat": "b", "amt": 5},
        {"cat": "a", "amt": 7},
    ]
    out, _ = apply_transformations(
        rows,
        [AggregateTransform(group_by=["cat"], value_column="amt", agg="sum", output_column="total")],
    )
    assert out == [{"cat": "a", "total": 17}, {"cat": "b", "total": 5}]


def test_aggregate_mean_median_count() -> None:
    rows = [{"g": "x", "v": 2}, {"g": "x", "v": 4}, {"g": "x", "v": 6}]
    mean, _ = apply_transformations(rows, [AggregateTransform(group_by=["g"], value_column="v", agg="mean")])
    assert mean == [{"g": "x", "v": 4.0}]
    median, _ = apply_transformations(rows, [AggregateTransform(group_by=["g"], value_column="v", agg="median")])
    assert median == [{"g": "x", "v": 4}]
    count, _ = apply_transformations(rows, [AggregateTransform(group_by=["g"], value_column="v", agg="count")])
    assert count == [{"g": "x", "count": 3}]


def test_top_n_by_value_keeps_original_order() -> None:
    out, _ = apply_transformations(_rows(), [TopN(column="region", n=2, by="value")])
    # East(91) and North(42) are the top 2, returned in their original order.
    assert [r["region"] for r in out] == ["North", "East"]


def test_top_n_without_by_takes_first_n() -> None:
    out, _ = apply_transformations(_rows(), [TopN(column="region", n=2)])
    assert [r["region"] for r in out] == ["North", "South"]


def test_group_others_relabels_non_kept() -> None:
    out, _ = apply_transformations(_rows(), [GroupOthers(column="region", keep=["North"], other_label="Rest")])
    assert [r["region"] for r in out] == ["North", "Rest", "Rest", "Rest"]


def test_calculate_difference_and_ratio() -> None:
    rows = [{"a": 10, "b": 4}, {"a": 6, "b": 0}]
    diff, _ = apply_transformations(rows, [CalculateDerived(calc="difference", left="a", right="b", output_column="d")])
    assert [r["d"] for r in diff] == [6.0, 6.0]
    ratio, _ = apply_transformations(rows, [CalculateDerived(calc="ratio", left="a", right="b", output_column="r")])
    assert ratio[0]["r"] == 2.5
    assert ratio[1]["r"] is None  # divide-by-zero -> None, never raises


def test_rename_display_is_a_data_noop() -> None:
    rows = _rows()
    out, notes = apply_transformations(rows, [RenameDisplay(column="region", display_name="Zone")])
    assert out == rows  # display renaming is a labelling concern, not a data change
    assert notes == []


def test_transforms_apply_in_order() -> None:
    # Filter to top values, then sort ascending: order-dependent result.
    out, _ = apply_transformations(
        _rows(),
        [
            FilterByRange(column="value", minimum=20),
            SortTransform(column="value", ascending=True),
        ],
    )
    assert [r["value"] for r in out] == [28, 42, 91]


def test_missing_column_is_skipped_not_silently_emptying() -> None:
    rows = _rows()
    out, notes = apply_transformations(rows, [FilterByValue(column="nope", op="eq", values=["x"])])
    assert out == rows  # a filter on an absent column can't empty the figure
    assert len(notes) == 1
    assert "nope" in notes[0]


def test_rows_are_not_mutated_in_place() -> None:
    rows = _rows()
    snapshot = [dict(r) for r in rows]
    apply_transformations(rows, [GroupOthers(column="region", keep=[], other_label="X")])
    assert rows == snapshot


def test_empty_transform_list_is_identity() -> None:
    rows = _rows()
    out, notes = apply_transformations(rows, [])
    assert out == rows
    assert notes == []
