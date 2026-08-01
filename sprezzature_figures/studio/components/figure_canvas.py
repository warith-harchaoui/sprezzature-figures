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


def build_figure_canvas(state: SessionState) -> Callable[[], None]:
    """Render the figure canvas; returns a `refresh()` callback the caller
    invokes after a new render lands in `state.render`.

    Each render lands in its own iteration directory (see
    core.projects.allocate_iteration_dir), so the preview path itself
    changes from render to render -- no extra cache-busting needed for
    the browser to pick up a fresh image.
    """
    with ui.column().classes("w-full items-center gap-2"):
        image = ui.image().classes("max-w-full border rounded-lg bg-neutral-50").style("min-height: 200px")
        caption = ui.label("No render yet -- import data and create a figure.").classes("text-sm text-gray-500")

    def refresh() -> None:
        if state.render is None:
            image.set_source("")
            caption.text = "No render yet -- import data and create a figure."
            return
        image.set_source(state.render.preview_path)
        caption.text = f"{state.render.figure_kind} · {state.render.width}x{state.render.height}"

    refresh()
    return refresh
