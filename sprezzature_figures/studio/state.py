"""
Per-browser-session state. One SessionState per connecting client, never a
module-level global (plan §13.7: "never a ProjectState shared between
users"). Each `@ui.page` handler in pages/ creates its own instance,
captured in that handler's closure.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sprezzature_figures.core import DatasetProfile, FigurePlan
from sprezzature_figures.core.operations import FigureOperation
from sprezzature_figures.core.rendering import RenderResult
from sprezzature_figures.studio.assistant.client import LLMClient, default_client
from sprezzature_figures.studio.i18n import DEFAULT_LANGUAGE
from sprezzature_figures.studio.ralph.engine import RalphMode
from sprezzature_figures.studio.ralph.history import RalphHistory
from sprezzature_figures.studio.ui_strings import DEFAULT_UI_LANGUAGE


@dataclass
class ChatMessage:
    role: str  # "user" | "assistant"
    text: str


@dataclass
class SessionState:
    """Everything one browser tab's editing session needs. Constructing an
    instance never touches the filesystem or the network -- a project
    directory and LLM client are only created/used once the user actually
    imports data or sends a chat message.
    """

    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    llm_client: LLMClient = field(default_factory=default_client)
    ralph_history: RalphHistory = field(default_factory=RalphHistory)
    ralph_mode: RalphMode = RalphMode.assisted

    project_dir: Path | None = None
    source_name: str = ""
    dataset_profile: DatasetProfile | None = None
    data: list[dict[str, Any]] = field(default_factory=list)
    # The single chrome language ("fr"/"en") every language-aware figure
    # renders in for this session -- French until a CSV is imported, then
    # re-detected from that CSV's column names (see studio/i18n.py) so one
    # dataset never mixes languages across its figures.
    language: str = DEFAULT_LANGUAGE
    # Studio's own interface language (buttons, labels, notifications) --
    # a separate, user-toggled setting (see ui_strings.py), never
    # auto-detected, and never mixed up with ``language`` above.
    ui_language: str = DEFAULT_UI_LANGUAGE

    plan: FigurePlan | None = None
    render: RenderResult | None = None
    chat_log: list[ChatMessage] = field(default_factory=list)
    last_error: str | None = None
    last_pending_confirmation: list[FigureOperation] = field(default_factory=list)

    def add_chat(self, role: str, text: str) -> None:
        self.chat_log.append(ChatMessage(role=role, text=text))

    @property
    def has_data(self) -> bool:
        return bool(self.data) and self.dataset_profile is not None

    @property
    def has_render(self) -> bool:
        return self.render is not None
