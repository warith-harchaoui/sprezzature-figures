"""
Recommended-figure cards (plan §13.4): after import, show the top few figure
kinds this dataset can actually fill, ranked by the deterministic engine
(`studio.recommendation`). "Use" auto-binds the best column to each required
role and builds the figure in one click, no manual role selection. The manual
kind/role controls stay available below for full control.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from collections.abc import Callable

from nicegui import ui

from sprezzature_figures.core.figure_plan import ColumnBinding, FigurePlan
from sprezzature_figures.studio.recommendation import assign_columns, infer_goal, rank
from sprezzature_figures.studio.state import SessionState
from sprezzature_figures.studio.ui_strings import t


def build_recommendation_cards(
    state: SessionState,
    *,
    on_select: Callable[[FigurePlan], None],
    limit: int = 3,
) -> None:
    """Render up to `limit` recommendation cards for the current dataset.
    `on_select` receives a ready-to-render FigurePlan when a card is used."""
    if state.dataset_profile is None:
        return
    # Read a likely analytical goal off the column shape so the top card suits
    # the data (a category+measure set leads with a bar, not a stacked area),
    # instead of the readability-only tie that falls back to registry order.
    goal = infer_goal(state.dataset_profile)
    ranked = rank(state.dataset_profile, goal=goal)[:limit]
    if not ranked:
        return

    def use(kind: str, bindings: dict[str, str]) -> None:
        plan = FigurePlan(
            figure_kind=kind,
            bindings={role: ColumnBinding(columns=[col]) for role, col in bindings.items()},
        )
        on_select(plan)

    ui.label(t("recommended", state.ui_language)).classes("text-sm font-semibold text-neutral-700")
    for definition, _score in ranked:
        bindings = assign_columns(definition, state.dataset_profile)
        if bindings is None:  # scored but not fillable (shouldn't happen post-rank)
            continue
        # Show each binding as its human role label ("Category"), not the
        # generator's internal role name ("region"), so the line reads as data
        # mapping rather than as an implementation detail.
        role_labels = {
            r.name: r.label for r in (*definition.required_roles, *definition.optional_roles)
        }
        with ui.column().classes("w-full gap-1 rounded-lg border p-3"):
            ui.label(definition.label).classes("text-sm font-medium text-neutral-900")
            if definition.description:
                ui.label(definition.description).classes("text-xs text-gray-500")
            using = ", ".join(
                f"{role_labels.get(role, role)} → {col}" for role, col in bindings.items()
            )
            ui.label(t("uses_bindings", state.ui_language, bindings=using)).classes(
                "text-xs text-gray-500"
            )
            ui.button(
                t("use", state.ui_language),
                on_click=lambda k=definition.kind, b=bindings: use(k, b),
            ).props("flat dense color=primary")
