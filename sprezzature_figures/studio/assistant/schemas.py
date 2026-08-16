"""
Structured LLM output contracts (plan §10). The model is never allowed to
return free-form JSON validated on faith -- every call site names one of
these types, and sprezzature_figures.studio.assistant.repair enforces it.

IntentAnalysis is not redefined here: it's sprezzature_figures.core.
figure_plan.UserIntent, which already has exactly this shape (plan's own
§4.1 and §10.1 name the same fields under two different type names; this
package treats them as one type rather than duplicating it).

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from sprezzature_figures.core.operations import FigureOperation


class EditProposal(BaseModel):
    """What the assistant wants to do to the current FigurePlan, in response
    to one chat message. Never applied without passing
    core.validate_operation() on every operation first.
    """

    summary: str = Field(
        description="One sentence, in plain language, describing the change you propose to the figure."
    )
    operations: list[FigureOperation] = Field(
        default_factory=list,
        description=(
            "The concrete, typed edits to apply, in order. Each must reference only "
            "columns present in the dataset and options the figure declares -- never "
            "invent a column, figure kind, or option. Empty if nothing should change."
        ),
    )
    expected_effect: str = Field(
        default="",
        description="What the reader will see differently after these operations are applied.",
    )
    requires_confirmation: bool = Field(
        default=False,
        description=(
            "True if the change alters the data's meaning (filtering rows, changing an "
            "aggregation or figure kind, log scale, dropping categories) and so needs "
            "the user's explicit OK before applying."
        ),
    )
    confirmation_reason: str | None = Field(
        default=None,
        description="If requires_confirmation is true, the one-line reason the user should confirm; else null.",
    )


class FigureRecommendation(BaseModel):
    """One reranked/explained candidate from a pre-filtered compatible-kind
    list (plan §6): the model may reorder, explain, title, and flag
    tradeoffs, but never invent a kind outside what it was given --
    recommend.explain_recommendations() drops anything that isn't in the
    candidate list it was actually handed.
    """

    kind: str = Field(
        description="The figure kind, copied EXACTLY from the candidate list you were given -- never a kind outside it."
    )
    reason: str = Field(
        description="Why this figure suits the user's intent and this dataset, in one concrete sentence."
    )
    suggested_title: str = Field(
        default="",
        description="A specific, editorially-worded title for this figure (not a generic label).",
    )
    tradeoff: str = Field(
        default="",
        description="The main limitation or reading difficulty of this figure for this data.",
    )


class RecommendationSet(BaseModel):
    recommendations: list[FigureRecommendation] = Field(default_factory=list)


class VisualIssue(BaseModel):
    category: Literal[
        "cropping",
        "overlap",
        "contrast",
        "labeling",
        "legend",
        "hierarchy",
        "density",
        "scale",
        "message",
        "accessibility",
        "data_fidelity",
    ] = Field(description="Which kind of visual problem this is, from the fixed list.")
    severity: Literal["low", "medium", "high", "critical"] = Field(
        description="How much this problem hurts the figure: low (cosmetic) to critical (misleads or breaks it)."
    )
    observation: str = Field(
        description="What you actually see in the image that is wrong, stated concretely."
    )
    evidence: str = Field(
        default="",
        description="The specific region or element of the image that shows the problem.",
    )
    suggested_action: str = Field(
        default="", description="The single most useful fix for this problem, phrased as an action."
    )


class EditorialSuggestion(BaseModel):
    summary: str = Field(
        description="An editorial improvement the user might choose (not a safe auto-fix), in one sentence."
    )
    rationale: str = Field(
        default="", description="Why this would strengthen the figure's message."
    )
    operation: FigureOperation | None = Field(
        default=None,
        description="The single typed edit that would carry out this suggestion, if it maps to one; else null.",
    )


class VisualCritique(BaseModel):
    """Ralph's verdict on one rendered PNG (plan §10.3). Built here, not in
    the ralph/ package, because it's an LLM output contract like the other
    two -- ralph/critic.py consumes it, doesn't define it.
    """

    verdict: Literal["satisfied", "needs_changes", "blocked"] = Field(
        description=(
            "Overall judgement: 'satisfied' (ship it), 'needs_changes' (fixable "
            "problems remain), or 'blocked' (the render failed or is unusable)."
        )
    )
    message_alignment_score: int = Field(
        ge=0, le=100, description="0-100: how well the figure conveys the user's intended message."
    )
    readability_score: int = Field(
        ge=0,
        le=100,
        description="0-100: how easily labels, values, and text can be read at this size.",
    )
    visual_hierarchy_score: int = Field(
        ge=0, le=100, description="0-100: how clearly the most important element stands out."
    )
    accessibility_score: int = Field(
        ge=0,
        le=100,
        description="0-100: contrast, colour-blind safety, and legibility for all readers.",
    )
    data_fidelity_score: int = Field(
        ge=0,
        le=100,
        description="0-100: how faithfully the figure represents the data without distortion.",
    )
    issues: list[VisualIssue] = Field(
        default_factory=list,
        description="Every distinct visual problem you can see, most severe first.",
    )
    safe_repairs: list[FigureOperation] = Field(
        default_factory=list,
        description=(
            "Only cosmetic, meaning-preserving fixes safe to apply automatically "
            "(margins, font size, label rotation, legend position, canvas size). "
            "NEVER anything that changes the data or its meaning."
        ),
    )
    editorial_suggestions: list[EditorialSuggestion] = Field(
        default_factory=list,
        description="Changes worth offering the user but that need their decision (they alter emphasis or meaning).",
    )
    concise_summary: str = Field(
        default="",
        description="A two-to-three line plain-language summary of the verdict and the top fixes.",
    )
