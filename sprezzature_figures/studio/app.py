"""
Sprezzature Studio's NiceGUI application: a single page registering a
fresh SessionState per connecting client (plan §13.7 -- never a global
ProjectState shared between users).

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from nicegui import ui

from .config import APP_TITLE, DEFAULT_HOST, DEFAULT_PORT
from .pages.editor import build_editor
from .state import SessionState


def register_pages() -> None:
    @ui.page("/")
    def index() -> None:
        state = SessionState()
        build_editor(state)


def run_app(
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    show: bool = True,
    native: bool = False,
    reload: bool = False,
) -> None:
    """Start the Studio server. Blocks until interrupted."""
    register_pages()
    ui.run(host=host, port=port, title=APP_TITLE, show=show, native=native, reload=reload)
