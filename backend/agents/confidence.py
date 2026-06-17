"""Confidence is computed, not self-reported by the model (ADR-0007).

It measures support for the chosen recommendation: indicator coverage for an
escalate, the inverse for a dismiss. A flagged verifier caps it below the
human-review threshold.
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
    if verifier_flagged:
        support = min(support, REVIEW_THRESHOLD - 0.01)
    return round(support, 2)
