#!/usr/bin/env python3
"""
make_line — a multi-series line chart via Vega-Lite.

The default chart for showing how a numeric value evolves over an ordered
axis (typically time) across a small number of series. Points are drawn on
top of the lines so exact readings and gaps in the data stay visible.
Typical uses: monthly revenue by product line, daily active users, sensor
readings over time.

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

SERIES_COLORS = {
    "Hardware": "#007AFF",
    "Software": "#FF9500",
    "Services": "#34C759",
}

DEMO_DATA: List[Dict[str, Any]] = [
    {"month": m, "series": s, "value": v}
    for s, values in {
        "Hardware": [12, 14, 13, 17, 19, 22, 21, 24, 23, 26, 28, 31],
        "Software": [8, 9, 10, 11, 13, 14, 16, 17, 19, 21, 23, 25],
        "Services": [5, 5, 6, 6, 7, 8, 8, 9, 10, 11, 12, 13],
    }.items()
    for m, v in zip(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        values,
    )
]


def _build_vegalite_spec(
    data: List[Dict[str, Any]],
    title: str,
    subtitle: str,
    width: int,
    height: int,
) -> Dict[str, Any]:
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    series = sorted({row["series"] for row in data})
    color_range = [SERIES_COLORS.get(s, "#007AFF") for s in series]

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
        "mark": {"type": "line", "point": True, "strokeWidth": 2.5},
        "encoding": {
            "x": {
                "field": "month",
                "type": "ordinal",
                "sort": months,
                "title": "Month",
                "axis": {
                    "labelFont": FONT,
                    "titleFont": FONT,
                    "titleColor": INK,
                    "labelColor": INK,
                    "grid": False,
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
                "field": "series",
                "type": "nominal",
                "scale": {"domain": series, "range": color_range},
                "legend": {"title": "Series", "titleFont": FONT, "labelFont": FONT, "orient": "top-left"},
            },
            "tooltip": [
                {"field": "series", "type": "nominal", "title": "Series"},
                {"field": "month", "type": "ordinal", "title": "Month"},
                {"field": "value", "type": "quantitative", "title": "Value"},
            ],
        },
        "config": {"view": {"stroke": "transparent"}, "font": FONT},
    }


def make_line(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Monthly Revenue by Product Line",
    subtitle: str = "Illustrative figures, thousands of EUR",
    width: int = 800,
    height: int = 420,
) -> Path:
    """Render a multi-series line chart and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``month`` (str), ``series`` (str), ``value`` (float).
        Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/line.svg``.
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
    >>> p = make_line()
    >>> p.exists()
    True
    """
    if data is None:
        data = DEMO_DATA
    spec = _build_vegalite_spec(data, title, subtitle, width, height)
    spec_json = json.dumps(spec, ensure_ascii=False)

    import vl_convert as vlc  # type: ignore

    svg_str = vlc.vegalite_to_svg(spec_json)

    dest = Path(out) if out else svg_example_path(__file__, "line")
    return write_svg(dest, svg_str)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Generate a multi-series line chart.")
    p.add_argument("--out", default=None)
    p.add_argument("--title", default="Monthly Revenue by Product Line")
    p.add_argument("--subtitle", default="Illustrative figures, thousands of EUR")
    p.add_argument("--width", type=int, default=800)
    p.add_argument("--height", type=int, default=420)
    args = p.parse_args()
    make_line(out=args.out, title=args.title, subtitle=args.subtitle, width=args.width, height=args.height)
