"""
sprezzature_figures.core — domain models for Sprezzature Studio.

The FigurePlan (not the conversation, not the rendered image) is the source
of truth for a figure under construction. This package only declares models
and pure validation; the render/ingest/assistant/Ralph engines that populate
and act on them live in sprezzature_figures.studio (later commits).

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from .dataset import ColumnProfile, DatasetProfile, DataWarning
from .figure_plan import ColumnBinding, FigurePlan, OutputOptions, StyleOptions, UserIntent
from .operations import (
    Annotation,
    FigureOperation,
    Transform,
)
from .validation import validate_operation, validate_plan

__all__ = [
    "Annotation",
    "ColumnBinding",
    "ColumnProfile",
    "DataWarning",
    "DatasetProfile",
    "FigureOperation",
    "FigurePlan",
    "OutputOptions",
    "StyleOptions",
    "Transform",
    "UserIntent",
    "validate_operation",
    "validate_plan",
]
