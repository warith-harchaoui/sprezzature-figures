#!/usr/bin/env python3
"""
make_dumbbell — a dumbbell (DNA / connected-dot) plot as hand-authored SVG.

A **dumbbell plot** compares two states of the same categories by
drawing, for each row, the two values as a pair of dots joined by a
short connecting segment: the "dumbbell". The length of the segment
*is* the change, so the eye reads the gap directly without arithmetic.
It is the cleanest way to show "before vs after" or "group A vs group B"
across many categories at once, and it beats a grouped bar chart because
the bars there force the reader to mentally subtract two heights while
here the distance is the message.

This generator builds the SVG string by hand (no matplotlib / seaborn /
plotly, no Vega) so the sorting-by-gap, the endpoint value labels, and
the side-aware label harmony are fully under our control, and matches the
sprezzature-* house style: Roboto, the Apple-ish palette, rounded corners, ink
``#1D1D1F``, secondary ``#6E6E73``, white background.

The fake scenario is a **gender pay gap by role** at a mid-size company:
median hourly pay for women and for men across ten job families, sorted so
the widest gap sits on top. Each row shows the two medians as dots joined
by a segment whose length is the gap; the gap in currency is printed on
the segment, and the two endpoint pay figures sit just outside their dots.
A faint reference band marks the company-wide median so a reader sees
which roles pull the average up or down. The figure is **static**: a
dumbbell already shows every gap in one still, so no motion is added: it
would reveal nothing the reader cannot already see. Each row carries a
native ``<title>`` tooltip and a :hover / :focus highlight; no JavaScript.

The final artifact is always an SVG written to
``sprezzature-figures/assets/svg-examples/dumbbell.svg``.

Usage
-----
::

    python make_dumbbell.py               # writes the SVG next to the skill
    python make_dumbbell.py --out /tmp/dumbbell.svg

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any, Dict, List

# The house-style palette and the shared XML escaper live in scripts/.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _labels import label_cell, readable_on_white  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _style import load_palette, os_adaptive_style, os_dark_style  # noqa: E402
from _svg import svg_open, tooltip_bubble, xml_escape  # noqa: E402
from _interactive import fullscreen_control  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme  # noqa: E402


# ------------------------------------------------------------------
# Communicative fake data
# ------------------------------------------------------------------
#: One entry per job family. ``category`` is the label; ``group_a`` and
#: ``group_b`` are the median hourly pay (in dollars) for each group (women,
#: men, by default -- see ``make_dumbbell``'s ``group_a_label``/
#: ``group_b_label``). Values are illustrative but internally consistent --
#: group_b out-earns group_a in every role here, and the gap is widest in
#: the highest-paid roles, the pattern most real pay audits surface. The
#: rows are *unsorted* on purpose; :func:`build_svg` sorts them by gap so
#: the story is ordered.
DEMO_DATA: List[Dict[str, Any]] = [
    {"category": "Sales director",     "group_a": 58.20, "group_b": 71.40},
    {"category": "Software engineer",  "group_a": 52.10, "group_b": 60.30},
    {"category": "Product manager",    "group_a": 55.40, "group_b": 65.90},
    {"category": "Data scientist",     "group_a": 51.80, "group_b": 58.20},
    {"category": "Marketing lead",     "group_a": 44.60, "group_b": 50.10},
    {"category": "Financial analyst",  "group_a": 41.30, "group_b": 47.80},
    {"category": "UX designer",        "group_a": 43.90, "group_b": 47.20},
    {"category": "Customer success",   "group_a": 33.70, "group_b": 37.10},
    {"category": "Recruiter",          "group_a": 34.20, "group_b": 36.40},
    {"category": "Support specialist", "group_a": 28.90, "group_b": 30.50},
]


def company_median(rows: List[Dict[str, Any]]) -> float:
    """Return the pooled median across both groups.

    Used only for the faint reference band, so a reader can see which
    categories sit above or below the overall middle. The pooled median is
    the mean of the two group values for each row, averaged — an
    illustrative summary, not a rigorous population median.

    Parameters
    ----------
    rows : list of dict
        The category records, each carrying ``group_a`` and ``group_b``.

    Returns
    -------
    float
        A single reference value.
    """
    mids = [(float(r["group_a"]) + float(r["group_b"])) / 2.0 for r in rows]
    return sum(mids) / len(mids)


def _nice_range(vmin: float, vmax: float, tick_count: int = 5) -> tuple[float, float, List[float]]:
    """A d3-style "nice numbers" axis range and tick list covering
    [vmin, vmax] with roughly `tick_count` round-number ticks.
    """
    span = max(vmax - vmin, 1e-9)
    raw_step = span / max(tick_count, 1)
    magnitude = 10 ** math.floor(math.log10(raw_step))
    residual = raw_step / magnitude
    step = (10 if residual > 5 else 5 if residual > 2 else 2 if residual > 1 else 1) * magnitude
    lo = math.floor(vmin / step) * step
    hi = math.ceil(vmax / step) * step
    ticks: List[float] = []
    t = lo
    while t <= hi + step * 1e-6:
        ticks.append(round(t, 6))
        t += step
    return lo, hi, ticks


# ------------------------------------------------------------------
# SVG assembly
# ------------------------------------------------------------------
def build_svg(
    data: List[Dict[str, Any]] | None = None,
    *,
    title: str = "Men out-earn women in every role",
    subtitle_template: str = "Median hourly pay, {a} vs {b} · the gap averages {pct}%",
    axis_title: str = "Median hourly pay (US dollars)",
    group_a_label: str = "Women",
    group_b_label: str = "Men",
    value_prefix: str = "$",
    value_suffix: str = "",
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full dumbbell-plot SVG string.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with ``category`` (str), ``group_a`` (float), ``group_b``
        (float) keys. Defaults to DEMO_DATA.
    title : str
        Chart headline.
    subtitle_template : str
        Subtitle with ``{a}``, ``{b}``, ``{pct}`` placeholders (group
        labels and the mean gap in percent).
    axis_title : str
        Value-axis caption.
    group_a_label, group_b_label : str
        Legend/tooltip labels for the two groups (``group_a``/``group_b``).
    value_prefix, value_suffix : str
        Formatting wrapped around each value label (e.g. ``"$"``/``""`` or
        ``""``/``"%"``).
    mode : str, optional
        Interactivity mode passed to :func:`_interactive.fullscreen_control`
        (``"self-contained"`` / ``"external"`` / ``"static"``).
    accessibility : str, optional
        Palette accessibility level passed to :func:`_style.load_palette`.
    theme : str, optional
        Visual theme: ``"corporate"`` (default, Roboto -- byte-identical to
        the pre-theme render) or ``"academic"`` (LaTeX-style Latin Modern).
        See :func:`sprezzature_figures.fonts.chrome_stack_for_theme`.

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    data = data if data is not None else DEMO_DATA
    palette: Dict[str, str] = load_palette(accessibility, theme=theme)
    # Purple for group A, Teal for group B: two distinct hues, neither
    # red-vs-green (CVD-safe), each carrying an explicit legend label so
    # the encoding never rides on colour alone.
    women_col = palette.get("Purple", "#AF52DE")
    men_col = palette.get("Teal", "#5AC8FA")
    # The bright teal reads fine as a *filled disk* on white, but it is far too
    # pale to use as *text* (luminance ~0.50). For the group-B value numbers we
    # darken it just enough to stay legible while keeping its teal identity, so
    # the two value columns have matched contrast (label harmony). Group A's
    # purple is already dark enough and passes through unchanged.
    men_text_col = readable_on_white(men_col)
    ink = "#1D1D1F"
    secondary = "#6E6E73"
    band = "#F5F5F7"

    # Sort by absolute gap, widest on top — the ordering *is* the argument.
    rows = sorted(data, key=lambda r: abs(float(r["group_b"]) - float(r["group_a"])), reverse=True)

    # --- canvas geometry -----------------------------------------
    # Poster-scale panel. Left gutter holds the category label; the plot
    # panel holds the dumbbells; a right gutter is reserved so the
    # rightmost value label never clips.
    width = 1280
    m_left = 70
    m_right = 70
    m_top = 208
    m_bottom = 118

    label_w = 300           # left column: category names
    plot_x = m_left + label_w
    plot_w = width - m_right - plot_x

    row_h = 74
    n_rows = len(rows)
    first_row_cy = m_top + row_h / 2
    plot_bottom = m_top + n_rows * row_h
    height = int(plot_bottom + m_bottom)

    # --- value axis ------------------------------------------------
    # "Nice" round-number headroom so the widest dumbbell and its outer
    # value label both sit comfortably inside the panel.
    all_values = [float(r["group_a"]) for r in rows] + [float(r["group_b"]) for r in rows]
    # Pad before "nice"-rounding so a dot/label pair never sits flush against
    # the plot edge, even when the raw data extremes already round to nice
    # numbers (e.g. min=10, max=20 with a step of 2 would otherwise yield
    # zero headroom).
    raw_span = max(all_values) - min(all_values) or max(abs(v) for v in all_values) or 1.0
    pad = raw_span * 0.12
    x_min, x_max, ticks = _nice_range(min(all_values) - pad, max(all_values) + pad)

    def sx(v: float) -> float:
        """Map a data value to an x pixel coordinate."""
        return plot_x + (v - x_min) / (x_max - x_min) * plot_w

    ref = company_median(rows)

    # Dot radius, big enough to read at gallery scale.
    r = 15.0

    # Aggregate for the subtitle: mean absolute gap in percentage points
    # (relative to the larger of the two group values, so it stays in
    # [0, 100] regardless of which group happens to lead a given row).
    gaps_pct = [
        100.0 * abs(float(r_["group_b"]) - float(r_["group_a"])) / max(abs(float(r_["group_b"])), abs(float(r_["group_a"])), 1e-9)
        for r_ in rows
    ]
    mean_gap_pct = round(sum(gaps_pct) / len(gaps_pct))
    widest = rows[0]
    widest_gap = abs(float(widest["group_b"]) - float(widest["group_a"]))

    parts: List[str] = []

    # --- SVG root + accessible description ------------------------
    parts.append(svg_open(width, height, "db-title", "db-desc", font_family=chrome_stack_for_theme(theme)))
    parts.append(f'<title id="db-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="db-desc">Dumbbell plot comparing {xml_escape(group_a_label)} '
        f'(purple) and {xml_escape(group_b_label)} (teal) across {n_rows} '
        f'categories, sorted by the size of the gap. Each row joins the two '
        f'values with a segment whose length is the gap. The gap averages '
        f'{mean_gap_pct}% and is widest for {xml_escape(str(widest["category"]))} at '
        f'{value_prefix}{widest_gap:.0f}{value_suffix}.</desc>'
    )

    # Hover / focus highlight only — the figure is static, so there is no
    # motion to guard with prefers-reduced-motion.
    # OS-adaptive overrides (additive; the default render stays byte-identical
    # because every rule below lives inside an @media query — the class only
    # takes over the inline fill once the query matches). The two states
    # (Women = purple, Men = teal) deepen to their high-contrast hues under
    # prefers-contrast, on the dots and their matched value numbers. forced=True
    # is safe: each state keeps a fixed side per row (women left, men right) and
    # an always-visible legend label, so identity survives with no colour.
    style_rows = [
        ".row{cursor:pointer}",
        f".row .seg{{stroke:{secondary};stroke-width:5;stroke-linecap:round}}",
        ".row:hover .rowbg,.row:focus .rowbg{fill:#F0F0F2}",
        f".row:hover .seg,.row:focus .seg{{stroke:{ink}}}",
        ".row:hover .dot,.row:focus .dot{stroke:#1D1D1F;stroke-width:2}",
        ".row:focus{outline:none}",
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}",
        ".hit:hover+.tip,.hit:focus+.tip{opacity:1}",
        "@media (prefers-reduced-motion:reduce){.tip{transition:none}}",
    ]
    women_series = {".mk-women": women_col}
    men_series = {".mk-men": men_col}
    style_rows.append(os_adaptive_style(women_series, role="fill", forced=True))
    style_rows.append(os_adaptive_style(men_series, role="fill", forced=True))
    # Additive dark mode: flip paper + the two ink tiers (data hues untouched).
    style_rows.append(os_dark_style())
    parts.append("<style>" + "".join(style_rows) + "</style>")

    # --- background ----------------------------------------------
    parts.append(f'<rect width="{width}" height="{height}" fill="#FFFFFF"/>')

    # --- title + subtitle (the takeaway) -------------------------
    parts.append(
        f'<text x="{m_left}" y="86" font-size="40" font-weight="700" '
        f'fill="{ink}">{xml_escape(title)}</text>'
    )
    subtitle = subtitle_template.format(a=group_a_label, b=group_b_label, pct=mean_gap_pct)
    parts.append(
        f'<text x="{m_left}" y="132" font-size="23" fill="{secondary}">{xml_escape(subtitle)}</text>'
    )

    # --- legend (two states) -------------------------------------
    # Pure-fill disks, labels in ink to the right — no dark ring, no halo.
    leg_y = 170
    leg_x = m_left
    lr = 11.0
    parts.append(
        f'<circle class="mk-women" cx="{leg_x + lr:.1f}" cy="{leg_y:.1f}" '
        f'r="{lr:.1f}" fill="{women_col}"/>'
    )
    parts.append(
        f'<text x="{leg_x + 2 * lr + 12:.1f}" y="{leg_y + 7:.1f}" font-size="22" '
        f'fill="{ink}">{xml_escape(group_a_label)}</text>'
    )
    leg_x2 = leg_x + 150
    parts.append(
        f'<circle class="mk-men" cx="{leg_x2 + lr:.1f}" cy="{leg_y:.1f}" '
        f'r="{lr:.1f}" fill="{men_col}"/>'
    )
    parts.append(
        f'<text x="{leg_x2 + 2 * lr + 12:.1f}" y="{leg_y + 7:.1f}" font-size="22" '
        f'fill="{ink}">{xml_escape(group_b_label)}</text>'
    )

    # --- company-median reference band ---------------------------
    # A soft grey band (not a lone dashed rule) marks the pooled median, drawn
    # first so the dumbbells sit on top. The band gives every row a shared
    # anchor and reads unmistakably as "reference", without competing for ink.
    # Its width is a fixed visual cushion, so it stays a band even though the
    # underlying value is a single point.
    ref_x = sx(ref)
    band_half = 9.0
    parts.append(
        f'<rect x="{ref_x - band_half:.1f}" y="{m_top - 6:.1f}" '
        f'width="{2 * band_half:.1f}" height="{plot_bottom - m_top + 12:.1f}" '
        f'rx="6" fill="{band}"/>'
    )
    parts.append(
        f'<line x1="{ref_x:.1f}" y1="{m_top - 6:.1f}" x2="{ref_x:.1f}" '
        f'y2="{plot_bottom + 6:.1f}" stroke="{secondary}" stroke-width="1.4" '
        f'stroke-dasharray="4 7"/>'
    )
    # Label sits above the plot, right-aligned to the band so it never crowds
    # the top row's gap chip.
    parts.append(
        f'<text x="{ref_x:.1f}" y="{m_top - 16:.1f}" font-size="17" '
        f'fill="{secondary}" text-anchor="middle">Overall median '
        f'{value_prefix}{ref:.0f}{value_suffix}</text>'
    )

    # --- x-axis gridlines (very light) ---------------------------
    for t in ticks:
        gx = sx(t)
        parts.append(
            f'<line x1="{gx:.1f}" y1="{m_top - 4:.1f}" x2="{gx:.1f}" '
            f'y2="{plot_bottom + 4:.1f}" stroke="{band}" stroke-width="1.4"/>'
        )

    # --- the dumbbells -------------------------------------------
    for i, rec in enumerate(rows):
        cy = first_row_cy + i * row_h
        w_val = float(rec["group_a"])
        m_val = float(rec["group_b"])
        xw = sx(w_val)
        xm = sx(m_val)
        # When two groups are nearly tied (e.g. $29 vs $30 against an
        # $20-$80 axis), the true-to-scale pixel gap is smaller than the
        # dots' own diameter, so the two 15px-radius circles fully overlap
        # and the connecting bar -- the whole point of a "dumbbell" -- is
        # invisible underneath them. Clamp the *drawn* separation to at
        # least one dot diameter plus a sliver of visible bar, nudging both
        # dots symmetrically outward from their true midpoint; the value
        # labels stay attached to these same nudged positions, so the text
        # is never far from the dot it names, and the numbers themselves
        # (never the drawn distance) are what carry the true reading.
        min_sep = 2.0 * r + 8.0
        sep = xm - xw
        if abs(sep) < min_sep:
            mid = (xw + xm) / 2.0
            half = min_sep / 2.0 if sep >= 0 else -min_sep / 2.0
            xw, xm = mid - half, mid + half
        gap = m_val - w_val
        gap_pct = round(100.0 * abs(gap) / max(abs(m_val), abs(w_val), 1e-9))
        category = xml_escape(str(rec["category"]))

        tip = (
            f'{category}: {group_a_label} {value_prefix}{w_val:.2f}{value_suffix} vs '
            f'{group_b_label} {value_prefix}{m_val:.2f}{value_suffix} — '
            f'gap {value_prefix}{abs(gap):.2f}{value_suffix} ({gap_pct}%)'
        )

        parts.append(f'<g class="row hit" tabindex="0" role="img" aria-label="{tip}">')
        parts.append(f"<title>{tip}</title>")

        # Full-width hover target. Transparent at rest so it never paints over
        # the company-median reference band underneath; it only fills on
        # :hover / :focus (see the stylesheet).
        parts.append(
            f'<rect class="rowbg" x="{m_left - 14:.1f}" y="{cy - row_h / 2 + 4:.1f}" '
            f'width="{width - m_left - m_right + 28:.1f}" '
            f'height="{row_h - 8:.1f}" rx="12" fill="none" pointer-events="all"/>'
        )

        # Category label (left column), right-aligned to the panel edge so
        # the names form a clean rule against the dumbbells.
        parts.append(
            f'<text x="{plot_x - 26:.1f}" y="{cy + 8:.1f}" font-size="23" '
            f'fill="{ink}" text-anchor="end">{category}</text>'
        )

        # Connecting segment (the dumbbell bar) — drawn in its finished
        # state so the static figure is complete.
        parts.append(
            f'<line class="seg" x1="{xw:.1f}" y1="{cy:.1f}" x2="{xm:.1f}" '
            f'y2="{cy:.1f}"/>'
        )

        # Endpoint dots. Pure fills, thin white keyline so a dot stays
        # crisp where it meets the segment — never a dark ring.
        parts.append(
            f'<circle class="dot mk-women" cx="{xw:.1f}" cy="{cy:.1f}" r="{r:.1f}" '
            f'fill="{women_col}" stroke="#FFFFFF" stroke-width="2"/>'
        )
        parts.append(
            f'<circle class="dot mk-men" cx="{xm:.1f}" cy="{cy:.1f}" r="{r:.1f}" '
            f'fill="{men_col}" stroke="#FFFFFF" stroke-width="2"/>'
        )

        # Endpoint value labels — side-aware harmony: the lower value
        # (women, on the left) is labelled to the LEFT of its dot; the
        # higher value (men, on the right) to the RIGHT of its dot. Each
        # in its own hue so the number ties back to the legend without a
        # second lookup.
        parts.append(
            f'<text class="mk-women" x="{xw - r - 12:.1f}" y="{cy + 7:.1f}" '
            f'font-size="20" font-family="Roboto Mono, monospace" fill="{women_col}" '
            f'font-weight="500" text-anchor="end">{value_prefix}{w_val:.0f}{value_suffix}</text>'
        )
        parts.append(
            f'<text class="mk-men" x="{xm + r + 12:.1f}" y="{cy + 7:.1f}" '
            f'font-size="20" font-family="Roboto Mono, monospace" fill="{men_text_col}" '
            f'font-weight="500">{value_prefix}{m_val:.0f}{value_suffix}</text>'
        )

        # Gap chip, centred over the segment and lifted just above it so it
        # never sits colour-on-colour with the bar. Routed through the shared
        # ``label_cell`` commons as a ``ghost`` pill (white fill, coloured
        # hairline, coloured text) so every "cell around text" in the gallery
        # is the same component. The chip is tinted teal because the gap is the
        # group_b-minus-group_a surplus — the number ties to the higher endpoint.
        mid_x = (xw + xm) / 2.0
        chip_y = cy - 27
        gap_sign = "+" if gap >= 0 else "−"
        parts.append(
            label_cell(
                mid_x,
                chip_y,
                f"{gap_sign}{value_prefix}{abs(gap):.0f}{value_suffix}",
                men_text_col,
                variant="ghost",
                size=17.0,
                weight="700",
                anchor="middle",
            )
        )

        parts.append("</g>")
        parts.append(
            tooltip_bubble(
                mid_x, chip_y - 34,
                [category, f"{group_a_label} {value_prefix}{w_val:.0f}{value_suffix} vs "
                           f"{group_b_label} {value_prefix}{m_val:.0f}{value_suffix}",
                 f"gap {gap_sign}{value_prefix}{abs(gap):.0f}{value_suffix} ({gap_pct}%)"],
                canvas_w=width, canvas_h=height, ink=ink, secondary=secondary, border=band,
            )
        )

    # --- x-axis (value scale) ------------------------------------
    axis_y = plot_bottom + 22
    parts.append(
        f'<line x1="{sx(x_min):.1f}" y1="{axis_y:.1f}" x2="{sx(x_max):.1f}" '
        f'y2="{axis_y:.1f}" stroke="{ink}" stroke-width="1.4"/>'
    )
    for t in ticks:
        px = sx(t)
        parts.append(
            f'<line x1="{px:.1f}" y1="{axis_y:.1f}" x2="{px:.1f}" '
            f'y2="{axis_y + 6:.1f}" stroke="{ink}" stroke-width="1.4"/>'
        )
        parts.append(
            f'<text x="{px:.1f}" y="{axis_y + 30:.1f}" font-size="19" '
            f'font-family="Roboto Mono, monospace" fill="{ink}" '
            f'text-anchor="middle">{value_prefix}{t:.0f}{value_suffix}</text>'
        )
    parts.append(
        f'<text x="{(sx(x_min) + sx(x_max)) / 2:.1f}" y="{axis_y + 62:.1f}" '
        f'font-size="21" fill="{ink}" text-anchor="middle">'
        f'{xml_escape(axis_title)}</text>'
    )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_dumbbell(
    data: List[Dict[str, Any]] | None = None,
    *,
    out: Path | str | None = None,
    title: str = "Men out-earn women in every role",
    subtitle_template: str = "Median hourly pay, {a} vs {b} · the gap averages {pct}%",
    axis_title: str = "Median hourly pay (US dollars)",
    group_a_label: str = "Women",
    group_b_label: str = "Men",
    value_prefix: str = "$",
    value_suffix: str = "",
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render a dumbbell plot and write it to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with ``category`` (str), ``group_a`` (float), ``group_b``
        (float) keys. Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/dumbbell.svg``.
    title : str
        Chart headline.
    subtitle_template : str
        Subtitle with ``{a}``, ``{b}``, ``{pct}`` placeholders.
    axis_title : str
        Value-axis caption.
    group_a_label, group_b_label : str
        Legend/tooltip labels for the two groups.
    value_prefix, value_suffix : str
        Formatting wrapped around each value label.
    mode : str
        Interactivity mode for the fullscreen control.
    accessibility : str
        Palette accessibility level.
    theme : str, optional
        Visual theme. Forwarded to :func:`build_svg`.

    Returns
    -------
    Path
        Absolute path to the written SVG file.

    Examples
    --------
    >>> p = make_dumbbell()
    >>> p.exists()
    True
    """
    svg = build_svg(
        data,
        title=title,
        subtitle_template=subtitle_template,
        axis_title=axis_title,
        group_a_label=group_a_label,
        group_b_label=group_b_label,
        value_prefix=value_prefix,
        value_suffix=value_suffix,
        mode=mode,
        accessibility=accessibility,
        theme=theme,
    )
    dest = Path(out) if out else svg_example_path(__file__, "dumbbell")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """Write the dumbbell-plot SVG to the canonical assets path (or --out)."""
    render_cli(__file__, "dumbbell", build_svg, description="Render the dumbbell-plot SVG.")


if __name__ == "__main__":
    main()
