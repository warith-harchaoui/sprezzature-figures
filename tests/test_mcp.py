"""
Smoke tests for the MCP surface (sprezzature_figures.mcp); MCP, the Model
Context Protocol, is the standard that lets an AI assistant call this
project's chart generators as tools.

A full protocol handshake (initialize, open a session, call a tool) needs a
real running server and is exercised manually: see the module docstring in
mcp.py. This just confirms the import chain resolves and the MCP endpoint
actually gets mounted on the shared FastAPI app, the one thing most likely
to break silently on a fastapi-mcp/mcp version bump (see the pinning
comment in pyproject.toml's [mcp] extra: this caught a real incompatibility
once already).

Author
------
Warith HARCHAOUI <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi_mcp")


def test_mcp_module_imports_and_mounts() -> None:
    from sprezzature_figures.api import app
    from sprezzature_figures.mcp import mcp

    assert mcp is not None
    mounted_paths = {getattr(r, "path", "") for r in app.routes}
    assert any(p.startswith("/mcp") for p in mounted_paths), (
        f"Expected an /mcp-prefixed route on the shared app; got {sorted(mounted_paths)}"
    )


def test_every_tool_has_a_written_summary() -> None:
    """The first line an MCP host shows is FastAPI's `summary`, and its
    default is the function name title-cased: `redraw_route` became "Redraw
    Route", `kinds` became "Kinds". An agent picking between tools from
    several servers reads those headlines and nothing else, so each one has
    to be a written phrase saying what the tool does -- not a restatement of
    the Python identifier.
    """
    from sprezzature_figures.api import app

    for route in app.routes:
        operation_id = getattr(route, "operation_id", None)
        # fastapi-mcp mounts its own transport route; only this package's
        # own tools are ours to document.
        if not operation_id or getattr(route, "path", "").startswith("/mcp"):
            continue
        summary = (getattr(route, "summary", "") or "").strip()
        assert summary, f"{operation_id}: no summary, so the MCP headline is a function name"
        derived = getattr(route, "name", "").replace("_", " ").title()
        assert summary != derived, (
            f"{operation_id}: summary {summary!r} is FastAPI's default (the function "
            f"name title-cased). Write one that says what the tool does."
        )
        assert " " in summary and len(summary) > 15, (
            f"{operation_id}: summary {summary!r} is too terse to route on."
        )


def test_every_tool_says_when_to_call_it() -> None:
    """A description that only restates the summary does not help an agent
    choose. Each route's docstring carries the deciding context: when to
    reach for it, what it needs first, or what it must not be used for.
    """
    from sprezzature_figures.api import app

    for route in app.routes:
        operation_id = getattr(route, "operation_id", None)
        # fastapi-mcp mounts its own transport route; only this package's
        # own tools are ours to document.
        if not operation_id or getattr(route, "path", "").startswith("/mcp"):
            continue
        description = (getattr(route, "description", "") or "").strip()
        assert len(description) > 120, (
            f"{operation_id}: description is {len(description)} chars. Say when to call "
            f"it, not just what it is."
        )
