"""
The small "which model is configured" badge (plan §9.4). Purely
informational -- never gates any action, since the plan requires the app
to start and stay usable even when the engine is unavailable.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from collections.abc import Callable

from nicegui import ui

from sprezzature_figures.studio.config import engine_status
from sprezzature_figures.studio.state import SessionState
from sprezzature_figures.studio.ui_strings import t


def build_engine_status(state: SessionState) -> Callable[[], None]:
    """Render the badge; returns a ``refresh()`` the editor's language toggle
    calls to re-render it in the other language (the underlying engine
    status itself never changes mid-session, only its label's language)."""

    @ui.refreshable
    def content() -> None:
        status = engine_status()
        ok = status["status"] == "configured"
        with ui.row().classes("items-center gap-2 text-xs text-gray-500"):
            ui.icon("circle", color="green" if ok else "orange").classes("text-xs")
            if ok:
                ui.label(
                    t(
                        "engine_models",
                        state.ui_language,
                        text=status["text_model"],
                        vision=status["vision_model"],
                    )
                )
            else:
                ui.label(t("engine_unavailable", state.ui_language, status=status["status"]))

    content()
    return content.refresh
