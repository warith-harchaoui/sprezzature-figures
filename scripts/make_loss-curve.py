#!/usr/bin/env python3
"""
make_loss_curve — loss per epoch, and the epoch you should have stopped at.

Training loss and validation loss against epoch: the figure every training
run produces and almost nobody reads carefully. It is drawn to find one
number -- the epoch where validation stopped improving -- and the usual
version makes the reader find it by eye, on a curve whose minimum is flat
enough that the eye gets it wrong by five epochs in either direction.

What this does that the usual version does not
-----------------------------------------------
* **It marks the best epoch and names it.** A rule, a label, a number.
  That is the checkpoint worth keeping, and a chart that does not say it
  has not finished the job it was drawn for.
* **It shades what came after.** Everything past the minimum is time and
  electricity spent getting worse; the region is drawn as such, with how
  many epochs it cost. A reader learns their patience setting was too
  generous without being told.
* **It reports the overfitting gap.** Training and validation loss at the
  final epoch, and the distance between them, because that distance is
  the diagnosis.
* **The minimum is read off the data, not off the picture.** Ties go to
  the earliest epoch, which is the conservative choice and the one early
  stopping makes.

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

_EPOCHS = 60


def _run(seed: int = 9) -> List[Dict[str, Any]]:
    """One training run that overfits, which is the case worth drawing.

    Training loss decays and keeps decaying; validation bottoms out around
    a third of the way in and climbs back. A run that never overfits makes
    a duller chart and teaches nothing about where to stop.
    """
    rng = random.Random(seed)
    rows: List[Dict[str, Any]] = []
    for epoch in range(1, _EPOCHS + 1):
        train = 0.08 + 1.55 * math.exp(-epoch / 9.5) + (rng.random() - 0.5) * 0.012
        valid = (
            0.33
            + 1.42 * math.exp(-epoch / 7.0)
            + 0.0032 * max(epoch - 18, 0)
            + (rng.random() - 0.5) * 0.028
        )
        rows.append({"epoch": epoch, "split": "Training", "loss": round(train, 4)})
        rows.append({"epoch": epoch, "split": "Validation", "loss": round(valid, 4)})
    return rows


DEMO_DATA: List[Dict[str, Any]] = _run()


def _best(points: List[Tuple[float, float]]) -> Tuple[float, float]:
    """Epoch and value of the lowest loss, earliest epoch winning a tie.

    The earliest is the conservative reading and the one an early-stopping
    callback takes: a later epoch that merely ties has bought nothing and
    cost a checkpoint.
    """
    best_epoch, best_value = points[0]
    for epoch, value in points[1:]:
        if value < best_value:
            best_epoch, best_value = epoch, value
    return best_epoch, best_value


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Validation loss bottomed out at epoch 30; the next 30 made it worse",
    subtitle: str = "One training run, 60 epochs. The shaded span is everything after the best checkpoint.",
    width: int = 900,
    height: int = 580,
    x: str = "epoch",
    series: str = "split",
    y: str = "loss",
    x_label: str = "Epoch",
    y_label: str = "Loss",
    best_label: Optional[str] = None,
    wasted_label: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full loss-curve SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        One row per epoch per split, with keys named by `x`, `series` and
        `y`. Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    x, series, y : str
        Which key holds the epoch, which splits training from validation,
        and which carries the loss.
    x_label, y_label : str
        Axis titles.
    best_label : str or None
        The label on the best-epoch rule. ``None`` writes the epoch and
        the loss it reached.
    wasted_label : str or None
        The label on the shaded span after the minimum. ``None`` writes
        how many epochs it holds.
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
    curves: Dict[str, List[Tuple[float, float]]] = {}
    for row in rows:
        name = str(row[series])
        if name not in series_names:
            series_names.append(name)
            curves[name] = []
        curves[name].append((float(row[x]), float(row[y])))
    for points in curves.values():
        points.sort()

    validation_name = next(
        (n for n in series_names if not n.lower().startswith("train")), series_names[-1]
    )
    best_epoch, best_value = _best(curves[validation_name])
    epochs = [e for e, _ in curves[series_names[0]]]
    wasted = sum(1 for e in epochs if e > best_epoch)

    everything = [v for points in curves.values() for _, v in points]
    lo, hi = min(everything), max(everything)
    span = (hi - lo) or 1.0
    # `_scale.nice_ticks_range` already solves this, and solving it again by
    # hand here produced an axis running 0 to 4 for data living between 0
    # and 1.6 -- the curves squashed into the bottom quarter, and the
    # overfitting rise this figure exists to show invisible.
    ticks = nice_ticks_range(max(lo - span * 0.08, 0.0), hi + span * 0.06)
    y_lo, y_hi = ticks[0], ticks[-1]

    plot_x, plot_y = 82.0, 156.0
    right_margin, bottom_margin = 118.0, 76.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_margin

    def px(epoch: float) -> float:
        return plot_x + (epoch - epochs[0]) / ((epochs[-1] - epochs[0]) or 1.0) * plot_w

    def py(value: float) -> float:
        return plot_y + plot_h - (value - y_lo) / ((y_hi - y_lo) or 1.0) * plot_h

    best_text = best_label if best_label is not None else (
        f"best epoch {fmt_number(best_epoch)} · {fmt_number(best_value)}"
    )
    wasted_text = wasted_label if wasted_label is not None else (
        f"{wasted} epochs past the minimum" if wasted else ""
    )

    parts: List[str] = []
    parts.append(
        svg_open(width, height, "loss-title", "loss-desc",
                 font_family=chrome_stack_for_theme(theme))
    )
    parts.append(f'<title id="loss-title">{xml_escape(title)}</title>')
    final_gap = abs(
        curves[validation_name][-1][1]
        - curves[series_names[0]][-1][1]
    )
    parts.append(
        f'<desc id="loss-desc">Loss per epoch for '
        f'{xml_escape(", ".join(series_names))} over {len(epochs)} epochs. '
        f'{xml_escape(validation_name)} reaches its minimum of {fmt_number(best_value)} at '
        f'epoch {fmt_number(best_epoch)}; the {wasted} epochs after it are shaded, and over '
        f'them the loss rises rather than falls. At the last epoch the two curves are '
        f'{fmt_number(final_gap)} apart.</desc>'
    )
    parts.append(
        "<style>"
        ".ep{cursor:default;}"
        ".ep:hover,.ep:focus{outline:none;}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        + foreground_tip_css(len(series_names), mark_prefix="ep", tip_prefix="eptip")
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
        f'font-family="{mono_family}">at the last epoch the two are '
        f'{fmt_number(final_gap)} apart</text>'
    )
    parts.append(
        f'<text x="{plot_x:.1f}" y="{plot_y - 14:.1f}" font-size="12" fill="{SECONDARY}">'
        f'{xml_escape(y_label)}</text>'
    )

    # Everything after the minimum, shaded: that span is the answer the
    # chart was drawn to give, and a reader should not have to measure it.
    if wasted:
        parts.append(
            f'<rect x="{px(best_epoch):.1f}" y="{plot_y:.1f}" '
            f'width="{plot_x + plot_w - px(best_epoch):.1f}" height="{plot_h:.1f}" '
            f'fill="{GRIDLINE}" opacity="0.5"/>'
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
    tick_every = max(1, len(epochs) // 6)
    for epoch in epochs[::tick_every]:
        parts.append(
            f'<text x="{px(epoch):.1f}" y="{plot_y + plot_h + 22:.1f}" font-size="11" '
            f'fill="{SECONDARY}" text-anchor="middle" font-family="{mono_family}">'
            f'{fmt_number(epoch)}</text>'
        )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{height - 22:.1f}" font-size="12" '
        f'fill="{SECONDARY}" text-anchor="middle">{xml_escape(x_label)}</text>'
    )

    tips: List[str] = []
    for index, name in enumerate(series_names):
        colour = hues["train"] if name.lower().startswith("train") else hues["valid"]
        parts.append(
            '<polyline points="'
            + " ".join(f"{px(e):.1f},{py(v):.1f}" for e, v in curves[name])
            + f'" fill="none" stroke="{colour}" stroke-width="2.2" stroke-linejoin="round"/>'
        )
        last_epoch, last_value = curves[name][-1]
        parts.append(
            f'<text x="{px(last_epoch) + 10:.1f}" y="{py(last_value) + 4:.1f}" font-size="12" '
            f'font-weight="700" fill="{colour}">{xml_escape(name)}</text>'
        )
        parts.append(
            f'<rect id="ep-{index}" class="ep hit" tabindex="0" role="img" '
            f'aria-label="{xml_escape(name)}: from {fmt_number(curves[name][0][1])} at epoch '
            f'{fmt_number(curves[name][0][0])} to {fmt_number(last_value)} at epoch '
            f'{fmt_number(last_epoch)}" '
            f'x="{plot_x:.1f}" y="{py(max(v for _, v in curves[name])) - 6:.1f}" '
            f'width="{plot_w:.1f}" height="12" fill="transparent">'
            f'<title>{xml_escape(name)}: {fmt_number(last_value)} at the last epoch</title></rect>'
        )
        tips.append(
            tooltip_bubble(
                plot_x + plot_w * 0.5, py(last_value),
                [
                    name,
                    f"start {fmt_number(curves[name][0][1])} · end {fmt_number(last_value)}",
                    f"over {len(curves[name])} epochs",
                ],
                canvas_w=width, canvas_h=height, ink=INK, secondary=SECONDARY,
                border=GRIDLINE, elem_id=f"eptip-{index}",
            )
        )

    # The best epoch: a rule, a dot and the number worth keeping.
    parts.append(
        f'<line x1="{px(best_epoch):.1f}" y1="{plot_y:.1f}" x2="{px(best_epoch):.1f}" '
        f'y2="{plot_y + plot_h:.1f}" stroke="{INK}" stroke-width="1.2" '
        f'stroke-dasharray="4 3"/>'
    )
    parts.append(
        f'<circle cx="{px(best_epoch):.1f}" cy="{py(best_value):.1f}" r="4.6" '
        f'fill="{hues["valid"]}" stroke="{BG}" stroke-width="2"/>'
    )
    parts.append(
        f'<rect x="{px(best_epoch) + 8:.1f}" y="{plot_y + 6:.1f}" '
        f'width="{6.6 * len(best_text) + 10:.1f}" height="19" fill="{BG}" opacity="0.9" rx="3"/>'
    )
    parts.append(
        f'<text x="{px(best_epoch) + 13:.1f}" y="{plot_y + 20:.1f}" font-size="11" '
        f'font-weight="700" fill="{INK}" font-family="{mono_family}">'
        f'{xml_escape(best_text)}</text>'
    )
    if wasted_text:
        parts.append(
            f'<text x="{plot_x + plot_w - 8:.1f}" y="{plot_y + 44:.1f}" '
            f'font-size="11" fill="{SECONDARY}" text-anchor="end" '
            f'font-family="{mono_family}">{xml_escape(wasted_text)}</text>'
        )

    parts.extend(tips)
    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_loss_curve(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "Validation loss bottomed out at epoch 30; the next 30 made it worse",
    subtitle: str = "One training run, 60 epochs. The shaded span is everything after the best checkpoint.",
    width: int = 900,
    height: int = 580,
    x: str = "epoch",
    series: str = "split",
    y: str = "loss",
    x_label: str = "Epoch",
    y_label: str = "Loss",
    best_label: Optional[str] = None,
    wasted_label: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render a hand-authored loss curve and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        One row per epoch per split, with keys ``epoch``, ``split`` and
        ``loss``, or whatever `x`, `series` and `y` name. Defaults to
        DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/loss-curve.svg``.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    x, series, y : str
        Which keys hold the epoch, the split and the loss.
    x_label, y_label : str
        Axis titles.
    best_label, wasted_label : str or None
        Labels on the best-epoch rule and the shaded span; ``None``
        composes each from the data.
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
    >>> p = make_loss_curve()
    >>> p.exists()
    True
    """
    svg = build_svg(
        data, title=title, subtitle=subtitle, width=width, height=height,
        x=x, series=series, y=y, x_label=x_label, y_label=y_label,
        best_label=best_label, wasted_label=wasted_label, mode=mode,
        accessibility=accessibility, theme=theme,
    )
    dest = Path(out) if out else svg_example_path(__file__, "loss-curve")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "loss-curve", build_svg, description="Generate a training loss curve.")


if __name__ == "__main__":
    main()
