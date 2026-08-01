"""
Copy a render's output artifacts into an export archive's ``output/``
directory under canonical names (plan §14).

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import shutil
from pathlib import Path

from sprezzature_figures.core.rendering import RenderResult


def copy_output_images(render: RenderResult, output_dir: Path) -> list[Path]:
    """Copy the render's source artifact and PNG preview into
    `output_dir` as `figure.<ext>` and `figure.png`. Returns the written
    paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []

    source_dest = output_dir / f"figure{render.source_path.suffix}"
    shutil.copyfile(render.source_path, source_dest)
    written.append(source_dest)

    if render.preview_path != render.source_path:
        preview_dest = output_dir / "figure.png"
        shutil.copyfile(render.preview_path, preview_dest)
        written.append(preview_dest)

    return written
