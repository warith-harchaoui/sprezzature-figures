#!/usr/bin/env python3
"""
make_learning_curve — score against training-set size, and the answer to why you drew it.

A learning curve is drawn for one reason: to decide whether collecting
more data is worth the money. Two curves, training and validation, against
the number of examples the model was fitted on; a band around each for the
spread across folds.

Almost every learning curve ever published leaves that decision to the
reader's eye, and the eye is bad at it: a curve that has flattened and a
curve still climbing at a hundredth per doubling look identical at the
scale a chart is read. So this one measures the last doubling and writes
the answer down.

What this does that the usual version does not
-----------------------------------------------
* **It answers "would more data help?".** The slope of the validation
  curve over its final doubling is computed and stated, in the units of
  the score. A reader who wanted a number gets one; a reader who wanted a
  shape still has the shape.
* **It says how much is left.** A slope says the curve is still moving; it
  does not say where it is going. The saturating curve
  ``ceiling - amplitude * n ** -exponent`` is fitted to the validation
  means, the fitted ceiling is drawn as a dashed line, and the distance
  from the last point up to it is stated with the number of further
  doublings that closes nine tenths of it. That last figure is what a
  budget is written against, and it falls straight out of the exponent.
  When the data will not carry the claim -- too few sizes, or a fit whose
  ceiling lands at or below the last observation, or above 1 -- the line
  and the sentence are both withheld rather than guessed.
* **It names the gap.** The distance between the two curves at the right
  edge is the bias-variance diagnosis in one number -- a wide gap means
  the model memorises, a low pair means it cannot fit -- and it is
  labelled rather than left to be measured off the axis.
* **The band is named.** Shaded regions on a learning curve may be a
  standard deviation across folds, a standard error, or an interval. Here
  it is the fold-to-fold range, and the chrome says so.
* **The demo data is a learning curve.** Two straight lines in ``log(n)``
  are not one: they never flatten, they cross just past the right edge,
  and they make the figure's own headline measurement a constant. The
  shape of the demo is now saturating by construction -- see
  :func:`_curve`, which records what the straight lines did and why that
  was impossible, and ``tests/test_a_learning_curve_is_a_learning_curve.py``,
  which asserts it of the shipped data rather than of the formula.

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
from _scale import nice_ticks_range  # noqa: E402
from _style import BG, GRIDLINE, INK, SECONDARY, load_palette  # noqa: E402
from _svg import fmt_number, foreground_tip_css, svg_open, tooltip_bubble, xml_escape  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402

#: Training sizes on a geometric ladder, which is how a learning curve is
#: run: doubling is the unit a reader thinks in ("twice the data buys me
#: what?"), and a linear ladder spends most of its points where nothing
#: changes any more.
_SIZES = (250, 500, 1000, 2000, 4000, 8000, 16000, 32000)


#: The irreducible score: what the task itself allows, and what no quantity
#: of training data buys past. Label noise, overlapping classes and features
#: nobody collected all live in the six points between this and 1.0.
#:
#: Every learning curve has one. A pair of demo curves that does not is the
#: defect this constant exists to prevent, so it is named here rather than
#: left implicit in two slopes.
_CEILING = 0.94

#: Where each curve stands at the smallest training size, and how fast its
#: distance to the ceiling decays per doubling of data.
#:
#: Both curves are ``ceiling -/+ offset * (n / n0) ** -exponent``: validation
#: climbs toward the ceiling from below, training descends toward it from
#: above. Two properties follow from that *form* rather than from the
#: numbers, and both are the point:
#:
#: * neither curve can cross the other at any training size, because one
#:   stays above the ceiling and the other below it;
#: * neither can leave ``[0, 1]``, because validation's supremum is the
#:   ceiling and the ceiling is under 1.
#:
#: An exponent near a half is the rate the statistics give you. The gentler
#: one on validation is the usual empirical finding on real tasks.
_VALID_AT_SMALLEST, _VALID_EXPONENT = 0.758, 0.42
_TRAIN_AT_SMALLEST, _TRAIN_EXPONENT = 0.986, 0.55


def _mean_scores(size: float) -> Tuple[float, float]:
    """Training and validation score this kind of model reaches at ``size``.

    Returns
    -------
    tuple of float
        ``(training, validation)``, both saturating on :data:`_CEILING`.
    """
    return (
        _CEILING + (_TRAIN_AT_SMALLEST - _CEILING) * (size / _SIZES[0]) ** -_TRAIN_EXPONENT,
        _CEILING - (_CEILING - _VALID_AT_SMALLEST) * (size / _SIZES[0]) ** -_VALID_EXPONENT,
    )


def _curve(seed: int = 3, folds: int = 5) -> List[Dict[str, Any]]:
    """A model that fits easily and generalises slowly, one row per fold.

    Shaped rather than random -- and shaped as a learning curve rather than
    as two straight lines. Training score falls from near-one as the model
    stops being able to memorise; validation climbs, decelerating, and is
    still climbing at the right edge but by much less than it was. That is
    the interesting case -- "yes, buy more data, and here is how much it is
    still worth" -- and it is the case a demo should show.

    What was wrong with the straight lines, because it is worth not doing
    again. The first version was linear in ``log2(n)``: training
    ``0.995 - 0.0055 * doublings``, validation ``0.742 + 0.0265 * doublings``.
    Three things followed, and all three are impossible.

    * **The curves never flattened.** Linear in the log of ``n`` means every
      doubling buys exactly what the one before it bought, for ever.
      Extending that validation line reaches accuracy ``1.0000`` at 213 000
      examples and passes it after. A score above 1 is not a score.
    * **They crossed.** The gap closed at ``0.032`` per doubling from
      ``0.253``, so validation overtook training at about 60 000 examples --
      a model scoring better on data it has never seen. The last point
      plotted was 32 000: the curves did not avoid the crossing, the x-axis
      stopped one doubling short of it, while a comment here claimed the case
      had been designed out.
    * **The figure's own measurement was a constant.** This chart exists to
      say whether the last doubling still bought anything. On a line, the
      slope over the final doubling is the slope everywhere: ``+0.0265``, at
      250 examples and at 32 000 alike. The one number it was built to
      deliver could not vary, and the "flat" verdict :func:`_verdict` knows
      how to write was unreachable from the demo data. A figure whose demo
      cannot produce one of its own answers has not been tried against its
      own claim.

    Here the slope decays from ``+0.046`` over the first doubling to
    ``+0.008`` over the last, which is the shape that number is read for.
    """
    rng = random.Random(seed)
    rows: List[Dict[str, Any]] = []
    for size in _SIZES:
        train_mean, valid_mean = _mean_scores(size)
        for fold in range(folds):
            # Fold-to-fold spread shrinks as 1/sqrt(n), the rate the standard
            # error of a mean actually follows. The old version decayed it
            # linearly in doublings, and went negative past 7.5 million.
            spread_t = 0.11 * size**-0.5 * (0.8 + 0.4 * rng.random())
            spread_v = 0.46 * size**-0.5 * (0.8 + 0.4 * rng.random())
            rows.append(
                {
                    "size": size,
                    "split": "Training",
                    "score": round(train_mean + (rng.random() - 0.5) * spread_t, 4),
                    "fold": fold,
                }
            )
            rows.append(
                {
                    "size": size,
                    "split": "Validation",
                    "score": round(valid_mean + (rng.random() - 0.5) * spread_v, 4),
                    "fold": fold,
                }
            )
    return rows


DEMO_DATA: List[Dict[str, Any]] = _curve()


def _fit_ceiling(points: List[Tuple[float, float]]) -> Optional[Tuple[float, float]]:
    """Estimate the score this curve is saturating on, and how fast.

    Fits ``score = ceiling - amplitude * size ** -exponent`` -- the
    saturating form a learning curve actually takes -- and returns the
    ceiling with the exponent.

    The fit is a one-dimensional search, which is why it needs no solver and
    cannot fail to converge: with the exponent held fixed the model is linear
    in its two remaining parameters, so each candidate exponent is scored by
    an ordinary least-squares line through ``size ** -exponent`` and the best
    exponent is picked off a grid, then refined around the winner.

    Parameters
    ----------
    points : list of tuple of float
        ``(size, score)`` for one curve, in any order, sizes positive.

    Returns
    -------
    tuple of float or None
        ``(ceiling, exponent)``, or ``None`` when the data does not support
        the claim: fewer than four sizes, a curve going the wrong way, or a
        ceiling at or below the last observation (nothing left to promise) or
        above 1 (a score that does not exist). Refusing to answer is part of
        the answer -- a fitted ceiling of 1.4 drawn as a line would be read.
    """
    usable = sorted({(size, score) for size, score in points if size > 0})
    if len(usable) < 4:
        return None

    def best_line(exponent: float) -> Tuple[float, float, float]:
        """Least-squares ``ceiling - amplitude * x`` and its error, at one exponent."""
        xs = [size**-exponent for size, _ in usable]
        ys = [score for _, score in usable]
        n = float(len(xs))
        mean_x, mean_y = sum(xs) / n, sum(ys) / n
        var_x = sum((x - mean_x) ** 2 for x in xs)
        if var_x <= 0:
            return (mean_y, 0.0, float("inf"))
        slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True)) / var_x
        intercept = mean_y - slope * mean_x
        error = sum((intercept + slope * x - y) ** 2 for x, y in zip(xs, ys, strict=True))
        # The model is written with a minus, so a rising curve has slope < 0.
        return (intercept, -slope, error)

    grid = [0.05 + 0.025 * step for step in range(60)]
    exponent = min(grid, key=lambda e: best_line(e)[2])
    for width in (0.0125, 0.00625, 0.003125):
        around = [exponent - width, exponent, exponent + width]
        exponent = min((e for e in around if e > 0), key=lambda e: best_line(e)[2])

    ceiling, amplitude, _ = best_line(exponent)
    if amplitude <= 0 or not 0.0 < ceiling <= 1.0:
        return None
    if ceiling <= max(score for _, score in usable):
        return None
    return (ceiling, exponent)


def _headroom(
    points: List[Tuple[float, float]], score_name: str
) -> Optional[Tuple[float, float, float]]:
    """How much score is left below the ceiling, and what it costs to get it.

    Returns
    -------
    tuple of float or None
        ``(ceiling, headroom, doublings)`` where ``headroom`` is the distance
        from the last observed score to the fitted ceiling, and ``doublings``
        is how many further doublings of data close nine tenths of it. That
        last number is the one a budget is written against, and it comes
        straight out of the exponent: closing a tenth of the remaining gap
        costs ``log2(10) / exponent`` doublings whatever the scale.
    """
    fit = _fit_ceiling(points)
    if fit is None:
        return None
    ceiling, exponent = fit
    last = max(points, key=lambda pair: pair[0])[1]
    return (ceiling, ceiling - last, math.log2(10.0) / exponent)


def _verdict(points: List[Tuple[float, float]], score_name: str) -> str:
    """Whether the last doubling of data still bought anything, in words.

    The whole reason a learning curve is drawn, and the one thing it
    normally does not say. The threshold is deliberately explicit: below a
    thousandth of a point per doubling the curve is flat for any practical
    purpose, and saying so is more useful than a hedge.

    Read over the *last* doubling specifically, which is only informative
    because the curve decelerates. See :func:`_curve` for what happened when
    it did not.
    """
    if len(points) < 2:
        return ""
    (x0, y0), (x1, y1) = points[-2], points[-1]
    if x0 <= 0 or x1 <= 0:
        return ""
    doublings = math.log2(x1 / x0) or 1.0
    slope = (y1 - y0) / doublings
    if abs(slope) < 0.001:
        return (
            f"Flat over the last doubling ({slope:+.4f} {score_name} per doubling): "
            f"more data is unlikely to help."
        )
    if slope > 0:
        return (
            f"Still climbing at {slope:+.4f} {score_name} per doubling: "
            f"more data should still buy something."
        )
    return f"Falling at {slope:+.4f} {score_name} per doubling: look at the data, not the model."


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "More data is still worth buying, but each doubling buys less than the last",
    subtitle: str = "Accuracy against training-set size, five folds. Bands are the fold-to-fold range; the dashed line is the fitted ceiling.",
    width: int = 900,
    height: int = 580,
    x: str = "size",
    series: str = "split",
    y: str = "score",
    x_label: str = "Training examples",
    y_label: str = "Accuracy",
    score_name: str = "accuracy",
    verdict: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full learning-curve SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        One row per fold per training size, with keys named by `x`,
        `series` and `y`. Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    x, series, y : str
        Which key holds the training-set size, which splits training from
        validation, and which carries the score.
    x_label, y_label : str
        Axis titles.
    score_name : str
        What the score is called in the verdict sentence ("accuracy",
        "F1", "R²"), so the number it quotes carries its unit.
    verdict : str or None
        The sentence about whether more data would help. ``None`` computes
        it from the last doubling of the validation curve.
    mode, accessibility : str, optional
        Forwarded to :func:`_interactive.fullscreen_control` /
        :func:`_style.load_palette`.
    theme : str, optional
        Visual theme: ``"corporate"`` (default, Roboto) or ``"academic"``
        (LaTeX-style Latin Modern).

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    rows = list(data if data else DEMO_DATA)
    mono_family = mono_stack_for_theme(theme)
    palette = load_palette(accessibility, theme=theme)
    hues = {
        "train": palette.get("Orange", "#FF9500"),
        "valid": palette.get("Blue", "#007AFF"),
    }

    series_names: List[str] = []
    grouped: Dict[Tuple[str, float], List[float]] = {}
    sizes: List[float] = []
    for row in rows:
        name, size = str(row[series]), float(row[x])
        if name not in series_names:
            series_names.append(name)
        if size not in sizes:
            sizes.append(size)
        grouped.setdefault((name, size), []).append(float(row[y]))
    sizes.sort()

    bands = {
        key: (sum(values) / len(values), min(values), max(values))
        for key, values in grouped.items()
    }
    everything = [v for _, low, high in bands.values() for v in (low, high)]
    lo, hi = min(everything), max(everything)
    # Round the step before padding out: padding first and rounding after
    # leaves ticks on 0.78 and 0.86, which read as data rather than an axis.
    span = (hi - lo) or 0.05
    # `_scale.nice_ticks_range` is the house answer to "ticks a reader can
    # read on an axis that does not start at zero". Writing it again here
    # cost two Ralph passes and still got it wrong on the next figure.
    ticks = nice_ticks_range(lo - span * 0.12, hi + span * 0.04)
    y_lo, y_hi = ticks[0], ticks[-1]

    plot_x, plot_y = 82.0, 156.0
    right_margin, bottom_margin = 124.0, 76.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_margin

    # Log-spaced x: a learning curve is run by doubling, and on a linear
    # axis seven eighths of the plot is the last two points.
    log_lo, log_hi = math.log2(sizes[0]), math.log2(sizes[-1])

    def px(size: float) -> float:
        return plot_x + (math.log2(size) - log_lo) / ((log_hi - log_lo) or 1.0) * plot_w

    def py(value: float) -> float:
        return plot_y + plot_h - (value - y_lo) / ((y_hi - y_lo) or 1.0) * plot_h

    def colour_for(name: str) -> str:
        return hues["train"] if name.lower().startswith("train") else hues["valid"]

    validation = [
        (size, bands[(name, size)][0])
        for name in series_names
        if not name.lower().startswith("train")
        for size in sizes
        if (name, size) in bands
    ]
    said = verdict if verdict is not None else _verdict(validation, score_name)
    # The slope says the curve is still moving. What a budget needs next is
    # how far there is left to go, which is a property of the whole curve
    # rather than of its last segment -- so it is fitted, and it is allowed
    # to come back empty when the data will not carry the claim.
    head = _headroom(validation, score_name)

    parts: List[str] = []
    parts.append(
        svg_open(width, height, "lc-title", "lc-desc", font_family=chrome_stack_for_theme(theme))
    )
    parts.append(f'<title id="lc-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="lc-desc">Learning curves for {xml_escape(", ".join(series_names))} '
        f"against training-set size, from {fmt_number(sizes[0])} to {fmt_number(sizes[-1])} "
        f"examples on a doubling scale. Each band is the range across folds, each line their "
        f"mean. {xml_escape(said)}</desc>"
    )
    parts.append(
        "<style>"
        ".pt{cursor:default;}"
        ".pt:hover,.pt:focus{outline:none;}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        + foreground_tip_css(len(series_names) * len(sizes), mark_prefix="pt", tip_prefix="pttip")
        + "@media (prefers-reduced-motion:reduce){.tip{transition:none}}"
        "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="{plot_x:.1f}" y="46" font-size="22" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(
        f'<text x="{plot_x:.1f}" y="72" font-size="14" fill="{SECONDARY}">'
        f"{xml_escape(subtitle)}</text>"
    )
    if said:
        parts.append(
            f'<text x="{plot_x:.1f}" y="98" font-size="12" fill="{SECONDARY}" '
            f'font-family="{mono_family}">{xml_escape(said)}</text>'
        )
    if head is not None:
        ceiling, left, doublings = head
        # Three decimals, not fmt_number: the headroom here is 0.023 and
        # fmt_number prints it 0.02, which rounds away most of what is left to
        # buy. A measurement whose last useful digit is dropped still reads as
        # a measurement.
        #
        # Built as a local rather than inlined into the append, because a
        # replacement field spanning lines inside a single-quoted f-string is
        # 3.12 syntax -- which ruff format produces willingly and this
        # package's 3.10 floor cannot parse.
        headroom_line = (
            f"Fitted ceiling {ceiling:.3f} -- {left:.3f} left, about "
            f"{doublings:.0f} more doublings to close nine tenths of it."
        )
        parts.append(
            f'<text x="{plot_x:.1f}" y="118" font-size="12" fill="{SECONDARY}" '
            f'font-family="{mono_family}">{xml_escape(headroom_line)}</text>'
        )
    parts.append(
        f'<text x="{plot_x:.1f}" y="{plot_y - 14:.1f}" font-size="12" fill="{SECONDARY}">'
        f"{xml_escape(y_label)}</text>"
    )

    for value_at in ticks:
        gy = py(value_at)
        parts.append(
            f'<line x1="{plot_x:.1f}" y1="{gy:.1f}" x2="{plot_x + plot_w:.1f}" y2="{gy:.1f}" '
            f'stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{plot_x - 10:.1f}" y="{gy + 4:.1f}" font-size="11" fill="{SECONDARY}" '
            f'text-anchor="end" font-family="{mono_family}">{fmt_number(value_at)}</text>'
        )

    # The ceiling, drawn where the two curves are heading. It is the quantity
    # the chart is read for -- the distance between the validation curve and
    # this line is what is left to buy -- and it is drawn only when it is on
    # the plot, because a reference line clipped to an edge reads as a value
    # the axis happens to end on.
    if head is not None and y_lo <= head[0] <= y_hi:
        ceiling_y = py(head[0])
        parts.append(
            f'<line x1="{plot_x:.1f}" y1="{ceiling_y:.1f}" '
            f'x2="{plot_x + plot_w:.1f}" y2="{ceiling_y:.1f}" stroke="{SECONDARY}" '
            f'stroke-width="1.4" stroke-dasharray="7 5"/>'
        )
        parts.append(
            f'<text x="{plot_x + plot_w - 4:.1f}" y="{ceiling_y - 7:.1f}" font-size="11" '
            f'fill="{SECONDARY}" text-anchor="end" font-family="{mono_family}">'
            f"ceiling {head[0]:.3f}</text>"
        )

    for size in sizes:
        parts.append(
            f'<text x="{px(size):.1f}" y="{plot_y + plot_h + 22:.1f}" font-size="11" '
            f'fill="{SECONDARY}" text-anchor="middle" font-family="{mono_family}">'
            f"{fmt_number(size)}</text>"
        )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{height - 22:.1f}" font-size="12" '
        f'fill="{SECONDARY}" text-anchor="middle">{xml_escape(x_label)}</text>'
    )

    tips: List[str] = []
    for name in series_names:
        colour = colour_for(name)
        present = [size for size in sizes if (name, size) in bands]
        upper = " ".join(f"{px(s):.1f},{py(bands[(name, s)][2]):.1f}" for s in present)
        lower = " ".join(f"{px(s):.1f},{py(bands[(name, s)][1]):.1f}" for s in reversed(present))
        parts.append(f'<polygon points="{upper} {lower}" fill="{colour}" opacity="0.16"/>')
        parts.append(
            '<polyline points="'
            + " ".join(f"{px(s):.1f},{py(bands[(name, s)][0]):.1f}" for s in present)
            + f'" fill="none" stroke="{colour}" stroke-width="2.4" stroke-linejoin="round"/>'
        )
        for size in present:
            mean, low, high = bands[(name, size)]
            element = len(tips)
            parts.append(
                f'<circle cx="{px(size):.1f}" cy="{py(mean):.1f}" r="3.4" fill="{colour}" '
                f'stroke="{BG}" stroke-width="1.4"/>'
            )
            parts.append(
                f'<rect id="pt-{element}" class="pt hit" tabindex="0" role="img" '
                f'aria-label="{xml_escape(name)} at {fmt_number(size)} examples: '
                f'{fmt_number(mean)}, folds {fmt_number(low)} to {fmt_number(high)}" '
                f'x="{px(size) - 10:.1f}" y="{py(high) - 10:.1f}" width="20" '
                f'height="{max(py(low) - py(high) + 20, 20):.1f}" fill="transparent">'
                f"<title>{xml_escape(name)} · {fmt_number(size)}: {fmt_number(mean)}</title></rect>"
            )
            tips.append(
                tooltip_bubble(
                    px(size),
                    py(mean),
                    [
                        f"{name} · {fmt_number(size)} examples",
                        f"mean {fmt_number(mean)}",
                        f"folds {fmt_number(low)} to {fmt_number(high)}",
                    ],
                    canvas_w=width,
                    canvas_h=height,
                    ink=INK,
                    secondary=SECONDARY,
                    border=GRIDLINE,
                    elem_id=f"pttip-{element}",
                )
            )
        last = present[-1]
        parts.append(
            f'<text x="{px(last) + 12:.1f}" y="{py(bands[(name, last)][0]) + 4:.1f}" '
            f'font-size="12" font-weight="700" fill="{colour}">{xml_escape(name)}</text>'
        )

    # The gap at the right edge is the bias-variance reading, in one number.
    if len(series_names) == 2:
        top_name, bottom_name = sorted(series_names, key=lambda n: -bands[(n, sizes[-1])][0])
        gap = bands[(top_name, sizes[-1])][0] - bands[(bottom_name, sizes[-1])][0]
        gy_top = py(bands[(top_name, sizes[-1])][0])
        gy_bottom = py(bands[(bottom_name, sizes[-1])][0])
        bracket_x = px(sizes[-1]) - 26.0
        parts.append(
            f'<path d="M {bracket_x:.1f},{gy_top:.1f} L {bracket_x - 7:.1f},{gy_top:.1f} '
            f'L {bracket_x - 7:.1f},{gy_bottom:.1f} L {bracket_x:.1f},{gy_bottom:.1f}" '
            f'fill="none" stroke="{SECONDARY}" stroke-width="1"/>'
        )
        label = f"gap {fmt_number(gap)}"
        label_x = bracket_x - 12.0
        label_y = (gy_top + gy_bottom) / 2.0
        # A backing plate: the bracket sits where the two curves are
        # closest, which is exactly where the label would otherwise be
        # read through a line.
        parts.append(
            f'<rect x="{label_x - 7.0 * len(label) - 4:.1f}" y="{label_y - 8:.1f}" '
            f'width="{7.0 * len(label) + 8:.1f}" height="15" fill="{BG}" opacity="0.88" rx="2"/>'
        )
        parts.append(
            f'<text x="{label_x:.1f}" y="{label_y + 4:.1f}" '
            f'font-size="11" fill="{SECONDARY}" text-anchor="end" '
            f'font-family="{mono_family}">{label}</text>'
        )

    parts.extend(tips)
    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_learning_curve(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "More data is still worth buying, but each doubling buys less than the last",
    subtitle: str = "Accuracy against training-set size, five folds. Bands are the fold-to-fold range; the dashed line is the fitted ceiling.",
    width: int = 900,
    height: int = 580,
    x: str = "size",
    series: str = "split",
    y: str = "score",
    x_label: str = "Training examples",
    y_label: str = "Accuracy",
    score_name: str = "accuracy",
    verdict: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render a hand-authored learning curve and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        One row per fold per size, with keys ``size``, ``split`` and
        ``score``, or whatever `x`, `series` and `y` name. Defaults to
        DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to
        ``assets/svg-examples/learning-curve.svg``.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    x, series, y : str
        Which keys hold the size, the split and the score.
    x_label, y_label : str
        Axis titles.
    score_name : str
        What the score is called in the verdict sentence.
    verdict : str or None
        The "would more data help" sentence; ``None`` computes it.
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
    >>> p = make_learning_curve()
    >>> p.exists()
    True
    """
    svg = build_svg(
        data,
        title=title,
        subtitle=subtitle,
        width=width,
        height=height,
        x=x,
        series=series,
        y=y,
        x_label=x_label,
        y_label=y_label,
        score_name=score_name,
        verdict=verdict,
        mode=mode,
        accessibility=accessibility,
        theme=theme,
    )
    dest = Path(out) if out else svg_example_path(__file__, "learning-curve")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "learning-curve", build_svg, description="Generate a learning curve.")


if __name__ == "__main__":
    main()
