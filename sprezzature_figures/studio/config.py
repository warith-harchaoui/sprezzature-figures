"""
Sprezzature Studio configuration: constants and the (non-blocking) engine
status snapshot shown in the UI (plan §9.4).

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

APP_TITLE = "Sprezzature Studio"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080


def engine_status() -> dict[str, str]:
    """A best-effort, non-blocking snapshot of which LLM/VLM model tags
    would be used. Never probes the backend (no network call, no timeout
    risk) -- the plan explicitly says engine unavailability must never
    block app startup, so this only reports resolved configuration, not
    verified connectivity.
    """
    try:
        from best_engine_ai_helper import text_model, vision_model

        return {
            "text_model": text_model(),
            "vision_model": vision_model(),
            "status": "configured",
        }
    except Exception as exc:  # noqa: BLE001 - shown to the user, not raised
        return {"text_model": "", "vision_model": "", "status": f"unavailable: {exc}"}
