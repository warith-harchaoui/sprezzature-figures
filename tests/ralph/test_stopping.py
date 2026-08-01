"""
Tests for sprezzature_figures.studio.ralph.stopping: the plan §11.5
stopping criteria and issue-signature computation.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

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


def test_issue_signature_normalizes_whitespace_and_case() -> None:
    a = VisualIssue(category="labeling", severity="high", observation="  Labels   Too Small  ")
    b = VisualIssue(category="labeling", severity="high", observation="labels too small")
    assert issue_signature(a) == issue_signature(b)


def test_issue_signature_differs_by_category_or_severity() -> None:
    a = VisualIssue(category="labeling", severity="high", observation="x")
    b = VisualIssue(category="contrast", severity="high", observation="x")
    c = VisualIssue(category="labeling", severity="low", observation="x")
    assert issue_signature(a) != issue_signature(b)
    assert issue_signature(a) != issue_signature(c)


def test_has_blocking_issues_true_for_high_or_critical() -> None:
    assert has_blocking_issues(_critique(issues=[VisualIssue(category="contrast", severity="high", observation="x")]))
    assert has_blocking_issues(
        _critique(issues=[VisualIssue(category="contrast", severity="critical", observation="x")])
    )


def test_has_blocking_issues_false_for_low_medium_only() -> None:
    assert not has_blocking_issues(
        _critique(issues=[VisualIssue(category="contrast", severity="low", observation="x")])
    )


def test_score_total_sums_all_five_scores() -> None:
    c = _critique(
        message_alignment_score=10, readability_score=20, visual_hierarchy_score=30,
        accessibility_score=40, data_fidelity_score=50,
    )
    assert score_total(c) == 150


def test_should_stop_when_satisfied() -> None:
    c = _critique(verdict="satisfied")
    stop, reason = should_stop(
        critique=c, repairs_applied_so_far=0, previous_signature_set=None,
        previous_score_total=None, remaining_safe_repairs=0,
    )
    assert stop and reason == "satisfied"


def test_should_stop_when_no_blocking_issues() -> None:
    c = _critique(verdict="needs_changes", issues=[VisualIssue(category="contrast", severity="low", observation="x")])
    stop, reason = should_stop(
        critique=c, repairs_applied_so_far=0, previous_signature_set=None,
        previous_score_total=None, remaining_safe_repairs=1,
    )
    assert stop and reason == "no_high_or_critical_issues"


def test_should_stop_when_signature_repeats() -> None:
    c = _critique(issues=[VisualIssue(category="contrast", severity="high", observation="same issue")])
    prev_sig = signature_set(c)
    stop, reason = should_stop(
        critique=c, repairs_applied_so_far=0, previous_signature_set=prev_sig,
        previous_score_total=None, remaining_safe_repairs=1,
    )
    assert stop and reason == "repeated_issue_signature"


def test_should_stop_when_no_safe_repair_left() -> None:
    c = _critique(issues=[VisualIssue(category="contrast", severity="high", observation="x")])
    stop, reason = should_stop(
        critique=c, repairs_applied_so_far=0, previous_signature_set=None,
        previous_score_total=None, remaining_safe_repairs=0,
    )
    assert stop and reason == "no_safe_repair_available"


def test_should_stop_when_max_auto_repairs_applied() -> None:
    c = _critique(issues=[VisualIssue(category="contrast", severity="high", observation="x")])
    stop, reason = should_stop(
        critique=c, repairs_applied_so_far=2, previous_signature_set=None,
        previous_score_total=None, remaining_safe_repairs=1,
    )
    assert stop and reason == "max_auto_repairs_applied"


def test_should_stop_when_render_regressed() -> None:
    c = _critique(issues=[VisualIssue(category="contrast", severity="high", observation="x")])
    stop, reason = should_stop(
        critique=c, repairs_applied_so_far=0, previous_signature_set=frozenset(),
        previous_score_total=score_total(c) + 50, remaining_safe_repairs=1,
    )
    assert stop and reason == "render_regressed"


def test_should_not_stop_when_progress_is_being_made() -> None:
    c = _critique(issues=[VisualIssue(category="contrast", severity="high", observation="x")])
    stop, reason = should_stop(
        critique=c, repairs_applied_so_far=0, previous_signature_set=frozenset({"other:high:different"}),
        previous_score_total=score_total(c) - 10, remaining_safe_repairs=1,
    )
    assert not stop and reason is None
