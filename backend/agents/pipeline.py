"""Pipeline orchestrator: retrieve → triage → verify → confidence → draft.

Plain linear Python (no framework). `run_triage_events` is the single source of
truth: it runs the pipeline and *yields* a stage event after each real step (so the
live "thinking" view can stream them over SSE as they happen), ending with the final
result. `run_triage` just consumes that generator and returns the result, so the
batch path and the streamed path can never drift. The verifier's verdict is never
overwritten by low confidence (ADR-0007); "needs review" is derived downstream as
(flagged OR confidence < threshold).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime

import config
from agents.confidence import compute_confidence
from agents.evidence import render_alert_evidence
from agents.knowledge_base import get_card, select_cards
from agents.str_drafter import draft_str
from agents.triage import NO_MATCH_CODE, triage
from agents.verifier import verify
from schemas import AlertInput, IndicatorCoverage, TriageResult, Verifier


def run_triage_events(
    alert: AlertInput, *, client=None, cost_sensitive: bool = False
) -> Iterator[dict]:
    """Run the pipeline, yielding one event per step so the UI can reveal the agent's
    reasoning live. Stage/indicator events are JSON-friendly dicts; the terminal event
    is {"type": "result", "triage": <TriageResult>} carrying the assembled object."""
    evidence = render_alert_evidence(alert)
    cards = select_cards(alert)
    yield {
        "type": "stage", "id": "retrieve",
        "label": "Retrieving typology cards (FATF / BNM)",
        "detail": f"Loaded {len(cards)} candidate typology cards",
    }

    tri = triage(evidence, cards, client=client, cost_sensitive=cost_sensitive)

    if tri.matched_typology.code == NO_MATCH_CODE:
        result = TriageResult(
            alert_id=alert.alert_id,
            recommendation="dismiss",
            confidence=compute_confidence(0, 0, "dismiss", verifier_flagged=False),
            explanation=tri.explanation,
            matched_typology=tri.matched_typology,
            cited_transaction_ids=[],
            indicator_coverage=IndicatorCoverage(indicators=[], fired=[]),
            verifier=Verifier(
                status="agreed",
                agrees_with_recommendation=True,
                note="No candidate typology matched the evidence; no laundering pattern to escalate.",
            ),
            str_draft=None,
            model=config.MODEL_WORKHORSE,
            generated_at=datetime.now(),
        )
        yield {"type": "stage", "id": "triage", "label": "Triage agent — assessing the call",
               "detail": "Dismiss — no candidate typology matched the evidence", "tone": "verified"}
        yield {"type": "stage", "id": "verifier", "label": "Adversarial verifier",
               "detail": "Agreed — no laundering pattern to challenge", "tone": "verified"}
        yield {"type": "stage", "id": "confidence", "label": "Computing confidence",
               "detail": f"{round(result.confidence * 100)}% — no pattern to score"}
        yield {"type": "stage", "id": "draft", "label": "STR drafter",
               "detail": "Skipped — no report drafted on a dismiss"}
        yield {"type": "result", "triage": result}
        return

    card = get_card(tri.matched_typology.code)
    yield {
        "type": "stage", "id": "triage", "label": "Triage agent — assessing the call",
        "detail": f"{'Escalate' if tri.recommendation == 'escalate' else 'Dismiss'} — "
                  f"matched {card.code} {card.name}. {tri.explanation}",
        "tone": "escalate" if tri.recommendation == "escalate" else "verified",
    }
    fired = set(tri.fired_indicators)
    for ind in card.indicators:
        yield {"type": "indicator", "text": ind, "fired": ind in fired}

    ver = verify(evidence, tri.recommendation, card, client=client)
    yield {
        "type": "stage", "id": "verifier", "label": "Adversarial verifier — challenging the call",
        "detail": f"{'FLAGGED for human review' if ver.status == 'flagged' else 'Agreed'} — {ver.note}",
        "tone": "flag" if ver.status == "flagged" else "verified",
    }

    confidence = compute_confidence(
        len(tri.fired_indicators), len(card.indicators), tri.recommendation,
        verifier_flagged=ver.status == "flagged",
    )
    total = len(card.indicators)
    yield {
        "type": "stage", "id": "confidence",
        "label": "Computing confidence from indicator coverage",
        "detail": f"{len(tri.fired_indicators)}/{total} indicators fired → {round(confidence * 100)}%"
                  + (" (capped below review threshold)" if ver.status == "flagged" else ""),
    }

    str_draft = draft_str(alert, tri, card, verifier_status=ver.status, client=client)
    yield {"type": "stage", "id": "draft", "label": "STR drafter",
           "detail": "Structured Suspicious Transaction Report drafted" if str_draft
                     else "Skipped — no report on a dismiss"}

    result = TriageResult(
        alert_id=alert.alert_id,
        recommendation=tri.recommendation,
        confidence=confidence,
        explanation=tri.explanation,
        matched_typology=tri.matched_typology,
        cited_transaction_ids=tri.cited_transaction_ids,
        indicator_coverage=IndicatorCoverage(indicators=card.indicators, fired=tri.fired_indicators),
        verifier=ver,
        str_draft=str_draft,
        model=config.MODEL_WORKHORSE,
        generated_at=datetime.now(),
    )
    yield {"type": "result", "triage": result}


def run_triage(alert: AlertInput, *, client=None, cost_sensitive: bool = False) -> TriageResult:
    """Batch path: run the pipeline and return the final assembled result."""
    result: TriageResult | None = None
    for ev in run_triage_events(alert, client=client, cost_sensitive=cost_sensitive):
        if ev["type"] == "result":
            result = ev["triage"]
    assert result is not None, "run_triage_events must yield a result event"
    return result
