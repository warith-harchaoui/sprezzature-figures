#!/usr/bin/env python3
"""
make_violin — a house-styled violin plot as hand-authored SVG.

Mirrors a Gaussian kernel density estimate left and right of a central
axis, one violin per category, so the full shape of each group's
distribution, not just its median and spread, is visible side by
side: bimodal groups show two bulges, skewed groups show an asymmetric
silhouette, a box plot alone would hide both. A median tick marks the
centre of each violin. Typical uses: comparing distribution shape across
experiment arms, cohorts, or any small set of groups where shape itself
carries information.

Previously rendered via Vega-Lite (a column-faceted, horizontally
mirrored ``area`` mark over pre-computed KDE points, ``vl_convert``);
this module now computes the Gaussian KDE itself and paints each
mirrored violin by hand: no Vega, no matplotlib, no scipy. Every violin
carries a native ``<title>`` tooltip with its median and spread.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _scale import nice_ticks_range  # noqa: E402
from _style import BG, GRIDLINE, INK, SECONDARY, cycle_hues  # noqa: E402
from _svg import svg_open, tooltip_bubble, xml_escape  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402


GROUPS = ["A", "B", "C"]


def _make_demo_data() -> List[Dict[str, Any]]:
    rng = random.Random(43)
    rows: List[Dict[str, Any]] = []
    for _ in range(70):
        rows.append({"g": "A", "y": round(rng.gauss(50.0, 6.0), 2)})
    for _ in range(70):
        # Widest spread, and a touch bimodal.
        base = rng.gauss(50.0, 13.0)
        if rng.random() < 0.35:
            base += rng.choice([-14.0, 14.0])
        rows.append({"g": "B", "y": round(base, 2)})
    for _ in range(70):
        rows.append({"g": "C", "y": round(rng.gauss(55.0, 4.5), 2)})
    return rows


DEMO_DATA: List[Dict[str, Any]] = _make_demo_data()


def _silverman_bandwidth(samples: List[float]) -> float:
    n = len(samples)
    mean = sum(samples) / n
    std = math.sqrt(sum((s - mean) ** 2 for s in samples) / max(1, n - 1)) or 1.0
    return 0.9 * std * n ** (-1.0 / 5.0)


def _gaussian_kde(samples: List[float], x_eval: List[float], bandwidth: float) -> List[float]:
    n = len(samples)
    norm = 1.0 / (n * bandwidth * math.sqrt(2.0 * math.pi))
    return [norm * sum(math.exp(-0.5 * ((x - s) / bandwidth) ** 2) for s in samples) for x in x_eval]


def _group_colors(
    groups: List[str], accessibility: str = "universal", theme: str = "corporate"
) -> Dict[str, str]:
    return cycle_hues(groups, accessibility, theme=theme)


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Group B Has the Widest Spread",
    subtitle: str = "Distribution shape by group (mirrored kernel density)",
    width: int = 620,
    height: int = 480,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full violin plot SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``g`` (str) and ``y`` (numeric). Defaults to
        :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    mode, accessibility : str, optional
        Forwarded to :func:`_interactive.fullscreen_control` /
        :func:`_style.load_palette`.
    theme : str, optional
        Visual theme: ``"corporate"`` (default, Roboto -- byte-identical to
        the pre-theme render) or ``"academic"`` (LaTeX-style Latin Modern).
        See :func:`sprezzature_figures.fonts.chrome_stack_for_theme`.

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    mono_family = mono_stack_for_theme(theme)
    rows = data if data else DEMO_DATA
    seen_groups: List[str] = []
    for r in rows:
        if r["g"] not in seen_groups:
            seen_groups.append(r["g"])
    groups = [g for g in GROUPS if g in seen_groups] + [g for g in seen_groups if g not in GROUPS]
    colors = _group_colors(groups, accessibility, theme=theme)
    all_vals = [float(r["y"]) for r in rows]
    raw_y_min, raw_y_max = min(all_vals), max(all_vals)
    y_pad = (raw_y_max - raw_y_min) * 0.08 or 1.0
    y_gridline_vals = nice_ticks_range(raw_y_min - y_pad, raw_y_max + y_pad, 5)
    y_min, y_max = y_gridline_vals[0], y_gridline_vals[-1]

    plot_x, plot_y = 60.0, 118.0
    right_margin, bottom_reserved = 30.0, 60.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_reserved
    n = len(groups)
    bin_w = plot_w / n if n else plot_w
    violin_half_w = bin_w * 0.38

    def y_for(v: float) -> float:
        return plot_y + plot_h - (v - y_min) / ((y_max - y_min) or 1.0) * plot_h

    parts: List[str] = []
    parts.append(svg_open(width, height, "vio-title", "vio-desc", font_family=chrome_stack_for_theme(theme)))
    parts.append(f'<title id="vio-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="vio-desc">Violin plot of {n} groups, values ranging {y_min:.0f} to '
        f'{y_max:.0f}. Hover or focus a violin for its exact median and spread.</desc>'
    )
    parts.append(
        "<style>"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        ".hit:hover+.tip,.hit:focus+.tip{opacity:1}"
        "@media (prefers-reduced-motion: reduce){.tip{transition:none}}"
        "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="40" y="46" font-size="22" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(f'<text x="40" y="70" font-size="14" fill="{SECONDARY}">{xml_escape(subtitle)}</text>')

    # ---- gridlines ----
    for val in y_gridline_vals:
        ty = y_for(val)
        parts.append(
            f'<line x1="{plot_x:.1f}" y1="{ty:.1f}" x2="{plot_x + plot_w:.1f}" y2="{ty:.1f}" '
            f'stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{plot_x - 10:.1f}" y="{ty + 4:.1f}" font-size="11" font-family="{mono_family}" '
            f'fill="{SECONDARY}" text-anchor="end">{val:.0f}</text>'
        )
    parts.append(
        f'<text x="18" y="{plot_y + plot_h / 2:.1f}" font-size="13" fill="{INK}" '
        f'text-anchor="middle" transform="rotate(-90 18 {plot_y + plot_h / 2:.1f})">Value</text>'
    )

    # ---- violins ----
    for gi, g in enumerate(groups):
        samples = sorted(float(r["y"]) for r in rows if r["g"] == g)
        if not samples:
            continue
        bandwidth = _silverman_bandwidth(samples)
        s_min, s_max = samples[0], samples[-1]
        span = (s_max - s_min) or 1.0
        n_points = 100
        y_eval = [s_min - span * 0.15 + i * (span * 1.3) / (n_points - 1) for i in range(n_points)]
        density = _gaussian_kde(samples, y_eval, bandwidth)
        peak = max(density) or 1.0

        cx = plot_x + gi * bin_w + bin_w / 2
        color = colors.get(g, "#8E8E93")
        right_pts = [(cx + (d / peak) * violin_half_w, y_for(y)) for y, d in zip(y_eval, density)]
        left_pts = [(cx - (d / peak) * violin_half_w, y_for(y)) for y, d in zip(y_eval, density)]
        path_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in right_pts)
        path_d += " L " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in reversed(left_pts)) + " Z"

        median = samples[len(samples) // 2]
        mean = sum(samples) / len(samples)
        std = math.sqrt(sum((s - mean) ** 2 for s in samples) / max(1, len(samples) - 1))
        tip = f"Group {g}: median {median:.1f}, std {std:.1f}, n={len(samples)}"
        parts.append(
            f'<path class="hit" tabindex="0" d="{path_d}" fill="{color}" fill-opacity="0.75" '
            f'stroke="{color}" stroke-width="1" role="img" aria-label="{xml_escape(tip)}"/>'
        )
        parts.append(
            tooltip_bubble(
                cx, y_for(s_max) - 16,
                [f"Group {g}", f"median {median:.1f}", f"std {std:.1f}, n={len(samples)}"],
                anchor="middle", canvas_w=width, canvas_h=height,
                ink=INK, secondary=SECONDARY, border=GRIDLINE,
            )
        )
        my = y_for(median)
        parts.append(
            f'<line x1="{cx - violin_half_w * 0.5:.1f}" y1="{my:.1f}" x2="{cx + violin_half_w * 0.5:.1f}" '
            f'y2="{my:.1f}" stroke="{BG}" stroke-width="2"/>'
        )
        parts.append(
            f'<text x="{cx:.1f}" y="{plot_y + plot_h + 20:.1f}" font-size="13" fill="{INK}" '
            f'text-anchor="middle">{xml_escape(g)}</text>'
        )

    axis_y = plot_y + plot_h
    parts.append(
        f'<line x1="{plot_x:.1f}" y1="{axis_y:.1f}" x2="{plot_x + plot_w:.1f}" y2="{axis_y:.1f}" '
        f'stroke="{INK}" stroke-width="1.2"/>'
    )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{axis_y + 42:.1f}" font-size="13" '
        f'fill="{INK}" text-anchor="middle">Group</text>'
    )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_violin(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Group B Has the Widest Spread",
    subtitle: str = "Distribution shape by group (mirrored kernel density)",
    width: int = 620,
    height: int = 480,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render a hand-authored violin plot and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``g`` (str) and ``y`` (float). Defaults to
        DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/violin.svg``.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    mode, accessibility : str
        Forwarded to :func:`build_svg`.
    theme : str, optional
        Visual theme. Forwarded to :func:`build_svg`.

    Returns
    -------
    Path
        Absolute path to the written SVG file.

    Examples
    --------
    >>> p = make_violin()
    >>> p.exists()
    True
    """
    svg = build_svg(data, title=title, subtitle=subtitle, width=width, height=height,
                     mode=mode, accessibility=accessibility, theme=theme)
    dest = Path(out) if out else svg_example_path(__file__, "violin")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "violin", build_svg, description="Generate a violin plot.")


if __name__ == "__main__":
    main()
