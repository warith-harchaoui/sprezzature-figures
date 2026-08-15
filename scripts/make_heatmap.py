#!/usr/bin/env python3
"""
make_heatmap — a house-styled row x column activity heatmap as a hand-authored SVG.

Encodes a numeric value as cell color across two categorical axes: rows are
days of the week, columns are hours of the day, and each cell's fill is a
single pale-to-navy blue ramp (a monotone lightness sweep, so it survives
greyscale and every colour-vision deficiency without a second encoding).
Typical uses: activity by day-of-week x hour, correlation matrices, A/B test
results by cohort x variant.

Previously rendered via Vega-Lite (``vl_convert``); this module now builds
the ``<svg>`` markup by hand — no Vega, no matplotlib — so it matches the
other hero figures and every cell carries a native ``<title>`` tooltip with
its exact reading ("Tue, 09:00-10:00: activity 58, 4.2% of week total").
Per the Sprezzature Corner Policy, grid cells never round (``rx`` stays at
0 — the grid *is* the message); hovering a cell dims every other cell and
keeps that cell's whole row and column lit, a pure-CSS crosshair
(``:has()``) that makes "how does this day compare" and "how does this hour
compare" both readable at a glance, guarded by ``prefers-reduced-motion``.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import svg_example_path, write_svg  # noqa: E402
from _style import GRIDLINE  # noqa: E402
from _svg import svg_open, tooltip_bubble, xml_escape  # noqa: E402

from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402

INK = "#1D1D1F"
SECONDARY = "#6E6E73"
BG = "#FFFFFF"
FONT_MONO = "Roboto Mono, ui-monospace, monospace"

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
HOURS = list(range(24))

# Sequential blue ramp — pale sky -> system blue -> deep navy. Mono-hue, so it
# encodes magnitude by lightness alone and is colour-vision-deficiency- and
# greyscale-safe by construction (the same ramp make_imshow-interpolated.py
# uses for its continuous field, applied here to a discrete grid).
_RAMP: Tuple[Tuple[float, str], ...] = (
    (0.00, "#EAF3FF"),
    (0.62, "#007AFF"),
    (1.00, "#0A4DA0"),
)


def _ramp_hex(t: float) -> str:
    """Sample the house blue ramp at position ``t`` in ``[0, 1]``."""
    t = min(1.0, max(0.0, t))
    for (lo_t, lo_c), (hi_t, hi_c) in zip(_RAMP, _RAMP[1:]):
        if lo_t <= t <= hi_t:
            local = (t - lo_t) / (hi_t - lo_t) if hi_t > lo_t else 0.0
            ar, ag, ab = int(lo_c[1:3], 16), int(lo_c[3:5], 16), int(lo_c[5:7], 16)
            br, bg, bb = int(hi_c[1:3], 16), int(hi_c[3:5], 16), int(hi_c[5:7], 16)
            r = round(ar + (br - ar) * local)
            g = round(ag + (bg - ag) * local)
            b = round(ab + (bb - ab) * local)
            return f"#{r:02X}{g:02X}{b:02X}"
    return _RAMP[-1][1]


def _make_demo_data() -> List[Dict[str, Any]]:
    rng = random.Random(11)
    rows: List[Dict[str, Any]] = []
    for day_idx, day in enumerate(DAYS):
        is_weekend = day_idx >= 5
        for hour in HOURS:
            if is_weekend:
                base = 30 if 11 <= hour <= 23 else 5
            else:
                base = 60 if (9 <= hour <= 11 or 18 <= hour <= 21) else (20 if 8 <= hour <= 22 else 3)
            rows.append({"day": day, "hour": hour, "activity": max(0, round(base + rng.uniform(-8, 8)))})
    return rows


DEMO_DATA: List[Dict[str, Any]] = _make_demo_data()


def _prepare_grid(
    data: List[Dict[str, Any]],
) -> Tuple[List[Any], List[Any], Dict[Tuple[Any, Any], float]]:
    """Fold rows of ``{day, hour, activity}`` into ordered axes + a lookup.

    Row order prefers the canonical Mon-Sun week when every day is present;
    otherwise rows/columns are ordered by first appearance (numeric columns
    sort numerically). Keeps the figure usable on arbitrary caller data, not
    only :data:`DEMO_DATA`.
    """
    days: List[Any] = []
    hours: List[Any] = []
    lookup: Dict[Tuple[Any, Any], float] = {}
    for row in data:
        d, h, v = row["day"], row["hour"], float(row["activity"])
        if d not in days:
            days.append(d)
        if h not in hours:
            hours.append(h)
        lookup[(d, h)] = v
    if set(days) == set(DAYS):
        days = [d for d in DAYS if d in days]
    try:
        hours = sorted(hours, key=float)
    except (TypeError, ValueError):
        hours = sorted(hours, key=str)
    return days, hours, lookup


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Activity by Day and Hour",
    subtitle: str = "Synthetic weekly usage pattern",
    width: int = 900,
    height: int = 400,
    mode: str = "self-contained",
    accessibility: str = "universal",
    x_label: str = "Hour of day",
    y_label: str = "",
    legend_label: str = "Activity",
    show_cell_labels: bool = True,
    square: bool = False,
    theme: str = "corporate",
    vmin: Optional[float] = None,
    vmax: Optional[float] = None,
) -> str:
    """Assemble the full row x column heatmap SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``day``, ``hour``, ``activity`` (numeric). Defaults to
        :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels (the whole document, axes/legend included).
    mode : str, optional
        Interactivity mode forwarded to
        :func:`_interactive.fullscreen_control`.
    accessibility : str, optional
        Accepted for CLI parity but a documented no-op: the single blue
        sequential ramp already encodes magnitude by lightness alone, so it
        is CVD- and greyscale-safe without a categorical re-levelling.
    theme : str, optional
        Visual theme: ``"corporate"`` (default, Roboto -- byte-identical to
        the pre-theme render) or ``"academic"`` (LaTeX-style Latin Modern).
        See :func:`sprezzature_figures.fonts.chrome_stack_for_theme`. The
        sequential blue ramp itself is not re-themed (no categorical hues to
        swap), matching the same deferral as other generators' sequential
        ramps.
    vmin, vmax : float, optional
        Explicit color-scale extremes, overriding the default of this
        call's own data min/max. Set both to the same fixed values across
        several heatmaps (e.g. a before/after pair) so their color ramps
        stay comparable instead of each auto-scaling to its own range.

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    _ = accessibility  # see docstring: the sequential ramp needs no re-levelling
    mono_family = mono_stack_for_theme(theme)
    rows = data if data else DEMO_DATA
    days, hours, lookup = _prepare_grid(rows)
    n_r, n_c = len(days), len(hours)

    values = list(lookup.values())
    vmax = vmax if vmax is not None else (max(values) if values else 0.0)
    vmin = vmin if vmin is not None else (min(values) if values else 0.0)
    total = sum(values)
    peak_key = max(lookup, key=lambda k: lookup[k]) if lookup else (None, None)

    # ---- geometry: content width/height drive everything else ------------
    grid_x = 92.0
    grid_y = 118.0
    legend_gap = 40.0
    legend_w = 18.0
    legend_labels_w = 46.0
    right_margin = 26.0
    bottom_reserved = 64.0

    grid_w = max(1.0, width - grid_x - legend_gap - legend_w - legend_labels_w - right_margin)
    grid_h = max(1.0, height - grid_y - bottom_reserved)
    cell_w = grid_w / n_c if n_c else grid_w
    cell_h = grid_h / n_r if n_r else grid_h
    if square and n_c and n_r:
        cell = min(cell_w, cell_h)  # equal cells so an N x N matrix reads square
        cell_w = cell_h = cell
        grid_w, grid_h = cell * n_c, cell * n_r

    def _fmt(v: float) -> str:
        """Adaptive numeric label: decimals for fractional data, integers otherwise."""
        if v == 0:
            return "0"
        av = abs(v)
        if av >= 10 or av == int(av):
            return f"{v:.0f}"
        if av >= 1:
            return f"{v:.1f}"
        return f"{v:.2f}"

    parts: List[str] = []
    parts.append(
        svg_open(width, height, "hm-title", "hm-desc", font_family=chrome_stack_for_theme(theme))
    )
    parts.append(f'<title id="hm-title">{xml_escape(title)}</title>')
    peak_desc = ""
    if peak_key[0] is not None:
        peak_desc = (
            f" The busiest cell is {xml_escape(str(peak_key[0]))} at "
            f"{xml_escape(str(peak_key[1]))}, {lookup[peak_key]:.0f}."
        )
    parts.append(
        f'<desc id="hm-desc">A {n_r} by {n_c} grid heatmap. Cell colour runs a '
        f'pale-to-navy blue ramp from {vmin:.0f} to {vmax:.0f}.{peak_desc}</desc>'
    )

    # ---- style: pure-CSS crosshair hover + dark mode, reduced-motion safe -
    style_rows = [
        ".cell{transition:opacity .15s ease;}",
        "svg:hover .cell,svg:focus-within .cell{opacity:.30;}",
    ]
    for i in range(n_r):
        style_rows.append(f"svg:has(.day-{i}:hover) .day-{i}{{opacity:1;}}")
    for j in range(n_c):
        style_rows.append(f"svg:has(.hour-{j}:hover) .hour-{j}{{opacity:1;}}")
    style_rows.append("@media (prefers-reduced-motion: reduce){.cell{transition:none;}}")
    style_rows.append(".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}")
    style_rows.append(".hit:hover+.tip,.hit:focus+.tip{opacity:1}")
    style_rows.append("@media (prefers-reduced-motion:reduce){.tip{transition:none}}")
    parts.append("<style>\n" + "\n".join(style_rows) + "\n</style>")

    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="40" y="56" font-size="26" font-weight="600" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(f'<text x="40" y="84" font-size="14" fill="{SECONDARY}">{xml_escape(subtitle)}</text>')

    # ---- cells (never rounded — the grid is the message) ------------------
    span = (vmax - vmin) or 1.0
    for i, day in enumerate(days):
        y = grid_y + i * cell_h
        if show_cell_labels:
            parts.append(
                f'<text x="{grid_x - 14:.1f}" y="{y + cell_h / 2 + 5:.1f}" font-size="13" '
                f'fill="{INK}" text-anchor="end">{xml_escape(str(day))}</text>'
            )
        for j, hour in enumerate(hours):
            x = grid_x + j * cell_w
            v = lookup.get((day, hour))
            if isinstance(hour, int):
                span_lbl = f"{hour:02d}:00-{(hour + 1) % 24:02d}:00"
            else:
                span_lbl = str(hour)
            if v is None:
                fill = "#F5F5F7"
                tip = f"{day}: no reading at {hour}"
                bubble_lines = [str(day), span_lbl, "no reading"]
            else:
                t = (v - vmin) / span
                fill = _ramp_hex(t)
                share = (v / total * 100.0) if total else 0.0
                tip = f"{day}, {span_lbl}: activity {v:.0f} ({share:.1f}% of week total)"
                bubble_lines = [str(day), span_lbl, f"activity {v:.0f} ({share:.1f}% of week total)"]
            parts.append(
                f'<rect class="cell hit day-{i} hour-{j}" tabindex="0" x="{x:.2f}" y="{y:.2f}" '
                f'width="{cell_w:.2f}" height="{cell_h:.2f}" fill="{fill}">'
                f'<title>{xml_escape(tip)}</title></rect>'
            )
            parts.append(
                tooltip_bubble(
                    x + cell_w / 2, y - 4,
                    bubble_lines,
                    anchor="middle", canvas_w=width, canvas_h=height,
                    ink=INK, secondary=SECONDARY, border=GRIDLINE,
                )
            )

    # ---- x-axis (hour) — a tick every 3rd column so labels never crowd ----
    axis_y = grid_y + grid_h
    if show_cell_labels:
        for j, hour in enumerate(hours):
            if j % 3 != 0:
                continue
            tx = grid_x + j * cell_w + cell_w / 2
            parts.append(
                f'<text x="{tx:.1f}" y="{axis_y + 20:.1f}" font-size="12" '
                f'font-family="{mono_family}" fill="{SECONDARY}" text-anchor="middle">{hour}</text>'
            )
    if x_label:
        parts.append(
            f'<text x="{grid_x + grid_w / 2:.1f}" y="{axis_y + (46 if show_cell_labels else 24):.1f}" '
            f'font-size="14" fill="{INK}" text-anchor="middle">{xml_escape(x_label)}</text>'
        )
    if y_label:
        yc = grid_y + grid_h / 2
        parts.append(
            f'<text x="{grid_x - 30:.1f}" y="{yc:.1f}" font-size="14" fill="{INK}" '
            f'text-anchor="middle" transform="rotate(-90 {grid_x - 30:.1f} {yc:.1f})">{xml_escape(y_label)}</text>'
        )

    # ---- colour legend (vertical ramp, right of the grid) ------------------
    leg_x = grid_x + grid_w + legend_gap
    leg_top = grid_y
    leg_h = grid_h
    grad_id = "hm-ramp"
    parts.append(f'<defs><linearGradient id="{grad_id}" x1="0" y1="1" x2="0" y2="0">')
    for pos, col in _RAMP:
        parts.append(f'<stop offset="{pos * 100:.0f}%" stop-color="{col}"/>')
    parts.append("</linearGradient></defs>")
    parts.append(
        f'<rect x="{leg_x:.1f}" y="{leg_top:.1f}" width="{legend_w:.0f}" height="{leg_h:.1f}" '
        f'rx="4" fill="url(#{grad_id})" stroke="#D2D2D7" stroke-width="1"/>'
    )
    vmid = (vmin + vmax) / 2.0
    for frac, val in ((1.0, vmax), (0.5, vmid), (0.0, vmin)):
        ly = leg_top + (1.0 - frac) * leg_h
        parts.append(
            f'<line x1="{leg_x + legend_w:.1f}" y1="{ly:.1f}" x2="{leg_x + legend_w + 6:.1f}" '
            f'y2="{ly:.1f}" stroke="{SECONDARY}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{leg_x + legend_w + 11:.1f}" y="{ly + 4:.1f}" font-size="12" '
            f'font-family="{mono_family}" fill="{SECONDARY}">{_fmt(val)}</text>'
        )
    parts.append(
        f'<text x="{leg_x + legend_w / 2:.1f}" y="{leg_top - 12:.1f}" font-size="13" '
        f'fill="{INK}" text-anchor="middle">{xml_escape(legend_label)}</text>'
    )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_heatmap(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Activity by Day and Hour",
    subtitle: str = "Synthetic weekly usage pattern",
    width: int = 900,
    height: int = 400,
    mode: str = "self-contained",
    accessibility: str = "universal",
    x_label: str = "Hour of day",
    y_label: str = "",
    legend_label: str = "Activity",
    show_cell_labels: bool = True,
    square: bool = False,
    theme: str = "corporate",
    vmin: Optional[float] = None,
    vmax: Optional[float] = None,
) -> Path:
    """Render a hand-authored row x column heatmap and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``day`` (str), ``hour`` (int), ``activity`` (float).
        Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/heatmap.svg``.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    mode, accessibility, theme : str
        Forwarded to :func:`build_svg`.
    vmin, vmax : float, optional
        Forwarded to :func:`build_svg`; see its docstring.

    Returns
    -------
    Path
        Absolute path to the written SVG file.

    Examples
    --------
    >>> p = make_heatmap()
    >>> p.exists()
    True
    """
    svg = build_svg(
        data, title=title, subtitle=subtitle, width=width, height=height,
        mode=mode, accessibility=accessibility, x_label=x_label, y_label=y_label,
        legend_label=legend_label, show_cell_labels=show_cell_labels, square=square,
        theme=theme, vmin=vmin, vmax=vmax,
    )
    dest = Path(out) if out else svg_example_path(__file__, "heatmap")
    return write_svg(dest, svg, theme=theme)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Generate a row x column heatmap (hand-authored SVG).")
    p.add_argument("--out", default=None)
    p.add_argument("--title", default="Activity by Day and Hour")
    p.add_argument("--subtitle", default="Synthetic weekly usage pattern")
    p.add_argument("--width", type=int, default=900)
    p.add_argument("--height", type=int, default=400)
    p.add_argument("--mode", choices=("self-contained", "external", "static"), default="self-contained")
    p.add_argument(
        "--accessibility",
        choices=("universal", "high-contrast", "monochrome", "deuteranopia", "protanopia", "tritanopia"),
        default="universal",
    )
    p.add_argument(
        "--theme",
        choices=("corporate", "academic"),
        default="corporate",
        help="visual theme: corporate (default, Roboto) or academic (LaTeX-style Latin Modern)",
    )
    p.add_argument(
        "--vmin", type=float, default=None,
        help="explicit color-scale minimum (default: this call's own data min)",
    )
    p.add_argument(
        "--vmax", type=float, default=None,
        help="explicit color-scale maximum (default: this call's own data max)",
    )
    args = p.parse_args()
    make_heatmap(
        out=args.out, title=args.title, subtitle=args.subtitle,
        width=args.width, height=args.height, mode=args.mode, accessibility=args.accessibility,
        theme=args.theme, vmin=args.vmin, vmax=args.vmax,
    )
