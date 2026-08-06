"""
fonts — the project's single Roboto source: Roboto, Roboto Serif and Roboto
Mono, bundled as variable TTF/WOFF2 files so every figure and the Studio web
app render the house typography identically regardless of what is (or is
not) installed on the host machine. No more hoping ``"Roboto, sans-serif"``
resolves to the real thing -- the font is registered / embedded directly.

Font files live under ``assets/fonts/`` in the source tree and ship in the
wheel as the sibling package ``sprezzature_figures_fonts`` (same pattern as
``scripts/`` -> ``sprezzature_figures_scripts``). Source: the OFL-licensed
Google Fonts repository (see the ``OFL-*.txt`` files alongside the fonts).

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
    (p for p in (_pkg_parent / "assets" / "fonts", _pkg_parent / "sprezzature_figures_fonts") if p.is_dir()),
    _pkg_parent / "assets" / "fonts",
)

# CSS font stacks every generator / the web app should use -- Roboto first,
# a close system fallback second (only exercised in the vanishingly rare
# case the bundled font file itself failed to load).
SANS_STACK = "Roboto, system-ui, sans-serif"
SERIF_STACK = "Roboto Serif, Georgia, serif"
MONO_STACK = "Roboto Mono, ui-monospace, monospace"

# key -> (ttf filename, woff2 filename, CSS font-family, font-style, font-weight range)
_FACES: dict[str, dict[str, str]] = {
    "sans": {
        "ttf": "Roboto-Variable.ttf", "woff2": "Roboto-Variable.woff2",
        "family": "Roboto", "style": "normal", "weight": "100 900",
    },
    "sans_italic": {
        "ttf": "Roboto-Italic-Variable.ttf", "woff2": "Roboto-Italic-Variable.woff2",
        "family": "Roboto", "style": "italic", "weight": "100 900",
    },
    "serif": {
        "ttf": "RobotoSerif-Variable.ttf", "woff2": "RobotoSerif-Variable.woff2",
        "family": "Roboto Serif", "style": "normal", "weight": "100 900",
    },
    "serif_italic": {
        "ttf": "RobotoSerif-Italic-Variable.ttf", "woff2": "RobotoSerif-Italic-Variable.woff2",
        "family": "Roboto Serif", "style": "italic", "weight": "100 900",
    },
    "mono": {
        "ttf": "RobotoMono-Variable.ttf", "woff2": "RobotoMono-Variable.woff2",
        "family": "Roboto Mono", "style": "normal", "weight": "100 900",
    },
    "mono_italic": {
        "ttf": "RobotoMono-Italic-Variable.ttf", "woff2": "RobotoMono-Italic-Variable.woff2",
        "family": "Roboto Mono", "style": "italic", "weight": "100 900",
    },
}

# The two faces figures actually set as font-family (see _svg.py svg_open());
# Roboto Serif is a publication/editorial option (references/publication-
# presets.md) that no generator currently uses, so it is registered for
# matplotlib/the web app but never embedded into every generated SVG.
DEFAULT_SVG_FACES: tuple[str, ...] = ("sans", "mono")


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
