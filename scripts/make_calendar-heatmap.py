#!/usr/bin/env python3
"""
make_calendar-heatmap — a house-styled GitHub-style calendar heatmap as hand-authored SVG.

Encodes a daily count as cell colour on a week-by-day grid: columns are
weeks, rows are the seven days, and each cell's fill is a single
pale-to-navy blue ramp -- a monotone lightness sweep so the pattern
survives greyscale and every colour-vision deficiency without a second
encoding. Typical uses: commit activity, daily active users, habit
tracking -- any daily count viewed over months at a glance.

Previously rendered via Vega-Lite (``vl_convert``); this module now
builds the ``<svg>`` grid by hand -- no Vega, no matplotlib. Grid cells
never round (Sprezzature Corner Policy: grids stay square) and every
cell carries a native ``<title>`` tooltip with its exact count.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _svg import svg_open, xml_escape  # noqa: E402
from _style import BG, INK, SECONDARY  # noqa: E402


DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Sequential blue ramp — pale sky -> system blue -> deep navy, mono-hue so
# magnitude reads by lightness alone (same ramp make_heatmap.py uses).
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
    rng = random.Random(5)
    rows: List[Dict[str, Any]] = []
    for week in range(18):
        for dow, day in enumerate(DAYS):
            is_weekend = dow >= 5
            base = 2 if is_weekend else 6
            spike = 5 if rng.random() < 0.12 else 0
            rows.append({"week": week, "day": day, "count": max(0, round(rng.gauss(base, 2.2) + spike))})
    return rows


DEMO_DATA: List[Dict[str, Any]] = _make_demo_data()


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Daily Activity",
    subtitle: str = "Events per day over 18 weeks",
    width: int = 620,
    height: int = 300,
    mode: str = "self-contained",
    accessibility: str = "universal",
) -> str:
    """Assemble the full calendar heatmap SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``week`` (int), ``day`` (str, Mon-Sun), ``count``
        (numeric). Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    mode : str, optional
        Forwarded to :func:`_interactive.fullscreen_control`.
    accessibility : str, optional
        Accepted for CLI parity but a documented no-op: the ramp is a
        single mono-hue blue scale, already colour-vision-deficiency-safe
        by construction (magnitude reads by lightness alone).

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    _ = accessibility
    rows = data if data else DEMO_DATA
    weeks = sorted({int(r["week"]) for r in rows})
    lookup: Dict[Tuple[int, str], float] = {(int(r["week"]), r["day"]): float(r["count"]) for r in rows}
    max_val = max(lookup.values()) if lookup else 1.0

    plot_x, plot_y = 76.0, 96.0
    right_margin, bottom_reserved = 24.0, 60.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_reserved
    n_weeks = len(weeks)
    cell_w = plot_w / n_weeks if n_weeks else plot_w
    cell_h = plot_h / len(DAYS)
    gap = min(cell_w, cell_h) * 0.14

    parts: List[str] = []
    parts.append(svg_open(width, height, "cal-title", "cal-desc"))
    parts.append(f'<title id="cal-title">{xml_escape(title)}</title>')
    total = sum(lookup.values())
    parts.append(
        f'<desc id="cal-desc">Calendar heatmap over {n_weeks} weeks, {total:,.0f} events total, '
        f'busiest day {max_val:.0f}. Hover or focus a cell for its exact count.</desc>'
    )
    parts.append(
        "<style>"
        ".cell{transition:stroke-width .1s ease;}"
        ".cell:hover,.cell:focus{stroke:#1D1D1F;stroke-width:1.5;outline:none;}"
        "@media (prefers-reduced-motion: reduce){.cell{transition:none;}}"
        "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="40" y="42" font-size="20" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(f'<text x="40" y="64" font-size="13" fill="{SECONDARY}">{xml_escape(subtitle)}</text>')

    # ---- day-of-week row labels (Mon/Wed/Fri only, GitHub convention) ----
    for di, day in enumerate(DAYS):
        if day not in ("Mon", "Wed", "Fri"):
            continue
        ty = plot_y + di * cell_h + cell_h / 2 + 4
        parts.append(
            f'<text x="{plot_x - 10:.1f}" y="{ty:.1f}" font-size="11" fill="{SECONDARY}" '
            f'text-anchor="end">{xml_escape(day)}</text>'
        )

    # ---- cells (grid marks: never rounded, per Sprezzature Corner Policy) ----
    for wi, week in enumerate(weeks):
        for di, day in enumerate(DAYS):
            count = lookup.get((week, day), 0.0)
            t = count / max_val if max_val else 0.0
            x = plot_x + wi * cell_w + gap / 2
            y = plot_y + di * cell_h + gap / 2
            w = cell_w - gap
            h = cell_h - gap
            tip = f"Week {week + 1}, {day}: {count:.0f} events"
            parts.append(
                f'<rect class="cell" tabindex="0" x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
                f'fill="{_ramp_hex(t)}" stroke="{BG}" stroke-width="1">'
                f'<title>{xml_escape(tip)}</title></rect>'
            )

    # ---- legend: Less -> More ramp swatches ----
    ly = height - 28.0
    parts.append(f'<text x="{plot_x:.1f}" y="{ly:.1f}" font-size="11" fill="{SECONDARY}">Less</text>')
    swatch_x = plot_x + 34.0
    for i in range(5):
        t = i / 4.0
        parts.append(f'<rect x="{swatch_x + i * 16:.1f}" y="{ly - 11:.1f}" width="12" height="12" fill="{_ramp_hex(t)}"/>')
    parts.append(f'<text x="{swatch_x + 5 * 16 + 8:.1f}" y="{ly:.1f}" font-size="11" fill="{SECONDARY}">More</text>')

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_calendar_heatmap(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Daily Activity",
    subtitle: str = "Events per day over 18 weeks",
    width: int = 620,
    height: int = 300,
    mode: str = "self-contained",
    accessibility: str = "universal",
) -> Path:
    """Render a hand-authored calendar heatmap and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``week`` (int), ``day`` (str), ``count`` (float).
        Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to
        ``assets/svg-examples/calendar-heatmap.svg``.
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
    >>> p = make_calendar_heatmap()
    >>> p.exists()
    True
    """
    svg = build_svg(data, title=title, subtitle=subtitle, width=width, height=height,
                     mode=mode, accessibility=accessibility)
    dest = Path(out) if out else svg_example_path(__file__, "calendar-heatmap")
    return write_svg(dest, svg)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "calendar-heatmap", build_svg, description="Generate a GitHub-style calendar heatmap.")


if __name__ == "__main__":
    main()
