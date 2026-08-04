"""
Left pane: direct controls for the common cosmetic style options, so a user
can tweak a figure without going through the chat (plan §13.1 "Réglages").
Each change is applied as a `SetStyleOption` and re-rendered by the editor.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from nicegui import ui

from sprezzature_figures.core.figure_plan import StyleOptions
from sprezzature_figures.studio.state import SessionState

# Preset font scales, labelled, so the control is a clean discrete choice
# rather than a free number that re-renders on every keystroke.
_FONT_SCALES = {0.8: "Small", 1.0: "Normal", 1.2: "Large", 1.4: "Larger", 1.6: "Huge"}
_LEGEND_POSITIONS = ["top", "bottom", "left", "right", "none"]


def build_property_panel(
    state: SessionState,
    *,
    on_change: Callable[[str, Any], Any],
) -> Callable[[], None]:
    """Render the style controls; returns a `refresh()` the editor calls after
    any plan change so the controls mirror the current `StyleOptions`.

    `on_change(option, value)` is invoked only for genuine user edits;
    programmatic updates during `refresh()` are suppressed so setting a control
    from the current plan never loops back into a re-render.
    """
    suppress = {"active": False}

    def emit(option: str) -> Callable[[Any], None]:
        def handler(event: Any) -> None:
            if suppress["active"]:
                return
            on_change(option, event.value)

        return handler

    with ui.column().classes("w-full gap-2"):
        ui.label("Style").classes("text-sm font-semibold text-neutral-700")
        font = ui.select(_FONT_SCALES, label="Text size", on_change=emit("font_scale")).classes("w-full")
        legend = ui.select(
            _LEGEND_POSITIONS, label="Legend", on_change=emit("legend_position")
        ).classes("w-full")
        grid = ui.switch("Grid", on_change=emit("show_grid"))
        labels = ui.switch("Value labels", on_change=emit("show_labels"))

    def refresh() -> None:
        has_figure = state.plan is not None
        style = state.plan.style if has_figure else StyleOptions()
        suppress["active"] = True
        try:
            # Snap the font scale to the nearest preset so the select has a value.
            font.value = min(_FONT_SCALES, key=lambda s: abs(s - style.font_scale))
            legend.value = style.legend_position
            grid.value = style.show_grid
            labels.value = style.show_labels
            # Grey the controls out until there is a figure to restyle: editing
            # them before then is a silent no-op (the editor's handler bails when
            # there is no plan), which reads as a broken control.
            for control in (font, legend, grid, labels):
                control.set_enabled(has_figure)
        finally:
            suppress["active"] = False

    refresh()
    return refresh
