#!/usr/bin/env python3
"""
make_bar — a house-styled grouped bar chart as a hand-authored SVG.

The default chart type for comparing a numeric value across a handful of
categories. Typical uses: revenue by region, headcount by department,
survey scores by cohort.

Previously rendered via Vega-Lite (``vl_convert``); this module now builds
the ``<svg>`` markup by hand -- no Vega, no matplotlib -- so every bar
carries a native ``<title>`` tooltip and rounds only its free (top) end
per the Sprezzature Corner Policy.

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
from _style import BG, GRIDLINE, INK, SECONDARY, corner_radius, cycle_hues, load_palette  # noqa: E402
from _svg import bar_path, fmt_number, svg_open, xml_escape  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402


CATEGORIES = ["North", "South", "East", "West"]

DEMO_DATA: List[Dict[str, Any]] = [
    {"region": "North", "value": 42},
    {"region": "South", "value": 28},
    {"region": "East", "value": 19},
    {"region": "West", "value": 11},
]

# Chrome text (title/subtitle/axis titles/desc/tooltip templates) in the two
# languages Studio can ask for (studio/i18n.py detects the language from the
# imported CSV's column names; the CLI/library/API/MCP always call with the
# "en" default). Category names and numeric labels are never translated here
# -- they render exactly as the caller's data/columns give them.
_STRINGS: Dict[str, Dict[str, str]] = {
    "en": {
        "title": "Revenue by Region",
        "subtitle": "Quarterly figures",
        "axis_value": "Value",
        "axis_category": "Region",
        "desc_template": "Bar chart of {n} categories, tallest {max_val:.0f}.",
        "peak_template": " {region} leads at {value:.0f}, {pct:.0f}% of the total.",
        "tooltip_template": "{region}: {value:.0f} ({share:.1f}% of total)",
    },
    "fr": {
        "title": "Chiffre d'affaires par région",
        "subtitle": "Chiffres trimestriels",
        "axis_value": "Valeur",
        "axis_category": "Région",
        "desc_template": "Graphique à barres de {n} catégories, maximum {max_val:.0f}.",
        "peak_template": " {region} est en tête avec {value:.0f}, {pct:.0f} % du total.",
        "tooltip_template": "{region} : {value:.0f} ({share:.1f} % du total)",
    },
}


def _strings(language: str) -> Dict[str, str]:
    """Chrome-text dict for `language`, falling back to English."""
    return _STRINGS.get(language, _STRINGS["en"])


def _category_colors(accessibility: str = "universal", theme: str = "corporate") -> Dict[str, str]:
    return cycle_hues(CATEGORIES, accessibility, theme=theme)


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    width: int = 745,
    height: int = 505,
    mode: str = "self-contained",
    accessibility: str = "universal",
    language: str = "en",
    x_label: Optional[str] = None,
    y_label: Optional[str] = None,
    theme: str = "corporate",
) -> str:
    """Assemble the full grouped bar chart SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``region`` (str) and ``value`` (numeric). Defaults
        to :data:`DEMO_DATA`.
    title, subtitle : str or None
        Chart text. ``None`` (the default) falls back to `language`'s
        chrome default (see :data:`_STRINGS`); an explicit string always
        wins regardless of `language`.
    width, height : int
        Canvas size in pixels.
    mode, accessibility : str, optional
        Forwarded to :func:`_interactive.fullscreen_control` /
        :func:`_style.load_palette`.
    language : str, optional
        Chrome-text language, ``"en"`` or ``"fr"``. Only title/subtitle
        defaults, axis titles, and the desc/tooltip wording switch; category
        names and numeric labels always render as given in `data`. Defaults
        to ``"en"``.
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
    strings = _strings(language)
    title = strings["title"] if title is None else title
    subtitle = strings["subtitle"] if subtitle is None else subtitle
    y_label = strings["axis_value"] if y_label is None else y_label
    x_label = strings["axis_category"] if x_label is None else x_label
    rows = data if data else DEMO_DATA
    colors = _category_colors(accessibility, theme)
    ordered = sorted(rows, key=lambda r: -float(r["value"]))
    total = sum(float(r["value"]) for r in rows) or 1.0
    max_val = max(float(r["value"]) for r in rows) if rows else 1.0

    y_step = max_val / 4.0
    y_ticks = [i * y_step for i in range(5)]
    y_domain = y_ticks[-1] or 1.0

    plot_y = 118.0
    # 64px was sized for short (2-3 digit) tick numbers; on 6-digit values
    # (e.g. "915000") the widest tick's right-anchored text overran that
    # margin and sat on top of the rotated axis title. Widen it to the
    # actual widest tick (mono font, flat per-char estimate) plus room for
    # the rotated title, instead of a fixed constant.
    max_tick_chars = max((len(fmt_number(t)) for t in y_ticks), default=1)
    tick_label_w = max_tick_chars * 12 * 0.62
    plot_x = max(64.0, 10 + tick_label_w + 24)
    right_margin, bottom_reserved = 32.0, 70.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_reserved
    n = len(ordered)
    bin_w = plot_w / n if n else plot_w
    bar_w = max(1.0, bin_w * 0.6)

    def y_for(v: float) -> float:
        return plot_y + plot_h - (v / y_domain * plot_h)

    parts: List[str] = []
    parts.append(svg_open(width, height, "bar-title", "bar-desc", font_family=chrome_stack_for_theme(theme)))
    parts.append(f'<title id="bar-title">{xml_escape(title)}</title>')
    top = ordered[0] if ordered else None
    peak_desc = (
        strings["peak_template"].format(
            region=top["region"], value=float(top["value"]), pct=float(top["value"]) / total * 100
        )
        if top else ""
    )
    parts.append(
        f'<desc id="bar-desc">{strings["desc_template"].format(n=n, max_val=max_val)}'
        f'{peak_desc}</desc>'
    )

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
    # plot_x above already widened to clear the widest tick label plus this
    # title's own room, so a fixed 14px inset from the canvas edge is enough
    # regardless of how many digits the tick numbers run to.
    axis_value_x = 14.0
    axis_value_y = plot_y + plot_h / 2
    parts.append(
        f'<text x="{axis_value_x:.1f}" y="{axis_value_y:.1f}" font-size="14" fill="{INK}" '
        f'text-anchor="middle" transform="rotate(-90 {axis_value_x:.1f} {axis_value_y:.1f})">'
        f'{xml_escape(y_label)}</text>'
    )

    for i, row in enumerate(ordered):
        region = str(row["region"])
        value = float(row["value"])
        x = plot_x + i * bin_w + (bin_w - bar_w) / 2
        y = y_for(value)
        h = plot_y + plot_h - y
        r = corner_radius(bar_w, max(h, 1.0), "bar")
        share = value / total * 100.0
        tip = strings["tooltip_template"].format(region=region, value=value, share=share)
        if h <= 0:
            continue
        path = bar_path(x, y, bar_w, h, r, side="top")
        parts.append(
            f'<path class="bar" tabindex="0" d="{path}" fill="{colors.get(region, "#007AFF")}">'
            f'<title>{xml_escape(tip)}</title></path>'
        )

    axis_y = plot_y + plot_h
    parts.append(
        f'<line x1="{plot_x:.1f}" y1="{axis_y:.1f}" x2="{plot_x + plot_w:.1f}" y2="{axis_y:.1f}" '
        f'stroke="{INK}" stroke-width="1.2"/>'
    )
    for i, row in enumerate(ordered):
        tx = plot_x + i * bin_w + bin_w / 2
        parts.append(
            f'<text x="{tx:.1f}" y="{axis_y + 20:.1f}" font-size="13" fill="{INK}" '
            f'text-anchor="middle">{xml_escape(str(row["region"]))}</text>'
        )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{axis_y + 44:.1f}" font-size="14" '
        f'fill="{INK}" text-anchor="middle">{xml_escape(x_label)}</text>'
    )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_bar(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    width: int = 745,
    height: int = 505,
    mode: str = "self-contained",
    accessibility: str = "universal",
    language: str = "en",
    x_label: Optional[str] = None,
    y_label: Optional[str] = None,
    theme: str = "corporate",
) -> Path:
    """Render a hand-authored grouped bar chart and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``region`` (str) and ``value`` (float).
        Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/bar.svg``.
    title, subtitle : str or None
        Chart text. ``None`` falls back to `language`'s chrome default.
    width, height : int
        Canvas size in pixels.
    mode, accessibility : str
        Forwarded to :func:`build_svg`.
    language : str, optional
        Chrome-text language, ``"en"`` or ``"fr"``. Defaults to ``"en"``;
        Sprezzature Studio passes the language detected from the imported
        CSV's column names (see :data:`_STRINGS`).
    theme : str, optional
        Visual theme. Forwarded to :func:`build_svg`.

    Returns
    -------
    Path
        Absolute path to the written SVG file.

    Examples
    --------
    >>> p = make_bar()
    >>> p.exists()
    True
    """
    svg = build_svg(data, title=title, subtitle=subtitle, width=width, height=height,
                     mode=mode, accessibility=accessibility, language=language,
                     x_label=x_label, y_label=y_label, theme=theme)
    dest = Path(out) if out else svg_example_path(__file__, "bar")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "bar", build_svg, description="Generate a grouped bar chart.")


if __name__ == "__main__":
    main()
