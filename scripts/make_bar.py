#!/usr/bin/env python3
"""
make_bar — a grouped bar chart via Vega-Lite.

The default chart type for comparing a numeric value across a handful of
categories. Grouped (colored) bars let a second categorical dimension share
the same axis without stacking, so individual values stay directly
comparable. Typical uses: revenue by region, headcount by department,
survey scores by cohort.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _render import svg_example_path, write_svg  # noqa: E402

INK = "#1D1D1F"
SECONDARY = "#6E6E73"
BG = "#FFFFFF"
GRIDLINE = "#E5E5EA"
FONT = "Roboto, system-ui, sans-serif"
FONT_MONO = "Roboto Mono, ui-monospace, monospace"

CATEGORY_COLORS = {
    "North": "#007AFF",
    "South": "#FF9500",
    "East": "#34C759",
    "West": "#AF52DE",
}

DEMO_DATA: List[Dict[str, Any]] = [
    {"region": "North", "value": 42},
    {"region": "South", "value": 28},
    {"region": "East", "value": 19},
    {"region": "West", "value": 11},
]


def _build_vegalite_spec(
    data: List[Dict[str, Any]],
    title: str,
    subtitle: str,
    width: int,
    height: int,
) -> Dict[str, Any]:
    categories = sorted({row["region"] for row in data})
    color_range = [CATEGORY_COLORS.get(c, "#007AFF") for c in categories]

    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "width": width,
        "height": height,
        "background": BG,
        "title": {
            "text": title,
            "subtitle": subtitle,
            "font": FONT,
            "fontSize": 20,
            "fontWeight": 600,
            "subtitleFont": FONT,
            "subtitleFontSize": 12,
            "subtitleColor": SECONDARY,
            "color": INK,
            "anchor": "start",
        },
        "data": {"values": data},
        "mark": {"type": "bar", "cornerRadiusTopLeft": 3, "cornerRadiusTopRight": 3},
        "encoding": {
            "x": {
                "field": "region",
                "type": "nominal",
                "sort": "-y",
                "title": "Region",
                "axis": {
                    "labelFont": FONT,
                    "titleFont": FONT,
                    "titleColor": INK,
                    "labelColor": INK,
                    "grid": False,
                    "labelAngle": 0,
                },
            },
            "y": {
                "field": "value",
                "type": "quantitative",
                "title": "Value",
                "axis": {
                    "labelFont": FONT_MONO,
                    "titleFont": FONT,
                    "titleColor": INK,
                    "labelColor": SECONDARY,
                    "gridColor": GRIDLINE,
                },
            },
            "color": {
                "field": "region",
                "type": "nominal",
                "scale": {"domain": categories, "range": color_range},
                "legend": None,
            },
            "tooltip": [
                {"field": "region", "type": "nominal", "title": "Region"},
                {"field": "value", "type": "quantitative", "title": "Value"},
            ],
        },
        "config": {"view": {"stroke": "transparent"}, "font": FONT},
    }


def make_bar(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Revenue by Region",
    subtitle: str = "Illustrative quarterly figures",
    width: int = 700,
    height: int = 420,
) -> Path:
    """Render a grouped bar chart and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``region`` (str) and ``value`` (float).
        Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/bar.svg``.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.

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
    if data is None:
        data = DEMO_DATA
    spec = _build_vegalite_spec(data, title, subtitle, width, height)
    spec_json = json.dumps(spec, ensure_ascii=False)

    import vl_convert as vlc  # type: ignore

    svg_str = vlc.vegalite_to_svg(spec_json)

    dest = Path(out) if out else svg_example_path(__file__, "bar")
    return write_svg(dest, svg_str)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Generate a grouped bar chart.")
    p.add_argument("--out", default=None)
    p.add_argument("--title", default="Revenue by Region")
    p.add_argument("--subtitle", default="Illustrative quarterly figures")
    p.add_argument("--width", type=int, default=700)
    p.add_argument("--height", type=int, default=420)
    args = p.parse_args()
    make_bar(out=args.out, title=args.title, subtitle=args.subtitle, width=args.width, height=args.height)
