"""
CLI entry point for the ``sprezzature-studio`` command.

Click, like the rest of the suite since 2026-10-25. The deferred import of
``run_app`` is the load-bearing detail and survives the rewrite: nicegui is
heavy, and ``sprezzature-studio --help`` should answer without paying for it.

Author
------
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

import click

from .config import DEFAULT_HOST, DEFAULT_PORT


@click.command(
    context_settings={"help_option_names": ["-h", "--help"]},
    help="Launch Sprezzature Studio, the chat-driven figure editor.",
    epilog=(
        "Shell completion:\n\n"
        "  \b\n"
        '  eval "$(_SPREZZATURE_STUDIO_COMPLETE=bash_source sprezzature-studio)"   # bash\n'
        '  eval "$(_SPREZZATURE_STUDIO_COMPLETE=zsh_source sprezzature-studio)"    # zsh\n'
    ),
)
@click.version_option(package_name="sprezzature-figures")
@click.option("--host", default=DEFAULT_HOST, show_default=True, help="Bind host.")
@click.option("--port", type=int, default=DEFAULT_PORT, show_default=True, help="Bind port.")
@click.option("--no-browser", is_flag=True, help="Don't auto-open a browser tab.")
@click.option(
    "--native", is_flag=True, help="Run as a native desktop window instead of a browser tab."
)
def main(host: str, port: int, no_browser: bool, native: bool) -> None:
    """Launch the studio."""
    # Deferred on purpose: keeps `--help` fast and nicegui-import-free until a
    # run is actually asked for.
    from .app import run_app

    run_app(host=host, port=port, show=not no_browser, native=native)


if __name__ == "__main__":
    main()
