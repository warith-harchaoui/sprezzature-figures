"""
sprezzature-figures — Model Context Protocol (MCP) surface.

Adapter that exposes the FastAPI app defined in :mod:`sprezzature_figures.api`
as MCP tools so any MCP-aware host (agent runtimes, IDE integrations,
custom shells) can call its eight routes as first-class tools, each named
by its ``operation_id``. Uses :mod:`fastapi_mcp`
(https://github.com/tadata-org/fastapi_mcp): one line wraps the whole
existing HTTP surface, so the same route definitions serve both plain HTTP
callers and MCP hosts without being written twice.

``fastapi-mcp`` is a base dependency since 2026-11-01, so there is no
extra to ask for::

    pip install 'sprezzature-figures'

Then run the MCP server::

    sprezzature-figures-mcp          # entry point (see pyproject)
    # or, equivalently:
    python -m sprezzature_figures.mcp

Usage Example
-------------
>>> # Register the MCP endpoint in your client. It publishes:
>>> #   health / list_kinds / get_kind / list_kind_options /
>>> #   render_figure / redraw_figure / recommend_figures / check_render
>>> # …with the same argument names as the FastAPI routes.

Author
------
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

import sys

try:
    from fastapi_mcp import FastApiMCP
except ImportError:  # pragma: no cover - dependency guard

    def main(argv: list[str] | None = None) -> int:
        """
        Entry point when ``fastapi-mcp`` cannot be imported.

        Takes the same ``argv`` as the real entry point and ignores it:
        the two variants are reached through the same console script, so
        a caller that passes arguments must not get a ``TypeError`` from
        the branch that happens to be missing a dependency.

        Says the install is broken and stops: ``fastapi-mcp`` is a base
        dependency, so the fix is a reinstall, and it deserves a one-line
        message rather than a stack trace.
        """
        print(
            "sprezzature-figures MCP surface could not import fastapi-mcp, which is a "
            "base dependency since 2026-11-01 -- a broken install rather than "
            "a missing extra. Reinstall with: "
            "pip install 'sprezzature-figures'",
            file=sys.stderr,
        )
        return 1

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
            # Wrapped after "chart types" on purpose: a number left at the
            # end of a fragment is invisible to the guards that keep it true.
            "data-role requirements and the options it accepts, render one of "
            "168 chart types from JSON rows, or redraw a chart from a picture of it."
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

    import click

    @click.command(
        name="sprezzature-figures-mcp",
        context_settings={"help_option_names": ["-h", "--help"]},
        help=(
            "Serve the sprezzature-figures MCP tools over HTTP. Every tool is a "
            "route on the same FastAPI app, with the MCP endpoint "
            "mounted beside them."
        ),
        epilog=(
            "\b\n"
            "Defaults come from SPREZZATURE_FIGURES_HOST and "
            "SPREZZATURE_FIGURES_PORT when those are set.\n"
            "The host defaults to 127.0.0.1: pass --host 0.0.0.0 to "
            "accept connections from outside this machine."
        ),
    )
    @click.version_option(None, "-V", "--version", package_name="sprezzature-figures")
    @click.option(
        "--host",
        envvar="SPREZZATURE_FIGURES_HOST",
        default="127.0.0.1",
        show_default=True,
        help="Interface to bind.",
    )
    @click.option(
        "--port",
        envvar="SPREZZATURE_FIGURES_PORT",
        type=int,
        default=8000,
        show_default=True,
        help="Port to bind.",
    )
    def _serve(host: str, port: int) -> None:
        """Bind and serve; reached only once the arguments have parsed."""
        import uvicorn

        # Single worker: the figure registry and generator-module cache
        # (sys.modules) are process-local state, so multiple workers would
        # each hold a separate copy of it.
        uvicorn.run(app, host=host, port=port, workers=1)

    def main(argv: list[str] | None = None) -> int:
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

        Returns
        -------
        int
            Exit code: 0 once the server stops, 2 on a usage error (an
            unknown flag, a port that is not a number), as before.
        """
        try:
            _serve.main(args=argv, prog_name="sprezzature-figures-mcp", standalone_mode=False)
        except click.exceptions.Exit as done:
            return int(done.exit_code)
        except click.ClickException as error:
            error.show()
            return error.exit_code
        except click.Abort:
            return 1
        return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
