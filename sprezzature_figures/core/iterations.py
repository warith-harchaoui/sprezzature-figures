"""
IterationRecord: an immutable record of one accepted change (plan §12).
Persisted alongside the render artifacts Commit 8 already writes into each
``iterations/NNNN/`` directory -- this module adds ``plan.json`` (the
resulting FigurePlan, kept as its own file so other consumers don't need
to parse the whole record) and ``event.json`` (the full record, including
the render result and critique).

Undo/redo/branch all fall out of one simple fact: every IterationRecord
names its ``parent_iteration_id``. "Undo" moves the project's current
pointer to the parent; "redo" moves it to the most recent child; reverting
to an old version and then recording a new one naturally creates a branch,
since the new record's parent is whatever was current at the time -- no
separate branch-tracking structure to keep in sync.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .figure_plan import FigurePlan
from .operations import FigureOperation
from .rendering import RenderResult, atomic_write_text


class IterationRecord(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    iteration_id: str
    parent_iteration_id: str | None
    timestamp: str
    user_message: str | None = None
    assistant_summary: str = ""
    plan_before: FigurePlan
    proposed_operations: list[FigureOperation] = Field(default_factory=list)
    accepted_operations: list[FigureOperation] = Field(default_factory=list)
    plan_after: FigurePlan
    render_result: RenderResult
    critique: dict[str, Any] | None = (
        None  # VisualCritique.model_dump(); avoids a core->studio import
    )
    status: Literal["success", "failed", "cancelled"] = "success"


def save_iteration_record(iteration_dir: Path, record: IterationRecord) -> None:
    """Write an IterationRecord to its iteration directory (render.svg/
    preview.png are already there via render_figure_to_project). Atomic
    per file.
    """
    atomic_write_text(iteration_dir / "plan.json", record.plan_after.model_dump_json(indent=2))
    atomic_write_text(iteration_dir / "event.json", record.model_dump_json(indent=2))


def load_iteration_record(iteration_dir: Path) -> IterationRecord:
    """Reconstruct an IterationRecord previously written by
    save_iteration_record.
    """
    return IterationRecord.model_validate_json(
        (iteration_dir / "event.json").read_text(encoding="utf-8")
    )


def list_iterations(project_dir: Path) -> list[IterationRecord]:
    """Every recorded iteration for a project, oldest first."""
    iterations_dir = project_dir / "iterations"
    if not iterations_dir.is_dir():
        return []
    dirs = sorted(
        (p for p in iterations_dir.iterdir() if p.is_dir() and (p / "event.json").exists()),
        key=lambda p: p.name,
    )
    return [load_iteration_record(p) for p in dirs]


def get_iteration(project_dir: Path, iteration_id: str) -> IterationRecord:
    return load_iteration_record(project_dir / "iterations" / iteration_id)
