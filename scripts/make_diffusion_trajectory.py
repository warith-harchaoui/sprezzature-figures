#!/usr/bin/env python3
"""
make_diffusion_trajectory — a diffusion process over a point cloud, as an
animated hand-authored SVG.

A **diffusion trajectory** shows what a forward noising process does to
structured data: a point cloud that starts on a manifold (here a 2-D swiss
roll) is pushed, step by step, toward isotropic noise, and then walked back.
The figure is built so the *loss of structure* is the thing you see, not just
"the dots moved":

* the **neighbourhood graph is computed once, on the clean data, and then
  held fixed**. Its edges are dragged along by their endpoints, so at high
  noise the graph is a visible tangle of long-range edges that used to be
  short. A cloud that merely looked "more spread out" would tell you nothing;
  a scrambled graph tells you the neighbourhoods are gone.
* each point **keeps its colour** — its arc position on the original
  manifold — for the whole trajectory, so mixing is legible: when the viridis
  ramp stops being ordered in space, the manifold is gone.
* the loop runs **forward then backward** (noising, then denoising), which is
  both the actual shape of a diffusion model's two processes and a seamless
  loop with no jump cut.

Three things the usual static version of this figure omits, and which are
supplied here: a scale (the panel is a real axis box, not a floating blob), a
colour key, and the noise schedule itself — a small σ-versus-step chart whose
cursor moves in sync, so the animation is tied to a quantity rather than to
vibes.

The animation is pure SMIL on ``cx``/``cy``/``x1``/``y1``/``x2``/``y2``: no
JavaScript is needed to run it. The one small script present honours
``prefers-reduced-motion`` by pausing at the first frame. That first frame is
the *clean data*, fully drawn — so a PNG export, a thumbnail, or a reader who
has asked for no motion all get a complete, meaningful figure rather than a
blank or half-formed one. The filmstrip along the bottom carries every step
statically for the same reason: the figure is readable with the motion
removed entirely.

Running the module writes the SVG artifact to
``sprezzature-figures/assets/svg-examples/diffusion_trajectory.svg``.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
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
from _style import BG, FONT_MONO, GRIDLINE, INK, SECONDARY, os_dark_style  # noqa: E402
from _svg import svg_open, viridis, xml_escape  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme  # noqa: E402


#: Points in the demo cloud. Two forces set this. Document weight grows
#: linearly (every point and every edge carries its own SMIL keyframe list),
#: and — the binding one — the graph has to be *visible*: at 110 points the
#: spacing along the spiral fell below the dot diameter and the edges, which
#: are the whole premise of the figure, were completely hidden behind their
#: own endpoints at 1x zoom. Found via the Ralph Eyeball Loop, where they
#: only appeared at 3x.
_N_POINTS = 76

#: Neighbours per point in the fixed graph (mutual pairs are de-duplicated).
#: Two is right for a 1-D manifold: it recovers the sequential chain along
#: the spiral, which is exactly the structure the noise destroys.
_K = 2

#: Noise steps in the forward process. The animation plays these forward and
#: then back, so the loop has ``2 * _N_STEPS - 1`` keyframes.
_N_STEPS = 10

#: Seed for the demo cloud and its noise draw. Fixed so the artifact is
#: byte-reproducible across runs and machines.
_SEED = 20260906

#: Keyboard focus ring, matching the rest of the catalogue.
_FOCUS = "#007AFF"

#: Each keyframe is emitted twice in a row. SMIL spaces a bare ``values``
#: list evenly, so a repeated frame spends its first slot holding still and
#: its second morphing into the next -- the eye gets to settle on each noise
#: level, and the document carries no ``keyTimes`` attribute at all. That
#: attribute was ~215 KB of the first draft, repeated identically across
#: every one of the ~900 ``<animate>`` tags.
_HOLD_REPEAT = 2


def _make_demo_data() -> List[Dict[str, Any]]:
    """A 2-D swiss roll pushed through a cosine noise schedule.

    Returns long-format rows, one per (step, point): the same contract
    :func:`build_svg` accepts from a caller. The forward marginal is the
    standard one, ``x_t = sqrt(a_t) * x_0 + sqrt(1 - a_t) * eps``, with
    ``eps`` drawn **once per point** and reused at every step, so each point
    travels a straight, smooth line toward its own noise target instead of
    jittering independently at each frame.
    """
    rng = random.Random(_SEED)
    rows: List[Dict[str, Any]] = []

    # Clean manifold: a spiral, sampled by arc parameter with a little
    # thickness so it reads as a band rather than a wire.
    base: List[Tuple[float, float, float]] = []
    for i in range(_N_POINTS):
        u = i / (_N_POINTS - 1)
        t = 1.6 * math.pi * (1.0 + 1.9 * u)
        jitter = (rng.random() - 0.5) * 0.9
        base.append(((t + jitter) * math.cos(t), (t + jitter) * math.sin(t), u))

    # Normalise to zero mean and unit variance, the same preprocessing a real
    # diffusion model applies. Without it the clean cloud is several times
    # smaller than its own noise target, so a domain fixed across all steps
    # (which it must be, or the collapse hides behind a rescaling axis) leaves
    # the first frames as a speck in an empty panel.
    mx = sum(b[0] for b in base) / len(base)
    my = sum(b[1] for b in base) / len(base)
    var = sum((b[0] - mx) ** 2 + (b[1] - my) ** 2 for b in base) / (2 * len(base))
    sd = math.sqrt(var) or 1.0
    base = [((x - mx) / sd, (y - my) / sd, u) for x, y, u in base]

    # One fixed noise target per point.
    eps = [(rng.gauss(0.0, 1.0), rng.gauss(0.0, 1.0)) for _ in range(_N_POINTS)]

    for s in range(_N_STEPS):
        # Cosine schedule: alpha_bar goes 1 -> ~0 with a gentle start, so the
        # early steps still show structure and the interesting collapse is
        # spread over several frames instead of happening in one.
        frac = s / (_N_STEPS - 1)
        alpha_bar = math.cos(frac * math.pi / 2.0) ** 2
        keep = math.sqrt(max(0.0, alpha_bar))
        add = math.sqrt(max(0.0, 1.0 - alpha_bar))
        for i, (x0, y0, u) in enumerate(base):
            ex, ey = eps[i]
            rows.append(
                {
                    "step": s,
                    "point": i,
                    "x": keep * x0 + add * ex,
                    "y": keep * y0 + add * ey,
                    "value": u,
                    "sigma": round(add, 3),
                }
            )
    return rows


DEMO_DATA: List[Dict[str, Any]] = _make_demo_data()


def _reshape(
    data: Optional[List[Dict[str, Any]]],
) -> Tuple[List[int], Dict[int, Dict[int, Tuple[float, float]]], Dict[int, float], Dict[int, float]]:
    """Group the long-format rows by step.

    Parameters
    ----------
    data : list of dict or None
        Long-format rows with keys ``step`` (ordinal), ``point`` (id),
        ``x``, ``y`` (float), ``value`` (float in [0, 1], the colour
        variable) and optionally ``sigma`` (float, the step's noise level,
        used only as a label). Defaults to :data:`DEMO_DATA`.

    Returns
    -------
    steps : list of int
        Sorted step ordinals.
    coords : dict
        ``step -> {point -> (x, y)}``.
    values : dict
        ``point -> value``, the colour variable (taken from any step; it is
        a property of the point, not of the step).
    sigmas : dict
        ``step -> sigma``. Missing sigmas fall back to the step ordinal.
    """
    rows = list(data) if data else DEMO_DATA
    coords: Dict[int, Dict[int, Tuple[float, float]]] = {}
    values: Dict[int, float] = {}
    sigmas: Dict[int, float] = {}
    for row in rows:
        s, p = int(row["step"]), int(row["point"])
        coords.setdefault(s, {})[p] = (float(row["x"]), float(row["y"]))
        values.setdefault(p, float(row.get("value", 0.0)))
        if "sigma" in row:
            sigmas[s] = float(row["sigma"])
    steps = sorted(coords)
    for s in steps:
        sigmas.setdefault(s, float(s))
    return steps, coords, values, sigmas


def _knn_edges(points: Dict[int, Tuple[float, float]], k: int) -> List[Tuple[int, int]]:
    """De-duplicated k-nearest-neighbour pairs over `points`.

    Computed once, on the clean (first-step) cloud, and then held fixed for
    the whole trajectory: the edges are what make the loss of neighbourhood
    structure visible.
    """
    ids = sorted(points)
    edges: set = set()
    for i in ids:
        xi, yi = points[i]
        near = sorted(
            (math.hypot(points[j][0] - xi, points[j][1] - yi), j) for j in ids if j != i
        )[:k]
        for _, j in near:
            edges.add((min(i, j), max(i, j)))
    return sorted(edges)


def _keyframes(n_steps: int) -> List[int]:
    """The sequence of step indices one animation loop visits.

    Forward through every step and then back to the start, so the loop is
    seamless *and* shows both halves of a diffusion model: the forward
    noising process and the reverse denoising one. Each index is repeated
    :data:`_HOLD_REPEAT` times so that an evenly spaced ``values`` list
    alternates hold and morph without needing a ``keyTimes`` attribute.
    """
    order = list(range(n_steps)) + list(range(n_steps - 2, -1, -1))
    return [f for f in order for _ in range(_HOLD_REPEAT)]


def _vals(seq: List[float]) -> str:
    """Format one SMIL ``values`` list at whole-pixel precision.

    Sub-pixel coordinates are invisible at any realistic render scale and
    cost roughly a fifth of the document's size across ~900 keyframe lists.
    """
    return ";".join(f"{v:.0f}" for v in seq)


def _mini_chart(
    x0: float,
    y0: float,
    w: float,
    h: float,
    series: List[float],
    order: List[int],
    *,
    heading: str,
    lo_label: str,
    hi_label: str,
    dur: str,
    cursor: str,
) -> List[str]:
    """One small step-indexed line chart with a cursor synced to the animation.

    Used for both side-column readouts. Their point is to tie the motion in
    the main panel to a *quantity*: without them the animation shows that
    something is happening but never says how much, which is the gap the
    usual static version of this figure leaves open.

    Parameters
    ----------
    x0, y0, w, h : float
        The chart's box in user space (the heading sits above ``y0``).
    series : list of float
        One value per step, in step order. Scaled to its own maximum.
    order : list of int
        Step indices the animation visits, from :func:`_keyframes`; the
        cursor walks the same path so the two readouts and the main panel
        never drift apart.
    heading, lo_label, hi_label : str
        Chart title, and the labels under the first and last step.
    dur : str
        SMIL duration string, e.g. ``"14s"``.
    cursor : str
        Cursor fill colour.

    Returns
    -------
    list of str
        SVG fragments, in draw order.
    """
    out: List[str] = []
    top = max(series) or 1.0
    n = len(series)
    pts = [
        (x0 + (i / max(1, n - 1)) * w, y0 + h - (v / top) * h)
        for i, v in enumerate(series)
    ]
    out.append(
        f'<text x="{x0:.1f}" y="{y0 - 14:.1f}" font-size="13" font-weight="600" '
        f'fill="{INK}">{xml_escape(heading)}</text>'
    )
    out.append(
        f'<line x1="{x0:.1f}" y1="{y0 + h:.1f}" x2="{x0 + w:.1f}" y2="{y0 + h:.1f}" '
        f'stroke="{GRIDLINE}" stroke-width="1.5"/>'
    )
    out.append(
        f'<polyline fill="none" stroke="{INK}" stroke-opacity="0.45" stroke-width="2" '
        f'points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in pts)}"/>'
    )
    for px, py in pts:
        out.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="2.6" fill="{INK}" fill-opacity="0.45"/>')
    out.append(
        f'<text x="{x0:.1f}" y="{y0 + h + 17:.1f}" font-size="11" fill="{SECONDARY}" '
        f'font-family="{FONT_MONO}">{xml_escape(lo_label)}</text>'
    )
    out.append(
        f'<text x="{x0 + w:.1f}" y="{y0 + h + 17:.1f}" font-size="11" fill="{SECONDARY}" '
        f'font-family="{FONT_MONO}" text-anchor="end">{xml_escape(hi_label)}</text>'
    )
    cx = [pts[i][0] for i in order]
    cy = [pts[i][1] for i in order]
    out.append(
        f'<circle cx="{cx[0]:.1f}" cy="{cy[0]:.1f}" r="6" fill="{cursor}" '
        f'stroke="{BG}" stroke-width="2">'
        f'<animate attributeName="cx" values="{_vals(cx)}" dur="{dur}" repeatCount="indefinite"/>'
        f'<animate attributeName="cy" values="{_vals(cy)}" dur="{dur}" repeatCount="indefinite"/>'
        f'</circle>'
    )
    return out


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Noise does not spread the manifold out — it shreds it",
    subtitle: str = "A fixed nearest-neighbour graph dragged through a cosine noise schedule, forward then back. Colour is each point's original position along the spiral.",
    width: int = 980,
    duration: float = 14.0,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the animated diffusion-trajectory SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Long-format rows; see :func:`_reshape` for the key contract.
        Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text. The title should state the takeaway, not name the chart.
    width : int
        Canvas width in pixels; the height follows from the layout.
    duration : float, optional
        Seconds for one full forward-and-back loop.
    mode : str, optional
        Forwarded to :func:`_interactive.fullscreen_control`.
    accessibility : str, optional
        Accepted for CLI parity but a documented no-op: the only colour
        encoding is the viridis ramp, which is colour-vision-deficiency-safe
        by construction, and structure is carried by position and by the
        graph, never by hue alone.
    theme : str, optional
        Visual theme: ``"corporate"`` (default, Roboto) or ``"academic"``
        (Latin Modern).

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    _ = accessibility
    steps, coords, values, sigmas = _reshape(data)
    n_steps = len(steps)
    point_ids = sorted(values)

    # ---- geometry ----
    left_pad = 40.0
    right_pad = 40.0
    panel_y0 = 124.0
    panel_size = 470.0
    panel_x0 = left_pad
    side_x0 = panel_x0 + panel_size + 46.0
    side_w = width - side_x0 - right_pad

    strip_y0 = panel_y0 + panel_size + 46.0
    strip_gap = 8.0
    strip_w = width - left_pad - right_pad
    thumb = (strip_w - (n_steps - 1) * strip_gap) / n_steps
    height = int(strip_y0 + thumb + 52.0)

    # A single domain across every step, so the cloud never rescales between
    # frames — a rescaling axis would hide exactly the growth this figure is
    # about.
    all_x = [p[0] for s in steps for p in coords[s].values()]
    all_y = [p[1] for s in steps for p in coords[s].values()]
    span = max(max(all_x) - min(all_x), max(all_y) - min(all_y)) or 1.0
    cx_data = (max(all_x) + min(all_x)) / 2.0
    cy_data = (max(all_y) + min(all_y)) / 2.0
    lo_x, lo_y = cx_data - span / 2.0, cy_data - span / 2.0

    def project(x: float, y: float, ox: float, oy: float, size: float) -> Tuple[float, float]:
        pad = size * 0.05
        inner = size - 2 * pad
        px = ox + pad + (x - lo_x) / span * inner
        # SVG y grows downward; flip so the data reads the usual way up.
        py = oy + pad + inner - (y - lo_y) / span * inner
        return px, py

    edges = _knn_edges(coords[steps[0]], _K)
    order = _keyframes(n_steps)
    dur = f"{duration:g}s"

    parts: List[str] = []
    parts.append(
        svg_open(width, height, "dt-title", "dt-desc", font_family=chrome_stack_for_theme(theme))
    )
    parts.append(f'<title id="dt-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="dt-desc">{_N_POINTS if not data else len(point_ids)} points sampled on a '
        f'2-D spiral, shown across {n_steps} noise levels from sigma '
        f'{sigmas[steps[0]]:g} to {sigmas[steps[-1]]:g}. A {_K}-nearest-neighbour graph '
        f'computed on the clean data is held fixed and dragged along, so the loss of '
        f'neighbourhood structure is visible as tangling. The filmstrip below shows every '
        f'step statically; the main panel animates through them and back.</desc>'
    )

    style_rows = [
        f".pt{{stroke:{BG};stroke-width:0.8}}",
        ".eg{stroke-linecap:round}",
        ".hit{cursor:pointer;fill:transparent}",
        f".hit:focus{{outline:3px solid {_FOCUS};outline-offset:2px}}",
        os_dark_style(
            screen_blend=False,
            extra=f'[fill="{GRIDLINE}"]{{fill:#2C2C2E;}} .pt{{stroke:#000;}}',
        ),
    ]
    parts.append("<style>\n" + "\n".join(style_rows) + "\n</style>")
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')

    parts.append(
        f'<text x="{left_pad:.0f}" y="52" font-size="26" font-weight="700" '
        f'fill="{INK}" letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    for i, line in enumerate(_wrap(subtitle, 118)):
        parts.append(
            f'<text x="{left_pad:.0f}" y="{78 + i * 20:.0f}" font-size="14.5" '
            f'fill="{SECONDARY}">{xml_escape(line)}</text>'
        )

    # ---- main panel frame ----
    parts.append(
        f'<rect x="{panel_x0:.1f}" y="{panel_y0:.1f}" width="{panel_size:.1f}" '
        f'height="{panel_size:.1f}" fill="none" stroke="{GRIDLINE}" stroke-width="1.5" rx="8"/>'
    )

    # ---- animated edges (drawn first: they sit under the points) ----
    for a, b in edges:
        xa: List[float] = []
        ya: List[float] = []
        xb: List[float] = []
        yb: List[float] = []
        for s_idx in order:
            s = steps[s_idx]
            pax, pay = project(*coords[s][a], panel_x0, panel_y0, panel_size)
            pbx, pby = project(*coords[s][b], panel_x0, panel_y0, panel_size)
            xa.append(pax)
            ya.append(pay)
            xb.append(pbx)
            yb.append(pby)
        parts.append(
            f'<line class="eg" x1="{xa[0]:.1f}" y1="{ya[0]:.1f}" x2="{xb[0]:.1f}" '
            f'y2="{yb[0]:.1f}" stroke="{INK}" stroke-opacity="0.42" stroke-width="1.4">'
            f'<animate attributeName="x1" values="{_vals(xa)}" dur="{dur}" repeatCount="indefinite"/>'
            f'<animate attributeName="y1" values="{_vals(ya)}" dur="{dur}" repeatCount="indefinite"/>'
            f'<animate attributeName="x2" values="{_vals(xb)}" dur="{dur}" repeatCount="indefinite"/>'
            f'<animate attributeName="y2" values="{_vals(yb)}" dur="{dur}" repeatCount="indefinite"/>'
            f'</line>'
        )

    # ---- animated points ----
    for p in point_ids:
        px: List[float] = []
        py: List[float] = []
        for s_idx in order:
            s = steps[s_idx]
            qx, qy = project(*coords[s][p], panel_x0, panel_y0, panel_size)
            px.append(qx)
            py.append(qy)
        fill = viridis(values[p])
        parts.append(
            f'<circle class="pt" cx="{px[0]:.1f}" cy="{py[0]:.1f}" r="3.5" fill="{fill}">'
            f'<title>Point {p}: position {values[p]:.2f} along the spiral</title>'
            f'<animate attributeName="cx" values="{_vals(px)}" dur="{dur}" repeatCount="indefinite"/>'
            f'<animate attributeName="cy" values="{_vals(py)}" dur="{dur}" repeatCount="indefinite"/>'
            f'</circle>'
        )

    # ---- side column: colour key + noise schedule ----
    sy = panel_y0 + 6.0
    parts.append(
        f'<text x="{side_x0:.1f}" y="{sy:.1f}" font-size="13" font-weight="600" '
        f'fill="{INK}">Position along the spiral</text>'
    )
    ramp_y = sy + 12.0
    ramp_h = 14.0
    n_swatch = 40
    for i in range(n_swatch):
        parts.append(
            f'<rect x="{side_x0 + i * side_w / n_swatch:.2f}" y="{ramp_y:.1f}" '
            f'width="{side_w / n_swatch + 0.6:.2f}" height="{ramp_h:.1f}" '
            f'fill="{viridis(i / (n_swatch - 1))}"/>'
        )
    parts.append(
        f'<text x="{side_x0:.1f}" y="{ramp_y + ramp_h + 15:.1f}" font-size="11.5" '
        f'fill="{SECONDARY}">inner end</text>'
    )
    parts.append(
        f'<text x="{side_x0 + side_w:.1f}" y="{ramp_y + ramp_h + 15:.1f}" font-size="11.5" '
        f'fill="{SECONDARY}" text-anchor="end">outer end</text>'
    )

    # Two synced readouts. The schedule says how much noise is being added;
    # the neighbour distance says what that noise did to the graph. The second
    # is the number the usual static version of this figure leaves the reader
    # to guess at from a pairwise-distance heatmap.
    chart_h = 118.0
    sched_y0 = ramp_y + ramp_h + 54.0
    parts.extend(
        _mini_chart(
            side_x0, sched_y0, side_w, chart_h,
            [sigmas[s] for s in steps], order,
            heading="Noise added (σ)",
            lo_label=f"σ {sigmas[steps[0]]:.2f}",
            hi_label=f"σ {sigmas[steps[-1]]:.2f}",
            dur=dur, cursor=_FOCUS,
        )
    )

    # How many of the clean data's nearest-neighbour pairs are STILL nearest
    # neighbours at each step. The first draft plotted mean edge *length*
    # instead, which for independent noise is just sigma * sqrt(2) — the same
    # curve as the chart above it, drawn twice. Retention is the measure that
    # is not a restatement of the schedule: it falls off a cliff early, so the
    # figure can say that most of the structure is gone well before the cloud
    # merely *looks* random.
    base_edges = set(edges)
    retention = [
        len(set(_knn_edges(coords[s], _K)) & base_edges) / max(1, len(base_edges))
        for s in steps
    ]
    dist_y0 = sched_y0 + chart_h + 74.0
    parts.extend(
        _mini_chart(
            side_x0, dist_y0, side_w, chart_h,
            retention, order,
            heading="Neighbours still neighbours",
            lo_label="100%",
            hi_label=f"{retention[-1] * 100:.0f}%",
            dur=dur, cursor=_FOCUS,
        )
    )

    # ---- filmstrip: every step, statically ----
    parts.append(
        f'<text x="{left_pad:.1f}" y="{strip_y0 - 14:.1f}" font-size="13" '
        f'font-weight="600" fill="{INK}">Every step, held still</text>'
    )
    for i, s in enumerate(steps):
        ox = left_pad + i * (thumb + strip_gap)
        parts.append(
            f'<rect x="{ox:.1f}" y="{strip_y0:.1f}" width="{thumb:.1f}" height="{thumb:.1f}" '
            f'fill="none" stroke="{GRIDLINE}" stroke-width="1" rx="5"/>'
        )
        for p in point_ids:
            qx, qy = project(*coords[s][p], ox, strip_y0, thumb)
            parts.append(
                f'<circle cx="{qx:.1f}" cy="{qy:.1f}" r="1.5" fill="{viridis(values[p])}"/>'
            )
        parts.append(
            f'<text x="{ox + thumb / 2:.1f}" y="{strip_y0 + thumb + 16:.1f}" font-size="10.5" '
            f'fill="{SECONDARY}" text-anchor="middle" font-family="{FONT_MONO}">'
            f'{sigmas[s]:.2f}</text>'
        )
    # Sliding highlight, in sync with the main panel.
    hx = [left_pad + i * (thumb + strip_gap) - 2.0 for i in order]
    parts.append(
        f'<rect x="{hx[0]:.1f}" y="{strip_y0 - 2:.1f}" width="{thumb + 4:.1f}" '
        f'height="{thumb + 4:.1f}" fill="none" stroke="{_FOCUS}" stroke-width="2.5" rx="7">'
        f'<animate attributeName="x" values="{_vals(hx)}" dur="{dur}" repeatCount="indefinite"/>'
        f'</rect>'
    )
    parts.append(
        f'<text x="{left_pad:.1f}" y="{strip_y0 + thumb + 36:.1f}" font-size="11.5" '
        f'fill="{SECONDARY}">σ, the standard deviation of the noise added at each step</text>'
    )

    # Honour prefers-reduced-motion: freeze on the first frame, which is the
    # clean data — a complete figure, not a half-formed one. The filmstrip
    # above already tells the whole story without any motion.
    parts.append(
        '<script><![CDATA['
        '(function(){var s=document.documentElement;try{'
        'if(matchMedia("(prefers-reduced-motion: reduce)").matches){'
        's.pauseAnimations();s.setCurrentTime(0);}}catch(e){}})();'
        ']]></script>'
    )
    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def _wrap(text: str, width: int) -> List[str]:
    """Greedy word wrap for the subtitle, which is longer than one line."""
    words = text.split()
    lines: List[str] = []
    cur = ""
    for w in words:
        candidate = f"{cur} {w}".strip()
        if len(candidate) > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = candidate
    if cur:
        lines.append(cur)
    return lines


def make_diffusion_trajectory(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Noise does not spread the manifold out — it shreds it",
    subtitle: str = "A fixed nearest-neighbour graph dragged through a cosine noise schedule, forward then back. Colour is each point's original position along the spiral.",
    width: int = 980,
    duration: float = 14.0,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render the animated diffusion trajectory and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Long-format rows with keys ``step``, ``point``, ``x``, ``y``,
        ``value`` and optionally ``sigma``. Defaults to :data:`DEMO_DATA`.
    out : Path, str, or None
        Output path (.svg). Defaults to
        ``assets/svg-examples/diffusion_trajectory.svg``.
    title, subtitle : str
        Chart text.
    width : int
        Canvas width in pixels.
    duration : float
        Seconds for one forward-and-back loop.
    mode, accessibility, theme : str
        Forwarded to :func:`build_svg`.

    Returns
    -------
    Path
        Absolute path to the written SVG file.

    Examples
    --------
    >>> p = make_diffusion_trajectory()
    >>> p.exists()
    True
    """
    svg = build_svg(
        data,
        title=title,
        subtitle=subtitle,
        width=width,
        duration=duration,
        mode=mode,
        accessibility=accessibility,
        theme=theme,
    )
    dest = Path(out) if out else svg_example_path(__file__, "diffusion_trajectory")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(
        __file__,
        "diffusion_trajectory",
        build_svg,
        description="Generate an animated diffusion trajectory over a point cloud.",
    )


if __name__ == "__main__":
    main()
