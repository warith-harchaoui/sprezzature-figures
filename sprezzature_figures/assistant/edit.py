"""
Chat-driven plan edits: turn one user message into an EditProposal (plan
§10.2), then drop any operation that fails validation (say, a reference to a
column that does not exist, or an undeclared style option) before it is ever
handed to whatever applies operations to a FigurePlan (the Ralph engine,
Commit 10).

Author
------
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

from sprezzature_figures.core.dataset import DatasetProfile
from sprezzature_figures.core.figure_plan import FigurePlan
from sprezzature_figures.core.operations import FigureOperation, SetFigureOption
from sprezzature_figures.core.validation import validate_operation
from sprezzature_figures.render_options import figure_option_is_valid

from .client import LLMClient
from .prompts import EDIT_SYSTEM, edit_prompt
from .schemas import EditProposal


def _dedup_operations(operations: list[FigureOperation]) -> list[FigureOperation]:
    """Drop operations that are identical apart from their id/reason metadata,
    keeping the first. A local model sometimes emits the same edit twice (two
    `set_style_option`s for one request); applying both is at best redundant
    and, for a non-idempotent op, wrong."""
    seen: set[str] = set()
    unique: list[FigureOperation] = []
    for op in operations:
        key = op.model_dump_json(exclude={"operation_id", "reason"})
        if key not in seen:
            seen.add(key)
            unique.append(op)
    return unique


def propose_edit(
    client: LLMClient,
    message: str,
    plan: FigurePlan,
    *,
    dataset: DatasetProfile | None = None,
) -> EditProposal:
    """Ask the model for an EditProposal, then strip any operation that
    references a nonexistent column or an undeclared style option. The
    proposal's `summary`/`expected_effect` text is left untouched even if
    operations were dropped -- the caller (Ralph, Commit 10) decides how to
    surface a partially-rejected proposal to the user.
    """
    result = client.chat_text(
        edit_prompt(message, plan, dataset),
        system=EDIT_SYSTEM,
        response_model=EditProposal,
        temperature=0.1,
    )
    assert isinstance(result, EditProposal)

    # A figure option is checked against the current kind's declaration:
    # an option the kind does not take would be dropped at render time,
    # and the reply would announce a change the picture never shows.
    valid_operations = [
        op
        for op in result.operations
        if not validate_operation(op, dataset=dataset)
        and (
            not isinstance(op, SetFigureOption)
            or figure_option_is_valid(plan.figure_kind, op.name, op.value)
        )
    ]
    return result.model_copy(update={"operations": _dedup_operations(valid_operations)})
