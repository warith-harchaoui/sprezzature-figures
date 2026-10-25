#!/usr/bin/env python3
"""
make_missing-matrix — where the holes are, and whether they fall together.

One column per field, one row per record, a mark wherever a value is
absent. The first thing anyone does with a new table is count the nulls;
the second thing, if they are careful, is ask whether the nulls line up.
This draws both, and the second is the one that changes what you do next.

Where the usual missingness plot goes wrong
--------------------------------------------
* **It reports a percentage per column and stops.** "age is 12% missing"
  tells you how much is gone, never whether it is gone at random. Two
  columns missing in the same records mean one cause, and dropping rows
  on one of them silently drops the other. The columns here are ranked by
  how often they go missing *together* with another column, and the
  strongest pair is named.
* **Every record gets a row of pixels.** At a hundred thousand records
  that is a grey smear; at a thousand it is unreadable. Records are
  binned into bands, each band shaded by how many of its records are
  missing that field, so the picture holds its shape at any size and the
  chrome says how many records a band stands for.
* **The order of the records is thrown away.** Missingness is very often
  a function of *when*: a field added in March is absent before March,
  and that is the whole explanation. Records are drawn in the order they
  arrive, so a block of absence at one end is visible as a block rather
  than averaged into a percentage.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

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

_RECORDS = 1800
_LATE_FIELD_FROM = 1100


def _records(seed: int = 11) -> List[Dict[str, Any]]:
    """Eighteen hundred patient records with four kinds of hole in them.

    Each kind is a different story, and the point of the figure is that
    they look different on the page:

    ``consent_date`` is absent before record 1100 and present after --
    a field that was added, which is the single most common cause of a
    hole and the one a per-column percentage hides completely.

    ``weight`` and ``height`` go missing together: the same visits
    skipped the whole physical measurement. Dropping records on one of
    them drops the other, and anyone treating them as independent losses
    twice what they think.

    ``referrer`` is missing at random, about one record in nine, with no
    partner and no pattern. It is here as the control: the case where
    "12% missing" really is the whole story.
    """
    rng = random.Random(seed)
    rows: List[Dict[str, Any]] = []
    for index in range(_RECORDS):
        skipped_physical = rng.random() < 0.14
        rows.append(
            {
                "patient": f"P{index + 1:05d}",
                "age": None if rng.random() < 0.02 else rng.randint(18, 89),
                "weight": None if skipped_physical else round(rng.uniform(48.0, 112.0), 1),
                "height": None
                if skipped_physical or rng.random() < 0.01
                else round(rng.uniform(1.50, 1.96), 2),
                "referrer": None if rng.random() < 0.11 else rng.choice(["GP", "A&E", "self"]),
                "consent_date": None
                if index < _LATE_FIELD_FROM
                else f"2025-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
            }
        )
    return rows


DEMO_DATA: List[Dict[str, Any]] = _records()


def _is_missing(value: Any, blanks_count: bool) -> bool:
    """Whether `value` counts as absent.

    ``None`` always does. An empty string counts only when `blanks_count`
    says so, because a blank is a different claim from a null in some
    tables -- an answer of "nothing" rather than no answer -- and reading
    one as the other is how a column comes to look 40% missing.
    """
    if value is None:
        return True
    return blanks_count and isinstance(value, str) and not value.strip()


def _pair_overlap(
    columns: Sequence[str], absent: Dict[str, List[bool]]
) -> Tuple[Optional[Tuple[str, str]], float]:
    """The pair of columns that most often goes missing together.

    Measured as the Jaccard overlap of the two sets of records -- shared
    absences over absences in either -- rather than as a raw count, so a
    column that is mostly empty does not pair with everything simply by
    being large.
    """
    best: Optional[Tuple[str, str]] = None
    best_score = 0.0
    for first_index, first in enumerate(columns):
        for second in columns[first_index + 1 :]:
            left, right = absent[first], absent[second]
            both = sum(1 for a, b in zip(left, right, strict=True) if a and b)
            either = sum(1 for a, b in zip(left, right, strict=True) if a or b)
            score = both / either if either else 0.0
            if score > best_score:
                best, best_score = (first, second), score
    return best, best_score


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "One field was added partway through; two others go missing together",
    subtitle: str = "Eighteen hundred patient records in arrival order, one column per field, shaded where values are absent.",
    width: int = 900,
    height: int = 620,
    columns: Optional[List[str]] = None,
    bands: int = 60,
    blanks_count: bool = True,
    order_label: str = "Records, in arrival order",
    complete_label: str = "complete",
    missing_label: str = "missing",
    pair_note: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full missingness matrix SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        The records, in the order they should be drawn. Defaults to
        :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    columns : list of str or None
        Which fields to draw, left to right. ``None`` takes every key
        present in the first record.
    bands : int
        How many horizontal bands the records are binned into. Each band
        is shaded by the share of its records missing that field.
    blanks_count : bool
        Whether an empty string counts as missing alongside ``None``.
    order_label : str
        Title on the vertical axis of records.
    complete_label, missing_label : str
        The two ends of the shading key.
    pair_note, finding : str or None
        The line naming the pair that most often goes missing together,
        and the sentence summarising the holes; ``None`` composes each
        from the data.
    mode : str
        ``"self-contained"`` keeps the interactive chrome inside the file.
    accessibility : str
        Palette variant.
    theme : str
        Visual theme.

    Returns
    -------
    str
        The SVG document.
    """
    rows = list(data if data else DEMO_DATA)
    if not rows:
        raise ValueError("a missingness matrix needs at least one record")
    fields = list(columns) if columns else list(rows[0].keys())
    if not fields:
        raise ValueError("no columns to draw: the first record has no keys")
    unknown = [field for field in fields if not any(field in row for row in rows)]
    if unknown:
        raise ValueError(f"no record carries the column(s) {unknown}")

    n = len(rows)
    absent = {
        field: [_is_missing(row.get(field), blanks_count) for row in rows] for field in fields
    }
    counts = {field: sum(flags) for field, flags in absent.items()}
    band_count = max(1, min(bands, n))
    band_size = n / band_count

    mono_family = mono_stack_for_theme(theme)
    palette = load_palette(accessibility, theme=theme)
    present_ink = palette.get("Blue", "#007AFF")
    absent_ink = palette.get("Orange", "#FF9500")

    plot_x = 150.0
    plot_y = 232.0
    plot_w = width - plot_x - 56.0
    plot_h = height - plot_y - 86.0
    column_w = plot_w / len(fields)
    band_h = plot_h / band_count

    def share(field: str, band: int) -> float:
        """The fraction of band `band`'s records missing `field`."""
        start = int(round(band * band_size))
        stop = max(start + 1, int(round((band + 1) * band_size)))
        window = absent[field][start:stop]
        return sum(window) / len(window) if window else 0.0

    pair, overlap = _pair_overlap(fields, absent)
    said_pair = (
        pair_note
        if pair_note is not None
        else (
            f"{pair[0]} and {pair[1]} share {fmt_number(overlap * 100.0)}% of their absences"
            if pair and overlap > 0.0
            else "no two columns go missing together"
        )
    )
    worst = max(counts, key=lambda field: counts[field]) if counts else ""
    said_parts: List[str] = []
    if finding is not None:
        said_parts.append(finding)
    else:
        empty = [field for field in fields if counts[field] == 0]
        said_parts.append(
            f"{worst} is the emptiest at {fmt_number(counts[worst] / n * 100.0)}% of {n} records."
        )
        if empty:
            said_parts.append(
                f"{len(empty)} of {len(fields)} columns "
                f"{'has' if len(empty) == 1 else 'have'} no holes at all: "
                f"{', '.join(empty)}."
            )
    said_lines: List[str] = []
    for sentence in said_parts:
        said_lines.extend(wrap_no_orphan(sentence, 98))

    parts: List[str] = []
    parts.append(
        svg_open(
            width, height, "miss-title", "miss-desc", font_family=chrome_stack_for_theme(theme)
        )
    )
    parts.append(f'<title id="miss-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="miss-desc">A missingness matrix of {n} records across '
        f"{len(fields)} columns: {xml_escape(', '.join(fields))}. Records run top to "
        f"bottom in order, binned into {band_count} bands, each shaded by the share of "
        f"its records missing that column. {xml_escape(said_pair)}. "
        f"{xml_escape(' '.join(said_parts))}</desc>"
    )
    parts.append(
        "<style>"
        ".cell{cursor:default;}"
        ".cell:hover,.cell:focus{outline:none;}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        + foreground_tip_css(len(fields) * band_count, mark_prefix="cell", tip_prefix="celltip")
        + "@media (prefers-reduced-motion:reduce){.tip{transition:none}}"
        "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="40" y="46" font-size="22" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    for line_index, line in enumerate(wrap_no_orphan(subtitle, 104)[:2]):
        parts.append(
            f'<text x="40" y="{72 + line_index * 20:.1f}" font-size="14" '
            f'fill="{SECONDARY}">{xml_escape(line)}</text>'
        )
    for line_index, line in enumerate(wrap_no_orphan(said_pair, 98)[:2]):
        parts.append(
            f'<text x="40" y="{124 + line_index * 17:.1f}" font-size="12" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(line)}</text>'
        )
    for line_index, line in enumerate(said_lines[:2]):
        parts.append(
            f'<text x="40" y="{162 + line_index * 17:.1f}" font-size="12" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(line)}</text>'
        )

    tips: List[str] = []
    for field_index, field in enumerate(fields):
        left = plot_x + field_index * column_w
        parts.append(
            f'<text x="{left + column_w / 2:.1f}" y="{plot_y - 28:.1f}" font-size="12" '
            f'font-weight="700" fill="{INK}" text-anchor="middle">{xml_escape(field)}</text>'
        )
        parts.append(
            f'<text x="{left + column_w / 2:.1f}" y="{plot_y - 11:.1f}" font-size="11" '
            f'fill="{SECONDARY}" text-anchor="middle" font-family="{mono_family}">'
            f"{fmt_number(counts[field] / n * 100.0)}%</text>"
        )
        for band in range(band_count):
            fraction = share(field, band)
            top = plot_y + band * band_h
            parts.append(
                f'<rect x="{left + 1:.1f}" y="{top:.1f}" width="{column_w - 2:.1f}" '
                f'height="{band_h + 0.5:.1f}" fill="{absent_ink if fraction else present_ink}" '
                f'opacity="{0.08 + 0.84 * fraction if fraction else 0.10:.2f}"/>'
            )
            element = len(tips)
            start = int(round(band * band_size)) + 1
            stop = max(start, int(round((band + 1) * band_size)))
            parts.append(
                f'<rect id="cell-{element}" class="cell hit" tabindex="0" role="img" '
                f'aria-label="{xml_escape(field)}, records {start} to {stop}: '
                f'{fmt_number(fraction * 100.0)}% missing" '
                f'x="{left + 1:.1f}" y="{top:.1f}" width="{column_w - 2:.1f}" '
                f'height="{band_h + 0.5:.1f}" fill="transparent">'
                f"<title>{xml_escape(field)} {start}-{stop}: "
                f"{fmt_number(fraction * 100.0)}%</title></rect>"
            )
            tips.append(
                tooltip_bubble(
                    left + column_w / 2,
                    top + band_h / 2,
                    [
                        f"{field} · {start}-{stop}",
                        f"{fmt_number(fraction * 100.0)}% {missing_label}",
                    ],
                    canvas_w=width,
                    canvas_h=height,
                    ink=INK,
                    secondary=SECONDARY,
                    border=GRIDLINE,
                    elem_id=f"celltip-{element}",
                )
            )

    parts.append(
        f'<rect x="{plot_x:.1f}" y="{plot_y:.1f}" width="{plot_w:.1f}" '
        f'height="{plot_h:.1f}" fill="none" stroke="{GRIDLINE}" stroke-width="1"/>'
    )
    for band, position in ((0, plot_y), (band_count, plot_y + plot_h)):
        record = 1 if band == 0 else n
        parts.append(
            f'<text x="{plot_x - 12:.1f}" y="{position + (12 if band == 0 else 0):.1f}" '
            f'font-size="11" fill="{SECONDARY}" text-anchor="end" '
            f'font-family="{mono_family}">{record}</text>'
        )
    parts.append(
        f'<text x="{plot_x - 12:.1f}" y="{plot_y + plot_h / 2:.1f}" font-size="12" '
        f'fill="{SECONDARY}" text-anchor="end">{xml_escape(order_label)}</text>'
    )

    key_x = plot_x
    key_y = plot_y + plot_h + 34.0
    parts.append(
        f'<text x="{key_x:.1f}" y="{key_y + 4:.1f}" font-size="11" fill="{SECONDARY}">'
        f"{xml_escape(complete_label)}</text>"
    )
    for step in range(10):
        fraction = step / 9.0
        parts.append(
            f'<rect x="{key_x + 60 + step * 16:.1f}" y="{key_y - 8:.1f}" width="16" '
            f'height="11" fill="{absent_ink if fraction else present_ink}" '
            f'opacity="{0.08 + 0.84 * fraction if fraction else 0.10:.2f}"/>'
        )
    parts.append(
        f'<text x="{key_x + 232:.1f}" y="{key_y + 4:.1f}" font-size="11" '
        f'fill="{SECONDARY}">{xml_escape(missing_label)}</text>'
    )
    parts.append(
        f'<text x="{key_x + 300:.1f}" y="{key_y + 4:.1f}" font-size="11" '
        f'fill="{SECONDARY}" font-family="{mono_family}">'
        f"one band = {fmt_number(band_size)} records</text>"
    )

    parts.extend(tips)
    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_missing_matrix(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[str] = None,
    title: str = "One field was added partway through; two others go missing together",
    subtitle: str = "Eighteen hundred patient records in arrival order, one column per field, shaded where values are absent.",
    width: int = 900,
    height: int = 620,
    columns: Optional[List[str]] = None,
    bands: int = 60,
    blanks_count: bool = True,
    order_label: str = "Records, in arrival order",
    complete_label: str = "complete",
    missing_label: str = "missing",
    pair_note: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Write a missingness matrix to disk and return the path.

    Parameters
    ----------
    data : list of dict or None
        The records, in the order they should be drawn. Defaults to
        :data:`DEMO_DATA`.
    out : str or None
        Destination path; ``None`` writes beside the script.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    columns : list of str or None
        Which fields to draw, left to right.
    bands : int
        How many horizontal bands the records are binned into.
    blanks_count : bool
        Whether an empty string counts as missing alongside ``None``.
    order_label : str
        Title on the vertical axis of records.
    complete_label, missing_label : str
        The two ends of the shading key.
    pair_note, finding : str or None
        The line naming the pair that most often goes missing together,
        and the sentence summarising the holes; ``None`` composes each
        from the data.
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
    >>> p = make_missing_matrix()
    >>> p.exists()
    True
    """
    svg = build_svg(
        data,
        title=title,
        subtitle=subtitle,
        width=width,
        height=height,
        columns=columns,
        bands=bands,
        blanks_count=blanks_count,
        order_label=order_label,
        complete_label=complete_label,
        missing_label=missing_label,
        pair_note=pair_note,
        finding=finding,
        mode=mode,
        accessibility=accessibility,
        theme=theme,
    )
    dest = Path(out) if out else svg_example_path(__file__, "missing-matrix")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(
        __file__,
        "missing-matrix",
        build_svg,
        description="Draw where a table's values are absent, and whether they fall together.",
    )


if __name__ == "__main__":
    main()
