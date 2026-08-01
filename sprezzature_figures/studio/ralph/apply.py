"""
Deterministic application of a FigureOperation to a FigurePlan. This lives
in ralph/, not core/, because applying operations is Ralph's job (plan
§1.3: "Ralph modifies the plan, never the image") -- core stays models and
pure validation only.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import uuid

from sprezzature_figures.core.figure_plan import ColumnBinding, FigurePlan
from sprezzature_figures.core.operations import (
    AddAnnotation,
    AddFilter,
    AggregateRows,
    BindColumn,
    CalculateColumn,
    FigureOperation,
    LimitCategories,
    RemoveAnnotation,
    RemoveFilter,
    SetFigureKind,
    SetOutputSize,
    SetStyleOption,
    SetSubtitle,
    SetTitle,
    SortRows,
    UnbindColumn,
)


def _with_transform_id(transform):
    if transform.transform_id:
        return transform
    return transform.model_copy(update={"transform_id": uuid.uuid4().hex[:8]})


def apply_operation(plan: FigurePlan, op: FigureOperation) -> FigurePlan:
    """Return a new FigurePlan with `op` applied. Never mutates `plan`."""
    if isinstance(op, SetFigureKind):
        return plan.model_copy(update={"figure_kind": op.new_kind})

    if isinstance(op, BindColumn):
        bindings = dict(plan.bindings)
        bindings[op.role] = ColumnBinding(columns=op.columns)
        return plan.model_copy(update={"bindings": bindings})

    if isinstance(op, UnbindColumn):
        bindings = dict(plan.bindings)
        bindings.pop(op.role, None)
        return plan.model_copy(update={"bindings": bindings})

    if isinstance(op, SetTitle):
        return plan.model_copy(update={"title": op.title})

    if isinstance(op, SetSubtitle):
        return plan.model_copy(update={"subtitle": op.subtitle})

    if isinstance(op, SetStyleOption):
        style = plan.style.model_copy(update={op.option: op.value})
        return plan.model_copy(update={"style": style})

    if isinstance(op, (AddFilter, SortRows, AggregateRows, CalculateColumn)):
        transform = _with_transform_id(op.transform)
        return plan.model_copy(update={"transformations": [*plan.transformations, transform]})

    if isinstance(op, LimitCategories):
        transform = _with_transform_id(op.transform)
        return plan.model_copy(update={"transformations": [*plan.transformations, transform]})

    if isinstance(op, RemoveFilter):
        remaining = [t for t in plan.transformations if t.transform_id != op.transform_id]
        return plan.model_copy(update={"transformations": remaining})

    if isinstance(op, AddAnnotation):
        return plan.model_copy(update={"annotations": [*plan.annotations, op.annotation]})

    if isinstance(op, RemoveAnnotation):
        remaining = [a for a in plan.annotations if a.annotation_id != op.annotation_id]
        return plan.model_copy(update={"annotations": remaining})

    if isinstance(op, SetOutputSize):
        style = plan.style.model_copy(update={"width": op.width, "height": op.height})
        return plan.model_copy(update={"style": style})

    raise ValueError(f"No apply rule for operation type {type(op).__name__}")


def apply_operations(plan: FigurePlan, ops: list[FigureOperation]) -> FigurePlan:
    for op in ops:
        plan = apply_operation(plan, op)
    return plan
