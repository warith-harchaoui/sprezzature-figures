"""Dark mode for house SVG figures.

House figures render for a LIGHT canvas: an opaque white background rectangle
and dark chrome (title, axes, labels, gridlines). ``dark`` mode rewrites a
rendered SVG so it reads on a DARK canvas instead:

  1. the full-canvas white background rectangle is dropped, so the SVG is
     TRANSPARENT and sits on whatever dark surface hosts it;
  2. the chrome colours (ink, secondary text, gridlines) are lightened so they
     stay legible on a dark background.

Only the known chrome colours from :mod:`scripts._style` are remapped, never the
data-series palette (already vivid and legible on dark) and never white in
general (white text sitting on a coloured bar must stay white): only the
full-canvas background rectangle is neutralised. This keeps the transform safe
across all figure kinds.

Exposed to callers through ``make_figure(kind, data, dark=True)``.
"""

from __future__ import annotations

import re

# Chrome colours emitted by scripts/_style.py, and their dark-canvas equivalents.
_BG = "#FFFFFF"          # full-canvas background rect (opaque) -> dropped
_INK = "#1D1D1F"         # titles, labels -> near white
_SECONDARY = "#6E6E73"   # secondary text -> light gray
_GRIDLINE = "#E5E5EA"    # gridlines -> subtle dark-on-dark line

_INK_DARK = "#F5F5F7"
_SECONDARY_DARK = "#98989D"
_GRIDLINE_DARK = "#3A3A3C"

_REMAP = {
    _INK: _INK_DARK,
    _SECONDARY: _SECONDARY_DARK,
    _GRIDLINE: _GRIDLINE_DARK,
}

_SVG_DIMS = re.compile(
    r'<svg\b[^>]*?\bwidth="(\d+(?:\.\d+)?)"[^>]*?\bheight="(\d+(?:\.\d+)?)"', re.I
)


def _drop_background(svg: str) -> str:
    """Remove the full-canvas white background rectangle (the one whose width and
    height equal the SVG canvas). Other white rectangles (tooltip bubbles, legend
    swatches) carry their own x/y and dimensions and are left untouched."""
    m = _SVG_DIMS.search(svg)
    if m:
        w, h = m.group(1), m.group(2)
    else:
        vb = re.search(r'viewBox="0 0 (\d+(?:\.\d+)?) (\d+(?:\.\d+)?)"', svg)
        if not vb:
            return svg
        w, h = vb.group(1), vb.group(2)
    for pat in (
        rf'<rect\b[^>]*?\bwidth="{re.escape(w)}"[^>]*?\bheight="{re.escape(h)}"[^>]*?\bfill="{_BG}"[^>]*?/>',
        rf'<rect\b[^>]*?\bfill="{_BG}"[^>]*?\bwidth="{re.escape(w)}"[^>]*?\bheight="{re.escape(h)}"[^>]*?/>',
    ):
        new, n = re.subn(pat, "", svg, count=1, flags=re.I)
        if n:
            return new
    return svg


def to_dark(svg: str) -> str:
    """Rewrite a rendered house SVG for a dark canvas: transparent background,
    lightened chrome. Data colours and useful white are preserved. Idempotent in
    practice (the original chrome colours are gone after one pass)."""
    if not svg:
        return svg
    out = _drop_background(svg)
    for src, dst in _REMAP.items():
        for s in (src, src.lower()):
            out = out.replace(f'"{s}"', f'"{dst}"')   # inline attributes
            out = out.replace(f":{s}", f":{dst}")     # CSS declarations (prop:value)
    return out


__all__ = ["to_dark"]
