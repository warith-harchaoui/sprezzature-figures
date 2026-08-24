#!/usr/bin/env python3
"""
make_bellcurve — a house-styled bell curve (normal distribution) as hand-authored SVG.

A bell curve visualises a normal distribution by plotting the probability
density function (PDF) against its horizontal axis. It communicates three
things at once: where the distribution is centred (the mean), how spread
out it is (the standard deviation), and how likely each range of values is
(area under the curve). Annotating the mean and one-sigma bands makes the
68-95-99.7 rule tangible.

Previously rendered via Vega-Lite (``vl_convert``); this module now samples
the PDF itself and paints the filled curve plus annotation lines by hand
-- no Vega, no matplotlib.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _scale import nice_ticks, nice_ticks_range  # noqa: E402
from _svg import foreground_tip_css, svg_open, tooltip_bubble, xml_escape  # noqa: E402
from _style import BG, GRIDLINE, INK, SECONDARY  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402


COLOR_FILL = "#007AFF"
COLOR_STROKE = "#0051A8"
COLOR_SIGMA1 = "#28CD41"
COLOR_MEAN = "#FF3B30"

# The make_<kind> contract's row-record view of the distribution: a single
# row carrying the two parameters the curve is drawn from. make_bellcurve()
# reads ``mean``/``std`` off the first row when ``data`` is supplied.
DEMO_DATA: List[Dict[str, Any]] = [{"mean": 72.4, "std": 9.1}]


def _normal_pdf(x: float, mean: float, std: float) -> float:
    """Return the normal probability density at ``x``."""
    z = (x - mean) / std
    return math.exp(-0.5 * z * z) / (std * math.sqrt(2.0 * math.pi))


def build_svg(
    mean: float = 72.4,
    std: float = 9.1,
    title: str = "Distribution of Student Exam Scores",
    subtitle: str = "Normal distribution fitted to 1,840 exam results; shaded area = one standard deviation around the mean",
    width: int = 845,
    height: int = 519,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
    y_axis_title: str = "Probability density",
    x_axis_title: str = "Value",
) -> str:
    """Assemble the full bell curve SVG document as a string.

    Parameters
    ----------
    mean, std : float
        Distribution parameters.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    mode : str, optional
        Forwarded to :func:`_interactive.fullscreen_control`.
    accessibility : str, optional
        Accepted for CLI parity but a documented no-op: the curve is a
        single house-blue fill, no categorical hues to re-level.
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
    n_points = 200
    x_min, x_max = mean - 4.0 * std, mean + 4.0 * std
    step = (x_max - x_min) / (n_points - 1)
    curve = [(x_min + i * step, _normal_pdf(x_min + i * step, mean, std)) for i in range(n_points)]
    peak_density = max(y for _, y in curve)
    # Nice round y-axis ticks (see _scale.nice_ticks) replace the old ad hoc
    # "raw peak * 1.18" headroom fudge -- both the tick values (previously
    # ugly quarters like 0.0103/0.0207/0.0310/0.0414/0.0517) and the axis
    # ceiling now come from the same rounded-up nice scale.
    y_tick_vals = nice_ticks(peak_density, n=5)
    peak_y = y_tick_vals[-1] if y_tick_vals[-1] > 0 else peak_density * 1.18

    plot_x, plot_y = 76.0, 118.0
    right_margin, bottom_reserved = 30.0, 70.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_reserved

    def x_for(v: float) -> float:
        return plot_x + (v - x_min) / (x_max - x_min) * plot_w

    def y_for(v: float) -> float:
        return plot_y + plot_h - (v / peak_y * plot_h)

    parts: List[str] = []
    parts.append(svg_open(width, height, "bc-title", "bc-desc", font_family=chrome_stack_for_theme(theme)))
    parts.append(f'<title id="bc-title">{xml_escape(title)}</title>')
    parts.append(f'<desc id="bc-desc">{xml_escape(subtitle)}</desc>')
    # House hover-tooltip pattern (previously absent from this generator --
    # every mark had a bare native <title> but no .hit/.tip reveal, no
    # :hover/:focus CSS at all, and no reduced-motion guard, unlike the rest
    # of the library since the tooltip_bubble standardisation).
    parts.append(
        "<style>"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        # A bubble drawn right next to its own mark would be covered by any
        # mark drawn afterward (SVG paints in document order, regardless of
        # hover) -- marks draw first, bubbles last, paired by id; see
        # _svg.foreground_tip_css. The curve is always a single mark; the
        # mean/-1sigma/+1sigma annotations are always exactly 3.
        + foreground_tip_css(1, mark_prefix="curve-hit", tip_prefix="curve-tip")
        + foreground_tip_css(3, mark_prefix="ann-hit", tip_prefix="ann-tip")
        + "@media (prefers-reduced-motion:reduce){.tip{transition:none}}"
        + "</style>"
    )

    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="40" y="46" font-size="24" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(f'<text x="40" y="70" font-size="14" fill="{SECONDARY}">{xml_escape(subtitle)}</text>')

    # ---- y-axis gridlines ----
    for val in y_tick_vals:
        ty = y_for(val)
        parts.append(
            f'<line x1="{plot_x:.1f}" y1="{ty:.1f}" x2="{plot_x + plot_w:.1f}" y2="{ty:.1f}" '
            f'stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{plot_x - 10:.1f}" y="{ty + 4:.1f}" font-size="10" font-family="{mono_family}" '
            f'fill="{SECONDARY}" text-anchor="end">{val:.4f}</text>'
        )
    parts.append(
        f'<text x="20" y="{plot_y + plot_h / 2:.1f}" font-size="13" fill="{INK}" '
        f'text-anchor="middle" transform="rotate(-90 20 {plot_y + plot_h / 2:.1f})">{xml_escape(y_axis_title)}</text>'
    )

    # ---- x-axis ----
    axis_y = plot_y + plot_h
    parts.append(
        f'<line x1="{plot_x:.1f}" y1="{axis_y:.1f}" x2="{plot_x + plot_w:.1f}" y2="{axis_y:.1f}" '
        f'stroke="{INK}" stroke-width="1"/>'
    )
    # Nice round x-axis ticks (see _scale.nice_ticks_range) instead of raw
    # eighths of mean+-4std, which produced labels like 36/45/54/63/72/81/
    # 91/100/109. Clipped to [x_min, x_max] so no tick lands outside the
    # plotted domain (x_for is not defined past that range).
    x_tick_vals = [t for t in nice_ticks_range(x_min, x_max, n=8) if x_min - 1e-9 <= t <= x_max + 1e-9]
    for val in x_tick_vals:
        tx = x_for(val)
        parts.append(
            f'<text x="{tx:.1f}" y="{axis_y + 20:.1f}" font-size="11" font-family="{mono_family}" '
            f'fill="{SECONDARY}" text-anchor="middle">{val:.0f}</text>'
        )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{axis_y + 42:.1f}" font-size="13" '
        f'fill="{INK}" text-anchor="middle">{xml_escape(x_axis_title)}</text>'
    )

    # ---- filled curve ----
    top_pts = [(x_for(x), y_for(y)) for x, y in curve]
    path_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in top_pts)
    path_d += f" L {top_pts[-1][0]:.1f},{axis_y:.1f} L {top_pts[0][0]:.1f},{axis_y:.1f} Z"
    tip = f"Normal(mean={mean:.1f}, std={std:.1f}), peak density {peak_density:.4f} at x={mean:.1f}"
    parts.append(
        f'<path id="curve-hit-0" class="hit" tabindex="0" d="{path_d}" fill="{COLOR_FILL}" fill-opacity="0.25" '
        f'stroke="{COLOR_STROKE}" stroke-width="2.5"><title>{xml_escape(tip)}</title></path>'
    )
    peak_x, peak_y_px = x_for(mean), y_for(peak_density)
    bell_tips: List[str] = [
        tooltip_bubble(
            peak_x, peak_y_px - 14,
            [f"Normal(μ={mean:.1f}, σ={std:.1f})", f"peak density {peak_density:.4f} at x={mean:.1f}"],
            canvas_w=width, canvas_h=height, ink=INK, secondary=SECONDARY, border=GRIDLINE,
            elem_id="curve-tip-0",
        )
    ]

    # ---- annotation lines: mean and +-1 sigma ----
    # ~34.1% of the area under a normal curve lies between the mean and one
    # sigma on either side (the standard 68-95-99.7 rule); surfaced in the
    # sigma tooltips since the on-canvas label only shows the raw value.
    annotations = [
        (mean, f"μ = {mean:.1f}", COLOR_MEAN, ["μ (mean)", f"{mean:.1f}", "center of the distribution"]),
        (
            mean - std,
            f"−1σ ({mean - std:.1f})",
            COLOR_SIGMA1,
            ["−1σ", f"{mean - std:.1f}", "~34.1% of the area lies between here and μ"],
        ),
        (
            mean + std,
            f"+1σ ({mean + std:.1f})",
            COLOR_SIGMA1,
            ["+1σ", f"{mean + std:.1f}", "~34.1% of the area lies between μ and here"],
        ),
    ]
    for ann_idx, (x_val, label, color, tip_lines) in enumerate(annotations):
        ax = x_for(x_val)
        parts.append(
            f'<line x1="{ax:.1f}" y1="{plot_y:.1f}" x2="{ax:.1f}" y2="{axis_y:.1f}" '
            f'stroke="{color}" stroke-width="1.5" stroke-dasharray="5 3"/>'
        )
        # Fat transparent hit-stroke over the (1.5px) visible dashed line so
        # it is a realistic hover/focus target. Its tooltip bubble is
        # collected into bell_tips and drawn after every mark, not right
        # here -- see the id-paired foreground_tip_css rule above.
        parts.append(
            f'<line id="ann-hit-{ann_idx}" class="hit" tabindex="0" x1="{ax:.1f}" y1="{plot_y:.1f}" x2="{ax:.1f}" y2="{axis_y:.1f}" '
            f'stroke="transparent" stroke-width="14"/>'
        )
        bell_tips.append(
            tooltip_bubble(
                ax, plot_y - 26,
                tip_lines,
                canvas_w=width, canvas_h=height, ink=INK, secondary=SECONDARY, border=GRIDLINE,
                elem_id=f"ann-tip-{ann_idx}",
            )
        )
        parts.append(
            f'<text x="{ax:.1f}" y="{plot_y - 8:.1f}" font-size="11" font-family="{mono_family}" '
            f'fill="{color}" text-anchor="middle">{xml_escape(label)}</text>'
        )
    parts.extend(bell_tips)

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_bellcurve(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    mean: Optional[float] = None,
    std: Optional[float] = None,
    out: Optional[Path | str] = None,
    title: str = "Distribution of Student Exam Scores",
    subtitle: str = "Normal distribution fitted to 1,840 exam results; shaded area = one standard deviation around the mean",
    width: int = 845,
    height: int = 519,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
    y_axis_title: str = "Probability density",
    x_axis_title: str = "Value",
) -> Path:
    """Render a hand-authored bell curve figure and write the SVG to *out*.

    Parameters
    ----------
    data : list of dict or None
        A single-row record ``[{"mean": ..., "std": ...}]`` (see
        :data:`DEMO_DATA`). Defaults to the illustrative exam-score
        distribution. Ignored for any parameter also passed explicitly via
        ``mean``/``std``.
    mean : float or None
        Distribution mean; overrides ``data`` when given. Falls back to
        72.4 (exam score example) if neither is supplied.
    std : float or None
        Standard deviation; overrides ``data`` when given. Falls back to 9.1.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/bellcurve.svg``.
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
    >>> p = make_bellcurve()
    >>> p.exists()
    True
    """
    rows = data if data else DEMO_DATA
    rec = rows[0] if rows else {}
    resolved_mean = mean if mean is not None else float(rec.get("mean", 72.4))
    resolved_std = std if std is not None else float(rec.get("std", 9.1))
    svg = build_svg(resolved_mean, resolved_std, title=title, subtitle=subtitle, width=width, height=height,
                     mode=mode, accessibility=accessibility, theme=theme, y_axis_title=y_axis_title, x_axis_title=x_axis_title)
    dest = Path(out) if out else svg_example_path(__file__, "bellcurve")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "bellcurve", build_svg, description="Generate a bell curve (normal distribution) figure.")


if __name__ == "__main__":
    main()
