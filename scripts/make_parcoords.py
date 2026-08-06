#!/usr/bin/env python3
"""
make_parcoords — a house-styled parallel-coordinates plot as a hand SVG.

Parallel coordinates show many numeric dimensions at once: one vertical axis per
metric, and each record a polyline crossing all of them. It is the tool for
seeing how a few groups separate across several measures simultaneously. Here,
car classes (compact / midsize / SUV) are traced across four metrics, each axis
carrying its **units** in the title and only min/max ticks so the labels never
collide. The three classes fall into three clean bands: compacts are light,
economical and low-powered; SUVs are heavy, thirsty and powerful; midsize sits
between.

Built by hand — no matplotlib / Vega — to match the other hero figures, with a
native ``<title>`` per line and an accessible ``<title>``/``<desc>``.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _style import load_palette  # noqa: E402
from _svg import svg_open, xml_escape  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _interactive import fullscreen_control  # noqa: E402

# --- axes: (key, title-with-unit, domain low, high) ---------------------------
AXES: List[Tuple[str, str, float, float]] = [
    ("mpg", "mpg", 14.0, 36.0),
    ("hp", "hp (ch)", 60.0, 220.0),
    ("weight", "weight (lb)", 2000.0, 4400.0),
    ("accel", "accel (0-100 km/h, s)", 7.0, 12.0),
]

# --- data: five cars per class, chosen so the classes separate cleanly --------
CARS: Dict[str, List[Dict[str, float]]] = {
    "Compact": [
        {"mpg": 33, "hp": 105, "weight": 2300, "accel": 10.8},
        {"mpg": 31, "hp": 120, "weight": 2500, "accel": 10.2},
        {"mpg": 30, "hp": 110, "weight": 2400, "accel": 11.4},
        {"mpg": 34, "hp": 100, "weight": 2200, "accel": 11.1},
        {"mpg": 29, "hp": 130, "weight": 2650, "accel": 9.6},
    ],
    "Midsize": [
        {"mpg": 25, "hp": 140, "weight": 3000, "accel": 9.2},
        {"mpg": 24, "hp": 150, "weight": 3200, "accel": 9.5},
        {"mpg": 26, "hp": 135, "weight": 2950, "accel": 9.0},
        {"mpg": 23, "hp": 160, "weight": 3300, "accel": 9.6},
        {"mpg": 24, "hp": 145, "weight": 3100, "accel": 9.3},
    ],
    "SUV": [
        {"mpg": 17, "hp": 205, "weight": 4200, "accel": 11.3},
        {"mpg": 15, "hp": 210, "weight": 4350, "accel": 11.6},
        {"mpg": 19, "hp": 185, "weight": 3950, "accel": 10.9},
        {"mpg": 16, "hp": 200, "weight": 4100, "accel": 11.4},
        {"mpg": 18, "hp": 190, "weight": 4000, "accel": 11.0},
    ],
}

_WIDTH = 1200
_HEIGHT = 720
_M_LEFT, _M_RIGHT = 96, 150  # generous right margin so the long last-axis title fits
_AX_TOP, _AX_BOT = 214.0, 628.0
_INK = "#1D1D1F"
_SUBTLE = "#6E6E73"
_GRID = "#E5E5EA"
_BG = "#FFFFFF"


def _fmt(v: float) -> str:
    return f"{v:g}"


#: Cycling hue order for a custom class set beyond the three the default
#: story names, in the same order the default classes already use.
_CLASS_HUE_ORDER = ["Blue", "Orange", "Green", "Purple", "Teal", "Pink", "Yellow", "Indigo", "Gray"]


def build_svg(
    rows: Optional[List[Dict[str, Any]]] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
) -> str:
    """Assemble the full parallel-coordinates SVG string.

    Parameters
    ----------
    rows : list of dict or None
        Records with a ``car_class`` label plus the four axis keys
        (``mpg``, ``hp``, ``weight``, ``accel``). Defaults to the built-in
        illustrative fleet (:data:`CARS`, flattened). A custom class set
        gets its colours by cycling house hues in order of first
        appearance rather than the three story-specific class hues.
    mode, accessibility : str
        Canvas interactivity mode / palette accessibility level.

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    pal = load_palette(accessibility)
    if rows:
        grouped: Dict[str, List[Dict[str, float]]] = {}
        for r in rows:
            grouped.setdefault(str(r["car_class"]), []).append(
                {key: float(r[key]) for key, _t, _lo, _hi in AXES if key in r}
            )
        cars_by_class = grouped
        class_color = {
            name: pal.get(_CLASS_HUE_ORDER[i % len(_CLASS_HUE_ORDER)], "#8E8E93")
            for i, name in enumerate(grouped)
        }
    else:
        cars_by_class = CARS
        class_color = {
            "Compact": pal.get("Blue", "#007AFF"),
            "Midsize": pal.get("Orange", "#FF9500"),
            "SUV": pal.get("Green", "#34C759"),
        }
    n_ax = len(AXES)
    span = _WIDTH - _M_LEFT - _M_RIGHT
    ax_x = [_M_LEFT + (span * i / (n_ax - 1)) for i in range(n_ax)]

    def y_of(value: float, lo: float, hi: float) -> float:
        t = 0.0 if hi == lo else (value - lo) / (hi - lo)
        t = max(0.0, min(1.0, t))
        return _AX_BOT - t * (_AX_BOT - _AX_TOP)

    parts: List[str] = []
    parts.append(svg_open(_WIDTH, _HEIGHT, "pc-title", "pc-desc"))
    parts.append(
        '<title id="pc-title">Car classes separate cleanly across four metrics: '
        'compacts light and economical, SUVs heavy and powerful</title>'
    )
    parts.append(
        '<desc id="pc-desc">Parallel-coordinates plot of three car classes '
        '(compact, midsize, SUV) across four metrics — fuel economy (mpg), power '
        '(hp), weight (lb) and 0-100 km/h time (s). Each car is a polyline '
        'crossing all four vertical axes; the three classes fall into three '
        'separated bands.</desc>'
    )
    parts.append(f'<rect width="{_WIDTH}" height="{_HEIGHT}" fill="{_BG}"/>')

    # Title + subtitle.
    parts.append(
        f'<text x="40" y="56" font-size="26" font-weight="600" fill="{_INK}" '
        f'letter-spacing="-0.3">Cars by class across four metrics</text>'
    )
    parts.append(
        f'<text x="40" y="84" font-size="14" fill="{_SUBTLE}">'
        f'Three classes traced over four measures · each line is one car</text>'
    )

    # Legend (top, under the subtitle).
    lx = 40.0
    for name in cars_by_class:
        color = class_color[name]
        parts.append(f'<rect x="{lx:.1f}" y="108" width="16" height="16" rx="3" fill="{color}"/>')
        parts.append(
            f'<text x="{lx + 22:.1f}" y="121" font-size="14" fill="{_INK}">{name}</text>'
        )
        lx += 40 + 8.5 * len(name) + 26

    # Axes: vertical line, title (with unit), min/max ticks.
    for i, (_key, title, lo, hi) in enumerate(AXES):
        x = ax_x[i]
        parts.append(
            f'<line x1="{x:.1f}" y1="{_AX_TOP:.1f}" x2="{x:.1f}" y2="{_AX_BOT:.1f}" '
            f'stroke="{_GRID}" stroke-width="1.5"/>'
        )
        parts.append(
            f'<text x="{x:.1f}" y="{_AX_TOP - 22:.1f}" font-size="15" font-weight="700" '
            f'fill="{_INK}" text-anchor="middle">{xml_escape(title)}</text>'
        )
        parts.append(
            f'<text x="{x:.1f}" y="{_AX_TOP - 4:.1f}" font-size="12.5" '
            f'font-family="Roboto Mono, monospace" fill="{_SUBTLE}" text-anchor="middle">'
            f'{_fmt(hi)}</text>'
        )
        parts.append(
            f'<text x="{x:.1f}" y="{_AX_BOT + 20:.1f}" font-size="12.5" '
            f'font-family="Roboto Mono, monospace" fill="{_SUBTLE}" text-anchor="middle">'
            f'{_fmt(lo)}</text>'
        )

    # Polylines: one per car, coloured by class.
    for name, cars in cars_by_class.items():
        color = class_color[name]
        for car in cars:
            pts = " ".join(
                f"{ax_x[i]:.1f},{y_of(car[key], lo, hi):.1f}"
                for i, (key, _t, lo, hi) in enumerate(AXES)
            )
            tip = f"{name}: " + ", ".join(f"{k} {_fmt(car[k])}" for k, _t, _l, _h in AXES)
            parts.append(
                f'<polyline points="{pts}" fill="none" stroke="{color}" '
                f'stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" '
                f'opacity="0.72"><title>{xml_escape(tip)}</title></polyline>'
            )

    parts.append(fullscreen_control(_WIDTH, _HEIGHT, mode))
    parts.append("</svg>")
    return "\n".join(parts)


#: The registry contract's DEMO_DATA: :data:`CARS` flattened to row records.
DEMO_DATA: List[Dict[str, Any]] = [
    {"car_class": name, **car} for name, cars in CARS.items() for car in cars
]


def make_parcoords(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "",
    mode: str = "self-contained",
    accessibility: str = "universal",
) -> Path:
    """Render the parallel-coordinates plot and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with a ``car_class`` label plus ``mpg``, ``hp``, ``weight``,
        ``accel``. Defaults to :data:`DEMO_DATA`. See :func:`build_svg` for
        how a custom class set is coloured. ``title`` is accepted for
        signature parity with the rest of the gallery and is currently a
        documented no-op.
    out : Path, str, or None
        Output path. Defaults to ``assets/svg-examples/parcoords.svg``.
    mode, accessibility : str
        Forwarded to :func:`build_svg`.

    Returns
    -------
    Path
        Absolute path to the written SVG file.
    """
    _ = title
    rows = data if data else DEMO_DATA
    svg = build_svg(rows, mode=mode, accessibility=accessibility)
    dest = Path(out) if out else svg_example_path(__file__, "parcoords")
    return write_svg(dest, svg)


def main() -> None:
    """Write the parallel-coordinates SVG to the canonical assets path."""
    render_cli(__file__, "parcoords", build_svg,
               description="Render the parallel-coordinates SVG.")


if __name__ == "__main__":
    main()
