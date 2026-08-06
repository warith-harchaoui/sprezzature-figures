"""
sprezzature-figures — Model Context Protocol (MCP) surface.

Adapter that exposes the FastAPI app defined in :mod:`sprezzature_figures.api`
as MCP tools so any MCP-aware host (agent runtimes, IDE integrations,
custom shells) can call ``kinds`` / ``kind_definition`` / ``render`` as
first-class tools. Uses :mod:`fastapi_mcp`
(https://github.com/tadata-org/fastapi_mcp) -- one line wraps the whole
existing HTTP surface, so we never duplicate the route definitions.

Install the extra to pull in ``fastapi-mcp``::

    pip install 'sprezzature-figures[api,mcp]'

Then run the MCP server::

    sprezzature-figures-mcp          # entry point (see pyproject)
    # or, equivalently:
    python -m sprezzature_figures.mcp

Usage Example
-------------
>>> # Register the MCP endpoint in your client. It publishes:
>>> #   health / kinds / kind_definition / render
>>> # …with the same argument names as the FastAPI routes.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

try:
    from fastapi_mcp import FastApiMCP
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "The MCP surface requires the [mcp] extra. "
        "Install with: pip install 'sprezzature-figures[api,mcp]'"
    ) from exc

# Reuse the exact same FastAPI app -- MCP is a thin wrapper on top.
from sprezzature_figures.api import app

# ``FastApiMCP`` mounts an MCP endpoint on the existing FastAPI app; we
# store the wrapped instance at module scope so downstream code (tests,
# ASGI runners) can access both the FastAPI app and the MCP handler.
mcp = FastApiMCP(
    app,
    name="sprezzature-figures",
    description=(
        "Sprezzature Figures MCP tools: list chart kinds, inspect a kind's "
        "data-role requirements, or render one of ~95 chart types from JSON rows."
    ),
)
# Attach the MCP endpoint to the FastAPI app. Newer fastapi-mcp releases
# split ``mount()`` into transport-specific ``mount_http()`` (recommended)
# and ``mount_sse()``. Fall back to the legacy ``mount()`` on older
# versions so users can install a range of ``fastapi-mcp`` versions.
if hasattr(mcp, "mount_http"):
    mcp.mount_http()
else:  # pragma: no cover -- legacy fastapi-mcp
    mcp.mount()


def main() -> None:
    """
    Entry point for the ``sprezzature-figures-mcp`` console script.

    Boots the FastAPI app (which now serves both the ``/…`` HTTP routes
    and the MCP endpoint) with ``uvicorn`` in single-worker mode. Meant
    for local / container usage; behind a real load balancer use
    ``uvicorn`` / ``gunicorn`` directly.
    """
    import os

    import uvicorn

    host = os.environ.get("SPREZZATURE_FIGURES_HOST", "0.0.0.0")
    port = int(os.environ.get("SPREZZATURE_FIGURES_PORT", "8000"))
    # Single worker: the figure registry and generator-module cache
    # (sys.modules) are process-local state, so multiple workers would
    # each pay the same import cost independently rather than sharing it.
    uvicorn.run(app, host=host, port=port, workers=1)


if __name__ == "__main__":  # pragma: no cover
    main()
