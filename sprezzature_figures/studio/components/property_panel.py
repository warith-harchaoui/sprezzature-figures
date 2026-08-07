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
from sprezzature_figures.studio.ui_strings import t

# Preset font scales, labelled, so the control is a clean discrete choice
# rather than a free number that re-renders on every keystroke. Keys are
# translation lookups (ui_strings.py), resolved to display text per language
# in `_font_scale_options`/`_legend_options` below -- the dict *keys* fed to
# `ui.select` (0.8, "top", ...) are what StyleOptions actually stores and
# never change with the UI language, only the displayed label does.
_FONT_SCALES = {
    0.8: "font_scale_small",
    1.0: "font_scale_normal",
    1.2: "font_scale_large",
    1.4: "font_scale_larger",
    1.6: "font_scale_huge",
}
_LEGEND_POSITIONS = {
    "top": "legend_top",
    "bottom": "legend_bottom",
    "left": "legend_left",
    "right": "legend_right",
    "none": "legend_none",
}


def _font_scale_options(lang: str) -> dict[float, str]:
    return {scale: t(key, lang) for scale, key in _FONT_SCALES.items()}


def _legend_options(lang: str) -> dict[str, str]:
    return {value: t(key, lang) for value, key in _LEGEND_POSITIONS.items()}


def build_property_panel(
    state: SessionState,
    *,
    on_change: Callable[[str, Any], Any],
) -> Callable[[], None]:
    """Render the style controls; returns a `refresh()` the editor calls after
    any plan change, and after a UI-language toggle, so the controls mirror
    the current `StyleOptions` and are labelled in the current language.

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
        heading = ui.label(t("style_heading", state.ui_language)).classes(
            "text-sm font-semibold text-neutral-700"
        )
        font = ui.select(
            _font_scale_options(state.ui_language), on_change=emit("font_scale")
        ).classes("w-full")
        legend = ui.select(
            _legend_options(state.ui_language), on_change=emit("legend_position")
        ).classes("w-full")
        grid = ui.switch(on_change=emit("show_grid"))
        labels = ui.switch(on_change=emit("show_labels"))

    def refresh() -> None:
        lang = state.ui_language
        has_figure = state.plan is not None
        style = state.plan.style if has_figure else StyleOptions()
        suppress["active"] = True
        try:
            heading.text = t("style_heading", lang)
            font.props(f"label='{t('text_size_label', lang)}'")
            legend.props(f"label='{t('legend_label', lang)}'")
            grid.set_text(t("grid_label", lang))
            labels.set_text(t("value_labels_label", lang))
            # Snap the font scale to the nearest preset so the select has a value.
            font_value = min(_FONT_SCALES, key=lambda s: abs(s - style.font_scale))
            font.set_options(_font_scale_options(lang), value=font_value)
            legend.set_options(_legend_options(lang), value=style.legend_position)
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
