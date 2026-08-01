"""
Tests for sprezzature_figures.studio.ralph.apply: deterministic
FigureOperation -> FigurePlan application.

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


def test_set_figure_kind() -> None:
    result = apply_operation(_plan(), SetFigureKind(operation_id="op1", new_kind="line"))
    assert result.figure_kind == "line"


def test_set_title_and_subtitle() -> None:
    plan = apply_operation(_plan(), SetTitle(operation_id="op1", title="New"))
    plan = apply_operation(plan, SetSubtitle(operation_id="op2", subtitle="Sub"))
    assert plan.title == "New"
    assert plan.subtitle == "Sub"


def test_bind_and_unbind_column() -> None:
    plan = apply_operation(_plan(), BindColumn(operation_id="op1", role="y", columns=["value"]))
    assert plan.bindings["y"].columns == ["value"]
    plan = apply_operation(plan, UnbindColumn(operation_id="op2", role="x"))
    assert "x" not in plan.bindings


def test_set_style_option() -> None:
    plan = apply_operation(_plan(), SetStyleOption(operation_id="op1", option="font_scale", value=1.5))
    assert plan.style.font_scale == 1.5


def test_set_output_size_updates_style_dimensions() -> None:
    plan = apply_operation(_plan(), SetOutputSize(operation_id="op1", width=1200, height=800))
    assert plan.style.width == 1200
    assert plan.style.height == 800


def test_add_filter_appends_transform_with_generated_id() -> None:
    op = AddFilter(operation_id="op1", transform=FilterByValue(column="region", values=["North"]))
    plan = apply_operation(_plan(), op)
    assert len(plan.transformations) == 1
    assert plan.transformations[0].transform_id  # auto-assigned, non-empty


def test_remove_filter_by_transform_id() -> None:
    op = AddFilter(operation_id="op1", transform=FilterByValue(column="region", values=["North"]))
    plan = apply_operation(_plan(), op)
    tid = plan.transformations[0].transform_id
    plan = apply_operation(plan, RemoveFilter(operation_id="op2", transform_id=tid))
    assert plan.transformations == []


def test_add_and_remove_annotation() -> None:
    ann = Annotation(annotation_id="a1", text="note")
    plan = apply_operation(_plan(), AddAnnotation(operation_id="op1", annotation=ann))
    assert len(plan.annotations) == 1
    plan = apply_operation(plan, RemoveAnnotation(operation_id="op2", annotation_id="a1"))
    assert plan.annotations == []


def test_apply_operation_does_not_mutate_original_plan() -> None:
    plan = _plan()
    apply_operation(plan, SetTitle(operation_id="op1", title="Changed"))
    assert plan.title == "Old"


def test_apply_operations_applies_in_order() -> None:
    ops = [
        SetTitle(operation_id="op1", title="First"),
        SetTitle(operation_id="op2", title="Second"),
    ]
    result = apply_operations(_plan(), ops)
    assert result.title == "Second"


def test_apply_operation_unknown_type_raises() -> None:
    class _Bogus:
        pass

    with pytest.raises(ValueError, match="No apply rule"):
        apply_operation(_plan(), _Bogus())  # type: ignore[arg-type]
