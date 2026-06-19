"""Pipeline orchestrator: retrieve → triage → verify → confidence → draft.

Plain linear Python (no framework). Shared by precompute and the live /triage
endpoint. The verifier's verdict is never overwritten by low confidence (ADR-0007);
"needs review" is derived downstream as (flagged OR confidence < threshold).
"""

from __future__ import annotations

from datetime import datetime

import config
from agents.confidence import compute_confidence
from agents.knowledge_base import get_card, select_cards
from agents.str_drafter import draft_str
from agents.triage import render_alert_evidence, triage
from agents.verifier import verify
from schemas import AlertInput, TriageResult


def run_triage(alert: AlertInput, *, client=None) -> TriageResult:
    evidence = render_alert_evidence(alert)
    cards = select_cards(alert)

    tri = triage(evidence, cards, client=client)
    card = get_card(tri.matched_typology.code)

    ver = verify(evidence, tri.recommendation, card, client=client)
    confidence = compute_confidence(
        len(tri.fired_indicators),
        len(card.indicators),
        tri.recommendation,
        verifier_flagged=ver.status == "flagged",
    )
    str_draft = draft_str(alert, tri, card, client=client)

    return TriageResult(
        alert_id=alert.alert_id,
        recommendation=tri.recommendation,
        confidence=confidence,
        explanation=tri.explanation,
        matched_typology=tri.matched_typology,
        cited_transaction_ids=tri.cited_transaction_ids,
        verifier=ver,
        str_draft=str_draft,
        model=config.MODEL_WORKHORSE,
        generated_at=datetime.now(),
    )
