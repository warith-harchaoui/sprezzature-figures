"""
Center-pane toolbar under the figure: undo / redo through the iteration
history, and export the current figure as a reproducible `.sprezzature.zip`
(plan §12 history, §14 export). The backends (`core.history`,
`studio.export`) are what these buttons drive.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from collections.abc import Callable

from nicegui import ui

from sprezzature_figures.core import current_record, list_iterations
from sprezzature_figures.studio.state import SessionState


def build_history_panel(
    state: SessionState,
    *,
    on_undo: Callable[[], None],
    on_redo: Callable[[], None],
    on_export: Callable[[], None],
) -> Callable[[], None]:
    """Render the undo / redo / export toolbar; returns a `refresh()` callback
    the editor calls whenever the render or history changes so the version
    label stays current."""
    with ui.row().classes("w-full items-center gap-2"):
        ui.button(icon="undo", on_click=on_undo).props("flat dense").tooltip("Undo")
        ui.button(icon="redo", on_click=on_redo).props("flat dense").tooltip("Redo")
        label = ui.label("").classes("text-sm text-gray-500")
        ui.space()
        ui.button("Export .zip", icon="download", on_click=on_export).props("flat dense")

    def refresh() -> None:
        if state.project_dir is None:
            label.text = ""
            return
        records = list_iterations(state.project_dir)
        current = current_record(state.project_dir)
        if not records or current is None:
            label.text = "No versions yet"
            return
        position = [r.iteration_id for r in records].index(current.iteration_id) + 1
        label.text = f"Version {position} of {len(records)}"

    refresh()
    return refresh
