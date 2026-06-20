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
from llm import complete_model
from schemas import LLMResponse, MatchedTypology, TriageOutput, TypologyCard

_SYSTEM = (
    "You are an AML alert-triage analyst. Decide Escalate or Dismiss for the alert by "
    "matching it to exactly one of the candidate typology cards. Use each card's indicators "
    "and distinguishing test, and rule out the card's benign look-alike before escalating. "
    "Reply ONLY with a JSON object: "
    '{"matchedTypologyCode", "firedIndicators" (subset of that card\'s indicators present in '
    'the evidence), "citedTransactionIds" (ids supporting the call, [] if none), '
    '"recommendation" ("escalate"|"dismiss"), "explanation"}.'
)


class _TriageResponse(LLMResponse):
    """The shape the Triage Agent prompt asks the model to return. Required fields
    (code, recommendation) gate the retry; the rest tolerate absence with defaults."""

    matched_typology_code: str
    recommendation: Literal["escalate", "dismiss"]
    fired_indicators: list[str] = []
    cited_transaction_ids: list[str] = []
    explanation: str = ""

    @field_validator("matched_typology_code")
    @classmethod
    def _known_code(cls, v: str) -> str:
        # Reject a hallucinated code at the seam so complete_model retries, rather
        # than letting get_card raise KeyError deeper in the pipeline.
        if v not in {c.code for c in load_cards()}:
            raise ValueError(f"unknown typology code: {v}")
        return v


def _render_cards(cards: list[TypologyCard]) -> str:
    out = []
    for c in cards:
        out.append(
            f"[{c.code}] {c.name} (source: {c.source})\n"
            f"  indicators: {c.indicators}\n"
            f"  benign look-alike: {c.benign_lookalike}\n"
            f"  distinguishing test: {c.distinguishing_test}"
        )
    return "\n".join(out)


def triage(evidence: str, cards: list[TypologyCard], *, client=None, model: str | None = None,
           max_tokens: int | None = None) -> TriageOutput:
    # Feature-evidence (eval) prompts make V4 reason harder; the caller can raise
    # max_tokens so the visible JSON isn't truncated to empty by reasoning tokens.
    extra = {"max_tokens": max_tokens} if max_tokens is not None else {}
    parsed = complete_model(
        _SYSTEM,
        f"Candidate typologies:\n{_render_cards(cards)}\n\nAlert evidence:\n{evidence}",
        model or config.MODEL_WORKHORSE,
        _TriageResponse,
        client=client,
        **extra,
    )
    card = get_card(parsed.matched_typology_code)
    fired = [i for i in parsed.fired_indicators if i in card.indicators]
    return TriageOutput(
        recommendation=parsed.recommendation,
        matched_typology=MatchedTypology(code=card.code, name=card.name, source=card.source),
        fired_indicators=fired,
        cited_transaction_ids=parsed.cited_transaction_ids,
        explanation=parsed.explanation,
    )
