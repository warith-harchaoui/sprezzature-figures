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

import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _style import BG, GRIDLINE, INK, SECONDARY, corner_radius, cycle_hues  # noqa: E402
from _svg import svg_open, tooltip_bubble, xml_escape  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402


def _nice_step(span: float, target_ticks: int = 6) -> float:
    """Pick a 1/2/5-times-a-power-of-ten step so ``span / step`` ~= `target_ticks`.

    The Gantt's x-axis is zero-anchored but its extent is the data's own
    ``max_end`` (e.g. 33 days), not a round ceiling, so ``_scale.nice_ticks``
    (which rounds the *ceiling* up, extending the axis past the data) isn't a
    drop-in fit -- the axis here must stay pinned to `max_end` so the last
    task's bar still reaches the plot's right edge. Rounding just the *step*
    (Heckbert 1990) instead turns a naive ``max_end / 6`` divide -- which used
    to print tick labels like ``6``/``11``/``16``/``22``/``28``/``33`` -- into
    round, scannable gridlines like ``0``/``5``/``10``/.../``30``.
    """
    if span <= 0:
        return 1.0
    raw_step = span / target_ticks
    exponent = math.floor(math.log10(raw_step))
    fraction = raw_step / (10.0**exponent)
    nice_fraction = 1.0 if fraction < 1.5 else 2.0 if fraction < 3 else 5.0 if fraction < 7 else 10.0
    return nice_fraction * (10.0**exponent)


TEAMS = ["Research", "Design", "Eng", "QA", "Ops"]

DEMO_DATA: List[Dict[str, Any]] = [
    {"task": "Discovery", "start": 0, "end": 5, "team": "Research"},
    {"task": "Design", "start": 4, "end": 11, "team": "Design"},
    {"task": "Build API", "start": 10, "end": 22, "team": "Eng"},
    {"task": "Build UI", "start": 14, "end": 26, "team": "Eng"},
    {"task": "QA", "start": 24, "end": 31, "team": "QA"},
    {"task": "Launch", "start": 30, "end": 33, "team": "Ops"},
]


def _team_colors(
    teams: List[str], accessibility: str = "universal", theme: str = "corporate"
) -> Dict[str, str]:
    """Assign each team a hue, one per legend/bar colour.

    ``Teal`` stands in for the more common ``Green`` here: at up to 5 teams
    the default cycle order also draws ``Orange``, and ``Orange``/``Green``
    are near-identical in grayscale (~1/255 luminance apart, caught by a
    grayscale render check) -- ``Teal`` keeps the same 5-hue cycle length
    but reads distinctly from ``Orange`` once colour is removed.

    Parameters
    ----------
    teams : list of str
        Team names, in the order they should receive hues.
    accessibility : str, optional
        Forwarded to :func:`_style.cycle_hues`. Defaults to ``"universal"``.
    theme : str, optional
        Forwarded to :func:`_style.cycle_hues`. Defaults to ``"corporate"``.

    Returns
    -------
    dict of str to str
        ``{team: hex_color}`` for every entry in `teams`.
    """
    return cycle_hues(teams, accessibility, hues=['Blue', 'Purple', 'Orange', 'Teal', 'Red'], theme=theme)


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Project Schedule",
    subtitle: str = "One bar per task, spanning its start and end day",
    width: int = 745,
    height: int = 420,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
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
    theme : str, optional
        Visual theme: ``"corporate"`` (default, Roboto -- byte-identical to
        the pre-theme render) or ``"academic"`` (LaTeX-style Latin Modern).
        See :func:`sprezzature_figures.fonts.chrome_stack_for_theme`.

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    mono_family = mono_stack_for_theme(theme)
    rows = data if data else DEMO_DATA
    seen_teams: List[str] = []
    for r in rows:
        if r["team"] not in seen_teams:
            seen_teams.append(r["team"])
    teams = [t for t in TEAMS if t in seen_teams] + [t for t in seen_teams if t not in TEAMS]
    colors = _team_colors(teams, accessibility, theme=theme)
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
    parts.append(svg_open(width, height, "gantt-title", "gantt-desc", font_family=chrome_stack_for_theme(theme)))
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
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        ".hit:hover+.tip,.hit:focus+.tip{opacity:1}"
        "@media (prefers-reduced-motion:reduce){.tip{transition:none}}"
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

    # ---- x-axis gridlines (round "nice" steps, not a naive 6-way split) ----
    step = _nice_step(max_end, 6)
    val = 0.0
    while val <= max_end + 1e-9:
        tx = x_for(val)
        parts.append(
            f'<line x1="{tx:.1f}" y1="{plot_y:.1f}" x2="{tx:.1f}" y2="{plot_y + plot_h:.1f}" '
            f'stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{tx:.1f}" y="{plot_y + plot_h + 20:.1f}" font-size="11" font-family="{mono_family}" '
            f'fill="{SECONDARY}" text-anchor="middle">{val:.0f}</text>'
        )
        val += step
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
            f'<rect class="task hit" tabindex="0" x="{x0:.1f}" y="{y:.1f}" width="{w:.1f}" '
            f'height="{bar_h:.1f}" rx="{r_corner:.1f}" fill="{color}">'
            f'<title>{xml_escape(tip)}</title></rect>'
        )
        parts.append(
            tooltip_bubble(
                x0 + w / 2, y - 12,
                [str(r["task"]), team, f"day {start:.0f}-{end:.0f} ({end - start:.0f} days)"],
                anchor="middle", canvas_w=width, canvas_h=height,
                ink=INK, secondary=SECONDARY, border=GRIDLINE,
            )
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
    theme: str = "corporate",
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
    theme : str, optional
        Visual theme. Forwarded to :func:`build_svg`.

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
                     mode=mode, accessibility=accessibility, theme=theme)
    dest = Path(out) if out else svg_example_path(__file__, "gantt")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "gantt", build_svg, description="Generate a Gantt chart.")


if __name__ == "__main__":
    main()
