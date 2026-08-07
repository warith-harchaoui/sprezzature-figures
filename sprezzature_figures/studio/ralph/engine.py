"""
RalphEngine: the interactive loop from plan §11.1.

    demande utilisateur
    -> interprétation structurée (assistant.edit.propose_edit)
    -> validation (core.validate_operation, already applied inside propose_edit)
    -> modification du FigurePlan (apply_operation)
    -> rendu (core.render_figure_to_project)
    -> inspection du rendu (ralph.critic.request_critique)
    -> critique structurée (VisualCritique)
    -> éventuelle réparation sûre (ralph.repair.apply_safe_repairs)
    -> nouveau rendu

Ralph never touches the rendered image directly -- every change goes
through a FigureOperation applied to the FigurePlan, then a fresh render
(plan §1.3).

This engine takes already-resolved `data` rows alongside the FigurePlan:
the caller resolves them via ``pages.editor._resolve_data``, which now
executes ``FigurePlan.transformations`` (filter/sort/aggregate/...) against
the imported rows before mapping columns onto role names -- see
``core.transformations.apply_transformations``. The transformations list
remains the auditable record of what was applied.

The two model-facing steps (interpret and visually inspect) are wrapped so
a live model failing -- empty/malformed JSON, a timeout, an unreachable
backend -- degrades gracefully (the figure still renders, the reason is
reported in ``RalphResult.notes``) instead of crashing the user's turn
(plan §11.4, §16.4).

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from sprezzature_figures.core.dataset import DatasetProfile
from sprezzature_figures.core.figure_plan import FigurePlan
from sprezzature_figures.core.operations import FigureOperation
from sprezzature_figures.core.rendering import RenderResult, render_figure_to_project
from sprezzature_figures.studio.assistant.client import LLMClient, default_client
from sprezzature_figures.studio.assistant.edit import propose_edit
from sprezzature_figures.studio.assistant.schemas import EditProposal, VisualCritique

from .apply import apply_operations
from .critic import request_critique
from .history import RalphHistory
from .policy import requires_confirmation
from .repair import apply_safe_repairs, safe_repairs_from_critique
from .stopping import should_stop


class RalphMode(str, Enum):
    manual = "manual"
    assisted = "assisted"
    autopilot = "autopilot"


class RalphResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    plan: FigurePlan
    render: RenderResult
    critique: VisualCritique | None = None
    applied_operations: list[FigureOperation] = Field(default_factory=list)
    pending_confirmation: list[FigureOperation] = Field(default_factory=list)
    stopped_reason: str | None = None
    rounds: int = 0
    notes: list[str] = Field(default_factory=list)


class RalphEngine:
    def __init__(self, client: LLMClient | None = None) -> None:
        self.client = client or default_client()

    def _try_propose(
        self, message: str, plan: FigurePlan, dataset: DatasetProfile | None
    ) -> tuple[EditProposal, str | None]:
        """Interpret the request into an EditProposal. A model failure here
        (bad JSON, timeout, backend down) degrades to an empty proposal plus
        a note -- the current figure still renders unchanged."""
        try:
            return propose_edit(self.client, message, plan, dataset=dataset), None
        except Exception as exc:  # noqa: BLE001 - any model/network failure degrades, never crashes the turn
            return (
                EditProposal(summary="", operations=[], expected_effect="", requires_confirmation=False),
                f"Could not interpret the request ({exc}). The figure is unchanged.",
            )

    def _try_critique(
        self,
        png_bytes: bytes,
        plan: FigurePlan,
        dataset: DatasetProfile | None,
        previous_critique: VisualCritique | None = None,
    ) -> tuple[VisualCritique | None, str | None]:
        """Visually inspect the render. A model failure degrades to no
        critique plus a note -- the figure still renders and is returned."""
        try:
            critique = request_critique(
                self.client, png_bytes, plan, dataset=dataset, previous_critique=previous_critique
            )
            return critique, None
        except Exception as exc:  # noqa: BLE001 - visual inspection is best-effort, never fatal
            return None, f"Visual inspection unavailable ({exc})."

    def apply_user_request(
        self,
        plan: FigurePlan,
        data: list[dict[str, Any]],
        message: str,
        *,
        mode: RalphMode,
        project_id: str,
        iteration_dir: Path,
        dataset: DatasetProfile | None = None,
        history: RalphHistory | None = None,
        language: str | None = None,
    ) -> RalphResult:
        """Interpret `message` against `plan`, apply what's safe to apply
        automatically, render, and (in assisted/autopilot mode) inspect and
        safely repair the result.

        Parameters
        ----------
        plan : FigurePlan
            The current figure plan.
        data : list[dict[str, Any]]
            Rows to render (already resolved from the dataset + plan's
            transformations -- see module docstring).
        message : str
            The user's chat message.
        mode : RalphMode
            manual: apply the explicit request only, render, report issues
            without fixing them.
            assisted: apply the explicit request, render, inspect, apply
            safe repairs once, surface editorial suggestions.
            autopilot: up to two safe-repair passes, stopping per plan §11.5.
        project_id, iteration_dir :
            Where to render (see core.projects.allocate_iteration_dir).
        dataset : DatasetProfile or None
            Sent to the model for column-existence validation and to the
            critic as context; never the raw rows.
        history : RalphHistory or None
            Carries stopping-criteria state across calls; pass the same
            instance back in for a multi-turn session, or omit for a
            one-shot call.
        language : str or None
            Forwarded to every render_figure_to_project() call in this
            method (see studio/state.SessionState.language); None leaves
            each generator on its own default ("en").

        Returns
        -------
        RalphResult
        """
        proposal, edit_note = self._try_propose(message, plan, dataset)
        notes: list[str] = [edit_note] if edit_note else []

        applied_ops: list[FigureOperation] = []
        pending: list[FigureOperation] = []
        for op in proposal.operations:
            if proposal.requires_confirmation or requires_confirmation(op):
                pending.append(op)
            else:
                applied_ops.append(op)

        current_plan = apply_operations(plan, applied_ops)
        render_result = render_figure_to_project(
            current_plan.figure_kind, data, project_id=project_id, iteration_dir=iteration_dir,
            title=current_plan.title, language=language,
        )

        if mode == RalphMode.manual:
            return RalphResult(
                plan=current_plan,
                render=render_result,
                applied_operations=applied_ops,
                pending_confirmation=pending,
                stopped_reason="manual_mode_no_inspection",
                rounds=0,
                notes=notes,
            )

        critique, crit_note = self._try_critique(
            render_result.preview_path.read_bytes(), current_plan, dataset
        )
        if crit_note:
            notes.append(crit_note)

        if mode == RalphMode.assisted:
            # No critique (model failed) -> return the render as-is, reason noted.
            if critique is None:
                return RalphResult(
                    plan=current_plan,
                    render=render_result,
                    applied_operations=applied_ops,
                    pending_confirmation=pending,
                    stopped_reason="critique_unavailable",
                    rounds=0,
                    notes=notes,
                )
            repaired_plan, repair_ops = apply_safe_repairs(current_plan, critique, dataset=dataset)
            if repair_ops:
                current_plan = repaired_plan
                render_result = render_figure_to_project(
                    current_plan.figure_kind, data, project_id=project_id, iteration_dir=iteration_dir,
                    title=current_plan.title, language=language,
                )
            return RalphResult(
                plan=current_plan,
                render=render_result,
                critique=critique,
                applied_operations=[*applied_ops, *repair_ops],
                pending_confirmation=pending,
                stopped_reason="assisted_single_pass",
                rounds=1,
                notes=notes,
            )

        # autopilot
        history = history if history is not None else RalphHistory()
        rounds = 0
        repairs_this_call: list[FigureOperation] = []
        stopped_reason: str | None = None
        while critique is not None:
            remaining = safe_repairs_from_critique(critique, dataset=dataset)
            stop, reason = should_stop(
                critique=critique,
                repairs_applied_so_far=history.repair_count(),
                previous_signature_set=history.last_signature_set(),
                previous_score_total=history.last_score_total(),
                remaining_safe_repairs=len(remaining),
            )
            history.record(critique, [])
            if stop:
                stopped_reason = reason
                break
            current_plan, repair_ops = apply_safe_repairs(current_plan, critique, dataset=dataset)
            history.rounds[-1].applied_operations = repair_ops
            repairs_this_call.extend(repair_ops)
            render_result = render_figure_to_project(
                current_plan.figure_kind, data, project_id=project_id, iteration_dir=iteration_dir,
                title=current_plan.title, language=language,
            )
            critique, crit_note = self._try_critique(
                render_result.preview_path.read_bytes(), current_plan, dataset, previous_critique=critique
            )
            if crit_note:
                notes.append(crit_note)
            rounds += 1

        # A re-critique that came back empty ends the loop as gracefully as a
        # satisfied verdict does -- the last successful render still stands.
        if stopped_reason is None:
            stopped_reason = "critique_unavailable"

        return RalphResult(
            plan=current_plan,
            render=render_result,
            critique=critique,
            applied_operations=[*applied_ops, *repairs_this_call],
            pending_confirmation=pending,
            stopped_reason=stopped_reason,
            rounds=rounds,
            notes=notes,
        )
