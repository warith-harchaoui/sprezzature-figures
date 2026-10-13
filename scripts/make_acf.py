#!/usr/bin/env python3
"""
make_acf — the correlogram: what the series still remembers, and at which lag.

Autocorrelation at each lag, drawn as stems from zero, with the band
inside which a lag is indistinguishable from noise. Two panels, because
the pair is what a reader needs: the autocorrelation function says how far
back the series remembers, the *partial* one says how much of that memory
is direct rather than inherited through the lags in between. One without
the other picks the wrong model order.

Where the usual correlogram goes wrong
--------------------------------------
* **Lag 0 is plotted.** It is 1 by definition -- a series correlates
  perfectly with itself -- and plotting it spends the whole vertical range
  on a fact, squashing every lag that carries information into the bottom
  tenth. Dropped here by default, and the chrome says it was.
* **The band is drawn and never named.** It is the white-noise null at
  95%, ±1.96/√n: "if this series were noise, a lag would land outside this
  band one time in twenty". Readers routinely take it for a confidence
  interval on the coefficient, which is a different claim. The band is
  labelled with its formula and its n.
* **Nothing says which lags matter.** The lags that cross the band are
  the finding; they are coloured apart and listed in the chrome, with the
  seasonal period called out when the crossings are its multiples.

The coefficients are computed here, from the series. A caller has a time
series, not a table of autocorrelations, and making them run statsmodels
first to draw a picture of their own data is the kind of step that stops a
figure from being drawn at all.

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
from _style import BG, GRIDLINE, INK, SECONDARY, load_palette  # noqa: E402
from _svg import (  # noqa: E402
    fmt_number,
    foreground_tip_css,
    svg_open,
    tooltip_bubble,
    wrap_no_orphan,
    xml_escape,
)
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402

_MONTHS = 144


def _series(seed: int = 31) -> List[Dict[str, Any]]:
    """Twelve years of monthly demand: a December, a carry-over, and noise.

    Two drafts were thrown away here, and both failures are worth keeping
    written down because both produce a correlogram that looks busy and
    says nothing.

    The first had a linear trend. A series that climbs correlates with
    itself at *every* lag: 31 of 36 crossed the band, and the figure's
    only message was "this goes up". A correlogram is read on a stationary
    series.

    The second made the season a sine wave. The autocorrelation of a
    sinusoid is a sinusoid -- it never decays, so 30 of 36 lags crossed
    and the panel came out a ripple with no quiet stretches to measure
    against. Real seasonality is a *shape*, not a tone: one month far
    from the others. A spike-shaped profile has an autocorrelation that
    is near zero away from the multiples of the period, which is what
    makes the spikes at 12, 24 and 36 legible as spikes.

    What is left carries both lessons the pair of panels exists to teach:
    the autocorrelation is significant at lags 1 and 2, and again at 12,
    24, 36; the partial autocorrelation keeps lag 1 and lag 12 and drops
    lag 2, because the second month is inherited through the first rather
    than remembered directly.
    """
    rng = random.Random(seed)
    december = 13.0
    other_months = -december / 11.0  # so the yearly profile averages to zero
    rows: List[Dict[str, Any]] = []
    level = 0.0
    for index in range(_MONTHS):
        level = 0.72 * level + (rng.random() - 0.5) * 9.0
        month_of_year = index % 12 + 1
        seasonal = december if month_of_year == 12 else other_months
        rows.append({
            "month": index + 1,
            "demand": round(220.0 + seasonal + level, 2),
        })
    return rows


DEMO_DATA: List[Dict[str, Any]] = _series()


def _autocorrelations(values: List[float], max_lag: int) -> List[float]:
    """r_k for k = 0..max_lag, on the usual single-denominator estimator.

    One denominator for every lag -- the sum of squared deviations over the
    whole series -- rather than a per-lag one. It is the estimator every
    statistics package uses by default, it keeps the sequence positive
    semi-definite, and it is what the ±1.96/√n band is derived for.
    """
    n = len(values)
    mean = sum(values) / n
    deviations = [v - mean for v in values]
    denominator = sum(d * d for d in deviations) or 1.0
    out: List[float] = []
    for lag in range(max_lag + 1):
        numerator = sum(
            deviations[t] * deviations[t - lag] for t in range(lag, n)
        )
        out.append(numerator / denominator)
    return out


def _partials(acf: List[float]) -> List[float]:
    """Partial autocorrelations by the Durbin-Levinson recursion.

    The partial coefficient at lag k is the correlation left between a
    point and its k-th predecessor once the lags in between have been
    accounted for -- which is what separates "the series remembers twelve
    months back" from "the series remembers one month back, twelve times
    over".
    """
    max_lag = len(acf) - 1
    phi: List[List[float]] = [[0.0] * (max_lag + 1) for _ in range(max_lag + 1)]
    out = [1.0]
    if max_lag >= 1:
        phi[1][1] = acf[1]
        out.append(phi[1][1])
    for k in range(2, max_lag + 1):
        numerator = acf[k] - sum(phi[k - 1][j] * acf[k - j] for j in range(1, k))
        denominator = 1.0 - sum(phi[k - 1][j] * acf[j] for j in range(1, k))
        phi[k][k] = numerator / denominator if denominator else 0.0
        for j in range(1, k):
            phi[k][j] = phi[k - 1][j] - phi[k][k] * phi[k - 1][k - j]
        out.append(phi[k][k])
    return out


def _seasonal_note(significant: List[int], period_hint: int) -> str:
    """Name the season when the crossings are its multiples, else say nothing.

    Deliberately conservative: it only speaks when at least two multiples
    of the period are among the significant lags, because one lag at 12 on
    a monthly series is as likely to be luck as a season.
    """
    if period_hint < 2:
        return ""
    multiples = [lag for lag in significant if lag % period_hint == 0]
    if len(multiples) < 2:
        return ""
    return (
        f" The crossings at {', '.join(str(lag) for lag in multiples)} are multiples of "
        f"{period_hint}: that is a season, not a trend."
    )


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "A December that returns every year, and one month of memory under it",
    subtitle: str = "Twelve years of monthly demand. A stem outside the band is what white noise produces at one lag in twenty.",
    width: int = 900,
    height: int = 660,
    x: str = "month",
    y: str = "demand",
    max_lag: int = 36,
    period_hint: int = 12,
    include_zero: bool = False,
    acf_label: str = "Autocorrelation",
    pacf_label: str = "Partial autocorrelation",
    x_label: str = "Lag (months)",
    band_label: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full correlogram SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        The time series itself, one row per observation, ordered by `x`
        and measured by `y`. Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    x, y : str
        Which key orders the series and which carries the value.
    max_lag : int
        How many lags to compute. Past about a quarter of the series
        length the estimates are built on too few pairs to trust, so the
        chrome says how many observations each lag rests on.
    period_hint : int
        The season to test for -- 12 for monthly data, 7 for daily, 4 for
        quarterly. Only used to decide whether to name a season in the
        finding; 0 disables it.
    include_zero : bool
        Plot lag 0. It is 1 by definition and spends the whole vertical
        range saying so, which is why it is off.
    acf_label, pacf_label, x_label : str
        Panel titles and the shared axis title.
    band_label : str or None
        What the significance band is, in words. ``None`` writes the
        formula and the n it was computed from.
    finding : str or None
        The sentence naming the significant lags. ``None`` composes it.
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
    def position(row: Dict[str, Any]) -> Tuple[int, float, str]:
        """Sort key that works for a month number and for "2026-01" alike.

        A correlogram needs the series *in order*; it never needs the
        positions as numbers. Forcing a float here rejected every series
        whose index is a date string, which is most of them.
        """
        raw = row[x]
        try:
            return (0, float(raw), "")
        except (TypeError, ValueError):
            return (1, 0.0, str(raw))

    rows = sorted(data if data else DEMO_DATA, key=position)
    values = [float(row[y]) for row in rows]
    n = len(values)
    mono_family = mono_stack_for_theme(theme)
    palette = load_palette(accessibility, theme=theme)
    inside = palette.get("Blue", "#007AFF")
    outside = palette.get("Orange", "#FF9500")

    lag_cap = max(1, min(max_lag, n - 2))
    acf = _autocorrelations(values, lag_cap)
    pacf = _partials(acf)
    first_lag = 0 if include_zero else 1
    lags = list(range(first_lag, lag_cap + 1))

    # The white-noise null at 95%: if the series were noise, a coefficient
    # would land outside this band about one lag in twenty.
    band = 1.959964 / math.sqrt(n)
    significant = [lag for lag in lags if lag > 0 and abs(acf[lag]) > band]

    plot_x = 92.0
    right_margin = 40.0
    plot_w = width - plot_x - right_margin
    panel_h = 182.0
    panels = (
        (acf_label, acf, 178.0),
        (pacf_label, pacf, 178.0 + panel_h + 56.0),
    )

    reach = max(
        max(abs(acf[lag]) for lag in lags),
        max(abs(pacf[lag]) for lag in lags),
        band * 1.6,
    )
    limit = min(1.0, math.ceil(reach * 10) / 10)

    def px(lag: int) -> float:
        return plot_x + (lag - lags[0]) / max(len(lags) - 1, 1) * plot_w

    def py(value: float, top: float) -> float:
        return top + panel_h / 2.0 - value / (limit or 1.0) * (panel_h / 2.0)

    said_band = band_label if band_label is not None else (
        f"band ±{fmt_number(band)} = ±1.96/√{n}, the 95% white-noise null"
    )
    if finding is not None:
        said = finding
    elif significant:
        shown = ", ".join(str(lag) for lag in significant[:8])
        more = f" and {len(significant) - 8} more" if len(significant) > 8 else ""
        said = (
            f"{len(significant)} of {lag_cap} lags cross the band: {shown}{more}."
            + _seasonal_note(significant, period_hint)
        )
    else:
        said = f"No lag of {lag_cap} crosses the band: this looks like noise."

    parts: List[str] = []
    parts.append(
        svg_open(width, height, "acf-title", "acf-desc",
                 font_family=chrome_stack_for_theme(theme))
    )
    parts.append(f'<title id="acf-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="acf-desc">Two correlograms of a series of {n} observations, for lags '
        f'{lags[0]} to {lag_cap}: {xml_escape(acf_label)} above, {xml_escape(pacf_label)} '
        f'below. Each stem is one lag; the shaded band is the 95% white-noise null at plus or '
        f'minus {fmt_number(band)}. {xml_escape(said)}</desc>'
    )
    parts.append(
        "<style>"
        ".lag{cursor:default;}"
        ".lag:hover,.lag:focus{outline:none;}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        + foreground_tip_css(len(lags) * 2, mark_prefix="lag", tip_prefix="lagtip")
        + "@media (prefers-reduced-motion:reduce){.tip{transition:none}}"
        "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="{plot_x - 60:.1f}" y="46" font-size="22" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(
        f'<text x="{plot_x - 60:.1f}" y="72" font-size="14" fill="{SECONDARY}">'
        f'{xml_escape(subtitle)}</text>'
    )
    parts.append(
        f'<text x="{plot_x - 60:.1f}" y="98" font-size="12" fill="{SECONDARY}" '
        f'font-family="{mono_family}">{xml_escape(said_band)}'
        + ("" if include_zero else " · lag 0 omitted, it is 1 by definition")
        + '</text>'
    )
    # Wrapped, not clipped: the finding names every crossing it found and
    # the seasonal reading on top, which on a seasonal series runs past the
    # canvas on one line.
    for line_index, line in enumerate(wrap_no_orphan(said, 96)[:2]):
        parts.append(
            f'<text x="{plot_x - 60:.1f}" y="{118 + line_index * 17:.1f}" font-size="12" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(line)}</text>'
        )

    tips: List[str] = []
    for panel_index, (label, coefficients, top) in enumerate(panels):
        parts.append(
            f'<text x="{plot_x:.1f}" y="{top - 12:.1f}" font-size="13" font-weight="700" '
            f'fill="{INK}">{xml_escape(label)}</text>'
        )
        parts.append(
            f'<rect x="{plot_x:.1f}" y="{py(band, top):.1f}" width="{plot_w:.1f}" '
            f'height="{py(-band, top) - py(band, top):.1f}" fill="{inside}" opacity="0.12"/>'
        )
        parts.append(
            f'<line x1="{plot_x:.1f}" y1="{py(0.0, top):.1f}" x2="{plot_x + plot_w:.1f}" '
            f'y2="{py(0.0, top):.1f}" stroke="{INK}" stroke-width="1"/>'
        )
        for value_at in (-limit, -limit / 2.0, limit / 2.0, limit):
            parts.append(
                f'<text x="{plot_x - 10:.1f}" y="{py(value_at, top) + 4:.1f}" font-size="10" '
                f'fill="{SECONDARY}" text-anchor="end" font-family="{mono_family}">'
                f'{fmt_number(value_at)}</text>'
            )
        for lag in lags:
            value = coefficients[lag]
            crosses = lag > 0 and abs(value) > band
            colour = outside if crosses else inside
            element = len(tips)
            parts.append(
                f'<line x1="{px(lag):.1f}" y1="{py(0.0, top):.1f}" x2="{px(lag):.1f}" '
                f'y2="{py(value, top):.1f}" stroke="{colour}" stroke-width="2.4" '
                f'stroke-linecap="round"/>'
            )
            parts.append(
                f'<circle cx="{px(lag):.1f}" cy="{py(value, top):.1f}" r="3" fill="{colour}"/>'
            )
            parts.append(
                f'<rect id="lag-{element}" class="lag hit" tabindex="0" role="img" '
                f'aria-label="{xml_escape(label)} at lag {lag}: {fmt_number(value)}'
                f'{", outside the band" if crosses else ", inside the band"}" '
                f'x="{px(lag) - 6:.1f}" y="{top:.1f}" width="12" height="{panel_h:.1f}" '
                f'fill="transparent"><title>lag {lag}: {fmt_number(value)}</title></rect>'
            )
            tips.append(
                tooltip_bubble(
                    px(lag), py(value, top),
                    [
                        f"{label} · lag {lag}",
                        fmt_number(value),
                        "outside the band" if crosses else "inside the band",
                    ],
                    canvas_w=width, canvas_h=height, ink=INK, secondary=SECONDARY,
                    border=GRIDLINE, elem_id=f"lagtip-{element}",
                )
            )
        if panel_index == len(panels) - 1:
            step = max(1, len(lags) // 12)
            for lag in lags[::step]:
                parts.append(
                    f'<text x="{px(lag):.1f}" y="{top + panel_h + 20:.1f}" font-size="11" '
                    f'fill="{SECONDARY}" text-anchor="middle" font-family="{mono_family}">'
                    f'{lag}</text>'
                )
            parts.append(
                f'<text x="{plot_x + plot_w / 2:.1f}" y="{top + panel_h + 46:.1f}" '
                f'font-size="12" fill="{SECONDARY}" text-anchor="middle">'
                f'{xml_escape(x_label)}</text>'
            )

    parts.extend(tips)
    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_acf(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "A December that returns every year, and one month of memory under it",
    subtitle: str = "Twelve years of monthly demand. A stem outside the band is what white noise produces at one lag in twenty.",
    width: int = 900,
    height: int = 660,
    x: str = "month",
    y: str = "demand",
    max_lag: int = 36,
    period_hint: int = 12,
    include_zero: bool = False,
    acf_label: str = "Autocorrelation",
    pacf_label: str = "Partial autocorrelation",
    x_label: str = "Lag (months)",
    band_label: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render a hand-authored correlogram and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        The time series, with keys ``month`` and ``demand``, or whatever
        `x` and `y` name. The autocorrelations are computed here.
        Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/acf.svg``.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    x, y : str
        Which key orders the series and which carries the value.
    max_lag : int
        How many lags to compute.
    period_hint : int
        Season to test for when naming the finding; 0 disables it.
    include_zero : bool
        Plot lag 0, which is 1 by definition.
    acf_label, pacf_label, x_label : str
        Panel titles and the shared axis title.
    band_label, finding : str or None
        What the band is, and the sentence naming the significant lags;
        ``None`` composes each from the data.
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
    >>> p = make_acf()
    >>> p.exists()
    True
    """
    svg = build_svg(
        data, title=title, subtitle=subtitle, width=width, height=height,
        x=x, y=y, max_lag=max_lag, period_hint=period_hint,
        include_zero=include_zero, acf_label=acf_label, pacf_label=pacf_label,
        x_label=x_label, band_label=band_label, finding=finding, mode=mode,
        accessibility=accessibility, theme=theme,
    )
    dest = Path(out) if out else svg_example_path(__file__, "acf")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "acf", build_svg,
               description="Generate an autocorrelation correlogram (ACF and PACF).")


if __name__ == "__main__":
    main()
