"""
Tests for sprezzature_figures.core: dataset/figure_plan/operations models
and validation.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

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


def test_figure_plan_defaults_are_valid() -> None:
    plan = FigurePlan(figure_kind="treemap")
    assert plan.version == 1
    assert plan.style == StyleOptions()
    assert plan.bound_columns() == set()


def test_column_binding_requires_at_least_one_column() -> None:
    with pytest.raises(ValidationError):
        ColumnBinding(columns=[])


def test_bound_columns_aggregates_across_roles() -> None:
    plan = FigurePlan(
        figure_kind="treemap",
        bindings={
            "parent": ColumnBinding(columns=["a"]),
            "name": ColumnBinding(columns=["b"]),
            "value": ColumnBinding(columns=["c"]),
        },
    )
    assert plan.bound_columns() == {"a", "b", "c"}


def test_figure_operation_discriminated_union_round_trips_through_json() -> None:
    adapter = TypeAdapter(FigureOperation)
    op = AddFilter(operation_id="op1", transform=FilterByValue(column="city", values=["Paris"]))
    restored = adapter.validate_python(op.model_dump())
    assert isinstance(restored, AddFilter)
    assert restored.transform == op.transform


def test_figure_operation_union_rejects_unknown_operation_type() -> None:
    adapter = TypeAdapter(FigureOperation)
    with pytest.raises(ValidationError):
        adapter.validate_python({"operation_id": "x", "operation_type": "delete_everything"})


def test_validate_operation_flags_unknown_bound_column() -> None:
    op = BindColumn(operation_id="op1", role="x", columns=["nope"])
    issues = validate_operation(op, dataset=_dataset())
    assert len(issues) == 1
    assert issues[0].severity == "error"


def test_validate_operation_accepts_known_bound_column() -> None:
    op = BindColumn(operation_id="op1", role="x", columns=["city"])
    assert validate_operation(op, dataset=_dataset()) == []


def test_validate_operation_flags_undeclared_style_option() -> None:
    op = SetStyleOption(operation_id="op1", option="not_a_real_option", value=1)
    issues = validate_operation(op, dataset=_dataset())
    assert any("not a declared StyleOptions field" in i.message for i in issues)


def test_validate_operation_accepts_declared_style_option() -> None:
    op = SetStyleOption(operation_id="op1", option="width", value=1200)
    assert validate_operation(op, dataset=_dataset()) == []


def test_validate_operation_ignores_operations_with_no_column_reference() -> None:
    op = SetTitle(operation_id="op1", title="New title")
    assert validate_operation(op, dataset=_dataset()) == []


def test_validate_operation_flags_filter_transform_unknown_column() -> None:
    op = AddFilter(operation_id="op1", transform=FilterByRange(column="ghost", minimum=0, maximum=10))
    issues = validate_operation(op, dataset=_dataset())
    assert issues and "ghost" in issues[0].message


def test_validate_plan_flags_missing_required_roles() -> None:
    definition = get_figure_definition("treemap")
    plan = FigurePlan(figure_kind="treemap")
    issues = validate_plan(plan, definition=definition)
    missing_fields = {i.field for i in issues}
    assert missing_fields == {"parent", "name", "value"}


def test_validate_plan_passes_with_all_required_roles_bound() -> None:
    definition = get_figure_definition("treemap")
    plan = FigurePlan(
        figure_kind="treemap",
        bindings={
            "parent": ColumnBinding(columns=["a"]),
            "name": ColumnBinding(columns=["b"]),
            "value": ColumnBinding(columns=["c"]),
        },
    )
    issues = validate_plan(plan, definition=definition)
    assert issues == []


def test_validate_plan_flags_bound_column_missing_from_dataset() -> None:
    plan = FigurePlan(
        figure_kind="columnrange",
        bindings={"month": ColumnBinding(columns=["not_in_dataset"])},
    )
    issues = validate_plan(plan, dataset=_dataset())
    assert any("not_in_dataset" in i.message for i in issues)
