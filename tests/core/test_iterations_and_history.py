"""
Tests for sprezzature_figures.core.iterations and .history: recording,
loading, undo/redo/revert/compare, and branch-by-revert (plan §12).

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


def test_save_and_load_iteration_record_round_trips() -> None:
    project_dir = create_project("round trip")
    r1 = _record(project_dir, title="v1", parent=None)
    loaded = load_iteration_record(project_dir / "iterations" / r1.iteration_id)
    assert loaded.plan_after.title == "v1"
    assert loaded.parent_iteration_id is None
    assert loaded.render_result.source_path.exists()


def test_list_iterations_returns_oldest_first() -> None:
    project_dir = create_project("list test")
    r1 = _record(project_dir, title="v1", parent=None)
    r2 = _record(project_dir, title="v2", parent=r1.iteration_id)
    records = list_iterations(project_dir)
    assert [r.iteration_id for r in records] == [r1.iteration_id, r2.iteration_id]


def test_current_record_none_for_fresh_project() -> None:
    project_dir = create_project("fresh")
    assert current_record(project_dir) is None


def test_undo_moves_to_parent() -> None:
    project_dir = create_project("undo test")
    r1 = _record(project_dir, title="v1", parent=None)
    _record(project_dir, title="v2", parent=r1.iteration_id)

    assert current_record(project_dir).plan_after.title == "v2"
    result = undo(project_dir)
    assert result.plan_after.title == "v1"
    assert current_record(project_dir).plan_after.title == "v1"


def test_undo_at_root_returns_none() -> None:
    project_dir = create_project("undo at root")
    _record(project_dir, title="v1", parent=None)
    undo(project_dir)
    assert undo(project_dir) is None


def test_redo_moves_to_most_recent_child() -> None:
    project_dir = create_project("redo test")
    r1 = _record(project_dir, title="v1", parent=None)
    r2 = _record(project_dir, title="v2", parent=r1.iteration_id)
    undo(project_dir)
    assert current_record(project_dir).iteration_id == r1.iteration_id
    result = redo(project_dir)
    assert result.iteration_id == r2.iteration_id


def test_redo_with_no_children_returns_none() -> None:
    project_dir = create_project("redo none")
    _record(project_dir, title="v1", parent=None)
    assert redo(project_dir) is None


def test_revert_then_new_record_creates_a_branch() -> None:
    project_dir = create_project("branch test")
    r1 = _record(project_dir, title="v1", parent=None)
    r2 = _record(project_dir, title="v2", parent=r1.iteration_id)

    reverted = revert_to(project_dir, r1.iteration_id)
    assert reverted.iteration_id == r1.iteration_id

    r3 = _record(project_dir, title="v3-branch", parent=r1.iteration_id)

    # r1 now has two children: r2 and r3 -- a branch point.
    children_of_r1 = [r for r in list_iterations(project_dir) if r.parent_iteration_id == r1.iteration_id]
    assert {r.iteration_id for r in children_of_r1} == {r2.iteration_id, r3.iteration_id}

    # _record() advances current to the newly created iteration (r3), not r2.
    assert current_record(project_dir).iteration_id == r3.iteration_id

    # undo from r3 goes back to their shared parent r1, not to r2 -- r3's
    # branch is independent of r2's.
    result = undo(project_dir)
    assert result.iteration_id == r1.iteration_id


def test_compare_returns_both_records() -> None:
    project_dir = create_project("compare test")
    r1 = _record(project_dir, title="v1", parent=None)
    r2 = _record(project_dir, title="v2", parent=r1.iteration_id)
    a, b = compare(project_dir, r1.iteration_id, r2.iteration_id)
    assert a.plan_after.title == "v1"
    assert b.plan_after.title == "v2"
