"""
sprezzature-figures — FastAPI HTTP surface.

Exposes :func:`sprezzature_figures.make_figure` (and the figure registry
behind ``--list`` / ``get_figure_definition``) over HTTP, so the 124 chart
types can be rendered from any language, not just Python.

What ships here
----------------
- ``GET /health`` — liveness probe.
- ``GET /kinds`` — list registered chart kinds, optionally filtered by
  ``status`` (``stable`` / ``experimental`` / ``legacy`` / ``unavailable``).
- ``GET /kinds/{kind}`` — full :class:`~sprezzature_figures.catalog.FigureDefinition`
  for one kind (required/optional data roles, default size, renderer, …).
- ``POST /render/{kind}`` — render a chart and return the file bytes
  directly (``Content-Type`` set from the requested format). Body omits
  ``data`` to fall back to that figure's built-in demo rows, same as
  ``make-figure <kind>`` with no ``--data``.
- ``POST /redraw`` — send a picture of somebody else's chart and get it
  back redrawn here, with the diagnosis that justified each change. Needs
  a vision model (the ``[local]`` extra plus a running Ollama); answers
  503 with what to install when there isn't one.

Install the extra to get the runtime dependencies::

    pip install 'sprezzature-figures[api]'

Then run the app with any ASGI server (the standard interface Python web
servers and frameworks use to talk to each other; Uvicorn below is one
implementation of it)::

    uvicorn sprezzature_figures.api:app --host 0.0.0.0 --port 8000

Usage Example
-------------
>>> # Start the server:
>>> #   uvicorn sprezzature_figures.api:app --reload
>>> # List stable chart kinds:
>>> #   curl http://localhost:8000/kinds?status=stable
>>> # Render the demo treemap as SVG:
>>> #   curl -X POST http://localhost:8000/render/treemap -o treemap.svg
>>> # Full OpenAPI docs at http://localhost:8000/docs

Author
------
Warith HARCHAOUI <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import os
import tempfile
import threading
from pathlib import Path
from typing import Any, Literal

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import RedirectResponse, Response
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "The FastAPI HTTP surface requires the [api] extra. "
        "Install with: pip install 'sprezzature-figures[api]'"
    ) from exc

from pydantic import BaseModel, Field

from . import __version__ as _VERSION
from .catalog import FigureDefinition, get_figure_definition, list_kinds, resolve_kind
from .make_figure import _demo_data_for, make_figure

_MEDIA_TYPES: dict[str, str] = {
    "svg": "image/svg+xml",
    "png": "image/png",
    "pdf": "application/pdf",
    "jpg": "image/jpeg",
    "html": "text/html",
}

app = FastAPI(
    title="Sprezzature Figures API",
    description=(
        "HTTP surface for sprezzature-figures: render any of 124 "
        "publication-quality chart types from JSON rows."
    ),
    version=_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

# SPREZZATURE_RENDER_SCALE (read by scripts/_render.py's rasterisation choke
# point) is a *process-wide* environment variable, not a per-call argument --
# threading a --scale-equivalent through every one of the ~90 hand-authored
# generator signatures was never done for the CLI either (see _render.py's
# own docstring). That's fine for a one-shot CLI process, but this server
# handles requests concurrently: two /render calls with different `scale`
# values could otherwise race on the same env var and one would render at
# the other's scale. Serialize the set-env / render / restore-env critical
# section so concurrent requests can never interleave it.
_render_lock = threading.Lock()


class RenderRequest(BaseModel):
    """Body for ``POST /render/{kind}``."""

    data: list[dict[str, Any]] | None = Field(
        default=None,
        description="Input rows. Omit to render that figure's built-in demo data.",
    )
    title: str = Field(default="", description="Chart title.")
    format: Literal["svg", "png", "pdf", "jpg", "html"] = Field(
        default="svg", description="Output format; picks the response Content-Type."
    )
    scale: float | None = Field(
        default=None,
        description="Upsample raster/PDF output N times for hi-DPI. Ignored for svg/html.",
    )
    options: dict[str, Any] = Field(
        default_factory=dict,
        description="Extra generator-specific kwargs forwarded as-is (e.g. subtitle, width, "
        "height, bin_count) -- see FIGURES.md for what each kind accepts.",
    )


class RedrawRequest(BaseModel):
    """Body for ``POST /redraw``."""

    image_base64: str = Field(
        description=(
            "The picture of the chart to redraw, base64-encoded. PNG, JPEG, GIF, WebP "
            "or SVG; a screenshot is the usual case."
        )
    )
    data: list[dict[str, Any]] | None = Field(
        default=None,
        description=(
            "Your real rows, keyed by the target kind's role names. Omit and you get "
            "the redesign on sample data -- the right chart, not your numbers."
        ),
    )
    kind: str | None = Field(
        default=None, description="Skip the model's choice of chart type and use this one."
    )
    title: str | None = Field(default=None, description="Override the title.")
    hint: str = Field(
        default="", description="Anything worth telling the model about the image."
    )
    language: Literal["en", "fr"] = Field(
        default="en", description="Language of the provenance caption written onto the figure."
    )
    format: Literal["svg", "png", "pdf", "jpg", "html"] = Field(
        default="svg", description="Output format of the returned figure."
    )
    options: dict[str, Any] = Field(
        default_factory=dict, description="Extra generator-specific kwargs forwarded as-is."
    )


class RedrawResponse(BaseModel):
    """What ``POST /redraw`` answers: the figure, and where it came from."""

    kind: str = Field(description="The canonical chart kind it was drawn as.")
    data_origin: Literal["your-data", "read-from-image", "demo"] = Field(
        description=(
            "Where the numbers came from. 'demo' means this is the redesign on sample "
            "data -- look at it, do not publish it."
        )
    )
    changes: list[str] = Field(
        default_factory=list, description="What this redraw does differently, costliest first."
    )
    warnings: list[str] = Field(
        default_factory=list, description="What to know before trusting this figure."
    )
    reading: dict[str, Any] = Field(
        default_factory=dict, description="The full ChartReading the vision model returned."
    )
    media_type: str = Field(description="Content type of `figure_base64`.")
    figure_base64: str = Field(description="The rendered figure, base64-encoded.")


@app.get("/health", tags=["meta"], operation_id="health")
def health() -> dict:
    """Simple liveness probe -- no dependency check, just proves the app is up."""
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    """Redirect the bare root to the interactive API docs."""
    return RedirectResponse(url="/docs")


@app.get("/kinds", tags=["meta"], operation_id="list_kinds")
def kinds(
    status: Literal["stable", "experimental", "legacy", "unavailable"] | None = None,
) -> list[str]:
    """List registered chart kinds, optionally filtered by ``status``."""
    return list_kinds(status=status)


@app.get("/kinds/{kind}", tags=["meta"], response_model=FigureDefinition, operation_id="get_kind")
def kind_definition(kind: str) -> FigureDefinition:
    """Full registry entry for one chart kind: data roles, renderer, default size, …"""
    canonical = resolve_kind(kind)
    if canonical is None:
        raise HTTPException(status_code=404, detail=f"No such kind: {kind!r}. See GET /kinds.")
    return get_figure_definition(canonical)


@app.post("/render/{kind}", tags=["actions"], operation_id="render_figure")
def render(kind: str, body: RenderRequest = RenderRequest()) -> Response:
    """Render a chart and return the file bytes with the matching Content-Type."""
    canonical = resolve_kind(kind)
    if canonical is None:
        raise HTTPException(status_code=404, detail=f"No such kind: {kind!r}. See GET /kinds.")

    data = body.data if body.data is not None else _demo_data_for(canonical)
    kwargs: dict[str, Any] = dict(body.options)
    kwargs["title"] = body.title

    suffix = f".{body.format}"
    with tempfile.TemporaryDirectory(prefix="sprezzature-figures-api-") as tmp:
        out_path = Path(tmp) / f"{canonical}{suffix}"
        kwargs["out"] = str(out_path)

        with _render_lock:
            prior_scale = os.environ.get("SPREZZATURE_RENDER_SCALE")
            if body.scale is not None:
                os.environ["SPREZZATURE_RENDER_SCALE"] = repr(body.scale)
            try:
                try:
                    result_path = make_figure(canonical, data, **kwargs)
                except (ValueError, AttributeError) as exc:
                    raise HTTPException(status_code=422, detail=str(exc)) from exc
                except (FileNotFoundError, RuntimeError) as exc:
                    raise HTTPException(status_code=500, detail=str(exc)) from exc
                content = result_path.read_bytes()
            finally:
                if prior_scale is None:
                    os.environ.pop("SPREZZATURE_RENDER_SCALE", None)
                else:
                    os.environ["SPREZZATURE_RENDER_SCALE"] = prior_scale

    media_type = _MEDIA_TYPES[body.format]
    return Response(content=content, media_type=media_type)


@app.post("/redraw", tags=["actions"], operation_id="redraw_figure")
def redraw_route(body: RedrawRequest) -> RedrawResponse:
    """Redraw a chart from a picture of it, and say what was changed and why.

    A picture of a chart carries its design legibly and its numbers rarely.
    This reads the design -- what kind of chart it is, what makes it hard to
    read -- and never invents the numbers: send ``data`` for a real figure,
    or read ``data_origin`` to see that you got the redesign on sample rows.
    """
    import base64
    import binascii

    try:
        image = base64.b64decode(body.image_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"image_base64 is not base64: {exc}") from exc

    try:
        from .redraw import redraw as _redraw
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise HTTPException(status_code=503, detail=f"redraw is unavailable: {exc}") from exc

    suffix = f".{body.format}"
    with tempfile.TemporaryDirectory(prefix="sprezzature-figures-redraw-") as tmp:
        out_path = Path(tmp) / f"redrawn{suffix}"
        try:
            result = _redraw(
                image,
                out=out_path,
                data=body.data,
                kind=body.kind,
                title=body.title,
                hint=body.hint,
                language=body.language,
                **body.options,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except ImportError as exc:
            raise HTTPException(
                status_code=503,
                detail=(
                    "redraw needs a vision model. Install "
                    "'sprezzature-figures[local]' and run Ollama. "
                    f"({exc})"
                ),
            ) from exc
        except (FileNotFoundError, RuntimeError) as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        payload = result.output.read_bytes()

    return RedrawResponse(
        kind=result.kind,
        data_origin=result.data_origin,
        changes=result.changes,
        warnings=result.warnings,
        reading=result.reading.model_dump() if result.reading is not None else {},
        media_type=_MEDIA_TYPES[body.format],
        figure_base64=base64.b64encode(payload).decode("ascii"),
    )
