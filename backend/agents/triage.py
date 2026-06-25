"""Triage agent: pick Escalate/Dismiss against the candidate typology cards.

Takes pre-rendered evidence (see agents/evidence.py for the two data worlds,
ADR-0005). The model returns a typology *code* and fired indicators; we resolve
the card and clamp the indicators so `source`/membership can't be hallucinated.
"""

from __future__ import annotations

from typing import Literal

from pydantic import field_validator

import config
from agents.knowledge_base import get_card, load_cards
from llm import coerce_text, complete_model
from schemas import Challenge, LLMResponse, MatchedTypology, Rebuttal, TriageOutput, TypologyCard

# Sentinel: no candidate typology matched the evidence. A first-class, one-call
# answer (recommendation = dismiss) rather than an empty code that retries until
# it exhausts and falls back to dismiss anyway — so a "no pattern" dismiss is
# reasoned, not timed-out, and the pipeline does no wasted work.
NO_MATCH_CODE = "NONE"

_SYSTEM = (
    "You are an AML alert-triage analyst. Decide Escalate or Dismiss for the alert by "
    "matching it to exactly one of the candidate typology cards. Escalate when the card's "
    "indicators are present in the evidence — match on the pattern. An independent second-line "
    "verifier separately tests benign look-alikes and the distinguishing test, so do NOT dismiss "
    "merely because a benign explanation is possible: escalate the pattern match and let the "
    "verifier challenge it. "
    "If NONE of the candidate typologies fit the evidence, do not force a match: return "
    f'matchedTypologyCode "{NO_MATCH_CODE}" with recommendation "dismiss". '
    "Reply ONLY with a JSON object: "
    '{"matchedTypologyCode", "firedIndicators" (subset of that card\'s indicators present in '
    'the evidence), "citedTransactionIds" (ids supporting the call, [] if none), '
    '"recommendation" ("escalate"|"dismiss"), "explanation"}.'
)

# Cost-sensitive operating-point note (opt-in via triage(cost_sensitive=True)). In AML a
# missed launderer (FN) costs far more than an extra review (FP), and a second-line verifier
# + human gate review every escalation — so on borderline evidence we prefer Escalate. It is
# appended to the otherwise-stable system prefix and stays constant across a whole eval/
# precompute run, so DeepSeek prompt-caching still holds.
_COST_SENSITIVE_NOTE = (
    "COST-SENSITIVE MODE: a missed suspicious case (false negative) is far costlier than an "
    "unnecessary review (false positive), and a second-line verifier and a human analyst review "
    "every escalation. When the evidence is borderline or only partially matches a card, prefer "
    "Escalate over Dismiss. This governs the MATCH decision too: do NOT return "
    f'"{NO_MATCH_CODE}" merely because the fit is imperfect — if the evidence shows a suspicious '
    "laundering-like pattern (e.g. running balance draining toward zero, rapid in-then-out movement, "
    "many unrelated counterparties, or repeated sub-threshold amounts) that resembles a candidate "
    "typology, match the CLOSEST card and escalate; the verifier will challenge it. Reserve "
    f'"{NO_MATCH_CODE}" for evidence with no suspicious pattern at all.'
)


def _cost_sensitive_escalate(recommendation: str, fired: list[str], min_fired_to_escalate: int) -> str:
    """Move the matched-card decision along the recall/false-positive frontier (ADR-0004/0007).

    A timid dismiss on a card that *did* fire indicators is exactly the false negative AML can
    least afford; the verifier + human gate absorb the extra escalations. So escalate when at
    least `min_fired_to_escalate` indicators fired. Only the matched-card branch calls this —
    NO_MATCH stays a reasoned dismiss; we never fabricate a typology match to escalate.
    """
    if recommendation == "dismiss" and len(fired) >= min_fired_to_escalate:
        return "escalate"
    return recommendation


class _TriageResponse(LLMResponse):
    """The shape the Triage Agent prompt asks the model to return. `recommendation`
    gates the retry; an absent/empty/NONE code means "no typology matched" (a clean
    dismiss), so it never retries. A *hallucinated* code still fails and retries."""

    matched_typology_code: str = NO_MATCH_CODE
    recommendation: Literal["escalate", "dismiss"]
    fired_indicators: list[str] = []
    cited_transaction_ids: list[str] = []
    explanation: str = ""

    @field_validator("matched_typology_code", mode="before")
    @classmethod
    def _empty_is_no_match(cls, v) -> str:
        # An empty/null code is the model saying "nothing matched" — normalise to
        # the sentinel rather than failing validation (which would retry uselessly).
        if v is None:
            return NO_MATCH_CODE
        return str(v).strip() or NO_MATCH_CODE

    @field_validator("matched_typology_code")
    @classmethod
    def _known_code(cls, v: str) -> str:
        # The sentinel is allowed; a *hallucinated* code is rejected so complete_model
        # retries, rather than letting get_card raise KeyError deeper in the pipeline.
        if v == NO_MATCH_CODE:
            return v
        if v not in {c.code for c in load_cards()}:
            raise ValueError(f"unknown typology code: {v}")
        return v


def _render_cards(cards: list[TypologyCard]) -> str:
    # Triage matches on indicators only. The benign look-alike + distinguishing test
    # are deliberately withheld here and given to the verifier alone (ADR-0001), so the
    # two agents don't run the same discrimination and the verifier isn't redundant.
    out = []
    for c in cards:
        out.append(
            f"[{c.code}] {c.name} (source: {c.source})\n"
            f"  indicators: {c.indicators}"
        )
    return "\n".join(out)


def triage(evidence: str, cards: list[TypologyCard], *, client=None, model: str | None = None,
           max_tokens: int | None = None, cost_sensitive: bool = False,
           min_fired_to_escalate: int = 1) -> TriageOutput:
    # Feature-evidence (eval) prompts make V4 reason harder; the caller can raise
    # max_tokens so the visible JSON isn't truncated to empty by reasoning tokens.
    extra = {"max_tokens": max_tokens} if max_tokens is not None else {}
    # The instructions + candidate cards are identical on every call (select_cards
    # returns all cards in stable order), so they go in the system message as one stable
    # prefix that DeepSeek prompt-caches; only the per-alert evidence varies in the user
    # message. Keeps the big static block out of the billed/processed tokens per call.
    system = f"{_SYSTEM}\n\nCandidate typologies (match the alert to exactly one):\n{_render_cards(cards)}"
    if cost_sensitive:
        # Constant for the whole run, so the cached prefix is unaffected across calls.
        system = f"{system}\n\n{_COST_SENSITIVE_NOTE}"
    parsed = complete_model(
        system,
        f"Alert evidence:\n{evidence}",
        model or config.MODEL_WORKHORSE,
        _TriageResponse,
        client=client,
        **extra,
    )
    if parsed.matched_typology_code == NO_MATCH_CODE:
        # No typology matched → reasoned dismiss, no card to resolve or draft against.
        return TriageOutput(
            recommendation="dismiss",
            matched_typology=MatchedTypology(code=NO_MATCH_CODE, name="No typology matched", source="—"),
            fired_indicators=[],
            cited_transaction_ids=[],
            explanation=parsed.explanation
            or "No candidate typology matched the evidence; no laundering pattern to escalate.",
        )
    card = get_card(parsed.matched_typology_code)
    fired = [i for i in parsed.fired_indicators if i in card.indicators]
    recommendation = parsed.recommendation
    if cost_sensitive:
        recommendation = _cost_sensitive_escalate(recommendation, fired, min_fired_to_escalate)
    return TriageOutput(
        recommendation=recommendation,
        matched_typology=MatchedTypology(code=card.code, name=card.name, source=card.source),
        fired_indicators=fired,
        cited_transaction_ids=parsed.cited_transaction_ids,
        explanation=parsed.explanation,
    )


# --- Adversarial debate rebuttal (ADR-0011) ----------------------------------------

_REBUT_SYSTEM = (
    "You are the AML triage agent. A second-line verifier has FLAGGED your call and put a "
    "counter-hypothesis to you. Re-examine the evidence honestly against the typology's "
    "distinguishing test. Defend your call ONLY if the evidence genuinely satisfies the test; if "
    "the verifier's benign explanation is the better fit, CONCEDE — conceding corrects the call and "
    "is not a failure. Reply ONLY with JSON: "
    '{"argument" (one or two sentences answering the challenge), '
    '"conceded" (true if you accept the verifier\'s counter-hypothesis, else false)}.'
)


class _RebutResponse(LLMResponse):
    argument: str
    conceded: bool

    @field_validator("argument", mode="before")
    @classmethod
    def _flatten(cls, v):
        return coerce_text(v)


def rebut(evidence: str, card: TypologyCard, challenge: Challenge, *, client=None,
          model: str | None = None) -> Rebuttal:
    """Triage's single response turn in the debate (ADR-0011). The only point Triage sees the
    verifier's reasoning; it defends the call against the Challenge or concedes (which flips the
    disposition downstream). Runs on the workhorse model."""
    parsed = complete_model(
        _REBUT_SYSTEM,
        f"Typology [{card.code}] {card.name}\n"
        f"Distinguishing test: {card.distinguishing_test}\n"
        f"Verifier's counter-hypothesis: {challenge.counter_hypothesis}\n"
        f"Verifier's test assessment: {challenge.distinguishing_test_assessment}\n\n"
        f"Evidence:\n{evidence}",
        model or config.MODEL_WORKHORSE,
        _RebutResponse,
        client=client,
    )
    return Rebuttal(argument=parsed.argument, conceded=parsed.conceded)
