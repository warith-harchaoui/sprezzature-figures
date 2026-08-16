"""
CLI entry point for the ``sprezzature-studio`` command.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import argparse

from .config import DEFAULT_HOST, DEFAULT_PORT


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="sprezzature-studio",
        description="Launch Sprezzature Studio, the chat-driven figure editor.",
    )
    parser.add_argument(
        "--host", default=DEFAULT_HOST, help=f"Bind host (default: {DEFAULT_HOST})."
    )
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help=f"Bind port (default: {DEFAULT_PORT})."
    )
    parser.add_argument("--no-browser", action="store_true", help="Don't auto-open a browser tab.")
    parser.add_argument(
        "--native",
        action="store_true",
        help="Run as a native desktop window instead of a browser tab.",
    )
    args = parser.parse_args()

    from .app import (
        run_app,  # deferred: keep `sprezzature-studio --help` fast and nicegui-import-free until needed
    )

    run_app(host=args.host, port=args.port, show=not args.no_browser, native=args.native)


if __name__ == "__main__":
    main()
