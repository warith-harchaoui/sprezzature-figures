#!/usr/bin/env python3
"""
make_heatmap — a row x column matrix heatmap via Vega-Lite.

Encodes a numeric value as cell color across two categorical axes. Typical
uses: activity by day-of-week x hour, correlation matrices, A/B test
results by cohort x variant.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import argparse
import json
import random
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

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
HOURS = list(range(24))


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


def _build_vegalite_spec(
    data: List[Dict[str, Any]],
    title: str,
    subtitle: str,
    width: int,
    height: int,
) -> Dict[str, Any]:
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
        "mark": {"type": "rect"},
        "encoding": {
            "x": {
                "field": "hour",
                "type": "ordinal",
                "title": "Hour of day",
                "axis": {
                    "labelFont": FONT_MONO,
                    "titleFont": FONT,
                    "titleColor": INK,
                    "labelColor": SECONDARY,
                    "labelAngle": 0,
                },
            },
            "y": {
                "field": "day",
                "type": "ordinal",
                "sort": DAYS,
                "title": None,
                "axis": {"labelFont": FONT, "titleFont": FONT, "labelColor": INK},
            },
            "color": {
                "field": "activity",
                "type": "quantitative",
                "title": "Activity",
                "scale": {"scheme": "blues"},
                "legend": {"titleFont": FONT, "labelFont": FONT_MONO},
            },
            "tooltip": [
                {"field": "day", "type": "ordinal", "title": "Day"},
                {"field": "hour", "type": "ordinal", "title": "Hour"},
                {"field": "activity", "type": "quantitative", "title": "Activity"},
            ],
        },
        "config": {"view": {"stroke": "transparent"}, "font": FONT, "axis": {"domain": False, "ticks": False}},
    }


def make_heatmap(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Activity by Day and Hour",
    subtitle: str = "Synthetic weekly usage pattern",
    width: int = 820,
    height: int = 320,
) -> Path:
    """Render a row x column heatmap and write the SVG to *out*.

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
    if data is None:
        data = DEMO_DATA
    spec = _build_vegalite_spec(data, title, subtitle, width, height)
    spec_json = json.dumps(spec, ensure_ascii=False)

    import vl_convert as vlc  # type: ignore

    svg_str = vlc.vegalite_to_svg(spec_json)

    dest = Path(out) if out else svg_example_path(__file__, "heatmap")
    return write_svg(dest, svg_str)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Generate a row x column heatmap.")
    p.add_argument("--out", default=None)
    p.add_argument("--title", default="Activity by Day and Hour")
    p.add_argument("--subtitle", default="Synthetic weekly usage pattern")
    p.add_argument("--width", type=int, default=820)
    p.add_argument("--height", type=int, default=320)
    args = p.parse_args()
    make_heatmap(out=args.out, title=args.title, subtitle=args.subtitle, width=args.width, height=args.height)
