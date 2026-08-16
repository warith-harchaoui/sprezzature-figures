"""
Tests for sprezzature_figures.core.iterations and .history: recording an
edit, loading it back, undo/redo/revert/compare, and branch-by-revert, the
case where reverting to an earlier state and then editing again forks a new
history branch instead of overwriting the old one (specified in the
project's internal design plan, §12).

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from sprezzature_figures.core import (
    FigurePlan,
    allocate_iteration_dir,
    compare,
    create_project,
    current_record,
    list_iterations,
    load_iteration_record,
    redo,
    render_figure_to_project,
    revert_to,
    save_iteration_record,
    undo,
)
from sprezzature_figures.core.iterations import IterationRecord
from sprezzature_figures.core.projects import load_manifest, save_manifest

pytestmark = pytest.mark.slow


@pytest.fixture(autouse=True)
def _isolated_studio_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPREZZATURE_STUDIO_HOME", str(tmp_path / "studio-home"))


def _record(project_dir: Path, *, title: str, parent: str | None) -> IterationRecord:
    iteration_dir = allocate_iteration_dir(project_dir)
    data = [{"region": "North", "value": 42}]
    plan_before = FigurePlan(figure_kind="bar", title=f"before-{title}")
    plan_after = FigurePlan(figure_kind="bar", title=title)
    render = render_figure_to_project(
        "bar", data, project_id=project_dir.name, iteration_dir=iteration_dir, title=title
    )
    record = IterationRecord(
        iteration_id=iteration_dir.name,
        parent_iteration_id=parent,
        timestamp=datetime.now(timezone.utc).isoformat(),
        user_message=f"make it say {title}",
        assistant_summary="done",
        plan_before=plan_before,
        plan_after=plan_after,
        render_result=render,
    )
    save_iteration_record(iteration_dir, record)
    manifest = load_manifest(project_dir)
    manifest.current_iteration = int(record.iteration_id)
    save_manifest(project_dir, manifest)
    return record


def test_iteration_record_round_trips() -> None:
    # A saved record reloads with its plan, parentage, and a render on disk.
    project_dir = create_project("round trip")
    r1 = _record(project_dir, title="v1", parent=None)
    loaded = load_iteration_record(project_dir / "iterations" / r1.iteration_id)
    assert loaded.plan_after.title == "v1"
    assert loaded.parent_iteration_id is None
    assert loaded.render_result.source_path.exists()


def test_history_navigation_workflow() -> None:
    # One linear v1 -> v2 history exercised through the whole navigation API:
    # fresh state, listing order, undo/redo, their end-of-line None returns,
    # and compare.
    project_dir = create_project("navigation")
    assert current_record(project_dir) is None  # nothing recorded yet

    r1 = _record(project_dir, title="v1", parent=None)
    r2 = _record(project_dir, title="v2", parent=r1.iteration_id)

    # list_iterations is oldest-first; current is the latest record.
    assert [r.iteration_id for r in list_iterations(project_dir)] == [r1.iteration_id, r2.iteration_id]
    assert current_record(project_dir).plan_after.title == "v2"

    # undo walks to the parent; a second undo past the root returns None.
    assert undo(project_dir).plan_after.title == "v1"
    assert current_record(project_dir).iteration_id == r1.iteration_id
    assert undo(project_dir) is None

    # redo returns to the most-recent child; redo with none left returns None.
    assert redo(project_dir).iteration_id == r2.iteration_id
    assert redo(project_dir) is None

    # compare returns both records, in the order asked.
    a, b = compare(project_dir, r1.iteration_id, r2.iteration_id)
    assert (a.plan_after.title, b.plan_after.title) == ("v1", "v2")


def test_revert_then_new_record_creates_a_branch() -> None:
    project_dir = create_project("branch test")
    r1 = _record(project_dir, title="v1", parent=None)
    r2 = _record(project_dir, title="v2", parent=r1.iteration_id)

    reverted = revert_to(project_dir, r1.iteration_id)
    assert reverted.iteration_id == r1.iteration_id

    r3 = _record(project_dir, title="v3-branch", parent=r1.iteration_id)

    # r1 now has two children: r2 and r3, a branch point.
    children_of_r1 = [r for r in list_iterations(project_dir) if r.parent_iteration_id == r1.iteration_id]
    assert {r.iteration_id for r in children_of_r1} == {r2.iteration_id, r3.iteration_id}

    # _record() advances current to the newly created iteration (r3), not r2,
    # and undo from r3 goes to the shared parent r1, independent of r2's branch.
    assert current_record(project_dir).iteration_id == r3.iteration_id
    assert undo(project_dir).iteration_id == r1.iteration_id
