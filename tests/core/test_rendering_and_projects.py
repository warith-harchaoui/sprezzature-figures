"""
Tests for sprezzature_figures.core.rendering and .projects: atomic writes,
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


def test_studio_home_respects_env_override(tmp_path: Path) -> None:
    assert studio_home() == Path(os.environ["SPREZZATURE_STUDIO_HOME"])


def test_atomic_write_text_creates_parents_and_content(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b" / "c.txt"
    atomic_write_text(target, "hello")
    assert target.read_text(encoding="utf-8") == "hello"


def test_atomic_write_bytes_leaves_no_temp_file_behind(tmp_path: Path) -> None:
    target = tmp_path / "out.bin"
    atomic_write_bytes(target, b"\x00\x01")
    leftovers = [p for p in tmp_path.iterdir() if p.name != "out.bin"]
    assert leftovers == []


def test_atomic_write_replaces_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "f.txt"
    atomic_write_text(target, "first")
    atomic_write_text(target, "second")
    assert target.read_text(encoding="utf-8") == "second"


def test_create_project_sets_up_isolated_layout() -> None:
    project_dir = create_project("My Project", source_name="revenue.csv")
    assert project_dir.parent == projects_root()
    for sub in ("source", "data", "iterations", "exports"):
        assert (project_dir / sub).is_dir()
    manifest = load_manifest(project_dir)
    assert manifest.name == "My Project"
    assert manifest.source_name == "revenue.csv"
    assert manifest.current_iteration == 0


def test_create_project_ids_are_unique_even_for_same_name() -> None:
    a = create_project("Duplicate")
    b = create_project("Duplicate")
    assert a != b
    assert load_manifest(a).project_id != load_manifest(b).project_id


def test_allocate_iteration_dir_numbers_sequentially_and_bumps_manifest() -> None:
    project_dir = create_project("Iter test")
    first = allocate_iteration_dir(project_dir)
    second = allocate_iteration_dir(project_dir)
    assert first.name == "0001"
    assert second.name == "0002"
    assert load_manifest(project_dir).current_iteration == 2


def test_save_manifest_round_trips() -> None:
    project_dir = create_project("Round trip")
    manifest = load_manifest(project_dir)
    manifest.current_iteration = 7
    save_manifest(project_dir, manifest)
    assert load_manifest(project_dir).current_iteration == 7


@pytest.mark.slow
def test_render_figure_to_project_vega_lite_kind_produces_svg_and_png() -> None:
    project_dir = create_project("Render test")
    iteration_dir = allocate_iteration_dir(project_dir)
    data = [{"region": "North", "value": 42}, {"region": "South", "value": 28}]
    result = render_figure_to_project(
        "bar", data, project_id=project_dir.name, iteration_dir=iteration_dir, title="t"
    )
    assert isinstance(result, RenderResult)
    assert result.source_path.exists() and result.source_path.suffix == ".svg"
    assert result.preview_path.exists() and result.preview_path.suffix == ".png"
    assert result.width > 0 and result.height > 0
    assert result.mime_type == "image/svg+xml"
    assert result.iteration_id == iteration_dir.name


@pytest.mark.slow
def test_render_figure_to_project_hand_authored_svg_kind_also_works() -> None:
    project_dir = create_project("Waffle render test")
    iteration_dir = allocate_iteration_dir(project_dir)
    result = render_figure_to_project(
        "waffle", None, project_id=project_dir.name, iteration_dir=iteration_dir
    )
    assert result.source_path.exists()
    assert result.preview_path.exists()
    assert result.preview_path.stat().st_size > 0


@pytest.mark.slow
def test_render_figure_to_project_writes_only_inside_iteration_dir() -> None:
    """Nothing from a render should ever land in assets/, web/, or the
    process cwd (plan §8's isolation requirement).
    """
    project_dir = create_project("Isolation test")
    iteration_dir = allocate_iteration_dir(project_dir)
    data = [{"region": "North", "value": 1}]
    result = render_figure_to_project(
        "bar", data, project_id=project_dir.name, iteration_dir=iteration_dir
    )
    assert iteration_dir in result.source_path.parents
    assert iteration_dir in result.preview_path.parents


def test_render_preview_rejects_unknown_renderer(tmp_path: Path) -> None:
    fake_source = tmp_path / "render.html"
    fake_source.write_text("<html></html>", encoding="utf-8")
    with pytest.raises(ValueError, match="No PNG preview conversion"):
        render_preview(fake_source, tmp_path / "preview.png", renderer="html")
