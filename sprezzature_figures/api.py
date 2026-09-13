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


class RecommendRequest(BaseModel):
    """Body for ``POST /recommend``."""

    data: list[dict[str, Any]] = Field(
        description="The rows you want to chart. One flat object per record."
    )
    limit: int = Field(default=5, ge=1, le=50, description="How many candidates to return.")
    goal: (
        Literal[
            "comparison",
            "trend",
            "distribution",
            "composition",
            "relationship",
            "flow",
            "hierarchy",
            "geography",
            "model_evaluation",
        ]
        | None
    ) = Field(
        default=None,
        description=(
            "What the reader should take away. Supply it whenever you can: without a "
            "goal many kinds tie at the top, because readability alone rarely separates "
            "them."
        ),
    )


class FigureCandidate(BaseModel):
    """One chart kind this data can fill, with the columns already bound."""

    kind: str = Field(description="Pass this to `render_figure`.")
    score: float = Field(description="Readability score for this data, higher is better.")
    bindings: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "role -> your column name. Rename your columns to the role names (or send "
            "both) so `render_figure` can find them."
        ),
    )


@app.get(
    "/health",
    tags=["meta"],
    operation_id="health",
    summary="Check that this figure server is up",
)
def health() -> dict:
    """Liveness probe: proves the process is answering, nothing more.

    Call this only to diagnose a connection problem. It checks no
    dependency, so a healthy answer does not promise that a render will
    succeed.
    """
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    """Redirect the bare root to the interactive API docs."""
    return RedirectResponse(url="/docs")


@app.get(
    "/kinds",
    tags=["meta"],
    operation_id="list_kinds",
    summary="List every chart type this server can draw",
)
def kinds(
    status: Literal["stable", "experimental", "legacy", "unavailable"] | None = None,
) -> list[str]:
    """The catalogue of chart kinds, as canonical names.

    Call this FIRST whenever you do not already know the exact kind name
    you need: `render_figure` takes a name from this list, not a free
    description, and guessing one that does not exist fails the call. The
    catalogue is a closed set of 127 hand-authored chart types, not an
    x/y/kind combinator.

    Pass `status="stable"` for the render-verified subset. Once you have a
    name, `get_kind` tells you which columns its rows must carry.
    """
    return list_kinds(status=status)


@app.get(
    "/kinds/{kind}",
    tags=["meta"],
    response_model=FigureDefinition,
    operation_id="get_kind",
    summary="Show which columns one chart type needs",
)
def kind_definition(kind: str) -> FigureDefinition:
    """Everything the registry knows about one kind: its data roles first.

    Call this BEFORE `render_figure` when you are unsure how to shape the
    rows. `required_roles` names the keys every row must carry (a bar chart
    wants `region` and `value`, not `x` and `y`); `optional_roles` may be
    left out and the figure still renders. Also carries aliases, default
    canvas size, and which output formats the kind supports.

    Accepts a kind name or any of its aliases, case-insensitively, with
    hyphens, underscores and spaces interchangeable.
    """
    canonical = resolve_kind(kind)
    if canonical is None:
        raise HTTPException(status_code=404, detail=f"No such kind: {kind!r}. See GET /kinds.")
    return get_figure_definition(canonical)


@app.post(
    "/render/{kind}",
    tags=["actions"],
    operation_id="render_figure",
    summary="Draw a chart from rows of data",
)
def render(kind: str, body: RenderRequest = RenderRequest()) -> Response:
    """Render one of 127 chart types and return the file bytes.

    This is the tool for "chart this", "plot this", "draw me a bar chart /
    treemap / sankey", "visualise this data", "make a figure". You supply
    the rows; the house palette, typography and layout are applied here.

    `kind` must be a name from `list_kinds`. Shape the rows to that kind's
    `required_roles` (`get_kind` lists them) -- a row is a flat object whose
    keys are role names. Omit `data` entirely to render that kind's built-in
    demo rows, which is the fast way to show someone what a kind looks like
    before committing real data to it.

    Do NOT use this to improve a chart that already exists as a picture:
    that is `redraw_figure`.
    """
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


@app.post(
    "/redraw",
    tags=["actions"],
    operation_id="redraw_figure",
    summary="Redraw someone else's chart from a picture of it",
)
def redraw_route(body: RedrawRequest) -> RedrawResponse:
    """Take an image of an existing chart and draw it properly, with reasons.

    This is the tool for "here is a screenshot of a chart, make it better",
    "redraw this", "my colleague sent me this graph, it is unreadable",
    "what is wrong with this chart". Send the picture base64-encoded in
    `image_base64` (PNG, JPEG, GIF, WebP or SVG; a screenshot is the usual
    case). A vision model reads what kind of chart it is and what costs the
    reader effort; the figure is then drawn in the house style.

    YOU MUST READ `data_origin` BEFORE PRESENTING THE RESULT. A picture of a
    chart carries its design legibly and its numbers rarely, so this never
    guesses values:

    - `your-data` -- you sent rows. The real figure.
    - `read-from-image` -- the values were printed on the original and read
      back. Approximate; say so.
    - `demo` -- nothing was readable, so the figure carries the kind's
      SAMPLE rows. Tell the user these are not their numbers and ask for
      the data. Never present it as their figure.

    `changes` lists what the redraw does differently, costliest first --
    report those, they are the answer to "why is this better".
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


@app.post(
    "/recommend",
    tags=["meta"],
    operation_id="recommend_figures",
    summary="Rank the chart types this data can fill",
)
def recommend(body: RecommendRequest) -> list[FigureCandidate]:
    """Which of the 127 kinds suit these rows, best first, with columns bound.

    This is the tool for "which chart should I use for this?", "what fits my
    data?", "quel graphique pour ces données ?" -- and the one to reach for
    before `render_figure` whenever the user has not named a chart type. It
    beats guessing from `list_kinds`: the filter is deterministic (no model),
    it only returns kinds your columns can actually fill, and each candidate
    arrives with its role bindings worked out.

    Send `goal` when the request implies one. "How do these regions compare"
    is `comparison`; "how has this moved" is `trend`; "what is this made of"
    is `composition`.

    Needs the profiling stack (`sprezzature-figures[studio]`); answers 503
    with what to install when it is absent.
    """
    try:
        import pandas as pd

        from .studio.ingest.profiler import profile_dataframe
        from .studio.recommendation import assign_columns, rank
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "recommend needs the profiling stack. Install "
                "'sprezzature-figures[studio]' (or [dataviz]). "
                f"({exc})"
            ),
        ) from exc

    if not body.data:
        raise HTTPException(status_code=422, detail="data is empty; send at least one row.")

    profile = profile_dataframe(
        pd.DataFrame(body.data), dataset_id="api", fingerprint="api", source_name="api"
    )
    ranked = rank(profile, goal=body.goal)
    return [
        FigureCandidate(
            kind=definition.kind,
            score=round(float(score), 4),
            bindings=assign_columns(definition, profile) or {},
        )
        for definition, score in ranked[: body.limit]
    ]
