"""
What Ralph is and isn't allowed to do on its own (plan §11.2-§11.4).

Safe repairs are cosmetic, meaning-preserving fixes Ralph may apply without
asking: a bigger margin, a larger font, rotated labels, a moved legend, a
bigger canvas, stronger contrast, a repositioned annotation. Everything
that changes what the data actually says, such as a different figure kind,
a filter, an aggregation, a top-N, or a group-others, requires explicit
user confirmation, even if the model itself did not flag it as such. That
redundancy is deliberate: a second line of defense in case the model
forgets to set `requires_confirmation`.

Author
------
Warith HARCHAOUI <warithmetics@deraison.ai>
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

#: StyleOptions fields a safe repair may **not** touch, each with the reason.
#:
#: Written on 2026-11-01, when counting found fourteen fields on
#: :class:`StyleOptions` and eight in the set above. The other six were
#: unclassified: :func:`is_safe_repair` answered False for them, so the
#: behaviour was right, but nobody had chosen it -- the default had. That is
#: the shape `sprezzature-maps` guards against in its own option registry,
#: where ``OPTIONS`` and ``NOT_AN_OPTION`` together have to account for every
#: keyword a renderer takes, so a new knob must be classified by somebody.
#:
#: The reasons matter more than the membership, because the next field will be
#: classified by reading them:
#:
#: - ``sort_order`` -- the order of categories *is* a claim. Which bar is
#:   first says which matters, and re-sorting a chart unattended rewrites that
#:   claim without anyone agreeing to it.
#: - ``highlight_values`` -- the same, more directly: emphasis is the message.
#: - ``palette`` -- a diverging ramp read as sequential, or the reverse, tells
#:   a different story about the same numbers. Cosmetic in general and not
#:   here.
#: - ``number_format`` and ``date_format`` -- rounding is a claim about
#:   precision. 1 234.5 shown as 1.2k is not the same statement.
#: - ``theme`` -- the one that is arguably cosmetic, and the one worth
#:   deciding deliberately rather than by omission. A critique that says the
#:   text is hard to read against this background could be answered by
#:   switching it, which would be a real repair. It stays here until somebody
#:   chooses otherwise, because widening what an unattended loop may change is
#:   a decision and not a tidy-up.
_NEEDS_CONFIRMATION_STYLE_OPTIONS = {
    "date_format",
    "highlight_values",
    "number_format",
    "palette",
    "sort_order",
    "theme",
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
