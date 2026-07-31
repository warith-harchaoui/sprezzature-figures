#!/usr/bin/env python3
"""
make_boxplot — a box plot by category via Vega-Lite.

Summarises a numeric distribution's median, quartiles, and outliers per
category using Vega-Lite's native ``boxplot`` mark. Typical uses: salary
distribution by department, response time by service, test scores by class.

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
COLOR_BOX = "#007AFF"


def _make_demo_data() -> List[Dict[str, Any]]:
    rng = random.Random(11)
    departments = {
        "Engineering": (65, 130),
        "Sales": (50, 110),
        "Marketing": (45, 95),
        "Support": (40, 80),
    }
    rows: List[Dict[str, Any]] = []
    for dept, (lo, hi) in departments.items():
        for _ in range(25):
            rows.append({"department": dept, "salary": round(rng.uniform(lo, hi), 1)})
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
        "mark": {"type": "boxplot", "color": COLOR_BOX, "size": 40},
        "encoding": {
            "x": {
                "field": "department",
                "type": "nominal",
                "title": "Department",
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
                "field": "salary",
                "type": "quantitative",
                "title": "Salary (thousands EUR)",
                "scale": {"zero": False},
                "axis": {
                    "labelFont": FONT_MONO,
                    "titleFont": FONT,
                    "titleColor": INK,
                    "labelColor": SECONDARY,
                    "gridColor": GRIDLINE,
                },
            },
        },
        "config": {"view": {"stroke": "transparent"}, "font": FONT},
    }


def make_boxplot(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Salary Distribution by Department",
    subtitle: str = "Synthetic sample, thousands of EUR",
    width: int = 700,
    height: int = 420,
) -> Path:
    """Render a box plot and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``department`` (str) and ``salary`` (float).
        Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/boxplot.svg``.
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
    >>> p = make_boxplot()
    >>> p.exists()
    True
    """
    if data is None:
        data = DEMO_DATA
    spec = _build_vegalite_spec(data, title, subtitle, width, height)
    spec_json = json.dumps(spec, ensure_ascii=False)

    import vl_convert as vlc  # type: ignore

    svg_str = vlc.vegalite_to_svg(spec_json)

    dest = Path(out) if out else svg_example_path(__file__, "boxplot")
    return write_svg(dest, svg_str)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Generate a box plot by category.")
    p.add_argument("--out", default=None)
    p.add_argument("--title", default="Salary Distribution by Department")
    p.add_argument("--subtitle", default="Synthetic sample, thousands of EUR")
    p.add_argument("--width", type=int, default=700)
    p.add_argument("--height", type=int, default=420)
    args = p.parse_args()
    make_boxplot(out=args.out, title=args.title, subtitle=args.subtitle, width=args.width, height=args.height)
