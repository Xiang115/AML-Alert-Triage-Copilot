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

import logging
from collections.abc import Iterator
from datetime import datetime

import config
from agents.anchoring import anchor_claims, evidence_integrity
from agents.confidence import compute_confidence
from agents.evidence import render_alert_evidence
from agents.knowledge_base import get_card, rank_cards, select_cards
from agents.screening import screen
from agents.str_drafter import draft_str
from agents.triage import NO_MATCH_CODE, rebut, triage
from agents.verifier import challenge, re_verdict, verify
from schemas import AlertInput, Debate, EvidenceIntegrity, IndicatorCoverage, Reverdict, TriageResult, Verifier

logger = logging.getLogger("pipeline")


def _alert_with_triage(alert: AlertInput, triage_dict: dict) -> dict:
    return {
        "alertId": alert.alert_id,
        "transactions": [t.model_dump(by_alias=True, mode="json") for t in (alert.transactions or [])],
        "triage": triage_dict,
    }


def _memory_context(suppression: dict | None) -> str | None:
    if not suppression:
        return None
    status = suppression.get("status")
    if status == "revoked":
        return (
            f"Prior clearance {suppression.get('sourceDecisionId')} matched signature "
            f"{suppression.get('signature')}, but network risk revoked it "
            f"({suppression.get('revokedNetworkId')}). Treat this as evidence against auto-clear."
        )
    return (
        f"Prior human dismissal {suppression.get('sourceDecisionId')} cleared signature "
        f"{suppression.get('signature')} {suppression.get('clearedCount')} time(s). "
        "Use it as benign-precedent evidence only if this alert's ledger still fits the same benign envelope."
    )


def enrich_served_alert(alert: dict) -> dict:
    """Slice A serve-time decorator: additive, deterministic enrichment of a served alert dict.
    Suppression is session-dynamic (it depends on decisions made this session), so it is computed
    at serve time here rather than baked into results.json. Screening (Slice B) is deterministic
    and already persisted on the triage by the pipeline, so it is NOT recomputed here."""
    from agents.memory import suppress

    triage = alert.get("triage")
    if triage is None:
        return alert
    # A learned suppression is benign-precedent context for a dismiss; it must never paint a
    # "matches a previously cleared pattern" panel onto a confident escalate (which it can, since
    # suppress() matches on the behavioral envelope alone). Gate the served display on the
    # recommendation — the triage-time memory_context (below) is unaffected.
    triage["suppression"] = suppress(alert) if triage.get("recommendation") == "dismiss" else None
    return alert


def resolve_concession(prior: str, fired_count: int, min_fired_to_resist: int) -> tuple[str, bool]:
    """Cost-sensitive gate on a Triage concession in the adversarial debate (ADR-0011/0012).

    A concession flips the disposition. We **honour a dismiss→escalate concession always** (catching
    more is the safe direction in AML), but **resist an escalate→dismiss concession when the typology
    match is strong** (>= `min_fired_to_resist` indicators fired): a multi-indicator escalation must
    not be silently dropped by a generic benign hypothesis — it HOLDS as escalate and routes to a
    human (needsReview), because a missed report is the costly error. This is what makes the debate
    *discriminative*: on SAML-D the verifier's "retained balance / no full forwarding" challenge fires
    the same on real consolidation and benign collection, so without this gate Triage conceded away
    true FI/ST reports. Returns (recommendation, flipped). Pure — unit-tested without tokens."""
    if prior == "dismiss":
        return "escalate", True
    if fired_count >= min_fired_to_resist:
        return "escalate", False  # strong match: resist the drop, hold for a human
    return "dismiss", True         # weak match: honour the concession


def run_triage_events(
    alert: AlertInput, *, client=None, cost_sensitive: bool = False, semantic: bool = False
) -> Iterator[dict]:
    """Run the pipeline, yielding one event per step so the UI can reveal the agent's
    reasoning live. Stage/indicator events are JSON-friendly dicts; the terminal event
    is {"type": "result", "triage": <TriageResult>} carrying the assembled object."""
    evidence = render_alert_evidence(alert)
    cards = select_cards(alert)
    # Cheap, deterministic relevance pre-rank for the retrieve step (display only — all cards
    # still go to triage, so the cached prompt prefix and recall are untouched, ADR-0002).
    ranked = rank_cards(evidence, cards)
    top = ", ".join(f"{c.code} ({score:g})" for c, score in ranked[:3] if score > 0) or "no strong signal"
    yield {
        "type": "stage", "id": "retrieve",
        "label": "Retrieving & ranking typology cards (FATF / BNM)",
        "detail": f"Ranked {len(cards)} candidate cards by signal overlap — strongest: {top}. "
                  f"All passed to triage to reason over.",
    }

    # Deterministic sanctions/PEP screening, computed once and persisted on the result. A hit
    # disqualifies the alert from auto-clear (queue_agent.auto_clear_policy reads screening.blocked).
    screening = screen(alert)
    yield {
        "type": "stage", "id": "screening",
        "label": "Sanctions / PEP screening",
        "detail": (f"Screened {screening.screened_counterparties} counterparties — "
                   + (f"MATCH: {screening.matches[0].matched_name} ({screening.matches[0].list_name}) "
                      "— human review required" if screening.blocked else "no watchlist matches")),
        "tone": "flag" if screening.blocked else "verified",
    }

    tri = triage(evidence, cards, client=client, cost_sensitive=cost_sensitive)

    if tri.matched_typology.code == NO_MATCH_CODE:
        result = TriageResult(
            alert_id=alert.alert_id,
            recommendation="dismiss",
            confidence=compute_confidence(0, 0, "dismiss", verifier_flagged=False),
            claims=[],
            evidence_integrity=EvidenceIntegrity(anchored_count=0, unanchored_count=0, total_count=0),
            matched_typology=tri.matched_typology,
            cited_transaction_ids=[],
            indicator_coverage=IndicatorCoverage(indicators=[], fired=[]),
            verifier=Verifier(
                status="agreed",
                agrees_with_recommendation=True,
                claims=[],
            ),
            screening=screening,
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

    alert_txns = list(alert.transactions or [])
    triage_traced, _ = anchor_claims(
        tri.claims,
        citable_transactions=alert_txns,
        fired_indicators=tri.fired_indicators,
        matched_typology_name=tri.matched_typology.name,
    )
    triage_integrity = evidence_integrity(triage_traced)

    yield {
        "type": "stage", "id": "triage", "label": "Triage agent — assessing the call",
        "detail": f"{'Escalate' if tri.recommendation == 'escalate' else 'Dismiss'} — "
                  f"matched {card.code} {card.name}. "
                  f"{triage_integrity.anchored_count}/{triage_integrity.total_count} grounds evidence-anchored.",
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

    from agents.memory import suppress

    triage_memory_dict = {
        "recommendation": tri.recommendation,
        "matchedTypology": tri.matched_typology.model_dump(by_alias=True, mode="json"),
        "citedTransactionIds": tri.cited_transaction_ids,
    }
    learned_suppression = suppress(_alert_with_triage(alert, triage_memory_dict))
    memory_context = _memory_context(learned_suppression)
    if learned_suppression:
        yield {
            "type": "stage",
            "id": "learned-memory",
            "label": "Learned memory retrieved",
            "detail": (
                f"{learned_suppression['status']} — cites decision "
                f"{learned_suppression['sourceDecisionId']} for {learned_suppression['signature']}"
            ),
            "tone": "verified" if learned_suppression["status"] == "suppressed" else "flag",
        }

    ver, ver_claims = verify(
        evidence,
        tri.recommendation,
        card,
        client=client,
        memory_context=memory_context,
    )
    ver_traced, _ = anchor_claims(
        ver_claims, citable_transactions=alert_txns, fired_indicators=tri.fired_indicators,
        matched_typology_name=tri.matched_typology.name)
    ver = ver.model_copy(update={"claims": ver_traced})
    yield {
        "type": "stage", "id": "verifier", "label": "Adversarial verifier — challenging the call",
        "detail": f"{'FLAGGED for human review' if ver.status == 'flagged' else 'Agreed'} — "
                  f"{len(ver_traced)} ground(s) assessed.",
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
            recommendation, flipped = resolve_concession(
                tri.recommendation, len(tri.fired_indicators), config.DEBATE_RESIST_MIN_FIRED)
            if flipped:
                rev = Reverdict(outcome="conceded", disposition_changed=True,
                                note=f"Triage conceded the challenge; disposition changed to {recommendation}.")
            else:
                # Cost-sensitive gate (ADR-0012): a strong multi-indicator escalation is not dropped
                # by the concession — it holds as escalate and routes to a human, never auto-dismissed.
                rev = Reverdict(outcome="holds", disposition_changed=False,
                                note=(f"Triage conceded, but {len(tri.fired_indicators)} indicators fired — "
                                      f"too strong a match to auto-dismiss; held as escalate for human review."))
        else:
            rev = re_verdict(evidence, tri.recommendation, card, ch, rb, client=client)
        final_status = "flagged" if rev.outcome == "holds" else "agreed"
        final_ver = Verifier(status=final_status, agrees_with_recommendation=final_status == "agreed",
                             claims=ver.claims)
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
                  + (" (capped below review threshold)"
                     if final_ver.status == "flagged" and recommendation == "dismiss" else ""),
    }

    str_draft = draft_str(alert, eff_tri, card, verifier_status=final_ver.status, client=client)
    yield {"type": "stage", "id": "draft", "label": "STR drafter",
           "detail": "Structured Suspicious Transaction Report drafted" if str_draft
                     else "Skipped — no report on a dismiss"}

    # LLM semantic anchor (ADR-0013) — off by default (deterministic demo path); the live
    # /triage?semantic=true Q&A opts in. One cheap MODEL_VERIFIER call reviews whether the evidence
    # actually substantiates each drafted claim, annotating (never editing) the report. Best-effort:
    # it is an advisory extra, so a provider failure must NOT discard the fresh live triage — on
    # error we keep the deterministic draft (verdicts stay None) and note that the reviewer was
    # unavailable, rather than letting the whole /triage fall back to precomputed.
    if semantic and str_draft is not None:
        try:
            from agents.semantic_anchor import semantic_review

            str_draft = semantic_review(str_draft, eff_tri, card, client=client)
            reviewed = str_draft.traced_claims or []
            yield {"type": "stage", "id": "semantic",
                   "label": "LLM semantic review of the drafted claims",
                   "detail": f"{sum(1 for c in reviewed if c.semantic_verdict == 'supported')} supported, "
                             f"{sum(1 for c in reviewed if c.semantic_verdict == 'unsupported')} unsupported, "
                             f"{sum(1 for c in reviewed if c.semantic_verdict == 'unclear')} unclear",
                   "tone": "verified"}
        except Exception as e:  # noqa: BLE001 — advisory pass; never fail the live triage over it
            logger.warning("Semantic review failed for %s (%s); serving the unannotated draft.",
                           alert.alert_id, e)
            yield {"type": "stage", "id": "semantic",
                   "label": "LLM semantic review of the drafted claims",
                   "detail": "Skipped — the semantic reviewer was unavailable; the deterministic anchoring stands.",
                   "tone": "flag"}

    result = TriageResult(
        alert_id=alert.alert_id,
        recommendation=recommendation,
        confidence=confidence,
        claims=triage_traced,
        evidence_integrity=triage_integrity,
        matched_typology=tri.matched_typology,
        cited_transaction_ids=tri.cited_transaction_ids,
        indicator_coverage=IndicatorCoverage(indicators=card.indicators, fired=tri.fired_indicators),
        verifier=final_ver,
        debate=debate,
        screening=screening,
        suppression=learned_suppression,
        str_draft=str_draft,
        model=config.MODEL_WORKHORSE,
        generated_at=datetime.now(),
    )
    yield {"type": "result", "triage": result}


def run_triage(
    alert: AlertInput, *, client=None, cost_sensitive: bool = False, semantic: bool = False
) -> TriageResult:
    """Batch path: run the pipeline and return the final assembled result."""
    result: TriageResult | None = None
    for ev in run_triage_events(alert, client=client, cost_sensitive=cost_sensitive, semantic=semantic):
        if ev["type"] == "result":
            result = ev["triage"]
    assert result is not None, "run_triage_events must yield a result event"
    return result
