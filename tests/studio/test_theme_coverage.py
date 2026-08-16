"""
Guard against the failure mode that left the first Studio UI unstyled: a
component using a Tailwind-style utility class (a short, single-purpose CSS
class name, like ``text-lg``, that stands in for a whole style rule) that
``theme.py`` never defines. The installed NiceGUI build (the Python UI
framework Studio is built on) ships no Tailwind CSS of its own, so such a
class is a silent no-op: the layout just quietly doesn't apply, with no
error to point at the mistake.

This test statically extracts every class token passed to a
``.classes(...)`` call across ``sprezzature_figures/studio`` and asserts
each is covered by ``theme.supported_classes()``, which is derived from the
shipped stylesheet itself. To make a new usage pass, add the class to
``theme.py``; for a class that instead comes from an external stylesheet
(Quasar, NiceGUI's underlying component library), add it to
``KNOWN_EXTERNAL`` below.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import ast
from pathlib import Path

from sprezzature_figures.studio.theme import supported_classes

STUDIO_DIR = Path(__file__).resolve().parents[2] / "sprezzature_figures" / "studio"

# Classes that are intentionally provided by something other than theme.py
# (e.g. a Quasar-native class). Empty today: the Studio styles itself
# entirely through theme.py. Extend this only with a class you have
# confirmed is defined by an external stylesheet that is actually loaded.
KNOWN_EXTERNAL: frozenset[str] = frozenset()


def _class_tokens_in(source: str) -> set[str]:
    """Return every static class token handed to a ``.classes(...)`` call.

    Handles plain string literals and f-strings (the literal parts only --
    an interpolated ``{expr}`` is skipped, since its value can't be known
    statically). Covers positional args and the ``add`` / ``replace`` /
    ``remove`` keyword arguments NiceGUI's ``classes()`` accepts.
    """
    tokens: set[str] = set()

    def collect(node: ast.AST) -> None:
        # A plain string literal: "w-full gap-2".
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            tokens.update(node.value.split())
        # An f-string: keep the constant segments, drop {expr} placeholders.
        elif isinstance(node, ast.JoinedStr):
            for part in node.values:
                if isinstance(part, ast.Constant) and isinstance(part.value, str):
                    tokens.update(part.value.split())

    tree = ast.parse(source)
    for call in ast.walk(tree):
        if not isinstance(call, ast.Call):
            continue
        func = call.func
        if not (isinstance(func, ast.Attribute) and func.attr == "classes"):
            continue
        for arg in call.args:
            collect(arg)
        for kw in call.keywords:
            if kw.arg in {"add", "replace", "remove", None}:
                collect(kw.value)

    return tokens


def _iter_studio_sources() -> list[Path]:
    return sorted(STUDIO_DIR.rglob("*.py"))


def test_studio_files_are_discovered() -> None:
    # Sanity check the walk actually finds the component files, so an empty
    # glob can never make the coverage assertion vacuously pass.
    files = _iter_studio_sources()
    names = {p.name for p in files}
    assert {"editor.py", "chat_panel.py", "data_panel.py"} <= names


def test_every_used_class_is_defined_by_the_theme() -> None:
    supported = supported_classes()
    uncovered: dict[str, set[str]] = {}
    for path in _iter_studio_sources():
        used = _class_tokens_in(path.read_text(encoding="utf-8"))
        missing = {c for c in used if c not in supported and c not in KNOWN_EXTERNAL}
        if missing:
            uncovered[str(path.relative_to(STUDIO_DIR.parents[1]))] = missing

    assert not uncovered, (
        "These .classes() tokens are used but not defined by theme.py, so they "
        "silently no-op. Add them to theme.py's _UTILITIES (or KNOWN_EXTERNAL "
        f"if provided by an external stylesheet):\n{uncovered}"
    )
