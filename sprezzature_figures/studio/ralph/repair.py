"""
Apply a VisualCritique's safe repairs to a FigurePlan (plan §11.2). Do not
confuse this with sprezzature_figures.studio.assistant.repair, which fixes
malformed JSON coming back from the model: this module fixes the *figure*
itself, and only ever with operations that ``policy.is_safe_repair()``
actually approves, regardless of what the critique claims is safe.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from sprezzature_figures.core.figure_plan import FigurePlan
from sprezzature_figures.core.operations import FigureOperation
from sprezzature_figures.core.validation import validate_operation
from sprezzature_figures.studio.assistant.schemas import VisualCritique

from .apply import apply_operations
from .policy import is_safe_repair


def safe_repairs_from_critique(critique: VisualCritique, *, dataset=None) -> list[FigureOperation]:
    """The subset of `critique.safe_repairs` that both the policy and
    ordinary operation validation actually approve.
    """
    return [
        op
        for op in critique.safe_repairs
        if is_safe_repair(op) and not validate_operation(op, dataset=dataset)
    ]


def apply_safe_repairs(
    plan: FigurePlan, critique: VisualCritique, *, dataset=None
) -> tuple[FigurePlan, list[FigureOperation]]:
    """Apply the approved safe repairs from `critique` to `plan`.

    Returns
    -------
    (new_plan, applied_operations)
    """
    approved = safe_repairs_from_critique(critique, dataset=dataset)
    if not approved:
        return plan, []
    return apply_operations(plan, approved), approved
