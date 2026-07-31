#!/usr/bin/env python3
"""
make_histogram — a binned distribution histogram via Vega-Lite.

Bins a single numeric variable and counts observations per bin, the default
chart for understanding a distribution's shape, spread, and skew. Typical
uses: exam score distributions, response time distributions, order value
distributions.

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
COLOR_BAR = "#007AFF"


def _make_demo_data() -> List[Dict[str, Any]]:
    rng = random.Random(11)
    # Approximate a bell-shaped distribution of exam scores via the
    # sum-of-uniforms trick, so no extra dependency (numpy) is needed here.
    scores = [round(sum(rng.uniform(0, 1) for _ in range(6)) / 6 * 60 + 40, 1) for _ in range(300)]
    return [{"score": s} for s in scores]


DEMO_DATA: List[Dict[str, Any]] = _make_demo_data()


def _build_vegalite_spec(
    data: List[Dict[str, Any]],
    title: str,
    subtitle: str,
    width: int,
    height: int,
    bin_count: int,
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
        "mark": {"type": "bar", "color": COLOR_BAR, "opacity": 0.85},
        "encoding": {
            "x": {
                "field": "score",
                "type": "quantitative",
                "bin": {"maxbins": bin_count},
                "title": "Exam score",
                "axis": {
                    "labelFont": FONT_MONO,
                    "titleFont": FONT,
                    "titleColor": INK,
                    "labelColor": INK,
                    "grid": False,
                },
            },
            "y": {
                "aggregate": "count",
                "type": "quantitative",
                "title": "Number of students",
                "axis": {
                    "labelFont": FONT_MONO,
                    "titleFont": FONT,
                    "titleColor": INK,
                    "labelColor": SECONDARY,
                    "gridColor": GRIDLINE,
                },
            },
            "tooltip": [
                {"field": "score", "type": "quantitative", "bin": {"maxbins": bin_count}, "title": "Score range"},
                {"aggregate": "count", "type": "quantitative", "title": "Count"},
            ],
        },
        "config": {"view": {"stroke": "transparent"}, "font": FONT, "bar": {"binSpacing": 1}},
    }


def make_histogram(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Exam Score Distribution",
    subtitle: str = "Synthetic sample, 300 students",
    width: int = 700,
    height: int = 420,
    bin_count: int = 20,
) -> Path:
    """Render a histogram and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with key ``score`` (float). Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/histogram.svg``.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    bin_count : int
        Approximate number of bins. Default 20.

    Returns
    -------
    Path
        Absolute path to the written SVG file.

    Examples
    --------
    >>> p = make_histogram()
    >>> p.exists()
    True
    """
    if data is None:
        data = DEMO_DATA
    spec = _build_vegalite_spec(data, title, subtitle, width, height, bin_count)
    spec_json = json.dumps(spec, ensure_ascii=False)

    import vl_convert as vlc  # type: ignore

    svg_str = vlc.vegalite_to_svg(spec_json)

    dest = Path(out) if out else svg_example_path(__file__, "histogram")
    return write_svg(dest, svg_str)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Generate a distribution histogram.")
    p.add_argument("--out", default=None)
    p.add_argument("--title", default="Exam Score Distribution")
    p.add_argument("--subtitle", default="Synthetic sample, 300 students")
    p.add_argument("--width", type=int, default=700)
    p.add_argument("--height", type=int, default=420)
    p.add_argument("--bin-count", type=int, default=20)
    args = p.parse_args()
    make_histogram(
        out=args.out, title=args.title, subtitle=args.subtitle,
        width=args.width, height=args.height, bin_count=args.bin_count,
    )
