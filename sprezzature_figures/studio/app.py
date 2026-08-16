"""
Sprezzature Studio's NiceGUI (the Python web-UI framework it's built on)
application: a single page registering a fresh SessionState per connecting
client (plan §13.7), so two people using the Studio at once never see or
edit a shared ProjectState by accident.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from nicegui import app, ui

from ..fonts import FONTS_DIR, MONO_STACK, SANS_STACK, web_font_faces_css
from .config import APP_TITLE, DEFAULT_HOST, DEFAULT_PORT
from .pages.editor import build_editor
from .state import SessionState
from .theme import theme_css

# House typography: the same self-hosted Roboto family bundled for the
# figures (sprezzature_figures.fonts) -- self-hosted, not a Google Fonts CDN
# fetch, so the Studio UI looks identical online or fully offline.
_FONTS_URL_PREFIX = "/sprezzature-fonts"


def register_fonts() -> None:
    """Serve the bundled Roboto/Roboto Serif/Roboto Mono WOFF2 files as
    static assets and inject `@font-face` + base font-family CSS into every
    page's `<head>`. Idempotent-safe to call once at app startup, before any
    page is registered.
    """
    app.add_static_files(_FONTS_URL_PREFIX, str(FONTS_DIR))
    css = web_font_faces_css(_FONTS_URL_PREFIX)
    ui.add_head_html(
        f"<style>{css}"
        f"html,body,.nicegui-content,.q-field,.q-btn{{font-family:{SANS_STACK} !important;}}"
        f"code,pre,.font-mono{{font-family:{MONO_STACK} !important;}}"
        "</style>",
        shared=True,
    )


def register_theme() -> None:
    """Inject the Studio's visual language (see `theme.py`): the same
    neutral/brand-blue palette and rounded-card look as the public
    harchaoui.org/warith/sprezzature site, backing the Tailwind-style
    utility classes the components already use (this NiceGUI build ships no
    Tailwind CSS itself, so those classes were previously silent no-ops).
    """
    ui.add_head_html(f"<style>{theme_css()}</style>", shared=True)


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
    register_fonts()
    register_theme()
    register_pages()
    ui.run(host=host, port=port, title=APP_TITLE, show=show, native=native, reload=reload)
