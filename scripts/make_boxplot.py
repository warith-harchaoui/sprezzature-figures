#!/usr/bin/env python3
"""
make_boxplot — a house-styled box plot by category as hand-authored SVG.

Summarises a numeric distribution's median, quartiles, and outliers per
category using the standard Tukey box-and-whisker convention. Typical
uses: salary distribution by department, response time by service, test
scores by class.

Previously rendered via Vega-Lite's native ``boxplot`` mark; this module
now computes the five-number summary and outliers itself and paints the
box, whiskers, and outlier points by hand -- no Vega, no matplotlib.
Every box carries a native ``<title>`` tooltip with its exact quartiles.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _style import BG, GRIDLINE, INK, SECONDARY  # noqa: E402
from _scale import log_position, log_ticks, nice_ticks_range  # noqa: E402
from _svg import svg_open, tooltip_bubble, xml_escape  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402

COLOR_BOX = "#007AFF"

# House palette for grouped boxes (side-by-side boxes within each category).
GROUP_COLORS = ["#007AFF", "#FF9500", "#34C759", "#AF52DE", "#FF2D55", "#5AC8FA"]

DEPARTMENTS = ["Engineering", "Sales", "Marketing", "Support"]


def _make_demo_data() -> List[Dict[str, Any]]:
    rng = random.Random(11)
    ranges = {"Engineering": (65, 130), "Sales": (50, 110), "Marketing": (45, 95), "Support": (40, 80)}
    rows: List[Dict[str, Any]] = []
    for dept, (lo, hi) in ranges.items():
        for _ in range(25):
            rows.append({"department": dept, "salary": round(rng.uniform(lo, hi), 1)})
    return rows


DEMO_DATA: List[Dict[str, Any]] = _make_demo_data()


def _quantile(sorted_vals: List[float], q: float) -> float:
    """Linear-interpolation quantile (matches numpy's default / Vega-Lite's)."""
    if not sorted_vals:
        return 0.0
    pos = q * (len(sorted_vals) - 1)
    lo, hi = int(pos), min(int(pos) + 1, len(sorted_vals) - 1)
    frac = pos - lo
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * frac


def _five_number_summary(values: List[float]) -> Dict[str, Any]:
    s = sorted(values)
    q1, med, q3 = _quantile(s, 0.25), _quantile(s, 0.5), _quantile(s, 0.75)
    iqr = q3 - q1
    lo_fence, hi_fence = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    inliers = [v for v in s if lo_fence <= v <= hi_fence]
    outliers = [v for v in s if v < lo_fence or v > hi_fence]
    whisker_lo = min(inliers) if inliers else s[0]
    whisker_hi = max(inliers) if inliers else s[-1]
    return {"q1": q1, "med": med, "q3": q3, "whisker_lo": whisker_lo, "whisker_hi": whisker_hi,
            "outliers": outliers, "n": len(s)}


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Salary Distribution by Department",
    subtitle: str = "Synthetic sample, thousands of EUR",
    width: int = 745,
    height: int = 505,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
    x_label: str = "Department",
    y_label: str = "Salary (thousands EUR)",
    log_y: bool = False,
) -> str:
    """Assemble the full box plot SVG document as a string.

    When rows carry an optional ``group`` key in addition to ``department``
    (category) and ``salary`` (value), the boxes are drawn grouped: one colored
    box per group side by side within each category, with a legend. Without a
    ``group`` key the behaviour is the original single-box-per-category plot.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``department`` (str) and ``salary`` (numeric).
        Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    mode : str, optional
        Forwarded to :func:`_interactive.fullscreen_control`.
    accessibility : str, optional
        Accepted for CLI parity but a documented no-op: every box is the
        single house blue, no categorical hues to re-level.
    theme : str, optional
        Visual theme: ``"corporate"`` (default, Roboto -- byte-identical to
        the pre-theme render) or ``"academic"`` (LaTeX-style Latin Modern).
        See :func:`sprezzature_figures.fonts.chrome_stack_for_theme`.

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    _ = accessibility
    mono_family = mono_stack_for_theme(theme)
    rows = data if data else DEMO_DATA
    grouped = any("group" in r for r in rows)

    # Categories (x positions) in first-appearance order, honouring the curated
    # DEPARTMENTS order for the demo data.
    seen_depts: List[str] = []
    for r in rows:
        if str(r["department"]) not in seen_depts:
            seen_depts.append(str(r["department"]))
    depts = [d for d in DEPARTMENTS if d in seen_depts] + [
        d for d in seen_depts if d not in DEPARTMENTS
    ]
    # Groups (colored boxes within a category) in first-appearance order.
    groups: List[Optional[str]]
    if grouped:
        groups = []
        for r in rows:
            g = str(r.get("group", ""))
            if g not in groups:
                groups.append(g)
    else:
        groups = [None]

    buckets: Dict[tuple, List[float]] = {(d, g): [] for d in depts for g in groups}
    for r in rows:
        d = str(r["department"])
        g = str(r.get("group", "")) if grouped else None
        if (d, g) in buckets:
            buckets[(d, g)].append(float(r["salary"]))
    stats = {key: _five_number_summary(v) for key, v in buckets.items() if v}

    all_vals = [v for vals in buckets.values() for v in vals]
    y_min, y_max = min(all_vals), max(all_vals)
    if log_y:
        pos = [v for v in all_vals if v > 0]
        lo_pos = min(pos) if pos else 1e-3
        ticks = log_ticks(lo_pos, y_max)
        if len(ticks) > 5:  # cap to ~4 decades so the boxes stay the focus
            ticks = ticks[-5:]
        y_tick_vals = ticks
        y0, y1 = ticks[0], ticks[-1]
    else:
        pad = ((y_max - y_min) or 1.0) * 0.08
        y0, y1 = y_min - pad, y_max + pad
        if y_min >= 0:  # a non-negative quantity never dips below zero on the axis
            y0 = max(0.0, y0)
        # Nice round tick values (see _scale.nice_ticks_range) instead of raw
        # sixths of the padded [y0, y1] span, which produced labels like
        # 36.0/52.6/69.2/85.9/102.5/119.1/135.7. Clipped back to [y0, y1] so
        # no gridline is drawn outside the plot rectangle.
        y_tick_vals = [t for t in nice_ticks_range(y0, y1, n=6) if y0 - 1e-9 <= t <= y1 + 1e-9]

    def _fmt(v: float) -> str:
        """Tick / tooltip format adapted to the value range (small values keep decimals)."""
        if log_y:
            return f"{v:g}"
        span = y1 - y0
        if span >= 100:
            return f"{v:.0f}"
        if span >= 10:
            return f"{v:.1f}"
        if span >= 1:
            return f"{v:.2f}"
        return f"{v:.3f}"

    plot_x, plot_y = 64.0, 118.0
    if grouped:  # reserve a legend row under the subtitle
        plot_y = 142.0
    right_margin, bottom_reserved = 30.0, 70.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_reserved
    n = len(depts)
    bin_w = plot_w / n if n else plot_w
    ng = len(groups)
    inner = bin_w * (0.72 if grouped else 0.4)
    box_w = max(10.0, inner / ng)
    colors = GROUP_COLORS if grouped else [COLOR_BOX]

    def y_for(v: float) -> float:
        if log_y:
            return log_position(max(v, y0), y0, y1, plot_y + plot_h, plot_y)
        return plot_y + plot_h - (v - y0) / (y1 - y0) * plot_h

    def cx_for(i: int, j: int) -> float:
        """Center x of category ``i``, group ``j`` (side-by-side within the bin)."""
        base = plot_x + i * bin_w + bin_w / 2
        return base + (j - (ng - 1) / 2.0) * box_w

    parts: List[str] = []
    parts.append(svg_open(width, height, "bp-title", "bp-desc", font_family=chrome_stack_for_theme(theme)))
    parts.append(f'<title id="bp-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="bp-desc">Box plot of {n} categories. Range {_fmt(y_min)} to '
        f'{_fmt(y_max)}. Hover or focus a box for its exact median and quartiles.</desc>'
    )

    parts.append(
        "<style>"
        ".box{transition:filter .15s ease;}"
        ".box:hover,.box:focus{filter:brightness(1.1);outline:none;}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        ".hit:hover+.tip,.hit:focus+.tip{opacity:1}"
        "@media (prefers-reduced-motion: reduce){.box{transition:none;}"
        ".tip{transition:none}}"
        "</style>"
    )

    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="40" y="46" font-size="24" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(f'<text x="40" y="70" font-size="14" fill="{SECONDARY}">{xml_escape(subtitle)}</text>')

    # ---- legend (grouped only) ----
    if grouped:
        lx, ly = 64.0, 96.0
        for j, gname in enumerate(groups):
            parts.append(
                f'<rect x="{lx:.1f}" y="{ly - 10:.1f}" width="13" height="13" rx="2.5" '
                f'fill="{colors[j % len(colors)]}" fill-opacity="0.85"/>'
            )
            label = xml_escape(str(gname))
            parts.append(
                f'<text x="{lx + 19:.1f}" y="{ly + 1:.1f}" font-size="12.5" '
                f'fill="{INK}">{label}</text>'
            )
            lx += 19 + 8.2 * len(str(gname)) + 26

    # ---- y-axis gridlines ----
    for val in y_tick_vals:
        ty = y_for(val)
        parts.append(
            f'<line x1="{plot_x:.1f}" y1="{ty:.1f}" x2="{plot_x + plot_w:.1f}" y2="{ty:.1f}" '
            f'stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{plot_x - 10:.1f}" y="{ty + 4:.1f}" font-size="11" font-family="{mono_family}" '
            f'fill="{SECONDARY}" text-anchor="end">{_fmt(val)}</text>'
        )
    parts.append(
        f'<text x="18" y="{plot_y + plot_h / 2:.1f}" font-size="13" fill="{INK}" '
        f'text-anchor="middle" transform="rotate(-90 18 {plot_y + plot_h / 2:.1f})">'
        f'{xml_escape(y_label)}</text>'
    )

    # ---- boxes ----
    cap = max(4.0, box_w * 0.32)  # whisker cap half-width
    for i, d in enumerate(depts):
        for j, gname in enumerate(groups):
            s = stats.get((d, gname))
            if not s:
                continue
            color = colors[j % len(colors)]
            cx = cx_for(i, j)
            x_left = cx - box_w / 2
            y_q1, y_q3 = y_for(s["q1"]), y_for(s["q3"])
            y_med = y_for(s["med"])
            y_whisk_lo, y_whisk_hi = y_for(s["whisker_lo"]), y_for(s["whisker_hi"])

            parts.append(f'<line x1="{cx:.1f}" y1="{y_whisk_hi:.1f}" x2="{cx:.1f}" y2="{y_q3:.1f}" stroke="{INK}" stroke-width="1.2"/>')
            parts.append(f'<line x1="{cx:.1f}" y1="{y_q1:.1f}" x2="{cx:.1f}" y2="{y_whisk_lo:.1f}" stroke="{INK}" stroke-width="1.2"/>')
            parts.append(f'<line x1="{cx - cap:.1f}" y1="{y_whisk_hi:.1f}" x2="{cx + cap:.1f}" y2="{y_whisk_hi:.1f}" stroke="{INK}" stroke-width="1.2"/>')
            parts.append(f'<line x1="{cx - cap:.1f}" y1="{y_whisk_lo:.1f}" x2="{cx + cap:.1f}" y2="{y_whisk_lo:.1f}" stroke="{INK}" stroke-width="1.2"/>')

            gtxt = f"{gname}, " if grouped else ""
            tip = (
                f"{gtxt}{d}: median {_fmt(s['med'])}, Q1 {_fmt(s['q1'])}, "
                f"Q3 {_fmt(s['q3'])}, whiskers {_fmt(s['whisker_lo'])}-"
                f"{_fmt(s['whisker_hi'])}, n={s['n']}"
            )
            parts.append(
                f'<rect class="box hit" tabindex="0" x="{x_left:.1f}" y="{y_q3:.1f}" '
                f'width="{box_w:.1f}" height="{max(1.0, y_q1 - y_q3):.1f}" '
                f'fill="{color}" fill-opacity="0.85"><title>{xml_escape(tip)}</title></rect>'
            )
            parts.append(
                tooltip_bubble(
                    cx, y_q3 - 10,
                    [
                        f"{gtxt}{d}" if grouped else str(d),
                        f"median {_fmt(s['med'])}",
                        f"Q1 {_fmt(s['q1'])} — Q3 {_fmt(s['q3'])}",
                        f"whiskers {_fmt(s['whisker_lo'])}-{_fmt(s['whisker_hi'])}, n={s['n']}",
                    ],
                    anchor="middle", canvas_w=width, canvas_h=height,
                    ink=INK, secondary=SECONDARY, border=GRIDLINE,
                )
            )
            parts.append(
                f'<line x1="{x_left:.1f}" y1="{y_med:.1f}" x2="{x_left + box_w:.1f}" y2="{y_med:.1f}" '
                f'stroke="{BG}" stroke-width="2"/>'
            )
            for o in s["outliers"]:
                parts.append(
                    f'<circle cx="{cx:.1f}" cy="{y_for(o):.1f}" r="2.5" fill="none" stroke="{color}" stroke-width="1.2"/>'
                )

    # ---- x-axis ----
    axis_y = plot_y + plot_h
    parts.append(
        f'<line x1="{plot_x:.1f}" y1="{axis_y:.1f}" x2="{plot_x + plot_w:.1f}" y2="{axis_y:.1f}" '
        f'stroke="{INK}" stroke-width="1.2"/>'
    )
    for i, d in enumerate(depts):
        tx = plot_x + i * bin_w + bin_w / 2
        parts.append(
            f'<text x="{tx:.1f}" y="{axis_y + 20:.1f}" font-size="13" fill="{INK}" '
            f'text-anchor="middle">{xml_escape(d)}</text>'
        )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{axis_y + 44:.1f}" font-size="13" '
        f'fill="{INK}" text-anchor="middle">{xml_escape(x_label)}</text>'
    )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_boxplot(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Salary Distribution by Department",
    subtitle: str = "Synthetic sample, thousands of EUR",
    width: int = 745,
    height: int = 505,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
    x_label: str = "Department",
    y_label: str = "Salary (thousands EUR)",
    log_y: bool = False,
) -> Path:
    """Render a hand-authored box plot and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``department`` (str) and ``salary`` (float).
        Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/boxplot.svg``.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
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
    >>> p = make_boxplot()
    >>> p.exists()
    True
    """
    svg = build_svg(data, title=title, subtitle=subtitle, width=width, height=height,
                     mode=mode, accessibility=accessibility, theme=theme,
                     x_label=x_label, y_label=y_label, log_y=log_y)
    dest = Path(out) if out else svg_example_path(__file__, "boxplot")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "boxplot", build_svg, description="Generate a box plot by category.")


if __name__ == "__main__":
    main()
