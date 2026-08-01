"""
Right-hand chat pane (plan §13.1 "Chat Ralph"): message log, mode
selector, and pending-confirmation controls for operations Ralph held
back per plan §11.3.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from nicegui import ui

from sprezzature_figures.studio.ralph.engine import RalphMode, RalphResult
from sprezzature_figures.studio.state import SessionState


def build_chat_panel(
    state: SessionState,
    *,
    on_send: Callable[[str], Awaitable[RalphResult | None]],
    on_confirm: Callable[[], Awaitable[None]],
    on_cancel_pending: Callable[[], None],
) -> None:
    """Render the chat log, input box, mode selector, and (when Ralph is
    holding operations back) an accept/cancel prompt.
    """
    mode_select = ui.select(
        {m.value: m.value for m in RalphMode}, value=state.ralph_mode.value, label="Ralph mode"
    ).classes("w-full")
    mode_select.on_value_change(lambda e: setattr(state, "ralph_mode", RalphMode(e.value)))

    log_container = ui.column().classes("w-full gap-1 overflow-y-auto").style("max-height: 50vh")
    pending_container = ui.column().classes("w-full")

    @ui.refreshable
    def render_log() -> None:
        log_container.clear()
        with log_container:
            for msg in state.chat_log:
                align = "items-end" if msg.role == "user" else "items-start"
                bubble_color = "bg-blue-100" if msg.role == "user" else "bg-gray-100"
                with ui.column().classes(f"w-full {align}"):
                    ui.label(msg.text).classes(f"{bubble_color} rounded px-3 py-2 max-w-[90%] text-sm whitespace-pre-wrap")

    @ui.refreshable
    def render_pending() -> None:
        pending_container.clear()
        if not state.last_pending_confirmation:
            return
        with pending_container:
            ui.label(
                f"Ralph wants to apply {len(state.last_pending_confirmation)} operation(s) "
                "that change what the data shows -- confirm to proceed:"
            ).classes("text-sm text-orange-700")
            for op in state.last_pending_confirmation:
                ui.label(f"- {op.operation_type}: {getattr(op, 'reason', '') or 'no reason given'}").classes(
                    "text-xs text-gray-600"
                )
            with ui.row():
                ui.button("Accept", on_click=lambda: _confirm()).props("color=primary")
                ui.button("Cancel", on_click=lambda: _cancel()).props("flat")

    async def _confirm() -> None:
        await on_confirm()
        render_pending.refresh()
        render_log.refresh()

    def _cancel() -> None:
        on_cancel_pending()
        render_pending.refresh()

    message_input = ui.input(placeholder="Ask Ralph to change something...").classes("w-full")

    async def send() -> None:
        text = message_input.value.strip()
        if not text:
            return
        message_input.value = ""
        state.add_chat("user", text)
        render_log.refresh()
        await on_send(text)
        render_log.refresh()
        render_pending.refresh()

    message_input.on("keydown.enter", lambda _: send())
    ui.button("Send", on_click=send).props("color=primary")

    render_log()
    render_pending()
