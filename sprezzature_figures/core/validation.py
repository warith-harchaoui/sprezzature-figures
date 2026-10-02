"""
Validation for FigureOperations and FigurePlans against what's actually
known: the dataset's columns and the target figure's declared role/style
contract. Plan §10.2: refuse any operation referencing a nonexistent column,
an incompatible figure kind, an undeclared option, or an out-of-bounds value
-- before it is ever applied.

Author
------
Warith HARCHAOUI <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from ..catalog.models import FigureDefinition, ValidationIssue
from .dataset import DatasetProfile
from .figure_plan import FigurePlan, StyleOptions
from .operations import (
    AddFilter,
    AggregateRows,
    AggregateTransform,
    BindColumn,
    CalculateColumn,
    CalculateDerived,
    FigureOperation,
    FilterByRange,
    FilterByValue,
    FilterTemporal,
    GroupOthers,
    LimitCategories,
    RenameDisplay,
    SetStyleOption,
    SortRows,
    SortTransform,
    TopN,
    Transform,
)

_STYLE_FIELDS = set(StyleOptions.model_fields)


def _transform_columns(transform: Transform) -> list[str]:
    """
    Every dataset column a transform names, so the caller can check they exist.

    Dispatch is by class, not by the ``kind`` string. ``Transform`` is a
    discriminated union and each member already declares its own
    ``kind: Literal[...]``, but reading that string into a local and testing
    it with ``in`` throws the discrimination away: a type checker then sees
    ``transform.column`` on the whole union and cannot tell which members
    have it. Thirty-four warnings said so. ``isinstance`` narrows, so a
    member added later without a branch here is a type error rather than an
    ``AttributeError`` the first time that transform reaches validation.
    """
    if isinstance(transform, AggregateTransform):
        return [*transform.group_by, transform.value_column]
    if isinstance(transform, CalculateDerived):
        return [transform.left, transform.right]
    if isinstance(
        transform,
        (
            FilterByValue,
            FilterByRange,
            FilterTemporal,
            SortTransform,
            RenameDisplay,
            TopN,
            GroupOthers,
        ),
    ):
        return [transform.column]
    return []


def _check_columns_exist(
    columns: list[str], dataset: DatasetProfile | None, field: str
) -> list[ValidationIssue]:
    if dataset is None:
        return []
    known = {c.name for c in dataset.columns}
    return [
        ValidationIssue(
            field=field, message=f"column {c!r} does not exist in the dataset", severity="error"
        )
        for c in columns
        if c not in known
    ]


def validate_operation(
    op: FigureOperation, *, dataset: DatasetProfile | None = None
) -> list[ValidationIssue]:
    """Issues that would make `op` unsafe or meaningless to apply.

    Only checks what's knowable independent of the rest of the plan (column
    existence, declared style option names). Cross-plan concerns (e.g. "does
    removing this filter leave the plan internally consistent") belong to the
    engine applying operations, not this pure check.
    """
    issues: list[ValidationIssue] = []

    if isinstance(op, BindColumn):
        issues += _check_columns_exist(op.columns, dataset, "columns")
    elif isinstance(op, SetStyleOption):
        if op.option not in _STYLE_FIELDS:
            issues.append(
                ValidationIssue(
                    field="option",
                    message=f"{op.option!r} is not a declared StyleOptions field",
                    severity="error",
                )
            )
    elif isinstance(op, (AddFilter, SortRows, AggregateRows, CalculateColumn, LimitCategories)):
        issues += _check_columns_exist(_transform_columns(op.transform), dataset, "transform")

    return issues


def validate_plan(
    plan: FigurePlan,
    *,
    dataset: DatasetProfile | None = None,
    definition: FigureDefinition | None = None,
) -> list[ValidationIssue]:
    """Issues with a FigurePlan as a whole: missing required role bindings,
    bound columns that don't exist in the dataset.
    """
    issues: list[ValidationIssue] = []

    if definition is not None:
        for role in definition.required_roles:
            if role.name not in plan.bindings:
                issues.append(
                    ValidationIssue(
                        field=role.name,
                        message=f"required role {role.name!r} is not bound for kind={plan.figure_kind!r}",
                        severity="error",
                    )
                )

    if dataset is not None:
        issues += _check_columns_exist(sorted(plan.bound_columns()), dataset, "bindings")
        for transform in plan.transformations:
            issues += _check_columns_exist(
                _transform_columns(transform), dataset, "transformations"
            )

    return issues
