"""
FigurePlan: the source of truth for a figure being edited in Sprezzature
Studio (plan §1.2). Neither the conversation nor the rendered PNG is
authoritative -- only this Pydantic model is. Every accepted edit produces a
new FigurePlan version (see sprezzature_figures.core.iterations, Commit 12).

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .operations import Annotation, Transform


class UserIntent(BaseModel):
    """What the user is trying to show, extracted once from their request and
    the dataset profile (plan §10.1's IntentAnalysis -- reused here as the
    FigurePlan's `intent` field rather than duplicating the same shape under
    two names).
    """

    analytical_goal: Literal[
        "comparison",
        "trend",
        "distribution",
        "composition",
        "relationship",
        "flow",
        "hierarchy",
        "geography",
        "model_evaluation",
        "unknown",
    ] = Field(
        default="unknown",
        description=(
            "The single analytical question the figure should answer. Choose the "
            "closest: comparison (rank/contrast categories), trend (change over "
            "time), distribution (spread of one measure), composition (parts of a "
            "whole), relationship (correlation between measures), flow (movement "
            "between nodes), hierarchy (nested parts), geography (values on a map), "
            "model_evaluation (ML metrics). Use 'unknown' ONLY when the request is "
            "genuinely too vague to classify."
        ),
    )
    message_to_convey: str = Field(
        default="",
        description="One plain sentence stating the takeaway the user wants the reader to leave with.",
    )
    audience: str | None = Field(
        default=None,
        description="Who will read the figure (e.g. 'executives', 'engineers'), if the request implies one; else null.",
    )
    emphasis: list[str] = Field(
        default_factory=list,
        description="Specific values, categories, or series the user wants highlighted (e.g. ['France', 'Q4']).",
    )
    requested_constraints: list[str] = Field(
        default_factory=list,
        description="Explicit constraints the user stated: date ranges, top-N, filters, format (e.g. '16:9'), etc.",
    )
    required_columns: list[str] = Field(
        default_factory=list,
        description="Dataset column names the figure must use, drawn ONLY from the provided data profile -- never invented.",
    )
    ambiguities: list[str] = Field(
        default_factory=list,
        description="Points the request leaves unclear and that a human should confirm; empty if the request is clear.",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Your confidence, 0.0-1.0, that this analysis captures the user's actual intent.",
    )


class ColumnBinding(BaseModel):
    """The column(s) filling one data role (plan §3.1 RoleDefinition)."""

    columns: list[str] = Field(min_length=1)

    @property
    def column(self) -> str:
        """The single bound column, for roles where `multiple=False`."""
        return self.columns[0]


class StyleOptions(BaseModel):
    theme: Literal["light", "dark", "auto"] = "light"
    accessibility_mode: Literal["standard", "high_contrast", "colorblind_safe"] = "standard"
    width: int = 900
    height: int = 600
    font_scale: float = 1.0
    legend_position: Literal["top", "bottom", "left", "right", "none"] = "right"
    sort_order: Literal["none", "ascending", "descending", "custom"] = "none"
    number_format: str = ""
    date_format: str = ""
    highlight_values: list[str] = Field(default_factory=list)
    show_grid: bool = True
    show_labels: bool = True
    label_rotation: int = 0
    palette: str = "default"


class OutputOptions(BaseModel):
    format: Literal["svg", "png", "html"] = "svg"
    width: int | None = None
    height: int | None = None
    filename: str | None = None


class FigurePlan(BaseModel):
    """The single structured source of truth for one figure iteration."""

    version: int = 1
    figure_kind: str
    intent: UserIntent = Field(default_factory=UserIntent)
    bindings: dict[str, ColumnBinding] = Field(default_factory=dict)
    transformations: list[Transform] = Field(default_factory=list)
    title: str = ""
    subtitle: str | None = None
    source_note: str | None = None
    annotations: list[Annotation] = Field(default_factory=list)
    style: StyleOptions = Field(default_factory=StyleOptions)
    output: OutputOptions = Field(default_factory=OutputOptions)

    def bound_columns(self) -> set[str]:
        return {c for binding in self.bindings.values() for c in binding.columns}
