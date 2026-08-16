"""
fonts — the project's typeface sources: Roboto/Roboto Serif/Roboto Mono (the
default **corporate** theme) and Latin Modern Roman/Mono (the **academic**
theme, a LaTeX-native face -- GUST e-foundry's free extension of Donald
Knuth's Computer Modern), bundled as TTF/WOFF2 files so every figure and the
Studio web app render the house typography identically regardless of what is
(or is not) installed on the host machine. No more hoping
``"Roboto, sans-serif"`` resolves to the real thing -- the font is
registered / embedded directly.

Font files live under ``assets/fonts/`` in the source tree and ship in the
wheel as the sibling package ``sprezzature_figures_fonts`` (same pattern as
``scripts/`` -> ``sprezzature_figures_scripts``). Sources: the OFL-licensed
Google Fonts repository for Roboto (see the ``OFL-*.txt`` files), and GUST
e-foundry's Latin Modern under the GUST Font License / LPPL (see
``GUST-FONT-LICENSE-LatinModern.txt``) -- both permit bundling and
redistribution.

This module is deliberately **stdlib-only** at import time (only
``base64``/``functools``/``pathlib``) so ``scripts/_svg.py`` -- which must
stay importable without the dataviz tier -- can depend on it. The optional
integration (:func:`register_matplotlib`) imports its target library lazily
and no-ops if it is not installed. The rasteriser (``resvg_py``) has no
persistent font-directory registration -- callers pass :data:`RESVG_FONT_DIRS`
as the ``font_dirs`` keyword on each ``svg_to_bytes`` call instead.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import base64
import functools
from collections.abc import Sequence
from pathlib import Path

# Font files live one level up from this package, under assets/fonts/. In
# the source tree that's <repo>/assets/fonts; once installed it ships
# (collision-free) as the sibling package sprezzature_figures_fonts/.
_pkg_parent = Path(__file__).resolve().parent.parent
FONTS_DIR = next(
    (
        p
        for p in (_pkg_parent / "assets" / "fonts", _pkg_parent / "sprezzature_figures_fonts")
        if p.is_dir()
    ),
    _pkg_parent / "assets" / "fonts",
)

# CSS font stacks every generator / the web app should use -- the bundled
# face first, a close system fallback second (only exercised in the
# vanishingly rare case the bundled font file itself failed to load).
SANS_STACK = "Roboto, system-ui, sans-serif"
SERIF_STACK = "Roboto Serif, Georgia, serif"
MONO_STACK = "Roboto Mono, ui-monospace, monospace"

# The academic theme's stacks (see :data:`THEMES`) -- Latin Modern is a
# LaTeX-native face, so a chart set in it reads as a journal figure rather
# than a product-UI chart. No sans stack: academic mode has no sans use
# (titles/body use the serif; ticks/values use the mono), unlike corporate.
ACADEMIC_SERIF_STACK = "LM Roman, Latin Modern Roman, Georgia, serif"
ACADEMIC_MONO_STACK = "LM Mono, Latin Modern Mono, ui-monospace, monospace"

# key -> (ttf filename, woff2 filename, CSS font-family, font-style, font-weight range)
_FACES: dict[str, dict[str, str]] = {
    "sans": {
        "ttf": "Roboto-Variable.ttf",
        "woff2": "Roboto-Variable.woff2",
        "family": "Roboto",
        "style": "normal",
        "weight": "100 900",
    },
    "sans_italic": {
        "ttf": "Roboto-Italic-Variable.ttf",
        "woff2": "Roboto-Italic-Variable.woff2",
        "family": "Roboto",
        "style": "italic",
        "weight": "100 900",
    },
    "serif": {
        "ttf": "RobotoSerif-Variable.ttf",
        "woff2": "RobotoSerif-Variable.woff2",
        "family": "Roboto Serif",
        "style": "normal",
        "weight": "100 900",
    },
    "serif_italic": {
        "ttf": "RobotoSerif-Italic-Variable.ttf",
        "woff2": "RobotoSerif-Italic-Variable.woff2",
        "family": "Roboto Serif",
        "style": "italic",
        "weight": "100 900",
    },
    "mono": {
        "ttf": "RobotoMono-Variable.ttf",
        "woff2": "RobotoMono-Variable.woff2",
        "family": "Roboto Mono",
        "style": "normal",
        "weight": "100 900",
    },
    "mono_italic": {
        "ttf": "RobotoMono-Italic-Variable.ttf",
        "woff2": "RobotoMono-Italic-Variable.woff2",
        "family": "Roboto Mono",
        "style": "italic",
        "weight": "100 900",
    },
    # Latin Modern is static (no variable-font axis), so bold/italic are
    # separate files rather than a weight range on one face.
    "academic_serif": {
        "ttf": "LatinModernRoman-Regular.ttf",
        "woff2": "LatinModernRoman-Regular.woff2",
        "family": "LM Roman",
        "style": "normal",
        "weight": "400",
    },
    "academic_serif_bold": {
        "ttf": "LatinModernRoman-Bold.ttf",
        "woff2": "LatinModernRoman-Bold.woff2",
        "family": "LM Roman",
        "style": "normal",
        "weight": "700",
    },
    "academic_serif_italic": {
        "ttf": "LatinModernRoman-Italic.ttf",
        "woff2": "LatinModernRoman-Italic.woff2",
        "family": "LM Roman",
        "style": "italic",
        "weight": "400",
    },
    "academic_mono": {
        "ttf": "LatinModernMono-Regular.ttf",
        "woff2": "LatinModernMono-Regular.woff2",
        "family": "LM Mono",
        "style": "normal",
        "weight": "400",
    },
}

# The faces figures actually set as font-family (see _svg.py svg_open());
# Roboto Serif is a publication/editorial option (references/publication-
# presets.md) that no generator currently uses under the corporate theme, so
# it is registered for matplotlib/the web app but not embedded by default.
DEFAULT_SVG_FACES: tuple[str, ...] = ("sans", "mono")

#: theme name -> (embedded SVG faces, chrome-text stack, tick/value-label
#: stack). ``THEMES["corporate"]`` reproduces :data:`DEFAULT_SVG_FACES` /
#: :data:`SANS_STACK` / :data:`MONO_STACK` exactly, so selecting it is a
#: no-op relative to today's default render. See :func:`svg_faces_for_theme`.
THEMES: dict[str, dict[str, object]] = {
    "corporate": {
        "faces": ("sans", "mono"),
        "chrome_stack": SANS_STACK,
        "mono_stack": MONO_STACK,
    },
    "academic": {
        "faces": (
            "academic_serif",
            "academic_serif_bold",
            "academic_serif_italic",
            "academic_mono",
        ),
        "chrome_stack": ACADEMIC_SERIF_STACK,
        "mono_stack": ACADEMIC_MONO_STACK,
    },
}


def svg_faces_for_theme(theme: str) -> tuple[str, ...]:
    """The :data:`_FACES` keys to embed for `theme` (``"corporate"`` or ``"academic"``).

    Unknown theme names fall back to ``"corporate"`` rather than raising, so
    a typo degrades to the current default look instead of crashing a render.
    """
    return tuple(THEMES.get(theme, THEMES["corporate"])["faces"])  # type: ignore[return-value]


def chrome_stack_for_theme(theme: str) -> str:
    """The CSS font-family stack for title/body chrome text under `theme`."""
    return str(THEMES.get(theme, THEMES["corporate"])["chrome_stack"])


def mono_stack_for_theme(theme: str) -> str:
    """The CSS font-family stack for tick/numeric-label text under `theme`."""
    return str(THEMES.get(theme, THEMES["corporate"])["mono_stack"])


def font_path(key: str, *, woff2: bool = False) -> Path:
    """Absolute path to one bundled font face, TTF by default."""
    face = _FACES[key]
    return FONTS_DIR / (face["woff2"] if woff2 else face["ttf"])


@functools.cache
def _data_uri(key: str) -> str:
    path = font_path(key, woff2=True)
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:font/woff2;base64,{encoded}"


@functools.cache
def embedded_font_css(keys: tuple[str, ...] = DEFAULT_SVG_FACES) -> str:
    """``@font-face`` rules embedding the given faces as base64 WOFF2 data
    URIs -- fully self-contained, no network fetch, no reliance on the
    viewer having Roboto installed. Cached: the base64 encode only happens
    once per face per process.
    """
    rules = []
    for key in keys:
        face = _FACES[key]
        rules.append(
            "@font-face{"
            f"font-family:'{face['family']}';"
            f"font-style:{face['style']};"
            f"font-weight:{face['weight']};"
            "font-display:swap;"
            f"src:url({_data_uri(key)}) format('woff2');"
            "}"
        )
    return "".join(rules)


def svg_font_defs(keys: tuple[str, ...] = DEFAULT_SVG_FACES) -> str:
    """A ``<defs><style>...</style></defs>`` block embedding `keys`, ready to
    splice right after an SVG's opening tag (see :func:`scripts._svg.svg_open`).
    """
    return f"<defs><style>{embedded_font_css(keys)}</style></defs>"


def web_font_faces_css(url_prefix: str, keys: tuple[str, ...] = tuple(_FACES)) -> str:
    """``@font-face`` rules pointing at `url_prefix`-served WOFF2 files
    (self-hosted, no Google Fonts CDN) -- for the Studio web app, where the
    browser fetches and caches each face once instead of paying the base64
    inlining cost on every page. Pair with a static-file mount at
    `url_prefix` serving :data:`FONTS_DIR` (see ``studio/app.py``).
    """
    rules = []
    for key in keys:
        face = _FACES[key]
        rules.append(
            "@font-face{"
            f"font-family:'{face['family']}';"
            f"font-style:{face['style']};"
            f"font-weight:{face['weight']};"
            "font-display:swap;"
            f"src:url('{url_prefix}/{face['woff2']}') format('woff2');"
            "}"
        )
    return "".join(rules)


_matplotlib_registered = False


def register_matplotlib() -> bool:
    """Register every bundled face with matplotlib's font manager and make
    Roboto/Roboto Serif/Roboto Mono the default sans/serif/monospace
    families, so matplotlib-based generators use the real bundled glyphs
    instead of whatever happens to be installed system-wide. Also sets
    ``svg.fonttype = "path"`` so any matplotlib SVG output bakes glyphs as
    vector paths -- correct on any viewer, with no font file needed at all.

    No-ops (returns False) if matplotlib is not installed -- this module
    must stay usable from the font-independent scripts/_svg.py path.
    Idempotent: safe to call on every render.
    """
    global _matplotlib_registered
    if _matplotlib_registered:
        return True
    try:
        import matplotlib as mpl
        from matplotlib import font_manager as fm
    except ImportError:
        return False

    for key in _FACES:
        path = font_path(key)
        if path.exists():
            fm.fontManager.addfont(str(path))

    mpl.rcParams["font.family"] = "sans-serif"
    mpl.rcParams["font.sans-serif"] = ["Roboto", "DejaVu Sans"]
    mpl.rcParams["font.serif"] = ["Roboto Serif", "DejaVu Serif"]
    mpl.rcParams["font.monospace"] = ["Roboto Mono", "DejaVu Sans Mono"]
    mpl.rcParams["svg.fonttype"] = "path"
    _matplotlib_registered = True
    return True


# ``resvg_py.svg_to_bytes(..., font_dirs=RESVG_FONT_DIRS)`` -- passed on each
# call (resvg has no persistent global font database to register into, unlike
# the vl_convert rasteriser this replaced). Covers faces that are registered
# for matplotlib/the web app but never embedded into every generated SVG
# (Roboto Serif -- see :data:`DEFAULT_SVG_FACES`); the embedded-font path
# already makes every generator's own render font-independent without this.
RESVG_FONT_DIRS: tuple[str, ...] = (str(FONTS_DIR),)


def register_all() -> None:
    """Register the bundled fonts with every renderer available in the
    current environment. Safe to call unconditionally and repeatedly (each
    integration is independently idempotent and no-ops if its library isn't
    installed) -- the natural place to call this is once at the top of
    :func:`sprezzature_figures.make_figure.make_figure`.
    """
    register_matplotlib()


def available_faces() -> Sequence[str]:
    """Face keys whose bundled font file actually exists on disk (mostly a
    guard for partial/broken installs -- normally all six)."""
    return tuple(key for key in _FACES if font_path(key).exists())
