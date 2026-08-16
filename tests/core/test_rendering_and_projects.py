"""
Tests for sprezzature_figures.core.rendering and .projects: atomic writes
(a file is written to a temporary path and only swapped into place once
complete, so a crash mid-write can never leave a half-written file behind),
isolated project workspaces, and the unified render-to-project pipeline.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from sprezzature_figures.core import (
    RenderResult,
    allocate_iteration_dir,
    atomic_write_bytes,
    atomic_write_text,
    create_project,
    load_manifest,
    projects_root,
    render_figure_to_project,
    render_preview,
    save_manifest,
    studio_home,
)


@pytest.fixture(autouse=True)
def _isolated_studio_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "studio-home"
    monkeypatch.setenv("SPREZZATURE_STUDIO_HOME", str(home))
    return home


def test_studio_home_respects_env_override() -> None:
    assert studio_home() == Path(os.environ["SPREZZATURE_STUDIO_HOME"])


def test_atomic_write_creates_parents_replaces_and_leaves_no_temp(tmp_path: Path) -> None:
    # Creates missing parent directories and writes the content.
    nested = tmp_path / "a" / "b" / "c.txt"
    atomic_write_text(nested, "hello")
    assert nested.read_text(encoding="utf-8") == "hello"

    # A second write replaces the file in place...
    atomic_write_text(nested, "second")
    assert nested.read_text(encoding="utf-8") == "second"

    # ...and byte writes leave no stray temp file behind (atomic rename).
    target = tmp_path / "out.bin"
    atomic_write_bytes(target, b"\x00\x01")
    assert [p for p in tmp_path.iterdir() if p.name not in {"out.bin", "a"}] == []


def test_create_project_sets_up_isolated_unique_layout() -> None:
    project_dir = create_project("My Project", source_name="revenue.csv")
    assert project_dir.parent == projects_root()
    for sub in ("source", "data", "iterations", "exports"):
        assert (project_dir / sub).is_dir()
    manifest = load_manifest(project_dir)
    assert manifest.name == "My Project"
    assert manifest.source_name == "revenue.csv"
    assert manifest.current_iteration == 0

    # Same name -> still a distinct project id and directory.
    other = create_project("My Project")
    assert other != project_dir
    assert load_manifest(other).project_id != manifest.project_id


def test_iteration_allocation_and_manifest_persistence() -> None:
    project_dir = create_project("Iter test")
    first = allocate_iteration_dir(project_dir)
    second = allocate_iteration_dir(project_dir)
    assert first.name == "0001"
    assert second.name == "0002"
    assert load_manifest(project_dir).current_iteration == 2

    # Manifest edits round-trip through save/load.
    manifest = load_manifest(project_dir)
    manifest.current_iteration = 7
    save_manifest(project_dir, manifest)
    assert load_manifest(project_dir).current_iteration == 7


@pytest.mark.slow
@pytest.mark.parametrize(
    "kind, data, is_vega",
    [
        # Vega-Lite kind renders through the spec pipeline.
        ("bar", [{"region": "North", "value": 42}, {"region": "South", "value": 28}], True),
        # Hand-authored SVG kind (no tabular data) uses the SVG path.
        ("waffle", None, False),
    ],
)
def test_render_figure_to_project_writes_only_inside_iteration_dir(kind, data, is_vega) -> None:
    project_dir = create_project(f"render {kind}")
    iteration_dir = allocate_iteration_dir(project_dir)
    result = render_figure_to_project(
        kind, data, project_id=project_dir.name, iteration_dir=iteration_dir, title="t"
    )
    assert isinstance(result, RenderResult)
    assert result.source_path.exists()
    assert result.preview_path.exists() and result.preview_path.stat().st_size > 0
    assert result.iteration_id == iteration_dir.name

    # Isolation (plan §8): every artifact lands inside the iteration dir, never
    # in assets/, web/, or the process cwd.
    assert iteration_dir in result.source_path.parents
    assert iteration_dir in result.preview_path.parents

    if is_vega:
        assert result.source_path.suffix == ".svg"
        assert result.preview_path.suffix == ".png"
        assert result.mime_type == "image/svg+xml"
        assert result.width > 0 and result.height > 0


def test_render_preview_rejects_unknown_renderer(tmp_path: Path) -> None:
    fake_source = tmp_path / "render.html"
    fake_source.write_text("<html></html>", encoding="utf-8")
    with pytest.raises(ValueError, match="No PNG preview conversion"):
        render_preview(fake_source, tmp_path / "preview.png", renderer="html")
