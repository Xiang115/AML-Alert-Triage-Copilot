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
from agents.triage import NO_MATCH_CODE, rebut, triage
from agents.verifier import challenge, re_verdict, verify
from schemas import AlertInput, Debate, IndicatorCoverage, Reverdict, TriageResult, Verifier


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
    # Citation Grounding: clamp the cited ids to the account's real ledger — the model
    # cannot cite a transaction that does not exist (the txn-level analogue of clamping
    # fired indicators to the card). Asserts provenance, not correctness.
    valid_ids = {t.transaction_id for t in (alert.transactions or [])}
    cited_count = len(tri.cited_transaction_ids)
    tri = tri.model_copy(
        update={"cited_transaction_ids": [c for c in tri.cited_transaction_ids if c in valid_ids]}
    )
    grounded_count = len(tri.cited_transaction_ids)
    dropped = cited_count - grounded_count
    yield {
        "type": "stage", "id": "triage", "label": "Triage agent — assessing the call",
        "detail": f"{'Escalate' if tri.recommendation == 'escalate' else 'Dismiss'} — "
                  f"matched {card.code} {card.name}. {tri.explanation}",
        "tone": "escalate" if tri.recommendation == "escalate" else "verified",
    }
    fired = set(tri.fired_indicators)
    for ind in card.indicators:
        yield {"type": "indicator", "text": ind, "fired": ind in fired}

    # Surface the grounding as its own reasoning beat — only when the call cited anything.
    if cited_count:
        plural = "s" if grounded_count != 1 else ""
        detail = (
            f"{grounded_count} cited transaction{plural} verified against the account ledger"
            if dropped == 0
            else f"{grounded_count} of {cited_count} cited transactions verified against the "
                 f"account ledger — {dropped} invalid citation{'s' if dropped != 1 else ''} dropped"
        )
        yield {"type": "stage", "id": "grounding",
               "label": "Grounding citations against the source ledger",
               "detail": detail, "tone": "verified"}

    ver = verify(evidence, tri.recommendation, card, client=client)
    yield {
        "type": "stage", "id": "verifier", "label": "Adversarial verifier — challenging the call",
        "detail": f"{'FLAGGED for human review' if ver.status == 'flagged' else 'Agreed'} — {ver.note}",
        "tone": "flag" if ver.status == "flagged" else "verified",
    }

    # Adversarial debate (ADR-0011): only on a flagged first pass. The challenge stays un-anchored
    # (raw evidence only, ADR-0001); Triage gets one rebuttal; a non-concede triggers a re-verdict.
    # `recommendation` and `final_ver` are the post-debate truth that drives confidence + the STR.
    recommendation = tri.recommendation
    final_ver = ver
    debate: Debate | None = None
    if ver.status == "flagged":
        ch = challenge(evidence, tri.recommendation, card, client=client)
        yield {"type": "stage", "id": "challenge",
               "label": "Adversarial debate — the verifier's challenge",
               "detail": f"{ch.counter_hypothesis} {ch.distinguishing_test_assessment}", "tone": "flag"}
        rb = rebut(evidence, card, ch, client=client)
        yield {"type": "stage", "id": "rebuttal", "label": "Triage rebuttal",
               "detail": ("Conceded — " if rb.conceded else "Defends the call — ") + rb.argument,
               "tone": "verified" if rb.conceded else "escalate"}
        if rb.conceded:
            recommendation = "escalate" if tri.recommendation == "dismiss" else "dismiss"
            rev = Reverdict(outcome="conceded", disposition_changed=True,
                            note=f"Triage conceded the challenge; disposition changed to {recommendation}.")
        else:
            rev = re_verdict(evidence, tri.recommendation, card, ch, rb, client=client)
        final_status = "flagged" if rev.outcome == "holds" else "agreed"
        final_ver = Verifier(status=final_status, agrees_with_recommendation=final_status == "agreed",
                             note=rev.note or ver.note)
        debate = Debate(challenge=ch, rebuttal=rb, reverdict=rev)
        yield {"type": "stage", "id": "reverdict", "label": "Verifier re-verdict",
               "detail": {"holds": f"Flag holds — {rev.note}",
                          "convinced": f"Verifier convinced; flag resolved — {rev.note}",
                          "conceded": rev.note}[rev.outcome],
               "tone": "flag" if rev.outcome == "holds" else "verified"}

    # The disposition may have flipped — draft + confidence run off the post-debate recommendation.
    eff_tri = tri if recommendation == tri.recommendation else tri.model_copy(
        update={"recommendation": recommendation})
    confidence = compute_confidence(
        len(tri.fired_indicators), len(card.indicators), recommendation,
        verifier_flagged=final_ver.status == "flagged",
    )
    total = len(card.indicators)
    yield {
        "type": "stage", "id": "confidence",
        "label": "Computing confidence from indicator coverage",
        "detail": f"{len(tri.fired_indicators)}/{total} indicators fired → {round(confidence * 100)}%"
                  + (" (capped below review threshold)" if final_ver.status == "flagged" else ""),
    }

    str_draft = draft_str(alert, eff_tri, card, verifier_status=final_ver.status, client=client)
    yield {"type": "stage", "id": "draft", "label": "STR drafter",
           "detail": "Structured Suspicious Transaction Report drafted" if str_draft
                     else "Skipped — no report on a dismiss"}

    result = TriageResult(
        alert_id=alert.alert_id,
        recommendation=recommendation,
        confidence=confidence,
        explanation=tri.explanation,
        matched_typology=tri.matched_typology,
        cited_transaction_ids=tri.cited_transaction_ids,
        indicator_coverage=IndicatorCoverage(indicators=card.indicators, fired=tri.fired_indicators),
        verifier=final_ver,
        debate=debate,
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
