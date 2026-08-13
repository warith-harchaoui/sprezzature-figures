#!/usr/bin/env python3
"""
make_elbow — elbow / knee detection (the Kneedle method) as a hand SVG.

Choosing "how many" — clusters for k-means, components for PCA, ``eps`` for
DBSCAN — usually comes down to reading an *elbow*: the point on a
diminishing-returns curve where the steep early gains give way to a flat
tail, so spending more stops paying off. The eye finds it easily; automating
it is the job of the **Kneedle** algorithm (Satopää et al., *Finding a Kneedle
in a Haystack*, 2011; reference implementation ``kneed`` by Kevin Arvai,
https://github.com/arvkevi/kneed).

Kneedle is simple and elegant: normalise both axes to the unit square, flip
the curve into a concave-increasing frame, subtract the diagonal to get a
*difference curve*, and take its peak — that peak is the point of maximum
curvature, the elbow. By default this figure applies exactly that method to a
demo k-means inertia curve and finds the elbow at ``k = 4``. Pass real
``data`` (see :func:`make_elbow`) to plot an actual sweep instead — the axis
domain, the elbow marker, and the Kneedle inset all follow the data.

A caller with its own uncertainty estimate (e.g. a bootstrap confidence
interval, a detection rate across resamples, a null-model p-value — see
`elbow-helper <https://github.com/warith-harchaoui/elbow-helper>`_, whose
``robust_elbow()`` computes exactly these) can pass them through ``ci``,
``detection_rate``, and ``null_p_value`` to enrich the Kneedle inset instead
of drawing a bare point estimate. Passing ``is_clear=False`` with an
``abstain_reason`` switches the whole figure to an honest "no clear elbow"
state (greyed curve, no marker, no inset, a plain-language reason) rather
than forcing a possibly-spurious point estimate onto noisy or structureless
data.

The generator builds the SVG string by hand (no matplotlib / Vega) so the
elbow marker, the split between steep gains and diminishing returns, and the
inset signal are all placed deliberately. House style follows ``_style.py``:
Roboto type, the Apple-system palette, ink ``#1D1D1F`` on white, a
start-anchored takeaway title. Every data point carries a native ``<title>``
tooltip; an additive dark-mode block flips the paper without touching the data
hues.

Running the module writes the SVG to
``sprezzature-figures/assets/svg-examples/elbow.svg``.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _scale import nice_ticks  # noqa: E402
from _style import BG, GRIDLINE, INK, load_palette, os_dark_style  # noqa: E402
from _svg import catmull_rom_beziers, fmt_compact, svg_open, tooltip_bubble  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402

# ------------------------------------------------------------------
# Canvas + house-style tokens
# ------------------------------------------------------------------
WIDTH = 1000
HEIGHT = 620

# Plot frame (baseline at PB, left axis at PL).
PL = 96.0
PR = 948.0
PT = 188.0
PB = 524.0
PLOT_W = PR - PL
PLOT_H = PB - PT

SUBINK = "#6E6E73"    # secondary text
HAIR = "#E5E5EA"      # gridlines


# ------------------------------------------------------------------
# Demo story (used only when the caller passes no ``data``): a k-means run
# swept over k = 1..10. Inertia (the within-cluster sum of squares) falls
# steeply as the first real clusters are found, then flattens once the
# structure is captured — the classic elbow. Values are illustrative but
# shaped like a real inertia curve.
# ------------------------------------------------------------------
_DEMO_KS: list[int] = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
_DEMO_INERTIA: list[float] = [1000, 560, 330, 210, 165, 138, 120, 108, 100, 95]

#: Row-record view of the demo sweep, the shape the ``make_<kind>`` contract
#: asks for: one dict per swept ``k``. Also the shape :func:`make_elbow`
#: expects from a real caller — ``k`` is any ordered x-axis quantity (cluster
#: count, PCA components, 1/eps, ...), ``inertia`` any decreasing y-axis
#: quantity (inertia, reconstruction error, ...).
DEMO_DATA: list[dict[str, Any]] = [
    {"k": k, "inertia": inertia} for k, inertia in zip(_DEMO_KS, _DEMO_INERTIA, strict=True)
]

_STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "steep": "steep gains",
        "flat": "diminishing returns",
        "elbow_pill": "Elbow",
        "inset_title": "Kneedle signal",
        "inset_subtitle": "normalised difference · peak = elbow",
        "detection_rate": "detection rate",
        "null_p": "null-model p",
        "no_elbow_title": "No clear elbow",
        "no_elbow_hint": "The evidence was too weak to report a point estimate.",
        "x_axis_default": "Number of clusters (k)",
        "y_axis_default": "Inertia (within-cluster sum of squares)",
    },
    "fr": {
        "steep": "gains marqués",
        "flat": "rendements décroissants",
        "elbow_pill": "Coude",
        "inset_title": "Signal Kneedle",
        "inset_subtitle": "différence normalisée · pic = coude",
        "detection_rate": "taux de détection",
        "null_p": "p (modèle nul)",
        "no_elbow_title": "Aucun coude net",
        "no_elbow_hint": "L'évidence était trop faible pour une estimation ponctuelle.",
        "x_axis_default": "Nombre de clusters (k)",
        "y_axis_default": "Inertie (somme des carrés intra-cluster)",
    },
}


def _strings(language: str) -> dict[str, str]:
    """Chrome-text dict for `language`, falling back to English."""
    return _STRINGS.get(language, _STRINGS["en"])


# ------------------------------------------------------------------
# Kneedle, in pure Python (faithful to arvkevi/kneed for a convex,
# decreasing curve): normalise both axes, flip y into an increasing frame,
# subtract the diagonal, and take the peak of the difference curve.
# ------------------------------------------------------------------
def kneedle_elbow(
    xs: list[float], ys: list[float]
) -> tuple[int, list[float]]:
    """Locate the elbow of a convex, decreasing curve by the Kneedle method.

    Parameters
    ----------
    xs : list of float
        Strictly increasing x values (here, the cluster counts ``k``).
    ys : list of float
        The curve values (here, inertia), convex and decreasing.

    Returns
    -------
    elbow_index : int
        Index into ``xs`` / ``ys`` of the detected elbow (the peak of the
        normalised difference curve).
    diff : list of float
        The normalised difference curve ``d = (1 - y_norm) - x_norm``; its
        maximum marks the elbow. Aligned with ``xs``.
    """
    x_lo, x_hi = min(xs), max(xs)
    y_lo, y_hi = min(ys), max(ys)
    x_span = (x_hi - x_lo) or 1.0
    y_span = (y_hi - y_lo) or 1.0
    diff: list[float] = []
    for x, y in zip(xs, ys, strict=True):
        xn = (x - x_lo) / x_span
        yn = (y - y_lo) / y_span
        # Flip the decreasing curve to increasing, then subtract the diagonal:
        # the gap between the flipped curve and the chord peaks at the knee.
        diff.append((1.0 - yn) - xn)
    elbow_index = max(range(len(diff)), key=lambda i: diff[i])
    return elbow_index, diff


# ------------------------------------------------------------------
# SVG emission
# ------------------------------------------------------------------
def build_svg(
    data: list[dict[str, Any]] | None = None,
    *,
    mode: str = "self-contained",
    accessibility: str = "universal",
    language: str = "en",
    x_label: str | None = None,
    y_label: str | None = None,
    ci: tuple[float, float] | None = None,
    is_clear: bool = True,
    abstain_reason: str | None = None,
    detection_rate: float | None = None,
    null_p_value: float | None = None,
    theme: str = "corporate",
) -> str:
    """Assemble the full elbow-detection SVG document as a string.

    Parameters
    ----------
    data : list of dict, optional
        Rows of ``{"k": x_value, "inertia": y_value}`` describing the swept
        curve, ordered by ``k``. Defaults to the demo k-means inertia sweep
        (:data:`DEMO_DATA`) when omitted. ``k``/``inertia`` are the catalog's
        role names (see ``figures.json``); the curve itself may be any
        ordered x-axis quantity against a convex, decreasing y-axis quantity
        — the labels can be overridden via ``x_label``/``y_label``.
    mode : str, optional
        Interactivity mode passed to :func:`_interactive.fullscreen_control`.
    accessibility : str, optional
        Palette accessibility level forwarded to :func:`_style.load_palette`.
    language : str, optional
        Chrome-text language, ``"en"`` or ``"fr"`` (default ``"en"``).
    x_label, y_label : str, optional
        Axis titles. Default to the k-means framing ("Number of clusters
        (k)" / "Inertia ...") in the selected language when omitted.
    ci : tuple of float, optional
        A ``(low, high)`` confidence interval for the elbow location, in the
        same units as ``k``. When given and ``is_clear`` is true, drawn as a
        shaded band around the elbow marker instead of a bare vertical line.
    is_clear : bool, optional
        When false, the figure renders an honest abstention state instead of
        a point estimate: the curve is greyed and dashed, no elbow marker or
        Kneedle inset is drawn, and ``abstain_reason`` is shown as plain-
        language prose. Mirrors the "abstain rather than over-claim"
        philosophy of `elbow-helper
        <https://github.com/warith-harchaoui/elbow-helper>`_.
    abstain_reason : str, optional
        Plain-language reason shown when ``is_clear`` is false.
    detection_rate : float, optional
        Fraction of bootstrap resamples that located the same elbow (0-1).
        When given, appended as an extra line in the Kneedle inset card.
    null_p_value : float, optional
        P-value of the elbow under a no-knee null model. When given,
        appended as an extra line in the Kneedle inset card.
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
    strings = _strings(language)
    rows = data if data else DEMO_DATA
    ks = [float(r["k"]) for r in rows]
    inertia = [float(r["inertia"]) for r in rows]
    x_label = x_label or strings["x_axis_default"]
    y_label = y_label or strings["y_axis_default"]

    # Axis domain follows the data rather than the demo's fixed 0-1050 span,
    # so a real caller's curve always fits. Ticks come from the shared "nice
    # numbers" generator (round 1/2/5 x 10**k steps, e.g. 0/200/400/.../1000)
    # instead of naive quartiles of the padded max, which used to print
    # labels like 262/525/788 -- arithmetically even but not values a reader
    # can scan or estimate against. `nice_ticks` also supplies its own
    # headroom (its top tick lands at or above the data max), so no separate
    # 1.05 padding factor is needed.
    y_ticks = nice_ticks(max(inertia) if inertia else 1.0, n=4)
    y_max = y_ticks[-1] if y_ticks[-1] > 0 else 1.0

    def sx(k: float) -> float:
        """Map an x value to a pixel x coordinate over the data's own span."""
        span = (ks[-1] - ks[0]) or 1.0
        return PL + (k - ks[0]) / span * PLOT_W

    def sy(v: float) -> float:
        """Map a y value to a pixel y coordinate (0 at the baseline)."""
        return PB - (v / y_max) * PLOT_H

    palette = load_palette(accessibility, theme=theme)
    curve_hue = palette.get("Blue", "#007AFF")
    curve_deep = palette.get("Indigo", "#0051A8")
    accent = palette.get("Red", "#FF3B30")
    muted = palette.get("Gray", "#8E8E93")

    if is_clear:
        elbow_i, diff = kneedle_elbow(ks, inertia)
        elbow_k = ks[elbow_i]
        elbow_val = inertia[elbow_i]
        ex, ey = sx(elbow_k), sy(elbow_val)
        title_txt = "Elbow detection: where adding clusters stops paying off"
        subtitle_txt = (
            f"The curve falls steeply, then flattens; the Kneedle method "
            f"flags the elbow at k = {fmt_compact(elbow_k)}"
        )
        desc_txt = (
            f"Line chart of a diminishing-returns curve against k, from "
            f"{fmt_compact(ks[0])} to {fmt_compact(ks[-1])}. The curve drops "
            f"sharply then flattens. The Kneedle algorithm normalises the "
            f"axes and takes the peak of the difference curve to locate the "
            f"elbow at k = {fmt_compact(elbow_k)}, where the value is "
            f"{elbow_val:.0f}. An inset shows that difference curve, whose "
            f"peak marks the elbow."
        )
    else:
        elbow_i = diff = None  # type: ignore[assignment]
        ex = ey = 0.0
        title_txt = strings["no_elbow_title"]
        subtitle_txt = abstain_reason or strings["no_elbow_hint"]
        desc_txt = (
            f"Line chart of a curve against k, from {fmt_compact(ks[0])} to "
            f"{fmt_compact(ks[-1])}. No elbow is reported: {subtitle_txt}"
        )

    p: list[str] = []
    p.append(svg_open(WIDTH, HEIGHT, "elb-title", "elb-desc", font_family=chrome_stack_for_theme(theme)))
    p.append(f'<title id="elb-title">{escape(title_txt)}</title>')
    p.append(f'<desc id="elb-desc">{escape(desc_txt)}</desc>')

    # --- gradients + additive dark mode ---
    fill_hue = curve_hue if is_clear else muted
    p.append(
        '<defs>'
        f'<linearGradient id="elb-fill" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{fill_hue}" stop-opacity="0.22"/>'
        f'<stop offset="1" stop-color="{fill_hue}" stop-opacity="0.02"/>'
        f'</linearGradient>'
        '</defs>'
    )
    dark = os_dark_style(extra='[stroke="#E5E5EA"]{stroke:#2C2C2E;}')
    tip_css = (
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        ".hit:hover+.tip,.hit:focus+.tip{opacity:1}"
        "@media (prefers-reduced-motion:reduce){.tip{transition:none}}"
    )
    p.append(f"<style>{tip_css}{dark}</style>")

    # --- background ---
    p.append(f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{BG}"/>')

    # --- title + subtitle (start-anchored, house style) ---
    p.append(
        f'<text x="{PL:.0f}" y="72" font-size="31" font-weight="700" '
        f'fill="{INK}">{escape(title_txt)}</text>'
    )
    p.append(
        f'<text x="{PL:.0f}" y="106" font-size="18" fill="{SUBINK}">'
        f'{escape(subtitle_txt)}</text>'
    )

    # --- horizontal gridlines + y tick labels ---
    for tv in y_ticks:
        gy = sy(tv)
        p.append(
            f'<line x1="{PL:.1f}" y1="{gy:.1f}" x2="{PR:.1f}" y2="{gy:.1f}" '
            f'stroke="{HAIR}" stroke-width="1"/>'
        )
        p.append(
            f'<text x="{PL - 14:.1f}" y="{gy + 5:.1f}" text-anchor="end" '
            f'font-family="{mono_family}" font-size="14" fill="{SUBINK}">'
            f'{tv:,.0f}</text>'
        )

    # --- curve points in pixel space ---
    pts: list[tuple[float, float]] = [(sx(k), sy(v)) for k, v in zip(ks, inertia, strict=True)]

    # --- filled area under the curve (smooth top, down to the baseline) ---
    area = [f'M{fmt_compact(pts[0][0])},{fmt_compact(PB)}']
    area.append(f'L{fmt_compact(pts[0][0])},{fmt_compact(pts[0][1])}')
    area.append(catmull_rom_beziers(pts, fmt_compact))
    area.append(f'L{fmt_compact(pts[-1][0])},{fmt_compact(PB)}Z')
    p.append(f'<path d="{"".join(area)}" fill="url(#elb-fill)"/>')

    if is_clear:
        # --- CI band (if given) or a bare vertical divider at the elbow ---
        if ci is not None:
            lo, hi = sx(ci[0]), sx(ci[1])
            p.append(
                f'<rect x="{lo:.1f}" y="{PT - 6:.1f}" width="{(hi - lo):.1f}" '
                f'height="{(PB - PT + 6):.1f}" fill="{accent}" fill-opacity="0.10"/>'
            )
        p.append(
            f'<line x1="{ex:.1f}" y1="{PT - 6:.1f}" x2="{ex:.1f}" y2="{PB:.1f}" '
            f'stroke="{accent}" stroke-width="1.4" stroke-dasharray="2 6" '
            f'stroke-linecap="round"/>'
        )
        p.append(
            f'<text x="{(PL + ex) / 2:.1f}" y="{PT + 22:.1f}" text-anchor="middle" '
            f'font-size="14" font-weight="600" fill="{SUBINK}">{escape(strings["steep"])}</text>'
        )
        # Sit the right-hand label in the clear gap between the elbow divider
        # and the inset card (the card would otherwise cover it).
        p.append(
            f'<text x="{(ex + 566.0) / 2:.1f}" y="{PT + 22:.1f}" text-anchor="middle" '
            f'font-size="14" font-weight="600" fill="{SUBINK}">{escape(strings["flat"])}</text>'
        )

    # --- the curve stroke (dashed + muted in the abstention state) ---
    line = [f'M{fmt_compact(pts[0][0])},{fmt_compact(pts[0][1])}']
    line.append(catmull_rom_beziers(pts, fmt_compact))
    dash = '' if is_clear else ' stroke-dasharray="6 5"'
    p.append(
        f'<path d="{"".join(line)}" fill="none" stroke="{curve_hue if is_clear else muted}" '
        f'stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"{dash}/>'
    )

    # --- data dots (every k), each with a native tooltip ---
    prev_v: float | None = None
    for k, v in zip(ks, inertia, strict=True):
        cx, cy = sx(k), sy(v)
        tip = f"k = {fmt_compact(k)}: {fmt_compact(v)}"
        dot_fill = curve_deep if is_clear else muted
        p.append(
            f'<circle class="hit" cx="{cx:.1f}" cy="{cy:.1f}" r="4.6" fill="{dot_fill}" '
            f'stroke="{BG}" stroke-width="1.6" tabindex="0" role="img" '
            f'aria-label="{escape(tip)}"><title>{escape(tip)}</title></circle>'
        )
        delta_line = f"delta {fmt_compact(v - prev_v)} from previous k" if prev_v is not None else "first point"
        p.append(
            tooltip_bubble(
                cx, cy - 14, [f"k = {fmt_compact(k)}", fmt_compact(v), delta_line],
                canvas_w=WIDTH, canvas_h=HEIGHT, ink=INK, secondary=SUBINK, border=GRIDLINE,
            )
        )
        prev_v = v

    if is_clear:
        # --- elbow marker: halo + ring + drop line to the axis ---
        p.append(
            f'<line x1="{ex:.1f}" y1="{ey:.1f}" x2="{ex:.1f}" y2="{PB:.1f}" '
            f'stroke="{accent}" stroke-width="1.6"/>'
        )
        p.append(f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="15" fill="{accent}" opacity="0.16"/>')
        p.append(
            f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="8.4" fill="{BG}" '
            f'stroke="{accent}" stroke-width="3"/>'
        )
        p.append(f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="3" fill="{accent}"/>')

        # --- elbow callout pill with a short leader ---
        call_txt = f'{strings["elbow_pill"]} · k = {fmt_compact(elbow_k)}'
        pill_w = 150.0
        px = ex + 78.0
        py = ey - 78.0
        p.append(
            f'<line x1="{ex + 11:.1f}" y1="{ey - 11:.1f}" x2="{px - pill_w / 2 + 8:.1f}" '
            f'y2="{py:.1f}" stroke="{accent}" stroke-width="1.6"/>'
        )
        p.append(
            f'<rect x="{px - pill_w / 2:.1f}" y="{py - 17:.1f}" width="{pill_w:.0f}" '
            f'height="34" rx="17" fill="{accent}"/>'
        )
        p.append(
            f'<text x="{px:.1f}" y="{py + 5:.1f}" text-anchor="middle" '
            f'font-family="{mono_family}" font-size="16" font-weight="700" '
            f'fill="{BG}">{escape(call_txt)}</text>'
        )
    else:
        # --- abstention callout: a plain card explaining why, no false marker ---
        _emit_abstain_card(p, strings, abstain_reason)

    # --- x axis: baseline, tick labels, title ---
    p.append(
        f'<line x1="{PL:.1f}" y1="{PB:.1f}" x2="{PR:.1f}" y2="{PB:.1f}" '
        f'stroke="{INK}" stroke-width="1.5"/>'
    )
    for k in ks:
        p.append(
            f'<text x="{sx(k):.1f}" y="{PB + 28:.1f}" text-anchor="middle" '
            f'font-family="{mono_family}" font-size="15" fill="{INK}">{fmt_compact(k)}</text>'
        )
    p.append(
        f'<text x="{(PL + PR) / 2:.1f}" y="{PB + 62:.1f}" text-anchor="middle" '
        f'font-size="17" fill="{INK}">{escape(x_label)}</text>'
    )
    # y-axis title, rotated up the left edge.
    p.append(
        f'<text x="30" y="{(PT + PB) / 2:.1f}" text-anchor="middle" font-size="17" '
        f'fill="{INK}" transform="rotate(-90 30 {(PT + PB) / 2:.1f})">'
        f'{escape(y_label)}</text>'
    )

    # --- inset: the Kneedle difference curve (the "how"), clear case only ---
    if is_clear:
        _emit_inset(
            p, diff, elbow_i, curve_hue, accent, strings, mono_family,
            detection_rate=detection_rate, null_p_value=null_p_value,
        )

    # Fullscreen control per interactivity mode, just before the close.
    p.append(fullscreen_control(WIDTH, HEIGHT, mode))
    p.append("</svg>")
    return "".join(p)


def _emit_abstain_card(
    p: list[str],
    strings: dict[str, str],
    reason: str | None,
) -> None:
    """Append the "no clear elbow" explanation card to ``p``.

    Sits in the same upper-right pocket the Kneedle inset would otherwise
    occupy, so the abstention state and the point-estimate state share one
    layout rhythm — the reader learns where to look regardless of outcome.

    Parameters
    ----------
    p : list of str
        The SVG fragment list being assembled; extended in place.
    strings : dict
        Chrome-text strings for the active language.
    reason : str, optional
        Plain-language abstention reason; a generic hint is used if omitted.
    """
    ix, iy, iw, ih = 566.0, 196.0, 372.0, 176.0
    p.append(
        f'<rect x="{ix:.0f}" y="{iy:.0f}" width="{iw:.0f}" height="{ih:.0f}" '
        f'rx="16" fill="#F5F5F7" stroke="{HAIR}" stroke-width="1"/>'
    )
    p.append(
        f'<text x="{ix + 20:.0f}" y="{iy + 34:.0f}" font-size="15" '
        f'font-weight="700" fill="{INK}">{escape(strings["no_elbow_title"])}</text>'
    )
    body = reason or strings["no_elbow_hint"]
    # Wrap the reason across the card width by hand (no textwrap import needed
    # for the short, single-sentence reasons this is fed in practice).
    words = body.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if len(trial) > 42 and cur:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    for i, line in enumerate(lines[:5]):
        p.append(
            f'<text x="{ix + 20:.0f}" y="{iy + 62 + i * 22:.0f}" font-size="13.5" '
            f'fill="{SUBINK}">{escape(line)}</text>'
        )


def _emit_inset(
    p: list[str],
    diff: list[float],
    elbow_i: int,
    curve: str,
    accent: str,
    strings: dict[str, str],
    mono_family: str,
    *,
    detection_rate: float | None = None,
    null_p_value: float | None = None,
) -> None:
    """Append the Kneedle-signal inset card to ``p``.

    The inset sits in the empty upper-right pocket (the inertia curve is low
    there) and draws the normalised difference curve whose peak located the
    elbow, so the figure shows the method, not just its result. When the
    caller supplies uncertainty evidence (``detection_rate``,
    ``null_p_value``), it is appended as two extra lines under the mini
    plot, so the card reads as evidence-backed rather than a bare peak.

    Parameters
    ----------
    p : list of str
        The SVG fragment list being assembled; extended in place.
    diff : list of float
        The Kneedle difference curve, aligned with the data's ``k`` values.
    elbow_i : int
        Index of the peak (the elbow) in ``diff``.
    curve, accent : str
        The curve and marker hues, matched to the main panel.
    strings : dict
        Chrome-text strings for the active language.
    mono_family : str
        Monospace font stack for the numeric read-out, from
        :func:`sprezzature_figures.fonts.mono_stack_for_theme`.
    detection_rate : float, optional
        Fraction of bootstrap resamples agreeing on this elbow (0-1).
    null_p_value : float, optional
        P-value of the elbow under a no-knee null model.
    """
    ix, iy, iw, ih = 566.0, 196.0, 372.0, 176.0   # card box
    pad = 20.0
    has_evidence = detection_rate is not None or null_p_value is not None
    # Grow the card downward when evidence lines are present so the mini
    # plot never crowds against the extra text.
    ih_eff = ih + (24.0 if has_evidence else 0.0)
    p.append(
        f'<rect x="{ix:.0f}" y="{iy:.0f}" width="{iw:.0f}" height="{ih_eff:.0f}" '
        f'rx="16" fill="#F5F5F7" stroke="{HAIR}" stroke-width="1"/>'
    )
    p.append(
        f'<text x="{ix + pad:.0f}" y="{iy + 30:.0f}" font-size="15" '
        f'font-weight="700" fill="{INK}">{escape(strings["inset_title"])}</text>'
    )
    p.append(
        f'<text x="{ix + pad:.0f}" y="{iy + 51:.0f}" font-size="13" '
        f'fill="{SUBINK}">{escape(strings["inset_subtitle"])}</text>'
    )

    # Mini plot frame inside the card.
    mx0 = ix + pad
    mx1 = ix + iw - pad
    my0 = iy + 66.0                 # top of the mini plot
    my1 = iy + ih - 30.0            # baseline (evidence lines sit below this)
    dmax = max(diff) or 1.0

    def msx(i: int) -> float:
        return mx0 + i / (len(diff) - 1) * (mx1 - mx0)

    def msy(v: float) -> float:
        return my1 - (v / dmax) * (my1 - my0)

    mpts = [(msx(i), msy(v)) for i, v in enumerate(diff)]

    # Faint fill + smooth stroke for the difference curve.
    a = [f'M{fmt_compact(mpts[0][0])},{fmt_compact(my1)}']
    a.append(f'L{fmt_compact(mpts[0][0])},{fmt_compact(mpts[0][1])}')
    a.append(catmull_rom_beziers(mpts, fmt_compact))
    a.append(f'L{fmt_compact(mpts[-1][0])},{fmt_compact(my1)}Z')
    p.append(f'<path d="{"".join(a)}" fill="{curve}" fill-opacity="0.12"/>')
    ln = [f'M{fmt_compact(mpts[0][0])},{fmt_compact(mpts[0][1])}']
    ln.append(catmull_rom_beziers(mpts, fmt_compact))
    p.append(
        f'<path d="{"".join(ln)}" fill="none" stroke="{curve}" '
        f'stroke-width="2.4" stroke-linecap="round"/>'
    )
    # Mini baseline.
    p.append(
        f'<line x1="{mx0:.1f}" y1="{my1:.1f}" x2="{mx1:.1f}" y2="{my1:.1f}" '
        f'stroke="{HAIR}" stroke-width="1"/>'
    )

    # Peak marker on the difference curve, aligned with the main elbow.
    peak_x, peak_y = mpts[elbow_i]
    p.append(
        f'<line x1="{peak_x:.1f}" y1="{peak_y:.1f}" x2="{peak_x:.1f}" '
        f'y2="{my1:.1f}" stroke="{accent}" stroke-width="1.3" '
        f'stroke-dasharray="2 4"/>'
    )
    p.append(
        f'<circle cx="{peak_x:.1f}" cy="{peak_y:.1f}" r="5" fill="{BG}" '
        f'stroke="{accent}" stroke-width="2.6"/>'
    )

    if has_evidence:
        # Two compact evidence lines under the mini plot: detection rate and
        # null-model p-value, whichever were supplied. Monospace so the
        # numbers align if both a "%" and a "p =" line are present.
        ey0 = my1 + 22.0
        parts: list[str] = []
        if detection_rate is not None:
            parts.append(f'{strings["detection_rate"]}: {detection_rate:.0%}')
        if null_p_value is not None:
            parts.append(f'{strings["null_p"]}: {null_p_value:.3g}')
        p.append(
            f'<text x="{mx0:.1f}" y="{ey0:.1f}" font-family="{mono_family}" '
            f'font-size="12" fill="{SUBINK}">{escape("  ·  ".join(parts))}</text>'
        )


def make_elbow(
    data: list[dict[str, Any]] | None = None,
    *,
    out: Path | str | None = None,
    title: str = "",
    mode: str = "self-contained",
    accessibility: str = "universal",
    language: str = "en",
    x_label: str | None = None,
    y_label: str | None = None,
    ci: tuple[float, float] | None = None,
    is_clear: bool = True,
    abstain_reason: str | None = None,
    detection_rate: float | None = None,
    null_p_value: float | None = None,
    theme: str = "corporate",
) -> Path:
    """Render an elbow/knee (Kneedle) SVG and write it to ``out``.

    The standard ``make_<kind>`` entry the figure registry dispatches to.
    With no ``data``, renders the demo k-means inertia sweep (backward
    compatible with the catalog's demo-render path). Pass a real ``data``
    sweep — and, for a caller like `elbow-helper
    <https://github.com/warith-harchaoui/elbow-helper>`_ that computes its
    own uncertainty, ``ci``/``detection_rate``/``null_p_value``/``is_clear``/
    ``abstain_reason`` — to render the actual result instead of the demo.

    Parameters
    ----------
    data : list of dict, optional
        Rows of ``{"k": x_value, "inertia": y_value}``; see
        :func:`build_svg`. Defaults to the demo sweep.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/elbow.svg``.
    title : str, optional
        Accepted for dispatcher/CLI parity; unused, since the chart's title
        is derived from the data (or the abstention state).
    mode, accessibility, language : str
        Forwarded to :func:`build_svg`.
    x_label, y_label : str, optional
        Forwarded to :func:`build_svg`.
    ci : tuple of float, optional
        Forwarded to :func:`build_svg`.
    is_clear : bool, optional
        Forwarded to :func:`build_svg`.
    abstain_reason : str, optional
        Forwarded to :func:`build_svg`.
    detection_rate : float, optional
        Forwarded to :func:`build_svg`.
    null_p_value : float, optional
        Forwarded to :func:`build_svg`.
    theme : str, optional
        Visual theme. Forwarded to :func:`build_svg`.

    Returns
    -------
    Path
        Absolute path to the written SVG file.
    """
    _ = title  # accepted for dispatcher/CLI parity; see docstring
    svg = build_svg(
        data,
        mode=mode,
        accessibility=accessibility,
        language=language,
        x_label=x_label,
        y_label=y_label,
        ci=ci,
        is_clear=is_clear,
        abstain_reason=abstain_reason,
        detection_rate=detection_rate,
        null_p_value=null_p_value,
        theme=theme,
    )
    dest = Path(out) if out else svg_example_path(__file__, "elbow")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """Write the demo elbow-detection SVG to the skill's example asset folder.

    The ``--mode``/``--accessibility``/``--language`` flags (via
    :func:`_render.render_cli`) select the rendering options threaded into
    :func:`build_svg`; the demo sweep is always used from the CLI (a real
    caller with its own data uses :func:`make_elbow` as a library call, or
    ``make_figure("elbow", data=...)``).
    """
    render_cli(
        __file__,
        "elbow",
        lambda **kwargs: build_svg(None, **kwargs),
        description="Write the house-style elbow-detection (Kneedle) SVG example.",
    )


if __name__ == "__main__":
    main()
