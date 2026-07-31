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
    ] = "unknown"
    message_to_convey: str = ""
    audience: str | None = None
    emphasis: list[str] = Field(default_factory=list)
    requested_constraints: list[str] = Field(default_factory=list)
    required_columns: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    confidence: float = 0.0


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
