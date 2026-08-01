"""
Ask a VLM to actually look at a rendered PNG and judge it (plan §10.3,
§11.6). The context sent is deliberately narrow: the image, the user's
intent, the figure kind and bound roles, title/subtitle, dimensions, a
statistical summary, the transformations applied, and the previous
critique if there is one -- never the full dataset.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from sprezzature_figures.core.dataset import DatasetProfile
from sprezzature_figures.core.figure_plan import FigurePlan
from sprezzature_figures.studio.assistant.client import LLMClient
from sprezzature_figures.studio.assistant.prompts import CRITIQUE_SYSTEM
from sprezzature_figures.studio.assistant.schemas import VisualCritique


def _stats_summary(dataset: DatasetProfile | None) -> str:
    if dataset is None:
        return "(no dataset profile available)"
    return "; ".join(
        f"{c.name}: {c.semantic_type}, {c.unique_count} unique, {c.null_ratio:.0%} null" for c in dataset.columns
    )


def critique_prompt(
    plan: FigurePlan,
    *,
    dataset: DatasetProfile | None,
    previous_critique: VisualCritique | None,
) -> str:
    bindings_txt = ", ".join(f"{role}={b.columns}" for role, b in plan.bindings.items()) or "(none)"
    transforms_txt = ", ".join(t.kind for t in plan.transformations) or "(none)"
    parts = [
        f"Figure kind: {plan.figure_kind}",
        f"Bound roles: {bindings_txt}",
        f"Title: {plan.title!r}",
        f"Subtitle: {plan.subtitle!r}",
        f"Canvas: {plan.style.width}x{plan.style.height}",
        f"Transformations applied: {transforms_txt}",
        f"Dataset summary: {_stats_summary(dataset)}",
        f"User's analytical goal: {plan.intent.analytical_goal}",
        f"Message to convey: {plan.intent.message_to_convey!r}",
    ]
    if previous_critique is not None:
        parts.append(f"Previous critique verdict: {previous_critique.verdict} -- {previous_critique.concise_summary}")
    parts.append(
        "\nLook at the attached PNG and judge THIS render against the intent above: "
        "score each dimension 0-100, list the concrete visual problems you can see, "
        "and propose only cosmetic safe_repairs (leave meaning-changing ideas as "
        "editorial_suggestions). Give a short concise_summary of the verdict."
    )
    return "\n".join(parts)


def request_critique(
    client: LLMClient,
    png_bytes: bytes,
    plan: FigurePlan,
    *,
    dataset: DatasetProfile | None = None,
    previous_critique: VisualCritique | None = None,
) -> VisualCritique:
    """Send the rendered PNG plus narrow context to the VLM and return its
    structured critique.
    """
    result = client.chat_vision(
        critique_prompt(plan, dataset=dataset, previous_critique=previous_critique),
        png_bytes,
        system=CRITIQUE_SYSTEM,
        response_model=VisualCritique,
        temperature=0.1,
    )
    assert isinstance(result, VisualCritique)
    return result
