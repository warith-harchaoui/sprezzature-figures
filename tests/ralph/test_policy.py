"""
Tests for sprezzature_figures.studio.ralph.policy: safe-repair and
confirmation-required classification (plan §11.2/§11.3).

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from sprezzature_figures.core.operations import (
    AddAnnotation,
    AddFilter,
    Annotation,
    BindColumn,
    FilterByValue,
    SetFigureKind,
    SetOutputSize,
    SetStyleOption,
    SetTitle,
    SortRows,
    SortTransform,
)
from sprezzature_figures.studio.ralph.policy import (
    can_apply_automatically,
    is_safe_repair,
    requires_confirmation,
)


def test_style_option_in_safe_list_is_safe_repair() -> None:
    op = SetStyleOption(operation_id="op1", option="font_scale", value=1.3)
    assert is_safe_repair(op) is True


def test_style_option_not_in_safe_list_is_not_safe_repair() -> None:
    op = SetStyleOption(operation_id="op1", option="theme", value="dark")
    assert is_safe_repair(op) is False


def test_set_output_size_is_safe_repair() -> None:
    assert is_safe_repair(SetOutputSize(operation_id="op1", width=1000, height=600)) is True


def test_add_annotation_is_safe_repair() -> None:
    ann = Annotation(annotation_id="a1", text="note")
    assert is_safe_repair(AddAnnotation(operation_id="op1", annotation=ann)) is True


def test_set_title_is_not_a_safe_repair() -> None:
    assert is_safe_repair(SetTitle(operation_id="op1", title="x")) is False


def test_figure_kind_change_requires_confirmation() -> None:
    op = SetFigureKind(operation_id="op1", new_kind="line")
    assert requires_confirmation(op) is True
    assert can_apply_automatically(op) is False


def test_add_filter_requires_confirmation() -> None:
    op = AddFilter(operation_id="op1", transform=FilterByValue(column="x", values=["a"]))
    assert requires_confirmation(op) is True


def test_bind_column_requires_confirmation() -> None:
    assert requires_confirmation(BindColumn(operation_id="op1", role="x", columns=["a"])) is True


def test_sort_rows_does_not_require_confirmation() -> None:
    op = SortRows(operation_id="op1", transform=SortTransform(column="x"))
    assert requires_confirmation(op) is False
    assert can_apply_automatically(op) is True


def test_set_title_does_not_require_confirmation() -> None:
    assert requires_confirmation(SetTitle(operation_id="op1", title="x")) is False
