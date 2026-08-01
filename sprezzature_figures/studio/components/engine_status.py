"""
The small "which model is configured" badge (plan §9.4). Purely
informational -- never gates any action, since the plan requires the app
to start and stay usable even when the engine is unavailable.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from nicegui import ui

from sprezzature_figures.studio.config import engine_status


def build_engine_status() -> None:
    status = engine_status()
    ok = status["status"] == "configured"
    with ui.row().classes("items-center gap-2 text-xs text-gray-500"):
        ui.icon("circle", color="green" if ok else "orange").classes("text-xs")
        if ok:
            ui.label(f"text: {status['text_model']} · vision: {status['vision_model']}")
        else:
            ui.label(f"engine unavailable ({status['status']}) — manual editing still works")
