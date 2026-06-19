"""Adversarial verifier (ADR-0001) — the demo's wow.

An independent second-line QA pass. It re-reads the RAW evidence (not the triage
agent's explanation, so it isn't anchored to the first call) and tests whether
that evidence actually satisfies the matched typology's distinguishing test or
could be the benign look-alike. Disagreement flags the alert for human review.
Runs on the cheaper verifier model.
"""

from __future__ import annotations

import config
from llm import complete_json
from schemas import TypologyCard, Verifier

_SYSTEM = (
    "You are a skeptical second-line AML QA reviewer. Independently re-examine the evidence and "
    "ASSUME THE TRIAGE CALL MAY BE WRONG. Using only the typology's distinguishing test and its "
    "benign look-alike, judge whether the evidence genuinely supports the recommendation or could "
    "instead be the benign look-alike. Do not defer to the triage agent. Reply ONLY with JSON: "
    '{"agreesWithRecommendation" (bool), "note" (one sentence on what is or is not satisfied)}.'
)


def verify(evidence: str, recommendation: str, card: TypologyCard, *, client=None,
           model: str | None = None) -> Verifier:
    raw = complete_json(
        _SYSTEM,
        f"Recommendation to challenge: {recommendation}\n"
        f"Typology [{card.code}] {card.name}\n"
        f"Distinguishing test: {card.distinguishing_test}\n"
        f"Benign look-alike: {card.benign_lookalike}\n\n"
        f"Evidence:\n{evidence}",
        model or config.MODEL_VERIFIER,
        client=client,
    )
    agrees = bool(raw["agreesWithRecommendation"])
    return Verifier(
        status="agreed" if agrees else "flagged",
        agrees_with_recommendation=agrees,
        note=raw.get("note", ""),
    )
