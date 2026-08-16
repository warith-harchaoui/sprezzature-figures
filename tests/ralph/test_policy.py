"""
Tests for sprezzature_figures.studio.ralph.policy: classifying a proposed
fix as either safe-repair (small enough to apply on its own) or
confirmation-required (needs the user's yes first), per the project's
internal design plan, §11.2/§11.3.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import pytest

from sprezzature_figures.core.operations import (
    AddAnnotation,
    AddFilter,
    Annotation,
    BindColumn,
    FigureOperation,
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


@pytest.mark.parametrize(
    ("op", "safe"),
    [
        (SetStyleOption(operation_id="op1", option="font_scale", value=1.3), True),
        (SetStyleOption(operation_id="op1", option="theme", value="dark"), False),  # not in safe list
        (SetOutputSize(operation_id="op1", width=1000, height=600), True),
        (AddAnnotation(operation_id="op1", annotation=Annotation(annotation_id="a1", text="note")), True),
        (SetTitle(operation_id="op1", title="x"), False),  # editorial, not a cosmetic repair
    ],
)
def test_is_safe_repair(op: FigureOperation, safe: bool) -> None:
    assert is_safe_repair(op) is safe


@pytest.mark.parametrize(
    ("op", "confirm"),
    [
        (SetFigureKind(operation_id="op1", new_kind="line"), True),
        (AddFilter(operation_id="op1", transform=FilterByValue(column="x", values=["a"])), True),
        (BindColumn(operation_id="op1", role="x", columns=["a"]), True),  # rebinding changes meaning
        (SortRows(operation_id="op1", transform=SortTransform(column="x")), False),  # display-only reorder
        (SetTitle(operation_id="op1", title="x"), False),
    ],
)
def test_requires_confirmation_and_complement(op: FigureOperation, confirm: bool) -> None:
    assert requires_confirmation(op) is confirm
    # can_apply_automatically is defined as the exact complement.
    assert can_apply_automatically(op) is (not confirm)
