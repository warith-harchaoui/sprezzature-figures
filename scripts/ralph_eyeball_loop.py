#!/usr/bin/env python3
"""
ralph_eyeball_loop
==================

The **Ralph Eyeball Loop** — the universal visual-quality technique for the
``sprezzature-*`` repo. Render any visual-from-code artifact to a PNG, critique it
honestly, edit the source, and loop until satisfied.

The loop applies to every surface that produces a visual from code:

* **Web pages and GUI screens** — ``.html``, ``.htm`` (Chrome headless)
* **Mathematical figures** — ``.tex``, ``.tikz`` (TikZ via tectonic / pdflatex)
* **Hand-authored graphics, flow diagrams included** — ``.svg`` (rsvg-convert
  or ImageMagick); ``sprezzature-figures render flowchart`` draws the diagrams

Data viz is *one* application. A webpage, a UI component, an architecture
diagram all go through the same four-step cycle.

Two modes
---------
**Agent mode (default)**
    The Claude Code / OpenCode agent reads the rendered PNG with its own
    vision and fills in the assessment template.  No Ollama call.  This is
    the primary, recommended workflow when running inside Claude Code.

**Local mode** (``--local``)
    A fully offline alternative.  After rendering the PNG, the script calls
    ``qwen3-vl:8b`` (a vision-language model) to generate the critique
    automatically and pre-fill the assessment file.  No cloud API, no Claude
    Code session required. It works in any terminal once Ollama is running and
    the model is pulled.

    The call itself is never made directly: every LLM/VLM call across the
    ``sprezzature-*`` suite routes through ``best_engine_ai_helper.llm.chat``,
    which resolves the model and the backend (Ollama by default; OpenAI-
    compatible or LangChain are opt-in via ``SPREZZATURE_LLM_BACKEND``). This
    script only shapes the prompt and hands it a PNG; it never talks to
    Ollama's REST API itself.

    Pull the model once::

        ollama pull qwen3-vl:8b

The loop (both modes)
---------------------
1. **Render** — PNG at the deployment-context size / background.
2. **Look**   — agent or Ollama vision reads the PNG.
3. **Assess** — critique written to ``.private/ralph-loop/assessment-<hash>.md``
   (gitignored, never committed; extended each iteration).
4. **Edit**   — improve the *source* (never the PNG).
5. **Repeat** — re-run; a new iteration section is appended.  Stop when the
   Verdict box is checked.

Rendering toolchain per surface
---------------------------------
+--------------------+----------------------------------------------+-----------------------------+
| Surface            | Tool                                         | Install                     |
+====================+==============================================+=============================+
| HTML / JS page     | Headless Chrome (Google Chrome or Chromium)  | https://google.com/chrome   |
+--------------------+----------------------------------------------+-----------------------------+
| TikZ figure        | tectonic (preferred) or pdflatex + pdftoppm  | brew install tectonic       |
+--------------------+----------------------------------------------+-----------------------------+
| SVG graphic        | rsvg-convert (preferred) or magick           | brew install librsvg        |
+--------------------+----------------------------------------------+-----------------------------+
| Local critique     | qwen3-vl:8b, via best-engine-ai-helper       | ollama pull qwen3-vl:8b    |
+--------------------+----------------------------------------------+-----------------------------+

Run ``python ralph_eyeball_loop.py --install-tools`` to see what is missing
and the command that installs each tool.

Not to be confused with ``sprezzature_figures.editor.ralph``, the
FigurePlan-editing engine behind the editor's in-app copilot: same
render-critique-edit idea, different surface (any file on disk here, a
structured ``FigurePlan`` there).

Usage
-----
::

    # Agent mode — desktop (default 1440 × 900)
    python sprezzature-figures/scripts/ralph_eyeball_loop.py web/index.html

    # Agent mode — mobile
    python sprezzature-figures/scripts/ralph_eyeball_loop.py web/index.html --width 375 --height 812

    # Local mode — TikZ figure, dark canvas
    python sprezzature-figures/scripts/ralph_eyeball_loop.py figs/dag.tex --bg dark --dark --local

    # Local mode — SVG, transparent canvas
    python sprezzature-figures/scripts/ralph_eyeball_loop.py figs/flow.svg --bg transparent --local

    # Check the rendering toolchain, and print how to install what is missing
    python sprezzature-figures/scripts/ralph_eyeball_loop.py --install-tools

Notes
-----
* Assessment files are keyed by a stable 8-char MD5 of the *resolved* source
  path: the same source always maps to the same assessment slot. That is a
  slot, not a cache — the file is a journal and iterations accumulate in it.
  The cache is a separate thing, added 2026-10-31: the ``--local`` critique
  is memoized through ``wallet_helper`` on the PNG's bytes, the prompt and
  the model name, so re-running the loop on a figure nobody changed costs
  nothing instead of 95-120 s. ``--no-critique-cache`` asks again anyway.
* ``.private/`` is in the top-level ``.gitignore``; assessment files and
  rendered PNGs are never committed.
* For diagram surfaces (TikZ / SVG), rendering is delegated
  to ``render_diagram.py`` in the same directory.
* Python 3.10+.  No extra stdlib-beyond dependencies; rendering tools are
  checked and surfaced as loud errors when absent.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Optional

# Every LLM/VLM call across sprezzature-* routes through this one function —
# no script imports an Ollama/OpenAI/LangChain client directly. It resolves
# the backend and model tag from the SPREZZATURE_LLM_* environment variables
# (SPREZZATURE_LLM_BACKEND defaults to "ollama") and shapes the request the
# same way regardless of which backend answers it.
from best_engine_ai_helper.llm import chat as _llm_chat

# The critique above is the expensive part of this loop and it was paid for in
# full on every run, including the runs where the figure had not changed by a
# single pixel. `wallet_helper` is the suite's answer to precisely that:
# content-addressed memoization with cross-process single-flight. The key and
# the measurement are in `_vlm_critique`.
import wallet_helper as _wallet

# ---------------------------------------------------------------------------
# Paths — resolved at import time so the script works from any cwd
# ---------------------------------------------------------------------------
_SCRIPT_DIR: Path = Path(__file__).resolve().parent      # sprezzature-figures/scripts/
_FIGURES_ROOT: Path = _SCRIPT_DIR.parent                 # sprezzature-figures/ (this package's own root)
_RENDER_DIAGRAM: Path = _SCRIPT_DIR / "render_diagram.py"

# Gitignored output directory (covered by .private/ in the top-level .gitignore).
# This package ships standalone (its own repo, own .gitignore): the root for
# .private/ is this package's own root, not a parent monorepo. An earlier
# version of this file assumed the pre-extraction monorepo layout
# (sprezzature/sprezzature-figures/scripts/) and went one directory too far
# up, landing in the user's home directory instead of this repo.
#
# Installed from the wheel, the same parent is `site-packages/`: the loop
# wrote its PNGs, assessments and critique ledger into the interpreter's own
# tree, which may not even be writable. A clone is recognised by the
# `pyproject.toml` beside `scripts/` *that names this project*: the wheel
# of dash-bootstrap-components (pulled in by shapash) drops its own
# `pyproject.toml` at the top of site-packages, so a bare existence test
# reads every real install as a clone. Without our own, the output goes under
# the directory the loop was run from, like any other command's output.


def _is_our_clone(root: Path) -> bool:
    """True when `root` holds this project's own ``pyproject.toml``."""
    pyproject = root / "pyproject.toml"
    try:
        return 'name = "sprezzature-figures"' in pyproject.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False


def _loop_dir(figures_root: Path, cwd: Path) -> Path:
    """Where the loop writes: the clone's ``.private/``, else the cwd's."""
    root = figures_root if _is_our_clone(figures_root) else cwd
    return root / ".private" / "ralph-loop"


_PRIVATE_LOOP_DIR: Path = _loop_dir(_FIGURES_ROOT, Path.cwd())

# ---------------------------------------------------------------------------
# qwen3-vl:8b — the one authorized VLM for the whole sprezzature-* repo's
# --local critique mode. Reached exclusively via best_engine_ai_helper.llm.chat
# (imported above); this module never opens an HTTP connection to Ollama
# itself. _OLLAMA_URL below is used only in the human-readable error message
# when the backend is unreachable, not to make the call.
# ---------------------------------------------------------------------------
_VISION_MODEL: str = "qwen3-vl:8b"
_OLLAMA_URL: str = "http://localhost:11434/api/generate"

#: Headless Chrome refuses to make its window narrower than this (~500 px on
#: macOS/Linux). Below it, the page lays out at ~485 px and the screenshot
#: crops — a false-overflow trap. HTML renders clamp to this floor and warn.
_CHROME_MIN_VIEWPORT: int = 500

# ---------------------------------------------------------------------------
# Surface kinds
# ---------------------------------------------------------------------------
_KIND_HTML: str = "html"
_KIND_TIKZ: str = "tikz"
_KIND_SVG: str = "svg"

# Kinds delegated to render_diagram.py.
_DIAGRAM_KINDS: frozenset[str] = frozenset({_KIND_TIKZ, _KIND_SVG})

# Suffixes refused outright: no renderer here reads them, and the
# ``flowchart`` kind draws what they were written for.
_REFUSED_SUFFIXES: tuple[str, ...] = (".mmd", ".mermaid")

# Suffix → kind.
_SUFFIX_KIND: dict[str, str] = {
    ".tex":      _KIND_TIKZ,
    ".tikz":     _KIND_TIKZ,
    ".svg":      _KIND_SVG,
    ".html":     _KIND_HTML,
    ".htm":      _KIND_HTML,
}

# ---------------------------------------------------------------------------
# Tool definitions — one record per surface / dependency
# ---------------------------------------------------------------------------
# Each entry: display name, surface kind, description, brew package, manual
# URL, and the check.
# check_fn returns True when the tool is usable.
_TOOLS: list[dict] = [
    {
        "name": "Chrome / Chromium",
        "kind": _KIND_HTML,
        "description": "Headless browser for HTML/JS page screenshots.",
        "brew": "google-chrome",
        "manual": "https://www.google.com/chrome/",
        "check": lambda: _chrome_path() is not None,
    },
    {
        "name": "tectonic",
        "kind": _KIND_TIKZ,
        "description": "Self-contained TeX engine for TikZ figures (preferred).",
        "brew": "tectonic",
        "manual": "https://tectonic-typesetting.github.io/",
        "check": lambda: bool(shutil.which("tectonic")),
    },
    {
        "name": "pdftoppm (poppler)",
        "kind": _KIND_TIKZ,
        "description": "PDF → PNG rasteriser used after pdflatex/tectonic.",
        "brew": "poppler",
        "manual": "https://poppler.freedesktop.org/",
        "check": lambda: bool(shutil.which("pdftoppm")),
    },
    {
        "name": "rsvg-convert (librsvg)",
        "kind": _KIND_SVG,
        "description": "High-fidelity SVG → PNG rasteriser.",
        "brew": "librsvg",
        "manual": "https://wiki.gnome.org/Projects/LibRsvg",
        "check": lambda: bool(shutil.which("rsvg-convert")),
    },
    {
        "name": "ImageMagick",
        "kind": "fallback",
        "description": "Fallback rasteriser for SVG and TikZ when preferred tools are absent.",
        "brew": "imagemagick",
        "manual": "https://imagemagick.org/",
        "check": lambda: bool(shutil.which("magick") or shutil.which("convert")),
    },
    {
        "name": f"Ollama + {_VISION_MODEL}",
        "kind": "local-critique",
        "description": "Vision-language model for --local mode automated critique.",
        "brew": None,
        "manual": "https://ollama.com/",
        "check": lambda: _ollama_model_available(),
    },
]


# ---------------------------------------------------------------------------
# Tool helpers
# ---------------------------------------------------------------------------
def _chrome_path() -> Optional[str]:
    """Return the path to Chrome / Chromium, or None."""
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
    ]
    for c in candidates:
        p = Path(c)
        if p.is_file() and p.stat().st_mode & 0o111:
            return str(p)
        if shutil.which(c):
            return c
    return None


def _find_chrome() -> str:
    """Return the Chrome path, or raise SystemExit."""
    path = _chrome_path()
    if path is None:
        raise SystemExit(
            "ralph_eyeball_loop: Chrome / Chromium not found.\n"
            "  macOS : install Google Chrome — https://www.google.com/chrome/\n"
            "  Linux : apt install chromium-browser  |  snap install chromium"
        )
    return path


def _ollama_model_available() -> bool:
    """Return True when Ollama is reachable and the vision model is pulled."""
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
        model_names = [m.get("name", "") for m in data.get("models", [])]
        # Accept exact match or tag-prefix match (e.g. "qwen3-vl:8b" or
        # "qwen3-vl:8b-instruct-q4_K_M").
        prefix = _VISION_MODEL.split(":")[0]
        return any(_VISION_MODEL in n or n.startswith(prefix + ":") for n in model_names)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Tool check / install
# ---------------------------------------------------------------------------
def check_tools(verbose: bool = True) -> dict[str, bool]:
    """Print a table of tool installation status and return a name → bool dict.

    Parameters
    ----------
    verbose : bool
        Print the status table when True.

    Returns
    -------
    dict[str, bool]
        Tool display name → installed.
    """
    status: dict[str, bool] = {}
    col = 34
    if verbose:
        print(f"{'Tool':<{col}}  {'Surface':<16}  Status")
        print("-" * (col + 36))
    for tool in _TOOLS:
        try:
            ok = tool["check"]()
        except Exception:
            ok = False
        status[tool["name"]] = ok
        if verbose:
            mark = "✓" if ok else "✗"
            print(f"{tool['name']:<{col}}  {tool['kind']:<16}  {mark}  {tool['description']}")
    if verbose:
        print()
        missing = [t for t in _TOOLS if not status[t["name"]]]
        if missing:
            print("Missing tools:")
            for t in missing:
                if t["brew"]:
                    print(f"  brew install {t['brew']}   # or see: {t['manual'] or ''}")
                if t["name"].startswith("Ollama"):
                    print("  ollama serve   # start Ollama daemon")
                    print(f"  ollama pull {_VISION_MODEL}")
        else:
            print("All tools installed.")
    return status


def install_tools() -> None:
    """Report each tool: already there, or the command that installs it."""
    status = check_tools(verbose=False)
    for tool in _TOOLS:
        if status[tool["name"]]:
            print(f"  ✓ {tool['name']} — already installed")
            continue
        hints: list[str] = []
        if tool["brew"]:
            hints.append(f"brew install {tool['brew']}")
        if tool["manual"]:
            hints.append(tool["manual"])
        if tool["name"].startswith("Ollama"):
            hints = ["ollama serve", f"ollama pull {_VISION_MODEL}"]
        print(f"  ✗ {tool['name']} — manual install: {' | '.join(hints)}")
    print()
    print("Install what is missing, then re-run with --check-tools.")


# ---------------------------------------------------------------------------
# Kind detection
# ---------------------------------------------------------------------------
def _detect_kind(path: Path) -> str:
    """Return the surface kind for *path* from its suffix.

    Parameters
    ----------
    path : Path
        Source file. Lowercased and matched against :data:`_SUFFIX_KIND`,
        longest suffix first.

    Returns
    -------
    str
        One of the ``_KIND_*`` constants.

    Raises
    ------
    SystemExit
        When no known suffix matches.
    """
    name = path.name.lower()
    for suffix in sorted(_SUFFIX_KIND, key=len, reverse=True):
        if name.endswith(suffix):
            return _SUFFIX_KIND[suffix]
    known = ", ".join(sorted(_SUFFIX_KIND))
    raise SystemExit(
        f"ralph_eyeball_loop: cannot detect surface kind for {path.name!r}.\n"
        f"Known suffixes: {known}"
    )


# ---------------------------------------------------------------------------
# Stable per-source hash
# ---------------------------------------------------------------------------
def _source_hash(path: Path) -> str:
    """Return an 8-char MD5 of the *resolved* absolute source path.

    A **slot identifier, not a content digest**, and the distinction is the
    whole point. The assessment file is a journal: iteration 2 is appended
    underneath iteration 1, so the same source has to land in the same file
    across runs however much its bytes changed in between. Keying it on the
    path is therefore right here.

    What it is not is a cache key, and ``assessment-<hash>.md`` read exactly
    like one for a long time — a hex digest in a filename says
    "content-addressed" to anybody who has met the idiom, so two runs on an
    unchanged figure repaid the entire VLM inference while looking as though
    they could not. That is the same shape as the defect found in
    ``os_helper.hashfile`` on 2026-10-31, which handed back a digest of the
    path when asked for a digest of the content, and therefore could not
    notice that the file was not there at all. A path digest and a content
    digest are both 32 hex characters, and the names do not tell them apart.

    The content-addressed half now exists, in :func:`_vlm_critique`, where it
    belongs: keyed on the pixels, the prompt and the model name.

    Parameters
    ----------
    path : Path
        Source file.

    Returns
    -------
    str
        8 lowercase hex characters, derived from the path and nothing else.
    """
    return hashlib.md5(str(path.resolve()).encode()).hexdigest()[:8]


def _rel(path: Path) -> str:
    """Return *path* relative to cwd when possible."""
    try:
        return str(path.resolve().relative_to(Path.cwd()))
    except ValueError:
        return str(path.resolve())


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------
def _render_html(src: Path, out: Path, width: int, height: int) -> None:
    """Screenshot an HTML page via headless Chrome.

    Parameters
    ----------
    src : Path
        HTML source file (resolved to absolute for the ``file://`` URL).
    out : Path
        PNG output path.
    width, height : int
        Viewport size in CSS pixels.

    Raises
    ------
    SystemExit
        When Chrome is not found or the screenshot fails.
    """
    chrome = _find_chrome()

    # Headless Chrome enforces a *minimum window width* (~500 px on macOS/Linux
    # builds): request a narrower window and Chrome silently lays the page out
    # at ~485 px, then the screenshot crops it to the requested width. That crop
    # looks exactly like a horizontal-overflow bug that isn't there. So a width
    # below the floor is a false-mobile trap — clamp it and say so out loud. For
    # a pixel-true phone viewport (375 px), use a real browser's device-mode;
    # the flag-only path cannot emulate it.
    effective_width = width
    if width < _CHROME_MIN_VIEWPORT:
        effective_width = _CHROME_MIN_VIEWPORT
        print(
            f"ralph_eyeball_loop: requested width {width} px is below Chrome's "
            f"headless minimum (~{_CHROME_MIN_VIEWPORT} px). Rendering at "
            f"{effective_width} px (a large-phone viewport) to avoid a "
            "misleading crop. For a true 375 px phone view, use a browser's "
            "device-mode.",
            file=sys.stderr,
        )

    url = f"file://{src.resolve()}"
    # A profile of its own, thrown away after the shot. Without it headless
    # Chrome opens the user's default profile, which the Chrome they have
    # open already holds: the run then fights that browser for the profile
    # lock and can exit non-zero after writing the PNG, or disturb the
    # session on screen.
    profile = tempfile.mkdtemp(prefix="ralph-chrome-")
    proc = subprocess.run(
        [
            chrome,
            "--headless=new",
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--no-default-browser-check",
            f"--screenshot={out}",
            f"--window-size={effective_width},{height}",
            # Without this the 15 px scrollbar makes the CSS viewport 15 px
            # narrower than the window, so the render never matches the width
            # you asked for. Hiding it makes viewport == window width.
            "--hide-scrollbars",
            "--no-sandbox",
            url,
        ],
        capture_output=True,
    )
    shutil.rmtree(profile, ignore_errors=True)
    # The screenshot is the contract, not the exit code: Chrome can report a
    # failure from its own shutdown after the PNG is complete on disk.
    if proc.returncode != 0 and not (out.exists() and out.stat().st_size > 0):
        detail = (proc.stderr or b"").decode(errors="replace")[-1000:]
        raise SystemExit(f"ralph_eyeball_loop: Chrome exited {proc.returncode}:\n{detail}")


def _render_diagram(src: Path, out: Path, bg: str, dark: bool) -> None:
    """Delegate diagram rendering to ``render_diagram.py``.

    Parameters
    ----------
    src : Path
        TikZ / SVG source file.
    out : Path
        PNG output path.
    bg : str
        Background token: ``"white"`` | ``"transparent"`` | ``"dark"`` | ``#RRGGBB``.
    dark : bool
        Activate the dark-mode house canvas.

    Raises
    ------
    SystemExit
        When ``render_diagram.py`` is missing or exits non-zero.
    """
    if not _RENDER_DIAGRAM.is_file():
        raise SystemExit(
            f"ralph_eyeball_loop: render_diagram.py not found at {_RENDER_DIAGRAM}.\n"
            "Ensure sprezzature-figures is installed and this script lives in "
            "sprezzature-figures/scripts/."
        )
    cmd = [
        sys.executable, str(_RENDER_DIAGRAM),
        str(src),
        "--background", bg,
        "--out", str(out),
    ]
    if dark:
        cmd.append("--dark")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise SystemExit(f"ralph_eyeball_loop: render_diagram.py exited {result.returncode}")


# ---------------------------------------------------------------------------
# Local-mode Ollama vision critique
# ---------------------------------------------------------------------------
_CRITIQUE_PROMPT_BASE = """\
You are a senior UI and data-visualization reviewer performing a Ralph Eyeball Loop pass.
Study this rendered image carefully and write a structured critique.
Be specific, honest, and actionable — describe what you actually *see*, not what you expect.
Name concrete problems and propose concrete fixes.

Format your response using exactly these bold labels (one paragraph per label):

**Layout** — overall composition, alignment, and use of white-space.

**Contrast** — legibility of text and marks against the background; any elements that are hard to read.

**Hierarchy** — does the eye land on the most important element first? Is visual weight correctly placed?

**Spacing** — padding, margins, and gaps between elements. Too tight, too loose, or inconsistent?

**Accessibility** — color-vision deficiency (CVD) safety, contrast ratios, missing alt-text or ARIA concerns.

**Colors** — purposeful vs decorative; on-brand; any hue that clashes, misleads, or is CVD-unsafe.

**OCR / text readability** — can every label, tick value, axis title, and caption be read at this rendered size?

**Overall verdict** — one or two sentences: what are the most important changes needed before shipping?
"""

_CRITIQUE_PROMPT_HTML_EXTRA = """
**First-fold content** — is the primary message, headline, or call-to-action (CTA) visible without scrolling at this viewport size?

**Responsiveness** — does the layout look intentional at this viewport, or are there overflow, clipping, or overflow-hidden artefacts?
"""


def _build_critique_prompt(kind: str) -> str:
    """Build the Ollama vision critique prompt for the given surface kind.

    Parameters
    ----------
    kind : str
        Surface kind (``"html"``, ``"tikz"``, etc.).

    Returns
    -------
    str
        The complete prompt string to send to the vision model.
    """
    prompt = _CRITIQUE_PROMPT_BASE
    if kind == _KIND_HTML:
        prompt += _CRITIQUE_PROMPT_HTML_EXTRA
    return prompt.strip()


class _VisionBackendUnreachable(RuntimeError):
    """The VLM backend refused the call or timed out.

    Raised inside the wallet-wrapped call rather than :exc:`SystemExit`,
    which is a :exc:`BaseException`: the ledger releases its in-flight claim
    when a computation fails, and handing third-party machinery a
    ``BaseException`` is not the way to find out whether it still does.
    Measured both ways — a raising call leaves no poisoned claim and the next
    caller recomputes — but the narrow exception is the honest contract.
    :func:`_vlm_critique` converts it to :exc:`SystemExit` at the boundary.
    """


#: Cache scope for the critique, so nothing else sharing a ledger can collide
#: with it whatever its payload happens to hash to.
_CRITIQUE_NAMESPACE: str = "sprezzature-figures.ralph.vlm-critique"

#: Where the stored critiques live: inside the loop's own gitignored output
#: directory, beside the assessments and PNGs they describe.
#:
#: Deliberately *not* the shared default (``$WALLET_HELPER_DIR``, then
#: ``~/.cache/wallet-helper``), for one reason: ``max_entries`` below evicts
#: within whichever database it is handed, so a cap set here against a ledger
#: shared by the whole suite would throw away other packages' entries. A
#: private file keeps the bound local to the thing being bounded.
_CRITIQUE_LEDGER: Path = _PRIVATE_LOOP_DIR / "critique-ledger.db"

#: Size cap on the store, applied on every write. 167 chart kinds plus web
#: pages and diagrams, several viewports each, at a couple of kilobytes per
#: critique: a generous ceiling that is still a ceiling. Without one the store
#: has no bound at all, which is the difference between a cache and a
#: directory that only grows.
_CRITIQUE_MAX_ENTRIES: int = 500

#: Attempts and first backoff step for opening the critique ledger. The names
#: and the shape are `sprezzature-audio`'s and `sprezzature-publish`'s, in
#: their `scripts/_wallet.py`: same defect, and they measured it first. Six
#: attempts span roughly 1.3 s in the worst case, far shorter than one vision
#: call.
_LEDGER_ATTEMPTS: int = 6
_LEDGER_BACKOFF: float = 0.02


@lru_cache(maxsize=1)
def _critique_wallet() -> _wallet.Wallet:
    """The wallet behind :func:`_vlm_critique`, built once per process.

    ``SqliteLedger`` and not the default JSON ``Ledger``, because the
    single-flight guarantee differs between them and the difference is the one
    that matters here. Measured with two processes started together on the same
    key against a four-second call: with ``SqliteLedger`` the heavy call ran
    **once** and the loser returned the stored answer; with the JSON ``Ledger``
    it ran **twice**, its single-flight being in-process only. Three sessions
    working this repository in parallel is a Saturday afternoon here, not a
    thought experiment.

    The retry was a measured wrinkle, not superstition: two processes *creating*
    the database file at the same instant raced inside the constructor's own
    ``PRAGMA journal_mode=WAL``, and one of them got
    ``sqlite3.OperationalError: database is locked`` before any of this
    package's code ran. ``wallet-helper`` **1.3.2** reads the mode before
    writing it, and this package's floor now names it, so that cause is out of
    reach here.

    What is left, and why the retry stays
    -------------------------------------
    A file that is not a database — ``sqlite3.DatabaseError`` — which is a disk
    and not a release: a ledger truncated by a crash, or a path that collided
    with something else. That degrades immediately, because no number of
    retries repairs a bad file, and because taking the whole loop down over a
    *cache* would trade a cache for a crash. ``sprezzature-audio`` and
    ``sprezzature-publish`` carry this branch in their shared
    ``scripts/_wallet.py``; this copy did not have it until the floor moved and
    the question was asked out loud.

    ``OperationalError`` keeps its retry for genuine contention past the busy
    timeout, which no floor rules out. The backoff is **jittered** for the
    reason the siblings' is: processes that collided and then back off on one
    fixed schedule collide again on the next rung, which is the collision the
    retry exists to recover from.
    """
    _CRITIQUE_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    reason = f"stayed locked after {_LEDGER_ATTEMPTS} attempts"
    for attempt in range(_LEDGER_ATTEMPTS):
        try:
            return _wallet.Wallet(
                _wallet.SqliteLedger(_CRITIQUE_LEDGER, max_entries=_CRITIQUE_MAX_ENTRIES)
            )
        except sqlite3.OperationalError:
            # Contention. Jittered, so two processes that collided do not retry
            # in lockstep. (`OperationalError` first: it is a subclass of the
            # clause below.)
            time.sleep(_LEDGER_BACKOFF * (2**attempt) * (0.5 + random.random()))
        except sqlite3.DatabaseError as exc:
            reason = f"is not a usable database ({exc})"
            break
    print(
        f"ralph_eyeball_loop: the critique ledger {reason}; falling back to the "
        "JSON store (caching still works, cross-process single-flight does not).",
        file=sys.stderr,
    )
    return _wallet.Wallet(
        _wallet.Ledger(_CRITIQUE_LEDGER.parent, max_entries=_CRITIQUE_MAX_ENTRIES)
    )


def _unreachable_message(exc: Exception) -> str:
    """The start-and-pull hint shown when the vision backend does not answer."""
    return (
        f"ralph_eyeball_loop: could not reach the vision model backend "
        f"(default: Ollama at {_OLLAMA_URL}).\n"
        "  Start it with:  ollama serve\n"
        f"  Pull the model: ollama pull {_VISION_MODEL}\n"
        f"  Error: {exc}"
    )


def _vlm_critique(png_path: Path, kind: str, use_cache: bool = True) -> str:
    """Call ``qwen3-vl:8b`` to critique a PNG, via ``best_engine_ai_helper``.

    The call is routed through :func:`best_engine_ai_helper.llm.chat`
    (imported at module level as ``_llm_chat``), never through a
    directly-opened Ollama connection. That function reads
    ``SPREZZATURE_LLM_BACKEND`` to pick the backend (Ollama by default)
    and ``SPREZZATURE_LLM_VISION`` to override the model tag; the ``model``
    argument passed here (:data:`_VISION_MODEL`) is a per-call override on
    top of that, since this loop always wants ``qwen3-vl:8b`` specifically.

    The result is memoized through ``wallet_helper`` on the three inputs the
    critique is a function of — **the PNG's bytes, the prompt, and the model
    name** — and on nothing else. Not the path: ``.private/ralph-loop/``
    already held one file per source path, and that file is a journal rather
    than a cache (see :func:`_source_hash`), so re-running the loop on a figure
    nobody had touched bought the whole inference a second time. Measured on
    ``assets/svg-examples/elbow.svg`` at 700 px with the model already resident
    in memory: **121.3 s** then **94.6 s** for two identical runs before the
    change. The variance between those two numbers is the other half of the
    argument — the critiques came back 3 039 and 3 495 characters long, so an
    unchanged figure drew a different verdict each time and the journal's next
    iteration read as progress.

    The bytes go in explicitly even though ``make_key`` would have done it for
    us: it recognises a string naming an existing file and digests the file's
    content rather than the text, which was measured here by sabotaging the key
    back to ``str(png_path)`` and watching the guard stay green. Two reasons to
    keep the bytes anyway. ``make_key``'s documented fallback is the path text
    when the file vanishes between detection and hashing, and that is the one
    case where this loop would silently reuse a critique of other pixels. And a
    key whose content-addressing depends on a courtesy of the library reads, to
    the next person, exactly like the path key this replaced.

    Parameters
    ----------
    png_path : Path
        Rendered PNG to critique.
    kind : str
        Surface kind (used to extend the prompt for web pages).
    use_cache : bool, optional
        Whether to consult the store. ``False`` (``--no-critique-cache``)
        forces a fresh inference and writes it back, which is what asking a
        non-deterministic model for a second opinion on the same pixels looks
        like.

    Returns
    -------
    str
        The model's critique text.

    Raises
    ------
    SystemExit
        When the backend is unreachable or the model is not pulled.
    """
    prompt = _build_critique_prompt(kind)
    png_bytes = png_path.read_bytes()

    def _ask_the_model() -> str:
        print(f"ralph_eyeball_loop: calling {_VISION_MODEL} for visual critique "
              "(first call loads the model, ~30 s cold) …", file=sys.stderr)
        try:
            return str(_llm_chat(prompt, images=[png_bytes], model=_VISION_MODEL)).strip()
        except Exception as exc:
            raise _VisionBackendUnreachable(str(exc)) from exc

    if not use_cache:
        try:
            return _ask_the_model()
        except _VisionBackendUnreachable as exc:
            raise SystemExit(_unreachable_message(exc)) from exc

    try:
        critique, was_stored = _critique_wallet().call(
            _CRITIQUE_NAMESPACE,
            {"png": png_bytes, "prompt": prompt, "model": _VISION_MODEL},
            _ask_the_model,
        )
    except _VisionBackendUnreachable as exc:
        raise SystemExit(_unreachable_message(exc)) from exc
    if was_stored:
        print(
            f"ralph_eyeball_loop: reusing the stored critique of {_rel(png_path)} — same "
            "pixels, same prompt, same model. --no-critique-cache asks again.",
            file=sys.stderr,
        )
    return str(critique)


# ---------------------------------------------------------------------------
# Assessment file
# ---------------------------------------------------------------------------
_HEADER_TMPL = """\
# Ralph Eyeball Loop — {rel_src}

| Field | Value |
|---|---|
| **Source** | `{rel_src}` |
| **Kind** | {kind} |
| **Hash** | `{h}` |
| **Started** | {ts} |

The loop: **render → look → fill in the critique → edit the source →
re-run → repeat** until the Verdict box is checked.

*The thing you edit is always the source, never the PNG.*

---

"""

# Template used in agent mode — the agent fills in the blank fields.
_ITERATION_AGENT_TMPL = """\
## Iteration {n} — {ts} [agent mode]

**PNG:** `{rel_png}`

### Critique

*Read the PNG with the `Read` tool, then fill in each section.*

**Layout** — overall composition, alignment, white-space:

**Contrast** — legibility of text and marks against the background:

**Hierarchy** — does the eye land on the most important element first?

**Spacing** — padding, margins, gaps between elements:

**Accessibility** — CVD safety, contrast ratios, ARIA/alt-text:

**Colors** — purposeful vs decorative; on-brand; CVD-safe?

**OCR / text readability** — can every label, tick, and caption be read?

**First-fold** *(web pages only)* — key message visible without scrolling?

**Overall verdict:**

### Planned changes

-

### Verdict

- [ ] Satisfied — stop the loop
- [ ] Not yet — edit the source and re-run

---

"""

# Template used in local mode — the vision model fills in the critique block.
_ITERATION_LOCAL_TMPL = """\
## Iteration {n} — {ts} [local mode — {vision_model}]

**PNG:** `{rel_png}`

### Critique (auto-generated — review and edit before acting)

{critique}

### Planned changes

-

### Verdict

- [ ] Satisfied — stop the loop
- [ ] Not yet — edit the source and re-run

---

"""


def _write_assessment(
    assess_path: Path,
    src: Path,
    png_path: Path,
    kind: str,
    h: str,
    auto_critique: Optional[str] = None,
) -> int:
    """Create or extend the assessment Markdown file.

    First call: writes the file header and iteration 1.
    Subsequent calls: appends the next numbered iteration section.

    Parameters
    ----------
    assess_path : Path
        ``.private/ralph-loop/assessment-<hash>.md``.
    src : Path
        Source file being looped on.
    png_path : Path
        The PNG just rendered.
    kind : str
        Surface kind.
    h : str
        8-char source hash.
    auto_critique : str, optional
        Auto-generated critique from Ollama (local mode).  When ``None``,
        agent-mode template blanks are written instead.

    Returns
    -------
    int
        The iteration number just written.
    """
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    rel_src = _rel(src)
    rel_png = _rel(png_path)

    if not assess_path.exists():
        header = _HEADER_TMPL.format(rel_src=rel_src, kind=kind, h=h, ts=ts)
        n = 1
        existing = ""
    else:
        existing = assess_path.read_text(encoding="utf-8")
        n = existing.count("\n## Iteration ") + 1
        header = ""

    if auto_critique is not None:
        body = _ITERATION_LOCAL_TMPL.format(
            n=n, ts=ts, rel_png=rel_png,
            vision_model=_VISION_MODEL,
            critique=auto_critique,
        )
    else:
        body = _ITERATION_AGENT_TMPL.format(n=n, ts=ts, rel_png=rel_png)

    assess_path.write_text(header + existing + body, encoding="utf-8")
    return n


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ralph_eyeball_loop",
        description=(
            "Ralph Eyeball Loop: render a visual-from-code artifact (web page, "
            "TikZ figure, SVG) to PNG and write a "
            "gitignored assessment file. "
            "Two modes: agent (Claude Code reads the PNG) or --local (Ollama vision)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Assessment files: .private/ralph-loop/assessment-<hash>.md\n"
            "Rendered PNGs:    .private/ralph-loop/<stem>-<hash>.png\n"
            "(both gitignored — never committed)\n\n"
            "Each re-run appends a new iteration section.\n\n"
            "Full protocol: https://github.com/warith-harchaoui/sprezzature/blob/main/"
            "sprezzature-figures/references/ralph-eyeball-loop.md"
        ),
    )
    p.add_argument(
        "source",
        nargs="?",
        help=(
            "Visual source file: "
            ".html/.htm (web page), "
            ".tex/.tikz (TikZ), "
            ".svg (SVG). "
            "Omit when using --install-tools or --check-tools."
        ),
    )
    p.add_argument(
        "--local",
        action="store_true",
        help=(
            f"Local mode: call {_VISION_MODEL} via Ollama to auto-generate "
            "the critique and pre-fill the assessment file. "
            "Requires: ollama serve && ollama pull " + _VISION_MODEL
        ),
    )
    p.add_argument(
        "--no-critique-cache",
        action="store_true",
        help=(
            "Ask the model again even though these exact pixels, prompt and model "
            "already have a stored critique. The critique is memoized on those three "
            "inputs (wallet_helper), so re-assessing an unchanged figure normally "
            "costs nothing; this is how you buy a second opinion from a model that "
            "does not give the same one twice."
        ),
    )
    p.add_argument(
        "--width", type=int, default=1440,
        help="Viewport width for HTML renders in CSS pixels (default: 1440). "
             "Values below ~500 are clamped up (Chrome's headless minimum); "
             "a true 375 px phone view needs a browser's device-mode.",
    )
    p.add_argument(
        "--height", type=int, default=900,
        help="Viewport height for HTML renders in CSS pixels (default: 900).",
    )
    p.add_argument(
        "--bg", default="white",
        help=(
            "Background for diagram renders: "
            "white | transparent | dark | #RRGGBB (default: white). "
            "Ignored for HTML — the page sets its own background."
        ),
    )
    p.add_argument(
        "--dark", action="store_true",
        help="Use the dark-mode house canvas for diagram renders.",
    )
    p.add_argument(
        "--out",
        help="Override the PNG output path.",
    )
    p.add_argument(
        "--install-tools",
        action="store_true",
        help=(
            "Print the command that installs each missing rendering tool "
            "(Chrome, system libs, the Ollama vision model); nothing is "
            "installed for you."
        ),
    )
    p.add_argument(
        "--check-tools",
        action="store_true",
        help="Print a table showing which rendering tools are installed.",
    )
    return p


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point.

    Parameters
    ----------
    argv : list[str], optional
        Argument list (uses ``sys.argv`` when *None*).

    Returns
    -------
    int
        Exit code: 0 on success, 2 on usage / IO error.
    """
    args = _build_parser().parse_args(argv)

    # ---- Tool management sub-commands ----
    if args.install_tools:
        install_tools()
        return 0
    if args.check_tools:
        check_tools(verbose=True)
        return 0

    if not args.source:
        _build_parser().print_help()
        return 2

    if args.source.lower().endswith(_REFUSED_SUFFIXES):
        print(
            f"ralph_eyeball_loop: {Path(args.source).name} is not a source this tool "
            "reads; draw the diagram with `sprezzature-figures render flowchart`.",
            file=sys.stderr,
        )
        return 2

    src = Path(args.source)
    if not src.exists():
        print(f"ralph_eyeball_loop: {src} — file not found", file=sys.stderr)
        return 2

    kind = _detect_kind(src)
    h = _source_hash(src)

    _PRIVATE_LOOP_DIR.mkdir(parents=True, exist_ok=True)

    # Derive PNG stem — strip compound suffixes (.vl.json → "fig").
    stem = src.name
    for suffix in sorted(_SUFFIX_KIND, key=len, reverse=True):
        if stem.lower().endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    png_path = Path(args.out) if args.out else _PRIVATE_LOOP_DIR / f"{stem}-{h}.png"
    assess_path = _PRIVATE_LOOP_DIR / f"assessment-{h}.md"

    mode = "local" if args.local else "agent"
    print(f"ralph_eyeball_loop: rendering {src.name!r}  [{kind}]  mode={mode} …", file=sys.stderr)

    if kind == _KIND_HTML:
        _render_html(src, png_path, width=args.width, height=args.height)
    else:
        _render_diagram(src, png_path, bg=args.bg, dark=args.dark)

    # ---- Critique ----
    auto_critique: Optional[str] = None
    if args.local:
        auto_critique = _vlm_critique(png_path, kind, use_cache=not args.no_critique_cache)

    iteration = _write_assessment(assess_path, src, png_path, kind, h, auto_critique)

    # ---- Summary ----
    rel_png = _rel(png_path)
    rel_assess = _rel(assess_path)
    print(f"\nralph_eyeball_loop: iteration {iteration}", file=sys.stderr)
    print(f"  PNG    → {rel_png}", file=sys.stderr)
    print(f"  assess → {rel_assess}", file=sys.stderr)
    print(file=sys.stderr)

    if args.local:
        print("Next steps:", file=sys.stderr)
        print(f"  1. Review the auto-critique in {Path(rel_assess).name}", file=sys.stderr)
        print(f"  2. Edit {src.name}  (never the PNG)", file=sys.stderr)
        print("  3. Re-run to loop", file=sys.stderr)
    else:
        print("Next steps (agent mode):", file=sys.stderr)
        print(f"  1. Read {png_path.name}  (use the Read tool to view it)", file=sys.stderr)
        print(f"  2. Fill in {Path(rel_assess).name} with your honest critique", file=sys.stderr)
        print(f"  3. Edit {src.name}  (never the PNG)", file=sys.stderr)
        print("  4. Re-run to loop", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
