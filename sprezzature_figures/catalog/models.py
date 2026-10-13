"""
Pydantic models describing a chart type in the figure registry.

Author
------
Warith HARCHAOUI <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ..options import OptionDefinition

FigureStatus = Literal["stable", "experimental", "legacy", "unavailable"]
RendererKind = Literal["svg", "html"]
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
    #: Every keyword the generator accepts beyond its rows, keyed by name:
    #: type, default, allowed values and the prose from its own docstring.
    #: Frozen here by ``tools/build_figures_catalog.py`` so a caller can
    #: list a figure's options without importing the generator module;
    #: ``tests/test_figure_options.py`` re-derives it and fails on drift.
    options_schema: dict[str, OptionDefinition] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("options_schema", mode="before")
    @classmethod
    def _name_options_after_their_key(cls, value: object) -> object:
        """Let ``figures.json`` key an option by name without repeating it inside.

        The JSON is read far more often than it is written (every CLI
        ``--describe``, every ``GET /kinds``), and a name stored twice is a
        name that can disagree with itself. The key is the name.
        """
        if not isinstance(value, dict):
            return value
        return {
            name: payload if not isinstance(payload, dict) else {"name": name, **payload}
            for name, payload in value.items()
        }


class ValidationIssue(BaseModel):
    """One reason a `make_figure()` call is invalid or risky."""

    field: str
    message: str
    severity: Literal["error", "warning"] = "error"
