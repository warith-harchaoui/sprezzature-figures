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
from sprezzature_figures.studio.ui_strings import t


def build_history_panel(
    state: SessionState,
    *,
    on_undo: Callable[[], None],
    on_redo: Callable[[], None],
    on_export: Callable[[], None],
) -> Callable[[], None]:
    """Render the undo / redo / export toolbar; returns a `refresh()` callback
    the editor calls whenever the render or history changes (or the UI
    language toggles) so the labels and version text stay current."""
    with ui.row().classes("w-full items-center gap-2"):
        undo_btn = ui.button(icon="undo", on_click=on_undo).props("flat dense")
        with undo_btn:
            undo_tip = ui.tooltip("")
        redo_btn = ui.button(icon="redo", on_click=on_redo).props("flat dense")
        with redo_btn:
            redo_tip = ui.tooltip("")
        label = ui.label("").classes("text-sm text-gray-500")
        ui.space()
        export_btn = ui.button(icon="download", on_click=on_export).props("flat dense")

    def refresh() -> None:
        lang = state.ui_language
        # `.tooltip(text)` (the one-shot helper) creates a *new* Tooltip
        # child every call -- holding the element and setting `.text`
        # instead avoids stacking a duplicate tooltip on every toggle.
        undo_tip.text = t("undo_tooltip", lang)
        redo_tip.text = t("redo_tooltip", lang)
        export_btn.text = t("export_zip", lang)
        if state.project_dir is None:
            label.text = ""
            return
        records = list_iterations(state.project_dir)
        current = current_record(state.project_dir)
        if not records or current is None:
            label.text = t("no_versions_yet", lang)
            return
        position = [r.iteration_id for r in records].index(current.iteration_id) + 1
        label.text = t("version_of", lang, n=position, total=len(records))

    refresh()
    return refresh
