#!/usr/bin/env python3
"""
make_gaussian-process — a house-styled Gaussian-process regression figure as hand-authored SVG.

Fits a Gaussian process (RBF kernel) to a handful of observed points and
plots the posterior: a shaded 95% credible band, the posterior mean line,
a few posterior sample functions drawn faintly to make "uncertainty" a
tangible spread of plausible curves rather than an abstract band, and the
observed points themselves. The classic figure for teaching or auditing
Bayesian nonparametric regression: wide band and diverging samples far
from data, narrow band and converging samples near it.

Previously rendered via Vega-Lite (a four-layer area + line + line + point
spec whose posterior was computed offline, ``vl_convert``); this module
now runs the GP regression itself -- RBF kernel, Cholesky-based posterior
mean/covariance, sampling via a Cholesky factor of the posterior
covariance, all via numpy (already a core dependency) -- no Vega, no
matplotlib, no scikit-learn. The mean curve carries a native ``<title>``
tooltip.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _svg import svg_open, tooltip_bubble, xml_escape  # noqa: E402
from _style import BG, GRIDLINE, INK, SECONDARY  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402


def _nice_step(span: float, target_ticks: int = 5) -> float:
    """Pick a 1/2/5-times-a-power-of-ten step so ``span / step`` ~= `target_ticks`.

    Both axes here are data-driven windows that cross zero (x is roughly
    symmetric around 0, y is a padded posterior range), so `_scale.nice_ticks`
    (zero-anchored, rounds the ceiling) doesn't fit. Rounding just the step
    (Heckbert 1990) turns a naive `span / n` divide -- which used to print
    labels like `-3.8`/`-1.2`/`1.2`/`3.8` on x and `-1.5`/`-0.5`/`1.6`/`2.6`
    on y -- into round, scannable values.
    """
    if span <= 0:
        return 1.0
    raw_step = span / target_ticks
    exponent = math.floor(math.log10(raw_step))
    fraction = raw_step / (10.0**exponent)
    nice_fraction = 1.0 if fraction < 1.5 else 2.0 if fraction < 3 else 5.0 if fraction < 7 else 10.0
    return nice_fraction * (10.0**exponent)

COLOR_BAND = "#3E9BFF"
COLOR_SAMPLE = "#9CC7FF"
COLOR_MEAN = "#007AFF"
COLOR_POINT = "#1D1D1F"

DEMO_DATA: List[Dict[str, Any]] = [
    {"x": -4.0, "y": 0.93}, {"x": -3.0, "y": -0.19}, {"x": -1.5, "y": -0.99},
    {"x": 0.0, "y": 0.05}, {"x": 1.5, "y": 0.97}, {"x": 3.5, "y": -0.55},
]


def _rbf_kernel(a: np.ndarray, b: np.ndarray, length_scale: float, sigma_f: float) -> np.ndarray:
    """Squared-exponential (RBF) covariance between every pair in ``a`` and ``b``."""
    sq_dist = (a[:, None] - b[None, :]) ** 2
    return sigma_f**2 * np.exp(-0.5 * sq_dist / length_scale**2)


def _gp_posterior(
    x_train: np.ndarray, y_train: np.ndarray, x_test: np.ndarray,
    length_scale: float = 1.1, sigma_f: float = 1.0, sigma_n: float = 0.08,
) -> Tuple[np.ndarray, np.ndarray]:
    """Return ``(mean, covariance)`` of the GP posterior at ``x_test``."""
    k = _rbf_kernel(x_train, x_train, length_scale, sigma_f) + sigma_n**2 * np.eye(len(x_train))
    k_s = _rbf_kernel(x_train, x_test, length_scale, sigma_f)
    k_ss = _rbf_kernel(x_test, x_test, length_scale, sigma_f) + 1e-8 * np.eye(len(x_test))
    k_inv_y = np.linalg.solve(k, y_train)
    mean = k_s.T @ k_inv_y
    k_inv_ks = np.linalg.solve(k, k_s)
    cov = k_ss - k_s.T @ k_inv_ks
    return mean, cov


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "The Model Is Unsure Between Samples",
    subtitle: str = "Gaussian-process posterior: mean and 95% band, 3 sample draws",
    width: int = 745,
    height: int = 480,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full Gaussian-process figure SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Observed points, rows with keys ``x``, ``y`` (numeric). Defaults
        to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    mode : str, optional
        Forwarded to :func:`_interactive.fullscreen_control`.
    accessibility : str, optional
        Accepted for CLI parity but a documented no-op: fixed house-blue
        band/mean/sample semantic, no categorical hues to re-level.
    theme : str, optional
        Visual theme: ``"corporate"`` (default, Roboto -- byte-identical to
        the pre-theme render) or ``"academic"`` (LaTeX-style Latin Modern).
        See :func:`sprezzature_figures.fonts.chrome_stack_for_theme`.

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    _ = accessibility
    mono_family = mono_stack_for_theme(theme)
    rows = data if data else DEMO_DATA
    x_train = np.array([float(r["x"]) for r in rows])
    y_train = np.array([float(r["y"]) for r in rows])

    x_lo, x_hi = min(-5.0, x_train.min() - 1.0), max(5.0, x_train.max() + 1.0)
    x_test = np.linspace(x_lo, x_hi, 80)
    mean, cov = _gp_posterior(x_train, y_train, x_test)
    std = np.sqrt(np.clip(np.diag(cov), 0.0, None))
    lo, hi = mean - 1.96 * std, mean + 1.96 * std

    rng = np.random.default_rng(4)
    jitter = 1e-6 * np.eye(len(x_test))
    chol = np.linalg.cholesky(cov + jitter)
    n_samples = 3
    samples = mean[:, None] + chol @ rng.standard_normal((len(x_test), n_samples))

    y_min = min(lo.min(), y_train.min(), samples.min())
    y_max = max(hi.max(), y_train.max(), samples.max())
    pad = (y_max - y_min) * 0.1 or 1.0

    plot_x, plot_y = 60.0, 118.0
    right_margin, bottom_reserved = 30.0, 60.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_reserved

    def x_for(v: float) -> float:
        return plot_x + (v - x_lo) / (x_hi - x_lo) * plot_w

    def y_for(v: float) -> float:
        return plot_y + plot_h - (v - (y_min - pad)) / ((y_max + pad) - (y_min - pad)) * plot_h

    parts: List[str] = []
    parts.append(svg_open(width, height, "gp-title", "gp-desc", font_family=chrome_stack_for_theme(theme)))
    parts.append(f'<title id="gp-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="gp-desc">Gaussian process posterior fit to {len(rows)} observed points. '
        f'Shaded band is the 95% credible interval; three faint lines are posterior samples.</desc>'
    )
    parts.append(
        "<style>"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        ".hit:hover+.tip,.hit:focus+.tip{opacity:1}"
        "@media (prefers-reduced-motion:reduce){.tip{transition:none}}"
        "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="40" y="46" font-size="22" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(f'<text x="40" y="70" font-size="14" fill="{SECONDARY}">{xml_escape(subtitle)}</text>')

    # ---- gridlines (round "nice" steps, not a naive 5-way split) ----
    y_axis_lo, y_axis_hi = y_min - pad, y_max + pad
    y_step = _nice_step(y_axis_hi - y_axis_lo, 5)
    val = math.floor(y_axis_lo / y_step) * y_step
    while val <= y_axis_hi + 1e-9:
        if val >= y_axis_lo - 1e-9:
            ty = y_for(val)
            parts.append(
                f'<line x1="{plot_x:.1f}" y1="{ty:.1f}" x2="{plot_x + plot_w:.1f}" y2="{ty:.1f}" '
                f'stroke="{GRIDLINE}" stroke-width="1"/>'
            )
            parts.append(
                f'<text x="{plot_x - 10:.1f}" y="{ty + 4:.1f}" font-size="11" font-family="{mono_family}" '
                f'fill="{SECONDARY}" text-anchor="end">{val:.1f}</text>'
            )
        val += y_step
    parts.append(
        f'<text x="18" y="{plot_y + plot_h / 2:.1f}" font-size="13" fill="{INK}" '
        f'text-anchor="middle" transform="rotate(-90 18 {plot_y + plot_h / 2:.1f})">f(x)</text>'
    )

    # ---- 95% credible band ----
    top_pts = [(x_for(x), y_for(v)) for x, v in zip(x_test, hi)]
    bot_pts = [(x_for(x), y_for(v)) for x, v in zip(x_test, lo)]
    band_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in top_pts)
    band_d += " L " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in reversed(bot_pts)) + " Z"
    parts.append(f'<path d="{band_d}" fill="{COLOR_BAND}" fill-opacity="0.22"/>')

    # ---- posterior sample paths ----
    for s in range(n_samples):
        pts = [(x_for(x), y_for(v)) for x, v in zip(x_test, samples[:, s])]
        path_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        parts.append(f'<path d="{path_d}" fill="none" stroke="{COLOR_SAMPLE}" stroke-width="1" opacity="0.6"/>')

    # ---- posterior mean ----
    mean_pts = [(x_for(x), y_for(v)) for x, v in zip(x_test, mean)]
    mean_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in mean_pts)
    tip = f"GP posterior mean, {len(rows)} observations, RBF kernel"
    parts.append(
        f'<path tabindex="0" d="{mean_d}" fill="none" stroke="{COLOR_MEAN}" stroke-width="2.5">'
        f'<title>{xml_escape(tip)}</title></path>'
    )

    # ---- observed points ----
    for r in rows:
        cx, cy = x_for(float(r["x"])), y_for(float(r["y"]))
        tip = f"Observed: x={float(r['x']):.2f}, y={float(r['y']):.2f}"
        parts.append(
            f'<circle class="hit" tabindex="0" cx="{cx:.1f}" cy="{cy:.1f}" r="5" fill="{COLOR_POINT}" '
            f'stroke="{BG}" stroke-width="1.5"><title>{xml_escape(tip)}</title></circle>'
        )
        parts.append(
            tooltip_bubble(
                cx, cy - 16,
                [f"x = {float(r['x']):.2f}", f"y = {float(r['y']):.2f}", "observed point"],
                anchor="middle", canvas_w=width, canvas_h=height,
                ink=INK, secondary=SECONDARY, border=GRIDLINE,
            )
        )

    # ---- x-axis ----
    axis_y = plot_y + plot_h
    parts.append(
        f'<line x1="{plot_x:.1f}" y1="{axis_y:.1f}" x2="{plot_x + plot_w:.1f}" y2="{axis_y:.1f}" '
        f'stroke="{INK}" stroke-width="1.2"/>'
    )
    x_step = _nice_step(x_hi - x_lo, 8)
    val = math.floor(x_lo / x_step) * x_step
    while val <= x_hi + 1e-9:
        if val >= x_lo - 1e-9:
            tx = x_for(val)
            parts.append(
                f'<text x="{tx:.1f}" y="{axis_y + 20:.1f}" font-size="11" font-family="{mono_family}" '
                f'fill="{SECONDARY}" text-anchor="middle">{val:.1f}</text>'
            )
        val += x_step
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{axis_y + 42:.1f}" font-size="13" '
        f'fill="{INK}" text-anchor="middle">x</text>'
    )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_gaussian_process(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "The Model Is Unsure Between Samples",
    subtitle: str = "Gaussian-process posterior: mean and 95% band, 3 sample draws",
    width: int = 745,
    height: int = 480,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render a hand-authored Gaussian-process figure and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Observed points, rows with keys ``x``, ``y`` (float). Defaults to
        DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to
        ``assets/svg-examples/gaussian-process.svg``.
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
    >>> p = make_gaussian_process()
    >>> p.exists()
    True
    """
    svg = build_svg(data, title=title, subtitle=subtitle, width=width, height=height,
                     mode=mode, accessibility=accessibility, theme=theme)
    dest = Path(out) if out else svg_example_path(__file__, "gaussian-process")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "gaussian-process", build_svg, description="Generate a Gaussian-process regression figure.")


if __name__ == "__main__":
    main()
