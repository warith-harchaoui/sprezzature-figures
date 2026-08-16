#!/usr/bin/env python3
"""
make_rug — a publication-quality **rug plot** as a hand-authored SVG.

A rug plot draws one short tick per raw observation along an axis, so
the reader sees the *actual* 1-D sample (every value, every gap, every
cluster) instead of a smoothed summary that hides them. This figure
pairs a soft kernel-density silhouette (the "shape") with the rug (the
"truth") underneath it, the classic seaborn ``rugplot`` + ``kdeplot``
combination, so the density curve is always anchored to the data that
produced it.

The example data are API response times for a checkout endpoint. The
rug makes the story legible at a glance: a dense band of fast requests
plus a thin, unmistakable spray of slow tail requests that a mean or a
single density peak would paper over.

Design follows the sprezzature-* house style (see ``_style.py``): Roboto,
the Apple-system palette, ink ``#1D1D1F`` on a white background,
secondary ``#6E6E73`` for supporting text, rounded corners. The output
is a single self-contained SVG: the only artifact this skill ships.
The figure is deliberately static: a density-plus-rug picture reads
fully at a glance, so no motion is added (it would only delay the
insight, and a draw-on curve leaves the first raster frame empty).
Each rug tick carries a native ``<title>`` tooltip (no JavaScript).

Running the module writes ``assets/svg-examples/rug.svg``.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations
from _render import svg_example_path, write_svg  # noqa: E402
from _style import BG, INK, SECONDARY, leveled_colors, os_adaptive_style, os_dark_style  # noqa: E402
from _svg import svg_open, tooltip_bubble, xml_escape  # noqa: E402
from _interactive import fullscreen_control  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402

import argparse
import math
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ------------------------------------------------------------------
# House-style tokens (kept local so the module is import-light; they
# mirror the house-style color/typography constants).
# ------------------------------------------------------------------
BLUE = "#007AFF"       # density fill / stroke (Apple system blue)
GRID = "#E5E5EA"       # hairline gridlines

# Canvas geometry. Poster-scale (~1.8x the old 640x380) so the figure
# reads big and generous rather than cramped.
W, H = 1160, 700
PAD_L, PAD_R = 96, 52
PAD_T, PAD_B = 150, 128
PLOT_L = PAD_L
PLOT_R = W - PAD_R
PLOT_T = PAD_T
PLOT_B = H - PAD_B                 # baseline of the density area
RUG_TOP = PLOT_B + 24              # where the rug band starts
RUG_LEN = 36                       # tick height


def sample_response_times(seed: int = 7) -> List[float]:
    """Draw a realistic, right-skewed sample of API response times.

    A dense body of fast requests (a lognormal-ish core) plus a thin
    slow tail — the shape a rug plot is uniquely good at exposing.

    Parameters
    ----------
    seed : int, optional
        Seed for reproducibility so the shipped SVG is deterministic.

    Returns
    -------
    list of float
        Response times in milliseconds, sorted ascending.
    """
    rng = random.Random(seed)
    values: List[float] = []
    # Fast core: most requests land here.
    for _ in range(58):
        values.append(math.exp(rng.gauss(math.log(120.0), 0.28)))
    # Slow tail: a sparse spray the mean would hide.
    for _ in range(12):
        values.append(math.exp(rng.gauss(math.log(340.0), 0.30)))
    # Clip to a clean display window and sort.
    values = [max(45.0, min(560.0, v)) for v in values]
    values.sort()
    return values


#: Row-record demo data: one row per observed response time, the
#: contract's ``list[dict[str, Any]]`` shape. :func:`_values_from_rows`
#: reshapes it (or any caller-supplied row list of the same shape) into
#: the flat value list :func:`build_svg` renders.
DEMO_DATA: List[Dict[str, Any]] = [
    {"response_ms": round(v, 1)} for v in sample_response_times()
]


def _values_from_rows(data: Optional[List[Dict[str, Any]]]) -> List[float]:
    """Reshape ``{"response_ms"}`` row records into a flat value list.

    Parameters
    ----------
    data : list of dict or None
        Rows with a ``response_ms`` (numeric) key. Falls back to
        :data:`DEMO_DATA` when ``None``/empty.

    Returns
    -------
    list of float
        Response times in milliseconds, sorted ascending.
    """
    rows = data if data else DEMO_DATA
    return sorted(float(r["response_ms"]) for r in rows)


def gaussian_kde(samples: List[float], grid: List[float], bandwidth: float) -> List[float]:
    """Evaluate a Gaussian kernel-density estimate on a grid.

    Parameters
    ----------
    samples : list of float
        The raw 1-D observations.
    grid : list of float
        Points at which to evaluate the density.
    bandwidth : float
        Gaussian kernel bandwidth (same units as the samples).

    Returns
    -------
    list of float
        Estimated density at each grid point (unnormalised scale is
        fine — the drawing rescales to the plot height).
    """
    n = len(samples)
    inv = 1.0 / (n * bandwidth * math.sqrt(2.0 * math.pi))
    out: List[float] = []
    for x in grid:
        acc = 0.0
        for s in samples:
            z = (x - s) / bandwidth
            acc += math.exp(-0.5 * z * z)
        out.append(acc * inv)
    return out


def _sx(v: float, lo: float, hi: float) -> float:
    """Map a data value to an x pixel coordinate."""
    return PLOT_L + (v - lo) / (hi - lo) * (PLOT_R - PLOT_L)


def _fmt(v: float) -> str:
    """Format a millisecond value for a tick label."""
    return f"{v:.0f}"


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full rug-plot SVG document as a string.

    Parameters
    ----------
    data : list of dict, optional
        Rows with a ``response_ms`` (numeric) key. Defaults to
        :data:`DEMO_DATA`.
    mode : str, optional
        Interactivity mode passed to :func:`_interactive.fullscreen_control`.
        One of ``"self-contained"`` (default, ships a hidden-until-live
        fullscreen button), ``"external"`` or ``"static"`` (no button).
    accessibility : str, optional
        Palette accessibility level for the single series colour. The one blue
        (density fill / stroke and rug ticks) is a categorical set of one,
        wrapped with :func:`_style.leveled_colors`. ``"universal"`` (default) is
        the identity, so the shipped SVG is byte-for-byte unchanged.
    theme : str, optional
        Visual theme: ``"corporate"`` (default, Roboto -- byte-identical to
        the pre-theme render) or ``"academic"`` (LaTeX-style Latin Modern).
        See :func:`sprezzature_figures.fonts.chrome_stack_for_theme`.

    Returns
    -------
    str
        A self-contained SVG (viewBox 0 0 640 380).
    """
    # The series colour is a single categorical hue; level it so the figure
    # answers to the accessibility argument.
    blue = leveled_colors({"series": BLUE}, accessibility)["series"]
    mono_family = mono_stack_for_theme(theme)

    samples = _values_from_rows(data)
    lo, hi = 40.0, 560.0           # display window (ms)

    # Kernel-density silhouette across the window.
    grid = [lo + (hi - lo) * i / 200.0 for i in range(201)]
    dens = gaussian_kde(samples, grid, bandwidth=26.0)
    dmax = max(dens) or 1.0
    # Reserve ~12% headroom above the tallest peak so the curve crest is
    # never clipped by the plot's top edge.
    area_h = (PLOT_B - PLOT_T) * 0.88
    pts: List[Tuple[float, float]] = []
    for x, d in zip(grid, dens):
        px = _sx(x, lo, hi)
        py = PLOT_B - (d / dmax) * area_h
        pts.append((px, py))

    parts: List[str] = []
    parts.append(svg_open(W, H, "rug-title", "rug-desc", font_family=chrome_stack_for_theme(theme)))
    parts.append(
        '<title id="rug-title">Rug plot of checkout API response times</title>'
    )
    parts.append(
        '<desc id="rug-desc">A kernel-density curve over a rug of raw '
        'observations. A dense band of fast requests near 120 ms sits '
        'beside a thin, unmistakable tail of slow requests past 300 ms '
        'that a single average would hide.</desc>'
    )
    parts.append(f'<rect width="{W}" height="{H}" fill="{BG}"/>')

    # ---- OS-adaptive overrides (additive; every rule lives inside an
    # @media block so the default render is byte-for-byte unchanged). The one
    # blue series carries stable classes as @media hooks: under
    # prefers-contrast the density fill/line and the rug ticks deepen to the
    # high-contrast blue. forced-colors is left to the browser default (a
    # single-hue density-plus-rug has no multi-category encoding to preserve,
    # and the browser leaves SVG fills alone there, which reads fine).
    # Dark mode: invert paper + inks, dim the light gridlines (#E5E5EA) and
    # re-light the ink axis / baseline stroke (#1D1D1F) so it reads on dark.
    dark_extra = (
        '[stroke="#E5E5EA"]{stroke:#2C2C2E;}'
        '[stroke="#1D1D1F"]{stroke:#F2F2F7;}'
    )
    parts.append(
        "<style>\n"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}\n"
        ".hit:hover+.tip,.hit:focus+.tip{opacity:1}\n"
        "@media (prefers-reduced-motion: reduce){.tip{transition:none}}\n"
        + os_adaptive_style({".rug-blue": blue}, role="both")
        + os_dark_style(extra=dark_extra)
        + "\n</style>"
    )

    # ---- Title + subtitle (takeaway) -----------------------------
    parts.append(
        f'<text x="{PAD_L}" y="60" font-size="30" font-weight="700" '
        f'fill="{INK}">The slow tail hides behind a fast average</text>'
    )
    parts.append(
        f'<text x="{PAD_L}" y="94" font-size="20" fill="{SECONDARY}">'
        f'Checkout API response times &#8212; every tick is one real '
        f'request</text>'
    )

    # ---- X gridlines + axis ticks --------------------------------
    ticks = [50, 150, 250, 350, 450, 550]
    for t in ticks:
        px = _sx(float(t), lo, hi)
        parts.append(
            f'<line x1="{px:.1f}" y1="{PLOT_T}" x2="{px:.1f}" y2="{PLOT_B}" '
            f'stroke="{GRID}" stroke-width="1"/>'
        )
    # Baseline / axis domain.
    parts.append(
        f'<line x1="{PLOT_L}" y1="{PLOT_B}" x2="{PLOT_R}" y2="{PLOT_B}" '
        f'stroke="{INK}" stroke-width="1"/>'
    )

    # ---- Density silhouette (static — reads fully at a glance) ----
    area_d = f"M {pts[0][0]:.1f} {PLOT_B:.1f} "
    area_d += " ".join(f"L {x:.1f} {y:.1f}" for x, y in pts)
    area_d += f" L {pts[-1][0]:.1f} {PLOT_B:.1f} Z"
    line_d = f"M {pts[0][0]:.1f} {pts[0][1]:.1f} "
    line_d += " ".join(f"L {x:.1f} {y:.1f}" for x, y in pts[1:])

    parts.append(f'<path class="rug-blue" d="{area_d}" fill="{blue}" fill-opacity="0.16"/>')
    parts.append(
        f'<path class="rug-blue" d="{line_d}" fill="none" stroke="{blue}" stroke-width="3.2" '
        f'stroke-linejoin="round"/>'
    )

    # ---- The rug: one tick per raw observation -------------------
    parts.append(
        f'<line x1="{PLOT_L}" y1="{RUG_TOP - 10:.1f}" x2="{PLOT_R}" '
        f'y2="{RUG_TOP - 10:.1f}" stroke="{GRID}" stroke-width="1"/>'
    )
    # Static rug: every tick is drawn in its final state. Ticks are kept
    # thin with partial opacity so that where fast requests pile up, the
    # individual observations stay countable rather than fusing into one
    # solid blue block (no colour-on-colour blob).
    n_samples = len(samples)
    for i, v in enumerate(samples):
        px = _sx(v, lo, hi)
        pct = 100.0 * (i + 1) / n_samples if n_samples else 0.0
        tip = f"{_fmt(v)} ms"
        parts.append(
            f'<line class="rug-blue hit" tabindex="0" x1="{px:.1f}" y1="{RUG_TOP:.1f}" x2="{px:.1f}" '
            f'y2="{RUG_TOP + RUG_LEN:.1f}" stroke="{blue}" '
            f'stroke-width="1.8" stroke-opacity="0.68" '
            f'role="img" aria-label="{xml_escape(tip)}"/>'
        )
        parts.append(
            tooltip_bubble(
                px, RUG_TOP - 14,
                [tip, f"{pct:.0f}th percentile", f"rank {i + 1} of {n_samples}"],
                anchor="middle", canvas_w=W, canvas_h=H,
                ink=INK, secondary=SECONDARY, border=GRID,
            )
        )

    # ---- X-axis tick labels + axis title -------------------------
    label_y = RUG_TOP + RUG_LEN + 30
    for t in ticks:
        px = _sx(float(t), lo, hi)
        parts.append(
            f'<text x="{px:.1f}" y="{label_y}" font-size="18" '
            f'font-family="{mono_family}" fill="{SECONDARY}" '
            f'text-anchor="middle">{t}</text>'
        )
    parts.append(
        f'<text x="{(PLOT_L + PLOT_R) / 2:.1f}" y="{label_y + 34}" '
        f'font-size="19" fill="{INK}" text-anchor="middle">'
        f'Response time (ms)</text>'
    )

    # ---- Density y-axis label (left, rotated) --------------------
    dy_x = PAD_L - 58
    dy_y = (PLOT_T + PLOT_B) / 2
    parts.append(
        f'<text x="{dy_x}" y="{dy_y:.1f}" '
        f'font-size="18" fill="{SECONDARY}" text-anchor="middle" '
        f'transform="rotate(-90 {dy_x} {dy_y:.1f})">'
        f'Density</text>'
    )

    # ---- Annotation calling out the tail -------------------------
    tail = [v for v in samples if v > 260.0]
    if tail:
        tx = _sx(sum(tail) / len(tail), lo, hi)
        parts.append(
            f'<line x1="{tx:.1f}" y1="{PLOT_T + 16:.1f}" x2="{tx:.1f}" '
            f'y2="{RUG_TOP - 12:.1f}" stroke="{SECONDARY}" '
            f'stroke-width="1.4" stroke-dasharray="4 4"/>'
        )
        parts.append(
            f'<text x="{tx:.1f}" y="{PLOT_T + 4:.1f}" font-size="18" '
            f'font-weight="600" fill="{SECONDARY}" text-anchor="middle">'
            f'slow tail</text>'
        )

    parts.append(fullscreen_control(W, H, mode))
    parts.append('</svg>')
    return "\n".join(parts)


def _out_path() -> Path:
    """Resolve the canonical output path for the rug SVG."""
    here = Path(__file__).resolve()
    return here.parent.parent / "assets" / "svg-examples" / "rug.svg"


def make_rug(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "",
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render the rug (+ KDE) plot and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with a ``response_ms`` (numeric) key. Defaults to
        :data:`DEMO_DATA`.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/rug.svg``.
    title : str, optional
        Accepted for signature parity; the figure's headline is baked into
        the takeaway text (unused).
    mode, accessibility : str
        Forwarded to :func:`build_svg`.
    theme : str, optional
        Visual theme. Forwarded to :func:`build_svg`.

    Returns
    -------
    Path
        Absolute path to the written SVG file.
    """
    _ = title
    svg = build_svg(data, mode=mode, accessibility=accessibility, theme=theme)
    dest = Path(out) if out else svg_example_path(__file__, "rug")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """Render the rug plot and write the SVG artifact to disk."""
    parser = argparse.ArgumentParser(description="Render the rug-plot SVG.")
    parser.add_argument(
        "--mode",
        choices=("self-contained", "external", "static"),
        default="self-contained",
        help="interactivity mode of the emitted SVG (default: self-contained)",
    )
    parser.add_argument(
        "--accessibility",
        choices=(
            "universal", "high-contrast", "monochrome",
            "deuteranopia", "protanopia", "tritanopia",
        ),
        default="universal",
        help="palette accessibility level (default: universal, the CVD-safe standard)",
    )
    parser.add_argument(
        "--theme",
        choices=("corporate", "academic"),
        default="corporate",
        help="visual theme: corporate (default, Roboto) or academic (LaTeX-style Latin Modern)",
    )
    args = parser.parse_args()
    out = _out_path()
    write_svg(
        out,
        build_svg(mode=args.mode, accessibility=args.accessibility, theme=args.theme) + "\n",
        theme=args.theme,
    )


# Keep a reference to satisfy the "types imported" style; harmless.
_TYPES: Dict[str, object] = {}

if __name__ == "__main__":
    main()
