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
Warith Harchaoui <warith.harchaoui@gmail.com>
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
