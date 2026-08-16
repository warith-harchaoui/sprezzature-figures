"""
When the Ralph loop stops (plan §11.5): satisfied verdict, no high/critical
issues left, two consecutive rounds surfacing the same issues, no safe
repair left to try, two automatic repairs already applied, a render
regression, or the user cancelling (handled by the caller, not here).

Issue signatures are category + severity + a normalized message, so the
same underlying problem reported with slightly different wording doesn't
look "new" round over round. The plan also mentions an "approximate zone",
meaning where on the figure the issue sits; VisualIssue (Commit 9) does not
carry bounding-box coordinates yet, because a real zone would need a
vision-language model that grounds its answer in image coordinates, which
is not wired up here. That is a documented simplification, not a silent
omission.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import re

from sprezzature_figures.studio.assistant.schemas import VisualCritique, VisualIssue

MAX_AUTO_REPAIRS = 2
_HIGH_SEVERITIES = {"high", "critical"}
_WHITESPACE_RE = re.compile(r"\s+")


def issue_signature(issue: VisualIssue) -> str:
    normalized = _WHITESPACE_RE.sub(" ", issue.observation.strip().lower())[:80]
    return f"{issue.category}:{issue.severity}:{normalized}"


def signature_set(critique: VisualCritique) -> frozenset[str]:
    return frozenset(issue_signature(i) for i in critique.issues)


def has_blocking_issues(critique: VisualCritique) -> bool:
    return any(i.severity in _HIGH_SEVERITIES for i in critique.issues)


def score_total(critique: VisualCritique) -> int:
    return (
        critique.message_alignment_score
        + critique.readability_score
        + critique.visual_hierarchy_score
        + critique.accessibility_score
        + critique.data_fidelity_score
    )


def should_stop(
    *,
    critique: VisualCritique,
    repairs_applied_so_far: int,
    previous_signature_set: frozenset[str] | None,
    previous_score_total: int | None,
    remaining_safe_repairs: int,
) -> tuple[bool, str | None]:
    """Decide whether the Ralph loop should stop after this round.

    Returns
    -------
    (stop, reason) : tuple[bool, str | None]
        `reason` is one of the plan §11.5 criteria's short names, or None
        if the loop should continue.
    """
    if critique.verdict == "satisfied":
        return True, "satisfied"
    if not has_blocking_issues(critique):
        return True, "no_high_or_critical_issues"
    current = signature_set(critique)
    if previous_signature_set is not None and current == previous_signature_set:
        return True, "repeated_issue_signature"
    if remaining_safe_repairs == 0:
        return True, "no_safe_repair_available"
    if repairs_applied_so_far >= MAX_AUTO_REPAIRS:
        return True, "max_auto_repairs_applied"
    if previous_score_total is not None and score_total(critique) < previous_score_total:
        return True, "render_regressed"
    return False, None
