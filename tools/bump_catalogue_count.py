#!/usr/bin/env python3
"""
bump_catalogue_count — rewrite every quoted catalogue size to the real one.

"127 chart types" is written out in prose in about twenty-five places: the
PyPI summary, the OpenAPI description, the MCP tool description, both
READMEs, the triggers table, the landscape pages, a module docstring. Every
one of them is a number quoted at a reader, and
``tests/test_release_consistency.py`` exists because they had already
drifted once -- the catalogue said 127 while the prose said 124.

Adding a figure therefore means editing two dozen sentences, which is
exactly the kind of chore that gets done four times and forgotten the
fifth. This does it from the one place that knows: ``list_kinds()``.

The dangerous part is that ``127`` is also an IP address, a port, a line
number and an exit code. Only a digit run that a catalogue word sits next
to is rewritten -- the same shape ``test_release_consistency`` looks for --
and any line containing ``127.0.0.1`` is skipped outright.

Usage
-----
::

    python tools/bump_catalogue_count.py            # rewrite
    python tools/bump_catalogue_count.py --check    # report, write nothing

Author
------
Warith HARCHAOUI <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from sprezzature_figures.catalog import list_kinds  # noqa: E402

#: Every file whose prose quotes the size of the catalogue. The first six
#: are the ones ``test_release_consistency`` already guards; the rest quote
#: it at a reader just as loudly and were being updated by hand.
CLAIMING_FILES: tuple[str, ...] = (
    "pyproject.toml",
    "sprezzature_figures/__init__.py",
    "sprezzature_figures/api.py",
    "sprezzature_figures/mcp.py",
    "scripts/render_diagram.py",
    "docs/studio/README.md",
    "README.md",
    "LISEZMOI.md",
    "FIGURES.md",
    "TRIGGERS.md",
    "LANDSCAPE.md",
    "PAYSAGE.md",
)

#: A digit run that a catalogue word sits beside, either way round:
#: "127 chart types", "the 127-kind catalogue", "All 127 registered",
#: "127 générateurs", "127 types de graphiques". Deliberately the same
#: shape the release test hunts for, so the two cannot disagree about what
#: counts as a claim.
_CLAIM = re.compile(
    # The word boundary is per-alternative, not trailing: "make_*.py" ends
    # on a character that has no boundary after it, so one shared `\b` at
    # the end silently dropped "128 make_*.py scripts total".
    r"\b(\d{2,4})(?=[\s-]+(?:hand-authored\b|registered\b|charts?\b|kinds?\b|"
    r"generators?\b|figures?\b|types?\b|scripts?\b|entry\b|entries\b|"
    r"make_\*|générateurs?\b))"
)


def rewrite(text: str, count: int) -> tuple[str, int]:
    r"""Return `text` with every catalogue claim set to `count`, and how many moved.

    Whole-text, not line by line: a wrapped string literal can put the
    number at the end of one line and the word "chart types" at the start
    of the next, and ``api.py`` does exactly that. ``[\s-]+`` spans the
    newline, so the claim is still seen -- which a per-line pass cannot do,
    and did not, the first time this was written.
    """
    changed = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal changed
        # A loopback address is never a catalogue size, and the two look
        # identical to an expression that only reads digits. Judge the line
        # the match starts on, which is where such an address would sit.
        line_start = text.rfind("\n", 0, match.start()) + 1
        line_end = text.find("\n", match.start())
        line = text[line_start : line_end if line_end != -1 else len(text)]
        if "127.0.0.1" in line:
            return match.group(0)
        if match.group(1) != str(count):
            changed += 1
        return str(count)

    return _CLAIM.sub(replace, text), changed


def main(argv: list[str] | None = None) -> int:
    """Rewrite the quoted catalogue size everywhere, or report what would move."""
    parser = argparse.ArgumentParser(
        prog="bump_catalogue_count",
        description="Set every quoted catalogue size to the real number of kinds.",
    )
    parser.add_argument("--check", action="store_true", help="Report stale claims; write nothing.")
    args = parser.parse_args(argv)

    count = len(list_kinds())
    stale = 0
    for name in CLAIMING_FILES:
        path = REPO_ROOT / name
        if not path.exists():
            print(f"warning: {name} is listed but absent", file=sys.stderr)
            continue
        text = path.read_text(encoding="utf-8")
        updated, moved = rewrite(text, count)
        if not moved:
            continue
        stale += moved
        print(f"{name}: {moved} claim(s) {'stale' if args.check else 'updated'}")
        if not args.check:
            path.write_text(updated, encoding="utf-8")

    if args.check and stale:
        print(
            f"{stale} claim(s) do not say {count}; run `python tools/bump_catalogue_count.py`",
            file=sys.stderr,
        )
        return 1
    print(f"catalogue is {count} kinds; {stale} claim(s) moved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
