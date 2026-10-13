#!/usr/bin/env python3
"""
make_silhouette — one blade per sample, and the points that are in the wrong cluster.

A silhouette plot: every sample's silhouette coefficient drawn as a
horizontal blade, sorted within its cluster, the clusters stacked. The
coefficient runs from −1 to 1 and answers, per sample, "is this point
closer to its own cluster than to the nearest other one?"

It is the standard way to judge a clustering, and the standard version
reports one number -- the overall mean -- which is exactly the number that
hides the problem. A clustering with three tight groups and one incoherent
one averages to "fine".

What this does that the usual version does not
-----------------------------------------------
* **It counts the misfits.** Samples with a negative coefficient are
  closer to another cluster than to their own; that count, per cluster and
  overall, is the actionable finding and it is printed. A reader learns
  which cluster to look at, not merely that the average is 0.55.
* **Every cluster carries its own mean and its own n.** A cluster of nine
  samples averaging 0.7 and one of nine hundred averaging 0.7 are not the
  same evidence, and the usual plot draws them the same height per sample
  and never says the count.
* **The overall mean is a rule across the whole figure**, so each cluster
  is read against it rather than against memory.

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
from _svg import fmt_number, foreground_tip_css, svg_open, tooltip_bubble, xml_escape  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402

#: Four clusters of different quality and different size: two tight, one
#: middling, one that should not have been split off at all. The last is
#: the point of the demo -- a clustering whose overall mean looks
#: acceptable while a quarter of one cluster sits on the wrong side of
#: zero.
_CLUSTERS: Tuple[Tuple[str, int, float, float], ...] = (
    ("Commuters", 120, 0.78, 0.09),
    ("Weekend drivers", 86, 0.71, 0.11),
    ("Night shift", 54, 0.49, 0.18),
    ("Unassigned", 38, 0.12, 0.26),
)


def _samples(seed: int = 23) -> List[Dict[str, Any]]:
    """One row per sample: its cluster and its silhouette coefficient."""
    rng = random.Random(seed)
    rows: List[Dict[str, Any]] = []
    for name, count, centre, spread in _CLUSTERS:
        for index in range(count):
            u1 = max(rng.random(), 1e-12)
            u2 = rng.random()
            draw = centre + spread * math.sqrt(-2.0 * math.log(u1)) * math.cos(
                2.0 * math.pi * u2
            )
            rows.append({
                "cluster": name,
                "sample": f"{name[:2].lower()}-{index:03d}",
                "silhouette": round(max(min(draw, 1.0), -1.0), 4),
            })
    return rows


DEMO_DATA: List[Dict[str, Any]] = _samples()


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "One cluster in four is not a cluster: a quarter of it sits on the wrong side of zero",
    subtitle: str = "Silhouette coefficient per sample, sorted inside each cluster. Negative means closer to another cluster.",
    width: int = 900,
    height: int = 620,
    cluster: str = "cluster",
    value: str = "silhouette",
    sample: str = "sample",
    x_label: str = "Silhouette coefficient",
    mean_label: Optional[str] = None,
    misfit_label: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full silhouette SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        One row per sample, with keys named by `cluster`, `value` and
        optionally `sample`. Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    cluster, value, sample : str
        Which key names the cluster, which carries the coefficient, and
        which identifies the sample in a tooltip.
    x_label : str
        Title under the coefficient axis.
    mean_label : str or None
        The label on the overall-mean rule. ``None`` writes the mean.
    misfit_label : str or None
        The line counting the samples on the wrong side of zero. ``None``
        composes it from the data.
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
    hues = [
        palette.get(name, fallback)
        for name, fallback in (
            ("Blue", "#007AFF"), ("Orange", "#FF9500"), ("Purple", "#AF52DE"),
            ("Green", "#28CD41"), ("Teal", "#79DBDC"), ("Yellow", "#FFCC00"),
        )
    ]
    misfit_colour = palette.get("Red", "#FF3B30")

    order: List[str] = []
    grouped: Dict[str, List[Tuple[float, str]]] = {}
    for row in rows:
        name = str(row[cluster])
        if name not in order:
            order.append(name)
            grouped[name] = []
        grouped[name].append((float(row[value]), str(row.get(sample, ""))))
    # Blades descend inside a cluster: the shape of the wedge is how a
    # reader sees at a glance whether a cluster is uniform or has a tail.
    for blades in grouped.values():
        blades.sort(key=lambda pair: -pair[0])

    total = sum(len(b) for b in grouped.values())
    overall = sum(v for blades in grouped.values() for v, _ in blades) / max(total, 1)
    misfits = {
        name: sum(1 for v, _ in blades if v < 0) for name, blades in grouped.items()
    }
    all_misfits = sum(misfits.values())

    plot_x, plot_y = 214.0, 150.0
    right_margin, bottom_margin = 56.0, 76.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_margin

    lowest = min(v for blades in grouped.values() for v, _ in blades)
    x_lo = min(-0.2, math.floor(lowest * 10) / 10)
    x_hi = 1.0
    gap_between_clusters = 14.0
    usable = plot_h - gap_between_clusters * (len(order) - 1)
    blade_h = usable / max(total, 1)

    def px(v: float) -> float:
        return plot_x + (v - x_lo) / ((x_hi - x_lo) or 1.0) * plot_w

    if misfit_label is not None:
        said = misfit_label
    elif all_misfits:
        worst = max(misfits, key=lambda name: misfits[name])
        share = misfits[worst] / len(grouped[worst]) * 100.0
        said = (
            f"{all_misfits} of {total} samples sit below zero, {misfits[worst]} of them "
            f"in {worst} — {share:.0f}% of that cluster"
        )
    else:
        said = f"no sample of {total} sits below zero"
    mean_text = mean_label if mean_label is not None else f"mean {fmt_number(overall)}"

    parts: List[str] = []
    parts.append(
        svg_open(width, height, "sil-title", "sil-desc",
                 font_family=chrome_stack_for_theme(theme))
    )
    parts.append(f'<title id="sil-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="sil-desc">A silhouette plot of {total} samples in {len(order)} '
        f'clusters: {xml_escape(", ".join(order))}. Each sample is one horizontal blade, '
        f'sorted descending inside its cluster. The overall mean coefficient is '
        f'{fmt_number(overall)}. {xml_escape(said)}.</desc>'
    )
    parts.append(
        "<style>"
        ".cl{cursor:default;}"
        ".cl:hover,.cl:focus{outline:none;}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        + foreground_tip_css(len(order), mark_prefix="cl", tip_prefix="cltip")
        + "@media (prefers-reduced-motion:reduce){.tip{transition:none}}"
        "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="{plot_x - 154:.1f}" y="46" font-size="22" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(
        f'<text x="{plot_x - 154:.1f}" y="72" font-size="14" fill="{SECONDARY}">'
        f'{xml_escape(subtitle)}</text>'
    )
    parts.append(
        f'<text x="{plot_x - 154:.1f}" y="98" font-size="12" fill="{SECONDARY}" '
        f'font-family="{mono_family}">{xml_escape(said)}</text>'
    )

    for tick in [x for x in (-0.2, 0.0, 0.2, 0.4, 0.6, 0.8, 1.0) if x_lo <= x <= x_hi]:
        gx = px(tick)
        parts.append(
            f'<line x1="{gx:.1f}" y1="{plot_y:.1f}" x2="{gx:.1f}" '
            f'y2="{plot_y + plot_h:.1f}" stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{gx:.1f}" y="{plot_y + plot_h + 22:.1f}" font-size="11" '
            f'fill="{SECONDARY}" text-anchor="middle" font-family="{mono_family}">'
            f'{fmt_number(tick)}</text>'
        )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{height - 24:.1f}" font-size="12" '
        f'fill="{SECONDARY}" text-anchor="middle">{xml_escape(x_label)}</text>'
    )

    tips: List[str] = []
    cursor = plot_y
    for index, name in enumerate(order):
        blades = grouped[name]
        colour = hues[index % len(hues)]
        cluster_mean = sum(v for v, _ in blades) / len(blades)
        band_top = cursor
        if blade_h >= 2.5:
            # Thick enough to read as individual blades, which is the
            # classic form and worth keeping when the cluster is small.
            for v, _ in blades:
                left = min(px(v), px(0.0))
                right = max(px(v), px(0.0))
                parts.append(
                    f'<rect x="{left:.1f}" y="{cursor:.2f}" '
                    f'width="{max(right - left, 0.6):.1f}" '
                    f'height="{max(blade_h - 0.3, 0.5):.2f}" '
                    f'fill="{misfit_colour if v < 0 else colour}"/>'
                )
                cursor += blade_h
        else:
            # Below about two pixels a blade is not a blade: drawn as
            # hundreds of thin rects at fractional offsets it rasterises
            # into alternating light and dark rows, and the first render of
            # this figure came out striped. The sorted profile is the same
            # information as one filled shape, and it is what the eye was
            # reading off the blades anyway. Positive and negative are two
            # polygons so the wrong-side samples keep their own colour.
            for low, high, fill in (
                (0.0, 1.0, colour), (-1.0, 0.0, misfit_colour),
            ):
                picked = [
                    (index, v) for index, (v, _) in enumerate(blades) if low <= v <= high
                ]
                if not picked:
                    continue
                top = cursor + picked[0][0] * blade_h
                bottom = cursor + (picked[-1][0] + 1) * blade_h
                outline = " ".join(
                    f"{px(v):.1f},{cursor + index * blade_h:.2f}" for index, v in picked
                )
                parts.append(
                    f'<polygon points="{px(0.0):.1f},{top:.2f} {outline} '
                    f'{px(0.0):.1f},{bottom:.2f}" fill="{fill}"/>'
                )
            cursor += blade_h * len(blades)
        band_bottom = cursor

        parts.append(
            f'<text x="{plot_x - 12:.1f}" y="{(band_top + band_bottom) / 2 - 2:.1f}" '
            f'font-size="12" font-weight="700" fill="{INK}" text-anchor="end">'
            f'{xml_escape(name)}</text>'
        )
        # Two lines rather than one: "n 38 · mean 0.09 · 10 below zero" ran
        # off the left edge of the canvas on the first two renders.
        captions = [f"n {len(blades)} · mean {fmt_number(cluster_mean)}"]
        if misfits[name]:
            captions.append(f"{misfits[name]} below zero")
        for line_index, line in enumerate(captions):
            parts.append(
                f'<text x="{plot_x - 12:.1f}" '
                f'y="{(band_top + band_bottom) / 2 + 13 + line_index * 15:.1f}" '
                f'font-size="11" fill="{SECONDARY}" text-anchor="end" '
                f'font-family="{mono_family}">{xml_escape(line)}</text>'
            )
        parts.append(
            f'<rect id="cl-{index}" class="cl hit" tabindex="0" role="img" '
            f'aria-label="{xml_escape(name)}: {len(blades)} samples, mean silhouette '
            f'{fmt_number(cluster_mean)}, {misfits[name]} below zero" '
            f'x="{plot_x:.1f}" y="{band_top:.1f}" width="{plot_w:.1f}" '
            f'height="{max(band_bottom - band_top, 2):.1f}" fill="transparent">'
            f'<title>{xml_escape(name)}: {fmt_number(cluster_mean)} over '
            f'{len(blades)} samples</title></rect>'
        )
        tips.append(
            tooltip_bubble(
                plot_x + plot_w * 0.62, (band_top + band_bottom) / 2,
                [
                    name,
                    f"{len(blades)} samples · mean {fmt_number(cluster_mean)}",
                    f"{misfits[name]} below zero",
                ],
                canvas_w=width, canvas_h=height, ink=INK, secondary=SECONDARY,
                border=GRIDLINE, elem_id=f"cltip-{index}",
            )
        )
        cursor += gap_between_clusters

    # Zero, then the overall mean: the first says which samples are in the
    # wrong cluster, the second is what every cluster is read against.
    parts.append(
        f'<line x1="{px(0.0):.1f}" y1="{plot_y:.1f}" x2="{px(0.0):.1f}" '
        f'y2="{plot_y + plot_h:.1f}" stroke="{INK}" stroke-width="1.2"/>'
    )
    parts.append(
        f'<line x1="{px(overall):.1f}" y1="{plot_y - 8:.1f}" x2="{px(overall):.1f}" '
        f'y2="{plot_y + plot_h:.1f}" stroke="{INK}" stroke-width="1.4" '
        f'stroke-dasharray="5 3"/>'
    )
    parts.append(
        f'<rect x="{px(overall) - 3:.1f}" y="{plot_y - 26:.1f}" '
        f'width="{6.6 * len(mean_text) + 8:.1f}" height="18" fill="{BG}" opacity="0.9" rx="3"/>'
    )
    parts.append(
        f'<text x="{px(overall) + 2:.1f}" y="{plot_y - 13:.1f}" font-size="11" '
        f'font-weight="700" fill="{INK}" font-family="{mono_family}">'
        f'{xml_escape(mean_text)}</text>'
    )

    parts.extend(tips)
    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_silhouette(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "One cluster in four is not a cluster: a quarter of it sits on the wrong side of zero",
    subtitle: str = "Silhouette coefficient per sample, sorted inside each cluster. Negative means closer to another cluster.",
    width: int = 900,
    height: int = 620,
    cluster: str = "cluster",
    value: str = "silhouette",
    sample: str = "sample",
    x_label: str = "Silhouette coefficient",
    mean_label: Optional[str] = None,
    misfit_label: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Render a hand-authored silhouette plot and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        One row per sample, with keys ``cluster``, ``silhouette`` and
        optionally ``sample``. Defaults to DEMO_DATA.
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/silhouette.svg``.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    cluster, value, sample : str
        Which keys name the cluster, the coefficient and the sample.
    x_label : str
        Title under the coefficient axis.
    mean_label, misfit_label : str or None
        The mean rule's label and the wrong-side-of-zero line; ``None``
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
    >>> p = make_silhouette()
    >>> p.exists()
    True
    """
    svg = build_svg(
        data, title=title, subtitle=subtitle, width=width, height=height,
        cluster=cluster, value=value, sample=sample, x_label=x_label,
        mean_label=mean_label, misfit_label=misfit_label, mode=mode,
        accessibility=accessibility, theme=theme,
    )
    dest = Path(out) if out else svg_example_path(__file__, "silhouette")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "silhouette", build_svg, description="Generate a silhouette plot.")


if __name__ == "__main__":
    main()
