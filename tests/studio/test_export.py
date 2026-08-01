"""
Tests for sprezzature_figures.studio.export: the reproducibility archive,
including actually unzipping it and running reproduce.py in a fresh
directory to confirm it's genuinely standalone (plan §14).

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from sprezzature_figures.core import (
    ColumnBinding,
    ColumnProfile,
    DatasetProfile,
    FigurePlan,
    allocate_iteration_dir,
    create_project,
    render_figure_to_project,
)
from sprezzature_figures.studio.export import export_project, generate_alt_text
from sprezzature_figures.studio.export.code import generate_reproduce_script

pytestmark = pytest.mark.slow


@pytest.fixture(autouse=True)
def _isolated_studio_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPREZZATURE_STUDIO_HOME", str(tmp_path / "studio-home"))


def _profile() -> DatasetProfile:
    return DatasetProfile(
        dataset_id="d", fingerprint="f", source_name="t.csv", row_count=2, column_count=2,
        columns=[
            ColumnProfile(name="region", physical_dtype="object", semantic_type="categorical"),
            ColumnProfile(name="value", physical_dtype="int64", semantic_type="numeric"),
        ],
    )


def _export(tmp_path: Path) -> Path:
    data = [{"region": "North", "value": 42}, {"region": "South", "value": 28}]
    plan = FigurePlan(
        figure_kind="bar",
        title="Revenue",
        bindings={"region": ColumnBinding(columns=["region"]), "value": ColumnBinding(columns=["value"])},
    )
    project_dir = create_project("export test")
    iteration_dir = allocate_iteration_dir(project_dir)
    render = render_figure_to_project(
        "bar", data, project_id=project_dir.name, iteration_dir=iteration_dir, title=plan.title
    )
    return export_project(
        project_name="export test",
        plan=plan,
        data=data,
        render=render,
        exports_dir=project_dir / "exports",
        dataset=_profile(),
    )


def test_export_project_writes_a_zip_with_the_expected_structure(tmp_path: Path) -> None:
    archive = _export(tmp_path)
    assert archive.exists() and archive.suffix == ".zip"

    with zipfile.ZipFile(archive) as z:
        names = {Path(n).relative_to(Path(n).parts[0]).as_posix() for n in z.namelist() if not n.endswith("/")}
    expected = {
        "README.md",
        "manifest.json",
        "figure-plan.json",
        "data/transformed.csv",
        "output/figure.svg",
        "output/figure.png",
        "reproduce.py",
        "accessibility/alt-text.txt",
    }
    assert expected <= names


def test_export_project_writes_only_into_the_given_exports_dir(tmp_path: Path) -> None:
    archive = _export(tmp_path)
    assert archive.parent.name == "exports"
    assert list(archive.parent.iterdir()) == [archive]


def test_reproduce_script_actually_regenerates_the_figure(tmp_path: Path) -> None:
    archive = _export(tmp_path)
    extract_dir = tmp_path / "extracted"
    with zipfile.ZipFile(archive) as z:
        z.extractall(extract_dir)

    project_root = next(p for p in extract_dir.iterdir() if p.is_dir())
    assert (project_root / "reproduce.py").exists()

    result = subprocess.run(
        [sys.executable, "reproduce.py"], cwd=project_root, capture_output=True, text=True, timeout=60
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (project_root / "output" / "figure.svg").exists()
    # The regenerated file should be non-trivial, not an empty stub.
    assert (project_root / "output" / "figure.svg").stat().st_size > 100


def test_generate_reproduce_script_uses_only_the_public_api() -> None:
    plan = FigurePlan(figure_kind="bar", bindings={"region": ColumnBinding(columns=["region"])})
    script = generate_reproduce_script(plan)
    assert "from sprezzature_figures import make_figure" in script
    assert "sprezzature_figures.studio" not in script
    assert "sprezzature_figures.core" not in script


def test_generate_alt_text_ends_each_sentence_with_a_period() -> None:
    plan = FigurePlan(figure_kind="bar", title="Revenue", bindings={"region": ColumnBinding(columns=["region"])})
    text = generate_alt_text(plan, _profile())
    assert ". Based on" in text  # regression: sentences must not run together
    assert text.endswith(".")
