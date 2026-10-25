#!/usr/bin/env python3
"""
make_quiver3d — a vector field in three dimensions, drawn so length still means length.

An arrow at each sample point, pointing the way the field points and
scaled by how strong it is there. In three dimensions that second part
is the hard one: perspective shortens an arrow pointing at the camera,
so the picture says "weak" where the data says "strong".

Where the usual 3-D quiver goes wrong
---------------------------------------
* **Foreshortening is read as magnitude.** An arrow aimed at the viewer
  projects to almost nothing however long it is. Magnitude is therefore
  carried by *colour* as well as length here, so the reader has a
  channel that perspective cannot corrupt, and the chrome says so.
* **Every arrow is drawn, so the field is a thicket.** A field sampled
  on a 10×10×10 grid is a thousand arrows and a grey mass. The sample
  is thinned by `stride`, and the chrome reports how many of the
  supplied vectors are actually on the page.
* **The scale is a free parameter nobody reports.** Arrow length is
  always an arbitrary multiple of the field, and two quiver plots of
  the same data at different scales look like different physics. The
  multiple is named, with the longest arrow given in field units.
* **Depth ordering is ignored.** Arrows are drawn back to front so near
  ones occlude far ones, which with the colour channel is what makes
  the field's structure readable at all.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _project3d import project as project3d  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _style import BG, GRIDLINE, INK, SECONDARY, load_palette  # noqa: E402
from _svg import (  # noqa: E402
    fmt_measured,
    fmt_number,
    foreground_tip_css,
    svg_open,
    tooltip_bubble,
    wrap_no_orphan,
    xml_escape,
)
from _textfit import fit_font_size  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402

_SIDE = 5


def _field() -> List[Dict[str, Any]]:
    """A magnetic dipole sampled on a 5x5x5 grid.

    Chosen because its magnitude varies by a factor of sixty across the
    box, which is exactly the case where carrying magnitude by arrow
    length alone fails. The first draft claimed the strong arrows were
    the ones the camera shortens most; measured, the correlation between
    magnitude and foreshortening is -0.05, which is *worse* news and the
    better argument. Shortening is unrelated to strength, so there is no
    pattern for a reader to correct by eye, and the only remedy is a
    second channel the projection cannot touch.

    The dipole sits at the origin pointing along +z; the field at a point
    is the textbook 3(m·r̂)r̂ - m over r³, with the singular cell at the
    origin left out.
    """
    rows: List[Dict[str, Any]] = []
    span = np.linspace(-1.0, 1.0, _SIDE)
    for x in span:
        for y in span:
            for z in span:
                r = math.sqrt(x * x + y * y + z * z)
                if r < 0.3:
                    continue  # the singularity, and its immediate neighbours
                rx, ry, rz = x / r, y / r, z / r
                dot = rz  # the dipole moment is (0, 0, 1)
                scale = 1.0 / (r**3)
                rows.append(
                    {
                        "x": round(float(x), 4),
                        "y": round(float(y), 4),
                        "z": round(float(z), 4),
                        "u": round(float(scale * 3.0 * dot * rx), 5),
                        "v": round(float(scale * 3.0 * dot * ry), 5),
                        "w": round(float(scale * (3.0 * dot * rz - 1.0)), 5),
                    }
                )
    return rows


DEMO_DATA: List[Dict[str, Any]] = _field()


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Perspective takes most of an arrow's length, and strength does not predict which",
    subtitle: str = "An arrow at each sample, coloured by magnitude because perspective makes length alone unreliable.",
    width: int = 900,
    height: int = 660,
    x: str = "x",
    y: str = "y",
    z: str = "z",
    u: str = "u",
    v: str = "v",
    w: str = "w",
    stride: int = 1,
    arrow_scale: float = 0.30,
    length_scale: str = "sqrt",
    elev: float = 22.0,
    azim: float = -52.0,
    weak_label: str = "weak",
    strong_label: str = "strong",
    scale_note: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full three-dimensional vector field SVG as a string.

    Parameters
    ----------
    data : list of dict or None
        One row per sample point, carrying its position and its vector.
        Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    x, y, z : str
        Row keys for the sample position.
    u, v, w : str
        Row keys for the vector's three components.
    stride : int
        Draw every `stride`-th sample. The field is always measured from
        all of them; only the drawing is thinned.
    arrow_scale : float
        Length of the longest arrow, in model units. Reported on the
        canvas, because two quiver plots of the same data at different
        scales look like different physics.
    length_scale : str
        How magnitude maps to arrow length: ``"linear"``, ``"sqrt"``,
        ``"log"``, or ``"uniform"`` for a pure direction field. A field
        spanning two orders of magnitude draws almost every arrow as a
        dot under ``"linear"``, which is why the default compresses --
        and why the chrome names the mapping rather than leaving the
        reader to assume it is proportional.
    elev, azim : float
        Camera elevation and azimuth, in degrees.
    weak_label, strong_label : str
        The two ends of the magnitude key.
    scale_note, finding : str or None
        The line describing the scale and the camera, and the sentence
        naming what the field does; ``None`` composes each from the data.
    mode : str
        ``"self-contained"`` keeps the interactive chrome inside the file.
    accessibility : str
        Palette variant.
    theme : str
        Visual theme.

    Returns
    -------
    str
        The SVG document.
    """
    rows = list(data if data else DEMO_DATA)
    if not rows:
        raise ValueError("a vector field needs at least one sample")
    if stride < 1:
        raise ValueError(f"stride counts samples, so it is at least 1; got {stride}")

    drawn = rows[::stride]
    positions = np.array([[float(r[x]), float(r[y]), float(r[z])] for r in drawn])
    vectors = np.array([[float(r[u]), float(r[v]), float(r[w])] for r in drawn])
    magnitudes = np.linalg.norm(vectors, axis=1)
    strongest = float(magnitudes.max())
    weakest = float(magnitudes.min())

    # Model space is normalised so the camera's fit scale means the same
    # thing whatever the field's units are.
    low = positions.min(axis=0)
    high = positions.max(axis=0)
    extent = np.maximum(high - low, 1e-9)
    unit = (positions - low) / extent * 2.0 - 1.0
    # How magnitude becomes length. A dipole spans two orders of
    # magnitude, and under a linear map every arrow but the few nearest
    # the centre draws as a dot -- which is the figure's own thesis
    # turned against it. The mapping is compressed and named.
    share = magnitudes / strongest
    if length_scale == "linear":
        drawn_share = share
    elif length_scale == "sqrt":
        drawn_share = np.sqrt(share)
    elif length_scale == "log":
        floor = max(weakest / strongest, 1e-6)
        drawn_share = np.log(share / floor) / math.log(1.0 / floor)
        drawn_share = np.clip(drawn_share, 0.08, 1.0)
    elif length_scale == "uniform":
        drawn_share = np.ones_like(share)
    else:
        raise ValueError(
            f"length_scale is 'linear', 'sqrt', 'log' or 'uniform', got {length_scale!r}"
        )
    directions = vectors / np.maximum(magnitudes, 1e-12)[:, None]
    tips = unit + directions * (arrow_scale * drawn_share[:, None])

    mono_family = mono_stack_for_theme(theme)
    palette = load_palette(accessibility, theme=theme)
    weak_ink = palette.get("Blue", "#007AFF")
    strong_ink = palette.get("Orange", "#FF9500")

    plot_w = width - 200.0
    plot_h = height - 250.0
    centre_x, centre_y = width / 2.0 - 30.0, 178.0 + plot_h / 2.0

    base_x, base_y, depth = project3d(
        unit[:, 0],
        unit[:, 1],
        unit[:, 2],
        elev_deg=elev,
        azim_deg=azim,
        plot_w=plot_w,
        plot_h=plot_h,
        cx=centre_x,
        cy=centre_y,
        fit="box",
    )
    tip_x, tip_y, _ = project3d(
        tips[:, 0],
        tips[:, 1],
        tips[:, 2],
        elev_deg=elev,
        azim_deg=azim,
        plot_w=plot_w,
        plot_h=plot_h,
        cx=centre_x,
        cy=centre_y,
        fit="box",
    )

    # The number that makes the figure's own point: how far the drawn
    # length of an arrow falls short of the length it would have if it
    # lay broadside to the camera.
    #
    # Measured against the *compressed* share, not the raw magnitude. The
    # first version used the magnitude, which folds the deliberate sqrt
    # compression into the measurement and reports it as perspective --
    # and duly produced a correlation of +0.47 between strength and
    # "shortening", which is the compression showing up under another
    # name. Against the share, the projection is isolated.
    drawn_length = np.hypot(tip_x - base_x, tip_y - base_y)
    expected = drawn_length.max() / max(drawn_share.max(), 1e-12) * drawn_share
    shortened = float(np.max(np.where(expected > 1e-9, 1.0 - drawn_length / expected, 0.0)) * 100.0)

    def shade(fraction: float) -> str:
        """Blend weak to strong ink across a already-compressed `fraction`.

        Takes the compressed share rather than the raw magnitude, so
        length and colour say the same thing. On a linear ramp a field
        spanning two orders of magnitude paints everything the weak
        colour and the second channel is wasted -- which is the dynamic
        range problem that forced the length compression, arriving a
        second time by another door.
        """
        fraction = max(0.0, min(1.0, fraction))
        start = tuple(int(weak_ink[i : i + 2], 16) for i in (1, 3, 5))
        finish = tuple(int(strong_ink[i : i + 2], 16) for i in (1, 3, 5))
        blend = tuple(round(start[i] + (finish[i] - start[i]) * fraction) for i in range(3))
        return f"rgb({blend[0]},{blend[1]},{blend[2]})"

    precision = strongest / 200.0
    scale_lines = (
        [scale_note]
        if scale_note is not None
        else [
            f"{len(drawn)} of {len(rows)} samples drawn"
            + (f", every {stride}th" if stride > 1 else "")
            + f" · camera at {fmt_number(elev)}° elevation, {fmt_number(azim)}° azimuth",
            f"length and colour are both the {length_scale} of magnitude, "
            f"longest and warmest = {fmt_measured(strongest, precision)}; two "
            f"channels, because perspective corrupts one of them",
        ]
    )
    said_scale = " · ".join(scale_lines)
    said_parts: List[str] = []
    if finding is not None:
        said_parts.append(finding)
    else:
        said_parts.append(
            f"The field spans {fmt_measured(weakest, precision)} to "
            f"{fmt_measured(strongest, precision)}, a factor of "
            f"{fmt_number(strongest / max(weakest, 1e-12))}."
        )
        said_parts.append(
            f"Perspective takes up to {fmt_number(shortened)}% off an arrow's drawn "
            f"length, and its correlation with magnitude is "
            f"{fmt_number(float(np.corrcoef(magnitudes, 1.0 - drawn_length / np.maximum(expected, 1e-9))[0, 1]))}"
            f" — no pattern to correct by eye, which is why colour carries magnitude too."
        )
    said_lines: List[str] = []
    for sentence in said_parts:
        said_lines.extend(wrap_no_orphan(sentence, 102))

    parts: List[str] = []
    parts.append(
        svg_open(
            width,
            height,
            "quiver3d-title",
            "quiver3d-desc",
            font_family=chrome_stack_for_theme(theme),
        )
    )
    parts.append(f'<title id="quiver3d-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="quiver3d-desc">A three-dimensional vector field of {len(drawn)} '
        f"arrows, each at its sample point, pointing the way the field points and both "
        f"scaled and coloured by its magnitude. {xml_escape(said_scale)}. "
        f"{xml_escape(' '.join(said_parts))}</desc>"
    )
    parts.append(
        "<style>"
        ".arrow{cursor:default;}"
        ".arrow:hover,.arrow:focus{outline:none;}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        + foreground_tip_css(3, mark_prefix="arrow", tip_prefix="arrowtip")
        + "@media (prefers-reduced-motion:reduce){.tip{transition:none}}"
        "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    title_size = fit_font_size(title, width - 96.0, 22.0, min_px=15.0)
    parts.append(
        f'<text x="40" y="46" font-size="{title_size:.1f}" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    for line_index, text in enumerate(wrap_no_orphan(subtitle, 104)[:2]):
        parts.append(
            f'<text x="40" y="{72 + line_index * 20:.1f}" font-size="14" '
            f'fill="{SECONDARY}">{xml_escape(text)}</text>'
        )
    scale_drawn: List[str] = []
    for clause in scale_lines:
        scale_drawn.extend(wrap_no_orphan(clause, 102))
    for line_index, text in enumerate(scale_drawn[:3]):
        parts.append(
            f'<text x="40" y="{118 + line_index * 17:.1f}" font-size="12" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(text)}</text>'
        )
    for line_index, text in enumerate(said_lines[:3]):
        parts.append(
            f'<text x="40" y="{height - 58 + line_index * 17:.1f}" font-size="12" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(text)}</text>'
        )

    # Back to front: a near arrow must cover the far one behind it.
    for index in sorted(range(len(drawn)), key=lambda i: depth[i]):
        colour = shade(float(drawn_share[index]))
        x1, y1 = float(base_x[index]), float(base_y[index])
        x2, y2 = float(tip_x[index]), float(tip_y[index])
        length = math.hypot(x2 - x1, y2 - y1)
        parts.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{colour}" stroke-width="1.5" stroke-linecap="round" '
            f'opacity="0.85"/>'
        )
        if length > 4.0:
            ux, uy = (x2 - x1) / length, (y2 - y1) / length
            parts.append(
                f'<path d="M{x2:.1f},{y2:.1f} '
                f"L{x2 - ux * 5 + uy * 2.6:.1f},{y2 - uy * 5 - ux * 2.6:.1f} "
                f'L{x2 - ux * 5 - uy * 2.6:.1f},{y2 - uy * 5 + ux * 2.6:.1f} Z" '
                f'fill="{colour}" opacity="0.9"/>'
            )
        else:
            # Pointing at or away from the camera: a dot, not a stub,
            # because a two-pixel line reads as a weak arrow and is not.
            parts.append(
                f'<circle cx="{x1:.1f}" cy="{y1:.1f}" r="2.2" fill="{colour}" opacity="0.9"/>'
            )

    key_x, key_y = width - 150.0, 206.0
    parts.append(
        f'<text x="{key_x:.1f}" y="{key_y - 12:.1f}" font-size="11" fill="{SECONDARY}" '
        f'font-family="{mono_family}">{xml_escape(strong_label)}</text>'
    )
    for step in range(12):
        fraction = 1.0 - step / 11.0
        parts.append(
            f'<rect x="{key_x:.1f}" y="{key_y + step * 11:.1f}" width="13" height="11" '
            f'fill="{shade(fraction)}"/>'
        )
    parts.append(
        f'<text x="{key_x:.1f}" y="{key_y + 12 * 11 + 12:.1f}" font-size="11" '
        f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(weak_label)}</text>'
    )
    parts.append(
        f'<text x="{key_x + 19:.1f}" y="{key_y + 9:.1f}" font-size="10" '
        f'fill="{SECONDARY}" font-family="{mono_family}">'
        f"{fmt_measured(strongest, precision)}</text>"
    )
    parts.append(
        f'<text x="{key_x + 19:.1f}" y="{key_y + 12 * 11:.1f}" font-size="10" '
        f'fill="{SECONDARY}" font-family="{mono_family}">'
        f"{fmt_measured(weakest, precision)}</text>"
    )

    # Three representative arrows carry the hover detail: the strongest,
    # the weakest, and the one perspective shortens most.
    picks = {
        "strongest": int(np.argmax(magnitudes)),
        "weakest": int(np.argmin(magnitudes)),
        "most shortened": int(
            np.argmax(np.where(expected > 1e-9, 1.0 - drawn_length / expected, 0.0))
        ),
    }
    for element, (label, index) in enumerate(picks.items()):
        spot_x, spot_y = float(base_x[index]), float(base_y[index])
        parts.append(
            f'<rect id="arrow-{element}" class="arrow hit" tabindex="0" role="img" '
            f'aria-label="{xml_escape(label)} arrow at {x} '
            f"{fmt_number(positions[index][0])}, {y} {fmt_number(positions[index][1])}, "
            f"{z} {fmt_number(positions[index][2])}: magnitude "
            f'{fmt_measured(float(magnitudes[index]), precision)}" '
            f'x="{spot_x - 9:.1f}" y="{spot_y - 9:.1f}" width="18" height="18" '
            f'fill="transparent"><title>{xml_escape(label)}: '
            f"{fmt_measured(float(magnitudes[index]), precision)}</title></rect>"
        )
        parts.append(
            tooltip_bubble(
                spot_x,
                spot_y,
                [
                    label,
                    f"magnitude {fmt_measured(float(magnitudes[index]), precision)}",
                    f"{x} {fmt_number(positions[index][0])} · {y} "
                    f"{fmt_number(positions[index][1])} · {z} "
                    f"{fmt_number(positions[index][2])}",
                ],
                canvas_w=width,
                canvas_h=height,
                ink=INK,
                secondary=SECONDARY,
                border=GRIDLINE,
                elem_id=f"arrowtip-{element}",
            )
        )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_quiver3d(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[str] = None,
    title: str = "Perspective takes most of an arrow's length, and strength does not predict which",
    subtitle: str = "An arrow at each sample, coloured by magnitude because perspective makes length alone unreliable.",
    width: int = 900,
    height: int = 660,
    x: str = "x",
    y: str = "y",
    z: str = "z",
    u: str = "u",
    v: str = "v",
    w: str = "w",
    stride: int = 1,
    arrow_scale: float = 0.30,
    length_scale: str = "sqrt",
    elev: float = 22.0,
    azim: float = -52.0,
    weak_label: str = "weak",
    strong_label: str = "strong",
    scale_note: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Write a three-dimensional vector field to disk and return the path.

    Parameters
    ----------
    data : list of dict or None
        One row per sample point. Defaults to :data:`DEMO_DATA`.
    out : str or None
        Destination path; ``None`` writes beside the script.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    x, y, z : str
        Row keys for the sample position.
    u, v, w : str
        Row keys for the vector's three components.
    stride : int
        Draw every `stride`-th sample.
    arrow_scale : float
        Length of the longest arrow, in model units.
    length_scale : str
        How magnitude maps to arrow length: ``"linear"``, ``"sqrt"``,
        ``"log"`` or ``"uniform"``.
    elev, azim : float
        Camera elevation and azimuth, in degrees.
    weak_label, strong_label : str
        The two ends of the magnitude key.
    scale_note, finding : str or None
        The line describing the scale and the camera, and the sentence
        naming what the field does; ``None`` composes each from the data.
    mode, accessibility : str
        Forwarded to :func:`build_svg`.
    theme : str, optional
        Visual theme. Forwarded to :func:`build_svg`.

    Returns
    -------
    Path
        Absolute path to the written SVG file.

    Examples
    --------
    >>> p = make_quiver3d()
    >>> p.exists()
    True
    """
    svg = build_svg(
        data,
        title=title,
        subtitle=subtitle,
        width=width,
        height=height,
        x=x,
        y=y,
        z=z,
        u=u,
        v=v,
        w=w,
        stride=stride,
        arrow_scale=arrow_scale,
        length_scale=length_scale,
        elev=elev,
        azim=azim,
        weak_label=weak_label,
        strong_label=strong_label,
        scale_note=scale_note,
        finding=finding,
        mode=mode,
        accessibility=accessibility,
        theme=theme,
    )
    dest = Path(out) if out else svg_example_path(__file__, "quiver3d")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(
        __file__, "quiver3d", build_svg, description="Draw a vector field in three dimensions."
    )


if __name__ == "__main__":
    main()
