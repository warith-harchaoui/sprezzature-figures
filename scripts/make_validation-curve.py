#!/usr/bin/env python3
"""
make_validation_curve — score against one hyper-parameter, and which value to take.

A sweep over a single hyper-parameter: training and validation score at
each value, a band for the spread across folds. It is drawn to make one
decision -- which value to ship -- and the usual version hands that
decision back to the reader as a hump to eyeball.

The peak is the wrong answer anyway, and that is the interesting part.
Picking the argmax of a noisy validation curve overfits the validation
set: the winner won partly on luck, and the model is more complex than
the evidence supports. The standard remedy is the **one-standard-error
rule** -- take the simplest model whose score is within one standard
error of the best -- and it is a line of arithmetic that almost no
published validation curve performs.

What this does that the usual version does not
-----------------------------------------------
* **It marks both candidates.** The peak, and the one-standard-error
  choice, each with its value. When they differ, the figure says so and
  says what the simpler model costs: usually nothing measurable.
* **The band is named.** A shaded region on a sweep may be a standard
  deviation, a standard error or an interval; here it is the fold-to-fold
  range, and the chrome says so.
* **The axis is logarithmic when the sweep is.** Regularisation strengths
  are tried by powers of ten, and a linear axis spends four fifths of the
  plot on the last two points.

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

#: A regularisation sweep by powers of ten, which is how one is run.
_ALPHAS = (1e-4, 1e-3, 1e-2, 1e-1, 1.0, 10.0, 100.0)


def _sweep(seed: int = 17, folds: int = 5) -> List[Dict[str, Any]]:
    """A sweep whose peak and whose one-standard-error choice disagree.

    That disagreement is the whole lesson, so the demo is built to show
    it: validation peaks at a middling alpha and is statistically flat for
    one step beyond, where the model is simpler and the noise no longer
    tells them apart.
    """
    rng = random.Random(seed)
    rows: List[Dict[str, Any]] = []
    for alpha in _ALPHAS:
        power = math.log10(alpha)
        # Training score falls as regularisation rises, monotonically.
        train_mean = 0.981 - 0.0145 * (power + 4)
        # Validation rises out of overfitting, peaks, then underfits away --
        # falling much faster on the overfitting side than on the
        # over-regularised one, which is both true of real sweeps and what
        # makes the peak broad enough for the one-standard-error rule to
        # pick a different value from the argmax. A first draft used one
        # symmetric curve, the two choices coincided, and the title claimed
        # a disagreement the data did not contain.
        offset = power + 1.0
        # 0.0006 on the over-regularised side, not 0.0022: the coefficients
        # were solved for numerically so the one-standard-error choice really
        # does land one step past the peak. Writing a demo whose title asserts
        # a disagreement, then not checking the arithmetic, is how a figure
        # ends up contradicting its own headline.
        valid_mean = 0.930 - (0.016 if offset < 0 else 0.0006) * offset ** 2
        for fold in range(folds):
            rows.append({
                "alpha": alpha, "split": "Training", "fold": fold,
                "score": round(train_mean + (rng.random() - 0.5) * 0.010, 4),
            })
            rows.append({
                "alpha": alpha, "split": "Validation", "fold": fold,
                "score": round(valid_mean + (rng.random() - 0.5) * 0.021, 4),
            })
    return rows


DEMO_DATA: List[Dict[str, Any]] = _sweep()


def _mean_and_error(values: List[float]) -> Tuple[float, float]:
    """Mean and standard error of the mean; zero error below two values."""
    n = len(values)
    mean = sum(values) / n
    if n < 2:
        return mean, 0.0
    variance = sum((v - mean) ** 2 for v in values) / (n - 1)
    return mean, math.sqrt(variance / n)


def _one_standard_error_choice(
    points: List[Tuple[float, float, float]], simpler_is: str
) -> Tuple[float, float]:
    """The simplest value scoring within one standard error of the best.

    `points` is ``(parameter, mean, standard error)``. "Simplest" is a
    property of the parameter, not of the chart, so the caller says which
    direction it lies in: more regularisation is simpler, more depth is
    not.
    """
    best_param, best_mean, best_error = max(points, key=lambda row: row[1])
    threshold = best_mean - best_error
    eligible = [row for row in points if row[1] >= threshold]
    if not eligible:
        return best_param, best_mean
    pick = max(eligible, key=lambda row: row[0]) if simpler_is == "larger" else min(
        eligible, key=lambda row: row[0]
    )
    return pick[0], pick[1]


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Ten times more regularisation costs nothing measurable — take it",
    subtitle: str = "Five folds per value. Bands are the fold-to-fold range; the rule is one standard error from the peak.",
    width: int = 900,
    height: int = 580,
    x: str = "alpha",
    series: str = "split",
    y: str = "score",
    x_label: str = "Regularisation strength α",
    y_label: str = "Accuracy",
    simpler_is: str = "larger",
    log_scale: bool = True,
    advice: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full validation-curve SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        One row per fold per parameter value, with keys named by `x`,
        `series` and `y`. Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    x, series, y : str
        Which key holds the hyper-parameter, which splits training from
        validation, and which carries the score.
    x_label, y_label : str
        Axis titles.
    simpler_is : str
        ``"larger"`` when a bigger value means a simpler model (a
        regularisation strength) or ``"smaller"`` when it does not (a tree
        depth, a number of components). The one-standard-error rule picks
        the simplest model, and only the caller knows which way that is.
    log_scale : bool
        Place the parameter on a logarithmic axis. Sweeps are run by
        powers of ten and a linear axis wastes most of the plot.

        Named ``log_scale`` and not ``log_x`` on purpose: ``log_x`` is one
        of the flags ``_render.render_cli`` hands every generator that
        declares it, as a store-true defaulting to False, and it passes
        that False straight in -- silently overriding a ``True`` default
        here and drawing the first render of this figure on a linear axis,
        four of its seven values piled against the left edge.
    advice : str or None
        The sentence comparing the peak with the one-standard-error
        choice. ``None`` composes it from the data.
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
    values: List[float] = []
    for row in rows:
        name, value = str(row[series]), float(row[x])
        if name not in series_names:
            series_names.append(name)
        if value not in values:
            values.append(value)
        grouped.setdefault((name, value), []).append(float(row[y]))
    values.sort()

    stats = {
        key: (sum(v) / len(v), min(v), max(v), *_mean_and_error(v)[1:])
        for key, v in grouped.items()
    }
    validation_name = next(
        (n for n in series_names if not n.lower().startswith("train")), series_names[-1]
    )
    sweep = [
        (value, stats[(validation_name, value)][0], stats[(validation_name, value)][3])
        for value in values
        if (validation_name, value) in stats
    ]
    peak_value, peak_mean, _ = max(sweep, key=lambda row: row[1])
    chosen_value, chosen_mean = _one_standard_error_choice(sweep, simpler_is)

    everything = [v for value_list in grouped.values() for v in value_list]
    lo, hi = min(everything), max(everything)
    span = (hi - lo) or 0.05
    ticks = nice_ticks_range(lo - span * 0.10, hi + span * 0.06)
    y_lo, y_hi = ticks[0], ticks[-1]

    plot_x, plot_y = 84.0, 162.0
    right_margin, bottom_margin = 126.0, 80.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_margin

    positions = [math.log10(v) if log_scale else v for v in values]
    p_lo, p_hi = positions[0], positions[-1]

    def px(value: float) -> float:
        position = math.log10(value) if log_scale else value
        return plot_x + (position - p_lo) / ((p_hi - p_lo) or 1.0) * plot_w

    def py(value: float) -> float:
        return plot_y + plot_h - (value - y_lo) / ((y_hi - y_lo) or 1.0) * plot_h

    def shown(value: float) -> str:
        """A parameter value as a reader writes it, powers of ten included."""
        if log_scale and value > 0:
            power = math.log10(value)
            if abs(power - round(power)) < 1e-9 and not -1 <= power <= 2:
                return f"1e{int(round(power))}"
        return fmt_number(value)

    if advice is not None:
        said = advice
    elif chosen_value == peak_value:
        said = (
            f"The peak at {shown(peak_value)} is also the simplest value within one "
            f"standard error of it."
        )
    else:
        cost = peak_mean - chosen_mean
        said = (
            f"Peak at {shown(peak_value)}; the simplest value within one standard error is "
            f"{shown(chosen_value)}, costing {fmt_number(cost)} of {y_label.lower()}."
        )

    parts: List[str] = []
    parts.append(
        svg_open(width, height, "vc-title", "vc-desc",
                 font_family=chrome_stack_for_theme(theme))
    )
    parts.append(f'<title id="vc-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="vc-desc">A sweep of {len(values)} values of '
        f'{xml_escape(x_label)}, from {shown(values[0])} to {shown(values[-1])}, with '
        f'{xml_escape(", ".join(series_names))} scored at each. Each band is the range '
        f'across folds. {xml_escape(said)}</desc>'
    )
    parts.append(
        "<style>"
        ".vp{cursor:default;}"
        ".vp:hover,.vp:focus{outline:none;}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        + foreground_tip_css(len(series_names) * len(values), mark_prefix="vp", tip_prefix="vptip")
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
        f'{xml_escape(subtitle)}</text>'
    )
    parts.append(
        f'<text x="{plot_x:.1f}" y="98" font-size="12" fill="{SECONDARY}" '
        f'font-family="{mono_family}">{xml_escape(said)}</text>'
    )
    parts.append(
        f'<text x="{plot_x:.1f}" y="{plot_y - 14:.1f}" font-size="12" fill="{SECONDARY}">'
        f'{xml_escape(y_label)}</text>'
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
    for value in values:
        parts.append(
            f'<text x="{px(value):.1f}" y="{plot_y + plot_h + 22:.1f}" font-size="11" '
            f'fill="{SECONDARY}" text-anchor="middle" font-family="{mono_family}">'
            f'{xml_escape(shown(value))}</text>'
        )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{height - 24:.1f}" font-size="12" '
        f'fill="{SECONDARY}" text-anchor="middle">{xml_escape(x_label)}</text>'
    )

    # The one-standard-error threshold, drawn: everything above this line
    # is statistically indistinguishable from the peak, which is what makes
    # the simpler choice defensible rather than merely cheaper.
    peak_error = next(error for value, _, error in sweep if value == peak_value)
    threshold = peak_mean - peak_error
    parts.append(
        f'<line x1="{plot_x:.1f}" y1="{py(threshold):.1f}" x2="{plot_x + plot_w:.1f}" '
        f'y2="{py(threshold):.1f}" stroke="{hues["valid"]}" stroke-width="1" '
        f'stroke-dasharray="3 3" opacity="0.7"/>'
    )
    parts.append(
        f'<text x="{plot_x + plot_w:.1f}" y="{py(threshold) - 6:.1f}" font-size="10" '
        f'fill="{hues["valid"]}" text-anchor="end" font-family="{mono_family}">'
        f'one standard error below the peak</text>'
    )

    tips: List[str] = []
    for name in series_names:
        colour = hues["train"] if name.lower().startswith("train") else hues["valid"]
        present = [v for v in values if (name, v) in stats]
        upper = " ".join(f"{px(v):.1f},{py(stats[(name, v)][2]):.1f}" for v in present)
        lower = " ".join(
            f"{px(v):.1f},{py(stats[(name, v)][1]):.1f}" for v in reversed(present)
        )
        parts.append(f'<polygon points="{upper} {lower}" fill="{colour}" opacity="0.16"/>')
        parts.append(
            '<polyline points="'
            + " ".join(f"{px(v):.1f},{py(stats[(name, v)][0]):.1f}" for v in present)
            + f'" fill="none" stroke="{colour}" stroke-width="2.4" stroke-linejoin="round"/>'
        )
        for value in present:
            mean, low, high, error = stats[(name, value)]
            element = len(tips)
            parts.append(
                f'<circle cx="{px(value):.1f}" cy="{py(mean):.1f}" r="3.4" fill="{colour}" '
                f'stroke="{BG}" stroke-width="1.4"/>'
            )
            parts.append(
                f'<rect id="vp-{element}" class="vp hit" tabindex="0" role="img" '
                f'aria-label="{xml_escape(name)} at {xml_escape(shown(value))}: '
                f'{fmt_number(mean)}, folds {fmt_number(low)} to {fmt_number(high)}" '
                f'x="{px(value) - 10:.1f}" y="{py(high) - 10:.1f}" width="20" '
                f'height="{max(py(low) - py(high) + 20, 20):.1f}" fill="transparent">'
                f'<title>{xml_escape(name)} · {xml_escape(shown(value))}: '
                f'{fmt_number(mean)}</title></rect>'
            )
            tips.append(
                tooltip_bubble(
                    px(value), py(mean),
                    [
                        f"{name} · {shown(value)}",
                        f"mean {fmt_number(mean)}",
                        f"folds {fmt_number(low)} to {fmt_number(high)}",
                    ],
                    canvas_w=width, canvas_h=height, ink=INK, secondary=SECONDARY,
                    border=GRIDLINE, elem_id=f"vptip-{element}",
                )
            )
        last = present[-1]
        parts.append(
            f'<text x="{px(last) + 12:.1f}" y="{py(stats[(name, last)][0]) + 4:.1f}" '
            f'font-size="12" font-weight="700" fill="{colour}">{xml_escape(name)}</text>'
        )

    # Both candidates marked. The peak first, the choice over it, so the
    # one a reader should act on is the one drawn on top.
    for value, label, weight in (
        (peak_value, "peak", 1.2),
        (chosen_value, "take this", 2.0),
    ):
        if value == peak_value and chosen_value == peak_value and label == "peak":
            continue
        parts.append(
            f'<line x1="{px(value):.1f}" y1="{plot_y:.1f}" x2="{px(value):.1f}" '
            f'y2="{plot_y + plot_h:.1f}" stroke="{INK}" stroke-width="{weight}" '
            f'stroke-dasharray="4 3" opacity="{0.45 if label == "peak" else 0.9}"/>'
        )
        text = f"{label} {shown(value)}"
        anchor_x = px(value) + 8
        parts.append(
            f'<rect x="{anchor_x - 3:.1f}" y="{plot_y + (6 if label == "peak" else 28):.1f}" '
            f'width="{6.6 * len(text) + 8:.1f}" height="18" fill="{BG}" opacity="0.9" rx="3"/>'
        )
        parts.append(
            f'<text x="{anchor_x + 2:.1f}" '
            f'y="{plot_y + (19 if label == "peak" else 41):.1f}" font-size="11" '
            f'font-weight="700" fill="{INK}" font-family="{mono_family}">'
            f'{xml_escape(text)}</text>'
        )

    parts.extend(tips)
    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_validation_curve(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Ten times more regularisation costs nothing measurable — take it",
    subtitle: str = "Five folds per value. Bands are the fold-to-fold range; the rule is one standard error from the peak.",
    width: int = 900,
    height: int = 580,
    x: str = "alpha",
    series: str = "split",
    y: str = "score",
    x_label: str = "Regularisation strength α",
    y_label: str = "Accuracy",
    simpler_is: str = "larger",
    log_scale: bool = True,
    advice: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render a hand-authored validation curve and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        One row per fold per parameter value, with keys ``alpha``,
        ``split`` and ``score``, or whatever `x`, `series` and `y` name.
        Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to
        ``assets/svg-examples/validation-curve.svg``.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    x, series, y : str
        Which keys hold the parameter, the split and the score.
    x_label, y_label : str
        Axis titles.
    simpler_is : str
        ``"larger"`` or ``"smaller"``: which direction along the parameter
        makes the model simpler.
    log_scale : bool
        Put the parameter on a logarithmic axis.
    advice : str or None
        The peak-versus-one-standard-error sentence; ``None`` composes it.
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
    >>> p = make_validation_curve()
    >>> p.exists()
    True
    """
    svg = build_svg(
        data, title=title, subtitle=subtitle, width=width, height=height,
        x=x, series=series, y=y, x_label=x_label, y_label=y_label,
        simpler_is=simpler_is, log_scale=log_scale, advice=advice, mode=mode,
        accessibility=accessibility, theme=theme,
    )
    dest = Path(out) if out else svg_example_path(__file__, "validation-curve")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "validation-curve", build_svg,
               description="Generate a validation curve over one hyper-parameter.")


if __name__ == "__main__":
    main()
