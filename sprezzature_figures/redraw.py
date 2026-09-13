"""
Redraw somebody else's chart: a picture in, a sprezzature figure out.

This started as a favour. A friend sent a screenshot of a two-panel
BTC/USDT figure and asked how the stack would draw it; the answer took a
day, and the useful part of that day was not the drawing. It was noticing
that a picture of a chart carries two things, and carries them with very
different confidence:

- **The design** -- what kind of chart it is, what it is about, what it
  costs the reader. Legible from pixels. A vision model recovers it well.
- **The data** -- the numbers. Usually *not* legible. A chart drawn
  without data labels does not contain its own numbers, and a model asked
  for them anyway will produce numbers, because that is what models do.

So this module keeps them apart, and every result says which one it got.
``RedrawResult.data_origin`` is the whole honesty of the thing:

``your-data``
    You passed rows. The image supplied only the design. This is the real
    figure, and the only mode whose numbers mean anything.
``read-from-image``
    The values were printed on the chart and the model read them back.
    Approximate by construction, and the figure says so on its face.
``demo``
    Nothing readable. You get the *redesign* -- the right chart type, the
    house typography and palette -- carrying the kind's built-in sample
    data, captioned as such. A mock-up to react to, never a result to
    publish.

What it does not do: guess. A redraw that silently invented plausible
numbers would be the most convincing lie this package could tell.

Usage Example
-------------
>>> from sprezzature_figures import redraw
>>> result = redraw("their-chart.png", out="better.svg")  # doctest: +SKIP
>>> result.kind, result.data_origin                       # doctest: +SKIP
('bar', 'demo')

Author
------
Warith HARCHAOUI <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import contextlib
import io
import re
import tempfile
from pathlib import Path
from typing import Any, Literal
from xml.sax.saxutils import escape

from pydantic import BaseModel, Field

from .catalog import FigureDefinition, get_figure_definition, get_registry, resolve_kind
from .make_figure import _demo_data_for, make_figure

DataOrigin = Literal["your-data", "read-from-image", "demo"]

#: Raster formats a vision model can be handed directly. An SVG input is
#: rasterised first (resvg-py is a core dependency, so that costs nothing);
#: a PDF is refused rather than silently half-handled.
_RASTER_MAGIC: dict[bytes, str] = {
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
    b"GIF87a": "image/gif",
    b"GIF89a": "image/gif",
}

#: The caption a figure carries when its numbers did not come from the
#: caller. Said on the figure itself, not only in the return value: the SVG
#: outlives the function call and will be looked at by someone who never
#: saw it.
_PROVENANCE: dict[str, dict[DataOrigin, str]] = {
    "en": {
        "your-data": "",
        "read-from-image": "Values read off the source image — approximate.",
        "demo": "Sample data — this is the redesign, not your numbers.",
    },
    "fr": {
        "your-data": "",
        "read-from-image": "Valeurs relevées sur l'image d'origine — approximatives.",
        "demo": "Données d'exemple — c'est la refonte, pas vos chiffres.",
    },
}


class RedrawResult(BaseModel):
    """What a redraw produced, and where every part of it came from."""

    output: Path = Field(description="The figure that was written.")
    kind: str = Field(description="The canonical chart kind it was drawn as.")
    data_origin: DataOrigin = Field(
        description=(
            "Where the numbers came from: 'your-data' (you passed rows), "
            "'read-from-image' (printed on the original and read back, approximate), "
            "or 'demo' (the kind's sample data -- a mock-up of the redesign)."
        )
    )
    reading: Any = Field(
        default=None, description="The ChartReading the vision model returned, verbatim."
    )
    changes: list[str] = Field(
        default_factory=list,
        description="What this redraw does differently, one line each, costliest first.",
    )
    warnings: list[str] = Field(
        default_factory=list, description="Anything the caller should know before trusting this."
    )

    model_config = {"arbitrary_types_allowed": True}


def _image_bytes(image: str | Path | bytes) -> bytes:
    """Raster bytes for `image`, rasterising an SVG on the way through.

    Raises
    ------
    ValueError
        If the payload is not a format a vision model can be shown. PDFs
        say so by name -- it is the one refusal people hit on purpose.
    """
    raw = image if isinstance(image, bytes) else Path(image).read_bytes()
    if any(raw.startswith(magic) for magic in _RASTER_MAGIC):
        return raw
    if raw.startswith(b"%PDF"):
        raise ValueError(
            "that is a PDF. Export the page as PNG first (any viewer's 'export image' "
            "will do) and pass that."
        )
    head = raw[:512].lstrip()
    if head.startswith(b"<?xml") or head.startswith(b"<svg") or b"<svg" in head:
        import resvg_py

        return bytes(resvg_py.svg_to_bytes(svg_string=raw.decode("utf-8", "replace")))
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return raw
    raise ValueError(
        "unrecognised image. Pass a PNG, JPEG, GIF, WebP or SVG of the chart "
        "(a screenshot is fine)."
    )


#: The house secondary-text colour (scripts/_style.py's ``_SECONDARY``),
#: legible on both the light canvas and the dark one.
_CAPTION_INK = "#6E6E73"

_SVG_ROOT = re.compile(r"<svg\b[^>]*>", re.I)
_VIEWBOX = re.compile(r'\bviewBox="\s*([-\d.]+)\s+([-\d.]+)\s+([\d.]+)\s+([\d.]+)\s*"', re.I)
_HEIGHT_ATTR = re.compile(r'(\bheight=")([\d.]+)(")', re.I)


def stamp_provenance(svg: str, caption: str, *, band: float = 34.0) -> str | None:
    """Add `caption` to `svg` in a strip grown below the drawing.

    Why not simply pass it as the figure's subtitle: 79 of the 127
    generators do not declare a ``subtitle`` parameter, and
    ``make_figure`` drops kwargs a generator does not accept. A caption
    that silently vanishes on two thirds of the catalogue is worse than no
    caption at all -- the figure would look like a real one. So the strip
    is grown here, after rendering, which works for every kind and cannot
    collide with anything the generator drew.

    Returns ``None`` when the document does not declare the geometry this
    needs (no ``viewBox``), so the caller can say so rather than ship an
    uncaptioned figure believing otherwise.
    """
    root = _SVG_ROOT.search(svg)
    if root is None:
        return None
    box = _VIEWBOX.search(root.group(0))
    if box is None:
        return None

    min_x, min_y, width, height = (float(g) for g in box.groups())
    grown = height + band
    new_root = _VIEWBOX.sub(
        f'viewBox="{min_x:g} {min_y:g} {width:g} {grown:g}"', root.group(0), count=1
    )
    # The height attribute is the canvas in user units; grow it in the same
    # proportion so the figure keeps its scale instead of squashing.
    new_root = _HEIGHT_ATTR.sub(
        lambda m: f"{m.group(1)}{float(m.group(2)) * grown / height:g}{m.group(3)}",
        new_root,
        count=1,
    )

    text = (
        f'<text x="{min_x + 16:g}" y="{min_y + height + band * 0.62:g}" '
        f'font-family="Roboto, system-ui, sans-serif" font-size="13" '
        f'fill="{_CAPTION_INK}">{escape(caption)}</text>'
    )
    body = svg[root.end() :]
    head, sep, tail = body.rpartition("</svg>")
    if not sep:
        return None
    return svg[: root.start()] + new_root + head + text + sep + tail


def _binding_roles(definition: FigureDefinition) -> tuple[str, str] | None:
    """The (label role, value role) pair of a plainly two-role figure.

    ``None`` for anything richer -- a figure needing three bound roles cannot
    be filled from one labels/values pair without guessing what fills the
    third, and guessing is the one thing this module refuses to do.
    """
    required = definition.required_roles
    numeric = [r for r in required if "numeric" in r.accepted_types]
    labelled = [r for r in required if "numeric" not in r.accepted_types]
    if len(numeric) == 1 and len(labelled) == 1 and len(required) == 2:
        return labelled[0].name, numeric[0].name
    return None


def rows_from_reading(reading: Any, kind: str) -> list[dict[str, Any]] | None:
    """Build renderable rows from what the model read, or ``None``.

    ``None`` is the normal answer and not a failure: it means the picture
    did not carry its numbers legibly enough to rebuild, which is true of
    most charts. Every condition below has to hold -- the model said the
    values are readable, exactly one series carries them, labels and values
    line up, and the target kind takes exactly one label plus one value.
    """
    if not getattr(reading, "values_are_readable", False):
        return None
    filled = [
        s for s in reading.series if s.values and len(s.values) == len(s.labels) and s.labels
    ]
    if len(filled) != 1:
        return None
    pair = _binding_roles(get_figure_definition(kind))
    if pair is None:
        return None
    label_role, value_role = pair
    series = filled[0]
    return [
        {label_role: label, value_role: value}
        for label, value in zip(series.labels, series.values, strict=True)
    ]


def _changes(reading: Any) -> list[str]:
    """The diagnosis, as a list of lines, worst first."""
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    issues = sorted(reading.issues, key=lambda i: order.get(i.severity, 4))
    return [
        f"{issue.suggested_action or issue.observation} ({issue.category}, {issue.severity})"
        for issue in issues
    ]


def _write_in_format(out: Path, svg: str) -> None:
    """Write `svg` to `out` in whatever format the extension asks for.

    Delegates to the generators' own writer (``scripts/_render.py``) rather
    than repeating its svg/png/pdf/jpg/html branches here, so a redrawn PNG
    is rasterised exactly like every other PNG this package produces.
    """
    from .make_figure import _SCRIPTS_DIR, _load_module

    render = _load_module(_SCRIPTS_DIR / "_render.py", "_sprezzature_figures_render")
    render._write_in_format(out, svg)


def _render_with_caption(
    kind: str,
    rows: list[dict[str, Any]],
    kwargs: dict[str, Any],
    destination: Path,
    caption: str,
    warnings: list[str],
) -> Path:
    """Render `kind`, stamp `caption` into it, write it where it was asked for.

    The figure is staged as an SVG first even when a PNG was requested: the
    caption is added to the markup, and only then is the document converted.
    Stamping after rasterisation would mean drawing text onto pixels.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not caption:
        kwargs["out"] = str(destination)
        return make_figure(kind, rows, **kwargs)

    with tempfile.TemporaryDirectory(prefix="sprezzature-redraw-") as tmp:
        kwargs["out"] = str(Path(tmp) / f"{kind}.svg")
        # Generators announce "wrote <path>" on stdout. That path is this
        # temporary one, which the caller neither chose nor will ever see
        # again; printing it would contradict the path actually reported.
        with contextlib.redirect_stdout(io.StringIO()):
            produced = make_figure(kind, rows, **kwargs)
        markup = produced.read_text(encoding="utf-8")

    stamped = stamp_provenance(markup, caption)
    if stamped is None:
        warnings.append(
            f"Could not write {caption!r} onto the figure itself -- {kind} renders a "
            f"document this cannot measure. The caption is in `data_origin` only, so "
            f"say where the numbers came from when you share it."
        )
        stamped = markup
    _write_in_format(destination, stamped)
    return destination


def redraw(
    image: str | Path | bytes,
    *,
    out: str | Path | None = None,
    data: list[dict[str, Any]] | None = None,
    kind: str | None = None,
    title: str | None = None,
    hint: str = "",
    language: str = "en",
    client: Any = None,
    candidates: list[FigureDefinition] | None = None,
    **options: Any,
) -> RedrawResult:
    """Redraw the chart in `image` as a sprezzature figure.

    Parameters
    ----------
    image : str or Path or bytes
        A picture of the chart to redraw: PNG, JPEG, GIF, WebP, or an SVG
        (rasterised here before it is shown to the model). A screenshot is
        fine -- that is the usual case.
    out : str or Path, optional
        Where to write. Defaults to ``<kind>-redrawn.svg`` in the working
        directory. The extension picks the format, as everywhere else in
        this package: ``.svg``, ``.png``, ``.pdf``, ``.jpg``, ``.html``.
    data : list of dict, optional
        Your real rows, keyed by the target kind's role names. Passing them
        is what turns a redesign into a figure worth publishing.
    kind : str, optional
        Skip the model's choice of chart type and use this one. The image is
        still read, for the diagnosis and the chrome text.
    title : str, optional
        Overrides both the original's title and the model's suggested one.
    hint : str, optional
        Anything you want to tell the model about the image.
    language : {'en', 'fr'}, optional
        Language of the provenance caption written onto the figure.
    client : LLMClient, optional
        The vision client. Defaults to the package's configured one.
    candidates : list of FigureDefinition, optional
        Restrict the kinds the model may choose from.
    **options
        Forwarded to the generator (``width``, ``height``, ``subtitle``, …).

    Returns
    -------
    RedrawResult
        The output path, the kind, where the numbers came from, the reading,
        and the list of changes.
    """
    from .studio.assistant.read_chart import read_chart

    if client is None:
        from .studio.assistant.client import default_client

        client = default_client()

    if candidates is None:
        candidates = [d for d in get_registry() if d.status == "stable"]
    if kind is not None:
        canonical = resolve_kind(kind)
        if canonical is None:
            raise ValueError(f"No registered figure for kind={kind!r}.")
        # Naming the kind narrows the model's job to reading the picture;
        # it can no longer answer with a chart type you did not ask for.
        candidates = [d for d in candidates if d.kind == canonical] or [
            get_figure_definition(canonical)
        ]

    reading = read_chart(client, _image_bytes(image), candidates=candidates, hint=hint)
    target = reading.kind
    warnings: list[str] = []

    if data is not None:
        rows, origin = data, "your-data"
    else:
        read_rows = rows_from_reading(reading, target)
        if read_rows is not None:
            rows, origin = read_rows, "read-from-image"
            warnings.append(
                "The numbers were read off a picture. Check them against your source "
                "before this figure leaves your desk."
            )
        else:
            rows, origin = _demo_data_for(target), "demo"
            warnings.append(
                "The image did not carry readable numbers, so this shows the redesign "
                "on sample data. Pass your own rows with `data=` to make it real."
            )

    if reading.kind_confidence == "low":
        warnings.append(
            f"The model was unsure this is a {target!r}. Name the kind yourself if it "
            f"picked wrong."
        )

    kwargs: dict[str, Any] = {"title": title or reading.suggested_title or reading.title or ""}
    if origin != "demo":
        # Axis titles and the standfirst describe the ORIGINAL's content. Over
        # the kind's sample rows they would be a lie with a straight face: a
        # y-axis labelled "Sales" above four invented regions reads as data.
        # The title survives because it names the subject being redesigned,
        # which the mock-up is still about.
        kwargs["subtitle"] = reading.subtitle
        if reading.x_label:
            kwargs["x_label"] = reading.x_label
        if reading.y_label:
            kwargs["y_label"] = reading.y_label
    kwargs.update(options)

    destination = Path(out) if out is not None else Path(f"{target}-redrawn.svg")
    caption = _PROVENANCE.get(language, _PROVENANCE["en"])[origin]  # type: ignore[index]
    output = _render_with_caption(target, rows, kwargs, destination, caption, warnings)

    return RedrawResult(
        output=output,
        kind=target,
        data_origin=origin,  # type: ignore[arg-type]
        reading=reading,
        changes=_changes(reading),
        warnings=warnings,
    )
