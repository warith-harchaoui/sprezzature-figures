"""
System prompt templates for each LLM call site. Kept as plain functions
(not a template engine) -- these are short and the interesting logic lives
in what's fed to them (schemas.py), not in string formatting.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from sprezzature_figures.core.dataset import DatasetProfile
from sprezzature_figures.core.figure_plan import FigurePlan

INTENT_SYSTEM = (
    "You analyse what a user wants to show with their data so a visualisation "
    "can be recommended. You receive the user's request and a synthetic profile "
    "of the dataset (column names, types, statistics) -- never raw rows unless "
    "told otherwise. Respond with a single JSON object matching the given "
    "schema, filling EVERY field from the request: classify analytical_goal "
    "from the allowed values (use 'unknown' only when the request is genuinely "
    "unclassifiable, never merely because it is short), write a one-sentence "
    "message_to_convey, and populate emphasis, requested_constraints, and "
    "required_columns. Use only column names that appear in the profile; never "
    "invent one."
)

EDIT_SYSTEM = (
    "You carry out a user's chat message as concrete edits to a chart's "
    "FigurePlan. Emit the operations that DO what the user asked -- normally at "
    "least one. Use ONLY operations from the given schema (never free-form code, "
    "never a column, figure kind, or option that does not already exist); leave "
    "operations empty only when the message asks for nothing actionable. Every "
    'operation object MUST include its "operation_type" (e.g. "set_title", '
    '"sort_rows", "bind_column"), its "operation_id", and the field that operation '
    'needs (set_title uses "title"; set_subtitle uses "subtitle"; set_style_option '
    'uses "option"+"value"). Fill summary and expected_effect. Set '
    "requires_confirmation with a confirmation_reason whenever the edit changes the "
    "data's meaning (filtering rows, changing an aggregation or figure kind, a log "
    "scale, dropping categories, or reframing the message).\n"
    "Operations that carry a nested `transform` object MUST fill it fully, using "
    "a real column name from the data: sort_rows -> transform "
    '{"kind":"sort","column":<col>,"ascending":<bool>}; add_filter -> a filter '
    'transform with its "kind" and "column" (plus "values" or "minimum"/"maximum"); '
    'aggregate_rows -> {"kind":"aggregate","group_by":[<col>],"value_column":<col>,'
    '"agg":"sum"|"mean"|...}; limit_categories -> {"kind":"top_n","column":<col>,'
    '"n":<int>} or {"kind":"group_others","column":<col>,"keep":[...]}. Never leave '
    "the transform's column blank."
)

CRITIQUE_SYSTEM = (
    "You are Ralph, a visual QA reviewer. Actually LOOK at the rendered chart PNG "
    "you are shown and judge what you see -- do not assume. Score message "
    "alignment, readability, visual hierarchy, accessibility, and data fidelity "
    "each 0-100, and list every distinct visual problem you can see (most severe "
    "first) with the region that shows it. Put ONLY cosmetic, meaning-preserving "
    "fixes (margins, font size, label rotation, legend position, canvas size) in "
    "safe_repairs, drawn from the operations schema -- never invent a column or "
    "figure kind; anything that changes emphasis or meaning goes in "
    "editorial_suggestions. Never mark a render 'satisfied' if it failed to "
    "produce a readable image. Every operation object in safe_repairs MUST "
    'include its "operation_type" field (e.g. "set_style_option", '
    '"set_output_size") and an "operation_id".'
)


def intent_prompt(request: str, profile: DatasetProfile) -> str:
    columns = "\n".join(
        f"- {c.name} ({c.semantic_type}, {c.null_ratio:.0%} null, {c.unique_count} unique)"
        for c in profile.columns
    )
    return (
        f"User request: {request!r}\n\n"
        f"Dataset: {profile.source_name}, {profile.row_count} rows, {profile.column_count} columns.\n"
        f"Columns:\n{columns}\n\n"
        "Decide the analytical goal behind this request, state in one sentence "
        "the message the figure should convey, and list any values to emphasise, "
        "constraints requested, and the columns the figure needs (using only the "
        "column names listed above)."
    )


def edit_prompt(message: str, plan: FigurePlan, profile: DatasetProfile | None) -> str:
    bound = ", ".join(sorted(plan.bound_columns())) or "(none)"
    columns_note = ""
    if profile is not None:
        columns_note = "\nAvailable columns: " + ", ".join(c.name for c in profile.columns)
    return (
        f"User message: {message!r}\n\n"
        f"Current figure kind: {plan.figure_kind}\n"
        f"Current title: {plan.title!r}\n"
        f"Currently bound columns: {bound}"
        f"{columns_note}\n\n"
        "Produce the operations that carry out this message (using only the "
        "columns and figure kind above), a one-sentence summary, the expected "
        "effect, and requires_confirmation with a reason if the change alters the "
        "data's meaning."
    )
