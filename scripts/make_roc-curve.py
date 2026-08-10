#!/usr/bin/env python3
"""
make_roc-curve — a house-styled ROC curve as hand-authored SVG.

Plots a binary classifier's true-positive rate against its false-positive
rate as the decision threshold sweeps from strict to lenient, against the
diagonal a random guesser would trace. The area under the curve (AUC,
shown in the title) condenses the whole curve into one number: 0.5 is
random, 1.0 is perfect separation. The standard chart for reporting a
classifier's discrimination ability independent of any one threshold.

Previously rendered via Vega-Lite (the ROC points computed offline,
``vl_convert``); this module now computes the ROC curve and AUC itself
from raw classifier scores -- sort-and-sweep over unique thresholds,
trapezoidal-rule AUC -- no Vega, no matplotlib, no scikit-learn. Every
point carries a native ``<title>`` tooltip with its threshold and rates.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _svg import svg_open, xml_escape  # noqa: E402
from _style import BG, FONT_MONO, GRIDLINE, INK, SECONDARY  # noqa: E402

COLOR_REF = "#C7C7CC"
COLOR_ROC = "#007AFF"


def _make_demo_data() -> List[Dict[str, Any]]:
    rng = random.Random(27)
    rows: List[Dict[str, Any]] = []
    for _ in range(140):
        rows.append({"score": min(1.0, max(0.0, rng.gauss(0.62, 0.17))), "label": 1})
    for _ in range(140):
        rows.append({"score": min(1.0, max(0.0, rng.gauss(0.36, 0.17))), "label": 0})
    return rows


DEMO_DATA: List[Dict[str, Any]] = _make_demo_data()


def _roc_curve(rows: List[Dict[str, Any]]) -> Tuple[List[Tuple[float, float]], float]:
    """Compute ROC points (FPR, TPR) swept over unique score thresholds, and
    the AUC via the trapezoidal rule."""
    n_pos = sum(1 for r in rows if r["label"] == 1)
    n_neg = sum(1 for r in rows if r["label"] == 0)
    thresholds = sorted({float(r["score"]) for r in rows}, reverse=True)
    points: List[Tuple[float, float]] = [(0.0, 0.0)]
    for t in thresholds:
        tp = sum(1 for r in rows if r["label"] == 1 and float(r["score"]) >= t)
        fp = sum(1 for r in rows if r["label"] == 0 and float(r["score"]) >= t)
        tpr = tp / n_pos if n_pos else 0.0
        fpr = fp / n_neg if n_neg else 0.0
        points.append((fpr, tpr))
    points.append((1.0, 1.0))
    # Trapezoidal AUC over the (already threshold-sorted, monotone-in-FPR-ish) points.
    points_sorted = sorted(set(points))
    auc = 0.0
    for (x0, y0), (x1, y1) in zip(points_sorted, points_sorted[1:]):
        auc += (x1 - x0) * (y0 + y1) / 2.0
    return points, auc


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    width: int = 520,
    height: int = 520,
    mode: str = "self-contained",
    accessibility: str = "universal",
    x_label: str = "False positive rate",
    y_label: str = "True positive rate",
) -> str:
    """Assemble the full ROC curve SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``score`` (numeric, 0..1) and ``label`` (0 or 1).
        Defaults to :data:`DEMO_DATA`.
    width, height : int
        Canvas size in pixels.
    mode : str, optional
        Forwarded to :func:`_interactive.fullscreen_control`.
    accessibility : str, optional
        Accepted for CLI parity but a documented no-op: a single house-
        blue ROC curve, no categorical hues to re-level.
    x_label, y_label : str, optional
        Axis titles. No log-scale option on either axis: both are rates
        bounded to [0, 1] and the curve always passes through exactly
        (0, 0), which a log axis cannot represent (log(0) is undefined).

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    _ = accessibility
    rows = data if data else DEMO_DATA
    points, auc = _roc_curve(rows)
    title = f"ROC Curve — AUC {auc:.2f}"
    subtitle = "True-positive rate vs. false-positive rate across all thresholds"

    plot_x, plot_y = 70.0, 118.0
    right_margin, bottom_reserved = 30.0, 60.0
    size = min(width - plot_x - right_margin, height - plot_y - bottom_reserved)
    plot_w = plot_h = size

    def x_for(v: float) -> float:
        return plot_x + v * plot_w

    def y_for(v: float) -> float:
        return plot_y + plot_h - v * plot_h

    parts: List[str] = []
    parts.append(svg_open(width, height, "roc-title", "roc-desc"))
    parts.append(f'<title id="roc-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="roc-desc">ROC curve over {len(rows)} scored observations, area under '
        f'the curve {auc:.3f}.</desc>'
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="40" y="46" font-size="22" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(f'<text x="40" y="70" font-size="14" fill="{SECONDARY}">{xml_escape(subtitle)}</text>')

    # ---- gridlines ----
    ticks = 5
    for i in range(ticks + 1):
        val = i / ticks
        tx, ty = x_for(val), y_for(val)
        parts.append(f'<line x1="{plot_x:.1f}" y1="{ty:.1f}" x2="{plot_x + plot_w:.1f}" y2="{ty:.1f}" stroke="{GRIDLINE}" stroke-width="1"/>')
        parts.append(f'<line x1="{tx:.1f}" y1="{plot_y:.1f}" x2="{tx:.1f}" y2="{plot_y + plot_h:.1f}" stroke="{GRIDLINE}" stroke-width="1"/>')
        parts.append(
            f'<text x="{plot_x - 10:.1f}" y="{ty + 4:.1f}" font-size="11" font-family="{FONT_MONO}" '
            f'fill="{SECONDARY}" text-anchor="end">{val:.1f}</text>'
        )
        parts.append(
            f'<text x="{tx:.1f}" y="{plot_y + plot_h + 20:.1f}" font-size="11" font-family="{FONT_MONO}" '
            f'fill="{SECONDARY}" text-anchor="middle">{val:.1f}</text>'
        )
    parts.append(
        f'<text x="20" y="{plot_y + plot_h / 2:.1f}" font-size="13" fill="{INK}" '
        f'text-anchor="middle" transform="rotate(-90 20 {plot_y + plot_h / 2:.1f})">{xml_escape(y_label)}</text>'
    )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{plot_y + plot_h + 42:.1f}" font-size="13" '
        f'fill="{INK}" text-anchor="middle">{xml_escape(x_label)}</text>'
    )

    # ---- diagonal reference ----
    parts.append(
        f'<line x1="{x_for(0.0):.1f}" y1="{y_for(0.0):.1f}" x2="{x_for(1.0):.1f}" y2="{y_for(1.0):.1f}" '
        f'stroke="{COLOR_REF}" stroke-width="1.5" stroke-dasharray="5 3"/>'
    )

    # ---- ROC curve ----
    path_pts = [(x_for(fpr), y_for(tpr)) for fpr, tpr in points]
    path_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in path_pts)
    tip = f"ROC curve, AUC = {auc:.3f}"
    parts.append(
        f'<path tabindex="0" d="{path_d}" fill="none" stroke="{COLOR_ROC}" stroke-width="2.5">'
        f'<title>{xml_escape(tip)}</title></path>'
    )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_roc_curve(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: Optional[str] = None,
    width: int = 520,
    height: int = 520,
    mode: str = "self-contained",
    accessibility: str = "universal",
    x_label: str = "False positive rate",
    y_label: str = "True positive rate",
) -> Path:
    """Render a hand-authored ROC curve and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``score`` (float, 0..1) and ``label`` (0 or 1).
        Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/roc-curve.svg``.
    title : str or None
        Accepted for contract parity with every other ``make_<kind>()``;
        the headline is always the data-derived "ROC Curve — AUC x.xx",
        so an explicit override is intentionally not threaded through.
    width, height : int
        Canvas size in pixels.
    mode, accessibility : str
        Forwarded to :func:`build_svg`.
    x_label, y_label : str, optional
        Axis titles. Forwarded to :func:`build_svg`.

    Returns
    -------
    Path
        Absolute path to the written SVG file.

    Examples
    --------
    >>> p = make_roc_curve()
    >>> p.exists()
    True
    """
    _ = title
    svg = build_svg(data, width=width, height=height, mode=mode, accessibility=accessibility,
                     x_label=x_label, y_label=y_label)
    dest = Path(out) if out else svg_example_path(__file__, "roc-curve")
    return write_svg(dest, svg)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "roc-curve", build_svg, description="Generate a ROC curve.")


if __name__ == "__main__":
    main()
