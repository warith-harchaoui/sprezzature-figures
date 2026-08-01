"""
Unified rendering: turns a figure kind + data into a RenderResult with both
the source artifact and a PNG preview, using atomic writes so a reader never
sees a half-written file. Never depends on the studio extras (pandas,
nicegui, ...) -- only vl_convert, already a core dependency, is needed to
convert SVG to PNG.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from ..catalog.models import ValidationIssue
from ..make_figure import get_figure_definition, make_figure

# Renderers whose source artifact needs conversion to get a PNG preview.
_SVG_LIKE_RENDERERS = {"vega_lite", "vega", "svg"}


class RenderResult(BaseModel):
    """Everything downstream (history, export, the Ralph loop) needs about
    one render: where the artifact lives, where its PNG preview lives, and
    what (if anything) was off about it.
    """

    project_id: str
    iteration_id: str
    figure_kind: str
    source_path: Path
    preview_path: Path
    mime_type: str
    width: int
    height: int
    warnings: list[ValidationIssue] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


def atomic_write_bytes(path: Path, data: bytes) -> Path:
    """Write `data` to `path` atomically: write to a sibling temp file, then
    rename over the destination, so a crash mid-write never leaves a
    truncated file at `path`.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp_name, path)
    finally:
        Path(tmp_name).unlink(missing_ok=True)
    return path


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> Path:
    return atomic_write_bytes(path, text.encode(encoding))


def svg_to_png_bytes(svg_text: str, *, scale: float = 2.0) -> bytes:
    """Rasterize an SVG string to PNG bytes via vl_convert.

    `scale` defaults to 2x so previews stay crisp on high-density displays
    (a VLM inspecting the preview also benefits from the extra resolution).
    """
    import vl_convert as vlc

    from ..fonts import register_vl_convert

    register_vl_convert()
    return vlc.svg_to_png(svg_text, scale=scale)


def render_preview(source_path: Path, preview_path: Path, *, renderer: str) -> Path:
    """Produce a PNG preview at `preview_path` from an already-rendered
    `source_path`, atomically.

    Parameters
    ----------
    source_path : Path
        The figure's rendered artifact (.svg or .png depending on renderer).
    preview_path : Path
        Where to write the PNG preview.
    renderer : str
        The FigureDefinition's declared renderer ("vega_lite", "vega",
        "svg", "matplotlib", "html").

    Raises
    ------
    ValueError
        If `renderer` has no known preview conversion path (e.g. "html" --
        would need a headless-browser screenshot, not implemented here).
    """
    if renderer in _SVG_LIKE_RENDERERS:
        svg_text = source_path.read_text(encoding="utf-8")
        return atomic_write_bytes(preview_path, svg_to_png_bytes(svg_text))
    if renderer == "matplotlib" and source_path.suffix.lower() == ".png":
        return atomic_write_bytes(preview_path, source_path.read_bytes())
    if source_path.suffix.lower() == ".png":
        return atomic_write_bytes(preview_path, source_path.read_bytes())
    raise ValueError(
        f"No PNG preview conversion available for renderer={renderer!r} "
        f"(source {source_path.name}). Supported: {_SVG_LIKE_RENDERERS} and direct .png output."
    )


def _png_dimensions(png_bytes: bytes) -> tuple[int, int]:
    """Width/height from a PNG's IHDR chunk, without an imaging library."""
    if png_bytes[:8] != b"\x89PNG\r\n\x1a\n" or len(png_bytes) < 24:
        return (0, 0)
    width = int.from_bytes(png_bytes[16:20], "big")
    height = int.from_bytes(png_bytes[20:24], "big")
    return (width, height)


def render_figure_to_project(
    kind: str,
    data: list[dict[str, Any]],
    *,
    project_id: str,
    iteration_dir: Path,
    **kwargs: Any,
) -> RenderResult:
    """Render `kind` with `data` into an isolated iteration directory and
    return a RenderResult carrying both the source artifact and its PNG
    preview. This is the one place that ties the registry (make_figure),
    atomic writes, and PNG conversion together, so nothing in the studio
    ever writes into assets/, web/, or a shared working directory.

    Parameters
    ----------
    kind : str
        Registered figure kind (see sprezzature_figures.list_kinds()).
    data : list[dict[str, Any]]
        Rows forwarded to make_figure().
    project_id : str
        The owning project's id (recorded on the result, not used for
        pathing here -- callers pass an already-resolved iteration_dir).
    iteration_dir : Path
        Directory to render into; must already exist (see
        sprezzature_figures.core.projects.allocate_iteration_dir).
    **kwargs
        Forwarded to make_figure() (title, style options, etc.).

    Returns
    -------
    RenderResult
    """
    definition = get_figure_definition(kind)
    extension = "svg" if definition.renderer in _SVG_LIKE_RENDERERS else "png"
    source_path = iteration_dir / f"render.{extension}"

    result_path = make_figure(kind, data, out=str(source_path), **kwargs)

    preview_path = iteration_dir / "preview.png"
    render_preview(result_path, preview_path, renderer=definition.renderer)
    width, height = _png_dimensions(preview_path.read_bytes())

    return RenderResult(
        project_id=project_id,
        iteration_id=iteration_dir.name,
        figure_kind=kind,
        source_path=result_path,
        preview_path=preview_path,
        mime_type="image/svg+xml" if extension == "svg" else "image/png",
        width=width,
        height=height,
        metadata={"renderer": definition.renderer, "status": definition.status},
    )
