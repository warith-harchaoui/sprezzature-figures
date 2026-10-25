#!/usr/bin/env python3
"""
make_table — a table drawn so the numbers can be compared down a column.

Rows and columns, with the numeric ones right-aligned at a consistent
precision and one of them carrying an in-cell bar. A table is a chart:
the reader is being asked to compare quantities, and almost everything
that makes a table hard to read is a decision about how the digits sit.

Where the usual rendered table goes wrong
-------------------------------------------
* **Numbers are centred or left-aligned.** Then the units digit of one
  row sits above the hundreds digit of the next and the column cannot
  be scanned at all. Numeric columns are right-aligned here and drawn
  in a tabular face, which is the single change that makes a table
  readable.
* **Each cell is rounded to whatever it happened to be.** One row says
  1.2, the next 1.23456, and the column stops being a column. Precision
  is settled per column, from the spread of its own values.
* **The reader is left to do the comparison.** A column of numbers is a
  bar chart with the bars removed. One column keeps them, in the cell,
  which costs nothing and answers "which is biggest" before the eye has
  finished reading.
* **Zebra stripes stand in for alignment.** Striping a badly aligned
  table makes it striped and badly aligned. The fix is the alignment;
  the rules here are hairlines and the emphasis goes on the sorted
  column instead.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _style import BG, GRIDLINE, INK, SECONDARY, load_palette  # noqa: E402
from _svg import (  # noqa: E402
    foreground_tip_css,
    svg_open,
    tooltip_bubble,
    wrap_no_orphan,
    xml_escape,
)
from _textfit import fit_font_size, text_width  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402

DEMO_DATA: List[Dict[str, Any]] = [
    {"region": "Île-de-France", "teams": 1_284, "revenue": 4_118_900.0, "churn": 0.0142, "nps": 41},
    {
        "region": "Auvergne-Rhône-Alpes",
        "teams": 612,
        "revenue": 1_903_400.0,
        "churn": 0.0188,
        "nps": 37,
    },
    {
        "region": "Nouvelle-Aquitaine",
        "teams": 398,
        "revenue": 1_142_700.0,
        "churn": 0.0231,
        "nps": 29,
    },
    {"region": "Occitanie", "teams": 377, "revenue": 1_097_050.0, "churn": 0.0205, "nps": 33},
    {"region": "Hauts-de-France", "teams": 281, "revenue": 742_380.0, "churn": 0.0297, "nps": 22},
    {"region": "Grand Est", "teams": 254, "revenue": 740_500.0, "churn": 0.0151, "nps": 38},
    {"region": "Bretagne", "teams": 196, "revenue": 553_900.0, "churn": 0.0176, "nps": 44},
    {"region": "Normandie", "teams": 148, "revenue": 402_600.0, "churn": 0.0312, "nps": 19},
]


#: Which of the demo's columns actually add up. A caller's own data
#: carries its own answer, so this applies only when no data is given.
_DEMO_SUMS = ("teams", "revenue")


def _is_number(value: Any) -> bool:
    """Whether `value` can be read as a number."""
    if isinstance(value, bool):
        return False
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str = "Two regions with almost the same revenue lose customers at very different rates",
    subtitle: str = "Numeric columns right-aligned at one precision each, with the sorted column carrying its bars in the cell.",
    width: int = 960,
    height: int = 520,
    columns: Optional[List[str]] = None,
    sort_by: str = "revenue",
    descending: bool = True,
    bar_column: str = "revenue",
    total_row: bool = True,
    sum_columns: Optional[List[str]] = None,
    total_label: str = "All regions",
    sort_note: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full table SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        One row per record. Defaults to :data:`DEMO_DATA`.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    columns : list of str or None
        Which columns to draw, left to right. ``None`` takes the keys of
        the first row.
    sort_by : str
        Column to sort on. Named on the canvas, because a table that
        does not say what it is sorted by invites the reader to assume
        it is sorted by the first column.
    descending : bool
        Sort direction.
    bar_column : str
        Which numeric column carries an in-cell bar. Empty string draws
        none.
    total_row : bool
        Add a summed row at the foot.
    sum_columns : list of str or None
        Which columns to total. ``None`` guesses: anything whose values
        all sit within 0 to 1 is taken for a rate and left blank. The
        guess cannot tell a count from a score -- adding eight NPS
        figures produces a number with no referent -- so a caller who
        knows should say.
    total_label : str
        Name for the summed row.
    sort_note, finding : str or None
        The line naming the sort and the precisions, and the sentence
        naming what the table shows; ``None`` composes each from the data.
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
    if data is None and sum_columns is None:
        sum_columns = list(_DEMO_SUMS)
    rows = list(data if data else DEMO_DATA)
    if not rows:
        raise ValueError("a table needs at least one row")
    names = list(columns) if columns else list(rows[0].keys())
    missing = [name for name in names if not any(name in row for row in rows)]
    if missing:
        raise ValueError(f"no row carries the column(s) {missing}")
    if sort_by and sort_by not in names:
        raise ValueError(f"sort_by names {sort_by!r}, which is not a drawn column")
    if bar_column and bar_column not in names:
        raise ValueError(f"bar_column names {bar_column!r}, which is not a drawn column")

    numeric = {
        name: all(_is_number(row.get(name)) for row in rows if name in row) for name in names
    }
    if bar_column and not numeric.get(bar_column):
        raise ValueError(f"bar_column {bar_column!r} is not numeric, so it has no bar")

    if sort_by:
        rows.sort(
            key=lambda row: float(row[sort_by]) if numeric[sort_by] else str(row.get(sort_by, "")),
            reverse=descending,
        )

    # Precision per column, from the spread of that column's own values:
    # a churn column of 0.0142 to 0.0312 needs four decimals, a revenue
    # column of millions needs none.
    decimals: Dict[str, int] = {}
    for name in names:
        if not numeric[name]:
            continue
        values = [float(row[name]) for row in rows if name in row]
        if all(value == int(value) for value in values):
            decimals[name] = 0
            continue
        spread = (max(values) - min(values)) or (abs(values[0]) or 1.0)
        # Enough decimals to tell two values a hundredth of the spread
        # apart; one more than that printed a churn of 0.0142 as
        # "0.01420", which is a digit the data does not have.
        decimals[name] = max(0, min(6, -int(math.floor(math.log10(spread / 100.0)))))

    def cell(name: str, value: float) -> str:
        """`value` at the number of decimals this column settled on."""
        return f"{value:.{decimals.get(name, 0)}f}"

    # A sum is only a sum for things that add up. Rates do not, and
    # neither do scores: adding eight NPS figures produces a number with
    # no referent. The figure cannot tell a count from a score by
    # looking, so it guesses conservatively -- anything whose values all
    # sit within 0 to 1 is a rate -- and `sum_columns` lets the caller,
    # who does know, say so outright.
    def summable(name: str) -> bool:
        """Whether adding this column's values produces a meaningful number."""
        if not numeric[name]:
            return False
        if sum_columns is not None:
            return name in sum_columns
        values = [abs(float(row[name])) for row in rows if name in row]
        return not all(value <= 1.0 for value in values)

    unknown_sums = sorted(set(sum_columns or ()) - set(names))
    if unknown_sums:
        raise ValueError(f"sum_columns names columns that are not drawn: {unknown_sums}")
    totals = {
        name: sum(float(row[name]) for row in rows if name in row)
        for name in names
        if summable(name)
    }

    mono_family = mono_stack_for_theme(theme)
    palette = load_palette(accessibility, theme=theme)
    bar_ink = palette.get("Blue", "#007AFF")

    plot_x = 40.0
    plot_y = 196.0
    plot_w = width - 80.0
    header_h = 30.0
    body_h = height - plot_y - header_h - 60.0
    line_h = body_h / (len(rows) + (1 if total_row else 0))

    # Columns are as wide as their widest cell needs, text columns first.
    def widest(name: str) -> float:
        cells = [
            cell(name, float(row[name])) if numeric[name] else str(row.get(name, ""))
            for row in rows
            if name in row
        ]
        return max(
            [text_width(name, 12.0, bold=True)]
            + [text_width(cell, 12.0, mono=numeric[name]) for cell in cells]
        )

    wanted = {name: widest(name) + (62.0 if name == bar_column else 26.0) for name in names}
    scale = plot_w / sum(wanted.values())
    lefts: Dict[str, float] = {}
    rights: Dict[str, float] = {}
    cursor = plot_x
    for name in names:
        lefts[name] = cursor
        cursor += wanted[name] * scale
        rights[name] = cursor

    sort_lines = (
        [sort_note]
        if sort_note is not None
        else [
            f"sorted by {sort_by}, {'highest' if descending else 'lowest'} first"
            if sort_by
            else "in the order the rows arrived",
            "each numeric column at one precision, read off its own spread"
            + (f" · {bar_column} carries its bar in the cell" if bar_column else ""),
        ]
    )
    said_sort = " · ".join(sort_lines)
    said_parts: List[str] = []
    if finding is not None:
        said_parts.append(finding)
    elif totals:
        named = ", ".join(
            f"{name} {cell(name, amount)}" for name, amount in list(totals.items())[:3]
        )
        said_parts.append(f"{len(rows)} rows. Totals where a total means something: {named}.")
        skipped = [name for name in names if numeric[name] and name not in totals]
        if skipped:
            said_parts.append(
                f"{', '.join(skipped)} "
                f"{'does' if len(skipped) == 1 else 'do'} not add up, so no total is "
                f"shown."
            )
    else:
        said_parts.append(f"{len(rows)} rows.")
    said_lines: List[str] = []
    for sentence in said_parts:
        said_lines.extend(wrap_no_orphan(sentence, 104))

    parts: List[str] = []
    parts.append(
        svg_open(
            width, height, "table-title", "table-desc", font_family=chrome_stack_for_theme(theme)
        )
    )
    parts.append(f'<title id="table-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="table-desc">A table of {len(rows)} rows and {len(names)} columns: '
        f"{xml_escape(', '.join(names))}. {xml_escape(said_sort)}. "
        f"{xml_escape(' '.join(said_parts))}</desc>"
    )
    parts.append(
        "<style>"
        ".line{cursor:default;}"
        ".line:hover,.line:focus{outline:none;}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        + foreground_tip_css(len(rows), mark_prefix="line", tip_prefix="linetip")
        + "@media (prefers-reduced-motion:reduce){.tip{transition:none}}"
        "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    title_size = fit_font_size(title, width - 80.0, 22.0, min_px=15.0)
    parts.append(
        f'<text x="40" y="46" font-size="{title_size:.1f}" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    for line_index, text in enumerate(wrap_no_orphan(subtitle, 110)[:2]):
        parts.append(
            f'<text x="40" y="{72 + line_index * 20:.1f}" font-size="14" '
            f'fill="{SECONDARY}">{xml_escape(text)}</text>'
        )
    sort_drawn: List[str] = []
    for clause in sort_lines:
        sort_drawn.extend(wrap_no_orphan(clause, 104))
    for line_index, text in enumerate(sort_drawn[:2]):
        parts.append(
            f'<text x="40" y="{120 + line_index * 17:.1f}" font-size="12" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(text)}</text>'
        )
    for line_index, text in enumerate(said_lines[:2]):
        parts.append(
            f'<text x="40" y="{158 + line_index * 17:.1f}" font-size="12" '
            f'fill="{SECONDARY}" font-family="{mono_family}">{xml_escape(text)}</text>'
        )

    for name in names:
        anchor = "end" if numeric[name] else "start"
        at = rights[name] - 13.0 if numeric[name] else lefts[name] + 13.0
        parts.append(
            f'<text x="{at:.1f}" y="{plot_y + 16:.1f}" font-size="12" font-weight="700" '
            f'fill="{INK}" text-anchor="{anchor}">{xml_escape(name)}'
            + (" ↓" if name == sort_by and descending else (" ↑" if name == sort_by else ""))
            + "</text>"
        )
    parts.append(
        f'<line x1="{plot_x:.1f}" y1="{plot_y + header_h - 6:.1f}" '
        f'x2="{plot_x + plot_w:.1f}" y2="{plot_y + header_h - 6:.1f}" stroke="{INK}" '
        f'stroke-width="1.2"/>'
    )

    bar_reach = (
        max(abs(float(row[bar_column])) for row in rows if bar_column in row) if bar_column else 1.0
    ) or 1.0
    tips: List[str] = []
    for index, row in enumerate(rows):
        top = plot_y + header_h + index * line_h
        middle = top + line_h * 0.62
        if index:
            parts.append(
                f'<line x1="{plot_x:.1f}" y1="{top:.1f}" x2="{plot_x + plot_w:.1f}" '
                f'y2="{top:.1f}" stroke="{GRIDLINE}" stroke-width="0.6"/>'
            )
        for name in names:
            raw = row.get(name, "")
            if numeric[name]:
                shown = cell(name, float(raw))
                if name == bar_column:
                    # Anchored to the right edge and grown leftwards, so it
                    # sits behind its own number. Grown rightwards from the
                    # column's left edge it butted against the previous
                    # column and read as belonging to that one.
                    span = (rights[name] - lefts[name]) - 26.0
                    length = max(abs(float(raw)) / bar_reach * span, 2.0)
                    parts.append(
                        f'<rect x="{rights[name] - 13 - length:.1f}" '
                        f'y="{middle - 11:.1f}" width="{length:.1f}" height="14" '
                        f'fill="{bar_ink}" opacity="0.18" rx="2"/>'
                    )
                parts.append(
                    f'<text x="{rights[name] - 13:.1f}" y="{middle:.1f}" font-size="12" '
                    f'fill="{INK}" text-anchor="end" font-family="{mono_family}">'
                    f"{shown}</text>"
                )
            else:
                parts.append(
                    f'<text x="{lefts[name] + 13:.1f}" y="{middle:.1f}" font-size="12" '
                    f'fill="{INK}">{xml_escape(str(raw))}</text>'
                )
        said_row = " · ".join(
            f"{name} " + (cell(name, float(row[name])) if numeric[name] else str(row.get(name, "")))
            for name in names
            if name in row
        )
        parts.append(
            f'<rect id="line-{index}" class="line hit" tabindex="0" role="img" '
            f'aria-label="{xml_escape(said_row)}" x="{plot_x:.1f}" y="{top:.1f}" '
            f'width="{plot_w:.1f}" height="{line_h:.1f}" fill="transparent">'
            f"<title>{xml_escape(str(row.get(names[0], '')))}</title></rect>"
        )
        # Built from whole fields rather than by wrapping the joined row.
        # A wrapped line breaks mid-field, which reads badly and hands a
        # translator half a column name.
        fields = [
            f"{name} " + (cell(name, float(row[name])) if numeric[name] else str(row.get(name, "")))
            for name in names[1:]
            if name in row
        ]
        bubble = [str(row.get(names[0], ""))] + [
            " · ".join(fields[at : at + 2]) for at in range(0, len(fields), 2)
        ]
        tips.append(
            tooltip_bubble(
                plot_x + plot_w * 0.5,
                middle,
                bubble[:3],
                canvas_w=width,
                canvas_h=height,
                ink=INK,
                secondary=SECONDARY,
                border=GRIDLINE,
                elem_id=f"linetip-{index}",
            )
        )

    if total_row:
        top = plot_y + header_h + len(rows) * line_h
        middle = top + line_h * 0.62
        parts.append(
            f'<line x1="{plot_x:.1f}" y1="{top:.1f}" x2="{plot_x + plot_w:.1f}" '
            f'y2="{top:.1f}" stroke="{INK}" stroke-width="1.2"/>'
        )
        for name in names:
            if name == names[0]:
                parts.append(
                    f'<text x="{lefts[name] + 13:.1f}" y="{middle:.1f}" font-size="12" '
                    f'font-weight="700" fill="{INK}">{xml_escape(total_label)}</text>'
                )
            elif name in totals:
                parts.append(
                    f'<text x="{rights[name] - 13:.1f}" y="{middle:.1f}" font-size="12" '
                    f'font-weight="700" fill="{INK}" text-anchor="end" '
                    f'font-family="{mono_family}">'
                    f"{cell(name, totals[name])}</text>"
                )
            elif numeric[name]:
                parts.append(
                    f'<text x="{rights[name] - 13:.1f}" y="{middle:.1f}" font-size="11" '
                    f'fill="{SECONDARY}" text-anchor="end" font-family="{mono_family}">'
                    f"—</text>"
                )

    parts.extend(tips)
    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_table(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[str] = None,
    title: str = "Two regions with almost the same revenue lose customers at very different rates",
    subtitle: str = "Numeric columns right-aligned at one precision each, with the sorted column carrying its bars in the cell.",
    width: int = 960,
    height: int = 520,
    columns: Optional[List[str]] = None,
    sort_by: str = "revenue",
    descending: bool = True,
    bar_column: str = "revenue",
    total_row: bool = True,
    sum_columns: Optional[List[str]] = None,
    total_label: str = "All regions",
    sort_note: Optional[str] = None,
    finding: Optional[str] = None,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Write a table to disk and return the path.

    Parameters
    ----------
    data : list of dict or None
        One row per record. Defaults to :data:`DEMO_DATA`.
    out : str or None
        Destination path; ``None`` writes beside the script.
    title, subtitle : str
        Chart text.
    width, height : int
        Canvas size in pixels.
    columns : list of str or None
        Which columns to draw, left to right.
    sort_by : str
        Column to sort on.
    descending : bool
        Sort direction.
    bar_column : str
        Which numeric column carries an in-cell bar.
    total_row : bool
        Add a summed row at the foot.
    sum_columns : list of str or None
        Which columns to total; ``None`` guesses from the values.
    total_label : str
        Name for the summed row.
    sort_note, finding : str or None
        The line naming the sort and the precisions, and the sentence
        naming what the table shows; ``None`` composes each from the data.
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
    >>> p = make_table()
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
        sort_by=sort_by,
        descending=descending,
        bar_column=bar_column,
        total_row=total_row,
        sum_columns=sum_columns,
        total_label=total_label,
        sort_note=sort_note,
        finding=finding,
        mode=mode,
        accessibility=accessibility,
        theme=theme,
    )
    dest = Path(out) if out else svg_example_path(__file__, "table")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(
        __file__,
        "table",
        build_svg,
        description="Draw a table whose columns can actually be compared.",
    )


if __name__ == "__main__":
    main()
