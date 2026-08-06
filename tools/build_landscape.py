"""
build_landscape.py — hand-authored SVG for the data-viz landscape quadrant.

``assets/landscape.{svg,white.svg,png,white.png}`` compare sprezzature-figures
to 36 other data-viz tools on two PCA-derived axes (user-friendly <-> versatile,
dynamic <-> robust). This diagram sits outside the ``make_<kind>.py`` chart
catalog (no generator produces it, it is not in FIGURES.md, ``make_figure()``
cannot reach it) — it is a one-off marketing quadrant, not a reusable chart
type. It used to be rendered from ``assets/landscape.vl.json`` via Vega; this
script replaces that with the same direct hand-authored SVG approach every
``make_<kind>.py`` generator already uses, so the repository carries zero Vega
specs anywhere.

``assets/landscape.yaml`` is the single data source: per-tool PCA coordinates
(``axis_1``/``axis_2``), a manually tuned label offset (``label_x``/
``label_y``, so 37 overlapping names stay legible), role, and color. The pixel
mapping below (``X_SCALE``/``Y_SCALE`` and the axis-label baseline nudges) was
recovered by fitting the previously Vega-rendered ``landscape.svg`` against
this same yaml data (affine regression, sub-pixel residual) so the hand-drawn
output lands in the same place the old Vega chart did — a one-time calibration
against this specific figure's layout, not a general chart-scale formula.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from _render import _svg_to_png_bytes, write_svg  # noqa: E402
from _svg import svg_open, xml_escape  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
YAML_PATH = ROOT / "assets" / "landscape.yaml"
ASSETS = ROOT / "assets"

FONT = "Roboto, -apple-system, Helvetica, Arial, sans-serif"
INK = "#1C1C1E"
MUTED = "#6E6E73"
GRID = "#C7C7CC"
TITLE = "Data viz tools in the Quadrant"

CANVAS_W = 1024
CANVAS_H = 1074

# Affine data -> absolute-pixel mapping, fit against the previously
# Vega-rendered landscape.svg (max residual < 0.004px across all 37 points).
# Already folds in the plot group's own (12, 34) translate, so callers work
# in absolute canvas pixels directly.
X_SCALE = 62.5
X_OFFSET = 512.0
Y_SCALE = -514.0 / 7.0
Y_OFFSET = 548.0

# The dashed quadrant cross lines stop short of the axis-label text, in data
# units (also recovered from the Vega spec).
CROSS_X_HALF = 6.862412171516243
CROSS_Y_HALF = 6.346176172906386

# (text, axis_1, axis_2, text-anchor, baseline dy) for the four pole labels.
# The dy values reproduce Vega's "bottom" (-4px) and "top" (+15.13px)
# baselines for this 19px italic label — specific to this one figure.
AXIS_LABELS = [
    ("Versatile", 6.652338329531052, 0.1523691758200813, "end", -4.0),
    ("User-friendly", -6.652338329531052, 0.1523691758200813, "start", -4.0),
    ("Robust", 0.16476379763544402, 6.151905473735782, "start", 15.13),
    ("Dynamic", 0.16476379763544402, -6.151905473735782, "start", -4.0),
]

POINT_RADIUS = 5.1
POINT_LABEL_DY = 4.0


def x_px(axis1: float) -> float:
    return X_SCALE * axis1 + X_OFFSET


def y_px(axis2: float) -> float:
    return Y_SCALE * axis2 + Y_OFFSET


def _load_approaches() -> List[Dict[str, Any]]:
    data = yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))
    return data["approaches"]


def build_svg(*, white_bg: bool = False) -> str:
    approaches = _load_approaches()
    parts: List[str] = [
        svg_open(CANVAS_W, CANVAS_H, "landscape-title", "landscape-desc", font_family=FONT),
        f'<title id="landscape-title">{xml_escape(TITLE)}</title>',
        f'<desc id="landscape-desc">Quadrant positioning sprezzature-figures against '
        f"36 other data-visualisation tools on user-friendly versus versatile and "
        f"dynamic versus robust axes.</desc>",
    ]
    if white_bg:
        parts.append(f'<rect width="{CANVAS_W}" height="{CANVAS_H}" fill="white"/>')

    # Dashed quadrant cross.
    parts.append(
        f'<line x1="{x_px(-CROSS_X_HALF):.2f}" y1="{y_px(0):.2f}" '
        f'x2="{x_px(CROSS_X_HALF):.2f}" y2="{y_px(0):.2f}" '
        f'stroke="{GRID}" stroke-width="1.2" stroke-dasharray="2,4"/>'
    )
    parts.append(
        f'<line x1="{x_px(0):.2f}" y1="{y_px(-CROSS_Y_HALF):.2f}" '
        f'x2="{x_px(0):.2f}" y2="{y_px(CROSS_Y_HALF):.2f}" '
        f'stroke="{GRID}" stroke-width="1.2" stroke-dasharray="2,4"/>'
    )

    # Pole labels.
    for text, a1, a2, anchor, dy in AXIS_LABELS:
        parts.append(
            f'<text x="{x_px(a1):.2f}" y="{y_px(a2) + dy:.2f}" font-family="{FONT}" '
            f'font-size="19" font-style="italic" fill="{MUTED}" text-anchor="{anchor}">'
            f"{xml_escape(text)}</text>"
        )

    # Points.
    for a in approaches:
        name = a["name"]
        coords = a["coordinates"]
        cx, cy = x_px(coords["axis_1"]), y_px(coords["axis_2"])
        parts.append(
            f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{POINT_RADIUS}" fill="{a["color"]}" '
            f'stroke="white" stroke-width="1" opacity="0.95">'
            f"<title>{xml_escape(name)}: {xml_escape(a['role'])}</title></circle>"
        )

    # Point-name labels (drawn last so no marker overlaps a label).
    for a in approaches:
        coords = a["coordinates"]
        lx, ly = x_px(coords["label_x"]), y_px(coords["label_y"]) + POINT_LABEL_DY
        parts.append(
            f'<text x="{lx:.2f}" y="{ly:.2f}" font-family="{FONT}" font-size="12" '
            f'fill="{INK}" text-anchor="middle">{xml_escape(a["name"])}</text>'
        )

    # Title.
    parts.append(
        f'<text x="{CANVAS_W / 2:.2f}" y="26" font-family="{FONT}" font-size="18" '
        f'font-weight="bold" fill="#000" text-anchor="middle">{xml_escape(TITLE)}</text>'
    )

    parts.append("</svg>")
    return "".join(parts)


def main() -> None:
    svg = build_svg(white_bg=False)
    svg_white = build_svg(white_bg=True)

    write_svg(ASSETS / "landscape.svg", svg, embed_fonts=False)
    write_svg(ASSETS / "landscape.white.svg", svg_white, embed_fonts=False)

    (ASSETS / "landscape.png").write_bytes(_svg_to_png_bytes(svg))
    (ASSETS / "landscape.white.png").write_bytes(_svg_to_png_bytes(svg_white))
    print(f"wrote {ASSETS / 'landscape.png'}")
    print(f"wrote {ASSETS / 'landscape.white.png'}")


if __name__ == "__main__":
    main()
