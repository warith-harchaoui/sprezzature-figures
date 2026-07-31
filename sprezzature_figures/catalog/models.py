"""
Pydantic models describing a chart type in the figure registry.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

FigureStatus = Literal["stable", "experimental", "legacy", "unavailable"]
RendererKind = Literal["vega_lite", "vega", "svg", "matplotlib", "html"]
ColumnType = Literal[
    "numeric",
    "categorical",
    "text",
    "datetime",
    "boolean",
    "latitude",
    "longitude",
    "identifier",
]


class RoleDefinition(BaseModel):
    """A single data role a figure needs bound to a column (e.g. 'x', 'value')."""

    name: str
    label: str
    accepted_types: list[ColumnType] = Field(default_factory=list)
    required: bool = True
    multiple: bool = False
    description: str = ""


class FigureDefinition(BaseModel):
    """Everything the dispatcher and the (future) recommendation engine need
    to know about one chart kind, decoupled from its filename and function
    name so those can stay whatever they historically are on disk.
    """

    kind: str
    label: str
    aliases: list[str] = Field(default_factory=list)
    category: str = "Uncategorized"
    description: str = ""
    intents: list[str] = Field(default_factory=list)
    status: FigureStatus = "legacy"
    renderer: RendererKind = "svg"
    module: str
    callable_name: str
    required_roles: list[RoleDefinition] = Field(default_factory=list)
    optional_roles: list[RoleDefinition] = Field(default_factory=list)
    supported_outputs: list[str] = Field(default_factory=lambda: ["svg"])
    min_rows: int | None = None
    max_recommended_rows: int | None = None
    max_recommended_categories: int | None = None
    default_width: int = 900
    default_height: int = 600
    options_schema: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class ValidationIssue(BaseModel):
    """One reason a `make_figure()` call is invalid or risky."""

    field: str
    message: str
    severity: Literal["error", "warning"] = "error"
