#!/usr/bin/env python3
"""
make_area — a stacked area chart via Vega-Lite.

Shows how a whole made of several categories evolves over an ordered axis,
emphasising both the total and each category's contribution. Typical uses:
traffic by acquisition channel over time, cumulative headcount by
department, resource usage by workload type.

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

CHANNEL_COLORS = {
    "Organic search": "#007AFF",
    "Paid search": "#FF9500",
    "Social": "#34C759",
    "Direct": "#AF52DE",
}

DEMO_DATA: List[Dict[str, Any]] = [
    {"month": m, "channel": c, "visits": v}
    for c, values in {
        "Organic search": [20, 22, 24, 25, 27, 29, 30, 32, 33, 35, 36, 38],
        "Paid search": [10, 11, 10, 12, 13, 12, 14, 15, 14, 16, 17, 18],
        "Social": [5, 6, 7, 9, 11, 13, 14, 16, 18, 19, 21, 23],
        "Direct": [8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13],
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
    channels = list(CHANNEL_COLORS.keys())
    color_range = [CHANNEL_COLORS[c] for c in channels]

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
        "mark": {"type": "area", "opacity": 0.85, "line": {"strokeWidth": 1.5}},
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
                "field": "visits",
                "type": "quantitative",
                "title": "Visits (thousands)",
                "stack": "zero",
                "axis": {
                    "labelFont": FONT_MONO,
                    "titleFont": FONT,
                    "titleColor": INK,
                    "labelColor": SECONDARY,
                    "gridColor": GRIDLINE,
                },
            },
            "color": {
                "field": "channel",
                "type": "nominal",
                "scale": {"domain": channels, "range": color_range},
                "legend": {"title": "Channel", "titleFont": FONT, "labelFont": FONT, "orient": "top-left"},
            },
            "order": {"field": "channel", "sort": "ascending"},
            "tooltip": [
                {"field": "channel", "type": "nominal", "title": "Channel"},
                {"field": "month", "type": "ordinal", "title": "Month"},
                {"field": "visits", "type": "quantitative", "title": "Visits (k)"},
            ],
        },
        "config": {"view": {"stroke": "transparent"}, "font": FONT},
    }


def make_area(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Website Traffic by Channel",
    subtitle: str = "Illustrative monthly visits, thousands",
    width: int = 800,
    height: int = 420,
) -> Path:
    """Render a stacked area chart and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``month`` (str), ``channel`` (str), ``visits`` (float).
        Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/area.svg``.
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
    >>> p = make_area()
    >>> p.exists()
    True
    """
    if data is None:
        data = DEMO_DATA
    spec = _build_vegalite_spec(data, title, subtitle, width, height)
    spec_json = json.dumps(spec, ensure_ascii=False)

    import vl_convert as vlc  # type: ignore

    svg_str = vlc.vegalite_to_svg(spec_json)

    dest = Path(out) if out else svg_example_path(__file__, "area")
    return write_svg(dest, svg_str)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Generate a stacked area chart.")
    p.add_argument("--out", default=None)
    p.add_argument("--title", default="Website Traffic by Channel")
    p.add_argument("--subtitle", default="Illustrative monthly visits, thousands")
    p.add_argument("--width", type=int, default=800)
    p.add_argument("--height", type=int, default=420)
    args = p.parse_args()
    make_area(out=args.out, title=args.title, subtitle=args.subtitle, width=args.width, height=args.height)
