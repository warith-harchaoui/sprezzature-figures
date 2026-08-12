#!/usr/bin/env python3
"""
make_population-pyramid — a house-styled population pyramid as hand-authored SVG.

Mirrors two categories' horizontal bars around a shared zero axis, one
row per age band, oldest at top: the classic demographic pyramid, one
side (typically male) drawn negative-left, the other (female)
positive-right, both labelled with their absolute share. The shape
itself tells the story -- a wide base means a young, growing population;
a bulge in the middle means an ageing one.

Previously rendered via Vega-Lite (negative/positive values on a shared
``x`` encoding with an absolute-value axis label expression, ``vl_convert``);
this module now paints each mirrored bar by hand -- no Vega, no
matplotlib. Every bar carries a native ``<title>`` tooltip with its
absolute share.

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
from _style import BG, GRIDLINE, INK, SECONDARY, corner_radius, load_palette  # noqa: E402
from _svg import svg_open, tooltip_bubble, xml_escape  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402


AGE_BANDS = ["75+", "60-74", "45-59", "30-44", "15-29", "0-14"]
SEXES = ["Male", "Female"]

DEMO_DATA: List[Dict[str, Any]] = [
    {"age": "0-14", "sex": "Male", "pct": -12}, {"age": "0-14", "sex": "Female", "pct": 11},
    {"age": "15-29", "sex": "Male", "pct": -15}, {"age": "15-29", "sex": "Female", "pct": 14},
    {"age": "30-44", "sex": "Male", "pct": -14}, {"age": "30-44", "sex": "Female", "pct": 14},
    {"age": "45-59", "sex": "Male", "pct": -12}, {"age": "45-59", "sex": "Female", "pct": 13},
    {"age": "60-74", "sex": "Male", "pct": -8}, {"age": "60-74", "sex": "Female", "pct": 9},
    {"age": "75+", "sex": "Male", "pct": -4}, {"age": "75+", "sex": "Female", "pct": 6},
]


def _sex_colors(accessibility: str = "universal", theme: str = "corporate") -> Dict[str, str]:
    palette = load_palette(accessibility, theme=theme)
    return {"Male": palette.get("Blue", "#007AFF"), "Female": palette.get("Orange", "#FF9500")}


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Population by Age and Sex",
    subtitle: str = "Share of total population (%), by age band",
    width: int = 620,
    height: int = 480,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full population pyramid SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``age`` (str), ``sex`` (str, Male/Female), ``pct``
        (numeric; negative for Male by convention, positive for Female).
        Defaults to :data:`DEMO_DATA`.
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
    seen_ages: List[str] = []
    for r in rows:
        if r["age"] not in seen_ages:
            seen_ages.append(r["age"])
    ages = [a for a in AGE_BANDS if a in seen_ages] + [a for a in seen_ages if a not in AGE_BANDS]
    colors = _sex_colors(accessibility, theme)
    lookup: Dict[tuple, float] = {(r["age"], r["sex"]): float(r["pct"]) for r in rows}
    max_abs = max(abs(v) for v in lookup.values()) if lookup else 1.0
    total_abs = sum(abs(v) for v in lookup.values()) or 1.0

    plot_x, plot_y = width / 2.0, 150.0
    right_margin, bottom_reserved = 60.0, 60.0
    left_margin = 60.0
    half_w = min(plot_x - left_margin, width - right_margin - plot_x)
    plot_h = height - plot_y - bottom_reserved
    n = len(ages)
    row_h = plot_h / n if n else plot_h
    bar_h = row_h * 0.6

    def bar_len(v: float) -> float:
        # Leave room for the value label past the bar's far end.
        return abs(v) / max_abs * half_w * 0.86

    parts: List[str] = []
    parts.append(svg_open(width, height, "pp-title", "pp-desc", font_family=chrome_stack_for_theme(theme)))
    parts.append(f'<title id="pp-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="pp-desc">Population pyramid across {n} age bands. Hover or focus a '
        f'bar for its exact share.</desc>'
    )
    parts.append(
        "<style>"
        ".pyr{transition:filter .15s ease;}"
        ".pyr:hover,.pyr:focus{filter:brightness(1.08);outline:none;}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        ".hit:hover+.tip,.hit:focus+.tip{opacity:1}"
        "@media (prefers-reduced-motion: reduce){.pyr{transition:none;}"
        ".tip{transition:none}}"
        "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="40" y="46" font-size="22" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(f'<text x="40" y="70" font-size="14" fill="{SECONDARY}">{xml_escape(subtitle)}</text>')

    # ---- legend ----
    lx, ly = 40.0, 100.0
    cursor = lx
    for sex in SEXES:
        parts.append(f'<rect x="{cursor:.1f}" y="{ly - 12:.1f}" width="14" height="14" rx="3" fill="{colors[sex]}"/>')
        parts.append(f'<text x="{cursor + 20:.1f}" y="{ly:.1f}" font-size="12" fill="{INK}">{xml_escape(sex)}</text>')
        cursor += 20 + 7.0 * len(sex) + 22

    # ---- center axis + age labels ----
    axis_y = plot_y + plot_h
    parts.append(
        f'<line x1="{plot_x:.1f}" y1="{plot_y:.1f}" x2="{plot_x:.1f}" y2="{axis_y:.1f}" '
        f'stroke="{INK}" stroke-width="1.2"/>'
    )
    for i, age in enumerate(ages):
        cy = plot_y + i * row_h + row_h / 2 + 4
        # A background-colour backplate masks the axis line behind the
        # label -- text glyphs alone don't fully cover their own bounding
        # box (the gap around a hyphen, inter-character spacing), so the
        # line was showing through "60-74"-style labels (found via the
        # Ralph Eyeball Loop).
        parts.append(
            f'<rect x="{plot_x - 26:.1f}" y="{cy - 12:.1f}" width="52" height="16" fill="{BG}"/>'
        )
        parts.append(f'<text x="{plot_x:.1f}" y="{cy:.1f}" font-size="12" fill="{INK}" text-anchor="middle">{xml_escape(age)}</text>')

    # ---- bars ----
    for i, age in enumerate(ages):
        cy = plot_y + i * row_h + row_h / 2
        y0 = cy - bar_h / 2
        for sex, sign in (("Male", -1), ("Female", 1)):
            v = lookup.get((age, sex), 0.0)
            length = bar_len(v)
            if length <= 0:
                continue
            gap = 22.0
            if sign < 0:
                x0 = plot_x - gap - length
            else:
                x0 = plot_x + gap
            r = corner_radius(length, bar_h, "bar")
            tip = f"{sex}, {age}: {abs(v):.0f}%"
            share = abs(v) / total_abs * 100.0
            parts.append(
                f'<rect class="pyr hit" tabindex="0" x="{x0:.1f}" y="{y0:.1f}" width="{length:.1f}" '
                f'height="{bar_h:.1f}" rx="{r:.1f}" fill="{colors[sex]}" '
                f'role="img" aria-label="{xml_escape(tip)}"/>'
            )
            parts.append(
                tooltip_bubble(
                    x0 + (length if sign < 0 else 0.0), y0 - 12,
                    [f"{sex}, {age}", f"{abs(v):.0f}% of population", f"{share:.1f}% of pyramid total"],
                    anchor="middle", canvas_w=width, canvas_h=height,
                    ink=INK, secondary=SECONDARY, border=GRIDLINE,
                )
            )
            label_x = x0 - 6 if sign < 0 else x0 + length + 6
            anchor = "end" if sign < 0 else "start"
            parts.append(
                f'<text x="{label_x:.1f}" y="{cy + 4:.1f}" font-size="10" font-family="{mono_family}" '
                f'fill="{SECONDARY}" text-anchor="{anchor}">{abs(v):.0f}%</text>'
            )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_population_pyramid(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Population by Age and Sex",
    subtitle: str = "Share of total population (%), by age band",
    width: int = 620,
    height: int = 480,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render a hand-authored population pyramid and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``age`` (str), ``sex`` (str), ``pct`` (float).
        Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to
        ``assets/svg-examples/population-pyramid.svg``.
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
    >>> p = make_population_pyramid()
    >>> p.exists()
    True
    """
    svg = build_svg(data, title=title, subtitle=subtitle, width=width, height=height,
                     mode=mode, accessibility=accessibility, theme=theme)
    dest = Path(out) if out else svg_example_path(__file__, "population-pyramid")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "population-pyramid", build_svg, description="Generate a population pyramid.")


if __name__ == "__main__":
    main()
