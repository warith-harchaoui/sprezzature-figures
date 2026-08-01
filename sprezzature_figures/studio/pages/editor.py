"""
The three-pane editor (plan §13.1): data panel, figure canvas, chat panel.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from typing import Any

from nicegui import run, ui

from sprezzature_figures.core import allocate_iteration_dir, create_project
from sprezzature_figures.core.figure_plan import FigurePlan
from sprezzature_figures.core.rendering import render_figure_to_project
from sprezzature_figures.studio.components.chat_panel import build_chat_panel
from sprezzature_figures.studio.components.data_panel import build_data_panel
from sprezzature_figures.studio.components.engine_status import build_engine_status
from sprezzature_figures.studio.components.figure_canvas import build_figure_canvas
from sprezzature_figures.studio.ralph.apply import apply_operations
from sprezzature_figures.studio.ralph.engine import RalphEngine, RalphResult
from sprezzature_figures.studio.state import SessionState


def _resolve_data(state: SessionState, plan: FigurePlan) -> list[dict[str, Any]]:
    """Map the plan's role bindings back onto row dicts keyed by role name
    -- what every make_<kind> generator actually expects (see
    tools/build_figures_catalog.py's HAND_ROLES, which names required_roles
    to match each generator's DEMO_DATA field names exactly).

    Does not execute plan.transformations (see ralph.engine's documented
    gap) -- rows are passed through as imported.
    """
    return [{role: row.get(binding.column) for role, binding in plan.bindings.items()} for row in state.data]


def _summarize_result(result: RalphResult) -> str:
    parts = []
    if result.applied_operations:
        parts.append(f"Applied {len(result.applied_operations)} change(s).")
    if result.critique is not None:
        parts.append(result.critique.concise_summary or f"Critique: {result.critique.verdict}.")
    if result.pending_confirmation:
        parts.append(f"{len(result.pending_confirmation)} change(s) need your confirmation (see below).")
    return " ".join(parts) or "No changes applied."


def build_editor(state: SessionState) -> None:
    # `refresh_canvas` is assigned below, once the canvas panel is built;
    # every handler here only *calls* it, and isn't invoked itself until
    # after that assignment has happened, so the forward reference is safe.
    refresh_canvas = None

    def create_initial_render(plan: FigurePlan) -> None:
        if state.project_dir is None:
            state.project_dir = create_project(state.source_name or "untitled", source_name=state.source_name)
        iteration_dir = allocate_iteration_dir(state.project_dir)
        resolved = _resolve_data(state, plan)
        try:
            result = render_figure_to_project(
                plan.figure_kind,
                resolved,
                project_id=state.project_dir.name,
                iteration_dir=iteration_dir,
                title=plan.title or plan.figure_kind.replace("-", " ").title(),
            )
        except Exception as exc:  # noqa: BLE001 - surfaced to the user, not raised
            ui.notify(f"Render failed: {exc}", type="negative")
            return
        state.plan = plan
        state.render = result
        state.last_pending_confirmation = []
        refresh_canvas()
        ui.notify("Figure created.", type="positive")

    async def handle_send(message: str) -> RalphResult | None:
        if state.plan is None or state.project_dir is None:
            ui.notify("Create a figure first.", type="warning")
            return None
        iteration_dir = allocate_iteration_dir(state.project_dir)
        resolved = _resolve_data(state, state.plan)
        engine = RalphEngine(client=state.llm_client)
        try:
            result = await run.io_bound(
                engine.apply_user_request,
                state.plan,
                resolved,
                message,
                mode=state.ralph_mode,
                project_id=state.project_dir.name,
                iteration_dir=iteration_dir,
                dataset=state.dataset_profile,
                history=state.ralph_history,
            )
        except Exception as exc:  # noqa: BLE001 - surfaced in chat, not raised
            state.add_chat("assistant", f"Something went wrong: {exc}")
            return None

        state.plan = result.plan
        state.render = result.render
        state.last_pending_confirmation = result.pending_confirmation
        refresh_canvas()
        state.add_chat("assistant", _summarize_result(result))
        return result

    async def handle_confirm() -> None:
        if not state.last_pending_confirmation or state.plan is None or state.project_dir is None:
            return
        state.plan = apply_operations(state.plan, state.last_pending_confirmation)
        iteration_dir = allocate_iteration_dir(state.project_dir)
        resolved = _resolve_data(state, state.plan)
        try:
            result = await run.io_bound(
                render_figure_to_project,
                state.plan.figure_kind,
                resolved,
                project_id=state.project_dir.name,
                iteration_dir=iteration_dir,
                title=state.plan.title or state.plan.figure_kind,
            )
        except Exception as exc:  # noqa: BLE001 - surfaced in chat, not raised
            state.add_chat("assistant", f"Confirmed changes but re-render failed: {exc}")
            return
        state.render = result
        state.last_pending_confirmation = []
        refresh_canvas()
        state.add_chat("assistant", "Applied the confirmed change(s).")

    def handle_cancel() -> None:
        state.last_pending_confirmation = []
        state.add_chat("assistant", "Cancelled the pending change(s).")

    with ui.row().classes("w-full items-center justify-between px-6 py-4 sz-header").style(
        "position: sticky; top: 0; z-index: 10;"
    ):
        ui.label("Sprezzature Studio").classes("text-lg font-semibold text-neutral-900")
        build_engine_status()

    # flex-basis:0 (not a width-% class) so the three panes divide the row by
    # grow ratio *after* the gaps are subtracted -- Quasar's own `.row` class
    # sets `flex-wrap: wrap`, so percentage widths that sum to 100% plus gap
    # spacing overflow and wrap the third pane onto its own line; explicit
    # `flex-wrap: nowrap` plus ratio-based flex-basis avoids that entirely.
    with ui.row().classes("w-full gap-4 p-6 items-start").style(
        "height: calc(100vh - 65px); box-sizing: border-box; flex-wrap: nowrap;"
    ):
        with (
            ui.column().classes("h-full overflow-y-auto gap-4").style("flex: 1 1 0%; min-width: 0;"),
            ui.column().classes("w-full gap-3 sz-card"),
        ):
            build_data_panel(state, on_ready=create_initial_render)

        with (
            ui.column().classes("h-full overflow-y-auto").style("flex: 2 1 0%; min-width: 0;"),
            ui.column().classes("w-full sz-card"),
        ):
            refresh_canvas = build_figure_canvas(state)

        with (
            ui.column().classes("h-full overflow-y-auto gap-4").style("flex: 1 1 0%; min-width: 0;"),
            ui.column().classes("w-full gap-3 sz-card").style("height: 100%; box-sizing: border-box;"),
        ):
            build_chat_panel(
                state, on_send=handle_send, on_confirm=handle_confirm, on_cancel_pending=handle_cancel
            )
