"""
Deterministic alt text for the exported figure (plan §14). Not
LLM-generated on purpose: export must work with no model active (plan
§1's "usable without an active model" requirement covers export
explicitly).

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from sprezzature_figures.core.dataset import DatasetProfile
from sprezzature_figures.core.figure_plan import FigurePlan


def generate_alt_text(plan: FigurePlan, dataset: DatasetProfile | None = None) -> str:
    # First sentence: what the figure is.
    headline = [f"{plan.figure_kind.replace('-', ' ').title()} chart"]
    if plan.title:
        headline.append(f'titled "{plan.title}"')
    if plan.subtitle:
        headline.append(f"({plan.subtitle})")
    if plan.bindings:
        roles = ", ".join(f"{role} = {', '.join(b.columns)}" for role, b in plan.bindings.items())
        headline.append(f"showing {roles}")
    sentences = [" ".join(headline).strip() + "."]

    if plan.intent.message_to_convey:
        sentences.append(f"Message: {plan.intent.message_to_convey}.")
    if dataset is not None:
        sentences.append(f"Based on {dataset.row_count} rows from {dataset.source_name}.")
    return " ".join(sentences)
