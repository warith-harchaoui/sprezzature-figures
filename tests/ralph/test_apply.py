"""
Tests for sprezzature_figures.studio.ralph.apply: applying a
FigureOperation (one requested edit, e.g. "change the color") to a
FigurePlan (the chart's current structured description) deterministically,
so the same operation applied to the same plan always produces the same
result.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import pytest

from sprezzature_figures.core.figure_plan import ColumnBinding, FigurePlan
from sprezzature_figures.core.operations import (
    AddAnnotation,
    AddFilter,
    Annotation,
    BindColumn,
    FilterByValue,
    RemoveAnnotation,
    RemoveFilter,
    SetFigureKind,
    SetOutputSize,
    SetStyleOption,
    SetSubtitle,
    SetTitle,
    UnbindColumn,
)
from sprezzature_figures.studio.ralph.apply import apply_operation, apply_operations


def _plan() -> FigurePlan:
    return FigurePlan(figure_kind="bar", title="Old", bindings={"x": ColumnBinding(columns=["region"])})


def test_scalar_field_operations_update_their_target() -> None:
    plan = apply_operation(_plan(), SetFigureKind(operation_id="op1", new_kind="line"))
    plan = apply_operation(plan, SetTitle(operation_id="op2", title="New"))
    plan = apply_operation(plan, SetSubtitle(operation_id="op3", subtitle="Sub"))
    plan = apply_operation(plan, SetStyleOption(operation_id="op4", option="font_scale", value=1.5))
    plan = apply_operation(plan, SetOutputSize(operation_id="op5", width=1200, height=800))

    assert plan.figure_kind == "line"
    assert plan.title == "New"
    assert plan.subtitle == "Sub"
    assert plan.style.font_scale == 1.5
    assert plan.style.width == 1200 and plan.style.height == 800


def test_bind_and_unbind_column() -> None:
    plan = apply_operation(_plan(), BindColumn(operation_id="op1", role="y", columns=["value"]))
    assert plan.bindings["y"].columns == ["value"]
    plan = apply_operation(plan, UnbindColumn(operation_id="op2", role="x"))
    assert "x" not in plan.bindings


def test_add_filter_generates_id_then_remove_by_id() -> None:
    plan = apply_operation(
        _plan(), AddFilter(operation_id="op1", transform=FilterByValue(column="region", values=["North"]))
    )
    assert len(plan.transformations) == 1
    tid = plan.transformations[0].transform_id
    assert tid  # auto-assigned, non-empty
    plan = apply_operation(plan, RemoveFilter(operation_id="op2", transform_id=tid))
    assert plan.transformations == []


def test_add_and_remove_annotation() -> None:
    ann = Annotation(annotation_id="a1", text="note")
    plan = apply_operation(_plan(), AddAnnotation(operation_id="op1", annotation=ann))
    assert len(plan.annotations) == 1
    plan = apply_operation(plan, RemoveAnnotation(operation_id="op2", annotation_id="a1"))
    assert plan.annotations == []


def test_apply_semantics_immutable_ordered_and_typed() -> None:
    # apply_operation never mutates its input plan.
    original = _plan()
    apply_operation(original, SetTitle(operation_id="op1", title="Changed"))
    assert original.title == "Old"

    # apply_operations applies in order (last SetTitle wins).
    result = apply_operations(
        _plan(),
        [SetTitle(operation_id="op1", title="First"), SetTitle(operation_id="op2", title="Second")],
    )
    assert result.title == "Second"

    # An unknown operation type is a hard error, not a silent no-op.
    class _Bogus:
        pass

    with pytest.raises(ValueError, match="No apply rule"):
        apply_operation(_plan(), _Bogus())  # type: ignore[arg-type]
