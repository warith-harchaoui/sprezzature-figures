#!/usr/bin/env python3
"""
make_jointplot — a scatter with marginal distributions as hand-authored SVG.

A **joint plot** shows the *joint* relation of two continuous variables in a
central scatter and each *marginal* distribution as a histogram glued to the
matching edge: the x-variable's histogram sits on the top rail, the
y-variable's on the right rail. This is the seaborn ``jointplot`` / R
``ggExtra`` capability: one panel that answers both "how do these two move
together?" and "how is each one spread?" at the same time.

This generator builds the SVG by hand (no matplotlib / seaborn / plotly, no
Vega) so the central scatter, the two marginal histograms, the fitted trend
line, and the shared numeric windows that glue the marginals to the scatter
edges are all under our control. It matches the sprezzature-* house style: Roboto,
the Apple-ish palette, rounded corners, ink ``#1D1D1F``, secondary
``#6E6E73``, white background, white keylines (never black rings).

The scenario is a **sleep study**: each of 120 volunteers reports how many
hours they slept the night before a timed reaction-time test. The scatter
shows the negative trend (more sleep, faster responses); the top marginal
shows sleep is roughly symmetric, the right marginal shows reaction time has
a long slow tail. Each marginal carries its own hue (sleep = Apple Green,
reaction time = Apple Purple) so the two distributions never blur together;
the scatter stays Blue and the fitted trend Orange, so the panel reads in
four clearly-separated house colours.

The figure is **static**: a joint plot shows the whole joint-and-marginal
story in one still. Each scatter point carries a native ``<title>`` tooltip
and a :hover / :focus enlargement; no JavaScript beyond the fullscreen
control.

The final artifact is always an SVG written to
``sprezzature-figures/assets/svg-examples/jointplot.svg``.

Usage
-----
::

    python make_jointplot.py            # writes next to the skill
    python make_jointplot.py --out /tmp/jointplot.svg

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

# House-style palette + the shared SVG primitives live alongside in scripts/.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _interactive import fullscreen_control  # noqa: E402
from _style import (  # noqa: E402
    forced_color_patterns,
    load_palette,
    os_adaptive_style,
    os_dark_style,
)
from _svg import foreground_tip_css, svg_open, tooltip_bubble, xml_escape  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme  # noqa: E402


def make_data(n: int = 120, seed: int = 7) -> List[Dict[str, float]]:
    """Sample a plausible *sleep vs. reaction-time* dataset.

    Hours slept are drawn from a mildly right-truncated normal centred on a
    typical night; reaction time is a linear function of sleep with a floor
    (nobody reacts instantly) plus noise, so the scatter shows a clear
    negative trend while the y-marginal keeps a slow long tail — exactly the
    shape a joint plot is meant to reveal.

    Parameters
    ----------
    n : int, optional
        Number of volunteers (points). Default 120.
    seed : int, optional
        NumPy random seed for reproducibility. Default 7.

    Returns
    -------
    list of dict
        One record per volunteer, ``{"sleep": <hours>, "rt": <ms>}``, rounded
        so the values read cleanly in a tooltip.
    """
    rng = np.random.default_rng(seed)

    # Hours slept: centred a touch under a full night, clipped to a realistic
    # 4.0-9.5 h window so both marginals stay on-scale.
    sleep = rng.normal(loc=6.6, scale=1.4, size=n)
    sleep = np.clip(sleep, 4.0, 9.5)

    # Reaction time (ms) falls ~28 ms for every extra hour of sleep, with a
    # subject-to-subject noise term. The intercept + slope put the cloud in
    # the 180-420 ms band that real go/no-go tasks show.
    rt = 470.0 - 28.0 * sleep + rng.normal(loc=0.0, scale=26.0, size=n)
    rt = np.clip(rt, 180.0, 420.0)

    return [
        {"sleep": round(float(s), 1), "rt": int(round(float(r)))}
        for s, r in zip(sleep, rt)
    ]


def histogram(
    values: List[float],
    lo: float,
    hi: float,
    bins: int,
) -> List[Tuple[float, float, int]]:
    """Bin ``values`` into ``bins`` equal-width buckets over ``[lo, hi]``.

    Returns each bucket as ``(left_edge, right_edge, count)`` so the caller
    can draw a bar per bucket. Values are clamped to the window before
    binning, so nothing spills off either end.

    Parameters
    ----------
    values : list of float
        The samples to bin (one marginal variable).
    lo, hi : float
        Inclusive lower and upper edges of the binning window — the same
        numeric domain the scatter axis uses, so the marginal lines up with
        the central panel.
    bins : int
        Number of equal-width buckets.

    Returns
    -------
    list of tuple
        ``(left, right, count)`` per bucket, left-to-right.
    """
    width = (hi - lo) / bins
    counts = [0] * bins
    for v in values:
        # Clamp into the window, then locate the bucket; the top edge folds
        # into the last bucket so a value exactly at ``hi`` still counts.
        vv = min(max(v, lo), hi)
        idx = int((vv - lo) / width)
        if idx >= bins:
            idx = bins - 1
        counts[idx] += 1
    return [(lo + i * width, lo + (i + 1) * width, counts[i]) for i in range(bins)]


def build_svg(
    data: "List[Dict[str, float]] | None" = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full joint-plot SVG string.

    Layout is a central scatter with two marginal histograms: the top rail
    holds the sleep histogram (shares the scatter's x-window), the right rail
    holds the reaction-time histogram (shares the scatter's y-window). A
    least-squares trend line is layered over the scatter.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``sleep`` (hours) and ``rt`` (reaction time, ms).
        Defaults to :func:`make_data`'s illustrative sleep study.
    mode : str, optional
        Interactivity mode passed to :func:`_interactive.fullscreen_control`
        (``"self-contained"``, ``"external"`` or ``"static"``). Defaults to
        ``"self-contained"``.
    accessibility : str, optional
        Palette accessibility level threaded into :func:`_style.load_palette`
        (``"universal"``, ``"high-contrast"``, ``"monochrome"``,
        ``"deuteranopia"``, ``"protanopia"`` or ``"tritanopia"``). Defaults to
        ``"universal"``, the colour-vision-safe standard.
    theme : str, optional
        Visual theme: ``"corporate"`` (default, Roboto -- byte-identical to
        the pre-theme render) or ``"academic"`` (LaTeX-style Latin Modern).
        See :func:`sprezzature_figures.fonts.chrome_stack_for_theme`.

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    palette: Dict[str, str] = load_palette(accessibility, theme=theme)
    accent = palette.get("Blue", "#007AFF")       # central scatter
    trend = palette.get("Orange", "#FF9500")      # fitted trend line
    # Each marginal carries its OWN hue so the eye tells the two distributions
    # apart at a glance: sleep (top) is Apple Green, reaction time (right) is
    # Apple Purple. Green / Blue / Orange / Purple all separate under
    # deuteranopia and in greyscale (distinct lightness), and each marginal is
    # also positioned + titled, so colour is never the only channel.
    top_fill = palette.get("Green", "#34C759")
    right_fill = palette.get("Purple", "#AF52DE")
    ink = "#1D1D1F"
    secondary = "#6E6E73"
    grid_col = "#EEEEEE"

    data = data if data else make_data()
    sleep = [float(d["sleep"]) for d in data]
    rt = [float(d["rt"]) for d in data]

    # --- shared numeric windows (glue marginals to the scatter) ---
    x_min, x_max = 4.0, 9.5
    y_min, y_max = 170.0, 420.0
    x_ticks = [4, 5, 6, 7, 8, 9]
    y_ticks = [180, 220, 260, 300, 340, 380, 420]

    # --- canvas geometry -----------------------------------------
    width = 940
    height = 940
    m_left = 118
    m_right = 40
    # 160, not the previous 236, so the ~75px gap between the subtitle and
    # the "Distribution of hours slept" label collapses; the freed space
    # goes to the scatter (plot_h grows automatically below), not wasted.
    m_top = 160
    m_bottom = 96
    marg = 132            # thickness of each marginal band
    gap = 12              # gap between a marginal and the scatter

    # The scatter fills the space left after the margins and the two bands.
    plot_x = m_left
    plot_w = width - m_left - m_right - marg - gap
    plot_y = m_top + marg + gap
    plot_h = height - plot_y - m_bottom

    def sx(v: float) -> float:
        """Map hours slept to an x pixel coordinate."""
        return plot_x + (v - x_min) / (x_max - x_min) * plot_w

    def sy(v: float) -> float:
        """Map reaction time (ms) to a y pixel coordinate (y-down)."""
        return plot_y + (y_max - v) / (y_max - y_min) * plot_h

    # --- marginal histograms -------------------------------------
    # ~14 buckets over each window: fine enough to show the sleep symmetry and
    # the reaction-time upper tail, coarse enough that each bar has presence
    # (the reference Vega spec nice-binned to a similar count).
    n_bins = 14
    top_hist = histogram(sleep, x_min, x_max, n_bins)
    right_hist = histogram(rt, y_min, y_max, n_bins)
    # A shared count ceiling with headroom so the tallest bar never touches a
    # rail (defect: clipped marginal). Both marginals use the same ceiling so
    # a reader can compare bar heights across the two.
    max_count = max(max(c for *_e, c in top_hist), max(c for *_e, c in right_hist))
    count_ceiling = max_count + 2

    # --- least-squares trend of reaction time on sleep -----------
    slope, intercept = np.polyfit(np.array(sleep), np.array(rt), deg=1)
    trend_x0, trend_x1 = x_min, x_max
    trend_y0 = intercept + slope * trend_x0
    trend_y1 = intercept + slope * trend_x1

    parts: List[str] = []

    # --- SVG root + accessible description ------------------------
    parts.append(svg_open(width, height, "jp-title", "jp-desc", font_family=chrome_stack_for_theme(theme)))
    parts.append(
        '<title id="jp-title">A good night\'s sleep sharpens reaction '
        'time</title>'
    )
    parts.append(
        '<desc id="jp-desc">Joint plot of a sleep study: a central scatter '
        'of mean reaction time (vertical, milliseconds, lower is better) '
        'against hours slept the night before (horizontal) for 120 '
        'volunteers, with a fitted trend line sloping downward — more sleep, '
        'faster responses. A green histogram along the top rail shows hours '
        'slept are roughly symmetric; a purple histogram along the right '
        'rail shows reaction time has a long slow upper tail. Illustrative '
        'data.</desc>'
    )

    # Static figure: hover / focus enlargement only, no motion to guard.
    # OS-adaptive overrides (additive; the default render is byte-identical
    # because every rule lives inside a media query). Under prefers-contrast the
    # four house hues that carry meaning — scatter dots (Blue), the fitted trend
    # (Orange), and the two marginals (sleep Green, reaction-time Purple) — deepen
    # to their high-contrast tones on the property each drives (fill for the two
    # marginal bar sets and the dots, stroke for the trend line).
    contrast = os_adaptive_style(
        {".jp-topbar": top_fill, ".jp-rightbar": right_fill, ".jp-dot": accent},
        role="fill",
    )
    contrast_line = os_adaptive_style({".jp-trend": trend}, role="stroke")
    # Under Windows High Contrast / forced-colors the ~4-colour system palette
    # cannot preserve four data hues, and colour is the sole key that separates
    # the two marginals (and the scatter). So each colour-encoded fill set takes a
    # distinct CanvasText pattern (hatch / dots) drawn on Canvas — identity by
    # texture, not hue. The patterns live in <defs> and are referenced only inside
    # the forced-colors media query, so the default render is unchanged.
    fcp_defs, fcp_style = forced_color_patterns(
        [".jp-topbar", ".jp-rightbar", ".jp-dot"], prefix="jp-fcp"
    )
    parts.append(
        "<style>"
        ".pt{cursor:pointer}"
        ".pt .halo{opacity:0}"
        ".pt:hover .halo,.pt:focus .halo{opacity:1}"
        ".pt:focus{outline:none}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        f"{foreground_tip_css(len(top_hist), mark_prefix='topbar', tip_prefix='topbartip')}"
        f"{foreground_tip_css(len(right_hist), mark_prefix='rightbar', tip_prefix='rightbartip')}"
        f"{foreground_tip_css(len(data), mark_prefix='point', tip_prefix='pointtip')}"
        "@media (prefers-reduced-motion:reduce){.tip{transition:none}}"
        "\n" + contrast + "\n" + contrast_line + "\n" + fcp_style + "\n"
        # Additive OS dark mode: dark paper + light ink (default ink_map); the
        # scatter Blue and trend Orange are data hues, left alone. The very light
        # gridlines are darkened so they read on the dark surface.
        + os_dark_style(extra='[stroke="#EEEEEE"]{stroke:#2E2E31;}') + "\n"
        "</style>"
    )
    # Forced-colors pattern tiles (referenced only inside the media query above).
    parts.append(f"<defs>{fcp_defs}</defs>")

    # --- background ----------------------------------------------
    parts.append(f'<rect width="{width}" height="{height}" fill="#FFFFFF"/>')

    # --- title + subtitle (the takeaway) -------------------------
    parts.append(
        f'<text x="{m_left}" y="70" font-size="34" font-weight="700" '
        f'fill="{ink}">A good night\'s sleep sharpens reaction time</text>'
    )
    parts.append(
        f'<text x="{m_left}" y="108" font-size="19" fill="{secondary}">'
        f'Reaction-time test vs. hours slept, 120 volunteers — marginals '
        f'show each distribution</text>'
    )
    # --- top marginal: histogram of hours slept ------------------
    # Bars grow downward from the top rail toward the scatter, so the marginal
    # reads as a distribution hugging the shared x-window.
    top_base = m_top + marg           # the rail the bars stand on
    # This chart has three independent hit/tip groups (top bars, right bars,
    # scatter points below); each gets its own id prefix and bubble list so
    # ids never collide across groups. Every group draws its marks first,
    # then its bubbles, all appended once at the very end (SVG has no
    # z-index; a bubble next to its own mark would be covered by any mark
    # drawn afterward -- in any group, not just its own) -- see
    # _svg.foreground_tip_css's docstring.
    topbar_tips: List[str] = []
    for i, (left, right, count) in enumerate(top_hist):
        bw = sx(right) - sx(left)
        bh = count / count_ceiling * marg
        bx = sx(left)
        by = top_base - bh
        bar_tip = f"{left:.1f}-{right:.1f} h slept: {count} volunteers"
        # Round only the top corners so the bar reads as a clean column.
        parts.append(
            f'<rect id="topbar-{i}" class="jp-topbar hit" tabindex="0" x="{bx + 1:.1f}" y="{by:.1f}" '
            f'width="{max(bw - 2, 0.5):.1f}" '
            f'height="{bh:.1f}" rx="3" fill="{top_fill}">'
            f'<title>{xml_escape(bar_tip)}</title></rect>'
        )
        topbar_tips.append(
            tooltip_bubble(
                bx + max(bw - 2, 0.5) / 2.0,
                max(4.0, by - 46.0),
                [f"{left:.1f}-{right:.1f} h slept", f"{count} volunteers"],
                canvas_w=width,
                canvas_h=height,
                ink=ink,
                secondary=secondary,
                border=grid_col,
                elem_id=f"topbartip-{i}",
            )
        )
    parts.append(
        f'<text x="{plot_x:.1f}" y="{m_top - 8:.1f}" font-size="16" '
        f'fill="{secondary}">Distribution of hours slept</text>'
    )

    # --- right marginal: histogram of reaction times -------------
    # Bars grow leftward from the right rail toward the scatter.
    right_base = plot_x + plot_w + gap    # left edge the bars stand on
    rightbar_tips: List[str] = []
    for i, (lo, hi, count) in enumerate(right_hist):
        by = sy(hi)
        bh = sy(lo) - sy(hi)
        bw = count / count_ceiling * marg
        bar_tip = f"{lo:.0f}-{hi:.0f} ms reaction time: {count} volunteers"
        parts.append(
            f'<rect id="rightbar-{i}" class="jp-rightbar hit" tabindex="0" x="{right_base:.1f}" y="{by + 1:.1f}" '
            f'width="{bw:.1f}" '
            f'height="{max(bh - 2, 0.5):.1f}" rx="3" fill="{right_fill}">'
            f'<title>{xml_escape(bar_tip)}</title></rect>'
        )
        rightbar_tips.append(
            tooltip_bubble(
                right_base + bw + 8.0,
                max(4.0, by + max(bh - 2, 0.5) / 2.0 - 24.0),
                [f"{lo:.0f}-{hi:.0f} ms reaction time", f"{count} volunteers"],
                anchor="start",
                canvas_w=width,
                canvas_h=height,
                ink=ink,
                secondary=secondary,
                border=grid_col,
                elem_id=f"rightbartip-{i}",
            )
        )
    # Rotated caption for the right marginal, clear of the bars.
    rcap_x = width - m_right + 2
    rcap_y = plot_y + plot_h / 2
    parts.append(
        f'<text x="{rcap_x:.1f}" y="{rcap_y:.1f}" font-size="16" '
        f'fill="{secondary}" text-anchor="middle" '
        f'transform="rotate(90 {rcap_x:.1f} {rcap_y:.1f})">'
        f'Distribution of reaction time</text>'
    )

    # --- gridlines (very light) ----------------------------------
    for t in x_ticks:
        gx = sx(t)
        parts.append(
            f'<line x1="{gx:.1f}" y1="{plot_y:.1f}" x2="{gx:.1f}" '
            f'y2="{plot_y + plot_h:.1f}" stroke="{grid_col}" stroke-width="1.4"/>'
        )
    for t in y_ticks:
        gy = sy(t)
        parts.append(
            f'<line x1="{plot_x:.1f}" y1="{gy:.1f}" x2="{plot_x + plot_w:.1f}" '
            f'y2="{gy:.1f}" stroke="{grid_col}" stroke-width="1.4"/>'
        )

    # --- axes (L-shaped, ink) ------------------------------------
    ax_bottom = plot_y + plot_h
    parts.append(
        f'<line x1="{plot_x:.1f}" y1="{ax_bottom:.1f}" '
        f'x2="{plot_x + plot_w:.1f}" y2="{ax_bottom:.1f}" '
        f'stroke="{ink}" stroke-width="1.6"/>'
    )
    parts.append(
        f'<line x1="{plot_x:.1f}" y1="{plot_y:.1f}" x2="{plot_x:.1f}" '
        f'y2="{ax_bottom:.1f}" stroke="{ink}" stroke-width="1.6"/>'
    )
    for t in x_ticks:
        gx = sx(t)
        parts.append(
            f'<line x1="{gx:.1f}" y1="{ax_bottom:.1f}" x2="{gx:.1f}" '
            f'y2="{ax_bottom + 6:.1f}" stroke="{ink}" stroke-width="1.4"/>'
        )
        parts.append(
            f'<text x="{gx:.1f}" y="{ax_bottom + 28:.1f}" font-size="17" '
            f'font-family="Roboto Mono, monospace" fill="{ink}" '
            f'text-anchor="middle">{t}.0</text>'
        )
    for t in y_ticks:
        gy = sy(t)
        parts.append(
            f'<line x1="{plot_x - 6:.1f}" y1="{gy:.1f}" x2="{plot_x:.1f}" '
            f'y2="{gy:.1f}" stroke="{ink}" stroke-width="1.4"/>'
        )
        parts.append(
            f'<text x="{plot_x - 14:.1f}" y="{gy + 6:.1f}" font-size="17" '
            f'font-family="Roboto Mono, monospace" fill="{ink}" '
            f'text-anchor="end">{t}</text>'
        )

    # --- axis titles ---------------------------------------------
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{ax_bottom + 62:.1f}" '
        f'font-size="19" fill="{ink}" text-anchor="middle">'
        f'Sleep the night before (hours)</text>'
    )
    ytitle_x = 44
    ytitle_y = plot_y + plot_h / 2
    parts.append(
        f'<text x="{ytitle_x:.1f}" y="{ytitle_y:.1f}" font-size="19" '
        f'fill="{ink}" text-anchor="middle" '
        f'transform="rotate(-90 {ytitle_x:.1f} {ytitle_y:.1f})">'
        f'Mean reaction time, ms (lower is better)</text>'
    )

    # --- scatter points ------------------------------------------
    # A white keyline lifts each dot off its neighbours and the gridlines — a
    # bright keyline, never a dark ring.
    r_dot = 7.0
    dot_px: List[Tuple[float, float]] = []
    point_tips: List[str] = []
    for i, d in enumerate(data):
        s = float(d["sleep"])
        r = float(d["rt"])
        cx, cy = sx(s), sy(r)
        dot_px.append((cx, cy))
        tip = f"{s:.1f} h slept, {int(r)} ms reaction time"
        parts.append(
            f'<g id="point-{i}" class="pt hit" tabindex="0" role="img" '
            f'aria-label="{xml_escape(tip)}">'
        )
        parts.append(f"<title>{xml_escape(tip)}</title>")
        parts.append(
            f'<circle class="halo" cx="{cx:.1f}" cy="{cy:.1f}" r="16" '
            f'fill="{ink}" fill-opacity="0.08"/>'
        )
        parts.append(
            f'<circle class="jp-dot" cx="{cx:.1f}" cy="{cy:.1f}" r="{r_dot:.1f}" '
            f'fill="{accent}" fill-opacity="0.62" stroke="#FFFFFF" '
            f'stroke-width="1.1"/>'
        )
        parts.append("</g>")
        point_tips.append(
            tooltip_bubble(
                cx,
                max(4.0, cy - 40.0),
                [f"{s:.1f} h slept", f"{int(r)} ms reaction time"],
                canvas_w=width,
                canvas_h=height,
                ink=ink,
                secondary=secondary,
                border=grid_col,
                elem_id=f"pointtip-{i}",
            )
        )

    # --- fitted trend line (drawn on top of the cloud) -----------
    # A soft white under-stroke keeps the trend crisp where it crosses the
    # densest part of the cloud; the Orange line rides on top.
    x0p, y0p = sx(trend_x0), sy(trend_y0)
    x1p, y1p = sx(trend_x1), sy(trend_y1)
    parts.append(
        f'<line x1="{x0p:.1f}" y1="{y0p:.1f}" x2="{x1p:.1f}" y2="{y1p:.1f}" '
        f'stroke="#FFFFFF" stroke-width="8" stroke-linecap="round"/>'
    )
    parts.append(
        f'<line class="jp-trend" x1="{x0p:.1f}" y1="{y0p:.1f}" x2="{x1p:.1f}" '
        f'y2="{y1p:.1f}" stroke="{trend}" stroke-width="4" stroke-linecap="round"/>'
    )
    # Name the trend on the line itself, so the reader needs no legend. A fixed
    # position along the line can land the label directly on a data point when
    # the cloud is dense there (a real "text overlaps data" defect caught by
    # visual review), so instead probe a handful of candidate positions along
    # the line's sparser second half and keep the one with the most clearance
    # from the nearest dot -- the white halo (paint-order: stroke) still
    # covers the rare close call, but this keeps close calls rare.
    best_t, best_clearance = 0.72, -1.0
    for t in (0.55, 0.62, 0.69, 0.76, 0.83, 0.90):
        cand_x = x0p + (x1p - x0p) * t
        cand_y = y0p + (y1p - y0p) * t - 15
        clearance = min(math.hypot(cand_x - px, cand_y - py) for px, py in dot_px)
        if clearance > best_clearance:
            best_t, best_clearance = t, clearance
    tl_x = x0p + (x1p - x0p) * best_t
    tl_y = y0p + (y1p - y0p) * best_t - 15
    ang = math.degrees(math.atan2(y1p - y0p, x1p - x0p))
    parts.append(
        f'<text x="{tl_x:.1f}" y="{tl_y:.1f}" font-size="17" '
        f'font-weight="700" fill="{trend}" stroke="#FFFFFF" stroke-width="3.5" '
        f'paint-order="stroke" text-anchor="middle" '
        f'transform="rotate({ang:.1f} {tl_x:.1f} {tl_y:.1f})">'
        f'fitted trend</text>'
    )

    parts.extend(topbar_tips)
    parts.extend(rightbar_tips)
    parts.extend(point_tips)
    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


#: The registry contract's DEMO_DATA — the same sleep-study rows
#: :func:`make_data` already produces (a fixed seed keeps it reproducible).
DEMO_DATA: List[Dict[str, float]] = make_data()


def make_jointplot(
    data: "List[Dict[str, float]] | None" = None,
    *,
    out: "Path | str | None" = None,
    title: str = "",
    subtitle: str = "",
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render the joint plot and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, float]] or None
        Rows with keys ``sleep`` (hours) and ``rt`` (reaction time, ms).
        Defaults to :data:`DEMO_DATA`. ``title``/``subtitle`` are accepted
        for signature parity with the rest of the gallery; the headline
        states a fact about the illustrative sleep study and is currently a
        documented no-op.
    out : Path, str, or None
        Output path. Defaults to ``assets/svg-examples/jointplot.svg``.
    mode, accessibility : str
        Forwarded to :func:`build_svg`.
    theme : str, optional
        Visual theme. Forwarded to :func:`build_svg`.

    Returns
    -------
    Path
        Absolute path to the written SVG file.
    """
    _ = title, subtitle
    rows = data if data else DEMO_DATA
    svg = build_svg(rows, mode=mode, accessibility=accessibility, theme=theme)
    dest = Path(out) if out else svg_example_path(__file__, "jointplot")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """Write the joint-plot SVG to the canonical assets path (or --out)."""
    render_cli(
        __file__, "jointplot", build_svg,
        description="Render the joint plot (scatter + marginal histograms) SVG.",
    )


if __name__ == "__main__":
    main()
