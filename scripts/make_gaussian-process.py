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

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _svg import svg_open, xml_escape  # noqa: E402
from _style import BG, FONT_MONO, GRIDLINE, INK, SECONDARY  # noqa: E402

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

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    _ = accessibility
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
    parts.append(svg_open(width, height, "gp-title", "gp-desc"))
    parts.append(f'<title id="gp-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="gp-desc">Gaussian process posterior fit to {len(rows)} observed points. '
        f'Shaded band is the 95% credible interval; three faint lines are posterior samples.</desc>'
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="40" y="46" font-size="22" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(f'<text x="40" y="70" font-size="14" fill="{SECONDARY}">{xml_escape(subtitle)}</text>')

    # ---- gridlines ----
    y_ticks = 5
    for i in range(y_ticks + 1):
        val = (y_min - pad) + ((y_max + pad) - (y_min - pad)) * i / y_ticks
        ty = y_for(val)
        parts.append(
            f'<line x1="{plot_x:.1f}" y1="{ty:.1f}" x2="{plot_x + plot_w:.1f}" y2="{ty:.1f}" '
            f'stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{plot_x - 10:.1f}" y="{ty + 4:.1f}" font-size="11" font-family="{FONT_MONO}" '
            f'fill="{SECONDARY}" text-anchor="end">{val:.1f}</text>'
        )
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
            f'<circle tabindex="0" cx="{cx:.1f}" cy="{cy:.1f}" r="5" fill="{COLOR_POINT}" '
            f'stroke="{BG}" stroke-width="1.5"><title>{xml_escape(tip)}</title></circle>'
        )

    # ---- x-axis ----
    axis_y = plot_y + plot_h
    parts.append(
        f'<line x1="{plot_x:.1f}" y1="{axis_y:.1f}" x2="{plot_x + plot_w:.1f}" y2="{axis_y:.1f}" '
        f'stroke="{INK}" stroke-width="1.2"/>'
    )
    x_ticks = 8
    for i in range(x_ticks + 1):
        val = x_lo + (x_hi - x_lo) * i / x_ticks
        tx = x_for(val)
        parts.append(
            f'<text x="{tx:.1f}" y="{axis_y + 20:.1f}" font-size="11" font-family="{FONT_MONO}" '
            f'fill="{SECONDARY}" text-anchor="middle">{val:.1f}</text>'
        )
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
                     mode=mode, accessibility=accessibility)
    dest = Path(out) if out else svg_example_path(__file__, "gaussian-process")
    return write_svg(dest, svg)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "gaussian-process", build_svg, description="Generate a Gaussian-process regression figure.")


if __name__ == "__main__":
    main()
