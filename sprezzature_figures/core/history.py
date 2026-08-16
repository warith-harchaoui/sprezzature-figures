"""
Undo/redo/revert/compare over a project's recorded iterations (plan §12).
All of it is a thin layer on top of two facts already on disk: the
project manifest's `current_iteration` pointer (projects.py) and each
IterationRecord's `parent_iteration_id` (iterations.py). There is no
separate branch-tracking structure: reverting to an old version and then
recording a new one is what creates a branch, automatically, because the
new record's parent is whatever was current at the time.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from pathlib import Path

from .iterations import IterationRecord, get_iteration, list_iterations
from .projects import load_manifest, save_manifest


def current_record(project_dir: Path) -> IterationRecord | None:
    manifest = load_manifest(project_dir)
    if manifest.current_iteration == 0:
        return None
    return get_iteration(project_dir, f"{manifest.current_iteration:04d}")


def _set_current(project_dir: Path, iteration_id: str) -> None:
    manifest = load_manifest(project_dir)
    manifest.current_iteration = int(iteration_id)
    save_manifest(project_dir, manifest)


def undo(project_dir: Path) -> IterationRecord | None:
    """Move the project's current pointer to the current iteration's
    parent. Returns the parent record, or None if there's nothing to undo
    (no current iteration, or already at the root).
    """
    record = current_record(project_dir)
    if record is None or record.parent_iteration_id is None:
        return None
    parent = get_iteration(project_dir, record.parent_iteration_id)
    _set_current(project_dir, parent.iteration_id)
    return parent


def redo(project_dir: Path) -> IterationRecord | None:
    """Move the current pointer to the most recently created child of the
    current iteration. Returns None if there's nothing to redo.
    """
    record = current_record(project_dir)
    current_id = record.iteration_id if record is not None else None
    children = [r for r in list_iterations(project_dir) if r.parent_iteration_id == current_id]
    if not children:
        return None
    child = max(children, key=lambda r: r.iteration_id)
    _set_current(project_dir, child.iteration_id)
    return child


def revert_to(project_dir: Path, iteration_id: str) -> IterationRecord:
    """Set the current pointer directly to `iteration_id`. The next
    recorded iteration will have this one as its parent, forming a branch
    if other children already exist off of it.
    """
    record = get_iteration(project_dir, iteration_id)
    _set_current(project_dir, iteration_id)
    return record


def compare(
    project_dir: Path, iteration_id_a: str, iteration_id_b: str
) -> tuple[IterationRecord, IterationRecord]:
    """Both records for side-by-side display (plan §12: for the MVP, a
    computed visual diff is not required).
    """
    return get_iteration(project_dir, iteration_id_a), get_iteration(project_dir, iteration_id_b)
