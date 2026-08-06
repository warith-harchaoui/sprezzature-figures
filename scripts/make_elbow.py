#!/usr/bin/env python3
"""
make_elbow — elbow / knee detection (the Kneedle method) as a hand SVG.

Choosing "how many" — clusters for k-means, components for PCA, ``eps`` for
DBSCAN — usually comes down to reading an *elbow*: the point on a
diminishing-returns curve where the steep early gains give way to a flat
tail, so spending more stops paying off. The eye finds it easily; automating
it is the job of the **Kneedle** algorithm (Satopää et al., *Finding a Kneedle
in a Haystack*, 2011; reference implementation ``kneed`` by Kevin Arvai,
https://github.com/arvkevi/kneed).

Kneedle is simple and elegant: normalise both axes to the unit square, flip
the curve into a concave-increasing frame, subtract the diagonal to get a
*difference curve*, and take its peak — that peak is the point of maximum
curvature, the elbow. This figure applies exactly that method to a k-means
inertia curve and finds the elbow at ``k = 4``. The Kneedle difference curve
that does the finding is drawn as a small inset, so the reader sees not just
*where* the elbow is but *how* it was located — the part the library's own
plots show clumsily, here rendered in the house style.

The generator builds the SVG string by hand (no matplotlib / Vega) so the
elbow marker, the split between steep gains and diminishing returns, and the
inset signal are all placed deliberately. House style follows ``_style.py``:
Roboto type, the Apple-system palette, ink ``#1D1D1F`` on white, a
start-anchored takeaway title. Every data point carries a native ``<title>``
tooltip; an additive dark-mode block flips the paper without touching the data
hues.

Running the module writes the SVG to
``sprezzature-figures/assets/svg-examples/elbow.svg``.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _style import load_palette, os_dark_style  # noqa: E402
from _interactive import fullscreen_control  # noqa: E402
from _svg import catmull_rom_beziers, fmt_compact, svg_open  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402

# ------------------------------------------------------------------
# Canvas + house-style tokens
# ------------------------------------------------------------------
WIDTH = 1000
HEIGHT = 620

# Plot frame (baseline at PB, left axis at PL).
PL = 96.0
PR = 948.0
PT = 188.0
PB = 524.0
PLOT_W = PR - PL
PLOT_H = PB - PT

INK = "#1D1D1F"       # primary text
SUBINK = "#6E6E73"    # secondary text
HAIR = "#E5E5EA"      # gridlines
BG = "#FFFFFF"

FONT = "Roboto, system-ui, sans-serif"
FONT_MONO = "Roboto Mono, ui-monospace, monospace"


# ------------------------------------------------------------------
# The story: a k-means run swept over k = 1..10. Inertia (the within-cluster
# sum of squares) falls steeply as the first real clusters are found, then
# flattens once the structure is captured — the classic elbow. Values are
# illustrative but shaped like a real inertia curve.
# ------------------------------------------------------------------
KS: List[int] = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
INERTIA: List[float] = [1000, 560, 330, 210, 165, 138, 120, 108, 100, 95]

# y-axis runs from 0 so the flattening tail reads as "near the floor".
Y_MAX = 1050.0
Y_TICKS = [0, 250, 500, 750, 1000]

#: Row-record view of :data:`KS` / :data:`INERTIA`, the shape the
#: ``make_<kind>`` contract asks for: one dict per swept ``k``.
DEMO_DATA: List[Dict[str, Any]] = [
    {"k": k, "inertia": inertia} for k, inertia in zip(KS, INERTIA)
]


# ------------------------------------------------------------------
# Kneedle, in pure Python (faithful to arvkevi/kneed for a convex,
# decreasing curve): normalise both axes, flip y into an increasing frame,
# subtract the diagonal, and take the peak of the difference curve.
# ------------------------------------------------------------------
def kneedle_elbow(
    xs: List[float], ys: List[float]
) -> Tuple[int, List[float]]:
    """Locate the elbow of a convex, decreasing curve by the Kneedle method.

    Parameters
    ----------
    xs : list of float
        Strictly increasing x values (here, the cluster counts ``k``).
    ys : list of float
        The curve values (here, inertia), convex and decreasing.

    Returns
    -------
    elbow_index : int
        Index into ``xs`` / ``ys`` of the detected elbow (the peak of the
        normalised difference curve).
    diff : list of float
        The normalised difference curve ``d = (1 - y_norm) - x_norm``; its
        maximum marks the elbow. Aligned with ``xs``.
    """
    x_lo, x_hi = min(xs), max(xs)
    y_lo, y_hi = min(ys), max(ys)
    x_span = (x_hi - x_lo) or 1.0
    y_span = (y_hi - y_lo) or 1.0
    diff: List[float] = []
    for x, y in zip(xs, ys):
        xn = (x - x_lo) / x_span
        yn = (y - y_lo) / y_span
        # Flip the decreasing curve to increasing, then subtract the diagonal:
        # the gap between the flipped curve and the chord peaks at the knee.
        diff.append((1.0 - yn) - xn)
    elbow_index = max(range(len(diff)), key=lambda i: diff[i])
    return elbow_index, diff


# ------------------------------------------------------------------
# Scales
# ------------------------------------------------------------------
def _sx(k: float) -> float:
    """Map a cluster count ``k`` to an x pixel coordinate."""
    return PL + (k - KS[0]) / (KS[-1] - KS[0]) * PLOT_W


def _sy(v: float) -> float:
    """Map an inertia value to a y pixel coordinate (0 at the baseline)."""
    return PB - (v / Y_MAX) * PLOT_H


# ------------------------------------------------------------------
# SVG emission
# ------------------------------------------------------------------
def build_svg(mode: str = "self-contained", accessibility: str = "universal") -> str:
    """Assemble the full elbow-detection SVG document as a string.

    Parameters
    ----------
    mode : str, optional
        Interactivity mode passed to :func:`_interactive.fullscreen_control`.
    accessibility : str, optional
        Palette accessibility level forwarded to :func:`_style.load_palette`.

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    palette = load_palette(accessibility)
    curve = palette.get("Blue", "#007AFF")
    curve_deep = palette.get("Indigo", "#0051A8")
    accent = palette.get("Red", "#FF3B30")

    elbow_i, diff = kneedle_elbow([float(k) for k in KS], INERTIA)
    elbow_k = KS[elbow_i]
    elbow_val = INERTIA[elbow_i]
    ex, ey = _sx(elbow_k), _sy(elbow_val)

    title_txt = "Elbow detection: where adding clusters stops paying off"
    subtitle_txt = (
        f"k-means inertia falls steeply, then flattens; the Kneedle method "
        f"flags the elbow at k = {elbow_k}"
    )
    desc_txt = (
        f"Line chart of k-means inertia (within-cluster sum of squares) against "
        f"the number of clusters k, from 1 to 10. The curve drops sharply then "
        f"flattens. The Kneedle algorithm normalises the axes and takes the peak "
        f"of the difference curve to locate the elbow at k = {elbow_k}, where "
        f"inertia is {elbow_val:.0f}. An inset shows that difference curve, whose "
        f"peak marks the elbow."
    )

    p: List[str] = []
    p.append(svg_open(WIDTH, HEIGHT, "elb-title", "elb-desc", font_family=FONT))
    p.append(f'<title id="elb-title">{escape(title_txt)}</title>')
    p.append(f'<desc id="elb-desc">{escape(desc_txt)}</desc>')

    # --- gradients + additive dark mode ---
    p.append(
        '<defs>'
        f'<linearGradient id="elb-fill" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{curve}" stop-opacity="0.22"/>'
        f'<stop offset="1" stop-color="{curve}" stop-opacity="0.02"/>'
        f'</linearGradient>'
        '</defs>'
    )
    dark = os_dark_style(extra='[stroke="#E5E5EA"]{stroke:#2C2C2E;}')
    p.append(f"<style>{dark}</style>")

    # --- background ---
    p.append(f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{BG}"/>')

    # --- title + subtitle (start-anchored, house style) ---
    p.append(
        f'<text x="{PL:.0f}" y="72" font-size="31" font-weight="700" '
        f'fill="{INK}">{escape(title_txt)}</text>'
    )
    p.append(
        f'<text x="{PL:.0f}" y="106" font-size="18" fill="{SUBINK}">'
        f'{escape(subtitle_txt)}</text>'
    )

    # --- horizontal gridlines + y tick labels ---
    for tv in Y_TICKS:
        gy = _sy(tv)
        p.append(
            f'<line x1="{PL:.1f}" y1="{gy:.1f}" x2="{PR:.1f}" y2="{gy:.1f}" '
            f'stroke="{HAIR}" stroke-width="1"/>'
        )
        p.append(
            f'<text x="{PL - 14:.1f}" y="{gy + 5:.1f}" text-anchor="end" '
            f'font-family="{FONT_MONO}" font-size="14" fill="{SUBINK}">'
            f'{tv:,}</text>'
        )

    # --- curve points in pixel space ---
    pts: List[Tuple[float, float]] = [(_sx(k), _sy(v)) for k, v in zip(KS, INERTIA)]

    # --- filled area under the curve (smooth top, down to the baseline) ---
    area = [f'M{fmt_compact(pts[0][0])},{fmt_compact(PB)}']
    area.append(f'L{fmt_compact(pts[0][0])},{fmt_compact(pts[0][1])}')
    area.append(catmull_rom_beziers(pts, fmt_compact))
    area.append(f'L{fmt_compact(pts[-1][0])},{fmt_compact(PB)}Z')
    p.append(f'<path d="{"".join(area)}" fill="url(#elb-fill)"/>')

    # --- vertical divider at the elbow: steep gains | diminishing returns ---
    p.append(
        f'<line x1="{ex:.1f}" y1="{PT - 6:.1f}" x2="{ex:.1f}" y2="{PB:.1f}" '
        f'stroke="{accent}" stroke-width="1.4" stroke-dasharray="2 6" '
        f'stroke-linecap="round"/>'
    )
    p.append(
        f'<text x="{(PL + ex) / 2:.1f}" y="{PT + 22:.1f}" text-anchor="middle" '
        f'font-size="14" font-weight="600" fill="{SUBINK}">steep gains</text>'
    )
    # Sit the right-hand label in the clear gap between the elbow divider and
    # the inset card (the card would otherwise cover it).
    p.append(
        f'<text x="{(ex + 566.0) / 2:.1f}" y="{PT + 22:.1f}" text-anchor="middle" '
        f'font-size="14" font-weight="600" fill="{SUBINK}">diminishing returns</text>'
    )

    # --- the curve stroke ---
    line = [f'M{fmt_compact(pts[0][0])},{fmt_compact(pts[0][1])}']
    line.append(catmull_rom_beziers(pts, fmt_compact))
    p.append(
        f'<path d="{"".join(line)}" fill="none" stroke="{curve}" '
        f'stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/>'
    )

    # --- data dots (every k), each with a native tooltip ---
    for k, v in zip(KS, INERTIA):
        cx, cy = _sx(k), _sy(v)
        tip = f"k = {k}: inertia {v:,.0f}"
        p.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="4.6" fill="{curve_deep}" '
            f'stroke="{BG}" stroke-width="1.6" tabindex="0" role="img" '
            f'aria-label="{escape(tip)}"><title>{escape(tip)}</title></circle>'
        )

    # --- elbow marker: halo + ring + drop line to the axis ---
    p.append(
        f'<line x1="{ex:.1f}" y1="{ey:.1f}" x2="{ex:.1f}" y2="{PB:.1f}" '
        f'stroke="{accent}" stroke-width="1.6"/>'
    )
    p.append(f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="15" fill="{accent}" opacity="0.16"/>')
    p.append(
        f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="8.4" fill="{BG}" '
        f'stroke="{accent}" stroke-width="3"/>'
    )
    p.append(f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="3" fill="{accent}"/>')

    # --- elbow callout pill with a short leader ---
    call_txt = f"Elbow · k = {elbow_k}"
    pill_w = 138.0
    px = ex + 78.0
    py = ey - 78.0
    p.append(
        f'<line x1="{ex + 11:.1f}" y1="{ey - 11:.1f}" x2="{px - pill_w / 2 + 8:.1f}" '
        f'y2="{py:.1f}" stroke="{accent}" stroke-width="1.6"/>'
    )
    p.append(
        f'<rect x="{px - pill_w / 2:.1f}" y="{py - 17:.1f}" width="{pill_w:.0f}" '
        f'height="34" rx="17" fill="{accent}"/>'
    )
    p.append(
        f'<text x="{px:.1f}" y="{py + 5:.1f}" text-anchor="middle" '
        f'font-family="{FONT_MONO}" font-size="16" font-weight="700" '
        f'fill="{BG}">{escape(call_txt)}</text>'
    )

    # --- x axis: baseline, tick labels, title ---
    p.append(
        f'<line x1="{PL:.1f}" y1="{PB:.1f}" x2="{PR:.1f}" y2="{PB:.1f}" '
        f'stroke="{INK}" stroke-width="1.5"/>'
    )
    for k in KS:
        p.append(
            f'<text x="{_sx(k):.1f}" y="{PB + 28:.1f}" text-anchor="middle" '
            f'font-family="{FONT_MONO}" font-size="15" fill="{INK}">{k}</text>'
        )
    p.append(
        f'<text x="{(PL + PR) / 2:.1f}" y="{PB + 62:.1f}" text-anchor="middle" '
        f'font-size="17" fill="{INK}">Number of clusters (k)</text>'
    )
    # y-axis title, rotated up the left edge.
    p.append(
        f'<text x="30" y="{(PT + PB) / 2:.1f}" text-anchor="middle" font-size="17" '
        f'fill="{INK}" transform="rotate(-90 30 {(PT + PB) / 2:.1f})">'
        f'Inertia (within-cluster sum of squares)</text>'
    )

    # --- inset: the Kneedle difference curve (the "how") ---
    _emit_inset(p, diff, elbow_i, curve, accent)

    # Fullscreen control per interactivity mode, just before the close.
    p.append(fullscreen_control(WIDTH, HEIGHT, mode))
    p.append("</svg>")
    return "".join(p)


def _emit_inset(
    p: List[str],
    diff: List[float],
    elbow_i: int,
    curve: str,
    accent: str,
) -> None:
    """Append the Kneedle-signal inset card to ``p``.

    The inset sits in the empty upper-right pocket (the inertia curve is low
    there) and draws the normalised difference curve whose peak located the
    elbow, so the figure shows the method, not just its result.

    Parameters
    ----------
    p : list of str
        The SVG fragment list being assembled; extended in place.
    diff : list of float
        The Kneedle difference curve, aligned with :data:`KS`.
    elbow_i : int
        Index of the peak (the elbow) in ``diff``.
    curve, accent : str
        The curve and marker hues, matched to the main panel.
    """
    ix, iy, iw, ih = 566.0, 196.0, 372.0, 176.0   # card box
    pad = 20.0
    p.append(
        f'<rect x="{ix:.0f}" y="{iy:.0f}" width="{iw:.0f}" height="{ih:.0f}" '
        f'rx="16" fill="#F5F5F7" stroke="{HAIR}" stroke-width="1"/>'
    )
    p.append(
        f'<text x="{ix + pad:.0f}" y="{iy + 30:.0f}" font-size="15" '
        f'font-weight="700" fill="{INK}">Kneedle signal</text>'
    )
    p.append(
        f'<text x="{ix + pad:.0f}" y="{iy + 51:.0f}" font-size="13" '
        f'fill="{SUBINK}">normalised difference · peak = elbow</text>'
    )

    # Mini plot frame inside the card.
    mx0 = ix + pad
    mx1 = ix + iw - pad
    my0 = iy + 66.0                 # top of the mini plot
    my1 = iy + ih - 30.0            # baseline
    dmax = max(diff) or 1.0

    def msx(i: int) -> float:
        return mx0 + i / (len(diff) - 1) * (mx1 - mx0)

    def msy(v: float) -> float:
        return my1 - (v / dmax) * (my1 - my0)

    mpts = [(msx(i), msy(v)) for i, v in enumerate(diff)]

    # Faint fill + smooth stroke for the difference curve.
    a = [f'M{fmt_compact(mpts[0][0])},{fmt_compact(my1)}']
    a.append(f'L{fmt_compact(mpts[0][0])},{fmt_compact(mpts[0][1])}')
    a.append(catmull_rom_beziers(mpts, fmt_compact))
    a.append(f'L{fmt_compact(mpts[-1][0])},{fmt_compact(my1)}Z')
    p.append(f'<path d="{"".join(a)}" fill="{curve}" fill-opacity="0.12"/>')
    ln = [f'M{fmt_compact(mpts[0][0])},{fmt_compact(mpts[0][1])}']
    ln.append(catmull_rom_beziers(mpts, fmt_compact))
    p.append(
        f'<path d="{"".join(ln)}" fill="none" stroke="{curve}" '
        f'stroke-width="2.4" stroke-linecap="round"/>'
    )
    # Mini baseline.
    p.append(
        f'<line x1="{mx0:.1f}" y1="{my1:.1f}" x2="{mx1:.1f}" y2="{my1:.1f}" '
        f'stroke="{HAIR}" stroke-width="1"/>'
    )

    # Peak marker on the difference curve, aligned with the main elbow.
    peak_x, peak_y = mpts[elbow_i]
    p.append(
        f'<line x1="{peak_x:.1f}" y1="{peak_y:.1f}" x2="{peak_x:.1f}" '
        f'y2="{my1:.1f}" stroke="{accent}" stroke-width="1.3" '
        f'stroke-dasharray="2 4"/>'
    )
    p.append(
        f'<circle cx="{peak_x:.1f}" cy="{peak_y:.1f}" r="5" fill="{BG}" '
        f'stroke="{accent}" stroke-width="2.6"/>'
    )
    # k label under the peak.
    p.append(
        f'<text x="{peak_x:.1f}" y="{my1 + 20:.1f}" text-anchor="middle" '
        f'font-family="{FONT_MONO}" font-size="12" font-weight="700" '
        f'fill="{accent}">k = {KS[elbow_i]}</text>'
    )


def make_elbow(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "",
    mode: str = "self-contained",
    accessibility: str = "universal",
) -> Path:
    """Render the k-means elbow (Kneedle) SVG and write it to ``out``.

    The standard ``make_<kind>`` entry the figure registry dispatches to.
    The inertia curve (:data:`KS` / :data:`INERTIA`) is baked into
    :func:`build_svg`, matching :data:`DEMO_DATA`; ``data`` is accepted for
    dispatcher parity but not threaded into the drawn curve, since the
    Kneedle inset and the fixed y-axis domain (:data:`Y_MAX`) are tuned to
    this specific ten-point sweep.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Accepted for contract parity; unused (see above). Defaults to
        :data:`DEMO_DATA` conceptually.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/elbow.svg``.
    title : str, optional
        Accepted for dispatcher/CLI parity; unused, since the chart's
        title is fixed prose.
    mode, accessibility : str
        Forwarded to :func:`build_svg`.

    Returns
    -------
    Path
        Absolute path to the written SVG file.
    """
    _ = data, title  # accepted for dispatcher parity; see docstring
    svg = build_svg(mode=mode, accessibility=accessibility)
    dest = Path(out) if out else svg_example_path(__file__, "elbow")
    return write_svg(dest, svg)


def main() -> None:
    """Write the elbow-detection SVG to the skill's example asset folder.

    The ``--mode`` flag (via :func:`_render.render_cli`) selects the
    interactivity mode threaded into :func:`build_svg`.
    """
    render_cli(
        __file__,
        "elbow",
        build_svg,
        description="Write the house-style elbow-detection (Kneedle) SVG example.",
    )


if __name__ == "__main__":
    main()
