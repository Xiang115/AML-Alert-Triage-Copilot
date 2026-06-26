"""Confidence is computed, not self-reported by the model (ADR-0007).

It measures support for the chosen recommendation: indicator coverage for an
escalate, the inverse for a dismiss. A flagged verifier caps a *dismiss* below the
human-review threshold so the Queue Agent cannot auto-clear a contested benign call.
A flagged escalate is never auto-cleared, so it keeps its true coverage and the
verifier flag alone routes it to a human — capping it would only understate a strong,
contested catch.
"""

from __future__ import annotations

from config import REVIEW_THRESHOLD


def compute_confidence(
    fired_count: int,
    total_count: int,
    recommendation: str,
    verifier_flagged: bool,
) -> float:
    coverage = fired_count / total_count if total_count else 0.0
    support = coverage if recommendation == "escalate" else 1.0 - coverage
    # Cap only a flagged DISMISS — that is the call the Queue Agent could otherwise
    # auto-clear, so a contested one must drop below the review line and route to a
    # human. A flagged escalate never auto-clears (the system never auto-escalates),
    # so it keeps its computed coverage; the verifier flag itself forces review.
    if verifier_flagged and recommendation == "dismiss":
        support = min(support, REVIEW_THRESHOLD - 0.01)
    return round(support, 2)
