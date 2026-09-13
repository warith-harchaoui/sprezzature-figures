"""
sprezzature-figures — Model Context Protocol (MCP) surface.

Adapter that exposes the FastAPI app defined in :mod:`sprezzature_figures.api`
as MCP tools so any MCP-aware host (agent runtimes, IDE integrations,
custom shells) can call ``kinds`` / ``kind_definition`` / ``render`` as
first-class tools. Uses :mod:`fastapi_mcp`
(https://github.com/tadata-org/fastapi_mcp): one line wraps the whole
existing HTTP surface, so the same route definitions serve both plain HTTP
callers and MCP hosts without being written twice.

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
Warith HARCHAOUI <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import sys

try:
    from fastapi_mcp import FastApiMCP
except ImportError:  # pragma: no cover - dependency guard

    def main() -> None:
        """
        Entry point when the MCP extra is not installed.

        Says which extra is missing and stops. Reaching an MCP
        command without the ``[mcp]`` extra needs a one-line fix,
        not a stack trace.
        """
        print(
            "sprezzature-figures MCP surface requires fastapi-mcp. "
            "Install with: pip install 'sprezzature-figures[api,mcp]'",
            file=sys.stderr,
        )
        sys.exit(1)

else:

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
            "data-role requirements, or render one of 124 chart types from JSON rows."
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


    def main(argv: list[str] | None = None) -> None:
        """
        Entry point for the ``sprezzature-figures-mcp`` console script.

        Serves the FastAPI app — which carries both the HTTP routes and the
        MCP endpoint — with ``uvicorn``, in single-worker mode. Meant for
        local or container use; behind a real load balancer, run ``uvicorn``
        or ``gunicorn`` directly.

        Arguments are parsed before anything is bound, so ``--help`` answers
        instead of starting a server and hanging.

        Parameters
        ----------
        argv : list of str or None, optional
            Arguments to parse. ``None`` reads ``sys.argv``.
        """
        import argparse
        import os

        parser = argparse.ArgumentParser(
            prog="sprezzature-figures-mcp",
            description=(
                "Serve the sprezzature-figures MCP tools over HTTP. Every tool is a "
                "route on the same FastAPI app, with the MCP endpoint "
                "mounted beside them."
            ),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog=(
                "Defaults come from SPREZZATURE_FIGURES_HOST and "
                "SPREZZATURE_FIGURES_PORT when those are set.\n"
                "The host defaults to 127.0.0.1: pass --host 0.0.0.0 to "
                "accept connections from outside this machine."
            ),
        )
        parser.add_argument(
            "--host",
            default=os.environ.get("SPREZZATURE_FIGURES_HOST", "127.0.0.1"),
            help="Interface to bind (default: %(default)s).",
        )
        parser.add_argument(
            "--port",
            type=int,
            default=int(os.environ.get("SPREZZATURE_FIGURES_PORT", "8000")),
            help="Port to bind (default: %(default)s).",
        )
        args = parser.parse_args(argv)

        import uvicorn

        # Single worker: the figure registry and generator-module cache
        # (sys.modules) are process-local state, so multiple workers would
        uvicorn.run(app, host=args.host, port=args.port, workers=1)

if __name__ == "__main__":  # pragma: no cover
    main()
