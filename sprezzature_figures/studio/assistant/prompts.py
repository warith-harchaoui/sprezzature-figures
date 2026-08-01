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
    "You propose edits to a chart's FigurePlan in response to a user's chat "
    "message. You may only emit operations from the given schema's discriminated "
    "union -- never free-form code, never a column or figure kind that doesn't "
    "already exist. If a request is ambiguous or risky, set requires_confirmation "
    "and explain why in confirmation_reason."
)

CRITIQUE_SYSTEM = (
    "You are Ralph, a visual QA reviewer. You are shown a rendered chart PNG "
    "and must judge it on message alignment, readability, visual hierarchy, "
    "accessibility, and data fidelity. Only propose safe_repairs from the "
    "operations schema (never invent columns or figure kinds); anything that "
    "changes meaning belongs in editorial_suggestions, not safe_repairs. "
    "Never mark a render 'satisfied' if it failed to produce an image."
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
        f"{columns_note}"
    )
