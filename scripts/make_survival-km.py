#!/usr/bin/env python3
"""
make_survival-km — a house-styled Kaplan-Meier survival curve as hand-authored SVG.

Estimates the probability of "surviving" (not yet experiencing the event
of interest) past each point in time from a sample of possibly-censored
durations, plotted as a step-down curve with a shaded confidence band and
small tick marks where a subject was censored (left the study before the
event, without it happening). Comparing two arms' curves -- which drops
faster, whether the bands overlap -- is the core visual of clinical-trial
and reliability-engineering reporting.

Previously rendered via Vega-Lite (the estimator computed offline, a
layered step-after ``area`` + ``line``, ``vl_convert``); this module now
computes the Kaplan-Meier estimator itself -- the product-limit formula
for the survival function, Greenwood's formula for its variance -- and
paints both layers plus censoring ticks by hand. No Vega, no matplotlib,
no lifelines. The curve carries a native ``<title>`` tooltip.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _style import BG, GRIDLINE, INK, SECONDARY, cycle_hues  # noqa: E402
from _svg import svg_open, tooltip_bubble, xml_escape  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402


ARMS = ["Treatment", "Control"]
FOLLOW_UP_MAX = 60.0


def _make_demo_data() -> List[Dict[str, Any]]:
    """Synthesise two-arm survival data with both kinds of censoring.

    Every real KM dataset has two independent censoring mechanisms, and the
    demo carries both so the "censoring ticks" the subtitle promises are
    actually visible rather than only existing in principle:

    - **Administrative** censoring: a subject who is still event-free when
      the study ends (``t >= FOLLOW_UP_MAX``) is censored at that boundary.
      Every censored subject landing at the exact same follow-up-max instant
      piles every tick on top of the curve's own terminal point, at the very
      edge of the plot -- indistinguishable from "the line stopped here".
    - **Loss to follow-up**: a subject who withdraws, moves away, or is
      otherwise lost to observation *before* either their event or the study
      end -- independent of the event process, the textbook mechanism KM is
      built to handle. Scattered through the middle of the timeline, these
      are what make a censoring tick actually read as a tick.
    """
    rng = random.Random(37)
    mean_survival = {"Treatment": 42.0, "Control": 24.0}
    # Probability a subject is lost to follow-up (independent of their event
    # time) rather than observed all the way to their event or study end.
    loss_to_follow_up = 0.12
    rows: List[Dict[str, Any]] = []
    for arm in ARMS:
        for _ in range(45):
            t = rng.expovariate(1.0 / mean_survival[arm])
            if t >= FOLLOW_UP_MAX:
                rows.append({"arm": arm, "t": round(FOLLOW_UP_MAX, 1), "event": False})
            elif rng.random() < loss_to_follow_up:
                # Withdrawn at a uniformly random point before their would-be
                # event, so censoring ticks land mid-timeline, not just at
                # the boundary.
                t_censor = rng.uniform(0.0, t)
                rows.append({"arm": arm, "t": round(t_censor, 1), "event": False})
            else:
                rows.append({"arm": arm, "t": round(t, 1), "event": True})
    return rows


DEMO_DATA: List[Dict[str, Any]] = _make_demo_data()


def _km_estimate(rows: List[Dict[str, Any]]) -> Tuple[List[Tuple[float, float, float, float]], List[float]]:
    """Kaplan-Meier product-limit estimator with a Greenwood-formula 95% band.

    Returns ``(curve, censor_times)`` where ``curve`` is a list of
    ``(t, s, lo, hi)`` steps (including the ``t=0, s=1`` start) and
    ``censor_times`` is every censored duration, for tick marks.
    """
    event_times = sorted({r["t"] for r in rows if r["event"]})
    censor_times = [r["t"] for r in rows if not r["event"]]
    s = 1.0
    var_sum = 0.0
    curve: List[Tuple[float, float, float, float]] = [(0.0, 1.0, 1.0, 1.0)]
    for t in event_times:
        n_at_risk = sum(1 for r in rows if r["t"] >= t)
        d_events = sum(1 for r in rows if r["t"] == t and r["event"])
        if n_at_risk > 0 and d_events > 0:
            s *= 1.0 - d_events / n_at_risk
            if n_at_risk > d_events:
                var_sum += d_events / (n_at_risk * (n_at_risk - d_events))
        se = s * math.sqrt(var_sum) if var_sum > 0 else 0.0
        lo, hi = max(0.0, s - 1.96 * se), min(1.0, s + 1.96 * se)
        curve.append((t, s, lo, hi))
    return curve, censor_times


def _survival_at(curve: List[Tuple[float, float, float, float]], t: float) -> float:
    s = 1.0
    for ct, cs, _, _ in curve:
        if ct <= t:
            s = cs
        else:
            break
    return s


def _arm_colors(
    arms: List[str], accessibility: str = "universal", theme: str = "corporate"
) -> Dict[str, str]:
    return cycle_hues(arms, accessibility, theme=theme)


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Kaplan-Meier Survival",
    subtitle: str = "Estimated survival probability by arm, with 95% confidence band and censoring ticks",
    width: int = 745,
    height: int = 480,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full Kaplan-Meier survival curve SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``arm`` (str), ``t`` (numeric duration), ``event``
        (bool; True if the event occurred, False if censored). Defaults
        to :data:`DEMO_DATA`.
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
    seen_arms: List[str] = []
    for r in rows:
        if r["arm"] not in seen_arms:
            seen_arms.append(r["arm"])
    arms = [a for a in ARMS if a in seen_arms] + [a for a in seen_arms if a not in ARMS]
    colors = _arm_colors(arms, accessibility, theme=theme)
    t_max = max(float(r["t"]) for r in rows) if rows else 1.0

    plot_x, plot_y = 60.0, 150.0
    right_margin, bottom_reserved = 30.0, 60.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_reserved

    def x_for(v: float) -> float:
        return plot_x + v / t_max * plot_w

    def y_for(v: float) -> float:
        return plot_y + plot_h - v * plot_h

    parts: List[str] = []
    parts.append(svg_open(width, height, "km-title", "km-desc", font_family=chrome_stack_for_theme(theme)))
    parts.append(f'<title id="km-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="km-desc">Kaplan-Meier survival curves for {len(arms)} arms over '
        f'{t_max:.0f} time units, with 95% confidence bands.</desc>'
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
        f'<text x="40" y="46" font-size="24" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(f'<text x="40" y="70" font-size="14" fill="{SECONDARY}">{xml_escape(subtitle)}</text>')

    # ---- legend ----
    lx, ly = 40.0, 100.0
    cursor = lx
    for a in arms:
        parts.append(f'<rect x="{cursor:.1f}" y="{ly - 12:.1f}" width="14" height="14" rx="3" fill="{colors.get(a, "#8E8E93")}"/>')
        parts.append(f'<text x="{cursor + 20:.1f}" y="{ly:.1f}" font-size="12" fill="{INK}">{xml_escape(a)}</text>')
        cursor += 20 + 7.0 * len(a) + 22

    # ---- gridlines ----
    for i in range(5):
        frac = i / 4.0
        ty = y_for(frac)
        parts.append(
            f'<line x1="{plot_x:.1f}" y1="{ty:.1f}" x2="{plot_x + plot_w:.1f}" y2="{ty:.1f}" '
            f'stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{plot_x - 10:.1f}" y="{ty + 4:.1f}" font-size="11" font-family="{mono_family}" '
            f'fill="{SECONDARY}" text-anchor="end">{frac * 100:.0f}%</text>'
        )
    parts.append(
        f'<text x="18" y="{plot_y + plot_h / 2:.1f}" font-size="13" fill="{INK}" '
        f'text-anchor="middle" transform="rotate(-90 18 {plot_y + plot_h / 2:.1f})">Survival</text>'
    )

    # ---- KM curves per arm ----
    for a in arms:
        arm_rows = [r for r in rows if r["arm"] == a]
        curve, censor_times = _km_estimate(arm_rows)
        color = colors.get(a, "#8E8E93")

        # Step-after band + line paths.
        top_pts: List[Tuple[float, float]] = []
        bot_pts: List[Tuple[float, float]] = []
        line_pts: List[Tuple[float, float]] = []
        for t, s, lo, hi in curve:
            x = x_for(t)
            if top_pts:
                top_pts.append((x, top_pts[-1][1]))
                bot_pts.append((x, bot_pts[-1][1]))
                line_pts.append((x, line_pts[-1][1]))
            top_pts.append((x, y_for(hi)))
            bot_pts.append((x, y_for(lo)))
            line_pts.append((x, y_for(s)))
        top_pts.append((x_for(t_max), top_pts[-1][1]))
        bot_pts.append((x_for(t_max), bot_pts[-1][1]))
        line_pts.append((x_for(t_max), line_pts[-1][1]))

        band_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in top_pts)
        band_d += " L " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in reversed(bot_pts)) + " Z"
        parts.append(f'<path d="{band_d}" fill="{color}" fill-opacity="0.14"/>')

        line_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in line_pts)
        final_s = curve[-1][1]
        n_events = sum(1 for r in arm_rows if r["event"])
        n_censored = len(arm_rows) - n_events
        tip = f"{a}: {final_s * 100:.0f}% surviving at {t_max:.0f} time units"
        parts.append(
            f'<path class="hit" tabindex="0" d="{line_d}" fill="none" stroke="{color}" '
            f'stroke-width="2.5" role="img" aria-label="{xml_escape(tip)}"/>'
        )
        parts.append(
            tooltip_bubble(
                x_for(t_max), y_for(final_s) - 16,
                [a, f"{final_s * 100:.0f}% surviving at {t_max:.0f} units",
                 f"{n_events} events · {n_censored} censored"],
                anchor="end", canvas_w=width, canvas_h=height,
                ink=INK, secondary=SECONDARY, border=GRIDLINE,
            )
        )

        # Censoring ticks.
        for ct in censor_times:
            s_at = _survival_at(curve, ct)
            cx, cy = x_for(ct), y_for(s_at)
            parts.append(
                f'<line x1="{cx:.1f}" y1="{cy - 5:.1f}" x2="{cx:.1f}" y2="{cy + 5:.1f}" '
                f'stroke="{color}" stroke-width="1.5"/>'
            )

    # ---- x-axis ----
    axis_y = plot_y + plot_h
    parts.append(
        f'<line x1="{plot_x:.1f}" y1="{axis_y:.1f}" x2="{plot_x + plot_w:.1f}" y2="{axis_y:.1f}" '
        f'stroke="{INK}" stroke-width="1.2"/>'
    )
    x_ticks = 6
    for i in range(x_ticks + 1):
        val = t_max * i / x_ticks
        tx = x_for(val)
        parts.append(
            f'<text x="{tx:.1f}" y="{axis_y + 20:.1f}" font-size="11" font-family="{mono_family}" '
            f'fill="{SECONDARY}" text-anchor="middle">{val:.0f}</text>'
        )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{axis_y + 42:.1f}" font-size="13" '
        f'fill="{INK}" text-anchor="middle">Months</text>'
    )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_survival_km(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Kaplan-Meier Survival",
    subtitle: str = "Estimated survival probability by arm, with 95% confidence band and censoring ticks",
    width: int = 745,
    height: int = 480,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render a hand-authored Kaplan-Meier survival curve and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``arm`` (str), ``t`` (float), ``event`` (bool).
        Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to
        ``assets/svg-examples/survival-km.svg``.
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
    >>> p = make_survival_km()
    >>> p.exists()
    True
    """
    svg = build_svg(data, title=title, subtitle=subtitle, width=width, height=height,
                     mode=mode, accessibility=accessibility, theme=theme)
    dest = Path(out) if out else svg_example_path(__file__, "survival-km")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "survival-km", build_svg, description="Generate a Kaplan-Meier survival curve.")


if __name__ == "__main__":
    main()
