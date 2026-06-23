"""The Queue Agent's Auto-Clear Policy (ADR-0010).

Deterministic routing of an Alert after triage. The policy may **auto-clear**
(dismiss) only a confident, verifier-agreed dismiss; everything else is left for a
human. It never auto-escalates and never auto-files — the human-in-the-loop gate
the regulatory moat depends on (CONTEXT.md: Queue Agent, Auto-Clear Policy).
"""

from __future__ import annotations

from datetime import datetime

import config
from llm import complete_model
from schemas import AuditEntry, LLMResponse, ShiftBriefing


def auto_clear_policy(
    recommendation: str,
    confidence: float,
    verifier_status: str,
    threshold: float,
) -> str:
    if (
        recommendation == "dismiss"
        and verifier_status == "agreed"
        and confidence >= threshold
    ):
        return "autoCleared"
    return "needsReview"


def route_triage(triage: dict, threshold: float) -> str:
    """Apply the Auto-Clear Policy to a stored (camelCase) triage dict — the adapter
    precompute uses to stamp `routing` onto each served Alert."""
    return auto_clear_policy(
        triage["recommendation"],
        triage["confidence"],
        triage["verifier"]["status"],
        threshold,
    )


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


def build_shift_briefing(alerts: list[dict], *, at: datetime) -> dict:
    """The Queue Agent's Shift Briefing over the routed queue (ADR-0010): deterministic
    counts + a templated narrative the analyst reads on arrival. Returns a camelCase dict.
    `escalations`/`flagged` are lenses on needsReview and may overlap."""
    total = len(alerts)
    review = [a for a in alerts if a.get("routing") != "autoCleared"]
    auto_cleared = total - len(review)
    escalations = sum(a["triage"]["recommendation"] == "escalate" for a in review)
    flagged = sum(a["triage"]["verifier"]["status"] == "flagged" for a in review)
    summary = (
        f"Processed {total} alerts overnight. Auto-cleared {auto_cleared} high-confidence "
        f"benign dismissals; {len(review)} need your review "
        f"({escalations} escalations to sign, {flagged} flagged for judgment)."
    )
    return ShiftBriefing(
        generated_at=at,
        processed=total,
        auto_cleared=auto_cleared,
        needs_review=len(review),
        escalations=escalations,
        flagged=flagged,
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
    parsed = complete_model(
        _BRIEFING_SYSTEM,
        f"Alerts processed: {briefing['processed']}\n"
        f"Auto-cleared (high-confidence, verifier-agreed benign dismissals): {briefing['autoCleared']}\n"
        f"Routed to human review: {briefing['needsReview']}\n"
        f"  - escalations to sign: {briefing['escalations']}\n"
        f"  - flagged for judgment: {briefing['flagged']}",
        model or config.MODEL_VERIFIER,
        _BriefingNarrative,
        client=client,
    )
    return parsed.summary
