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
from .history import compare, current_record, redo, revert_to, undo
from .iterations import (
    IterationRecord,
    get_iteration,
    list_iterations,
    load_iteration_record,
    save_iteration_record,
)
from .operations import (
    Annotation,
    FigureOperation,
    Transform,
)
from .projects import (
    ProjectManifest,
    allocate_iteration_dir,
    create_project,
    load_manifest,
    projects_root,
    save_manifest,
    studio_home,
    write_iteration_json,
)
from .rendering import (
    RenderResult,
    atomic_write_bytes,
    atomic_write_text,
    render_figure_to_project,
    render_preview,
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
    "IterationRecord",
    "OutputOptions",
    "ProjectManifest",
    "RenderResult",
    "StyleOptions",
    "Transform",
    "UserIntent",
    "allocate_iteration_dir",
    "atomic_write_bytes",
    "atomic_write_text",
    "compare",
    "create_project",
    "current_record",
    "get_iteration",
    "list_iterations",
    "load_iteration_record",
    "load_manifest",
    "projects_root",
    "redo",
    "render_figure_to_project",
    "render_preview",
    "revert_to",
    "save_iteration_record",
    "save_manifest",
    "studio_home",
    "undo",
    "validate_operation",
    "validate_plan",
    "write_iteration_json",
]
