#!/usr/bin/env python3
"""
make_scatter — a scatter plot via Vega-Lite.

Plots two numeric variables against each other, with an optional categorical
color and numeric size encoding, to reveal correlation, clusters, or
outliers. Typical uses: price vs. quality rating, engine size vs. fuel
economy, marketing spend vs. conversions.

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
from _vl import categorical_domain_and_range  # noqa: E402

INK = "#1D1D1F"
SECONDARY = "#6E6E73"
BG = "#FFFFFF"
GRIDLINE = "#E5E5EA"
FONT = "Roboto, system-ui, sans-serif"
FONT_MONO = "Roboto Mono, ui-monospace, monospace"

SEGMENT_COLORS = {
    "Economy": "#007AFF",
    "Midsize": "#FF9500",
    "Premium": "#34C759",
}


def _make_demo_data() -> List[Dict[str, Any]]:
    rng = random.Random(11)
    rows: List[Dict[str, Any]] = []
    segments = {
        "Economy": (25, 35, 90, 120),
        "Midsize": (18, 26, 130, 180),
        "Premium": (10, 18, 200, 320),
    }
    for segment, (mpg_lo, mpg_hi, hp_lo, hp_hi) in segments.items():
        for _ in range(15):
            rows.append(
                {
                    "segment": segment,
                    "horsepower": round(rng.uniform(hp_lo, hp_hi), 1),
                    "mpg": round(rng.uniform(mpg_lo, mpg_hi), 1),
                    "weight": round(rng.uniform(1100, 1900), 0),
                }
            )
    return rows


DEMO_DATA: List[Dict[str, Any]] = _make_demo_data()


def _build_vegalite_spec(
    data: List[Dict[str, Any]],
    title: str,
    subtitle: str,
    width: int,
    height: int,
) -> Dict[str, Any]:
    domain_range = categorical_domain_and_range(data, "segment", SEGMENT_COLORS)
    has_weight = any("weight" in row and row["weight"] is not None for row in data)

    encoding: Dict[str, Any] = {
        "x": {
            "field": "horsepower",
            "type": "quantitative",
            "title": "Horsepower",
            "scale": {"zero": False},
            "axis": {
                "labelFont": FONT_MONO,
                "titleFont": FONT,
                "titleColor": INK,
                "labelColor": SECONDARY,
                "gridColor": GRIDLINE,
            },
        },
        "y": {
            "field": "mpg",
            "type": "quantitative",
            "title": "Fuel economy (mpg)",
            "scale": {"zero": False},
            "axis": {
                "labelFont": FONT_MONO,
                "titleFont": FONT,
                "titleColor": INK,
                "labelColor": SECONDARY,
                "gridColor": GRIDLINE,
            },
        },
        "tooltip": [
            {"field": "horsepower", "type": "quantitative", "title": "Horsepower"},
            {"field": "mpg", "type": "quantitative", "title": "MPG"},
        ],
    }
    # "weight" and "segment" are both optional data roles (see
    # catalog.HAND_ROLES): only size/color-encode by them when the data
    # actually carries them -- otherwise every mark got an undefined size
    # (weight) or a legend for demo categories that aren't in the data
    # (segment).
    if has_weight:
        encoding["size"] = {
            "field": "weight",
            "type": "quantitative",
            "title": "Weight (kg)",
            "scale": {"range": [40, 300]},
            "legend": {"titleFont": FONT, "labelFont": FONT},
        }
        encoding["tooltip"].append({"field": "weight", "type": "quantitative", "title": "Weight (kg)"})
    if domain_range is not None:
        domain, color_range = domain_range
        encoding["color"] = {
            "field": "segment",
            "type": "nominal",
            "scale": {"domain": domain, "range": color_range},
            "legend": {"title": "Segment", "titleFont": FONT, "labelFont": FONT},
        }
        encoding["tooltip"].insert(0, {"field": "segment", "type": "nominal", "title": "Segment"})

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
        "mark": {"type": "circle", "opacity": 0.75},
        "encoding": encoding,
        "config": {"view": {"stroke": "transparent"}, "font": FONT},
    }


def make_scatter(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Horsepower vs. Fuel Economy",
    subtitle: str = "Synthetic sample, sized by weight, colored by segment",
    width: int = 800,
    height: int = 500,
) -> Path:
    """Render a scatter plot and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``segment`` (str), ``horsepower`` (float), ``mpg``
        (float), ``weight`` (float). Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/scatter.svg``.
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
    >>> p = make_scatter()
    >>> p.exists()
    True
    """
    if data is None:
        data = DEMO_DATA
    spec = _build_vegalite_spec(data, title, subtitle, width, height)
    spec_json = json.dumps(spec, ensure_ascii=False)

    import vl_convert as vlc  # type: ignore

    svg_str = vlc.vegalite_to_svg(spec_json)

    dest = Path(out) if out else svg_example_path(__file__, "scatter")
    return write_svg(dest, svg_str)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Generate a scatter plot.")
    p.add_argument("--out", default=None)
    p.add_argument("--title", default="Horsepower vs. Fuel Economy")
    p.add_argument("--subtitle", default="Synthetic sample, sized by weight, colored by segment")
    p.add_argument("--width", type=int, default=800)
    p.add_argument("--height", type=int, default=500)
    args = p.parse_args()
    make_scatter(out=args.out, title=args.title, subtitle=args.subtitle, width=args.width, height=args.height)
