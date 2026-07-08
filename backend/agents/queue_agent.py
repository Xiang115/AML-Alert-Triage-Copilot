"""The Queue Agent's Auto-Clear Policy (ADR-0010).

Deterministic routing of an Alert after triage. The policy may **auto-clear**
(dismiss) only a confident, verifier-agreed dismiss; everything else is left for a
human. It never auto-escalates and never auto-files — the human-in-the-loop gate
the regulatory moat depends on (CONTEXT.md: Queue Agent, Auto-Clear Policy).
"""

from __future__ import annotations

from datetime import datetime

import config
from decision_control import DecisionControlPlane
from llm import complete_model
from schemas import AuditEntry, BlockedReason, LLMResponse, QueueNextAction, ShiftBriefing


def _control_plane(threshold: float = config.AUTO_CLEAR_THRESHOLD) -> DecisionControlPlane:
    return DecisionControlPlane(
        auto_clear_threshold=threshold,
        review_threshold=config.REVIEW_THRESHOLD,
        qa_sample_rate=config.QA_SAMPLE_RATE,
        borderline_margin=config.BORDERLINE_MARGIN,
    )


def auto_clear_policy(
    recommendation: str,
    confidence: float,
    verifier_status: str,
    threshold: float,
    *,
    debated: bool = False,
    screening_blocked: bool = False,
    suppressed: bool = False,
    review_threshold: float | None = None,
) -> str:
    plane = DecisionControlPlane(
        auto_clear_threshold=threshold,
        review_threshold=review_threshold if review_threshold is not None else config.REVIEW_THRESHOLD,
        qa_sample_rate=config.QA_SAMPLE_RATE,
        borderline_margin=config.BORDERLINE_MARGIN,
    )
    return plane.route_decision(
        recommendation=recommendation,
        confidence=confidence,
        verifier_status=verifier_status,
        debated=debated,
        screening_blocked=screening_blocked,
        suppressed=suppressed and review_threshold is not None,
    )


def route_triage(triage: dict, threshold: float) -> str:
    """Apply the Auto-Clear Policy to a stored (camelCase) triage dict — the adapter
    precompute uses to stamp `routing` onto each served Alert. A triage that carries a
    `debate` was contested (ADR-0011), or a `screening` hit (Slice B fail-safe), is
    firewalled to needsReview regardless of its final verdict."""
    return _control_plane(threshold).route_triage(triage)


def route_served_alert(alert: dict, threshold: float, review_threshold: float) -> str:
    """Serve-time routing that folds in a session-dynamic, envelope-gated suppression (ADR-0021).

    Distinct from `route_triage` (precompute, suppression-blind): a borderline dismiss carrying a
    matched `suppression` whose own ledger envelope is benign-consistent is **auto-cleared** — the
    analyst's prior clearance acting on a look-alike. The envelope gate (`envelope_benign_consistent`)
    is what stops a launderer reusing a cleared corridor: a drain/pass-through structure is denied the
    auto-clear and routes to a human. Needs the alert's transactions for that gate, so it runs on the
    detail path, not the transaction-less queue list. Falls back to plain routing when no suppression."""
    plane = DecisionControlPlane(
        auto_clear_threshold=threshold,
        review_threshold=review_threshold,
        qa_sample_rate=config.QA_SAMPLE_RATE,
        borderline_margin=config.BORDERLINE_MARGIN,
    )
    return plane.evaluate_alert(alert).routing


def stamp_routing(alerts: list[dict], threshold: float) -> list[dict]:
    """Return the served alerts with the Queue Agent's `routing` stamped on each.
    Pure (new dicts) — derived only from each alert's existing triage, so it adds no
    LLM cost and can re-stamp an already-precomputed results.json."""
    return [{**a, "routing": route_triage(a["triage"], threshold)} for a in alerts]


def build_audit_seed(alerts: list[dict], *, at: datetime) -> list[dict]:
    """The `autoClear` audit entries for the alerts the Queue Agent cleared, so the
    accountability trail opens populated with the autonomous run instead of empty
    until a human acts. Returns camelCase AuditEntry dicts ready to write/load."""
    seed = []
    for a in alerts:
        if a.get("routing") != "autoCleared":
            continue
        t = a["triage"]
        seed.append(
            AuditEntry(
                alert_id=a["alertId"],
                event="autoClear",
                at=at,
                ai_recommendation=t["recommendation"],
                confidence=t["confidence"],
                verifier_status=t["verifier"]["status"],
            ).model_dump(by_alias=True, mode="json")
        )
    return seed


def build_debate_audit_seed(alerts: list[dict], *, at: datetime) -> list[dict]:
    """The `debateResolved` audit entries for the alerts that entered an adversarial debate
    (ADR-0011), so the accountability trail records every contested call — the post-debate
    recommendation, the final verifier verdict, and the re-verdict note. Returns camelCase
    AuditEntry dicts; derived only from the stored triage, so it adds no LLM cost."""
    seed = []
    for a in alerts:
        t = a["triage"]
        debate = t.get("debate")
        if not debate:
            continue
        rev = debate["reverdict"]
        seed.append(
            AuditEntry(
                alert_id=a["alertId"],
                event="debateResolved",
                at=at,
                ai_recommendation=t["recommendation"],
                verifier_status=t["verifier"]["status"],
                note=rev.get("note", ""),
            ).model_dump(by_alias=True, mode="json")
        )
    return seed


_BLOCKED_REASON_META = {
    "escalation": (
        "Escalations to sign",
        "Escalation is consequential and can never be auto-cleared or auto-filed.",
    ),
    "screeningHit": (
        "Screening hits",
        "Sanctions or PEP screening matched a counterparty, so the alert stays with a human.",
    ),
    "adversarialDebate": (
        "Adversarial debate",
        "The agents contested the call; contested alerts are firewalled from auto-clear.",
    ),
    "verifierFlagged": (
        "Verifier flagged",
        "The independent verifier challenged the recommendation.",
    ),
    "revokedSuppression": (
        "Revoked suppressions",
        "A learned clearance was cancelled because network evidence made it unsafe.",
    ),
    "lowConfidenceDismiss": (
        "Low-confidence dismissals",
        "The alert was a dismiss, but confidence did not meet the auto-clear bar.",
    ),
    "other": (
        "Other review",
        "The alert stayed in review outside the standard autonomous-clear lanes.",
    ),
}


def blocked_reason_code(alert: dict) -> str:
    """Disjoint primary reason a non-cleared alert stayed in needsReview.

    This powers the Shift Briefing's blocked-reason breakdown. It intentionally chooses one primary
    reason per alert so counts add up to needsReview; per-alert Defense Case still carries the full
    overlapping control story.
    """
    return _control_plane().blocked_reason_code(alert)


def blocked_reason_breakdown(alerts: list[dict]) -> list[dict]:
    """Return non-zero blocked reasons as camelCase-ready dicts."""
    counts: dict[str, int] = {code: 0 for code in _BLOCKED_REASON_META}
    for alert in alerts:
        if alert.get("routing") == "autoCleared":
            continue
        counts[blocked_reason_code(alert)] += 1
    reasons: list[dict] = []
    for code, (label, explanation) in _BLOCKED_REASON_META.items():
        count = counts[code]
        if count:
            reasons.append(BlockedReason(
                code=code,
                label=label,
                count=count,
                explanation=explanation,
            ).model_dump(by_alias=True, mode="json"))
    return reasons


def next_shift_actions(*, auto_cleared: int, escalations: int, flagged: int, blocked_reasons: list[dict]) -> list[dict]:
    """Prioritized operating moves for the analyst shift.

    This turns the Queue Agent from a passive summary into workflow automation: it says what the
    human should do first, while still respecting the same no-auto-escalation/no-auto-filing gates.
    """
    actions: list[QueueNextAction] = []
    priority = 1

    if escalations:
        actions.append(QueueNextAction(
            priority=priority,
            label="Sign escalation-ready cases",
            lane="needsReview",
            count=escalations,
            rationale="Consequential cases stay human-gated; clear these first for filing SLA and compliance review.",
        ))
        priority += 1

    challenged = sum(
        reason["count"]
        for reason in blocked_reasons
        if reason["code"] in {"screeningHit", "adversarialDebate", "verifierFlagged", "revokedSuppression"}
    )
    if challenged:
        actions.append(QueueNextAction(
            priority=priority,
            label="Resolve challenged decisions",
            lane="needsReview",
            count=challenged,
            rationale="Verifier, screening, debate, or network-revocation controls challenged the automation path.",
        ))
        priority += 1

    low_confidence = next(
        (reason["count"] for reason in blocked_reasons if reason["code"] == "lowConfidenceDismiss"),
        0,
    )
    if low_confidence:
        actions.append(QueueNextAction(
            priority=priority,
            label="Review low-confidence dismissals",
            lane="needsReview",
            count=low_confidence,
            rationale="These are benign-looking alerts that failed the auto-clear confidence bar.",
        ))
        priority += 1

    if auto_cleared:
        actions.append(QueueNextAction(
            priority=priority,
            label="Spot-check cleared lane",
            lane="qaSample",
            count=auto_cleared,
            rationale="The agent removed benign noise, but sampled clears remain inspectable for leakage control.",
        ))

    return [a.model_dump(by_alias=True, mode="json") for a in actions[:3]]


def build_shift_briefing(alerts: list[dict], *, at: datetime) -> dict:
    """The Queue Agent's Shift Briefing over the routed queue (ADR-0010): deterministic
    counts + a templated narrative the analyst reads on arrival. Returns a camelCase dict.
    `escalations`/`flagged` are lenses on needsReview and may overlap."""
    total = len(alerts)
    review = [a for a in alerts if a.get("routing") != "autoCleared"]
    auto_cleared = total - len(review)
    escalations = sum(a["triage"]["recommendation"] == "escalate" for a in review)
    flagged = sum(a["triage"]["verifier"]["status"] == "flagged" for a in review)
    blocked_reasons = blocked_reason_breakdown(alerts)
    next_actions = next_shift_actions(
        auto_cleared=auto_cleared,
        escalations=escalations,
        flagged=flagged,
        blocked_reasons=blocked_reasons,
    )
    top_block = blocked_reasons[0] if blocked_reasons else None
    blocked_note = f"; top review reason: {top_block['label']} ({top_block['count']})" if top_block else ""
    summary = (
        f"Processed {total} alerts overnight. Auto-cleared {auto_cleared} high-confidence "
        f"benign dismissals; {len(review)} need your review "
        f"({escalations} escalations to sign, {flagged} flagged for judgment{blocked_note})."
    )
    return ShiftBriefing(
        generated_at=at,
        processed=total,
        auto_cleared=auto_cleared,
        needs_review=len(review),
        escalations=escalations,
        flagged=flagged,
        blocked_reasons=blocked_reasons,
        next_actions=next_actions,
        summary=summary,
    ).model_dump(by_alias=True, mode="json")


class _BriefingNarrative(LLMResponse):
    """The single field the briefing narrator writes."""
    summary: str


_BRIEFING_SYSTEM = (
    "You are the overnight AML triage agent reporting to the analyst arriving for their shift. "
    "In 2-3 crisp sentences, first person plural (\"We processed...\"), summarise what was done to the "
    "alert queue overnight, grounded ONLY in the numbers provided — invent no names, amounts, or "
    "specifics. Make clear that auto-cleared items were high-confidence, verifier-agreed benign "
    "dismissals and that every uncertain call was left for the human. "
    'Reply ONLY with JSON: {"summary": "..."}.'
)


def narrate_briefing(briefing: dict, *, client=None, model: str | None = None) -> str:
    """LLM-written Shift Briefing narrative (#8): the agentic flourish over the deterministic
    counts. Precomputed (ADR-0003) so it carries no demo latency, and the caller falls back to
    the deterministic `summary` if this raises. Runs on the cheap verifier model."""
    blocked = ", ".join(
        f"{reason['label']}={reason['count']}"
        for reason in briefing.get("blockedReasons", [])
    )
    parsed = complete_model(
        _BRIEFING_SYSTEM,
        f"Alerts processed: {briefing['processed']}\n"
        f"Auto-cleared (high-confidence, verifier-agreed benign dismissals): {briefing['autoCleared']}\n"
        f"Routed to human review: {briefing['needsReview']}\n"
        f"  - escalations to sign: {briefing['escalations']}\n"
        f"  - flagged for judgment: {briefing['flagged']}\n"
        f"Blocked reasons: {blocked or 'none'}",
        model or config.MODEL_VERIFIER,
        _BriefingNarrative,
        client=client,
    )
    return parsed.summary
