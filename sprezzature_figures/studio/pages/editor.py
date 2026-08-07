"""
The three-pane editor (plan §13.1): data panel, figure canvas, chat panel.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nicegui import run, ui

from sprezzature_figures.core import (
    allocate_iteration_dir,
    create_project,
    redo,
    undo,
)
from sprezzature_figures.core.figure_plan import FigurePlan
from sprezzature_figures.core.iterations import IterationRecord, save_iteration_record
from sprezzature_figures.core.operations import SetStyleOption
from sprezzature_figures.core.projects import load_manifest
from sprezzature_figures.core.rendering import RenderResult, render_figure_to_project
from sprezzature_figures.core.transformations import apply_transformations
from sprezzature_figures.studio.components.chat_panel import build_chat_panel
from sprezzature_figures.studio.components.data_panel import build_data_panel
from sprezzature_figures.studio.components.engine_status import build_engine_status
from sprezzature_figures.studio.components.figure_canvas import build_figure_canvas
from sprezzature_figures.studio.components.history_panel import build_history_panel
from sprezzature_figures.studio.components.property_panel import build_property_panel
from sprezzature_figures.studio.export import export_project
from sprezzature_figures.studio.ralph.apply import apply_operations
from sprezzature_figures.studio.ralph.engine import RalphEngine, RalphResult
from sprezzature_figures.studio.state import SessionState

logger = logging.getLogger(__name__)


def _parent_iteration_id(project_dir: Path) -> str | None:
    """The current iteration id (zero-padded) before a new one is allocated;
    becomes the new record's parent so undo can walk back to it."""
    current = load_manifest(project_dir).current_iteration
    return f"{current:04d}" if current else None


def _record_iteration(
    project_dir: Path,
    render: RenderResult,
    *,
    parent_id: str | None,
    plan_before: FigurePlan,
    plan_after: FigurePlan,
    user_message: str | None,
    summary: str,
) -> None:
    """Persist an immutable IterationRecord for the render that just happened,
    so undo/redo/compare and the export bundle have a history to work with.
    ``allocate_iteration_dir`` already bumped the manifest's current pointer to
    ``render.iteration_id``; here we only write the record."""
    record = IterationRecord(
        iteration_id=render.iteration_id,
        parent_iteration_id=parent_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        user_message=user_message,
        assistant_summary=summary,
        plan_before=plan_before,
        plan_after=plan_after,
        render_result=render,
    )
    save_iteration_record(project_dir / "iterations" / render.iteration_id, record)


def _resolve_data_and_notes(
    state: SessionState, plan: FigurePlan
) -> tuple[list[dict[str, Any]], list[str]]:
    """Turn imported rows into what a make_<kind> generator expects, and report
    any transform that was skipped.

    First execute the plan's transformations (filter/sort/aggregate/top-N/...),
    then map each surviving row's columns onto role names via ``plan.bindings``
    (see tools/build_figures_catalog.py's HAND_ROLES, which names required roles
    to match each generator's DEMO_DATA field names exactly). Transformations
    reference the original imported column names, so they run *before* the role
    remap. A transform skipped for a missing column comes back as a note so the
    caller can show it, instead of it only reaching the log.
    """
    rows, notes = apply_transformations(state.data, plan.transformations)
    resolved = [
        {role: row.get(binding.column) for role, binding in plan.bindings.items()} for row in rows
    ]
    return resolved, [str(note) for note in notes]


def _resolve_data(state: SessionState, plan: FigurePlan) -> list[dict[str, Any]]:
    """Role-mapped rows only (drops the transform notes). See
    :func:`_resolve_data_and_notes`."""
    return _resolve_data_and_notes(state, plan)[0]


def _summarize_result(result: RalphResult) -> str:
    parts = []
    if result.applied_operations:
        parts.append(f"Applied {len(result.applied_operations)} change(s).")
    if result.critique is not None:
        parts.append(result.critique.concise_summary or f"Critique: {result.critique.verdict}.")
    if result.pending_confirmation:
        parts.append(
            f"{len(result.pending_confirmation)} change(s) need your confirmation (see below)."
        )
    summary = " ".join(parts) or "No changes applied."
    # RalphResult.notes carries best-effort warnings (a model that couldn't be
    # reached, a critique that didn't come back): surface them, never swallow.
    if result.notes:
        summary += " " + " ".join(result.notes)
    return summary


def build_editor(state: SessionState) -> None:
    # `refresh_canvas` / `refresh_history` are assigned below, once their panels
    # are built; every handler here only *calls* them, and isn't invoked itself
    # until after those assignments have happened, so the forward reference is
    # safe.
    refresh_canvas = None
    refresh_history = None
    refresh_properties = None

    def create_initial_render(plan: FigurePlan) -> None:
        if state.project_dir is None:
            state.project_dir = create_project(
                state.source_name or "untitled", source_name=state.source_name
            )
        parent = _parent_iteration_id(state.project_dir)
        iteration_dir = allocate_iteration_dir(state.project_dir)
        resolved, notes = _resolve_data_and_notes(state, plan)
        for note in notes:
            logger.warning(note)
            ui.notify(note, type="warning")
        try:
            result = render_figure_to_project(
                plan.figure_kind,
                resolved,
                project_id=state.project_dir.name,
                iteration_dir=iteration_dir,
                title=plan.title or plan.figure_kind.replace("-", " ").title(),
                language=state.language,
            )
        except Exception as exc:  # noqa: BLE001 - surfaced to the user, not raised
            ui.notify(f"Render failed: {exc}", type="negative")
            return
        _record_iteration(
            state.project_dir,
            result,
            parent_id=parent,
            plan_before=plan,
            plan_after=plan,
            user_message=None,
            summary="Figure created.",
        )
        state.plan = plan
        state.render = result
        state.last_pending_confirmation = []
        refresh_canvas()
        refresh_history()
        refresh_properties()
        ui.notify("Figure created.", type="positive")

    async def handle_send(message: str) -> RalphResult | None:
        if state.plan is None or state.project_dir is None:
            ui.notify("Create a figure first.", type="warning")
            return None
        plan_before = state.plan
        parent = _parent_iteration_id(state.project_dir)
        iteration_dir = allocate_iteration_dir(state.project_dir)
        resolved, notes = _resolve_data_and_notes(state, state.plan)
        for note in notes:
            logger.warning(note)
            ui.notify(note, type="warning")
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
                language=state.language,
            )
        except Exception as exc:  # noqa: BLE001 - surfaced in chat, not raised
            state.add_chat("assistant", f"Something went wrong: {exc}")
            return None

        summary = _summarize_result(result)
        _record_iteration(
            state.project_dir,
            result.render,
            parent_id=parent,
            plan_before=plan_before,
            plan_after=result.plan,
            user_message=message,
            summary=summary,
        )
        state.plan = result.plan
        state.render = result.render
        state.last_pending_confirmation = result.pending_confirmation
        refresh_canvas()
        refresh_history()
        refresh_properties()
        state.add_chat("assistant", summary)
        return result

    async def handle_confirm() -> None:
        if not state.last_pending_confirmation or state.plan is None or state.project_dir is None:
            return
        plan_before = state.plan
        state.plan = apply_operations(state.plan, state.last_pending_confirmation)
        parent = _parent_iteration_id(state.project_dir)
        iteration_dir = allocate_iteration_dir(state.project_dir)
        resolved, notes = _resolve_data_and_notes(state, state.plan)
        for note in notes:
            logger.warning(note)
            ui.notify(note, type="warning")
        try:
            result = await run.io_bound(
                render_figure_to_project,
                state.plan.figure_kind,
                resolved,
                project_id=state.project_dir.name,
                iteration_dir=iteration_dir,
                title=state.plan.title or state.plan.figure_kind,
                language=state.language,
            )
        except Exception as exc:  # noqa: BLE001 - surfaced in chat, not raised
            state.add_chat("assistant", f"Confirmed changes but re-render failed: {exc}")
            return
        _record_iteration(
            state.project_dir,
            result,
            parent_id=parent,
            plan_before=plan_before,
            plan_after=state.plan,
            user_message=None,
            summary="Applied the confirmed change(s).",
        )
        state.render = result
        state.last_pending_confirmation = []
        refresh_canvas()
        refresh_history()
        refresh_properties()
        state.add_chat("assistant", "Applied the confirmed change(s).")

    def handle_cancel() -> None:
        state.last_pending_confirmation = []
        state.add_chat("assistant", "Cancelled the pending change(s).")

    def handle_undo() -> None:
        if state.project_dir is None:
            return
        record = undo(state.project_dir)
        if record is None:
            ui.notify("Nothing to undo.", type="info")
            return
        state.plan = record.plan_after
        state.render = record.render_result
        refresh_canvas()
        refresh_history()
        refresh_properties()
        ui.notify("Reverted to the previous version.", type="positive")

    def handle_redo() -> None:
        if state.project_dir is None:
            return
        record = redo(state.project_dir)
        if record is None:
            ui.notify("Nothing to redo.", type="info")
            return
        state.plan = record.plan_after
        state.render = record.render_result
        refresh_canvas()
        refresh_history()
        refresh_properties()
        ui.notify("Restored the next version.", type="positive")

    async def handle_export() -> None:
        if state.plan is None or state.render is None or state.project_dir is None:
            ui.notify("Create a figure first.", type="warning")
            return
        try:
            archive = await run.io_bound(
                lambda: export_project(
                    project_name=state.source_name or state.project_dir.name,
                    plan=state.plan,
                    data=state.data,
                    render=state.render,
                    exports_dir=state.project_dir / "exports",
                    dataset=state.dataset_profile,
                )
            )
        except Exception as exc:  # noqa: BLE001 - surfaced to the user, not raised
            ui.notify(f"Export failed: {exc}", type="negative")
            return
        ui.notify(f"Exported to {archive}", type="positive")

    async def handle_style_change(option: str, value: Any) -> None:
        """Apply one style change from the property panel as a SetStyleOption,
        then re-render and record it like any other edit."""
        if state.plan is None or state.project_dir is None:
            return
        plan_before = state.plan
        op = SetStyleOption(operation_id=uuid.uuid4().hex[:8], option=option, value=value)
        new_plan = apply_operations(state.plan, [op])
        parent = _parent_iteration_id(state.project_dir)
        iteration_dir = allocate_iteration_dir(state.project_dir)
        resolved, notes = _resolve_data_and_notes(state, new_plan)
        for note in notes:
            logger.warning(note)
            ui.notify(note, type="warning")
        try:
            result = await run.io_bound(
                render_figure_to_project,
                new_plan.figure_kind,
                resolved,
                project_id=state.project_dir.name,
                iteration_dir=iteration_dir,
                title=new_plan.title or new_plan.figure_kind,
                language=state.language,
            )
        except Exception as exc:  # noqa: BLE001 - surfaced to the user, not raised
            ui.notify(f"Render failed: {exc}", type="negative")
            return
        _record_iteration(
            state.project_dir,
            result,
            parent_id=parent,
            plan_before=plan_before,
            plan_after=new_plan,
            user_message=None,
            summary=f"Set {option} to {value}.",
        )
        state.plan = new_plan
        state.render = result
        refresh_canvas()
        refresh_history()
        refresh_properties()

    dark = ui.dark_mode(value=False)
    _THEME_KEY = "sprezzature-studio-theme"

    def _paint_toggle() -> None:
        theme_toggle.set_text("🌛" if dark.value else "🌞")
        theme_toggle.props(
            f"aria-label={'Switch to light theme' if dark.value else 'Switch to dark theme'}"
        )

    def _toggle_dark() -> None:
        dark.toggle()
        _paint_toggle()
        ui.run_javascript(
            f"localStorage.setItem('{_THEME_KEY}', '{'dark' if dark.value else 'light'}')"
        )

    async def _restore_theme() -> None:
        # NiceGUI element creation runs server-side before the browser has a
        # DOM at all, so an initial ``ui.dark_mode(value=...)`` can't read
        # localStorage -- restore it right after connect instead, same
        # storage key + mechanism as the public gallery's theme.js (plain
        # localStorage, not NiceGUI's cookie-based app.storage, so no
        # storage_secret / session plumbing needed for one boolean).
        pref = await ui.run_javascript(f"localStorage.getItem('{_THEME_KEY}')")
        if pref == "dark":
            dark.value = True
            _paint_toggle()

    with (
        ui.row()
        .classes("w-full items-center justify-between px-6 py-4 sz-header")
        .style("position: sticky; top: 0; z-index: 10;")
    ):
        ui.label("Sprezzature Studio").classes("text-lg font-semibold text-neutral-900")
        with ui.row().classes("items-center gap-3"):
            build_engine_status()
            theme_toggle = (
                ui.button("🌞", on_click=_toggle_dark)
                .props("flat round dense aria-label='Switch to dark theme'")
                .classes("text-lg")
            )

    ui.timer(0.01, _restore_theme, once=True)

    # flex-basis:0 (not a width-% class) so the three panes divide the row by
    # grow ratio *after* the gaps are subtracted -- Quasar's own `.row` class
    # sets `flex-wrap: wrap`, so percentage widths that sum to 100% plus gap
    # spacing overflow and wrap the third pane onto its own line; explicit
    # `flex-wrap: nowrap` plus ratio-based flex-basis avoids that entirely.
    with (
        ui.row()
        .classes("w-full gap-4 p-6 items-start")
        .style("height: calc(100vh - 65px); box-sizing: border-box; flex-wrap: nowrap;")
    ):
        with (
            ui.column().classes("h-full overflow-y-auto gap-4").style("flex: 1 1 0%; min-width: 0;")
        ):
            with ui.column().classes("w-full gap-3 sz-card"):
                build_data_panel(state, on_ready=create_initial_render)
            with ui.column().classes("w-full gap-3 sz-card"):
                refresh_properties = build_property_panel(state, on_change=handle_style_change)

        with (
            ui.column()
            .classes("h-full overflow-y-auto gap-3")
            .style("flex: 2 1 0%; min-width: 0;"),
            ui.column().classes("w-full gap-3 sz-card"),
        ):
            refresh_canvas = build_figure_canvas(state)
            refresh_history = build_history_panel(
                state, on_undo=handle_undo, on_redo=handle_redo, on_export=handle_export
            )

        with (
            ui.column()
            .classes("h-full overflow-y-auto gap-4")
            .style("flex: 1 1 0%; min-width: 0;"),
            ui.column()
            .classes("w-full gap-3 sz-card")
            .style("height: 100%; box-sizing: border-box;"),
        ):
            build_chat_panel(
                state,
                on_send=handle_send,
                on_confirm=handle_confirm,
                on_cancel_pending=handle_cancel,
            )
