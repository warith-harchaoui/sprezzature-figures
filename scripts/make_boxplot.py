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
from _svg import svg_open, xml_escape  # noqa: E402
from _style import BG, FONT_MONO, GRIDLINE, INK, SECONDARY  # noqa: E402

COLOR_BOX = "#007AFF"

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
) -> str:
    """Assemble the full box plot SVG document as a string.

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

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    _ = accessibility
    rows = data if data else DEMO_DATA
    seen_depts: List[str] = []
    for r in rows:
        if r["department"] not in seen_depts:
            seen_depts.append(r["department"])
    depts = [d for d in DEPARTMENTS if d in seen_depts] + [d for d in seen_depts if d not in DEPARTMENTS]
    by_dept: Dict[str, List[float]] = {d: [] for d in depts}
    for r in rows:
        if r["department"] in by_dept:
            by_dept[r["department"]].append(float(r["salary"]))
    stats = {d: _five_number_summary(v) for d, v in by_dept.items()}

    all_vals = [v for vals in by_dept.values() for v in vals]
    y_min, y_max = min(all_vals), max(all_vals)
    pad = (y_max - y_min) * 0.08
    y0, y1 = y_min - pad, y_max + pad

    plot_x, plot_y = 60.0, 118.0
    right_margin, bottom_reserved = 30.0, 70.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_reserved
    n = len(depts)
    bin_w = plot_w / n if n else plot_w
    box_w = max(20.0, bin_w * 0.4)

    def y_for(v: float) -> float:
        return plot_y + plot_h - (v - y0) / (y1 - y0) * plot_h

    parts: List[str] = []
    parts.append(svg_open(width, height, "bp-title", "bp-desc"))
    parts.append(f'<title id="bp-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="bp-desc">Box plot of {n} departments. Range {y_min:.0f} to {y_max:.0f}. '
        f'Hover or focus a box for its exact median and quartiles.</desc>'
    )

    parts.append(
        "<style>"
        ".box{transition:filter .15s ease;}"
        ".box:hover,.box:focus{filter:brightness(1.1);outline:none;}"
        "@media (prefers-reduced-motion: reduce){.box{transition:none;}}"
        "</style>"
    )

    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="40" y="46" font-size="24" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(f'<text x="40" y="70" font-size="14" fill="{SECONDARY}">{xml_escape(subtitle)}</text>')

    # ---- y-axis gridlines ----
    y_ticks = 6
    for i in range(y_ticks + 1):
        val = y0 + (y1 - y0) * i / y_ticks
        ty = y_for(val)
        parts.append(
            f'<line x1="{plot_x:.1f}" y1="{ty:.1f}" x2="{plot_x + plot_w:.1f}" y2="{ty:.1f}" '
            f'stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{plot_x - 10:.1f}" y="{ty + 4:.1f}" font-size="11" font-family="{FONT_MONO}" '
            f'fill="{SECONDARY}" text-anchor="end">{val:.0f}</text>'
        )
    parts.append(
        f'<text x="18" y="{plot_y + plot_h / 2:.1f}" font-size="13" fill="{INK}" '
        f'text-anchor="middle" transform="rotate(-90 18 {plot_y + plot_h / 2:.1f})">Salary (thousands EUR)</text>'
    )

    # ---- boxes ----
    for i, d in enumerate(depts):
        s = stats[d]
        cx = plot_x + i * bin_w + bin_w / 2
        x_left = cx - box_w / 2
        y_q1, y_q3 = y_for(s["q1"]), y_for(s["q3"])
        y_med = y_for(s["med"])
        y_whisk_lo, y_whisk_hi = y_for(s["whisker_lo"]), y_for(s["whisker_hi"])

        parts.append(f'<line x1="{cx:.1f}" y1="{y_whisk_hi:.1f}" x2="{cx:.1f}" y2="{y_q3:.1f}" stroke="{INK}" stroke-width="1.2"/>')
        parts.append(f'<line x1="{cx:.1f}" y1="{y_q1:.1f}" x2="{cx:.1f}" y2="{y_whisk_lo:.1f}" stroke="{INK}" stroke-width="1.2"/>')
        parts.append(f'<line x1="{x_left + box_w * 0.25:.1f}" y1="{y_whisk_hi:.1f}" x2="{x_left + box_w * 0.75:.1f}" y2="{y_whisk_hi:.1f}" stroke="{INK}" stroke-width="1.2"/>')
        parts.append(f'<line x1="{x_left + box_w * 0.25:.1f}" y1="{y_whisk_lo:.1f}" x2="{x_left + box_w * 0.75:.1f}" y2="{y_whisk_lo:.1f}" stroke="{INK}" stroke-width="1.2"/>')

        tip = (
            f"{d}: median {s['med']:.0f}, Q1 {s['q1']:.0f}, Q3 {s['q3']:.0f}, "
            f"whiskers {s['whisker_lo']:.0f}-{s['whisker_hi']:.0f}, n={s['n']}"
        )
        parts.append(
            f'<rect class="box" tabindex="0" x="{x_left:.1f}" y="{y_q3:.1f}" '
            f'width="{box_w:.1f}" height="{max(1.0, y_q1 - y_q3):.1f}" '
            f'fill="{COLOR_BOX}" fill-opacity="0.85"><title>{xml_escape(tip)}</title></rect>'
        )
        parts.append(
            f'<line x1="{x_left:.1f}" y1="{y_med:.1f}" x2="{x_left + box_w:.1f}" y2="{y_med:.1f}" '
            f'stroke="{BG}" stroke-width="2"/>'
        )
        for o in s["outliers"]:
            parts.append(
                f'<circle cx="{cx:.1f}" cy="{y_for(o):.1f}" r="3" fill="none" stroke="{COLOR_BOX}" stroke-width="1.2"/>'
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
        f'fill="{INK}" text-anchor="middle">Department</text>'
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
                     mode=mode, accessibility=accessibility)
    dest = Path(out) if out else svg_example_path(__file__, "boxplot")
    return write_svg(dest, svg)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "boxplot", build_svg, description="Generate a box plot by category.")


if __name__ == "__main__":
    main()
