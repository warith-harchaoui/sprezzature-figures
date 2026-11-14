"""
_style — house-style tokens shared by every make/audit script.

Exposes the single source of truth for palette and typography tokens.
When ``sprezzature-colors`` is co-installed next to ``sprezzature-figures``,
the palette is read from ``sprezzature-colors/references/palette.csv``
to keep make ↔ audit brand tokens from drifting; otherwise the module's
built-in curated fallback (the same 8 saturated Apple-system hues) is
used.

The module is **stdlib-only**, with no numpy or pandas at import time,
so ``audit_figure.py`` can pull tokens without installing the dataviz
tier.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import csv
import importlib.util
import os
import re
import sys
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ------------------------------------------------------------------
# House chrome — the ink/paper/gridline/mono-font quartet every generator's
# title, axis and tick text is drawn in. ~65 generators each re-declared
# these five names as bare module-level constants (confirmed byte-identical
# by grep before centralizing here); import them instead of re-typing the
# hex codes so a house-style change is one edit, not sixty-five.
# ------------------------------------------------------------------
INK = "#1D1D1F"
SECONDARY = "#6E6E73"
BG = "#FFFFFF"
GRIDLINE = "#E5E5EA"
FONT_MONO = "Roboto Mono, ui-monospace, monospace"


# ------------------------------------------------------------------
# The three palettes of https://deraison.ai/colors, the source of truth for
# every colour in the suite: the same eleven names in each (eight hues, then
# Brown, Black, Gray). ``corporate`` is Apple's system colours (light mode,
# values of June 9, 2025); ``academic`` is Okabe and Ito (2002), readable
# with colour blindness by construction, completed from the Colour Universal
# Design (CUD) recommended set ver.4 (2018); ``print`` is checked for offset
# printing on coated paper. sprezzature-colors ships the site's CSV files
# (``references/palette-<theme>.csv``) and :func:`load_palette` reads them
# when it is co-installed; these copies are used only when it is not.
# ------------------------------------------------------------------
THEMES: Tuple[str, ...] = ("corporate", "academic", "print")

_PALETTES: Dict[str, Dict[str, str]] = {
    "corporate": {
        "Red": "#FF383C",
        "Orange": "#FF8D28",
        "Yellow": "#FFCC00",
        "Green": "#34C759",
        "Turquoise": "#00C3D0",
        "Blue": "#0088FF",
        "Purple": "#CB30E0",
        "Pink": "#FF2D55",
        "Brown": "#AC7F5E",
        "Black": "#000000",
        "Gray": "#8E8E93",
    },
    "academic": {
        "Red": "#E73121",
        "Orange": "#E69F00",
        "Yellow": "#F0E442",
        "Green": "#009E73",
        "Turquoise": "#56B4E9",
        "Blue": "#0072B2",
        "Purple": "#CC79A7",
        "Pink": "#FF8082",
        "Brown": "#804000",
        "Black": "#000000",
        "Gray": "#84919E",
    },
    "print": {
        "Red": "#EE454C",
        "Orange": "#F88D38",
        "Yellow": "#F7DE68",
        "Green": "#14B880",
        "Turquoise": "#4FBFB9",
        "Blue": "#437DB5",
        "Purple": "#BC67AB",
        "Pink": "#FF849B",
        "Brown": "#A8704D",
        "Black": "#261F1F",
        "Gray": "#818690",
    },
}

#: Names older generators still ask for. Teal and Mint were two of Apple's
#: earlier system colours; the site has one turquoise (Apple's teal), so Teal
#: is Turquoise and Mint is Green, the rule the academic palette already
#: followed. White is the paper, not a palette colour: the site dropped it on
#: 2026-11-13, but a generator asking for it still gets white.
_HUE_ALIASES: Dict[str, str] = {"Teal": "Turquoise", "Mint": "Green"}


def _with_aliases(palette: Dict[str, str]) -> Dict[str, str]:
    """Add the :data:`_HUE_ALIASES` keys and White to a palette, after its own names."""
    out = dict(palette)
    for alias, name in _HUE_ALIASES.items():
        if name in out:
            out.setdefault(alias, out[name])
    out.setdefault("White", "#FFFFFF")
    return out


#: The corporate palette with its aliases, the fallback every lookup ends on.
_FALLBACK_PALETTE: Dict[str, str] = _with_aliases(_PALETTES["corporate"])
_ACADEMIC_PALETTE: Dict[str, str] = _with_aliases(_PALETTES["academic"])
_PRINT_PALETTE: Dict[str, str] = _with_aliases(_PALETTES["print"])


def _fallback_for(theme: str) -> Dict[str, str]:
    """The built-in copy of ``theme``'s palette, aliases included."""
    return {"academic": _ACADEMIC_PALETTE, "print": _PRINT_PALETTE}.get(theme, _FALLBACK_PALETTE)


#: Emotion → hex fallback, the ``Emotion`` column of the corporate palette
#: of <https://deraison.ai/colors/>.
_FALLBACK_EMOTIONS: Dict[str, str] = {
    "Anger": "#FF383C",
    "Surprise": "#FF8D28",
    "Joy": "#FFCC00",
    "Disgust": "#34C759",
    "Happiness": "#00C3D0",
    "Sadness": "#0088FF",
    "Fear": "#CB30E0",
    "Love": "#FF2D55",
    "Comfort": "#AC7F5E",
    "Silence": "#000000",
    "Neutral": "#8E8E93",
}


def _installed_colors_package(package: str) -> Optional[Path]:
    """Directory of one of the packages the ``sprezzature-colors`` wheel installs.

    The searches below only knew a checkout beside this one and a skill folder.
    The wheel puts ``scripts/`` and ``references/`` under other names, so
    ``pip install sprezzature-colors`` was never found, and every level but
    ``universal`` came back as the universal palette.
    """
    try:
        spec = importlib.util.find_spec(package)
    except (ImportError, ValueError):
        return None
    if spec is None or not spec.submodule_search_locations:
        return None
    return Path(next(iter(spec.submodule_search_locations)))


def _colors_references_dir() -> Optional[Path]:
    """Locate the ``references`` folder of a co-installed sprezzature-colors.

    Search order: a checkout beside this one, the skill folders of Claude Code
    and OpenCode, then the installed wheel. A folder counts only if it carries
    the site's palettes (``palette-corporate.csv``), which sprezzature-colors
    ships since 1.4.0: an older one still has the colours of before
    2026-11-14 in its ``palette.csv``, and reading it would bring them back.
    """
    here = Path(__file__).resolve()
    candidates = [here.parent.parent.parent / "sprezzature-colors" / "references"]
    candidates += [
        Path.home() / f".{runtime}" / "skills" / "sprezzature-colors" / "references"
        for runtime in ("claude", "opencode")
    ]
    installed = _installed_colors_package("sprezzature_colors_references")
    if installed is not None:
        candidates.append(installed)
    for d in candidates:
        if (d / "palette-corporate.csv").is_file():
            return d
    return None


def _sibling_palette_csv(theme: str = "corporate") -> Optional[Path]:
    """Locate the CSV of ``theme``'s palette, if sprezzature-colors is co-installed.

    Returns
    -------
    pathlib.Path or None
        The path to the CSV if found; ``None`` otherwise. Search:

        1. ``SPREZZATURE_COLORS_PALETTE`` env var (explicit override, a
           project's own brand palette; corporate theme only).
        2. ``palette-<theme>.csv`` in :func:`_colors_references_dir`.
    """
    if theme == "corporate":
        env = (os.environ.get("SPREZZATURE_COLORS_PALETTE") or os.environ.get("FRONT_COLORS_PALETTE") or "").strip()
        if env:
            p = Path(env).expanduser()
            if p.is_file():
                return p
    refs = _colors_references_dir()
    if refs is not None and (refs / f"palette-{theme}.csv").is_file():
        return refs / f"palette-{theme}.csv"
    return None


def _read_palette_rows(csv_path: Path) -> List[Dict[str, str]]:
    """Rows of a palette CSV, with the site's column names mapped to ``palette.csv``'s.

    The site's files name the colour ``Name`` and the psychology ``Positive`` /
    ``Negative``; ``palette.csv`` and a project's own file say ``Base`` and
    ``PsychologyPositive`` / ``PsychologyNegative``. Both read the same here.
    """
    renames = {"Name": "Base", "Positive": "PsychologyPositive", "Negative": "PsychologyNegative"}
    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    return [{renames.get(k, k): (v or "") for k, v in row.items() if k} for row in rows]


def _sibling_sprezzature_colors_scripts() -> Optional[Path]:
    """Locate ``sprezzature-colors/scripts`` (the accessibility-level engine) if present.

    Same co-installation search as :func:`_colors_references_dir`, one directory
    over. Returns ``None`` when sprezzature-colors is not alongside, in which case only
    the ``universal`` level is available (see :func:`load_palette`).
    """
    refs = _colors_references_dir()
    if refs is not None:
        # references/ -> ../scripts
        scripts = refs.parent / "scripts"
        if (scripts / "accessibility_levels.py").is_file():
            return scripts
    installed = _installed_colors_package("sprezzature_colors_scripts")
    if installed is not None and (installed / "accessibility_levels.py").is_file():
        return installed
    return None


def _apply_accessibility_level(palette: Dict[str, str], level: str) -> Dict[str, str]:
    """Remap ``palette`` to an accessibility ``level`` via the sprezzature-colors engine.

    The colour science (OKLCH round-trip, WCAG contrast, Machado colour-vision
    matrices) lives in ``sprezzature-colors/scripts/accessibility_levels.py`` so it is
    not duplicated here. When sprezzature-colors is not co-installed, or the level is
    unknown, the palette is returned unchanged and a warning is emitted, so a
    figure never crashes over accessibility styling.
    """
    scripts = _sibling_sprezzature_colors_scripts()
    if scripts is None:
        warnings.warn(
            f"accessibility level {level!r} requested but sprezzature-colors is not "
            "co-installed; using the universal palette",
            stacklevel=2,
        )
        return palette
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    try:
        from accessibility_levels import apply_level  # noqa: PLC0415 (lazy, optional dep)

        return apply_level(palette, level)
    except Exception as exc:  # pragma: no cover - defensive; never break a figure
        warnings.warn(f"accessibility level {level!r} failed ({exc}); using universal", stacklevel=2)
        return palette


def load_palette(accessibility: str = "universal", theme: str = "corporate") -> Dict[str, str]:
    """Read the canonical palette, at a chosen accessibility level and theme.

    Parameters
    ----------
    accessibility : str, optional
        The accessibility level to render the palette at. ``"universal"``
        (default) is the curated, colour-vision-safe standard everyone gets.
        Other levels are ``"high-contrast"``, ``"monochrome"``,
        ``"deuteranopia"``, ``"protanopia"`` and ``"tritanopia"``; they are
        applied by the sprezzature-colors engine when it is co-installed. See
        ``sprezzature-colors/references/accessibility-levels.md`` for the model.
        Applies on top of any theme's base palette -- academic's
        ``universal`` default is already CVD-safe by construction (Okabe-Ito),
        but the engine still runs for e.g. ``"monochrome"`` grayscale output.
    theme : str, optional
        One of :data:`THEMES`, the three palettes of deraison.ai/colors:
        ``"corporate"`` (default), ``"academic"`` or ``"print"``. Read from
        sprezzature-colors' copy of the site's CSV when it is co-installed,
        else from :data:`_PALETTES`. ``SPREZZATURE_COLORS_PALETTE`` replaces
        the corporate one with a project's own file.

    Returns
    -------
    dict of str to str
        Mapping ``{"Red": "#FF383C", ...}``: the eleven names in the site's
        order, then the aliases Teal, Mint and White (see
        :data:`_HUE_ALIASES`); values are the level-appropriate hex.
    """
    csv_path = _sibling_palette_csv(theme)
    palette: Dict[str, str] = {}
    if csv_path is not None:
        for row in _read_palette_rows(csv_path):
            name = (row.get("Base") or row.get("name") or "").strip()
            hexv = (row.get("Hexcode") or row.get("Hex") or row.get("hex") or "").strip()
            if name and hexv.startswith("#") and len(hexv) in (4, 7):
                palette[name] = hexv.upper()
    palette = _with_aliases(palette) if palette else dict(_fallback_for(theme))

    # ``universal`` is the identity, so the default path never touches the engine
    # and stays byte-for-byte what it always produced.
    if accessibility and accessibility != "universal":
        palette = _apply_accessibility_level(palette, accessibility)
    return palette


def leveled_colors(colors: Dict[str, str], accessibility: str = "universal") -> Dict[str, str]:
    """Apply an accessibility level to an *arbitrary* ``{name: hex}`` colour set.

    Some figures pick categorical colours that are not the shared palette (a
    curated per-species or per-class set tuned during the accessibility pass).
    Wrapping that set with this helper lets the figure still answer to the
    ``accessibility`` argument without adopting the house palette: ``universal``
    returns the colours unchanged (so the default figure is byte-for-byte the
    same), and every other level remaps *these* colours through the same
    sprezzature-colors engine that levels the palette.

    Do NOT use this on a continuous / perceptual colour map (viridis, a single
    hue ramp): those are already colour-vision- and greyscale-safe by
    construction, and re-spacing their anchors by lightness would de-tune them.
    Leave such maps at ``universal``.

    Parameters
    ----------
    colors : dict of str to str
        The figure's own ``{category: "#RRGGBB"}`` mapping.
    accessibility : str, optional
        One of the levels understood by :func:`load_palette`. Defaults to
        ``"universal"`` (the identity).

    Returns
    -------
    dict of str to str
        The same keys, remapped to the level (or unchanged for ``universal``).
    """
    if not accessibility or accessibility == "universal":
        return dict(colors)
    return _apply_accessibility_level(colors, accessibility)


#: Default categorical cycle order for :func:`cycle_hues` — the four hues
#: every ``_category_colors``/``_series_colors``/``_segment_colors`` copy
#: picked, before this helper existed, reordered once: the original
#: (Blue, Orange, Green, Purple) put Orange directly next to Green, two
#: hues of nearly the same luminance that several Ralph Eyeball Loop passes
#: independently found collapsing to the same grey under
#: grayscale/achromatopsia simulation. Swapping Green and Purple keeps the
#: same four hues (no caller's semantics change) but spaces every adjacent
#: pair (including the wrap) apart; on the corporate palette of 2026-11-14,
#: in Rec. 709 luma on 0-255, at least ~42 points:
#: Blue(115.7)-Orange(157.9)-Purple(93.7)-Green(159.8)-wrap.
_DEFAULT_CYCLE = ("Blue", "Orange", "Purple", "Green")


def cycle_hues(
    keys: List[str], accessibility: str = "universal", hues: Optional[List[str]] = None,
    theme: str = "corporate", semantic: bool = False,
) -> Dict[str, str]:
    """Assign each of `keys` a hue, cycling through a small qualitative set.

    Generalizes the ``_category_colors``/``_series_colors``/``_segment_colors``
    pattern that ~14 generators each hand-rolled: look up a handful of named
    hues from the accessibility-leveled palette, then hand them out to
    `keys` in order, wrapping around once the hue list is exhausted. Callers
    keep their own thin wrapper (its name and signature vary by figure, e.g.
    ``_category_colors(accessibility)``) that just delegates its body here.

    Parameters
    ----------
    keys : list of str
        The categories/series to color, in the order they should receive
        hues (typically a chart's fixed category list, not the row order,
        so the mapping is stable across `data` inputs).
    accessibility : str, optional
        Forwarded to :func:`load_palette`. Defaults to ``"universal"``.
    hues : list of str, optional
        Palette hue *names* to cycle through, e.g. ``["Blue", "Red"]``.
        Defaults to :data:`_DEFAULT_CYCLE` (``Blue, Orange, Purple, Green``),
        chosen for grayscale/CVD luminance separation between adjacent
        hues (see that constant's own comment). Names are
        shared across themes (see :data:`_ACADEMIC_PALETTE`), so a caller's
        existing `hues` list needs no change to theme correctly.
    theme : str, optional
        Forwarded to :func:`load_palette`. Defaults to ``"corporate"``.
    semantic : bool, optional
        ``False`` (default) keeps the plain cycle, byte for byte. ``True``
        first gives each key whose text names a meaning the hue of that
        meaning (see :func:`semantic_hue`: "Risque" gets the danger hue,
        "Confiance" the trust hue), then hands the rest the cycle, skipping
        the hues already taken.

    Returns
    -------
    dict of str to str
        ``{key: hex}``, one entry per `keys`, hues repeating past the 4th.

    Examples
    --------
    >>> colors = cycle_hues(["North", "South", "East", "West", "Central"])
    >>> len(colors)
    5
    >>> colors["North"] == colors["Central"]  # wraps after 4 hues
    True
    """
    palette = load_palette(accessibility, theme=theme)
    fallback = _fallback_for(theme)
    order = hues or list(_DEFAULT_CYCLE)
    picked = [palette.get(name, fallback.get(name, fallback["Blue"])) for name in order]
    if not picked:
        picked = [fallback["Blue"]]
    if not semantic:
        return {key: picked[i % len(picked)] for i, key in enumerate(keys)}
    return _semantic_assign(keys, palette, fallback, picked)


def os_adaptive_style(
    series: Dict[str, str],
    *,
    role: str = "fill",
    forced: bool = False,
    forced_keyword: str = "CanvasText",
    extra_contrast: str = "",
    extra_forced: str = "",
) -> str:
    """Emit the additive ``@media`` overrides that let one SVG adapt to the OS.

    The idea behind the "OS-adaptive" figure: ship *one* SVG that quietly
    retunes itself when the reader's operating system signals a preference,
    instead of a separate file per level. This returns only the ``@media``
    blocks — append them **inside the figure's existing** ``<style>``. Because
    a CSS class rule outranks an inline ``fill=""``/``stroke=""`` presentation
    attribute, and because *every* rule here lives inside a media query, the
    default render (no preference active) matches none of them and stays
    byte-for-byte what the figure always produced. Only when the OS asks does a
    block take over.

    Two signals are handled, deliberately:

    - ``prefers-contrast: more`` — deepen each series to its ``high-contrast``
      hue (via the same sprezzature-colors engine that levels the palette) on the
      chosen ``role``. This is the broad, safe win: it never loses category
      identity, it only strengthens it.
    - ``forced-colors: active`` (Windows High Contrast and kin) — opt-in via
      ``forced=True``. Only meaningful for figures whose category identity is
      carried by **position or shape, not colour** (a Venn, a parliament, a
      waffle): those can drop to system-palette line art and still read. Do
      **not** set ``forced=True`` on a colour-encoded figure (multi-line,
      stacked area, heatmap) — the ~4-colour system palette cannot preserve the
      encoding, and the browser leaves SVG fills alone by default, which is the
      correct behaviour there.

    ``prefers-color-scheme: dark`` is intentionally **not** handled: on a
    light-poster figure it needs a real design pass (ink inversion, blend-mode
    flips), not a hue swap, so it is left to a separate, deliberate effort.

    Parameters
    ----------
    series : dict of str to str
        Maps a **CSS selector** (e.g. ``".bar-3"``, ``".setlabel-A"``) to that
        series' base hex. The whole set is deepened together so the
        ``high-contrast`` spacing stays balanced.
    role : str, optional
        Which property the hue drives on these selectors under
        ``prefers-contrast``: ``"fill"`` (default), ``"stroke"``, or ``"both"``.
    forced : bool, optional
        Emit a ``forced-colors: active`` block. Default ``False``.
    forced_keyword : str, optional
        System colour keyword the selectors take under forced colours
        (``"CanvasText"`` default; ``"Canvas"`` for fills you want to blank).
    extra_contrast, extra_forced : str, optional
        Figure-specific CSS appended inside the respective block — for the
        legibility tuning the engine cannot know (e.g. dropping a lobe's
        ``fill-opacity`` so region counts stay readable, or a text backplate).

    Returns
    -------
    str
        The ``@media`` block(s), ready to concatenate into the figure's
        ``<style>``. Empty selectors + no ``forced`` + no extras yield ``""``.
    """
    if role not in ("fill", "stroke", "both"):
        raise ValueError(f"role must be fill/stroke/both, got {role!r}")

    blocks: List[str] = []

    # ---- prefers-contrast: more -> deepened, higher-contrast hues ----
    hc = leveled_colors(series, "high-contrast") if series else {}
    contrast_rows: List[str] = []
    for selector, hexv in hc.items():
        if role == "fill":
            decl = f"fill:{hexv};"
        elif role == "stroke":
            decl = f"stroke:{hexv};"
        else:
            decl = f"fill:{hexv};stroke:{hexv};"
        contrast_rows.append(f"{selector}{{{decl}}}")
    if extra_contrast:
        contrast_rows.append(extra_contrast)
    if contrast_rows:
        blocks.append(
            "@media (prefers-contrast: more){\n  " + "\n  ".join(contrast_rows) + "\n}"
        )

    # ---- forced-colors: active -> hand identity to the system palette ----
    if forced or extra_forced:
        forced_rows = [f"{selector}{{fill:{forced_keyword};}}" for selector in series]
        if extra_forced:
            forced_rows.append(extra_forced)
        blocks.append(
            "@media (forced-colors: active){\n  " + "\n  ".join(forced_rows) + "\n}"
        )

    return "\n".join(blocks)


#: House inks and their dark-mode counterparts. The generators pull ink from a
#: shared, fixed set (`_BG` #FFFFFF, `_INK` #1D1D1F, `_SUBTLE` #6E6E73), so a
#: single attribute-selector block flips the whole catalogue to a dark surface
#: without per-figure bespoke selectors.
_DARK_INK_MAP: Dict[str, str] = {
    "#FFFFFF": "#0B0B0C",   # paper -> near-black surface
    "#1D1D1F": "#F2F2F7",   # primary ink -> off-white
    "#6E6E73": "#9C9CA3",   # secondary ink -> light grey
}


def os_dark_style(*, ink_map: Optional[Dict[str, str]] = None, screen_blend: bool = True, extra: str = "") -> str:
    """Emit an additive ``prefers-color-scheme: dark`` block for a house figure.

    Because every generator inks its text and paper from the same fixed
    constants, dark mode is mostly uniform: invert the paper and the two ink
    tiers with attribute selectors (`[fill="#RRGGBB"]`), and flip any
    ``mix-blend-mode: multiply`` group to ``screen`` so overlaps *lighten* on a
    dark surface instead of turning to mud. The data hues are left alone (the
    saturated house palette reads on dark). White keylines and halos
    (``stroke="#FFFFFF"``) are deliberately not touched — white-on-dark still
    separates marks. Anything figure-specific (a light panel, a custom
    gridline, a white pill that should darken) goes through ``extra``.

    The block is additive and media-gated, so the default (light) render is
    unchanged; it only applies when the reader's operating system asks for dark.

    Parameters
    ----------
    ink_map : dict of str to str, optional
        Light-hex -> dark-hex overrides. Defaults to :data:`_DARK_INK_MAP`
        (paper + the two ink tiers). Keys are matched as ``[fill="key"]``.
    screen_blend : bool, optional
        If ``True`` (default), flip ``mix-blend-mode: multiply`` groups to
        ``screen`` for correct overlap behaviour on dark.
    extra : str, optional
        Figure-specific CSS appended inside the block.

    Returns
    -------
    str
        A single ``@media (prefers-color-scheme: dark){ ... }`` block, or ``""``
        if nothing would be emitted.
    """
    rows: List[str] = []
    for light, dark in (ink_map or _DARK_INK_MAP).items():
        rows.append(f'[fill="{light}"]{{fill:{dark};}}')
    if screen_blend:
        rows.append('[style*="multiply"]{mix-blend-mode:screen;}')
    if extra:
        rows.append(extra)
    if not rows:
        return ""
    return "@media (prefers-color-scheme: dark){\n  " + "\n  ".join(rows) + "\n}"


#: A cycling set of forced-colors fill patterns. Each is a `Canvas`-backed tile
#: stroked/dotted in `CanvasText`, so it renders in the reader's system theme
#: and survives Windows High Contrast, where a colour encoding would collapse.
_FC_PATTERN_TILES: List[str] = [
    '<rect width="8" height="8" fill="Canvas"/><path d="M0,8L8,0" stroke="CanvasText" stroke-width="1.6"/>',       # diag /
    '<rect width="8" height="8" fill="Canvas"/><path d="M0,0L8,8" stroke="CanvasText" stroke-width="1.6"/>',       # diag \
    '<rect width="8" height="8" fill="Canvas"/><path d="M0,4L8,4" stroke="CanvasText" stroke-width="1.6"/>',       # horizontal
    '<rect width="8" height="8" fill="Canvas"/><path d="M4,0L4,8" stroke="CanvasText" stroke-width="1.6"/>',       # vertical
    '<rect width="10" height="10" fill="Canvas"/><circle cx="5" cy="5" r="1.8" fill="CanvasText"/>',               # dots
    '<rect width="8" height="8" fill="Canvas"/><path d="M0,4L8,4M4,0L4,8" stroke="CanvasText" stroke-width="1.4"/>',  # cross
]


def forced_color_patterns(series: List[str], *, prefix: str = "fcp") -> Tuple[str, str]:
    """Build per-series SVG patterns + the forced-colors block that applies them.

    For a colour-*encoded* figure (multi-line, streamgraph, many wedges) the
    roughly four-colour Windows High Contrast palette cannot preserve the
    encoding, and a flat system colour would merge every series. This gives each
    series a distinct **pattern** (hatch, dots, cross) drawn in ``Canvas`` /
    ``CanvasText``, so identity survives without colour. ``forced-color-adjust:
    none`` keeps the pattern fill from being overridden by the user agent.

    The patterns are additive and only referenced inside the forced-colors media
    query, so the default render is unchanged.

    Parameters
    ----------
    series : list of str
        The CSS selectors (e.g. ``[".river-0", ".river-1", ...]``) whose fills
        should become patterns under forced colours, in order.
    prefix : str, optional
        Id prefix for the generated ``<pattern>`` elements. Defaults to
        ``"fcp"``. Pass a figure-unique prefix if a page inlines several SVGs.

    Returns
    -------
    tuple of (str, str)
        ``(defs, style)`` — the ``<pattern>`` definitions to drop anywhere in
        the SVG, and the ``@media (forced-colors: active){ ... }`` block to
        append inside ``<style>``. Both are ``""`` when ``series`` is empty.
    """
    if not series:
        return "", ""
    defs: List[str] = []
    rules: List[str] = []
    for i, selector in enumerate(series):
        pid = f"{prefix}-{i}"
        tile = _FC_PATTERN_TILES[i % len(_FC_PATTERN_TILES)]
        # A 10-unit tile for dots, 8 for the rest; patternUnits keeps it stable
        # under the figure's own transforms.
        size = 10 if "circle" in tile else 8
        defs.append(
            f'<pattern id="{pid}" width="{size}" height="{size}" '
            f'patternUnits="userSpaceOnUse">{tile}</pattern>'
        )
        rules.append(f"{selector}{{fill:url(#{pid});forced-color-adjust:none;}}")
    style = "@media (forced-colors: active){\n  " + "\n  ".join(rules) + "\n}"
    return "".join(defs), style


def load_semantic_palette() -> Dict[str, Dict[str, Any]]:
    """Load the full semantic palette (base + emotion + concepts + psychology).

    Reads every column of ``sprezzature-colors/references/palette.csv``:
    ``Hexcode``, ``Base``, ``LightHex``, ``Emotion``, ``Concepts``,
    ``PsychologyPositive``, ``PsychologyNegative``. Documented at
    <https://deraison.ai/colors/>.

    Returns
    -------
    dict of str to dict
        Mapping ``{base_color_name: {"hex": "#RRGGBB", "light":
        "#RRGGBB", "emotion": str, "concepts": [str, ...],
        "psychology_positive": [str, ...],
        "psychology_negative": [str, ...]}}``.
    """
    csv_path = _sibling_palette_csv()
    if csv_path is None:
        return _fallback_semantic()

    out: Dict[str, Dict[str, Any]] = {}
    for row in _read_palette_rows(csv_path):
        base = (row.get("Base") or "").strip()
        hex_ = (row.get("Hexcode") or "").strip().upper()
        if not (base and hex_.startswith("#")):
            continue
        out[base] = {
            "hex": hex_,
            "light": (row.get("LightHex") or "").strip().upper() or hex_,
            "emotion": (row.get("Emotion") or "").strip(),
            "concepts": [c.strip() for c in (row.get("Concepts") or "").split(",") if c.strip()],
            "psychology_positive": [
                c.strip() for c in (row.get("PsychologyPositive") or "").split(",") if c.strip()
            ],
            "psychology_negative": [
                c.strip() for c in (row.get("PsychologyNegative") or "").split(",") if c.strip()
            ],
        }
    return out or _fallback_semantic()


def _fallback_semantic() -> Dict[str, Dict[str, Any]]:
    """Return a minimal semantic palette when the CSV is unavailable."""
    return {
        base: {
            "hex": hexv,
            "light": hexv,
            "emotion": next((e for e, h in _FALLBACK_EMOTIONS.items() if h == hexv), ""),
            "concepts": [],
            "psychology_positive": [],
            "psychology_negative": [],
        }
        for base, hexv in _PALETTES["corporate"].items()
    }


def emotion_to_hex(emotion: str) -> Optional[str]:
    """Return the curated hex for one of the palette's Emotion labels.

    Parameters
    ----------
    emotion : str
        Case-insensitive Emotion label from the palette CSV
        (``"Anger"``, ``"Joy"``, ``"Sadness"``, …).

    Returns
    -------
    str or None
        Hex string, or ``None`` when the label is not in the palette.
    """
    target = emotion.strip().lower()
    for _base, meta in load_semantic_palette().items():
        if meta["emotion"].lower() == target:
            return meta["hex"]
    fallback = {k.lower(): v for k, v in _FALLBACK_EMOTIONS.items()}
    return fallback.get(target)


def concept_search(term: str) -> List[str]:
    """Return every palette hex whose ``Concepts`` column mentions ``term``.

    Parameters
    ----------
    term : str
        Case-insensitive concept term (``"Trust"``, ``"Bold"``,
        ``"Optimism"``, …).

    Returns
    -------
    list of str
        Hex strings, order-preserving.
    """
    target = term.strip().lower()
    matches: List[str] = []
    for meta in load_semantic_palette().values():
        joined = " ".join(meta.get("concepts", [])).lower()
        joined_pos = " ".join(meta.get("psychology_positive", [])).lower()
        if target in joined or target in joined_pos:
            matches.append(meta["hex"])
    return matches


def psychology_for(base: str) -> Dict[str, List[str]]:
    """Return the positive / negative psychology terms for a base color.

    Parameters
    ----------
    base : str
        Case-insensitive base color name (``"Red"``, ``"Green"``, …).

    Returns
    -------
    dict
        ``{"positive": [...], "negative": [...]}``. Empty lists if the
        palette CSV is unavailable.
    """
    target = base.strip().lower()
    for name, meta in load_semantic_palette().items():
        if name.lower() == target:
            return {
                "positive": meta.get("psychology_positive", []),
                "negative": meta.get("psychology_negative", []),
            }
    return {"positive": [], "negative": []}


# ------------------------------------------------------------------
# Categorical sequences for chart encodings
# ------------------------------------------------------------------
def qualitative_sequence(n: int = 8, theme: str = "corporate") -> List[str]:
    """Return the first ``n`` curated saturated hues.

    Parameters
    ----------
    n : int, optional
        How many colors to return (default 8). Cycles the base list
        when ``n`` exceeds the palette size.
    theme : str, optional
        Forwarded to :func:`load_palette`. Defaults to ``"corporate"``.
        Each palette has eight distinct hues; the neutrals and the aliases
        (Teal, Mint, White) are skipped, and duplicates are dropped so a
        caller never sees the same hex twice in a row.

    Returns
    -------
    list of str
        ``n`` hex strings, brand-order.
    """
    # Skip the neutrals and the aliases for a qualitative encoding, by name:
    # each palette has its own grey and brown, so a list of hex codes to skip
    # was right for one palette only. De-duplicate in case a project's own
    # file gives two names one hex.
    skip = {"Brown", "Black", "Gray", "White", *_HUE_ALIASES}
    seen: set = set()
    saturated: List[str] = []
    for name, h in load_palette(theme=theme).items():
        hu = h.upper()
        if name in skip or hu in seen:
            continue
        seen.add(hu)
        saturated.append(h)
    if n <= len(saturated):
        return saturated[:n]
    out: List[str] = []
    while len(out) < n:
        out.extend(saturated)
    return out[:n]


# ------------------------------------------------------------------
# Colour = meaning: a label's words pick its hue
# ------------------------------------------------------------------
#: Words that name the psychological dimension of a palette hue, in English
#: and French, lower case. Source: <https://deraison.ai/en/colors> (its
#: psychology, concepts and emotions tables). A hue carries a positive and a negative
#: side, and both are listed: red is power and energy, and also danger,
#: warning and anger; purple is wisdom and imagination, and also fear.
#: The keys are palette hue NAMES, shared by the three palettes of
#: <https://deraison.ai/colors/>, so each resolves the same meaning to its
#: own hex. Kept short on purpose: a word belongs here only if a reader would
#: agree on its colour without being told.
SEMANTIC_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    # Red: power, energy / danger, warning, anger.
    "Red": (
        "danger", "dangers", "dangereux", "risk", "risque", "error", "erreur", "warning",
        "alert", "alerte", "avertissement", "anger", "colère", "threat", "menace", "loss",
        "perte", "failure", "fail", "échec", "incident", "attack", "attaque", "urgent",
        "urgence", "critical", "critique", "power", "puissance", "energy", "énergie",
        "passion", "pain", "douleur", "defect", "défaut", "bug",
    ),
    # Orange: courage, warmth, innovation / frustration.
    "Orange": (
        "courage", "warmth", "chaleur", "innovation", "innover", "friendly", "convivial",
        "cheerful", "confidence", "enthusiasm", "enthousiasme", "frustration", "surprise",
    ),
    # Yellow: optimism, creativity / caution, anxiety.
    "Yellow": (
        "optimism", "optimisme", "creativity", "créativité", "idea", "idée", "caution",
        "prudence", "anxiety", "anxiété", "joy", "joie", "happiness", "bonheur", "pending",
        "attente",
    ),
    # Green: health, hope, growth, nature / stagnation, sickness.
    "Green": (
        "health", "santé", "growth", "croissance", "gain", "profit", "hope", "espoir",
        "nature", "environment", "environnement", "prosperity", "prospérité", "success",
        "succès", "réussite", "win", "sustainable", "durable", "fresh", "healthy", "sain",
        "stagnation", "sickness", "maladie",
    ),
    # Turquoise: communication, clarity, calm / secrecy, unreliability.
    "Turquoise": (
        "communication", "clarity", "clarté", "calm", "calme", "transparency",
        "transparence", "inspiration", "dialogue", "healing", "guérison", "secrecy",
        "secret", "unreliable",
    ),
    # Blue: trust, dependability, logic, security / coldness.
    "Blue": (
        "trust", "confiance", "reliable", "fiable", "fiabilité", "reliability",
        "dependable", "secure", "security", "sécurité", "sûr", "sûre", "safe", "safety",
        "logic", "logique", "loyalty", "loyauté", "stability", "stabilité", "serenity",
        "sérénité", "coldness", "froideur",
    ),
    # Purple: wisdom, imagination, sophistication / fear.
    "Purple": (
        "wisdom", "sagesse", "imagination", "imaginative", "sophistication", "luxury",
        "luxe", "wealth", "richesse", "spirituality", "spiritualité", "fear", "peur",
        "crainte",
    ),
    # #AC7F5E brown: seriousness, earthiness, support, authenticity.
    "Brown": (
        "serious", "seriousness", "sérieux", "earth", "terre", "earthiness", "support",
        "soutien", "authenticity", "authenticité", "authentic", "authentique",
    ),
    # Black: authority, substance / menace, mourning.
    "Black": (
        "authority", "autorité", "elegance", "élégance", "mourning", "deuil",
        "oppression", "evil",
    ),
    # Grey: neutrality, balance / lack of energy.
    "Gray": (
        "neutral", "neutre", "neutrality", "neutralité", "balance", "équilibre", "other",
        "others", "autre", "autres", "misc", "unknown", "inconnu", "n/a",
    ),
}

#: Longest suffix a keyword may take and still match (plurals, inflections):
#: "risques", "erreurs", "risky". Longer would let "fear" match "fearless".
_SUFFIX_SLACK = 3


def semantic_hue(label: str) -> Optional[str]:
    """The palette hue NAME whose meaning `label` carries, or ``None``.

    Reads the label's words in order and returns the hue of the first one
    listed in :data:`SEMANTIC_KEYWORDS`. A keyword of four letters or more
    also matches with up to three more letters ("risques", "erreurs"); a
    shorter one only matches whole ("gain", "sûr", never "sur").

    Parameters
    ----------
    label : str
        A series, card or category label, in English or French.

    Returns
    -------
    str or None
        A key of :func:`load_palette` (``"Red"``, ``"Blue"``, ...), or
        ``None`` when no word of the label names a meaning.

    Examples
    --------
    >>> semantic_hue("Risque opérationnel")
    'Red'
    >>> semantic_hue("Customer trust")
    'Blue'
    >>> semantic_hue("Q3") is None
    True
    """
    words = re.findall(r"[\w/'’-]+", (label or "").casefold())
    for word in words:
        for hue, keywords in SEMANTIC_KEYWORDS.items():
            for kw in keywords:
                if word == kw or (
                    len(kw) >= 4 and word.startswith(kw) and len(word) - len(kw) <= _SUFFIX_SLACK
                ):
                    return hue
    return None


def _semantic_assign(
    keys: List[str], palette: Dict[str, str], fallback: Dict[str, str], picked: List[str],
) -> Dict[str, str]:
    """Meaning first, then the cycle for whatever names no meaning.

    One hue per meaning: the first key naming it takes it, a second key
    naming the same meaning gets the next free cycle hue, because two
    categories drawn alike can no longer be told apart.
    """
    out: Dict[str, str] = {}
    taken: set = set()
    for key in keys:
        hue = semantic_hue(str(key))
        if hue is None:
            continue
        hexv = palette.get(hue, fallback.get(hue))
        if hexv and hexv.upper() not in taken:
            out[key] = hexv
            taken.add(hexv.upper())
    free = [h for h in picked if h.upper() not in taken] or picked
    i = 0
    for key in keys:
        if key in out:
            continue
        out[key] = free[i % len(free)]
        i += 1
    return {key: out[key] for key in keys}


def semantic_colors(
    labels: List[str], *, theme: str = "corporate", accessibility: str = "universal",
    hues: Optional[List[str]] = None,
) -> Dict[str, str]:
    """Suggest one colour per label, read from what the label says.

    The house rule "colour = meaning" as a function: a label about danger or
    risk gets vermilion, one about trust or reliability gets blue, one about
    health or growth gets green, and so on (see :data:`SEMANTIC_KEYWORDS`).
    Labels that name no meaning get the usual categorical cycle, minus the
    hues already taken. A suggestion, not a law: pass the result to a
    figure's own colour option (``series_colors=`` for ``line-multi``) or
    override any entry.

    Parameters
    ----------
    labels : list of str
        The series, cards or categories to colour, in order.
    theme : str, optional
        ``"corporate"`` (default), ``"academic"`` or ``"print"``.
    accessibility : str, optional
        Forwarded to :func:`load_palette`.
    hues : list of str, optional
        The fallback cycle, as hue names. Defaults to :func:`cycle_hues`'s.

    Returns
    -------
    dict of str to str
        ``{label: "#RRGGBB"}``, one entry per label, in order.

    Examples
    --------
    >>> colors = semantic_colors(["Risque", "Confiance", "Croissance"], theme="academic")
    >>> colors["Risque"], colors["Confiance"], colors["Croissance"]
    ('#E73121', '#0072B2', '#009E73')
    """
    return cycle_hues(list(labels), accessibility, hues=hues, theme=theme, semantic=True)


# ------------------------------------------------------------------
# Colour-blind-safe diverging pair for signed / +/- data
# ------------------------------------------------------------------
#: The habitual **red ↔ green** diverging is hostile to red-green colour
#: blindness (~8 % of men): under protanopia / deuteranopia the two ends both
#: drift to a muddy tan and collapse into one hue, so the sign of the data can no
#: longer be read from colour. The **blue ↔ red** axis stays discriminable — blue
#: survives, red darkens toward brown — so it is the default whenever the +/-
#: distinction must be legible *from colour*, not only from a sign or a label.
#: Blue also carries *Trust / Logic* and red *Danger / Warning* in the sprezzature-colors
#: concepts, which fits "positive vs negative". Verify any diverging choice on the
#: rendered pixels with ``simulate_cvd.py``. Source:
#: <https://deraison.ai/colors/>.
DIVERGING_CVD_SAFE = (_PALETTES["corporate"]["Blue"], "#F2F4F6", _PALETTES["corporate"]["Red"])  # (positive, neutral mid, negative)


def diverging_pair(cvd_safe: bool = True) -> tuple:
    """Return a ``(positive, negative)`` hex pair for signed / growth data.

    Parameters
    ----------
    cvd_safe : bool, optional
        When ``True`` (default) return the **blue ↔ red** pair, which survives
        red-green colour blindness. When ``False`` return the conventional
        **green ↔ red** pair (finance-idiomatic but not colour-blind-safe) —
        only pick it when the sign is *also* encoded another way (a +/- glyph,
        position above/below zero) and you have confirmed it in ``simulate_cvd``.

    Returns
    -------
    tuple of str
        ``(positive_hex, negative_hex)``.
    """
    if cvd_safe:
        return DIVERGING_CVD_SAFE[0], DIVERGING_CVD_SAFE[2]
    palette = load_palette()
    return palette["Green"], palette["Red"]


# ------------------------------------------------------------------
# Corners — the Sprezzature Corner Policy (see references/corners.md)
# ------------------------------------------------------------------
#: The house radius scale in user-space pixels (figures). The UI mirrors these
#: as rem tokens in sprezzature-ui's generated CSS.
CORNERS: Dict[str, float] = {
    "none": 0.0,       # measurements, grids, adjacent/baseline corners
    "hairline": 1.0,   # the MOST a grid cell may ever have
    "xs": 2.5,         # tiles (treemap/mosaic/waffle), arc segments, small chips
    "sm": 4.0,         # bar value-ends, legend swatches, small controls
    "md": 7.0,         # buttons, inputs, node boxes, badges, tooltips
    "lg": 12.0,        # cards, chart panels, the figure frame
    "xl": 16.0,        # large containers / hero panels
}

#: Per-family size coefficient and cap token for the sizing rule
#: ``radius = clamp(0, k * min(w, h), cap)``.
_FAMILY_RULE: Dict[str, Tuple[float, str]] = {
    "bar": (0.18, "sm"),      # round the value-end only; a flat enough cap to read
    "tile": (0.12, "xs"),     # treemap / mosaic / waffle; also clamp to gap/2 at call site
    "arc": (1.0, "xs"),       # pie / donut / sunburst / rose; gentle, subtle
    "box": (0.20, "md"),      # text/node boxes
    "panel": (1.0, "lg"),     # cards / chart frame (fixed, not size-scaled)
}


def corner_radius(width: float, height: float, family: str = "bar") -> float:
    """Radius in px for a data mark, per the Sprezzature Corner Policy.

    ``radius = clamp(0, k * min(width, height), cap)`` where ``k`` and the cap
    come from the mark ``family`` (see :data:`_FAMILY_RULE`). Small marks fall to
    ~0 by the cap, which is intended: crisp beats mushy. Grids and measurement
    marks must not call this at all — they stay square.
    """
    k, cap_token = _FAMILY_RULE.get(family, _FAMILY_RULE["bar"])
    cap = CORNERS[cap_token]
    return max(0.0, min(k * min(width, height), cap))


def inner_radius(outer: float, gap: float) -> float:
    """Concentric inner radius for a shape nested in a rounded container:
    ``max(0, outer - gap)`` (Apple's concentric-corner rule). If the gap is at
    least the outer radius, the inner corner is square."""
    return max(0.0, outer - gap)


# ------------------------------------------------------------------
# Polarity vocabulary
# ------------------------------------------------------------------
POLARITY_HINTS: Dict[str, str] = {
    # metric substring (lowercase) -> "higher-better" | "lower-better"
    "latency":       "lower-better",
    "response":      "lower-better",
    "response_time": "lower-better",
    "error":         "lower-better",
    "errors":        "lower-better",
    "bug":           "lower-better",
    "bugs":          "lower-better",
    "cost":          "lower-better",
    "churn":         "lower-better",
    "attrition":     "lower-better",
    "conversion":    "higher-better",
    "revenue":       "higher-better",
    "sales":         "higher-better",
    "retention":     "higher-better",
    "engagement":    "higher-better",
    "accuracy":      "higher-better",
    "f1":            "higher-better",
    "recall":        "higher-better",
    "precision":     "higher-better",
    "auc":           "higher-better",
    "roc_auc":       "higher-better",
    "r2":            "higher-better",
    "throughput":    "higher-better",
    "uptime":        "higher-better",
    "availability":  "higher-better",
    "mae":           "lower-better",
    "mse":           "lower-better",
    "rmse":          "lower-better",
    "loss":          "lower-better",
}


def infer_polarity(metric_name: str) -> Optional[str]:
    """Guess polarity from a metric name; return ``None`` when ambiguous.

    Parameters
    ----------
    metric_name : str
        The axis-title or column name to score.

    Returns
    -------
    str or None
        ``"higher-better"``, ``"lower-better"``, or ``None`` if no
        substring in :data:`POLARITY_HINTS` matched.
    """
    if not metric_name:
        return None
    lower = metric_name.lower()
    for substr, polarity in POLARITY_HINTS.items():
        # word-ish boundary: substring surrounded by non-alphanumerics or ends
        if substr in lower:
            return polarity
    return None


# ------------------------------------------------------------------
# Polarity → color mapping
# ------------------------------------------------------------------
#: Base color to reach for by polarity intent. Rationale:
#: **higher-better** and **lower-better** are both "goal-directed" —
#: readers want to see the metric move — so both map to Green
#: (psychology-positive: *Health*, *Hope*, *Growth*, *Prosperity*).
#: **target=** shifts to Blue (psychology-positive: *Trust*, *Logic*,
#: *Security*) — the metric is neutral; the frame is compliance.
#: The **breach** overlay uses Red (psychology-negative: *Warning*,
#: *Danger*) to flag SLA violations without co-opting the base
#: encoding. Source: <https://deraison.ai/colors/>.
POLARITY_COLOR: Dict[str, str] = {
    "higher-better": "Green",
    "lower-better":  "Green",
    "target":        "Blue",
    "breach":        "Red",
    "neutral":       "Gray",
}


def polarity_color(
    polarity: Optional[str],
    *,
    role: str = "primary",
    dark: bool = False,
) -> Optional[str]:
    """Return the house-style hex for a polarity intent.

    Never a substitute for the polarity text tag on the axis title —
    ~8 % of male viewers cannot read the color signal alone (see
    ``cvd-simulation.md``). Used as a *reinforcement* layer.

    Parameters
    ----------
    polarity : str or None
        One of ``"higher-better"``, ``"lower-better"``, or
        ``"target=<N>"``. Anything else returns ``None`` (caller keeps
        the qualitative palette).
    role : {'primary', 'breach'}, optional
        ``"primary"`` returns the goal color (Green or Blue);
        ``"breach"`` returns the SLA-violation overlay (Red).
    dark : bool, optional
        Currently unused — every curated base hex meets contrast on
        both background modes. Reserved for future light/dark variant
        selection.

    Returns
    -------
    str or None
        A hex string from the curated palette, or ``None`` when the
        polarity is not one the mapping recognises.
    """
    if not polarity:
        return None
    if role == "breach":
        base: str | None = POLARITY_COLOR["breach"]
    elif polarity.startswith("target="):
        base = POLARITY_COLOR["target"]
    else:
        base = POLARITY_COLOR.get(polarity)
    if base is None:
        return None
    palette = load_palette()
    return palette.get(base)


def polarity_tag(polarity: Optional[str], lang: str = "en") -> str:
    """Return the parenthesised polarity tag for an axis title.

    Parameters
    ----------
    polarity : {'higher-better', 'lower-better', None} or ``"target=<N>"``
        The polarity to render.
    lang : str, optional
        BCP-47 base tag; controls the translation.

    Returns
    -------
    str
        E.g. ``" (higher is better)"`` — includes the leading space so
        it can be safely appended to any axis title. Empty when
        polarity is ``None``.
    """
    if not polarity:
        return ""
    translations = {
        "higher-better": {"en": " (higher is better)", "fr": " (plus c’est haut, mieux c’est)", "de": " (höher ist besser)", "es": " (más alto es mejor)"},
        "lower-better":  {"en": " (lower is better)",  "fr": " (plus c’est bas, mieux c’est)",  "de": " (niedriger ist besser)", "es": " (más bajo es mejor)"},
    }
    if polarity.startswith("target="):
        n = polarity.split("=", 1)[1]
        return {
            "en": f" (target = {n})",
            "fr": f" (cible = {n})",
            "de": f" (Ziel = {n})",
            "es": f" (objetivo = {n})",
        }.get(lang, f" (target = {n})")
    return translations.get(polarity, {}).get(lang, translations.get(polarity, {}).get("en", ""))
