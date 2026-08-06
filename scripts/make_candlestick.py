#!/usr/bin/env python3
"""
make_candlestick — a house-styled OHLC candlestick chart as hand-authored SVG.

Encodes four numbers per period at once: a thin wick spans low to high, a
thick body spans open to close, coloured green when the period closed
higher than it opened and red when it closed lower. Reading the wick
length shows intraday range; the body's colour and length show direction
and magnitude of the move. The default chart for daily price data in
finance, and equally usable for any open/high/low/close-shaped series
(sensor readings, auction prices).

Previously rendered via Vega-Lite (a layered ``rule`` + ``bar`` mark,
``vl_convert``); this module now paints both layers by hand -- no Vega,
no matplotlib. Every candle carries a native ``<title>`` tooltip with all
four values.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _svg import svg_open, xml_escape  # noqa: E402

INK = "#1D1D1F"
SECONDARY = "#6E6E73"
BG = "#FFFFFF"
GRIDLINE = "#E5E5EA"
FONT_MONO = "Roboto Mono, ui-monospace, monospace"
COLOR_UP = "#28CD41"
COLOR_DOWN = "#FF3B30"


def _make_demo_data() -> List[Dict[str, Any]]:
    rng = random.Random(3)
    rows: List[Dict[str, Any]] = []
    price = 100.0
    for day in range(1, 21):
        open_p = price
        drift = rng.gauss(0, 2.6)
        close_p = max(1.0, open_p + drift)
        high_p = max(open_p, close_p) + abs(rng.gauss(0, 1.2))
        low_p = min(open_p, close_p) - abs(rng.gauss(0, 1.2))
        rows.append({
            "day": day, "open": round(open_p, 2), "close": round(close_p, 2),
            "high": round(high_p, 2), "low": round(low_p, 2), "up": close_p >= open_p,
        })
        price = close_p
    return rows


DEMO_DATA: List[Dict[str, Any]] = _make_demo_data()


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Daily Price (Open, High, Low, Close)",
    subtitle: str = "20 trading days, synthetic series",
    width: int = 745,
    height: int = 480,
    mode: str = "self-contained",
    accessibility: str = "universal",
) -> str:
    """Assemble the full candlestick chart SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``day``, ``open``, ``close``, ``high``, ``low``
        (numeric) and ``up`` (bool). Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    mode : str, optional
        Forwarded to :func:`_interactive.fullscreen_control`.
    accessibility : str, optional
        Accepted for CLI parity but a documented no-op: up/down is a
        fixed two-colour semantic (green/red), not a re-levelled palette.

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    _ = accessibility
    rows = data if data else DEMO_DATA
    days = [r["day"] for r in rows]
    lows = [float(r["low"]) for r in rows]
    highs = [float(r["high"]) for r in rows]
    v_min, v_max = min(lows), max(highs)
    pad = (v_max - v_min) * 0.08 or 1.0

    plot_x, plot_y = 60.0, 118.0
    right_margin, bottom_reserved = 30.0, 60.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_reserved
    n = len(rows)
    bin_w = plot_w / n if n else plot_w
    body_w = max(3.0, bin_w * 0.5)

    def y_for(v: float) -> float:
        return plot_y + plot_h - (v - (v_min - pad)) / ((v_max + pad) - (v_min - pad)) * plot_h

    parts: List[str] = []
    parts.append(svg_open(width, height, "candle-title", "candle-desc"))
    parts.append(f'<title id="candle-title">{xml_escape(title)}</title>')
    n_up = sum(1 for r in rows if r["up"])
    parts.append(
        f'<desc id="candle-desc">Candlestick chart of {n} periods, {n_up} up and '
        f'{n - n_up} down. Hover or focus a candle for its exact OHLC values.</desc>'
    )
    parts.append(
        "<style>"
        ".candle{transition:opacity .15s ease;}"
        ".candle:hover,.candle:focus{opacity:.72;outline:none;}"
        "@media (prefers-reduced-motion: reduce){.candle{transition:none;}}"
        "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="40" y="46" font-size="24" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(f'<text x="40" y="70" font-size="14" fill="{SECONDARY}">{xml_escape(subtitle)}</text>')

    # ---- y-axis gridlines ----
    y_ticks = 6
    for i in range(y_ticks + 1):
        val = (v_min - pad) + ((v_max + pad) - (v_min - pad)) * i / y_ticks
        ty = y_for(val)
        parts.append(
            f'<line x1="{plot_x:.1f}" y1="{ty:.1f}" x2="{plot_x + plot_w:.1f}" y2="{ty:.1f}" '
            f'stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{plot_x - 10:.1f}" y="{ty + 4:.1f}" font-size="11" font-family="{FONT_MONO}" '
            f'fill="{SECONDARY}" text-anchor="end">{val:.0f}</text>'
        )
    parts.append(
        f'<text x="18" y="{plot_y + plot_h / 2:.1f}" font-size="13" fill="{INK}" '
        f'text-anchor="middle" transform="rotate(-90 18 {plot_y + plot_h / 2:.1f})">Price</text>'
    )

    # ---- candles ----
    for i, r in enumerate(rows):
        cx = plot_x + i * bin_w + bin_w / 2
        color = COLOR_UP if r["up"] else COLOR_DOWN
        y_high, y_low = y_for(float(r["high"])), y_for(float(r["low"]))
        y_open, y_close = y_for(float(r["open"])), y_for(float(r["close"]))
        body_top, body_bottom = min(y_open, y_close), max(y_open, y_close)
        tip = (
            f"Day {r['day']}: open {r['open']:.2f}, high {r['high']:.2f}, "
            f"low {r['low']:.2f}, close {r['close']:.2f}"
        )
        parts.append('<g class="candle" tabindex="0">')
        parts.append(f'<title>{xml_escape(tip)}</title>')
        parts.append(
            f'<line x1="{cx:.1f}" y1="{y_high:.1f}" x2="{cx:.1f}" y2="{y_low:.1f}" '
            f'stroke="{color}" stroke-width="1.5"/>'
        )
        parts.append(
            f'<rect x="{cx - body_w / 2:.1f}" y="{body_top:.1f}" width="{body_w:.1f}" '
            f'height="{max(1.5, body_bottom - body_top):.1f}" fill="{color}"/>'
        )
        parts.append("</g>")

    # ---- x-axis ----
    axis_y = plot_y + plot_h
    parts.append(
        f'<line x1="{plot_x:.1f}" y1="{axis_y:.1f}" x2="{plot_x + plot_w:.1f}" y2="{axis_y:.1f}" '
        f'stroke="{INK}" stroke-width="1.2"/>'
    )
    step = max(1, n // 10)
    for i, d in enumerate(days):
        if i % step != 0 and i != n - 1:
            continue
        tx = plot_x + i * bin_w + bin_w / 2
        parts.append(
            f'<text x="{tx:.1f}" y="{axis_y + 20:.1f}" font-size="11" font-family="{FONT_MONO}" '
            f'fill="{SECONDARY}" text-anchor="middle">{d}</text>'
        )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{axis_y + 42:.1f}" font-size="13" '
        f'fill="{INK}" text-anchor="middle">Day</text>'
    )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_candlestick(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Daily Price (Open, High, Low, Close)",
    subtitle: str = "20 trading days, synthetic series",
    width: int = 745,
    height: int = 480,
    mode: str = "self-contained",
    accessibility: str = "universal",
) -> Path:
    """Render a hand-authored candlestick chart and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``day``, ``open``, ``close``, ``high``, ``low``
        (float) and ``up`` (bool). Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to
        ``assets/svg-examples/candlestick.svg``.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    mode, accessibility : str
        Forwarded to :func:`build_svg`.

    Returns
    -------
    Path
        Absolute path to the written SVG file.

    Examples
    --------
    >>> p = make_candlestick()
    >>> p.exists()
    True
    """
    svg = build_svg(data, title=title, subtitle=subtitle, width=width, height=height,
                     mode=mode, accessibility=accessibility)
    dest = Path(out) if out else svg_example_path(__file__, "candlestick")
    return write_svg(dest, svg)


def main() -> None:
    render_cli(__file__, "candlestick", build_svg, description="Generate an OHLC candlestick chart.")


if __name__ == "__main__":
    main()
