"""
Both halves of the dependency guard in ``mcp.py`` must take the same call.

``mcp.py`` defines ``main`` twice: once in the ``except ImportError`` branch
taken when the ``[mcp]`` extra is absent, once in the ``else`` branch that
runs the real server. The two are reached through the same console script,
so they are one function as far as any caller is concerned. They were not:
the fallback was ``def main() -> None`` while the real one was
``def main(argv: list[str] | None = None) -> None``, so
``main(["--host", "127.0.0.1"])`` answered on a machine with the extra and
raised ``TypeError: main() takes 0 positional arguments`` on a machine
without it. The branch that fires is the one a user who skipped the extra
hits, which is the worse half to have broken.

mypy says this too (``All conditional function variants must have identical
signatures``), and said it in all six packages at once, because the file is
deliberately duplicated across them. The type gate that used to catch it
stayed in the monorepo when the packages were split out. This test is the
part of that gate the packages can carry themselves: no mypy, no install, it
reads the source.

Author
------
Warith HARCHAOUI <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import ast
from pathlib import Path

MCP_SOURCE = Path(__file__).resolve().parent.parent / "sprezzature_figures" / "mcp.py"


def _main_definitions() -> list[ast.FunctionDef]:
    """Every ``def main`` in mcp.py, whichever branch it sits in."""
    tree = ast.parse(MCP_SOURCE.read_text(encoding="utf-8"))
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    ]


def test_mcp_defines_main_in_both_branches() -> None:
    """The guard only means something if both branches are still there."""
    assert len(_main_definitions()) == 2, (
        "mcp.py should define main() twice: once for the missing-extra "
        "fallback and once for the real server."
    )


def test_both_main_variants_accept_the_same_call() -> None:
    """A caller must not need to know which branch was taken."""
    signatures = {ast.unparse(node.args) for node in _main_definitions()}
    assert len(signatures) == 1, (
        f"mcp.py's two main() definitions take different arguments: "
        f"{sorted(signatures)}. They are reached through one console script, "
        f"so a caller cannot tell them apart and must not have to."
    )
