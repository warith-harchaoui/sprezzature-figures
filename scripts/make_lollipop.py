#!/usr/bin/env python3
"""
make_lollipop — a house-styled lollipop chart as hand-authored SVG.

A lighter-weight cousin of the bar chart: a thin stem from zero to the
value, capped with a dot, one per category, sorted largest to smallest.
The thin stem draws less ink than a filled bar while keeping the same
"length encodes value" reading, so it suits a longer category list or a
report where restraint matters more than a bar's visual weight.

Previously rendered via Vega-Lite (a layered ``rule`` + ``point`` mark,
``vl_convert``). This module now paints both by hand: no Vega, no
matplotlib. Every lollipop carries a native ``<title>`` tooltip.

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
from _scale import nice_ticks  # noqa: E402
from _svg import svg_open, tooltip_bubble, xml_escape  # noqa: E402
from _style import BG, GRIDLINE, INK, SECONDARY  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402

COLOR_STEM = "#C7C7CC"
COLOR_DOT = "#007AFF"

DEMO_DATA: List[Dict[str, Any]] = [
    {"c": "alpha", "v": 28}, {"c": "beta", "v": 55}, {"c": "gamma", "v": 43},
    {"c": "delta", "v": 91}, {"c": "epsilon", "v": 62},
]

# Chrome text (Studio detects "en"/"fr" from the imported CSV's column
# names; the CLI/library/API/MCP default to "en"). Title/subtitle are
# already caller-supplied strings (Studio always passes an explicit
# `title=`), so only this generator's own fixed labels need translation:
# the x-axis title, the desc template, the "leads at" clause, and the
# tooltip's "of total" suffix. Category names and values are never
# translated -- they come straight from the caller's data.
_STRINGS: Dict[str, Dict[str, str]] = {
    "en": {
        "x_axis": "Score",
        "desc": "Lollipop chart of {n} categories, tallest {max_v:.0f}.",
        "leads_at": " {name} leads at {value:.0f}.",
        "of_total": "of total",
    },
    "fr": {
        "x_axis": "Score",
        "desc": "Graphique en sucette de {n} catégories, la plus haute à {max_v:.0f}.",
        "leads_at": " {name} est en tête à {value:.0f}.",
        "of_total": "du total",
    },
}


def _strings(language: str) -> Dict[str, str]:
    """Chrome-text dict for `language`, falling back to English."""
    return _STRINGS.get(language, _STRINGS["en"])


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Score by Group",
    subtitle: str = "Categories sorted largest to smallest",
    width: int = 620,
    height: int = 420,
    mode: str = "self-contained",
    accessibility: str = "universal",
    language: str = "en",
    theme: str = "corporate",
) -> str:
    """Assemble the full lollipop chart SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``c`` (str) and ``v`` (numeric). Defaults to
        :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    mode : str, optional
        Forwarded to :func:`_interactive.fullscreen_control`.
    accessibility : str, optional
        Accepted for CLI parity but a documented no-op: a single house-
        blue dot/stem, no categorical hues to re-level.
    language : str, optional
        Chrome-text language, ``"en"`` or ``"fr"`` (see :data:`_STRINGS`).
        Only this generator's own fixed labels switch; category names and
        values always render exactly as given. Defaults to ``"en"``.
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
    strings = _strings(language)
    rows = sorted(data if data else DEMO_DATA, key=lambda r: -float(r["v"]))
    max_v = max(float(r["v"]) for r in rows) if rows else 1.0
    total = sum(float(r["v"]) for r in rows) or 1.0

    plot_x, plot_y = 110.0, 118.0
    right_margin, bottom_reserved = 40.0, 60.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_reserved
    n = len(rows)
    row_h = plot_h / n if n else plot_h

    # Nice, round tick values (shared _scale.nice_ticks, the house
    # convention) instead of raw max_v/5 fractions, which produced
    # unreadable labels like 0/18/36/55/73/91. The axis domain is the nice
    # ceiling itself (e.g. 100 for a max of 91), so the top gridline lands
    # on the plot's right edge and the ad hoc "* 0.92" headroom fudge factor
    # is no longer needed — the nice ceiling already provides it.
    x_tick_vals = nice_ticks(max_v, 5)
    x_domain = x_tick_vals[-1] or 1.0

    def x_for(v: float) -> float:
        return plot_x + v / x_domain * plot_w

    parts: List[str] = []
    parts.append(svg_open(width, height, "lp-title", "lp-desc", font_family=chrome_stack_for_theme(theme)))
    parts.append(f'<title id="lp-title">{xml_escape(title)}</title>')
    top = rows[0] if rows else None
    peak_desc = strings["leads_at"].format(name=top["c"], value=top["v"]) if top else ""
    parts.append(
        f'<desc id="lp-desc">{strings["desc"].format(n=n, max_v=max_v)}'
        f'{peak_desc}</desc>'
    )
    parts.append(
        "<style>"
        ".pop{transition:r .12s ease;}"
        ".pop:hover,.pop:focus{r:8;outline:none;}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        ".hit:hover+.tip,.hit:focus+.tip{opacity:1}"
        "@media (prefers-reduced-motion: reduce){.pop{transition:none;}"
        ".tip{transition:none}}"
        "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="40" y="46" font-size="22" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(f'<text x="40" y="70" font-size="14" fill="{SECONDARY}">{xml_escape(subtitle)}</text>')

    # ---- x-axis gridlines ----
    for val in x_tick_vals:
        tx = x_for(val)
        parts.append(
            f'<line x1="{tx:.1f}" y1="{plot_y:.1f}" x2="{tx:.1f}" y2="{plot_y + plot_h:.1f}" '
            f'stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{tx:.1f}" y="{plot_y + plot_h + 20:.1f}" font-size="11" font-family="{mono_family}" '
            f'fill="{SECONDARY}" text-anchor="middle">{val:.0f}</text>'
        )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{plot_y + plot_h + 42:.1f}" font-size="13" '
        f'fill="{INK}" text-anchor="middle">{strings["x_axis"]}</text>'
    )

    # ---- lollipops ----
    for i, row in enumerate(rows):
        v = float(row["v"])
        cy = plot_y + i * row_h + row_h / 2
        x1 = x_for(v)
        share = v / total * 100.0
        tip = f"{row['c']}: {v:.0f} ({share:.1f}% {strings['of_total']})"
        parts.append(f'<line x1="{plot_x:.1f}" y1="{cy:.1f}" x2="{x1:.1f}" y2="{cy:.1f}" stroke="{COLOR_STEM}" stroke-width="2"/>')
        parts.append(
            f'<circle class="pop hit" tabindex="0" cx="{x1:.1f}" cy="{cy:.1f}" r="7" fill="{COLOR_DOT}" '
            f'stroke="{BG}" stroke-width="1.5" role="img" aria-label="{xml_escape(tip)}"/>'
        )
        parts.append(
            tooltip_bubble(
                x1, cy - 14,
                [str(row["c"]), f"{v:.0f} pts", f"{share:.1f}% {strings['of_total']}"],
                anchor="middle", canvas_w=width, canvas_h=height,
                ink=INK, secondary=SECONDARY, border=GRIDLINE,
            )
        )
        parts.append(
            f'<text x="{plot_x - 12:.1f}" y="{cy + 4:.1f}" font-size="13" fill="{INK}" '
            f'text-anchor="end">{xml_escape(str(row["c"]))}</text>'
        )

    axis_y = plot_y + plot_h
    parts.append(
        f'<line x1="{plot_x:.1f}" y1="{axis_y:.1f}" x2="{plot_x + plot_w:.1f}" y2="{axis_y:.1f}" '
        f'stroke="{INK}" stroke-width="1.2"/>'
    )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_lollipop(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Score by Group",
    subtitle: str = "Categories sorted largest to smallest",
    width: int = 620,
    height: int = 420,
    mode: str = "self-contained",
    accessibility: str = "universal",
    language: str = "en",
    theme: str = "corporate",
) -> Path:
    """Render a hand-authored lollipop chart and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``c`` (str) and ``v`` (float). Defaults to
        DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/lollipop.svg``.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    mode, accessibility, language : str
        Forwarded to :func:`build_svg`.
    theme : str, optional
        Visual theme. Forwarded to :func:`build_svg`.

    Returns
    -------
    Path
        Absolute path to the written SVG file.

    Examples
    --------
    >>> p = make_lollipop()
    >>> p.exists()
    True
    """
    svg = build_svg(data, title=title, subtitle=subtitle, width=width, height=height,
                     mode=mode, accessibility=accessibility, language=language, theme=theme)
    dest = Path(out) if out else svg_example_path(__file__, "lollipop")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "lollipop", build_svg, description="Generate a lollipop chart.")


if __name__ == "__main__":
    main()
