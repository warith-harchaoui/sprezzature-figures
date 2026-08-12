#!/usr/bin/env python3
"""
make_radviz — RadViz multivariate projection as a hand-authored SVG.

**RadViz** (Radial Visualisation; Hoffman et al. 1997) squeezes a
high-dimensional table onto a 2-D disc using a physical *spring*
metaphor. Each of the ``D`` features is an **anchor** pinned at an
equally-spaced point on a unit circle. Every row is a ball tied to all
``D`` anchors by springs; the spring to anchor *j* pulls with a force
proportional to that row's (min-max normalised) value of feature *j*.
The ball settles at the force-balanced point — the value-weighted
average of the anchor positions:

    p_i = ( Σ_j v_ij · a_j ) / ( Σ_j v_ij )

A row that is extreme on one feature is dragged toward that anchor; a
row that is balanced across features lands near the centre. The upshot
is a *class-separation* read at a glance: if the coloured clouds pull
apart toward different rims, the raw features already carry the signal a
classifier would exploit; if they pile up in the middle, they do not.

The plot is built **by hand** as an SVG string — Vega-Lite has no
RadViz mark, and hand SVG lets each anchor and each point carry its own
``<title>`` tooltip and a CSS ``:hover`` lift. The figure is a clean
**static** poster: a RadViz projection is a settled spring layout, so
there is nothing a motion intro would reveal that the resting picture
does not already show. No matplotlib, seaborn, or plotly. Running the
module writes the SVG artifact.

The data is synthetic but communicative: three wheat-kernel varieties
(Kama, Rosa, Canadian) described by seven geometric measurements — the
shape of a real seed-sorting problem, where a grain elevator wants to
know whether cheap calliper measurements separate the varieties before
training anything.

Style follows the sprezzature-* house tokens (Roboto, Apple-system palette,
ink ``#1D1D1F`` on white, rounded corners) from ``_style.py``.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import math
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import _style
from _style import forced_color_patterns, os_adaptive_style, os_dark_style
from _svg import point_on_circle, tooltip_bubble
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _interactive import fullscreen_control  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402

# ------------------------------------------------------------------
# Canvas + layout constants (all in user-space px).
# ------------------------------------------------------------------
WIDTH: int = 1160
HEIGHT: int = 940
MARGIN_TOP: int = 132  # title + subtitle band
CX: float = 580.0  # disc centre x
CY: float = 540.0  # disc centre y
RADIUS: float = 330.0  # disc radius (anchor circle)

INK: str = "#1D1D1F"  # primary text
SUBTLE: str = "#6E6E73"  # secondary text
GRID: str = "#E5E5EA"  # hairline gridlines
WHITE: str = "#FFFFFF"

# The seven kernel measurements become the seven anchors, in the order
# they ring the disc. Short labels keep the rim legible.
# Anchor order is chosen so each variety's dominant measurements sit on
# a contiguous arc — that is what makes the three clouds pull toward
# distinct rim sectors instead of piling up in the middle. The four
# "size" measurements ring the top-right, Compactness the right, and the
# two "small / irregular" measurements the lower-left.
FEATURES: List[str] = [
    "Area",
    "Perimeter",
    "Kernel length",
    "Kernel width",
    "Compactness",
    "Asymmetry",
    "Groove length",
]

# Three wheat varieties, each a coloured cloud. Colours are pulled from
# the house palette (Blue / Orange / Green) — a categorical, CVD-aware
# triple (never rainbow), reinforced by distinct marker outlines.
CLASSES: List[Dict[str, str]] = [
    {"name": "Rosa", "color": "#FF9500"},
    {"name": "Kama", "color": "#007AFF"},
    {"name": "Canadian", "color": "#34C759"},
]


def _class_profiles() -> List[Dict[str, Any]]:
    """Return each variety's mean feature vector and spread.

    The means are hand-set so the three clouds pull toward *different*
    rim sectors — Rosa is the big, long, heavy kernel (drags toward
    Area / Perimeter / length anchors); Canadian is the small, asymmetric
    one (drags toward Asymmetry / Groove); Kama sits between them. Values
    are on the raw measurement scales of the wheat-kernel problem and are
    min-max normalised per feature before projection, exactly as RadViz
    requires.

    Returns
    -------
    list of dict
        One entry per class with ``name``, ``color``, ``mean`` (7-vector)
        and ``sd`` (7-vector of per-feature standard deviations).
    """
    # Feature order matches FEATURES:
    # Area, Perimeter, Kernel length, Kernel width, Compactness, Asymmetry, Groove
    #
    # The means are pushed apart so that, after per-feature min-max
    # scaling, each variety *peaks* on a distinct arc of anchors and sits
    # near-zero on the others — that peaked profile is what a spring
    # layout needs to fling the clouds toward different rim sectors:
    #   * Rosa — big kernel: tops Area / Perimeter / Length / Width.
    #   * Kama — round kernel: tops Compactness, mid everything else.
    #   * Canadian — small, irregular: tops Asymmetry / Groove, low size.
    return [
        {
            "name": "Rosa",
            "color": "#FF9500",
            "mean": [21.0, 16.8, 6.55, 3.90, 0.884, 2.6, 6.10],
            "sd": [0.8, 0.32, 0.16, 0.11, 0.010, 0.55, 0.18],
        },
        {
            "name": "Kama",
            "color": "#007AFF",
            "mean": [14.3, 14.2, 5.50, 3.28, 0.905, 3.0, 5.20],
            "sd": [0.7, 0.30, 0.14, 0.10, 0.008, 0.55, 0.16],
        },
        {
            "name": "Canadian",
            "color": "#34C759",
            "mean": [11.5, 13.0, 5.15, 2.80, 0.845, 5.6, 5.95],
            "sd": [0.5, 0.24, 0.11, 0.09, 0.010, 0.60, 0.15],
        },
    ]


def sample_rows(seed: int, per_class: int) -> List[Dict[str, object]]:
    """Draw a synthetic wheat-kernel table, one Gaussian cloud per class.

    Parameters
    ----------
    seed : int
        Seed for the local ``random.Random`` so the artifact is
        byte-reproducible run to run.
    per_class : int
        Kernels sampled per variety.

    Returns
    -------
    list of dict
        Each row has ``cls`` (class index), ``name`` (variety) and
        ``raw`` (the 7 measured features, pre-normalisation).
    """
    rng = random.Random(seed)
    rows: List[Dict[str, object]] = []
    for ci, prof in enumerate(_class_profiles()):
        mean = prof["mean"]
        sd = prof["sd"]
        for _ in range(per_class):
            raw = [rng.gauss(m, s) for m, s in zip(mean, sd)]  # type: ignore[arg-type]
            # Measurements are physical, so floor them at zero.
            raw = [max(0.0, v) for v in raw]
            rows.append({"cls": ci, "name": prof["name"], "raw": raw})
    return rows


#: Row-record demo data: one row per synthetic kernel, the contract's
#: ``list[dict[str, Any]]`` shape — a ``variety`` key plus one numeric key
#: per entry of :data:`FEATURES`. :func:`_kernel_rows_from_records`
#: reshapes it (or any caller-supplied row list of the same shape) into the
#: ``{"cls", "name", "raw"}`` records :func:`normalise`/:func:`project` use.
def _demo_rows() -> List[Dict[str, Any]]:
    """Flatten :func:`sample_rows` into ``{"variety", <feature>: value, ...}`` rows."""
    rows: List[Dict[str, Any]] = []
    for r in sample_rows(seed=7, per_class=60):
        raw = r["raw"]  # type: ignore[index]
        row: Dict[str, Any] = {"variety": str(r["name"])}
        for feat, v in zip(FEATURES, raw, strict=True):  # type: ignore[arg-type]
            row[feat] = round(float(v), 3)
        rows.append(row)
    return rows


DEMO_DATA: List[Dict[str, Any]] = _demo_rows()


def _kernel_rows_from_records(rows: List[Dict[str, Any]]) -> List[Dict[str, object]]:
    """Reshape ``{"variety", <feature>: value, ...}`` rows into RadViz kernel records.

    Parameters
    ----------
    rows : list of dict
        Rows with a ``variety`` key (str, matching a :data:`CLASSES` name)
        plus one numeric key per entry of :data:`FEATURES`. A variety not
        in :data:`CLASSES` is dropped (it has no anchor colour).

    Returns
    -------
    list of dict
        ``{"cls": int, "name": str, "raw": [float, ...]}`` records in
        :data:`FEATURES` order, ready for :func:`normalise`/:func:`project`.
    """
    class_index = {c["name"]: i for i, c in enumerate(CLASSES)}
    out: List[Dict[str, object]] = []
    for r in rows:
        name = str(r.get("variety", ""))
        ci = class_index.get(name)
        if ci is None:
            continue
        raw = [float(r.get(feat, 0.0)) for feat in FEATURES]
        out.append({"cls": ci, "name": name, "raw": raw})
    return out


def normalise(rows: List[Dict[str, object]]) -> None:
    """Min-max scale every feature into ``[0, 1]`` **in place**.

    RadViz weights are meaningless across features on different physical
    units (an Area of 18 would swamp a Compactness of 0.88), so each of
    the seven columns is rescaled to a common ``[0, 1]`` before the
    spring average. The scaled vector is stored back on each row under
    ``norm``.

    Parameters
    ----------
    rows : list of dict
        Rows from :func:`sample_rows`; mutated to gain a ``norm`` key.
    """
    d = len(FEATURES)
    cols = [[float(r["raw"][j]) for r in rows] for j in range(d)]  # type: ignore[index]
    lo = [min(c) for c in cols]
    hi = [max(c) for c in cols]
    for r in rows:
        raw = r["raw"]
        r["norm"] = [
            (float(raw[j]) - lo[j]) / (hi[j] - lo[j]) if hi[j] > lo[j] else 0.0  # type: ignore[index]
            for j in range(d)
        ]


def anchor_points() -> List[Tuple[float, float]]:
    """Return the (x, y) pixel of each feature anchor on the disc rim.

    Anchors are placed clockwise from the top (12 o'clock), equally
    spaced by ``2π / D``. Top-start keeps the first, most-read anchor at
    the crown of the disc.

    Returns
    -------
    list of (float, float)
        One pixel coordinate per feature, in ``FEATURES`` order.
    """
    d = len(FEATURES)
    pts: List[Tuple[float, float]] = []
    for j in range(d):
        ang = -math.pi / 2.0 + 2.0 * math.pi * j / d  # start at top, go clockwise
        pts.append(point_on_circle(CX, CY, RADIUS, ang))
    return pts


def project(norm: List[float], anchors: List[Tuple[float, float]]) -> Tuple[float, float]:
    """Spring-embed one normalised row to its resting pixel.

    Implements the RadViz force balance ``p = Σ v_j a_j / Σ v_j``: the
    value-weighted average of the anchor positions. A row that is all
    zeros (degenerate) is pinned at the centre.

    Parameters
    ----------
    norm : list of float
        The row's min-max normalised feature vector.
    anchors : list of (float, float)
        Anchor pixel coordinates from :func:`anchor_points`.

    Returns
    -------
    tuple of float
        The (x, y) pixel where the row settles.
    """
    total = sum(norm)
    if total <= 1e-12:
        return (CX, CY)
    x = sum(v * a[0] for v, a in zip(norm, anchors)) / total
    y = sum(v * a[1] for v, a in zip(norm, anchors)) / total
    return (x, y)


# ------------------------------------------------------------------
# SVG assembly
# ------------------------------------------------------------------
def _disc_and_anchors(anchors: List[Tuple[float, float]]) -> str:
    """Render the bounding circle, spoke guides and the seven anchors."""
    parts: List[str] = ['  <g class="frame" aria-hidden="true">']
    # Outer disc.
    parts.append(
        f'    <circle cx="{CX}" cy="{CY}" r="{RADIUS}" fill="none" '
        f'stroke="{GRID}" stroke-width="2"/>'
    )
    # A faint inner ring at half radius, to read distance from centre.
    parts.append(
        f'    <circle cx="{CX}" cy="{CY}" r="{RADIUS / 2:.1f}" fill="none" '
        f'stroke="{GRID}" stroke-width="1.5" stroke-dasharray="3 6"/>'
    )
    # Spokes + anchor knobs + labels.
    for (ax, ay), name in zip(anchors, FEATURES):
        parts.append(
            f'    <line x1="{CX}" y1="{CY}" x2="{ax:.1f}" y2="{ay:.1f}" '
            f'stroke="{GRID}" stroke-width="1.5"/>'
        )
        # Label placed just outside the rim, side-aware so text never
        # overhangs the disc: right labels anchor start, left labels end,
        # top / bottom labels centre, at a consistent radial gap.
        dx = ax - CX
        dy = ay - CY
        norm = math.hypot(dx, dy) or 1.0
        lx = ax + 26 * dx / norm
        ly = ay + 26 * dy / norm
        if abs(dx) < 14:
            anchor = "middle"
        elif dx > 0:
            anchor = "start"
        else:
            anchor = "end"
        vshift = 6.0 if dy >= 0 else -2.0
        parts.append(
            f'    <text x="{lx:.1f}" y="{ly + vshift:.1f}" font-size="19" '
            f'fill="{INK}" text-anchor="{anchor}" font-weight="500">{name}</text>'
        )
        anchor_tip = f"Anchor: {name}. Kernels rich in this measurement are pulled toward it."
        parts.append(
            f'    <circle class="anchor hit" tabindex="0" cx="{ax:.1f}" cy="{ay:.1f}" r="7" '
            f'fill="{INK}" stroke="{WHITE}" stroke-width="2.5" '
            f'role="img" aria-label="{anchor_tip}"/>'
        )
        parts.append(
            tooltip_bubble(
                ax, ay - 20,
                [name, "Anchor: pulls rich kernels toward it"],
                anchor="middle", canvas_w=WIDTH, canvas_h=HEIGHT,
                ink=INK, secondary=SUBTLE, border=GRID,
            )
        )
    parts.append("  </g>")
    return "\n".join(parts)


def _points(
    rows: List[Dict[str, object]],
    anchors: List[Tuple[float, float]],
    colours: Dict[str, str] | None = None,
) -> Tuple[str, List[Tuple[float, float]]]:
    """Render every kernel as a coloured dot, grouped by variety.

    Each dot is drawn in its final resting position with a thin **light**
    halo (white ring) and reduced fill opacity, so that where same-variety
    kernels pile up their outlines still read as separate marks instead of
    fusing into one flat blob. The picture is fully static.

    Parameters
    ----------
    rows : list of dict
        Per-kernel records with a class index and normalised feature vector.
    anchors : list of (float, float)
        The rim anchor positions the springs pull toward.
    colours : dict of str to str, optional
        Per-variety ``{name: hex}`` override (e.g. an accessibility-levelled
        palette). When ``None`` the shipped :data:`CLASSES` hues are used, so
        the default figure is byte-for-byte unchanged.

    Returns
    -------
    tuple of (str, list of (float, float))
        The SVG markup and, per class, the centroid pixel (for the class
        labels drawn on top).
    """
    parts: List[str] = ['  <g class="points" role="list">']
    centroids: List[Tuple[float, float]] = []
    for ci, cls in enumerate(CLASSES):
        col = (colours or {}).get(cls["name"], cls["color"])
        name = cls["name"]
        cls_rows = [r for r in rows if r["cls"] == ci]
        sx = sy = 0.0
        parts.append(
            f'    <g class="rv-{name.lower()}" role="listitem" '
            f'aria-label="{name} kernels" fill="{col}">'
        )
        for r in cls_rows:
            x, y = project(r["norm"], anchors)  # type: ignore[arg-type]
            sx += x
            sy += y
            norm_vec = r["norm"]  # type: ignore[assignment]
            dom_idx = max(range(len(norm_vec)), key=lambda j: norm_vec[j])  # type: ignore[index]
            dom_feat = FEATURES[dom_idx]
            dom_val = r["raw"][dom_idx]  # type: ignore[index]
            tip = f"{name} kernel — pulled toward {dom_feat}"
            parts.append(
                f'      <circle class="pt hit" tabindex="0" cx="{x:.1f}" cy="{y:.1f}" r="6.5" '
                f'stroke="{WHITE}" stroke-width="1.4" fill-opacity="0.78" '
                f'role="img" aria-label="{tip}"/>'
            )
            parts.append(
                tooltip_bubble(
                    x, y - 16,
                    [name, f"Dominant: {dom_feat}", f"{dom_feat}: {dom_val:.2f}"],
                    anchor="middle", canvas_w=WIDTH, canvas_h=HEIGHT,
                    ink=INK, secondary=SUBTLE, border=GRID,
                )
            )
        parts.append("    </g>")
        n = max(1, len(cls_rows))
        centroids.append((sx / n, sy / n))
    parts.append("  </g>")
    return "\n".join(parts), centroids


def _class_labels(
    centroids: List[Tuple[float, float]],
    colours: Dict[str, str] | None = None,
) -> str:
    """Draw a bold variety label near each cloud's centroid.

    Parameters
    ----------
    centroids : list of (float, float)
        The cloud-centroid pixel per variety, in :data:`CLASSES` order.
    colours : dict of str to str, optional
        Per-variety ``{name: hex}`` override (an accessibility-levelled
        palette); ``None`` keeps the shipped hues, byte-for-byte unchanged.
    """
    parts: List[str] = ['  <g class="clslabels" aria-hidden="true">']
    for (cx, cy), cls in zip(centroids, CLASSES):
        col = (colours or {}).get(cls["name"], cls["color"])
        name = cls["name"]
        # Nudge the label outward from the disc centre so it clears the
        # cloud, and paint it on the variety colour over a light (white)
        # halo — never a dark outline — so the name reads on any backdrop.
        dx = cx - CX
        dy = cy - CY
        norm = math.hypot(dx, dy) or 1.0
        lx = cx + 66 * dx / norm
        ly = cy + 66 * dy / norm
        parts.append(
            f'    <text x="{lx:.1f}" y="{ly:.1f}" font-size="24" font-weight="700" '
            f'fill="{col}" text-anchor="middle" paint-order="stroke" '
            f'stroke="{WHITE}" stroke-width="5">{name}</text>'
        )
    parts.append("  </g>")
    return "\n".join(parts)


def _legend(colours: Dict[str, str] | None = None) -> str:
    """Render the variety legend under the disc.

    Parameters
    ----------
    colours : dict of str to str, optional
        Per-variety ``{name: hex}`` override (an accessibility-levelled
        palette); ``None`` keeps the shipped hues, byte-for-byte unchanged.
    """
    lx = 60.0
    ly = HEIGHT - 42
    parts: List[str] = [f'  <g class="legend" transform="translate({lx},{ly})" aria-hidden="true">']
    x = 0.0
    for cls in CLASSES:
        col = (colours or {}).get(cls["name"], cls["color"])
        name = cls["name"]
        parts.append(
            f'    <circle class="rv-{name.lower()}" cx="{x + 8:.1f}" cy="-6" r="8" fill="{col}"/>'
        )
        parts.append(f'    <text x="{x + 26:.1f}" y="0" font-size="18" fill="{SUBTLE}">{name}</text>')
        x += 26 + 11.5 * len(name) + 34
    parts.append("  </g>")
    return "\n".join(parts)


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full RadViz SVG document as a string.

    Parameters
    ----------
    data : list of dict, optional
        Rows with a ``variety`` key plus one numeric key per
        :data:`FEATURES` entry; see :func:`_kernel_rows_from_records`.
        Defaults to :data:`DEMO_DATA`.
    mode : str, default ``"self-contained"``
        Fullscreen-control wiring for the emitted SVG:

        * ``"self-contained"`` — carry a self-revealing fullscreen button
          plus its inline script, so the standalone SVG toggles fullscreen
          on its own (the button stays hidden until the live script shows
          it, keeping the static raster byte-identical).
        * ``"external"`` — emit no button/script here; defer the control to
          a page-level module that wires every figure on the page.
        * ``"static"`` — emit nothing; a plain, non-interactive SVG.
    accessibility : str, default ``"universal"``
        Palette accessibility level (``"universal"``, ``"high-contrast"``,
        ``"monochrome"``, ``"deuteranopia"``, ``"protanopia"`` or
        ``"tritanopia"``). The ``"universal"`` default is the
        colour-vision-safe standard and leaves the shipped palette unchanged.
    theme : str, optional
        Visual theme: ``"corporate"`` (default, Roboto -- byte-identical to
        the pre-theme render) or ``"academic"`` (LaTeX-style Latin Modern).
        See :func:`sprezzature_figures.fonts.chrome_stack_for_theme`.

    Returns
    -------
    str
        A complete, self-contained SVG (fonts + colors inline), ready to
        write to disk or embed.
    """
    # Confirm the house palette is reachable (keeps make ↔ audit in sync);
    # the categorical triple is anchored on the palette's Blue/Orange/Green.
    palette = _style.load_palette(accessibility, theme=theme)
    for base in ("Blue", "Orange", "Green"):
        assert palette.get(base), f"house palette must expose {base}"

    # Level the per-variety cloud colours for the requested accessibility mode.
    # ``universal`` is the identity, so the shipped SVG stays byte-for-byte the
    # same; other levels remap the three hues so the clouds stay distinct.
    class_colours = _style.leveled_colors(
        {cls["name"]: cls["color"] for cls in CLASSES}, accessibility
    )

    rows = _kernel_rows_from_records(data if data else DEMO_DATA)
    normalise(rows)
    anchors = anchor_points()

    disc = _disc_and_anchors(anchors)
    pts_markup, centroids = _points(rows, anchors, class_colours)
    labels = _class_labels(centroids, class_colours)

    n_total = len(rows)
    n_feat = len(FEATURES)

    title = "Seven calliper measurements already separate the wheat varieties"
    subtitle = (
        "Rosa pulls to size, Kama to Compactness, Canadian to Asymmetry "
        "— the raw features already carry the signal"
    )

    header = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}" font-family="{chrome_stack_for_theme(theme)}" '
        f'role="img" aria-labelledby="rv-title rv-desc">'
    )
    title_block = (
        f'<title id="rv-title">{title}</title>'
        f'<desc id="rv-desc">RadViz projection of {n_total} synthetic wheat kernels from '
        f"three varieties (Kama, Rosa, Canadian), each described by {n_feat} geometric "
        f"measurements. The measurements are anchors equally spaced on a circle; every "
        f"kernel sits at the value-weighted average of the anchors it scores high on, as "
        f"if pulled by springs. The three coloured clouds pull apart toward different rim "
        f"sectors, so the raw measurements carry the variety signal a classifier would "
        f"use. {subtitle}.</desc>"
    )
    # OS-adaptive overrides (additive; every rule lives inside an @media block,
    # so the default render is byte-for-byte unchanged). Each variety carries a
    # ``.rv-<name>`` class on its dot group, centroid label and legend disk.
    # Under prefers-contrast the three cloud hues deepen together to their
    # high-contrast spacing, keeping the clouds separable (role="fill" only, so
    # each dot's white keyline and each label's white halo are untouched).
    # Under forced-colors (Windows High Contrast) the ~4-colour system palette
    # cannot preserve three intermixed cloud hues, so each variety is instead
    # handed a distinct Canvas/CanvasText PATTERN (hatch / dots / cross) via
    # forced_color_patterns: the dot group, centroid label and legend disk of a
    # variety all take that pattern, so the three clouds stay separable even where
    # they overlap and colour is stripped.
    rv_series = [f".rv-{cls['name'].lower()}" for cls in CLASSES]
    contrast_block = os_adaptive_style(
        {sel: class_colours[cls["name"]] for sel, cls in zip(rv_series, CLASSES)},
        role="fill",
    )
    fcp_defs, fcp_style = forced_color_patterns(rv_series, prefix="rv-fcp")
    style = f"""  <style>
    .pt {{ transition: r .12s ease; }}
    .pt:hover {{ r: 9; fill-opacity: 1; }}
    .anchor {{ transition: r .12s ease; }}
    .anchor:hover {{ r: 10; }}
    text {{ fill: {INK}; }}
    .tip{{opacity:0;pointer-events:none;transition:opacity .12s ease}}
    .hit:hover+.tip,.hit:focus+.tip{{opacity:1}}
    @media (prefers-reduced-motion: reduce){{.tip{{transition:none}}}}
{contrast_block}
{fcp_style}
{os_dark_style(extra='text{fill:#F2F2F7;}[stroke="#E5E5EA"]{stroke:#2C2C2E;}')}
  </style>
  <defs>{fcp_defs}</defs>"""
    bg = f'  <rect width="{WIDTH}" height="{HEIGHT}" fill="{WHITE}"/>'
    title_text = (
        f'  <text x="60" y="58" font-size="30" font-weight="700" fill="{INK}">'
        f"Seven measurements separate the wheat varieties</text>"
    )
    subtitle_text = (
        f'  <text x="60" y="92" font-size="19" fill="{SUBTLE}">{subtitle}</text>'
    )
    # "Roboto Mono, monospace" (not the canonical _style.FONT_MONO stack) is
    # this figure's pre-existing literal -- kept verbatim for the corporate
    # default so byte identity holds; only academic swaps it for real.
    caption_mono = "Roboto Mono, monospace" if theme == "corporate" else mono_stack_for_theme(theme)
    caption = (
        f'  <text x="60" y="118" font-size="15" fill="{SUBTLE}" '
        f'font-family="{caption_mono}">RadViz spring layout · '
        f"{n_total} kernels · {n_feat} anchors</text>"
    )

    body = "\n".join(
        [
            header,
            title_block,
            style,
            bg,
            title_text,
            subtitle_text,
            caption,
            f'  <g transform="translate(0,{MARGIN_TOP - 132})">',
            disc,
            pts_markup,
            labels,
            "  </g>",
            _legend(class_colours),
            fullscreen_control(WIDTH, HEIGHT, mode),
            "</svg>",
        ]
    )
    return body


def make_radviz(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "",
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render the RadViz projection and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with a ``variety`` key (str) plus one numeric key per
        :data:`FEATURES` entry (``"Area"``, ``"Perimeter"``, ...).
        Defaults to :data:`DEMO_DATA`.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/radviz.svg``.
    title : str, optional
        Accepted for signature parity; the figure's headline is baked into
        the takeaway text (unused).
    mode, accessibility : str
        Forwarded to :func:`build_svg`.
    theme : str, optional
        Visual theme. Forwarded to :func:`build_svg`.

    Returns
    -------
    Path
        Absolute path to the written SVG file.
    """
    _ = title
    svg = build_svg(data, mode=mode, accessibility=accessibility, theme=theme)
    dest = Path(out) if out else svg_example_path(__file__, "radviz")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """Build the SVG and write it to the skill's asset directory."""
    render_cli(__file__, "radviz", build_svg, description="Render the RadViz SVG.")


if __name__ == "__main__":
    main()
