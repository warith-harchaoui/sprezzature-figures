"""
Dataset profiling models: what the Studio knows about an imported CSV/XLSX
before any figure is chosen. Populated by sprezzature_figures.studio.ingest
(not built yet); this module only declares the shape.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

SemanticType = Literal[
    "numeric",
    "categorical",
    "text",
    "datetime",
    "boolean",
    "identifier",
    "latitude",
    "longitude",
    "percentage",
    "currency",
    "url",
    "email",
]


class DataWarning(BaseModel):
    """One issue noticed while profiling a dataset (not necessarily fatal)."""

    column: str | None = None
    message: str
    severity: Literal["info", "warning", "error"] = "warning"


class ColumnProfile(BaseModel):
    """Everything known about a single column without sending it to an LLM."""

    name: str
    physical_dtype: str
    semantic_type: SemanticType
    null_count: int = 0
    null_ratio: float = 0.0
    unique_count: int = 0
    unique_ratio: float = 0.0
    sample_values: list[Any] = Field(default_factory=list)
    minimum: float | str | None = None
    maximum: float | str | None = None
    mean: float | None = None
    median: float | None = None
    quantiles: dict[str, float] = Field(default_factory=dict)
    inferred_unit: str | None = None
    likely_identifier: bool = False
    likely_sensitive: bool = False


class DatasetProfile(BaseModel):
    """The synthetic summary of an imported dataset — what actually gets sent
    to an LLM for intent analysis and recommendation (plan §1.4: never the
    raw rows, unless the user has explicitly opted in to sending samples).
    """

    dataset_id: str
    fingerprint: str
    source_name: str
    sheet_name: str | None = None
    row_count: int
    column_count: int
    columns: list[ColumnProfile] = Field(default_factory=list)
    warnings: list[DataWarning] = Field(default_factory=list)

    def column(self, name: str) -> ColumnProfile | None:
        return next((c for c in self.columns if c.name == name), None)
