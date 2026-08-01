"""
In-memory round-by-round history for one Ralph session, feeding the
stopping criteria (plan §11.5). Not to be confused with the persistent,
disk-backed IterationRecord history (plan §12, Commit 12) -- this is
Ralph's own short-term memory of "what did I just try", scoped to however
long the caller keeps a RalphHistory instance alive (typically one
autopilot repair loop, or one chat session).

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sprezzature_figures.core.operations import FigureOperation
from sprezzature_figures.studio.assistant.schemas import VisualCritique

from .stopping import score_total, signature_set


@dataclass
class RalphRound:
    critique: VisualCritique
    applied_operations: list[FigureOperation]


@dataclass
class RalphHistory:
    rounds: list[RalphRound] = field(default_factory=list)

    def record(self, critique: VisualCritique, applied_operations: list[FigureOperation]) -> None:
        self.rounds.append(RalphRound(critique=critique, applied_operations=applied_operations))

    def repair_count(self) -> int:
        """Number of rounds so far that actually applied at least one
        safe-repair operation.
        """
        return sum(1 for r in self.rounds if r.applied_operations)

    def last_signature_set(self) -> frozenset[str] | None:
        return signature_set(self.rounds[-1].critique) if self.rounds else None

    def last_score_total(self) -> int | None:
        return score_total(self.rounds[-1].critique) if self.rounds else None
