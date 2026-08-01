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

Known gap, documented rather than silently assumed away: this engine takes
already-resolved `data` rows alongside the FigurePlan. It does not execute
FigurePlan.transformations against a live dataset (filter/sort/aggregate
over a DataFrame) -- that data-resolution step isn't owned by any commit in
the plan's own 13-commit table and is left for a future addition; the
FigurePlan's `transformations` list is still the auditable record of what
*should* apply, ready for that engine to consume later.

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
from sprezzature_figures.studio.assistant.schemas import VisualCritique

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


class RalphEngine:
    def __init__(self, client: LLMClient | None = None) -> None:
        self.client = client or default_client()

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

        Returns
        -------
        RalphResult
        """
        proposal = propose_edit(self.client, message, plan, dataset=dataset)

        applied_ops: list[FigureOperation] = []
        pending: list[FigureOperation] = []
        for op in proposal.operations:
            if proposal.requires_confirmation or requires_confirmation(op):
                pending.append(op)
            else:
                applied_ops.append(op)

        current_plan = apply_operations(plan, applied_ops)
        render_result = render_figure_to_project(
            current_plan.figure_kind, data, project_id=project_id, iteration_dir=iteration_dir, title=current_plan.title
        )

        if mode == RalphMode.manual:
            return RalphResult(
                plan=current_plan,
                render=render_result,
                applied_operations=applied_ops,
                pending_confirmation=pending,
                stopped_reason="manual_mode_no_inspection",
                rounds=0,
            )

        critique = request_critique(self.client, render_result.preview_path.read_bytes(), current_plan, dataset=dataset)

        if mode == RalphMode.assisted:
            repaired_plan, repair_ops = apply_safe_repairs(current_plan, critique, dataset=dataset)
            if repair_ops:
                current_plan = repaired_plan
                render_result = render_figure_to_project(
                    current_plan.figure_kind, data, project_id=project_id, iteration_dir=iteration_dir, title=current_plan.title
                )
            return RalphResult(
                plan=current_plan,
                render=render_result,
                critique=critique,
                applied_operations=[*applied_ops, *repair_ops],
                pending_confirmation=pending,
                stopped_reason="assisted_single_pass",
                rounds=1,
            )

        # autopilot
        history = history if history is not None else RalphHistory()
        rounds = 0
        repairs_this_call: list[FigureOperation] = []
        stopped_reason: str | None = None
        while True:
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
                current_plan.figure_kind, data, project_id=project_id, iteration_dir=iteration_dir, title=current_plan.title
            )
            critique = request_critique(
                self.client, render_result.preview_path.read_bytes(), current_plan, dataset=dataset, previous_critique=critique
            )
            rounds += 1

        return RalphResult(
            plan=current_plan,
            render=render_result,
            critique=critique,
            applied_operations=[*applied_ops, *repairs_this_call],
            pending_confirmation=pending,
            stopped_reason=stopped_reason,
            rounds=rounds,
        )
