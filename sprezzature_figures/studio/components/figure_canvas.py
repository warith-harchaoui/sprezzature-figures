"""
Center pane: the current figure's rendered preview (plan §13.1 "Figure").

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from collections.abc import Callable

from nicegui import ui

from sprezzature_figures.studio.state import SessionState
from sprezzature_figures.studio.ui_strings import t


def build_figure_canvas(state: SessionState) -> Callable[[], None]:
    """Render the figure canvas; returns a `refresh()` callback the caller
    invokes after a new render lands in `state.render` -- and that the
    editor's language toggle also calls, since the "no render yet" caption
    is chrome text, not figure content.

    Each render lands in its own iteration directory (see
    core.projects.allocate_iteration_dir), so the preview path itself
    changes from render to render -- no extra cache-busting needed for
    the browser to pick up a fresh image.
    """
    with ui.column().classes("w-full items-center gap-2"):
        image = (
            ui.image()
            .classes("max-w-full border rounded-lg bg-neutral-50")
            .style("min-height: 200px")
        )
        caption = ui.label(t("no_render_yet", state.ui_language)).classes("text-sm text-gray-500")

    def refresh() -> None:
        if state.render is None:
            image.set_source("")
            caption.text = t("no_render_yet", state.ui_language)
            return
        image.set_source(state.render.preview_path)
        kind = state.render.figure_kind.replace("-", " ").replace("_", " ").title()
        caption.text = f"{kind} · {state.render.width} × {state.render.height} px"

    refresh()
    return refresh
