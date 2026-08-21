#!/usr/bin/env python3
"""
render_diagram
==============

Rasterise a *declarative graphical source* to an image for the
**Ralph Eyeball Loop** — the render → look → refine cycle documented in
``references/ralph-eyeball-loop.md``. The loop needs one thing this
script provides: turn a text source you can edit (a TikZ figure, a
Mermaid diagram, a raw SVG) into a PNG the agent can actually *look*
at, then critique, then edit the **original source**, then re-render.

Three source kinds, detected automatically from the file (you never
pass the kind: ``<svg>`` is svg, a LaTeX preamble is tikz, a ``graph``
/ ``%%{init}`` header is mermaid):

* ``tikz``    — a LaTeX / TikZ figure. Compiled with ``tectonic`` (a
  single-binary TeX engine) when present, else ``pdflatex`` / ``latexmk``,
  then rasterised from PDF with ``pdftoppm`` (poppler) or ImageMagick.
* ``mermaid`` — a Mermaid diagram. Rendered with ``mmdc`` (mermaid-cli).
* ``svg``     — a raw, hand-authored SVG document. Rasterised with
  ``rsvg-convert`` (librsvg) or ImageMagick. Every chart this package's
  own catalogue produces is already this kind; this is also the kind for
  a smoothing filter, arrowhead markers, or a gradient a diagram needs.

Vega-Lite/Vega specs are not a source kind here: this package no longer
renders Vega anywhere (the 124-kind chart catalogue moved to
hand-authored SVG; see ``references/figure-catalog.md``). A caller with
an existing Vega spec must convert or re-author it as TikZ, Mermaid, or
raw SVG before handing it to this renderer.

House style, by default: every kind is themed from the **canonical
sprezzature-colors palette** (``sprezzature-colors/references/palette.csv``, the same
tokens documented at <https://harchaoui.org/warith/colors/>) via
:mod:`_style`. TikZ gets a ``\\definecolor`` preamble of the base hues;
Mermaid gets an injected ``%%{init}%%`` theme. You can always edit the
colors afterwards: the palette is the *first* choice, not a lock-in.

Background is selectable per the embedding context:
``--background white`` (drop onto a light page), ``--background
transparent`` (overlay / dark page), ``--background dark`` (house dark
canvas), or an explicit ``#RRGGBB``. ``auto`` follows ``--dark``.

Usage
-----
::

    # A TikZ figure, palette-themed, tight-cropped PNG
    python render_diagram.py diagram.tex --out diagram.png

    # A Mermaid flowchart
    python render_diagram.py flow.mmd --background transparent --out flow.png

    # A raw SVG, rasterised to PNG
    python render_diagram.py fig.svg --background white --out fig.png

    # See the palette-themed source without rendering (no toolchain needed)
    python render_diagram.py diagram.tex --dry-run

Notes
-----
* Python 3.10+.
* TikZ:    a TeX engine — ``tectonic`` (recommended) or a TeX Live
  ``pdflatex`` — plus ``pdftoppm`` (poppler) or ``magick`` for PNG.
* Mermaid: ``npm install -g @mermaid-js/mermaid-cli`` (provides ``mmdc``).
  Each missing tool fails loud with an install hint; nothing is silent.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _argparse import make_parser  # noqa: E402
from _style import load_palette, load_semantic_palette  # noqa: E402


# ------------------------------------------------------------------
# House canvas tokens — mirror the house-style background / foreground
# constants so TikZ and Mermaid share the same palette as everything
# else. Kept as small local constants so this module stays cheap to
# import.
# ------------------------------------------------------------------
_LIGHT_BG = "#FFFFFF"
_DARK_BG = "#1D1D1F"
_LIGHT_FG = "#1D1D1F"
_DARK_FG = "#F5F5F7"

#: Source kinds this renderer understands.
KINDS = ("tikz", "mermaid", "svg")


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    """Return the argparse parser for the script."""
    parser = make_parser(
        prog="render_diagram",
        description=(
            "Rasterise a graphical source (TikZ, Mermaid, or raw SVG) to a "
            "PNG for the Ralph Eyeball Loop: render -> look -> edit the "
            "source -> re-render. The kind is detected automatically from "
            "the file; you never pass it. Palette-themed from "
            "sprezzature-colors; background is white / transparent / dark "
            "selectable."
        ),
        epilog=(
            "Auto-routed by content: \\documentclass / tikzpicture -> tikz "
            "(tectonic/pdflatex + pdftoppm/magick); graph / %%{init} -> "
            "mermaid (mmdc); <svg> -> svg (rsvg-convert / magick)."
        ),
    )
    parser.add_argument("source", help="Input source file (.tex, .mmd, .svg).")
    parser.add_argument("--out", default=None,
                        help="Output image path. Required unless --dry-run.")
    parser.add_argument("--background", default="auto",
                        help='Canvas background: "white", "transparent", "dark", '
                             '"auto" (follow --dark), or an explicit #RRGGBB.')
    parser.add_argument("--dark", action="store_true",
                        help="Use the dark-mode house canvas / foreground.")
    parser.add_argument("--dpi", type=int, default=300,
                        help="TikZ PDF->PNG rasterisation density. Default: 300.")
    parser.add_argument("--no-theme", action="store_true",
                        help="Do not inject the sprezzature-colors palette (render the source verbatim).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the palette-themed source and exit (no toolchain needed).")
    return parser


# ------------------------------------------------------------------
# Kind detection
# ------------------------------------------------------------------
def detect_kind(path: str, text: str) -> str:
    """Infer the source kind from a file path, then its content.

    Parameters
    ----------
    path : str
        Source filename; the extension is checked first.
    text : str
        Source body, used as a fallback when the extension is ambiguous.

    Returns
    -------
    str
        One of :data:`KINDS`.

    Raises
    ------
    SystemExit
        When neither the extension nor the content identifies a kind.
    """
    suffix = "".join(Path(path).suffixes).lower()
    if suffix.endswith((".tex", ".tikz")):
        return "tikz"
    if suffix.endswith((".mmd", ".mermaid")):
        return "mermaid"
    if suffix.endswith(".svg"):
        return "svg"
    # No decisive extension — route on the content. The three formats are
    # syntactically distinct, so a first-token sniff is unambiguous: an XML
    # document is SVG, a LaTeX preamble is TikZ, a graph keyword is Mermaid.
    head = text.lstrip("﻿ \t\r\n")
    if head[:6].lower().startswith(("<?xml", "<svg")) or "<svg" in head[:400].lower():
        return "svg"
    if "\\documentclass" in head[:400] or "\\begin{tikzpicture}" in text:
        return "tikz"
    if head.startswith("%%{init") or _looks_like_mermaid(head):
        return "mermaid"
    raise SystemExit(
        f"Could not detect the source kind of {path!r} from its extension or "
        "content (expected <svg>=svg, \\documentclass/tikzpicture=tikz, or "
        "graph/%%{init}=mermaid)."
    )


def _looks_like_mermaid(head: str) -> bool:
    """Return True when the first line opens a known Mermaid diagram type."""
    first = head.splitlines()[0].strip() if head.splitlines() else ""
    starters = (
        "graph ", "flowchart ", "sequenceDiagram", "classDiagram", "stateDiagram",
        "erDiagram", "gantt", "pie", "journey", "gitGraph", "mindmap", "timeline",
        "quadrantChart", "xychart", "C4Context",
    )
    return first.startswith(starters)


# ------------------------------------------------------------------
# Background resolution
# ------------------------------------------------------------------
def resolve_background(background: str, dark: bool) -> Optional[str]:
    """Resolve the ``--background`` flag to a hex string or ``None``.

    Parameters
    ----------
    background : str
        ``"white"``, ``"transparent"``, ``"dark"``, ``"auto"``, or a
        literal ``#RRGGBB``.
    dark : bool
        Whether the dark-mode house canvas is active (used by ``auto``).

    Returns
    -------
    str or None
        A hex color, or ``None`` for a transparent canvas.

    Raises
    ------
    SystemExit
        On an unrecognised value.
    """
    value = background.strip().lower()
    if value == "transparent":
        return None
    if value == "white":
        return "#FFFFFF"
    if value == "dark":
        return _DARK_BG
    if value == "auto":
        return _DARK_BG if dark else _LIGHT_BG
    if background.startswith("#") and len(background) in (4, 7):
        return background
    raise SystemExit(
        f"Unrecognised --background {background!r}. "
        "Use white | transparent | dark | auto | #RRGGBB."
    )


# ------------------------------------------------------------------
# Palette theming — TikZ
# ------------------------------------------------------------------
def tikz_color_preamble(dark: bool) -> str:
    """Build a ``\\definecolor`` block for every base palette hue.

    Each base color ``Red`` becomes ``\\definecolor{sprezzatureRed}{HTML}{FF3B30}``
    so a TikZ figure can reach for ``sprezzatureRed``, ``sprezzatureBlue``, … and stay
    on the house palette. Also defines ``sprezzatureFg`` (default draw color) and
    ``sprezzatureBg`` from the active canvas.

    Parameters
    ----------
    dark : bool
        Select the dark-mode foreground / background.

    Returns
    -------
    str
        LaTeX ``\\definecolor`` lines, newline-terminated.
    """
    lines: List[str] = []
    for name, hexv in load_palette().items():
        lines.append(f"\\definecolor{{sprezzature{name}}}{{HTML}}{{{hexv.lstrip('#').upper()}}}")
    fg = _DARK_FG if dark else _LIGHT_FG
    bg = _DARK_BG if dark else _LIGHT_BG
    lines.append(f"\\definecolor{{sprezzatureFg}}{{HTML}}{{{fg.lstrip('#').upper()}}}")
    lines.append(f"\\definecolor{{sprezzatureBg}}{{HTML}}{{{bg.lstrip('#').upper()}}}")
    return "\n".join(lines) + "\n"


def wrap_tikz_document(source: str, dark: bool, theme: bool) -> str:
    """Wrap a bare TikZ fragment in a compilable ``standalone`` document.

    A source that already declares ``\\documentclass`` is returned
    untouched (the author owns the full document, including its colors).
    Otherwise the fragment is wrapped in the ``standalone`` class with the
    xcolor + tikz packages and — unless ``theme`` is False — the
    sprezzature-colors ``\\definecolor`` preamble and ``sprezzatureFg`` default pen.

    Parameters
    ----------
    source : str
        A ``\\begin{tikzpicture}…\\end{tikzpicture}`` block, or looser TikZ
        commands to be wrapped in one.
    dark : bool
        Select the dark-mode canvas.
    theme : bool
        Inject the sprezzature-colors preamble when True.

    Returns
    -------
    str
        A complete LaTeX document ready for ``tectonic`` / ``pdflatex``.
    """
    if "\\documentclass" in source:
        return source

    body = source if "\\begin{tikzpicture}" in source else (
        "\\begin{tikzpicture}\n" + source.strip() + "\n\\end{tikzpicture}"
    )
    preamble = tikz_color_preamble(dark) if theme else ""
    default_pen = "\\tikzset{every picture/.style={color=sprezzatureFg}}\n" if theme else ""
    return (
        "\\documentclass[border=6pt]{standalone}\n"
        "\\usepackage{xcolor}\n"
        "\\usepackage{tikz}\n"
        "\\usetikzlibrary{arrows.meta,positioning,shapes.geometric,calc}\n"
        f"{preamble}"
        f"{default_pen}"
        "\\begin{document}\n"
        f"{body}\n"
        "\\end{document}\n"
    )


# ------------------------------------------------------------------
# Palette theming — Mermaid
# ------------------------------------------------------------------
def mermaid_init_directive(dark: bool, background: Optional[str]) -> str:
    """Build a Mermaid ``%%{init}%%`` theme directive from the palette.

    Maps the base palette onto Mermaid's ``base`` theme variables: soft
    light-variant fills, saturated borders, gray edges, Roboto type. Keeps
    the diagram on-brand without hand-editing every node.

    Parameters
    ----------
    dark : bool
        Select the dark-mode foreground.
    background : str or None
        Resolved canvas background; ``None`` (transparent) is left to the
        renderer's ``-b`` flag rather than baked into the theme.

    Returns
    -------
    str
        A single ``%%{init: {...}}%%`` line (newline-terminated).
    """
    sem = load_semantic_palette()
    fg = _DARK_FG if dark else _LIGHT_FG

    def _light(name: str, fallback: str) -> str:
        return (sem.get(name, {}).get("light") or fallback)

    def _hex(name: str, fallback: str) -> str:
        return (sem.get(name, {}).get("hex") or fallback)

    theme_vars: Dict[str, str] = {
        "primaryColor": _light("Blue", "#CCE4FF"),
        "primaryBorderColor": _hex("Blue", "#007AFF"),
        "primaryTextColor": fg,
        "secondaryColor": _light("Green", "#D4F5D9"),
        "tertiaryColor": _light("Purple", "#EFDCF8"),
        "lineColor": _hex("Gray", "#8E8E93"),
        "fontFamily": "Roboto, system-ui, sans-serif",
    }
    if background:
        theme_vars["background"] = background
    init = {"theme": "base", "themeVariables": theme_vars}
    return "%%{init: " + json.dumps(init, ensure_ascii=False) + "}%%\n"


def inject_mermaid_theme(source: str, dark: bool, background: Optional[str], theme: bool) -> str:
    """Prepend the palette ``%%{init}%%`` directive unless one is present.

    Parameters
    ----------
    source : str
        Raw Mermaid diagram text.
    dark : bool
        Select the dark-mode foreground.
    background : str or None
        Resolved canvas background.
    theme : bool
        Inject the directive when True and the source lacks its own.

    Returns
    -------
    str
        The (possibly themed) Mermaid source.
    """
    if not theme or source.lstrip().startswith("%%{init"):
        return source
    return mermaid_init_directive(dark, background) + source


# ------------------------------------------------------------------
# Toolchain guard
# ------------------------------------------------------------------
def _require(tool: str, hint: str) -> str:
    """Return the resolved path to ``tool`` or fail loud with ``hint``.

    Parameters
    ----------
    tool : str
        Executable name to look up on ``PATH``.
    hint : str
        Install guidance shown when the tool is missing.

    Returns
    -------
    str
        Absolute path to the executable.

    Raises
    ------
    SystemExit
        When the tool is not on ``PATH``.
    """
    found = shutil.which(tool)
    if found is None:
        raise SystemExit(f"Required tool {tool!r} not found on PATH.\n{hint}")
    return found


# ------------------------------------------------------------------
# Renderers
# ------------------------------------------------------------------
def render_tikz(source: str, out: str, dpi: int, background: Optional[str]) -> None:
    """Compile a TikZ document and rasterise the PDF to PNG.

    Prefers ``tectonic`` (self-contained), falling back to ``pdflatex`` /
    ``latexmk``. Rasterises with ImageMagick when a transparent background
    is requested (poppler's ``pdftoppm`` cannot emit alpha), otherwise
    ``pdftoppm`` for a crisp flat PNG.

    Parameters
    ----------
    source : str
        A complete LaTeX document (see :func:`wrap_tikz_document`).
    out : str
        Output PNG path.
    dpi : int
        Rasterisation density.
    background : str or None
        ``None`` renders a transparent PNG; a hex flattens onto that color.

    Raises
    ------
    SystemExit
        When no TeX engine or rasteriser is available, or compilation fails.
    """
    with tempfile.TemporaryDirectory() as tmp:
        tex = Path(tmp) / "figure.tex"
        tex.write_text(source, encoding="utf-8")

        if shutil.which("tectonic"):
            cmd = ["tectonic", "--outdir", tmp, "--keep-logs", str(tex)]
        elif shutil.which("latexmk"):
            cmd = ["latexmk", "-pdf", "-interaction=nonstopmode", f"-outdir={tmp}", str(tex)]
        else:
            engine = _require(
                "pdflatex",
                "Install a TeX engine: tectonic (brew install tectonic — see "
                "https://brew.sh) or TeX Live (apt install texlive-latex-extra).",
            )
            cmd = [engine, "-interaction=nonstopmode", "-halt-on-error",
                   "-output-directory", tmp, str(tex)]

        proc = subprocess.run(cmd, capture_output=True, text=True)
        pdf = Path(tmp) / "figure.pdf"
        if proc.returncode != 0 or not pdf.is_file():
            raise SystemExit(
                "TikZ compilation failed:\n" + (proc.stdout or "")[-2000:] + (proc.stderr or "")[-500:]
            )

        _rasterise_pdf(pdf, Path(out), dpi, background)


def _rasterise_pdf(pdf: Path, out: Path, dpi: int, background: Optional[str]) -> None:
    """Rasterise a single-page PDF to PNG at ``dpi``.

    Uses ImageMagick for transparency, poppler's ``pdftoppm`` otherwise.
    """
    magick = shutil.which("magick") or shutil.which("convert")
    if background is None:
        if magick is None:
            raise SystemExit(
                "A transparent TikZ PNG needs ImageMagick.\n"
                "  brew install imagemagick  (https://brew.sh)  |  apt install imagemagick"
            )
        cmd = [magick, "-density", str(dpi), str(pdf), "-background", "none",
               "-trim", "+repage", str(out)]
        _run_or_die(cmd, "ImageMagick rasterisation failed")
        return

    if shutil.which("pdftoppm"):
        stem = str(out.with_suffix(""))
        cmd = ["pdftoppm", "-png", "-r", str(dpi), "-singlefile", str(pdf), stem]
        _run_or_die(cmd, "pdftoppm rasterisation failed")
        return

    if magick is not None:
        cmd = [magick, "-density", str(dpi), str(pdf), "-background",
               background, "-flatten", "-trim", "+repage", str(out)]
        _run_or_die(cmd, "ImageMagick rasterisation failed")
        return

    raise SystemExit(
        "No PDF rasteriser found.\n"
        "  brew install poppler   (pdftoppm)   |  apt install poppler-utils\n"
        "  brew install imagemagick            |  apt install imagemagick"
    )


def render_mermaid(source: str, out: str, background: Optional[str]) -> None:
    """Render a Mermaid diagram to PNG with ``mmdc``.

    Parameters
    ----------
    source : str
        The (themed) Mermaid source.
    out : str
        Output PNG path.
    background : str or None
        ``None`` maps to ``mmdc -b transparent``; a hex is passed through.

    Raises
    ------
    SystemExit
        When ``mmdc`` is not installed or rendering fails.
    """
    mmdc = _require(
        "mmdc",
        "Install mermaid-cli: npm install -g @mermaid-js/mermaid-cli",
    )
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "diagram.mmd"
        src.write_text(source, encoding="utf-8")
        cmd = [mmdc, "-i", str(src), "-o", out, "-b",
               ("transparent" if background is None else background)]
        _run_or_die(cmd, "Mermaid (mmdc) rendering failed")


def render_svg(source: str, out: str, background: Optional[str]) -> None:
    """Rasterise a raw, hand-authored SVG document to PNG.

    Every chart this package's own catalogue produces is already this
    kind. When a diagram needs something a declarative grammar cannot
    express — a smoothing filter, arrowhead markers, a gradient — author
    the SVG by hand and rasterise it here so it still goes through the
    render → look → refine loop. Prefers ``rsvg-convert`` (librsvg,
    faithful filter support), then ImageMagick.

    Parameters
    ----------
    source : str
        The SVG document text.
    out : str
        Output PNG path.
    background : str or None
        ``None`` keeps the SVG transparent; a hex flattens onto that color.

    Raises
    ------
    SystemExit
        When no SVG rasteriser is available or rasterisation fails.
    """
    with tempfile.TemporaryDirectory() as tmp:
        svg = Path(tmp) / "figure.svg"
        svg.write_text(source, encoding="utf-8")
        if shutil.which("rsvg-convert"):
            cmd = ["rsvg-convert", "-o", out]
            if background is not None:
                cmd += ["--background-color", background]
            cmd.append(str(svg))
            _run_or_die(cmd, "rsvg-convert rasterisation failed")
            return
        magick = shutil.which("magick") or shutil.which("convert")
        if magick is not None:
            bg = "none" if background is None else background
            _run_or_die([magick, "-background", bg, str(svg), out],
                        "ImageMagick SVG rasterisation failed")
            return
        raise SystemExit(
            "No SVG rasteriser found.\n"
            "  brew install librsvg (rsvg-convert)  |  apt install librsvg2-bin\n"
            "  brew install imagemagick             |  apt install imagemagick"
        )


def _run_or_die(cmd: List[str], message: str) -> None:
    """Run ``cmd``; raise :class:`SystemExit` with ``message`` on failure."""
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"{message}:\n{(proc.stderr or proc.stdout or '')[-1500:]}")


# ------------------------------------------------------------------
# Theming dispatch (shared by --dry-run and the real render)
# ------------------------------------------------------------------
def themed_source(kind: str, raw: str, dark: bool, background: Optional[str], theme: bool) -> str:
    """Return the palette-themed source for a kind (SVG is passed through).

    Parameters
    ----------
    kind : str
        One of :data:`KINDS`.
    raw : str
        The raw source text.
    dark : bool
        Dark-mode canvas.
    background : str or None
        Resolved background (used by the Mermaid theme).
    theme : bool
        Inject the palette when True.

    Returns
    -------
    str
        The themed source (or ``raw`` for SVG — a hand-authored figure's
        colors are already baked into its markup).
    """
    if kind == "tikz":
        return wrap_tikz_document(raw, dark, theme)
    if kind == "mermaid":
        return inject_mermaid_theme(raw, dark, background, theme)
    return raw


# ------------------------------------------------------------------
# main
# ------------------------------------------------------------------
def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point."""
    args = build_parser().parse_args(argv)

    src_path = Path(args.source)
    if not src_path.is_file():
        print(f"No such source file: {args.source}", file=sys.stderr)
        return 2
    raw = src_path.read_text(encoding="utf-8")

    kind = detect_kind(args.source, raw)
    background = resolve_background(args.background, args.dark)
    theme = not args.no_theme

    prepared = themed_source(kind, raw, args.dark, background, theme)

    if args.dry_run:
        print(prepared)
        return 0

    if not args.out:
        print("--out is required unless --dry-run.", file=sys.stderr)
        return 2

    if kind == "tikz":
        render_tikz(prepared, args.out, args.dpi, background)
    elif kind == "mermaid":
        render_mermaid(prepared, args.out, background)
    else:  # svg
        render_svg(prepared, args.out, background)

    print(f"wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
