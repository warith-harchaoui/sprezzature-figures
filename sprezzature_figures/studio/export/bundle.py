"""
Build the full ``<project-name>.sprezzature.zip`` reproducibility archive
(plan §14):

    project-name.sprezzature.zip
    ├── README.md
    ├── manifest.json
    ├── figure-plan.json
    ├── data/
    │   └── transformed.csv
    ├── output/
    │   ├── figure.svg
    │   └── figure.png
    ├── reproduce.py
    └── accessibility/
        └── alt-text.txt

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import csv
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from sprezzature_figures.core.dataset import DatasetProfile
from sprezzature_figures.core.figure_plan import FigurePlan
from sprezzature_figures.core.rendering import RenderResult

from .alt_text import generate_alt_text
from .code import generate_reproduce_script
from .images import copy_output_images
from .manifest import build_export_manifest

_README_TEMPLATE = """\
# {project_name}

Exported from Sprezzature Studio.

- `figure-plan.json` -- the full FigurePlan (bindings, style, transformations).
- `data/transformed.csv` -- the data as imported (see figure-plan.json's
  `bindings` for which columns feed the figure).
- `output/` -- the rendered figure (SVG and/or PNG).
- `reproduce.py` -- regenerates `output/figure.svg` from the data using only
  the public `sprezzature-figures` package (`pip install sprezzature-figures`).
- `accessibility/alt-text.txt` -- a plain-language description of the figure.
"""


def _write_data_csv(data: list[dict[str, Any]], dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not data:
        dest.write_text("", encoding="utf-8")
        return
    fieldnames = list(data[0].keys())
    with dest.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)


def export_project(
    *,
    project_name: str,
    plan: FigurePlan,
    data: list[dict[str, Any]],
    render: RenderResult,
    exports_dir: Path,
    dataset: DatasetProfile | None = None,
) -> Path:
    """Build the reproducibility archive and write it into `exports_dir`
    (typically a project's own ``exports/`` directory -- never a shared
    location). Returns the path to the written .sprezzature.zip file.
    """
    exports_dir.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in project_name).strip("-") or "project"

    with tempfile.TemporaryDirectory(prefix="sprezzature-export-") as tmp:
        root = Path(tmp) / safe_name
        root.mkdir()

        (root / "README.md").write_text(_README_TEMPLATE.format(project_name=project_name), encoding="utf-8")
        (root / "figure-plan.json").write_text(plan.model_dump_json(indent=2), encoding="utf-8")
        (root / "manifest.json").write_text(
            json.dumps(build_export_manifest(project_name=project_name, plan=plan, render=render), indent=2),
            encoding="utf-8",
        )
        _write_data_csv(data, root / "data" / "transformed.csv")
        copy_output_images(render, root / "output")
        (root / "reproduce.py").write_text(generate_reproduce_script(plan), encoding="utf-8")
        (root / "accessibility").mkdir()
        (root / "accessibility" / "alt-text.txt").write_text(generate_alt_text(plan, dataset), encoding="utf-8")

        archive_path = exports_dir / f"{safe_name}.sprezzature.zip"
        archive_base = str(archive_path).removesuffix(".zip")
        built = shutil.make_archive(archive_base, "zip", root_dir=root.parent, base_dir=root.name)
        final_path = Path(built)
        if final_path != archive_path:
            final_path = final_path.rename(archive_path)
        return final_path
