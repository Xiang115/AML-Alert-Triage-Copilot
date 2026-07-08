"""The analyst Decision applied to an Alert (CONTEXT.md: Decision, Disposition).

The disposition->STR invariant lives here as one pure function, off the FastAPI
store: a `dismiss` drops the STR draft; an `escalate` keeps the existing draft, or
replaces it with the analyst's edit. The serving store stays dict (ADR-0008) — the
endpoint applies this result and records a typed `schemas.Decision`.
"""

from __future__ import annotations

from schemas import STRDraft


def final_disposition_for(recommendation: str, action: str) -> str:
    """Approving keeps the AI recommendation; overriding flips it."""
    if action == "approve":
        return recommendation
    return "dismiss" if recommendation == "escalate" else "escalate"


def resolve_str_draft(
    current: dict | None,
    final_disposition: str,
    edited: STRDraft | None,
) -> dict | None:
    """The STR draft after a decision (as a camelCase dict for the store):
    dropped on `dismiss`; replaced by the analyst's edit on `escalate`, or kept
    as-is when they didn't edit."""
    if final_disposition == "dismiss":
        return None
    if edited is not None:
        return edited.model_dump(by_alias=True, mode="json")
    return current


def learn_from_decision(alert: dict, decision) -> None:
    """Slice A: learn a suppression pattern from a human dismiss so future look-alikes surface it.
    A no-op on escalate/approve — only a benign dismiss teaches a clearance. Records the clearance
    against the alert's behavioral-envelope signature (agents.memory.signature)."""
    if decision.final_disposition != "dismiss":
        return

    import store
    from agents.memory import signature

    sig = signature(alert)
    if not sig:
        return

    store.record_clearance(
        signature=sig,
        typology=alert["triage"]["matchedTypology"]["code"],
        source_decision_id=alert["alertId"],
        source_alert_id=alert["alertId"],
        cleared_at=decision.decided_at.isoformat(),
    )
