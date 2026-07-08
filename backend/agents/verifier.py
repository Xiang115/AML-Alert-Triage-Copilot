"""Adversarial verifier (ADR-0001) — the demo's wow.

An independent second-line QA pass. It re-reads the RAW evidence (not the triage
agent's explanation, so it isn't anchored to the first call) and tests whether
that evidence actually satisfies the matched typology's distinguishing test or
could be the benign look-alike. Disagreement flags the alert for human review.
Runs on the cheaper verifier model.
"""

from __future__ import annotations

from pydantic import field_validator

import config
from llm import coerce_text, complete_model
from schemas import Challenge, ClaimCitation, LLMResponse, Rebuttal, Reverdict, TypologyCard, Verifier

_SYSTEM = (
    "You are a skeptical second-line AML QA reviewer. Independently re-examine the evidence and "
    "ASSUME THE TRIAGE CALL MAY BE WRONG. Using only the typology's distinguishing test and its "
    "benign look-alike, judge whether the evidence genuinely supports the recommendation or could "
    "instead be the benign look-alike. Do not defer to the triage agent. Reply ONLY with JSON: "
    '{"agreesWithRecommendation" (bool), '
    '"claims": a list of your grounds, each {"claim" (one sentence on what is or is not satisfied), '
    '"citedTransactionIds" (ids it rests on, [] if none), '
    '"firedIndicators" (indicators it rests on, [] if none)}}.'
)


class _VerifyClaim(LLMResponse):
    claim: str
    cited_transaction_ids: list[str] = []
    fired_indicators: list[str] = []

    @field_validator("claim", mode="before")
    @classmethod
    def _flatten(cls, v):
        return coerce_text(v)


class _VerifyResponse(LLMResponse):
    """The verifier's verdict shape. `agreesWithRecommendation` is required (it
    drives the agreed/flagged status); the claims are the raw, unanchored rationale."""

    agrees_with_recommendation: bool
    claims: list[_VerifyClaim] = []


def verify(
    evidence: str,
    recommendation: str,
    card: TypologyCard,
    *,
    client=None,
    model: str | None = None,
    memory_context: str | None = None,
) -> tuple[Verifier, list[ClaimCitation]]:
    memory_block = (
        "\n\nLearned clearance precedent to challenge, not blindly trust:\n"
        f"{memory_context}"
        if memory_context
        else ""
    )
    parsed = complete_model(
        _SYSTEM,
        f"Recommendation to challenge: {recommendation}\n"
        f"Typology [{card.code}] {card.name}\n"
        f"Distinguishing test: {card.distinguishing_test}\n"
        f"Benign look-alike: {card.benign_lookalike}\n\n"
        f"Evidence:\n{evidence}"
        f"{memory_block}",
        model or config.MODEL_VERIFIER,
        _VerifyResponse,
        client=client,
        stage="verifier",
        template_id="verifier-v1",
    )
    agrees = parsed.agrees_with_recommendation
    claims = [ClaimCitation(text=c.claim, cited_transaction_ids=c.cited_transaction_ids,
                            fired_indicators=c.fired_indicators) for c in parsed.claims]
    return (
        Verifier(status="agreed" if agrees else "flagged", agrees_with_recommendation=agrees),
        claims,
    )


# --- Adversarial debate (ADR-0011) -------------------------------------------------
# When the first, independent pass flags, the verifier articulates its objection (the
# Challenge), Triage gets one Rebuttal turn (agents/triage.rebut), and the verifier
# re-judges (re_verdict). The debate is the resolution *after* an independent
# disagreement, so the first pass stays un-anchored (ADR-0001 preserved).

_CHALLENGE_SYSTEM = (
    "You are a skeptical second-line AML QA reviewer who has FLAGGED a triage call. State your "
    "strongest case that the call is wrong, using only the typology's distinguishing test and its "
    "benign look-alike. Reply ONLY with JSON: "
    '{"counterHypothesis" (the benign explanation that best fits the evidence), '
    '"distinguishingTestAssessment" (point-by-point: which parts of the distinguishing test the '
    "evidence does NOT satisfy)}."
)


class _ChallengeResponse(LLMResponse):
    counter_hypothesis: str
    distinguishing_test_assessment: str

    @field_validator("counter_hypothesis", "distinguishing_test_assessment", mode="before")
    @classmethod
    def _flatten(cls, v):
        return coerce_text(v)


def challenge(evidence: str, recommendation: str, card: TypologyCard, *, client=None,
              model: str | None = None) -> Challenge:
    """Articulate a flagged call's objection (ADR-0011): the counter-hypothesis + a read of the
    evidence against the distinguishing test. Un-anchored — sees only the raw evidence and the
    card, never the triage explanation. Runs on the cheap verifier model."""
    parsed = complete_model(
        _CHALLENGE_SYSTEM,
        f"Recommendation challenged: {recommendation}\n"
        f"Typology [{card.code}] {card.name}\n"
        f"Distinguishing test: {card.distinguishing_test}\n"
        f"Benign look-alike: {card.benign_lookalike}\n\n"
        f"Evidence:\n{evidence}",
        model or config.MODEL_VERIFIER,
        _ChallengeResponse,
        client=client,
        stage="verifierChallenge",
        template_id="verifier-challenge-v1",
    )
    return Challenge(
        counter_hypothesis=parsed.counter_hypothesis,
        distinguishing_test_assessment=parsed.distinguishing_test_assessment,
    )


_REVERDICT_SYSTEM = (
    "You are the second-line AML QA reviewer who challenged a triage call. The triage agent has "
    "responded but did NOT concede. Judge whether its rebuttal genuinely resolves your objection "
    "against the typology's distinguishing test. Be hard to convince: in AML a missed launderer is "
    "the costly error, so resolve the flag ONLY if the rebuttal clearly satisfies the test. Reply "
    'ONLY with JSON: {"outcome" ("convinced" if the rebuttal resolves it, else "holds"), '
    '"note" (one sentence on why)}.'
)


class _ReverdictResponse(LLMResponse):
    outcome: str  # "convinced" | "holds"
    note: str = ""

    @field_validator("note", mode="before")
    @classmethod
    def _flatten(cls, v):
        return coerce_text(v)


def re_verdict(evidence: str, recommendation: str, card: TypologyCard, challenge_: Challenge,
               rebuttal: Rebuttal, *, client=None, model: str | None = None) -> Reverdict:
    """The verifier's final judgment after a non-conceding Rebuttal (ADR-0011). Returns `convinced`
    (flag resolves → agreed) or `holds` (flag stands → needsReview); the disposition never flips on
    this path (a flip only happens when Triage concedes, handled by the pipeline). Cheap model."""
    parsed = complete_model(
        _REVERDICT_SYSTEM,
        f"Recommendation challenged: {recommendation}\n"
        f"Typology [{card.code}] {card.name}\n"
        f"Distinguishing test: {card.distinguishing_test}\n"
        f"Your challenge — counter-hypothesis: {challenge_.counter_hypothesis}\n"
        f"Your challenge — test assessment: {challenge_.distinguishing_test_assessment}\n"
        f"Triage's rebuttal: {rebuttal.argument}\n\n"
        f"Evidence:\n{evidence}",
        model or config.MODEL_VERIFIER,
        _ReverdictResponse,
        client=client,
        stage="verifierReverdict",
        template_id="verifier-reverdict-v1",
    )
    outcome = "convinced" if parsed.outcome == "convinced" else "holds"
    return Reverdict(outcome=outcome, disposition_changed=False, note=parsed.note)
