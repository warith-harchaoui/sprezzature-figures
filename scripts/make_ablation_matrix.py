#!/usr/bin/env python3
"""
make_ablation_matrix — a house-styled ablation study as a hand-authored SVG.

An **ablation matrix** answers the question every methods paper has to
answer: *which parts of the model actually earn their place?* One row per
model variant, and for each row two things side by side:

* a **component matrix** on the left — one column per ablatable component,
  a filled dot where the variant keeps that component and a quiet hollow
  slot where it drops it, with the kept dots joined by a connector (the
  UpSet idiom, see :mod:`make_upset`), so a variant's recipe reads as a
  shape rather than as a sentence;
* one **metric panel per metric** on the right, sharing that same row axis,
  each showing the variant's score with its uncertainty interval.

Hovering or keyboard-focusing any row highlights that variant *across every
panel at once* and dims the rest, so "the row that wins on AUROC" and "the
row that wins on AUPRC" can be compared without counting rows with a finger.
The highlight is pure CSS — one ``<g>`` per row spanning the whole figure,
no JavaScript — so it survives being embedded as a bare ``<object>``.

Two design decisions worth stating, because the common way of drawing this
figure gets both wrong:

**The recipe is a matrix, not a label.** The widespread alternative writes
each variant's recipe as a concatenated string
(``"Structure + Sequence + Bchems + MMA + Transfer Learning"``). Past three
components that label is longer than the bar it annotates, every row repeats
most of its neighbour's text, and the reader has to diff two sentences to
see which single component changed. A dot matrix makes the same comparison
a vertical scan.

**Truncated axes forbid bars.** Model metrics cluster in a narrow band
(0.75–0.90 AUROC is a normal spread), so the axis has to be tightened or
every bar looks identical. But a bar encodes its *length* as the value, and
a bar chart whose axis starts at 0.75 overstates every difference by the
ratio of the truncation. The honest resolution is to change the mark, not
to hide the truncation: ``mark="dot"`` (the default) draws a position-coded
dot with its uncertainty interval, which reads correctly on any axis range.
``mark="bar"`` is available and *forces the axis back to zero*, because a
bar that does not start at zero is a misleading figure regardless of what
the caption says.

Colour in the matrix is the component's own hue, so the matrix doubles as
the legend and no separate colour key is needed. The metric marks are a
single hue: which components a row combines is read from its matrix
position, never from the colour of its dot.

Every mark is drawn at full size in its final state. There is no entrance
animation: an ablation table is a static comparison, motion would add
nothing, and a frozen first frame (a PNG export, a thumbnail) must never
look empty.

Running the module writes the SVG artifact to
``sprezzature-figures/assets/svg-examples/ablation_matrix.svg``.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _scale import nice_ticks_range  # noqa: E402
from _style import (  # noqa: E402
    BG,
    FONT_MONO,
    GRIDLINE,
    INK,
    SECONDARY,
    cycle_hues,
    load_palette,
    os_adaptive_style,
    os_dark_style,
)
from _svg import svg_open, xml_escape  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme  # noqa: E402


#: Fill for a component the variant *drops*. Light enough to read as an
#: empty slot, dark enough to stay visible on white (never `opacity`, which
#: is what makes the usual alpha-ramped version of this figure illegible).
_EMPTY = "#D6D6DB"

#: Zebra band behind every other row, so a row's dots and its metric marks
#: stay visually joined across the ~1000px the figure spans.
_ZEBRA = "#F5F5F7"

#: Keyboard focus ring, matching the rest of the catalogue.
_FOCUS = "#007AFF"

#: Separator between the pipe-joined components of one variant.
_SEP = "|"


def _make_demo_data() -> List[Dict[str, Any]]:
    """Twelve variants of a five-component model, scored on three metrics.

    Deterministic and hand-tuned rather than sampled, so the figure tells a
    readable story: the full model wins, ``Transfer`` is the single most
    valuable component, and ``MMA`` only pays off once ``Biochem`` is
    present — an interaction that is invisible in a ranked bar list and
    obvious in a matrix.
    """
    variants: List[Tuple[Tuple[str, ...], Tuple[float, float, float]]] = [
        (("Structure",), (0.771, 0.437, 0.431)),
        (("Sequence",), (0.842, 0.551, 0.427)),
        (("Structure", "Sequence"), (0.839, 0.546, 0.444)),
        (("Sequence", "Biochem"), (0.841, 0.548, 0.436)),
        (("Structure", "Sequence", "Biochem"), (0.844, 0.547, 0.441)),
        (("Structure", "Sequence", "Biochem", "MMA"), (0.861, 0.613, 0.463)),
        (("Structure", "Transfer"), (0.804, 0.497, 0.424)),
        (("Sequence", "Transfer"), (0.846, 0.567, 0.451)),
        (("Structure", "Sequence", "Transfer"), (0.845, 0.566, 0.448)),
        (("Sequence", "Biochem", "Transfer"), (0.845, 0.559, 0.446)),
        (("Structure", "Sequence", "Biochem", "Transfer"), (0.843, 0.553, 0.447)),
        (
            ("Structure", "Sequence", "Biochem", "MMA", "Transfer"),
            (0.883, 0.696, 0.517),
        ),
    ]
    metrics = ("AUROC", "AUPRC", "Mean PPVn")
    # Uncertainty shrinks as the recipe grows: more signal, steadier folds.
    errors = (0.007, 0.014, 0.009)
    rows: List[Dict[str, Any]] = []
    for components, scores in variants:
        shrink = 1.25 - 0.09 * len(components)
        for metric, value, err in zip(metrics, scores, errors):
            rows.append(
                {
                    "components": _SEP.join(components),
                    "metric": metric,
                    "value": value,
                    "error": round(err * shrink, 4),
                }
            )
    return rows


DEMO_DATA: List[Dict[str, Any]] = _make_demo_data()


def _slug(label: str) -> str:
    """A CSS-class-safe token for `label` (used to pair a row with its band)."""
    return "".join(ch if ch.isalnum() else "-" for ch in label.lower()).strip("-")


def _reshape(
    data: Optional[List[Dict[str, Any]]],
) -> Tuple[List[Tuple[str, ...]], List[str], List[str], Dict[Tuple[str, str], Tuple[float, float]]]:
    """Split the long-format rows into the four things the layout needs.

    Parameters
    ----------
    data : list of dict or None
        Long-format rows, one per (variant, metric) pair, with keys
        ``components`` (pipe-joined component names), ``metric`` (str),
        ``value`` (float) and optionally ``error`` (float, a symmetric
        half-interval; defaults to 0). Defaults to :data:`DEMO_DATA`.

    Returns
    -------
    variants : list of tuple of str
        One entry per model variant, in first-appearance order, each the
        tuple of components that variant keeps.
    components : list of str
        Every component named anywhere in the data, in first-appearance
        order. These become the matrix columns.
    metrics : list of str
        Every metric name, in first-appearance order. These become the
        panels.
    scores : dict
        ``(variant_key, metric) -> (value, error)``, where ``variant_key``
        is the row's raw ``components`` string.
    """
    rows = list(data) if data else DEMO_DATA
    variants: List[Tuple[str, ...]] = []
    seen_variants: set = set()
    components: List[str] = []
    metrics: List[str] = []
    scores: Dict[Tuple[str, str], Tuple[float, float]] = {}

    for row in rows:
        raw = str(row["components"])
        members = tuple(p.strip() for p in raw.split(_SEP) if p.strip())
        if raw not in seen_variants:
            seen_variants.add(raw)
            variants.append(members)
        for member in members:
            if member not in components:
                components.append(member)
        metric = str(row["metric"])
        if metric not in metrics:
            metrics.append(metric)
        scores[(raw, metric)] = (float(row["value"]), float(row.get("error", 0.0) or 0.0))

    return variants, components, metrics, scores


def _domain(
    values: Sequence[Tuple[float, float]], zero_based: bool
) -> Tuple[float, float, List[float]]:
    """Pick the x-domain and tick positions for one metric panel.

    Parameters
    ----------
    values : sequence of (float, float)
        The (value, error) pairs shown in this panel.
    zero_based : bool
        True when the panel draws bars, which must be anchored at zero.

    Returns
    -------
    lo, hi : float
        The panel's x-domain.
    ticks : list of float
        Tick positions inside ``[lo, hi]``.
    """
    lows = [v - e for v, e in values]
    highs = [v + e for v, e in values]
    lo, hi = (0.0 if zero_based else min(lows)), max(highs)
    span = (hi - lo) or 1.0
    if not zero_based:
        # Breathe on both sides so the leftmost dot never sits on the axis
        # line and the rightmost never touches the value column.
        lo -= span * 0.16
        hi += span * 0.16
    else:
        hi += span * 0.06
    ticks = [t for t in nice_ticks_range(lo, hi, 4) if lo <= t <= hi]
    return lo, hi, ticks


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Only the full recipe clears every metric at once",
    subtitle: str = "Each row is one model variant; filled dots are the components it keeps. Bands are 95% CI over 5 folds.",
    width: int = 1120,
    mark: str = "dot",
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full ablation-matrix SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Long-format rows; see :func:`_reshape` for the key contract.
        Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text. The title should state the takeaway, not name the chart.
    width : int
        Canvas width in pixels. The height is derived from the row count.
    mark : {"dot", "bar"}, optional
        ``"dot"`` (default) draws a position-coded dot and its uncertainty
        interval on a tightened axis — the correct mark when the metrics
        occupy a narrow band. ``"bar"`` draws length-coded bars and, because
        a bar encodes length, *forces the axis to start at zero* whatever
        the data range is.
    mode : str, optional
        Forwarded to :func:`_interactive.fullscreen_control`.
    accessibility : str, optional
        Palette accessibility level, forwarded to :func:`_style.cycle_hues`
        and :func:`_style.load_palette`.
    theme : str, optional
        Visual theme: ``"corporate"`` (default, Roboto) or ``"academic"``
        (Latin Modern + the Okabe-Ito palette).

    Returns
    -------
    str
        A complete, standalone SVG document.

    Raises
    ------
    ValueError
        If `mark` is not one of ``"dot"`` or ``"bar"``.
    """
    if mark not in ("dot", "bar"):
        raise ValueError(f"mark must be 'dot' or 'bar', got {mark!r}")

    variants, components, metrics, scores = _reshape(data)
    n_rows, n_comp, n_metrics = len(variants), len(components), len(metrics)
    comp_hues = cycle_hues(components, accessibility, theme=theme)
    palette = load_palette(accessibility, theme)
    mark_color = palette["Blue"]
    best_color = palette["Purple"]

    # ---- geometry ----
    left_pad = 40.0
    right_pad = 40.0
    top_pad = 100.0          # title (y=52) + subtitle (y=82) sit above this
    header_h = 84.0          # rotated component-column labels
    row_h = 34.0
    axis_h = 46.0
    bottom_pad = 30.0

    col_pitch = 26.0
    matrix_x0 = left_pad + 8.0
    matrix_w = n_comp * col_pitch
    matrix_y0 = top_pad + header_h

    # The value column belongs to the panel on its LEFT, so it sits close to
    # that panel's plot area and the generous gap goes *after* it. The first
    # layout had these the other way round and every number read as if it
    # labelled the next metric (found via the Ralph Eyeball Loop).
    value_w = 54.0           # right-aligned mono value column, per panel
    panel_gap = 52.0
    panels_x0 = matrix_x0 + matrix_w + 34.0
    panels_total = width - panels_x0 - right_pad
    panel_pitch = panels_total / n_metrics
    plot_w = panel_pitch - value_w - panel_gap

    rows_h = n_rows * row_h
    axis_y = matrix_y0 + rows_h + 14.0
    height = int(matrix_y0 + rows_h + axis_h + bottom_pad)

    def col_cx(i: int) -> float:
        return matrix_x0 + (i + 0.5) * col_pitch

    def row_cy(r: int) -> float:
        return matrix_y0 + (r + 0.5) * row_h

    def panel_x0(m: int) -> float:
        return panels_x0 + m * panel_pitch

    # Per-panel domains, computed once.
    domains: List[Tuple[float, float, List[float]]] = []
    for metric in metrics:
        pairs = [scores[(_SEP.join(v), metric)] for v in variants if (_SEP.join(v), metric) in scores]
        domains.append(_domain(pairs, zero_based=(mark == "bar")))

    def x_for(m: int, v: float) -> float:
        lo, hi, _ = domains[m]
        return panel_x0(m) + (v - lo) / ((hi - lo) or 1.0) * plot_w

    # Best variant per metric, so the winner can be called out rather than
    # left for the reader to find by eye.
    best_row: Dict[str, int] = {}
    for m, metric in enumerate(metrics):
        vals = [(scores.get((_SEP.join(v), metric), (float("-inf"), 0.0))[0], r) for r, v in enumerate(variants)]
        best_row[metric] = max(vals)[1]

    parts: List[str] = []
    parts.append(
        svg_open(width, height, "am-title", "am-desc", font_family=chrome_stack_for_theme(theme))
    )
    parts.append(f'<title id="am-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="am-desc">Ablation study of {n_rows} model variants over '
        f'{n_comp} components ({xml_escape(", ".join(components))}), scored on '
        f'{xml_escape(", ".join(metrics))}. Hover or focus a row to highlight that '
        f'variant across every metric panel.</desc>'
    )

    # ---- styles ----
    style_rows = [
        ".row{transition:opacity .18s ease}",
        # Hover/focus one row dims every other; untouched, the figure is
        # fully drawn.
        "svg:hover .row,svg:focus-within .row{opacity:.28}",
        ".row:hover,.row:focus,.row:focus-within{opacity:1!important}",
        ".row:focus{outline:none}",
        ".hit{cursor:pointer;fill:transparent}",
        f".hit:focus{{outline:3px solid {_FOCUS};outline-offset:-2px}}",
        "@media (prefers-reduced-motion: reduce){.row{transition:none}}",
    ]
    # Under prefers-contrast the encoding hues deepen. The component dots
    # carry identity by hue, so they deepen as fills; the metric marks and
    # their intervals deepen as fill and stroke respectively.
    style_rows.append(
        os_adaptive_style({f".c-{_slug(c)}": comp_hues[c] for c in components}, role="fill")
    )
    style_rows.append(os_adaptive_style({".mk": mark_color, ".mk-best": best_color}, role="fill"))
    style_rows.append(os_adaptive_style({".ci": mark_color}, role="stroke"))
    # Additive dark-mode block: the page darkens, ink flips via the default
    # ink map, and the two flat greys (empty slot, zebra band) drop to quiet
    # dark tones so they keep reading as "absent" and "banding" rather than
    # glaring. Encoding hues are left alone.
    style_rows.append(
        os_dark_style(
            screen_blend=False,
            extra=f'[fill="{_EMPTY}"]{{fill:#3A3A3C;}} [fill="{_ZEBRA}"]{{fill:#1A1A1C;}}',
        )
    )
    parts.append("<style>\n" + "\n".join(style_rows) + "\n</style>")

    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')

    # ---- title + subtitle ----
    parts.append(
        f'<text x="{left_pad:.0f}" y="52" font-size="26" font-weight="700" '
        f'fill="{INK}" letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(
        f'<text x="{left_pad:.0f}" y="80" font-size="15" fill="{SECONDARY}">'
        f'{xml_escape(subtitle)}</text>'
    )

    # ---- component column headers (rotated, anchored at the column) ----
    header_baseline = matrix_y0 - 12.0
    for i, comp in enumerate(components):
        cx = col_cx(i)
        parts.append(
            f'<text x="{cx:.1f}" y="{header_baseline:.1f}" font-size="13" '
            f'font-weight="600" fill="{comp_hues[comp]}" text-anchor="start" '
            f'transform="rotate(-42 {cx:.1f} {header_baseline:.1f})">'
            f'{xml_escape(comp)}</text>'
        )
    parts.append(
        f'<text x="{matrix_x0:.1f}" y="{matrix_y0 + rows_h + 30:.1f}" font-size="12" '
        f'fill="{SECONDARY}">Components kept</text>'
    )

    # ---- metric panel headers + axes ----
    for m, metric in enumerate(metrics):
        lo, hi, ticks = domains[m]
        px0 = panel_x0(m)
        parts.append(
            f'<text x="{px0:.1f}" y="{matrix_y0 - 16:.1f}" font-size="15" '
            f'font-weight="600" fill="{INK}">{xml_escape(metric)}</text>'
        )
        # Gridlines run the full row block, behind every mark.
        for t in ticks:
            gx = x_for(m, t)
            parts.append(
                f'<line x1="{gx:.1f}" y1="{matrix_y0:.1f}" x2="{gx:.1f}" '
                f'y2="{matrix_y0 + rows_h:.1f}" stroke="{GRIDLINE}" stroke-width="1"/>'
            )
            parts.append(
                f'<text x="{gx:.1f}" y="{axis_y + 14:.1f}" font-size="11" '
                f'fill="{SECONDARY}" text-anchor="middle" '
                f'font-family="{FONT_MONO}">{t:g}</text>'
            )
        if mark == "dot" and lo > 0:
            # Say it out loud rather than hiding it: the axis is tightened,
            # which is why these are dots and not bars.
            parts.append(
                f'<text x="{px0:.1f}" y="{axis_y + 32:.1f}" font-size="10.5" '
                f'fill="{SECONDARY}">axis starts at {lo:.2f}</text>'
            )

    # ---- one group per variant: zebra band, matrix dots, every metric mark ----
    for r, members in enumerate(variants):
        key = _SEP.join(members)
        cy = row_cy(r)
        band_y = matrix_y0 + r * row_h
        member_cols = [i for i, c in enumerate(components) if c in members]
        score_text = ", ".join(
            f"{mt} {scores[(key, mt)][0]:.3f} plus or minus {scores[(key, mt)][1]:.3f}"
            for mt in metrics
            if (key, mt) in scores
        )
        tip = f"{' + '.join(members)}: {score_text}"

        parts.append(f'<g class="row">')
        if r % 2 == 0:
            parts.append(
                f'<rect x="{left_pad:.1f}" y="{band_y:.1f}" '
                f'width="{width - left_pad - right_pad + 8:.1f}" height="{row_h:.1f}" '
                f'fill="{_ZEBRA}"/>'
            )

        # -- connector through the kept components --
        if len(member_cols) > 1:
            parts.append(
                f'<line x1="{col_cx(min(member_cols)):.1f}" y1="{cy:.1f}" '
                f'x2="{col_cx(max(member_cols)):.1f}" y2="{cy:.1f}" '
                f'stroke="{INK}" stroke-opacity="0.30" stroke-width="2.5" '
                f'stroke-linecap="round"/>'
            )

        # -- matrix dots: kept ones in the component's own hue --
        for i, comp in enumerate(components):
            kept = comp in members
            fill = comp_hues[comp] if kept else _EMPTY
            cls = f' class="c-{_slug(comp)}"' if kept else ""
            parts.append(
                f'<circle{cls} cx="{col_cx(i):.1f}" cy="{cy:.1f}" r="6" fill="{fill}"/>'
            )

        # -- one mark per metric panel --
        for m, metric in enumerate(metrics):
            if (key, metric) not in scores:
                continue
            value, err = scores[(key, metric)]
            is_best = best_row[metric] == r
            fill = best_color if is_best else mark_color
            cls = "mk-best" if is_best else "mk"
            vx = x_for(m, value)
            radius = 7.0 if is_best else 5.5
            # The interval is drawn BEFORE the mark, and the mark carries a
            # paper-coloured ring. Painted the other way round, an interval
            # narrower than the marker vanished *inside* it and only its
            # overshoot poked out, which both deformed the dot's silhouette
            # and hid the uncertainty on exactly the winning row the reader
            # looks at first (found via the Ralph Eyeball Loop). Caps are
            # taller than the marker so a narrow interval still reads as an
            # interval rather than as a lump.
            if err > 0:
                x_lo, x_hi = x_for(m, value - err), x_for(m, value + err)
                cap = radius + 2.5
                parts.append(
                    f'<g class="ci" stroke="{fill}" stroke-width="1.6" stroke-linecap="round">'
                    f'<line x1="{x_lo:.1f}" y1="{cy:.1f}" x2="{x_hi:.1f}" y2="{cy:.1f}"/>'
                    f'<line x1="{x_lo:.1f}" y1="{cy - cap:.1f}" x2="{x_lo:.1f}" y2="{cy + cap:.1f}"/>'
                    f'<line x1="{x_hi:.1f}" y1="{cy - cap:.1f}" x2="{x_hi:.1f}" y2="{cy + cap:.1f}"/>'
                    f'</g>'
                )
            if mark == "bar":
                bx0 = x_for(m, domains[m][0])
                parts.append(
                    f'<rect class="{cls}" x="{bx0:.1f}" y="{cy - 9:.1f}" '
                    f'width="{max(0.0, vx - bx0):.1f}" height="18" rx="4" fill="{fill}"/>'
                )
            else:
                parts.append(
                    f'<circle class="{cls}" cx="{vx:.1f}" cy="{cy:.1f}" '
                    f'r="{radius:.1f}" fill="{fill}" stroke="{BG}" stroke-width="1.5"/>'
                )
            # Right-aligned mono value column: exact numbers without any
            # chance of a label colliding with a neighbouring mark.
            parts.append(
                f'<text x="{panel_x0(m) + plot_w + value_w:.1f}" y="{cy + 4:.1f}" '
                f'font-size="12.5" font-family="{FONT_MONO}" text-anchor="end" '
                f'font-weight="{700 if is_best else 400}" '
                f'fill="{fill if is_best else INK}">{value:.3f}</text>'
            )

        # -- full-width hit rect: one hover/focus target for the whole row --
        parts.append(
            f'<rect class="hit" x="{left_pad:.1f}" y="{band_y:.1f}" '
            f'width="{width - left_pad - right_pad + 8:.1f}" height="{row_h:.1f}" '
            f'tabindex="0" role="img" aria-label="{xml_escape(tip)}">'
            f'<title>{xml_escape(tip)}</title></rect>'
        )
        parts.append("</g>")

    # ---- separators between metric panels ----
    # Drawn last so they sit above the zebra bands: without them the value
    # column of one panel and the plot area of the next read as one field.
    for m in range(1, n_metrics):
        sx = panel_x0(m) - panel_gap / 2.0
        parts.append(
            f'<line x1="{sx:.1f}" y1="{matrix_y0 - 34:.1f}" x2="{sx:.1f}" '
            f'y2="{matrix_y0 + rows_h + 6:.1f}" stroke="{GRIDLINE}" stroke-width="1"/>'
        )

    # ---- axis rule under the panels ----
    for m in range(n_metrics):
        parts.append(
            f'<line x1="{panel_x0(m):.1f}" y1="{axis_y - 8:.1f}" '
            f'x2="{panel_x0(m) + plot_w:.1f}" y2="{axis_y - 8:.1f}" '
            f'stroke="{GRIDLINE}" stroke-width="1.5"/>'
        )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_ablation_matrix(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Only the full recipe clears every metric at once",
    subtitle: str = "Each row is one model variant; filled dots are the components it keeps. Bands are 95% CI over 5 folds.",
    width: int = 1120,
    mark: str = "dot",
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render a hand-authored ablation matrix and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Long-format rows with keys ``components``, ``metric``, ``value`` and
        optionally ``error``. Defaults to :data:`DEMO_DATA`.
    out : Path, str, or None
        Output path (.svg). Defaults to
        ``assets/svg-examples/ablation_matrix.svg``.
    title, subtitle : str
        Chart text.
    width : int
        Canvas width in pixels; height follows the row count.
    mark, mode, accessibility, theme : str
        Forwarded to :func:`build_svg`.

    Returns
    -------
    Path
        Absolute path to the written SVG file.

    Examples
    --------
    >>> p = make_ablation_matrix()
    >>> p.exists()
    True
    """
    svg = build_svg(
        data,
        title=title,
        subtitle=subtitle,
        width=width,
        mark=mark,
        mode=mode,
        accessibility=accessibility,
        theme=theme,
    )
    dest = Path(out) if out else svg_example_path(__file__, "ablation_matrix")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(
        __file__,
        "ablation_matrix",
        build_svg,
        description="Generate an ablation matrix (component dot-matrix + one metric panel per metric).",
    )


if __name__ == "__main__":
    main()
