"""Triage agent: pick Escalate/Dismiss against the candidate typology cards.

Takes pre-rendered evidence (see agents/evidence.py for the two data worlds,
ADR-0005). The model returns a typology *code* and fired indicators; we resolve
the card and clamp the indicators so `source`/membership can't be hallucinated.
"""

from __future__ import annotations

import config
from agents.knowledge_base import get_card
from llm import complete_json
from schemas import MatchedTypology, TriageOutput, TypologyCard

_SYSTEM = (
    "You are an AML alert-triage analyst. Decide Escalate or Dismiss for the alert by "
    "matching it to exactly one of the candidate typology cards. Use each card's indicators "
    "and distinguishing test. Reply ONLY with a JSON object: "
    '{"matchedTypologyCode", "firedIndicators" (subset of that card\'s indicators present in '
    'the evidence), "citedTransactionIds" (ids supporting the call, [] if none), '
    '"recommendation" ("escalate"|"dismiss"), "explanation"}.'
)


def _render_cards(cards: list[TypologyCard]) -> str:
    out = []
    for c in cards:
        out.append(
            f"[{c.code}] {c.name} (source: {c.source})\n"
            f"  indicators: {c.indicators}\n"
            f"  distinguishing test: {c.distinguishing_test}"
        )
    return "\n".join(out)


def triage(evidence: str, cards: list[TypologyCard], *, client=None, model: str | None = None,
           max_tokens: int | None = None) -> TriageOutput:
    # Feature-evidence (eval) prompts make V4 reason harder; the caller can raise
    # max_tokens so the visible JSON isn't truncated to empty by reasoning tokens.
    extra = {"max_tokens": max_tokens} if max_tokens is not None else {}
    raw = complete_json(
        _SYSTEM,
        f"Candidate typologies:\n{_render_cards(cards)}\n\nAlert evidence:\n{evidence}",
        model or config.MODEL_WORKHORSE,
        client=client,
        **extra,
    )
    card = get_card(raw["matchedTypologyCode"])
    fired = [i for i in raw.get("firedIndicators", []) if i in card.indicators]
    return TriageOutput(
        recommendation=raw["recommendation"],
        matched_typology=MatchedTypology(code=card.code, name=card.name, source=card.source),
        fired_indicators=fired,
        cited_transaction_ids=raw.get("citedTransactionIds", []),
        explanation=raw.get("explanation", ""),
    )
