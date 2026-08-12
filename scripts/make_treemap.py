#!/usr/bin/env python3
"""
make_treemap — a house-styled treemap as hand-authored SVG.

A treemap encodes a hierarchy as a set of nested rectangles. Area is
proportional to a numeric measure so the viewer can compare part-to-whole
relationships across many categories at once. Colour encodes a second
dimension (the parent category) so the eye groups siblings before comparing
across groups. Typical uses: software package sizes, portfolio composition,
file-system usage, and any taxonomy with a value attached to each leaf.

Previously rendered via full Vega (``vl_convert``, ``treemap`` transform
with the squarify method); this module now runs the squarify algorithm
itself (Bruls, Huizing & van Wijk, 2000) and paints the nested rectangles
by hand -- no Vega, no matplotlib. Every leaf carries a native ``<title>``
tooltip with its exact value.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _interactive import fullscreen_control  # noqa: E402
from _render import render_cli, svg_example_path, write_svg  # noqa: E402
from _style import BG, GRIDLINE, INK, SECONDARY, qualitative_sequence  # noqa: E402
from _svg import svg_open, tooltip_bubble, xml_escape  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme  # noqa: E402
from _textfit import fit_font_size, text_width, wrap_to_width  # noqa: E402


CATEGORY_COLORS: Dict[str, str] = {
    "Infrastructure": "#007AFF",
    "Applications": "#AF52DE",
    "Security": "#FF9500",
    "Data & AI": "#28CD41",
    "Networking": "#FF3B30",
    "Compliance": "#79DBDC",
}

# Chrome text (title/subtitle/accessible desc) in the two languages Studio
# can ask for (studio/i18n.py detects the language from the imported CSV's
# column names; the CLI/library/API/MCP always call with the "en" default).
# Data-derived text -- parent/name labels, numeric values -- is never
# translated here; it already carries whatever language the caller's data
# uses.
_STRINGS: Dict[str, Dict[str, str]] = {
    "en": {
        "title": "IT Cloud Spending by Service — FY 2024",
        "subtitle": "Annual spend in thousands of EUR; area proportional to budget",
        "desc_template": (
            "Treemap of {n_parents} domains and {n_children} services. "
            "Hover or focus a rectangle for its exact value."
        ),
    },
    "fr": {
        "title": "Dépenses cloud IT par service — exercice 2024",
        "subtitle": "Dépense annuelle en milliers d'euros ; l'aire est proportionnelle au budget",
        "desc_template": (
            "Treemap de {n_parents} domaines et {n_children} services. "
            "Survolez ou activez le focus sur un rectangle pour sa valeur exacte."
        ),
    },
}


def _strings(language: str) -> Dict[str, str]:
    """Chrome-text dict for `language`, falling back to English."""
    return _STRINGS.get(language, _STRINGS["en"])

# ---------------------------------------------------------------------------
# Demo data: annual cloud spending by service, IT department FY-2024 (k EUR).
# Two-level hierarchy: parent = domain, name = service, value = spend.
# ---------------------------------------------------------------------------
DEMO_DATA: List[Dict[str, Any]] = [
    {"parent": "Infrastructure", "name": "Compute (EC2/GCE)", "value": 312},
    {"parent": "Infrastructure", "name": "Storage (S3/GCS)", "value": 148},
    {"parent": "Infrastructure", "name": "Managed DB", "value": 97},
    {"parent": "Infrastructure", "name": "Container registry", "value": 34},
    {"parent": "Applications", "name": "CRM platform", "value": 210},
    {"parent": "Applications", "name": "ERP system", "value": 178},
    {"parent": "Applications", "name": "Dev toolchain", "value": 85},
    {"parent": "Applications", "name": "Collaboration", "value": 62},
    {"parent": "Security", "name": "SIEM / SOC", "value": 134},
    {"parent": "Security", "name": "WAF / DDoS", "value": 76},
    {"parent": "Security", "name": "Identity (IAM)", "value": 58},
    {"parent": "Data & AI", "name": "Data warehouse", "value": 189},
    {"parent": "Data & AI", "name": "ML training", "value": 143},
    {"parent": "Data & AI", "name": "BI tooling", "value": 67},
    {"parent": "Networking", "name": "CDN / egress", "value": 112},
    {"parent": "Networking", "name": "VPN / SD-WAN", "value": 54},
    {"parent": "Compliance", "name": "Audit tooling", "value": 43},
    {"parent": "Compliance", "name": "Data residency", "value": 29},
]


def _layout_row(sizes: List[float], x: float, y: float, dx: float, dy: float) -> List[Dict[str, float]]:
    covered = sum(sizes)
    width = covered / dy if dy else 0.0
    rects, cy = [], y
    for size in sizes:
        h = size / width if width else 0.0
        rects.append({"x": x, "y": cy, "dx": width, "dy": h})
        cy += h
    return rects


def _layout_col(sizes: List[float], x: float, y: float, dx: float, dy: float) -> List[Dict[str, float]]:
    covered = sum(sizes)
    height = covered / dx if dx else 0.0
    rects, cx = [], x
    for size in sizes:
        w = size / height if height else 0.0
        rects.append({"x": cx, "y": y, "dx": w, "dy": height})
        cx += w
    return rects


def _layout(sizes: List[float], x: float, y: float, dx: float, dy: float) -> List[Dict[str, float]]:
    return _layout_row(sizes, x, y, dx, dy) if dx >= dy else _layout_col(sizes, x, y, dx, dy)


def _leftover(sizes: List[float], x: float, y: float, dx: float, dy: float):
    covered = sum(sizes)
    if dx >= dy:
        width = covered / dy if dy else 0.0
        return (x + width, y, dx - width, dy)
    height = covered / dx if dx else 0.0
    return (x, y + height, dx, dy - height)


def _worst_ratio(sizes: List[float], x: float, y: float, dx: float, dy: float) -> float:
    rects = _layout(sizes, x, y, dx, dy)
    return max(max(r["dx"] / r["dy"], r["dy"] / r["dx"]) for r in rects if r["dx"] and r["dy"])


def _squarify(sizes: List[float], x: float, y: float, dx: float, dy: float) -> List[Dict[str, float]]:
    """Squarified treemap layout (Bruls, Huizing & van Wijk, 2000).

    Parameters
    ----------
    sizes : list of float
        Areas, pre-normalised so that ``sum(sizes) == dx * dy``, sorted
        descending for best aspect ratios.
    x, y, dx, dy : float
        The rectangle to subdivide.

    Returns
    -------
    list of dict
        One ``{x, y, dx, dy}`` rect per input size, same order as *sizes*.
    """
    if not sizes:
        return []
    if len(sizes) == 1:
        return _layout(sizes, x, y, dx, dy)
    i = 1
    while i < len(sizes) and _worst_ratio(sizes[:i], x, y, dx, dy) >= _worst_ratio(sizes[: i + 1], x, y, dx, dy):
        i += 1
    current, remaining = sizes[:i], sizes[i:]
    lx, ly, ldx, ldy = _leftover(current, x, y, dx, dy)
    return _layout(current, x, y, dx, dy) + _squarify(remaining, lx, ly, ldx, ldy)


def _normalize(values: List[float], area: float) -> List[float]:
    total = sum(values)
    if total <= 0:
        return [0.0 for _ in values]
    return [v * area / total for v in values]


def build_svg(
    data: Optional[List[Dict[str, Any]]] = None,
    title: str | None = None,
    subtitle: str | None = None,
    width: int = 900,
    height: int = 600,
    mode: str = "self-contained",
    accessibility: str = "universal",
    language: str = "en",
    value_unit: str | None = None,
    theme: str = "corporate",
) -> str:
    """Assemble the full treemap SVG document as a string.

    Parameters
    ----------
    data : list of dict or None
        Rows with keys ``parent`` (str), ``name`` (str), ``value``
        (numeric). Defaults to :data:`DEMO_DATA`.
    title, subtitle : str or None
        Chart text. ``None`` (the default) picks the illustrative title/
        subtitle for `language`; an explicit string is always honoured
        verbatim regardless of `language`.
    width, height : int
        Canvas size in pixels.
    mode : str, optional
        Forwarded to :func:`_interactive.fullscreen_control`.
    accessibility : str, optional
        Accepted for CLI parity but a documented no-op: category colours
        are fixed house hues, not a CVD-safe palette re-level.
    language : str, optional
        Chrome-text language, ``"en"`` or ``"fr"`` (see :data:`_STRINGS`).
        Only the title/subtitle default and accessible desc switch;
        ``parent``/``name`` labels and values always render as given in
        `data`. Defaults to ``"en"``.
    value_unit : str or None, optional
        Word appended after each leaf's value, in the tooltip and the
        on-canvas number (e.g. ``"EUR"``, ``"détections"``). ``None`` (the
        default) falls back to ``"k EUR"`` when `data` is left at
        :data:`DEMO_DATA` (the illustrative IT-spend story, whose values are
        already expressed in thousands of euros) and to no unit at all
        otherwise — a caller passing raw counts (e.g. "4" occurrences) must
        not have a fabricated "k" (thousands) suffix silently attached, which
        previously turned a plain count of 4 into a misleading "4k".
    theme : str, optional
        Visual theme: ``"corporate"`` (default, Roboto -- byte-identical to
        the pre-theme render) or ``"academic"`` (LaTeX-style Latin Modern).
        See :func:`sprezzature_figures.fonts.chrome_stack_for_theme`.

    Returns
    -------
    str
        A complete, standalone SVG document.
    """
    _ = accessibility
    strings = _strings(language)
    title = strings["title"] if title is None else title
    subtitle = strings["subtitle"] if subtitle is None else subtitle
    is_demo_data = not data
    if value_unit is None:
        value_unit = "k EUR" if is_demo_data else ""
    rows = data if data else DEMO_DATA
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["parent"]].append(row)
    for p in grouped:
        grouped[p].sort(key=lambda r: -float(r["value"]))
    categories = sorted(grouped, key=lambda p: -sum(float(r["value"]) for r in grouped[p]))
    # CATEGORY_COLORS only names the shipped demo's 6 domains; a category
    # outside that set used to fall back to flat grey for every rectangle.
    # Keep the fixed house hues where they match (stable colours for the
    # demo data) and assign the qualitative sequence to anything else.
    palette_cycle = iter(qualitative_sequence(max(len(categories), 1), theme=theme))
    category_colors = {
        cat: CATEGORY_COLORS.get(cat) or next(palette_cycle) for cat in categories
    }

    legend_y = 94.0
    plot_x, plot_y = 20.0, 128.0
    right_margin, bottom_margin = 20.0, 20.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_margin
    area = plot_w * plot_h

    cat_totals = [sum(float(r["value"]) for r in grouped[p]) for p in categories]
    cat_sizes = _normalize(cat_totals, area)
    cat_rects = _squarify(cat_sizes, plot_x, plot_y, plot_w, plot_h)

    parts: List[str] = []
    parts.append(svg_open(width, height, "tm-title", "tm-desc", font_family=chrome_stack_for_theme(theme)))
    parts.append(f'<title id="tm-title">{xml_escape(title)}</title>')
    desc = strings["desc_template"].format(n_parents=len(categories), n_children=len(rows))
    parts.append(f'<desc id="tm-desc">{xml_escape(desc)}</desc>')

    parts.append(
        "<style>"
        ".leaf{transition:opacity .15s ease;cursor:default;}"
        ".leaf:hover,.leaf:focus{opacity:.72;outline:none;}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        ".hit:hover+.tip,.hit:focus+.tip{opacity:1}"
        "@media (prefers-reduced-motion: reduce){.leaf{transition:none;}"
        ".tip{transition:none}}"
        "</style>"
    )

    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<text x="20" y="46" font-size="24" font-weight="700" fill="{INK}" '
        f'letter-spacing="-0.3">{xml_escape(title)}</text>'
    )
    parts.append(f'<text x="20" y="70" font-size="14" fill="{SECONDARY}">{xml_escape(subtitle)}</text>')

    # ---- legend ----
    cursor = 20.0
    for cat in categories:
        color = category_colors[cat]
        parts.append(f'<rect x="{cursor:.1f}" y="{legend_y - 11:.1f}" width="12" height="12" rx="2" fill="{color}"/>')
        parts.append(f'<text x="{cursor + 18:.1f}" y="{legend_y:.1f}" font-size="12" fill="{INK}">{xml_escape(cat)}</text>')
        cursor += 24 + 7.0 * len(cat) + 22

    # ---- rectangles ----
    for cat, crect in zip(categories, cat_rects):
        color = category_colors[cat]
        leaves = grouped[cat]
        leaf_vals = [float(r["value"]) for r in leaves]
        leaf_area = crect["dx"] * crect["dy"]
        leaf_sizes = _normalize(leaf_vals, leaf_area)
        leaf_rects = _squarify(leaf_sizes, crect["x"], crect["y"], crect["dx"], crect["dy"])
        cat_total = sum(leaf_vals) or 1.0
        for row, r in zip(leaves, leaf_rects):
            val_txt = f"{float(row['value']):,.0f}"
            unit_suffix = f" {value_unit}" if value_unit else ""
            share = float(row["value"]) / cat_total * 100.0
            tip = f"{cat} / {row['name']}: {val_txt}{unit_suffix}"
            parts.append(
                f'<rect class="leaf hit" tabindex="0" x="{r["x"]:.1f}" y="{r["y"]:.1f}" '
                f'width="{max(0.0, r["dx"]):.1f}" height="{max(0.0, r["dy"]):.1f}" '
                f'fill="{color}" fill-opacity="0.82" stroke="{BG}" stroke-width="2" '
                f'role="img" aria-label="{xml_escape(tip)}"/>'
            )
            parts.append(
                tooltip_bubble(
                    r["x"] + max(0.0, r["dx"]) / 2.0, r["y"] - 4,
                    [row["name"], f"{val_txt}{unit_suffix}", f"{share:.1f}% of {cat}"],
                    anchor="middle", canvas_w=width, canvas_h=height,
                    ink=INK, secondary=SECONDARY, border=GRIDLINE,
                )
            )
            # Fit the label to the leaf's actual pixel box instead of assuming a
            # fixed threshold fits any string: a long name (French routinely runs
            # 20-40% longer than English) previously overran its rectangle and
            # bled into the neighbouring leaf's label. Shrink the font, wrap to
            # the box width, then drop lines that still don't fit the box height
            # — and skip the label entirely once the box is too small for even
            # one line, rather than emit unreadable overlapping text.
            pad = 6.0
            avail_w = r["dx"] - 2 * pad
            avail_h = r["dy"] - 2 * pad
            name_size = fit_font_size(row["name"], avail_w, 11.0, min_px=8.0)
            lines = wrap_to_width(row["name"], avail_w, name_size) if avail_w >= 20 else []
            line_h = name_size * 1.2
            value_h = 10.0 * 1.2
            max_lines = max(1, int((avail_h - value_h) // line_h)) if avail_h > value_h else 0
            show_value = max_lines >= 1 and avail_h >= value_h
            if not show_value:
                max_lines = max(0, int(avail_h // line_h))
            if len(lines) > max_lines:
                lines = lines[:max_lines]
                if lines:
                    last = lines[-1]
                    while last and text_width(f"{last}…", name_size) > avail_w:
                        last = last[:-1]
                    lines[-1] = f"{last}…" if last else "…"
            if lines:
                cxm = r["x"] + r["dx"] / 2
                n = len(lines)
                block_h = n * line_h + (value_h if show_value else 0.0)
                top = r["y"] + r["dy"] / 2 - block_h / 2 + name_size * 0.85
                for i, ln in enumerate(lines):
                    parts.append(
                        f'<text x="{cxm:.1f}" y="{top + i * line_h:.1f}" '
                        f'font-size="{name_size:.1f}" fill="{BG}" '
                        f'text-anchor="middle">{xml_escape(ln)}</text>'
                    )
                if show_value:
                    parts.append(
                        f'<text x="{cxm:.1f}" y="{top + n * line_h + 9:.1f}" font-size="10" '
                        f'fill="{BG}" fill-opacity="0.85" text-anchor="middle">'
                        f'{xml_escape(val_txt)}{xml_escape(unit_suffix)}</text>'
                    )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "\n".join(parts)


def make_treemap(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str | None = None,
    subtitle: str | None = None,
    width: int = 900,
    height: int = 600,
    mode: str = "self-contained",
    accessibility: str = "universal",
    language: str = "en",
    value_unit: str | None = None,
    theme: str = "corporate",
) -> Path:
    """Render a hand-authored treemap and write the SVG to *out*.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows with keys ``parent`` (str), ``name`` (str), ``value`` (float).
        Defaults to DEMO_DATA (IT cloud spending by domain and service).
    out : Path, str, or None
        Output path (.svg). Defaults to ``assets/svg-examples/treemap.svg``.
    title, subtitle : str or None
        Chart text. ``None`` picks the `language`-appropriate default.
    width, height : int
        Canvas size in pixels.
    mode, accessibility : str
        Forwarded to :func:`build_svg`.
    language : str, optional
        Chrome-text language, ``"en"`` or ``"fr"``. Defaults to ``"en"``;
        Sprezzature Studio passes the language detected from the imported
        CSV's column names (see :data:`_STRINGS`).
    theme : str, optional
        Visual theme. Forwarded to :func:`build_svg`.

    Returns
    -------
    Path
        Absolute path to the written SVG file.

    Examples
    --------
    >>> p = make_treemap()
    >>> p.exists()
    True
    """
    svg = build_svg(data, title=title, subtitle=subtitle, width=width, height=height,
                     mode=mode, accessibility=accessibility, language=language,
                     value_unit=value_unit, theme=theme)
    dest = Path(out) if out else svg_example_path(__file__, "treemap")
    return write_svg(dest, svg, theme=theme)


def main() -> None:
    """CLI entry point: build the SVG and write it to disk."""
    render_cli(__file__, "treemap", build_svg, description="Generate a treemap figure.")


if __name__ == "__main__":
    main()
