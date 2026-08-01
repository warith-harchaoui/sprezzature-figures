"""
Tests for sprezzature_figures.studio.ralph.repair (applying a critique's
safe repairs) and .history (RalphHistory bookkeeping).

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from sprezzature_figures.core.figure_plan import FigurePlan
from sprezzature_figures.core.operations import BindColumn, SetStyleOption
from sprezzature_figures.studio.assistant.schemas import VisualCritique
from sprezzature_figures.studio.ralph.history import RalphHistory
from sprezzature_figures.studio.ralph.repair import apply_safe_repairs, safe_repairs_from_critique


def _plan() -> FigurePlan:
    return FigurePlan(figure_kind="bar")


def _critique(safe_repairs, **overrides) -> VisualCritique:
    defaults = {
        "verdict": "needs_changes",
        "message_alignment_score": 70, "readability_score": 70, "visual_hierarchy_score": 70,
        "accessibility_score": 70, "data_fidelity_score": 70, "safe_repairs": safe_repairs,
    }
    defaults.update(overrides)
    return VisualCritique(**defaults)


def test_safe_repairs_from_critique_filters_by_policy() -> None:
    safe = SetStyleOption(operation_id="s1", option="font_scale", value=1.3)
    unsafe = BindColumn(operation_id="u1", role="x", columns=["a"])  # not a safe repair type
    critique = _critique([safe, unsafe])
    approved = safe_repairs_from_critique(critique)
    assert [op.operation_id for op in approved] == ["s1"]


def test_apply_safe_repairs_applies_only_approved_operations() -> None:
    safe = SetStyleOption(operation_id="s1", option="font_scale", value=1.6)
    critique = _critique([safe])
    plan, applied = apply_safe_repairs(_plan(), critique)
    assert plan.style.font_scale == 1.6
    assert [op.operation_id for op in applied] == ["s1"]


def test_apply_safe_repairs_no_op_when_nothing_approved() -> None:
    critique = _critique([BindColumn(operation_id="u1", role="x", columns=["a"])])
    plan, applied = apply_safe_repairs(_plan(), critique)
    assert plan == _plan()
    assert applied == []


def test_ralph_history_tracks_signature_and_score() -> None:
    history = RalphHistory()
    assert history.last_signature_set() is None
    assert history.last_score_total() is None
    assert history.repair_count() == 0

    c1 = _critique([], verdict="needs_changes")
    history.record(c1, [SetStyleOption(operation_id="s1", option="font_scale", value=1.2)])
    assert history.repair_count() == 1
    assert history.last_score_total() == 350

    c2 = _critique([], verdict="satisfied")
    history.record(c2, [])
    assert history.repair_count() == 1  # second round applied no repairs
    assert history.last_signature_set() == frozenset()
