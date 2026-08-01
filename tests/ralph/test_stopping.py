"""
Tests for sprezzature_figures.studio.ralph.stopping: the plan §11.5
stopping criteria and issue-signature computation.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import pytest

from sprezzature_figures.studio.assistant.schemas import VisualCritique, VisualIssue
from sprezzature_figures.studio.ralph.stopping import (
    has_blocking_issues,
    issue_signature,
    score_total,
    should_stop,
    signature_set,
)


def _critique(**overrides) -> VisualCritique:
    defaults = {
        "verdict": "needs_changes",
        "message_alignment_score": 70,
        "readability_score": 70,
        "visual_hierarchy_score": 70,
        "accessibility_score": 70,
        "data_fidelity_score": 70,
        "issues": [],
        "safe_repairs": [],
    }
    defaults.update(overrides)
    return VisualCritique(**defaults)


def _issue(category: str = "contrast", severity: str = "high", observation: str = "x") -> VisualIssue:
    return VisualIssue(category=category, severity=severity, observation=observation)


def test_issue_signature_normalizes_and_discriminates() -> None:
    # Same problem, different whitespace/case -> identical signature.
    assert issue_signature(_issue(category="labeling", observation="  Labels   Too Small  ")) == issue_signature(
        _issue(category="labeling", observation="labels too small")
    )
    # Category or severity changing -> distinct signature.
    base = _issue(category="labeling", severity="high")
    assert issue_signature(base) != issue_signature(_issue(category="contrast", severity="high"))
    assert issue_signature(base) != issue_signature(_issue(category="labeling", severity="low"))


@pytest.mark.parametrize(
    ("severity", "blocking"),
    [("critical", True), ("high", True), ("medium", False), ("low", False)],
)
def test_has_blocking_issues_only_for_high_or_critical(severity: str, blocking: bool) -> None:
    assert has_blocking_issues(_critique(issues=[_issue(severity=severity)])) is blocking


def test_score_total_sums_all_five_scores() -> None:
    c = _critique(
        message_alignment_score=10, readability_score=20, visual_hierarchy_score=30,
        accessibility_score=40, data_fidelity_score=50,
    )
    assert score_total(c) == 150


# One critique per stopping scenario, with the loop state that should trigger
# (or, for the last case, not trigger) that specific §11.5 criterion.
_SATISFIED = _critique(verdict="satisfied")
_LOW_ONLY = _critique(issues=[_issue(severity="low")])
_REPEATED = _critique(issues=[_issue(observation="same issue")])
_BLOCKING = _critique(issues=[_issue()])


@pytest.mark.parametrize(
    ("critique", "state", "expected"),
    [
        (_SATISFIED, {"remaining_safe_repairs": 0}, (True, "satisfied")),
        (_LOW_ONLY, {"remaining_safe_repairs": 1}, (True, "no_high_or_critical_issues")),
        (_REPEATED, {"previous_signature_set": signature_set(_REPEATED), "remaining_safe_repairs": 1},
         (True, "repeated_issue_signature")),
        (_BLOCKING, {"remaining_safe_repairs": 0}, (True, "no_safe_repair_available")),
        (_BLOCKING, {"repairs_applied_so_far": 2, "remaining_safe_repairs": 1},
         (True, "max_auto_repairs_applied")),
        (_BLOCKING, {"previous_signature_set": frozenset(), "previous_score_total": score_total(_BLOCKING) + 50,
                     "remaining_safe_repairs": 1}, (True, "render_regressed")),
        (_BLOCKING, {"previous_signature_set": frozenset({"other:high:different"}),
                     "previous_score_total": score_total(_BLOCKING) - 10, "remaining_safe_repairs": 1},
         (False, None)),
    ],
    ids=[
        "satisfied", "no_blocking_issues", "repeated_signature", "no_safe_repair",
        "max_auto_repairs", "render_regressed", "progress_continues",
    ],
)
def test_should_stop(critique: VisualCritique, state: dict, expected: tuple[bool, str | None]) -> None:
    kwargs = {
        "repairs_applied_so_far": 0,
        "previous_signature_set": None,
        "previous_score_total": None,
        "remaining_safe_repairs": 1,
    }
    kwargs.update(state)
    assert should_stop(critique=critique, **kwargs) == expected
