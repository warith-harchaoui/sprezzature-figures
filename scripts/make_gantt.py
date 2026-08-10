#!/usr/bin/env python3
"""
make_gantt — a house-styled Gantt chart as hand-authored SVG.

Encodes a project schedule as one horizontal bar per task, spanning its
start and end day, coloured by owning team. Top-to-bottom order follows
the caller's data (typically chronological or dependency order), so the
staircase shape of overlapping bars reads as the project's critical path
at a glance. The default chart for a project plan or roadmap.

Previously rendered via Vega-Lite (an ``x``/``x2`` bar mark, ``vl_convert``);
this module now paints each bar by hand -- no Vega, no matplotlib. Every
bar carries a native ``<title>`` tooltip with its exact span and duration.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _style import BG, FONT_MONO, GRIDLINE, INK, SECONDARY, corner_radius, cycle_hues, load_palette  # noqa: E402
from _svg import svg_open, xml_escape  # noqa: E402


TEAMS = ["Research", "Design", "Eng", "QA", "Ops"]

DEMO_DATA: List[Dict[str, Any]] = [
    {"task": "Discovery", "start": 0, "end": 5, "team": "Research"},
    {"task": "Design", "start": 4, "end": 11, "team": "Design"},
    {"task": "Build API", "start": 10, "end": 22, "team": "Eng"},
    {"task": "Build UI", "start": 14, "end": 26, "team": "Eng"},
    {"task": "QA", "start": 24, "end": 31, "team": "QA"},
    {"task": "Launch", "start": 30, "end": 33, "team": "Ops"},
]


def _team_colors(teams: List[str], accessibility: str = "universal") -> Dict[str, str]:
    return cycle_hues(teams, accessibility, hues=['Blue', 'Purple', 'Orange', 'Green', 'Red'])


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Project Schedule",
    subtitle: str = "One bar per task, spanning its start and end day",
    width: int = 745,
    height: int = 420,
    mode: str = "self-contained",
    accessibility: str = "universal",
) -> str:
    """Assemble the full Gantt chart SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``task`` (str), ``start``, ``end`` (numeric day),
        ``team`` (str). Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    mode, accessibility : str, optional
        Forwarded to :func:`_interactive.fullscreen_control` /
        :func:`_style.load_palette`.

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    rows = data if data else DEMO_DATA
    seen_teams: List[str] = []
    for r in rows:
        if r["team"] not in seen_teams:
            seen_teams.append(r["team"])
    teams = [t for t in TEAMS if t in seen_teams] + [t for t in seen_teams if t not in TEAMS]
    colors = _team_colors(teams, accessibility)
    max_end = max(float(r["end"]) for r in rows) if rows else 1.0

    plot_x, plot_y = 130.0, 150.0
    right_margin, bottom_reserved = 30.0, 60.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_reserved
    n = len(rows)
    row_h = plot_h / n if n else plot_h
    bar_h = row_h * 0.55

    def x_for(v: float) -> float:
        return plot_x + v / max_end * plot_w

    parts: List[str] = []
    parts.append(svg_open(width, height, "gantt-title", "gantt-desc"))
    parts.append(f'<title id="gantt-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="gantt-desc">Gantt chart of {n} tasks spanning {max_end:.0f} days. '
        f'Hover or focus a bar for its exact span.</desc>'
    )
    parts.append(
        "<style>"
        ".task{transition:filter .15s ease;}"
        ".task:hover,.task:focus{filter:brightness(1.08);outline:none;}"
        "@media (prefers-reduced-motion: reduce){.task{transition:none;}}"
        "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="40" y="46" font-size="24" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(f'<text x="40" y="70" font-size="14" fill="{SECONDARY}">{xml_escape(subtitle)}</text>')

    # ---- legend ----
    lx, ly = 40.0, 104.0
    cursor = lx
    for t in teams:
        parts.append(f'<rect x="{cursor:.1f}" y="{ly - 12:.1f}" width="14" height="14" rx="3" fill="{colors[t]}"/>')
        parts.append(f'<text x="{cursor + 20:.1f}" y="{ly:.1f}" font-size="12" fill="{INK}">{xml_escape(t)}</text>')
        cursor += 20 + 7.0 * len(t) + 22

    # ---- x-axis gridlines ----
    x_ticks = 6
    for i in range(x_ticks + 1):
        val = max_end * i / x_ticks
        tx = x_for(val)
        parts.append(
            f'<line x1="{tx:.1f}" y1="{plot_y:.1f}" x2="{tx:.1f}" y2="{plot_y + plot_h:.1f}" '
            f'stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{tx:.1f}" y="{plot_y + plot_h + 20:.1f}" font-size="11" font-family="{FONT_MONO}" '
            f'fill="{SECONDARY}" text-anchor="middle">{val:.0f}</text>'
        )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{plot_y + plot_h + 42:.1f}" font-size="13" '
        f'fill="{INK}" text-anchor="middle">Day</text>'
    )

    # ---- task bars ----
    for i, r in enumerate(rows):
        start, end = float(r["start"]), float(r["end"])
        y = plot_y + i * row_h + (row_h - bar_h) / 2
        x0, x1 = x_for(start), x_for(end)
        w = max(2.0, x1 - x0)
        team = str(r["team"])
        color = colors.get(team, "#8E8E93")
        r_corner = corner_radius(w, bar_h, "bar")
        tip = f"{r['task']} ({team}): day {start:.0f}-{end:.0f}, {end - start:.0f} days"
        parts.append(
            f'<rect class="task" tabindex="0" x="{x0:.1f}" y="{y:.1f}" width="{w:.1f}" '
            f'height="{bar_h:.1f}" rx="{r_corner:.1f}" fill="{color}">'
            f'<title>{xml_escape(tip)}</title></rect>'
        )
        ty = plot_y + i * row_h + row_h / 2 + 4
        parts.append(
            f'<text x="{plot_x - 12:.1f}" y="{ty:.1f}" font-size="12" fill="{INK}" '
            f'text-anchor="end">{xml_escape(str(r["task"]))}</text>'
        )

    axis_y = plot_y + plot_h
    parts.append(
        f'<line x1="{plot_x:.1f}" y1="{axis_y:.1f}" x2="{plot_x + plot_w:.1f}" y2="{axis_y:.1f}" '
        f'stroke="{INK}" stroke-width="1.2"/>'
    )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_gantt(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Project Schedule",
    subtitle: str = "One bar per task, spanning its start and end day",
    width: int = 745,
    height: int = 420,
    mode: str = "self-contained",
    accessibility: str = "universal",
) -> Path:
    """Render a hand-authored Gantt chart and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``task`` (str), ``start``, ``end`` (float),
        ``team`` (str). Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/gantt.svg``.
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
    >>> p = make_gantt()
    >>> p.exists()
    True
    """
    svg = build_svg(data, title=title, subtitle=subtitle, width=width, height=height,
                     mode=mode, accessibility=accessibility)
    dest = Path(out) if out else svg_example_path(__file__, "gantt")
    return write_svg(dest, svg)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "gantt", build_svg, description="Generate a Gantt chart.")


if __name__ == "__main__":
    main()
