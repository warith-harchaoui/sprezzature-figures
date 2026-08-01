"""
sprezzature_figures.studio.ralph — the interactive Ralph engine (plan §11).

Ralph modifies the FigurePlan, never the rendered image (plan §1.3): every
change is a typed FigureOperation, applied deterministically, then
re-rendered. The vision model only ever judges a PNG it's shown; it never
edits pixels.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from .apply import apply_operation, apply_operations
from .critic import critique_prompt, request_critique
from .engine import RalphEngine, RalphMode, RalphResult
from .history import RalphHistory, RalphRound
from .policy import can_apply_automatically, is_safe_repair, requires_confirmation
from .repair import apply_safe_repairs, safe_repairs_from_critique
from .stopping import (
    MAX_AUTO_REPAIRS,
    has_blocking_issues,
    issue_signature,
    score_total,
    should_stop,
    signature_set,
)

__all__ = [
    "MAX_AUTO_REPAIRS",
    "RalphEngine",
    "RalphHistory",
    "RalphMode",
    "RalphResult",
    "RalphRound",
    "apply_operation",
    "apply_operations",
    "apply_safe_repairs",
    "can_apply_automatically",
    "critique_prompt",
    "has_blocking_issues",
    "is_safe_repair",
    "issue_signature",
    "request_critique",
    "requires_confirmation",
    "safe_repairs_from_critique",
    "score_total",
    "should_stop",
    "signature_set",
]
