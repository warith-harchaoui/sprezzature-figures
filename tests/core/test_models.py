"""
Tests for sprezzature_figures.core: the dataset, figure_plan (the
structured, editable description of a chart before it's rendered), and
operations models, plus their validation.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from typing import get_args

import pytest
from pydantic import TypeAdapter, ValidationError

from sprezzature_figures.catalog import get_figure_definition
from sprezzature_figures.core import (
    ColumnBinding,
    ColumnProfile,
    DatasetProfile,
    FigureOperation,
    FigurePlan,
    StyleOptions,
    validate_operation,
    validate_plan,
)
from sprezzature_figures.core.operations import (
    AddFilter,
    BindColumn,
    FilterByRange,
    FilterByValue,
    SetStyleOption,
    SetTitle,
    StyleOptionName,
)


def _dataset() -> DatasetProfile:
    return DatasetProfile(
        dataset_id="d1",
        fingerprint="abc123",
        source_name="test.csv",
        row_count=100,
        column_count=3,
        columns=[
            ColumnProfile(name="city", physical_dtype="object", semantic_type="categorical"),
            ColumnProfile(name="low", physical_dtype="int64", semantic_type="numeric"),
            ColumnProfile(name="high", physical_dtype="int64", semantic_type="numeric"),
        ],
    )


def test_figure_plan_model_basics() -> None:
    empty = FigurePlan(figure_kind="treemap")
    assert empty.version == 1
    assert empty.style == StyleOptions()
    assert empty.bound_columns() == set()

    # bound_columns() aggregates the columns across every role binding
    bound = FigurePlan(
        figure_kind="treemap",
        bindings={
            "parent": ColumnBinding(columns=["a"]),
            "name": ColumnBinding(columns=["b"]),
            "value": ColumnBinding(columns=["c"]),
        },
    )
    assert bound.bound_columns() == {"a", "b", "c"}


def test_column_binding_requires_at_least_one_column() -> None:
    with pytest.raises(ValidationError):
        ColumnBinding(columns=[])


def test_figure_operation_discriminated_union() -> None:
    adapter = TypeAdapter(FigureOperation)

    # round-trips through JSON, preserving the concrete operation + nested transform
    op = AddFilter(operation_id="op1", transform=FilterByValue(column="city", values=["Paris"]))
    restored = adapter.validate_python(op.model_dump())
    assert isinstance(restored, AddFilter)
    assert restored.transform == op.transform

    # and rejects an operation_type outside the union
    with pytest.raises(ValidationError):
        adapter.validate_python({"operation_id": "x", "operation_type": "delete_everything"})


def test_set_style_option_literal_tracks_style_fields() -> None:
    # SetStyleOption.option's Literal must list exactly the StyleOptions fields;
    # this catches drift if a style option is added/renamed on one side only,
    # and means an invented name is rejected the moment the operation is built.
    assert set(get_args(StyleOptionName)) == set(StyleOptions.model_fields)
    with pytest.raises(ValidationError):
        SetStyleOption(operation_id="op1", option="not_a_real_option", value=1)


@pytest.mark.parametrize(
    "op, expected_substr",
    [
        # unknown bound column -> flagged
        (BindColumn(operation_id="op1", role="x", columns=["nope"]), "nope"),
        # known bound column -> clean
        (BindColumn(operation_id="op1", role="x", columns=["city"]), None),
        # declared style option name -> clean
        (SetStyleOption(operation_id="op1", option="width", value=1200), None),
        # operation with no column reference at all -> clean
        (SetTitle(operation_id="op1", title="New title"), None),
        # a filter transform reaching for a missing column -> flagged
        (AddFilter(operation_id="op1", transform=FilterByRange(column="ghost", minimum=0, maximum=10)), "ghost"),
    ],
)
def test_validate_operation(op, expected_substr) -> None:
    issues = validate_operation(op, dataset=_dataset())
    if expected_substr is None:
        assert issues == []
    else:
        assert issues
        assert expected_substr in issues[0].message
        assert all(i.severity == "error" for i in issues)


@pytest.mark.parametrize(
    "bindings, expected_missing",
    [
        # nothing bound -> every required role is reported missing
        ({}, {"parent", "name", "value"}),
        # all required roles bound -> no issues
        (
            {
                "parent": ColumnBinding(columns=["a"]),
                "name": ColumnBinding(columns=["b"]),
                "value": ColumnBinding(columns=["c"]),
            },
            set(),
        ),
    ],
)
def test_validate_plan_required_roles(bindings, expected_missing) -> None:
    definition = get_figure_definition("treemap")
    plan = FigurePlan(figure_kind="treemap", bindings=bindings)
    issues = validate_plan(plan, definition=definition)
    assert {i.field for i in issues} == expected_missing


def test_validate_plan_flags_bound_column_missing_from_dataset() -> None:
    plan = FigurePlan(
        figure_kind="columnrange",
        bindings={"month": ColumnBinding(columns=["not_in_dataset"])},
    )
    issues = validate_plan(plan, dataset=_dataset())
    assert any("not_in_dataset" in i.message for i in issues)
