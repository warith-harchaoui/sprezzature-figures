"""
What Ralph is and isn't allowed to do on its own (plan §11.2-§11.4).

Safe repairs are cosmetic, meaning-preserving fixes Ralph may apply without
asking: a bigger margin, a larger font, rotated labels, a moved legend, a
bigger canvas, stronger contrast, a repositioned annotation. Everything
that changes what the data says -- a different figure kind, a filter, an
aggregation, a top-N, a group-others -- requires explicit user confirmation,
even if the model itself didn't flag it as such (defense in depth against a
model that forgets to set `requires_confirmation`).

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from sprezzature_figures.core.operations import (
    AddAnnotation,
    AddFilter,
    AggregateRows,
    BindColumn,
    CalculateColumn,
    FigureOperation,
    LimitCategories,
    RemoveFilter,
    SetFigureKind,
    SetOutputSize,
    SetStyleOption,
    SortRows,
    UnbindColumn,
)

#: StyleOptions fields a safe repair may touch -- all cosmetic/legibility,
#: none of them change what the data says.
_SAFE_STYLE_OPTIONS = {
    "width",
    "height",
    "font_scale",
    "legend_position",
    "label_rotation",
    "show_grid",
    "show_labels",
    "accessibility_mode",
}

#: Operation types that reshape what the figure shows and always require
#: confirmation, regardless of what the model itself claims.
_CONFIRMATION_REQUIRED_TYPES = (
    SetFigureKind,
    AddFilter,
    RemoveFilter,
    AggregateRows,
    LimitCategories,
    CalculateColumn,
)


def is_safe_repair(op: FigureOperation) -> bool:
    """True if `op` is a cosmetic, meaning-preserving fix Ralph may apply
    without asking (plan §11.2).
    """
    if isinstance(op, SetStyleOption):
        return op.option in _SAFE_STYLE_OPTIONS
    if isinstance(op, SetOutputSize):
        return True
    # Adding an annotation is cosmetic; it never changes a value.
    return isinstance(op, AddAnnotation)


def requires_confirmation(op: FigureOperation) -> bool:
    """True if `op` must be confirmed by the user before being applied,
    per plan §11.3 -- independent of the model's own
    `requires_confirmation` flag on the enclosing EditProposal.
    """
    if isinstance(op, _CONFIRMATION_REQUIRED_TYPES):
        return True
    # Rebinding a role changes which column drives the figure -- treat as
    # data-shape-changing, same bucket as a filter/aggregate.
    if isinstance(op, (BindColumn, UnbindColumn)):
        return True
    if isinstance(op, SortRows):
        return False  # reordering rows for display is not a meaning change
    return False


def can_apply_automatically(op: FigureOperation) -> bool:
    """True if `op` may be applied without confirmation -- the complement
    of `requires_confirmation`, named separately so call sites read as
    intent ("can I just do this?") rather than a double negative.
    """
    return not requires_confirmation(op)
