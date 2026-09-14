"""
The two numbers a release is most likely to get wrong: the version and the
size of the catalogue.

Both are hand-written in more than one place and both are read by someone
outside this repository. ``__version__`` is what ``api.py`` hands FastAPI, so
it lands in ``/openapi.json`` and in the headline an MCP host shows — it sat
at 2.0.0 through the 2.1.0 release, advertising a version that had not been
published. The catalogue size is printed in the PyPI summary, the API
description and the MCP tool description; it said 124 while
``list_kinds()`` returned 127.

Neither drift breaks a render, which is exactly why nothing caught them. A
number quoted at a reader has to come from the thing it describes.

Author
------
Warith HARCHAOUI <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from sprezzature_figures import __version__
from sprezzature_figures.catalog import list_kinds

REPO_ROOT = Path(__file__).resolve().parent.parent

_PYPROJECT_VERSION_RE = re.compile(r'^\s*version\s*=\s*["\']([\d.]+)["\']', re.MULTILINE)

#: Files whose prose quotes the catalogue size at a reader. Machine-facing
#: first: the PyPI summary, the OpenAPI description, the MCP tool description.
_COUNT_CLAIMING_FILES = (
    "pyproject.toml",
    "sprezzature_figures/__init__.py",
    "sprezzature_figures/api.py",
    "sprezzature_figures/mcp.py",
    "scripts/render_diagram.py",
    "docs/studio/README.md",
)

#: "127 chart types", "the 127-kind catalogue", "All 127 registered …" — a
#: three-digit number close enough to a catalogue word to be a claim about it.
_CLAIM_RE = re.compile(
    r"\b(\d{2,4})[\s-]+(?:hand-authored|registered|chart|kind|generator|figure)",
    re.IGNORECASE,
)


def _pyproject_version() -> str:
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = _PYPROJECT_VERSION_RE.search(text)
    assert match, "pyproject.toml declares no project version"
    return match.group(1)


def test_package_version_matches_pyproject() -> None:
    """``__version__`` is what the API advertises; pyproject is what pip installs."""
    assert __version__ == _pyproject_version(), (
        f"version drift: sprezzature_figures.__version__ is {__version__!r} but "
        f"pyproject.toml declares {_pyproject_version()!r}. The first is what "
        f"/openapi.json and every MCP host display."
    )


def test_changelog_leads_with_the_current_version() -> None:
    """The top release section of the CHANGELOG names the version being shipped."""
    text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    headings = re.findall(r"^##\s+\[?([\d.]+)\]?", text, re.MULTILINE)
    assert headings, "CHANGELOG.md has no release headings"
    assert headings[0] == __version__, (
        f"CHANGELOG.md leads with {headings[0]}, but the package is {__version__}. "
        f"A release whose top section is an older version ships undocumented changes."
    )


@pytest.mark.parametrize("relative_path", _COUNT_CLAIMING_FILES)
def test_quoted_catalogue_size_matches_the_catalogue(relative_path: str) -> None:
    """Any catalogue count written in prose equals ``len(list_kinds())``."""
    kinds = len(list_kinds())
    text = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
    claimed = {int(n) for n, in ((m.group(1),) for m in _CLAIM_RE.finditer(text))}
    wrong = sorted(n for n in claimed if n != kinds)
    assert not wrong, (
        f"{relative_path} tells the reader the catalogue holds {wrong}, but "
        f"list_kinds() returns {kinds}. Adding a generator without touching this "
        f"file is how the count went stale last time."
    )
