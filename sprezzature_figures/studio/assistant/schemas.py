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

    summary: str
    operations: list[FigureOperation] = Field(default_factory=list)
    expected_effect: str = ""
    requires_confirmation: bool = False
    confirmation_reason: str | None = None


class FigureRecommendation(BaseModel):
    """One reranked/explained candidate from a pre-filtered compatible-kind
    list (plan §6): the model may reorder, explain, title, and flag
    tradeoffs, but never invent a kind outside what it was given --
    recommend.explain_recommendations() drops anything that isn't in the
    candidate list it was actually handed.
    """

    kind: str
    reason: str
    suggested_title: str = ""
    tradeoff: str = ""


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
    ]
    severity: Literal["low", "medium", "high", "critical"]
    observation: str
    evidence: str = ""
    suggested_action: str = ""


class EditorialSuggestion(BaseModel):
    summary: str
    rationale: str = ""
    operation: FigureOperation | None = None


class VisualCritique(BaseModel):
    """Ralph's verdict on one rendered PNG (plan §10.3). Built here, not in
    the ralph/ package, because it's an LLM output contract like the other
    two -- ralph/critic.py consumes it, doesn't define it.
    """

    verdict: Literal["satisfied", "needs_changes", "blocked"]
    message_alignment_score: int = Field(ge=0, le=100)
    readability_score: int = Field(ge=0, le=100)
    visual_hierarchy_score: int = Field(ge=0, le=100)
    accessibility_score: int = Field(ge=0, le=100)
    data_fidelity_score: int = Field(ge=0, le=100)
    issues: list[VisualIssue] = Field(default_factory=list)
    safe_repairs: list[FigureOperation] = Field(default_factory=list)
    editorial_suggestions: list[EditorialSuggestion] = Field(default_factory=list)
    concise_summary: str = ""
