"""
fonts — the project's typeface sources: Roboto/Roboto Serif/Roboto Mono (the
default **corporate** theme) and Latin Modern Roman/Mono (the **academic**
theme, the face LaTeX documents use by default: GUST e-foundry's free
extension of Donald Knuth's Computer Modern), bundled as TTF/WOFF2 font
files so every figure and the Studio web app render the house typography
identically regardless of what is, or is not, installed on the host
machine. Without this, writing ``"Roboto, sans-serif"`` in a stylesheet
only *hopes* the browser or renderer happens to have Roboto installed; here
the font itself is registered or embedded directly, so the figure always
carries its own typeface with it.

Font files live under ``assets/fonts/`` in the source tree and ship in the
wheel as the sibling package ``sprezzature_figures_fonts`` (same pattern as
``scripts/`` becoming ``sprezzature_figures_scripts``). Sources: the
OFL-licensed Google Fonts repository for Roboto (see the ``OFL-*.txt``
files), and GUST e-foundry's Latin Modern under the GUST Font License /
LPPL (see ``GUST-FONT-LICENSE-LatinModern.txt``). Both licenses permit
bundling and redistribution, which is why these fonts, and not some other
free alternative, were chosen.

This module is deliberately **stdlib-only** at import time, meaning it
imports nothing beyond Python's own standard library (only
``base64``/``functools``/``pathlib``, no third-party package). That matters
because ``scripts/_svg.py`` must stay importable even without the
``dataviz`` extra installed, and this module is one of the things it
depends on. The rasteriser, the component
that turns an SVG into pixels (``resvg_py``), keeps no persistent
font-directory registration of its own; callers pass
:data:`RESVG_FONT_DIRS` as the ``font_dirs`` keyword on each
``svg_to_bytes`` call instead.

Author
------
Warith HARCHAOUI <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import base64
import functools
from collections.abc import Sequence
from pathlib import Path
from typing import Any

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
# Roboto Serif was briefly cut from the wheel to save 12.2 MB, which made this
# stack resolve to Georgia in every installed copy while the module went on
# offering it. It ships again: the suite's typography rule is three Roboto --
# sans, serif, mono -- and a rule that holds only in a source checkout is not
# a rule. The size is the price of the rule, paid on purpose.
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

#: Every face key this module offers. The wheel ships all of them: see
#: ``pyproject.toml``'s font package-data globs, and
#: ``tests/test_the_package_serves_only_fonts_it_ships.py``, which reads those
#: globs and fails if any face here would be left out of a build.
#:
#: That test exists because the two silently disagreed at 2.6.0. The globs
#: were narrowed to drop Roboto Serif; ``_FACES`` kept listing it; a source
#: checkout has every file on disk regardless, so nothing local could tell.
#: The gap surfaced downstream, in another package's CI, as a bare
#: ``FileNotFoundError`` naming a filename and no reason.
OFFERED_FACES: tuple[str, ...] = tuple(_FACES)


class MissingFaceError(FileNotFoundError):
    """A face named in :data:`_FACES` has no font file in *this* install.

    Every offered face ships (:data:`OFFERED_FACES`), so reaching this means
    the install is damaged rather than merely partial -- and the message says
    so. Subclasses :class:`FileNotFoundError`, which is what the failure
    surfaced as before, so existing handlers keep working; what changed is
    that the text names the *face key* that asked and what to do about it,
    where the bare version offered only a filename.
    """


# The faces figures actually set as font-family (see _svg.py svg_open()).
# Roboto Serif ships but is not embedded by default: it is a publication/
# editorial option (references/publication-presets.md) that no generator sets
# under the corporate theme, and every face listed here lands as base64 in
# every SVG produced.
DEFAULT_SVG_FACES: tuple[str, ...] = ("sans", "mono")

#: theme name -> (embedded SVG faces, chrome-text stack, tick/value-label
#: stack). ``THEMES["corporate"]`` reproduces :data:`DEFAULT_SVG_FACES` /
#: :data:`SANS_STACK` / :data:`MONO_STACK` exactly, so selecting it is a
#: no-op relative to today's default render. See :func:`svg_faces_for_theme`.
# `Any`, not `object`: these inner dicts are deliberately mixed (a tuple of
# face keys next to plain strings), and `object` forbids every operation on
# the values, which is what the `type: ignore` below was papering over.
THEMES: dict[str, dict[str, Any]] = {
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
    return tuple(THEMES.get(theme, THEMES["corporate"])["faces"])


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
    try:
        payload = path.read_bytes()
    except FileNotFoundError as exc:
        raise MissingFaceError(_missing_face_message(key, path)) from exc
    encoded = base64.b64encode(payload).decode("ascii")
    return f"data:font/woff2;base64,{encoded}"


def _missing_face_message(key: str, path: Path) -> str:
    """Why `key` has no file here, in the terms the caller needs to act on."""
    return (
        f"font face {key!r} needs {path.name}, which is not at {path.parent}. "
        "Every face sprezzature-figures offers ships in its wheel, so this install "
        f"is incomplete rather than merely missing an extra -- reinstall it. "
        f"Faces offered: {', '.join(OFFERED_FACES)}."
    )


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


def web_font_faces_css(url_prefix: str, keys: tuple[str, ...] | None = None) -> str:
    """``@font-face`` rules pointing at `url_prefix`-served WOFF2 files
    (self-hosted, no Google Fonts CDN) -- for the Studio web app, where the
    browser fetches and caches each face once instead of paying the base64
    inlining cost on every page. Pair with a static-file mount at
    `url_prefix` serving :data:`FONTS_DIR` (see ``studio/app.py``).

    `keys` defaults to :func:`available_faces`, i.e. whatever this install
    actually has, rather than to every key in :data:`_FACES`. The difference is
    not cosmetic: the mount serves :data:`FONTS_DIR`, so a rule for a face the
    install lacks is a URL that 404s -- and a browser that cannot fetch a
    ``@font-face`` source silently moves on to the next family in the stack.
    With the old default, every page of an installed Studio linked the four
    Roboto Serif files the wheel leaves out, and drew in Georgia without a
    word. Deriving from disk is also correct in a source checkout, where those
    four files are present and get served as before.
    """
    rules = []
    for key in tuple(available_faces()) if keys is None else keys:
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


# ``resvg_py.svg_to_bytes(..., font_dirs=RESVG_FONT_DIRS)`` -- passed on each
# call, because resvg keeps no persistent global font database to register
# into. It lets the rasteriser find any face sitting in this directory -- all
# of :data:`OFFERED_FACES`, including the Roboto Serif that no generator
# embeds by default; the embedded-font path already makes every generator's
# own render font-independent without it.
RESVG_FONT_DIRS: tuple[str, ...] = (str(FONTS_DIR),)


def available_faces() -> Sequence[str]:
    """Face keys whose bundled font file actually exists on disk.

    Expect :data:`OFFERED_FACES` -- all of them, from a source checkout and
    from an installed copy alike, since the wheel ships every face offered.
    Anything short of that is the damaged install this guards against, and it
    is why the function reads the directory instead of trusting the table.
    """
    return tuple(key for key in _FACES if font_path(key).exists())
