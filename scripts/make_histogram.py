#!/usr/bin/env python3
"""
make_histogram — a house-styled binned distribution histogram as a hand-authored SVG.

Bins a single numeric variable and counts observations per bin, the default
chart for understanding a distribution's shape, spread, and skew. Typical
uses: exam score distributions, response time distributions, order value
distributions.

Previously rendered via Vega-Lite (``vl_convert``); this module now bins the
data itself (a small "nice-step" binning routine, the same idea Vega's own
binning uses: round the bin width to 1/2/5x10^k so edges read as friendly
numbers) and paints the bars by hand — no Vega, no matplotlib. Each bar
carries a native ``<title>`` tooltip with its exact bin range, count and
share of the sample, and rounds only its free (top) end per the Sprezzature
Corner Policy — the baseline stays flat so every bar visibly starts at zero.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import argparse
import math
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import svg_example_path, write_svg  # noqa: E402
from _scale import log_position, log_ticks  # noqa: E402
from _style import BG, GRIDLINE, INK, SECONDARY, corner_radius  # noqa: E402
from _svg import bar_path, fmt_number, svg_open, xml_escape  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402

COLOR_BAR = "#007AFF"


def _make_demo_data() -> List[Dict[str, Any]]:
    rng = random.Random(11)
    # Approximate a bell-shaped distribution of exam scores via the
    # sum-of-uniforms trick, so no extra dependency (numpy) is needed here.
    scores = [round(sum(rng.uniform(0, 1) for _ in range(6)) / 6 * 60 + 40, 1) for _ in range(300)]
    return [{"score": s} for s in scores]


DEMO_DATA: List[Dict[str, Any]] = _make_demo_data()


def _nice_step(raw_step: float) -> float:
    """Round ``raw_step`` up to a friendly 1/2/5 x 10^k bin width (Vega's own
    binning follows the same rule so the axis reads in round numbers)."""
    if raw_step <= 0:
        return 1.0
    power = 10.0 ** math.floor(math.log10(raw_step))
    frac = raw_step / power
    nice = 1.0 if frac < 1.5 else (2.0 if frac < 3.0 else (5.0 if frac < 7.0 else 10.0))
    return nice * power


def _bin_scores(values: List[float], bin_count: int) -> tuple[List[float], List[int]]:
    """Bin ``values`` into ``~bin_count`` nice-width bins.

    Returns
    -------
    tuple of (list of float, list of int)
        ``(edges, counts)`` — ``len(edges) == len(counts) + 1``.
    """
    lo, hi = min(values), max(values)
    if hi <= lo:
        hi = lo + 1.0
    step = _nice_step((hi - lo) / max(bin_count, 1))
    bin_lo = math.floor(lo / step) * step
    bin_hi = math.ceil(hi / step) * step
    n_bins = max(1, round((bin_hi - bin_lo) / step))
    edges = [bin_lo + i * step for i in range(n_bins + 1)]
    counts = [0] * n_bins
    for v in values:
        idx = min(int((v - bin_lo) / step), n_bins - 1)
        counts[idx] += 1
    return edges, counts


def _fmt_edge(v: float) -> str:
    """Format a bin edge compactly: whole numbers with no decimal point."""
    return f"{v:.0f}" if abs(v - round(v)) < 1e-6 else f"{v:.1f}"


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Exam Score Distribution",
    subtitle: str = "Synthetic sample, 300 students",
    width: int = 760,
    height: int = 500,
    bin_count: int = 20,
    mode: str = "self-contained",
    accessibility: str = "universal",
    x_label: str = "Exam score",
    y_label: str = "Number of students",
    log_y: bool = False,
    theme: str = "corporate",
) -> str:
    """Assemble the full histogram SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with key ``score`` (float). Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels (the whole document, axes included).
    bin_count : int
        Approximate number of bins; the actual count is rounded to a nice
        bin width (see :func:`_nice_step`). Default 20.
    mode : str, optional
        Interactivity mode forwarded to
        :func:`_interactive.fullscreen_control`.
    accessibility : str, optional
        Accepted for CLI parity but a documented no-op: every bar is the
        single house blue — there is no categorical encoding to re-level.
    x_label, y_label : str, optional
        Axis titles.
    log_y : bool, optional
        Use a logarithmic count axis — useful when one or two bins dwarf
        the rest (a power-law-shaped distribution) and a linear axis would
        flatten every other bin to a sliver. The x-axis stays linear: bins
        are equal-width in score, not in pixels, so a log x-axis would mean
        re-binning geometrically, a different feature from an axis toggle.
    theme : str, optional
        Visual theme: ``"corporate"`` (default, Roboto -- byte-identical to
        the pre-theme render) or ``"academic"`` (LaTeX-style Latin Modern).
        See :func:`sprezzature_figures.fonts.chrome_stack_for_theme`.

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    _ = accessibility  # single-series bars; no categorical hues to re-level
    mono_family = mono_stack_for_theme(theme)
    rows = data if data else DEMO_DATA
    values = [float(r["score"]) for r in rows]
    edges, counts = _bin_scores(values, bin_count)
    n_bins = len(counts)
    total = len(values)
    max_count = max(counts) if counts else 1

    # ---- geometry -----------------------------------------------------
    plot_x, plot_y = 64.0, 118.0
    right_margin, bottom_reserved = 32.0, 96.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_reserved
    bin_w = plot_w / n_bins if n_bins else plot_w
    bar_gap = min(2.0, bin_w * 0.06)
    bar_w = max(1.0, bin_w - bar_gap)

    if log_y:
        pos_counts = [c for c in counts if c > 0]
        min_pos = min(pos_counts) if pos_counts else 1.0
        y_ticks = log_ticks(min_pos, max_count)
        y_lo, y_hi = y_ticks[0], y_ticks[-1]

        def y_for(count: float) -> float:
            return log_position(count, y_lo, y_hi, plot_y + plot_h, plot_y)
    else:
        # "Nice" 5-tick y-scale, computed up front: the headroom tick above
        # max_count sets the actual plotted domain, so y_for must scale against
        # it (not max_count) or that top gridline lands above the plot area.
        y_step = _nice_step(max_count / 4.0)
        y_ticks = []
        t = 0.0
        while t <= max_count + 1e-9:
            y_ticks.append(t)
            t += y_step
        if not y_ticks or y_ticks[-1] < max_count:
            y_ticks.append(y_ticks[-1] + y_step if y_ticks else y_step)
        y_domain = y_ticks[-1] or 1.0

        def y_for(count: float) -> float:
            return plot_y + plot_h - (count / y_domain * plot_h)

    peak_idx = counts.index(max_count) if counts else 0

    parts: List[str] = []
    parts.append(svg_open(width, height, "hist-title", "hist-desc", font_family=chrome_stack_for_theme(theme)))
    parts.append(f'<title id="hist-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="hist-desc">Histogram of {total} observations across {n_bins} bins '
        f'from {_fmt_edge(edges[0])} to {_fmt_edge(edges[-1])}. The tallest bin is '
        f'{_fmt_edge(edges[peak_idx])}-{_fmt_edge(edges[peak_idx + 1])} with {max_count} '
        f'observations, {max_count / total * 100:.0f}% of the sample.</desc>'
    )

    # Hover: brighten + lift the bar under the pointer so it reads as
    # interactive; guarded by prefers-reduced-motion per house style.
    parts.append(
        "<style>"
        ".bar{transition:filter .15s ease,transform .15s ease;"
        "transform-box:fill-box;transform-origin:bottom;}"
        ".bar:hover,.bar:focus{filter:brightness(1.08);transform:scaleY(1.015);outline:none;}"
        "@media (prefers-reduced-motion: reduce){.bar{transition:none;}"
        ".bar:hover,.bar:focus{transform:none;}}"
        "</style>"
    )

    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="40" y="56" font-size="26" font-weight="600" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(f'<text x="40" y="84" font-size="14" fill="{SECONDARY}">{xml_escape(subtitle)}</text>')

    # ---- y-axis gridlines + labels --------------------------------------
    for tick in y_ticks:
        ty = y_for(tick)
        parts.append(
            f'<line x1="{plot_x:.1f}" y1="{ty:.1f}" x2="{plot_x + plot_w:.1f}" y2="{ty:.1f}" '
            f'stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{plot_x - 10:.1f}" y="{ty + 4:.1f}" font-size="12" '
            f'font-family="{mono_family}" fill="{SECONDARY}" text-anchor="end">{fmt_number(tick)}</text>'
        )
    parts.append(
        f'<text x="24" y="{plot_y + plot_h / 2:.1f}" font-size="14" fill="{INK}" '
        f'text-anchor="middle" transform="rotate(-90 24 {plot_y + plot_h / 2:.1f})">'
        f'{xml_escape(y_label)}</text>'
    )

    # ---- bars: round the free (top) end only, capped per the bar family -
    for i in range(n_bins):
        count = counts[i]
        x = plot_x + i * bin_w
        y = y_for(count)
        h = plot_y + plot_h - y
        r = corner_radius(bar_w, max(h, 1.0), "bar")
        share = count / total * 100.0 if total else 0.0
        tip = f"{_fmt_edge(edges[i])}-{_fmt_edge(edges[i + 1])}: {count} students ({share:.1f}% of sample)"
        if h <= 0:
            continue
        path = bar_path(x, y, bar_w, h, r, side="top")
        parts.append(
            f'<path class="bar" tabindex="0" d="{path}" fill="{COLOR_BAR}" fill-opacity="0.88">'
            f'<title>{xml_escape(tip)}</title></path>'
        )

    # ---- x-axis: a tick at every other bin edge so labels never crowd ---
    axis_y = plot_y + plot_h
    parts.append(f'<line x1="{plot_x:.1f}" y1="{axis_y:.1f}" x2="{plot_x + plot_w:.1f}" y2="{axis_y:.1f}" stroke="{INK}" stroke-width="1.2"/>')
    label_stride = 2 if n_bins > 12 else 1
    for i, edge in enumerate(edges):
        if i % label_stride != 0 and i != n_bins:
            continue
        tx = plot_x + i * bin_w
        parts.append(f'<line x1="{tx:.1f}" y1="{axis_y:.1f}" x2="{tx:.1f}" y2="{axis_y + 6:.1f}" stroke="{INK}" stroke-width="1"/>')
        parts.append(
            f'<text x="{tx:.1f}" y="{axis_y + 22:.1f}" font-size="11" font-family="{mono_family}" '
            f'fill="{SECONDARY}" text-anchor="middle">{_fmt_edge(edge)}</text>'
        )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{axis_y + 46:.1f}" font-size="14" '
        f'fill="{INK}" text-anchor="middle">{xml_escape(x_label)}</text>'
    )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_histogram(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Exam Score Distribution",
    subtitle: str = "Synthetic sample, 300 students",
    width: int = 760,
    height: int = 500,
    bin_count: int = 20,
    mode: str = "self-contained",
    accessibility: str = "universal",
    x_label: str = "Exam score",
    y_label: str = "Number of students",
    log_y: bool = False,
    theme: str = "corporate",
) -> Path:
    """Render a hand-authored histogram and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with key ``score`` (float). Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/histogram.svg``.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    bin_count : int
        Approximate number of bins. Default 20.
    mode, accessibility : str
        Forwarded to :func:`build_svg`.
    x_label, y_label : str, optional
        Axis titles. Forwarded to :func:`build_svg`.
    log_y : bool, optional
        Use a logarithmic count axis. Forwarded to :func:`build_svg`.
    theme : str, optional
        Visual theme. Forwarded to :func:`build_svg`.

    Returns
    -------
    Path
        Absolute path to the written SVG file.

    Examples
    --------
    >>> p = make_histogram()
    >>> p.exists()
    True
    """
    svg = build_svg(
        data, title=title, subtitle=subtitle, width=width, height=height,
        bin_count=bin_count, mode=mode, accessibility=accessibility,
        x_label=x_label, y_label=y_label, log_y=log_y, theme=theme,
    )
    dest = Path(out) if out else svg_example_path(__file__, "histogram")
    return write_svg(dest, svg, theme=theme)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Generate a distribution histogram (hand-authored SVG).")
    p.add_argument("--out", default=None)
    p.add_argument("--title", default="Exam Score Distribution")
    p.add_argument("--subtitle", default="Synthetic sample, 300 students")
    p.add_argument("--width", type=int, default=760)
    p.add_argument("--height", type=int, default=500)
    p.add_argument("--bin-count", type=int, default=20)
    p.add_argument("--mode", choices=("self-contained", "external", "static"), default="self-contained")
    p.add_argument(
        "--accessibility",
        choices=("universal", "high-contrast", "monochrome", "deuteranopia", "protanopia", "tritanopia"),
        default="universal",
    )
    p.add_argument("--x-label", default="Exam score")
    p.add_argument("--y-label", default="Number of students")
    p.add_argument("--log-y", action="store_true", help="use a logarithmic count axis")
    args = p.parse_args()
    make_histogram(
        out=args.out, title=args.title, subtitle=args.subtitle,
        width=args.width, height=args.height, bin_count=args.bin_count,
        mode=args.mode, accessibility=args.accessibility,
        x_label=args.x_label, y_label=args.y_label, log_y=args.log_y,
    )
