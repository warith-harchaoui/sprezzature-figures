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
from sprezzature_figures.studio.ui_strings import t

_MODE_LABEL_KEYS = {
    RalphMode.manual: "ralph_mode_manual",
    RalphMode.assisted: "ralph_mode_assisted",
    RalphMode.autopilot: "ralph_mode_autopilot",
}


def _mode_options(lang: str) -> dict[str, str]:
    # Keys stay RalphMode's own English values (what the backend expects);
    # only the displayed label is localised.
    return {m.value: t(key, lang) for m, key in _MODE_LABEL_KEYS.items()}


def build_chat_panel(
    state: SessionState,
    *,
    on_send: Callable[[str], Awaitable[RalphResult | None]],
    on_confirm: Callable[[], Awaitable[None]],
    on_cancel_pending: Callable[[], None],
) -> Callable[[], None]:
    """Render the chat log, input box, mode selector, and (when Ralph is
    holding operations back) an accept/cancel prompt. Returns a
    `refresh_language()` the editor's UI-language toggle calls."""
    mode_select = ui.select(_mode_options(state.ui_language), value=state.ralph_mode.value).classes(
        "w-full"
    )
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
                    ui.label(msg.text).classes(
                        f"{bubble_color} rounded-lg px-3 py-2 text-sm whitespace-pre-wrap"
                    ).style("max-width: 90%")

    @ui.refreshable
    def render_pending() -> None:
        pending_container.clear()
        if not state.last_pending_confirmation:
            return
        lang = state.ui_language
        with pending_container:
            ui.label(
                t("pending_confirmation", lang, n=len(state.last_pending_confirmation))
            ).classes("text-sm text-orange-700")
            for op in state.last_pending_confirmation:
                reason = getattr(op, "reason", "") or t("no_reason_given", lang)
                ui.label(f"- {op.operation_type}: {reason}").classes("text-xs text-gray-600")
            with ui.row():
                ui.button(t("accept", lang), on_click=lambda: _confirm()).props("color=primary")
                ui.button(t("cancel", lang), on_click=lambda: _cancel()).props("flat")

    async def _confirm() -> None:
        await on_confirm()
        render_pending.refresh()
        render_log.refresh()

    def _cancel() -> None:
        on_cancel_pending()
        render_pending.refresh()

    message_input = ui.input(placeholder=t("chat_placeholder", state.ui_language)).classes("w-full")

    # A "Ralph is working..." row shown only while a request is in flight, so the
    # gap between sending and the model answering (a local model can take many
    # seconds) reads as progress rather than a frozen panel.
    with ui.row().classes("w-full items-center gap-2") as thinking:
        ui.spinner(size="sm")
        thinking_label = ui.label(t("ralph_working", state.ui_language)).classes(
            "text-sm text-gray-500"
        )
    thinking.visible = False

    send_button = ui.button(t("send", state.ui_language)).props("color=primary")

    async def send() -> None:
        text = message_input.value.strip()
        if not text:
            return
        message_input.value = ""
        state.add_chat("user", text)
        render_log.refresh()
        # Lock the controls and show the spinner while Ralph runs, then always
        # restore them, even if the request raised on the way through.
        thinking.visible = True
        send_button.disable()
        message_input.disable()
        try:
            await on_send(text)
        finally:
            thinking.visible = False
            send_button.enable()
            message_input.enable()
        render_log.refresh()
        render_pending.refresh()

    send_button.on_click(send)
    message_input.on("keydown.enter", lambda _: send())

    render_log()
    render_pending()

    def refresh_language() -> None:
        lang = state.ui_language
        mode_select.set_options(_mode_options(lang), value=state.ralph_mode.value)
        placeholder = t("chat_placeholder", lang)
        message_input.props(f"placeholder='{placeholder}'")
        thinking_label.text = t("ralph_working", lang)
        send_button.text = t("send", lang)
        render_pending.refresh()

    return refresh_language
