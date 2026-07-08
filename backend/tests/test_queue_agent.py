import json
from datetime import datetime

from agents.queue_agent import (
    auto_clear_policy,
    blocked_reason_breakdown,
    build_audit_seed,
    build_debate_audit_seed,
    build_shift_briefing,
    narrate_briefing,
    route_served_alert,
    route_triage,
    stamp_routing,
)
from config import AUTO_CLEAR_THRESHOLD, REVIEW_THRESHOLD
from schemas import AuditEntry, ShiftBriefing

# A borderline dismiss confidence: below the auto-clear threshold, at/above the review threshold —
# exactly the band a learned suppression is allowed to auto-clear (ADR-0021).
_BORDERLINE = (AUTO_CLEAR_THRESHOLD + REVIEW_THRESHOLD) / 2  # 0.725 with the defaults

# Minimal ledgers compute_activity_profile accepts; the sweep tell drives the envelope gate.
_BENIGN_TXNS = [
    {"amount": 8000, "direction": "inbound", "currency": "MYR", "runningBalance": 11000,
     "flags": [], "counterpartyAccount": "CP1"},
    {"amount": 3000, "direction": "outbound", "currency": "MYR", "runningBalance": 8000,
     "flags": [], "counterpartyAccount": "CP1"},
]  # peak 11000, low 8000 -> not swept -> benign-consistent
_DRAIN_TXNS = [
    {"amount": 10000, "direction": "inbound", "currency": "MYR", "runningBalance": 10200,
     "flags": [], "counterpartyAccount": "CP1"},
    {"amount": 10000, "direction": "outbound", "currency": "MYR", "runningBalance": 200,
     "flags": [], "counterpartyAccount": "CP1"},
]  # peak 10200, low 200 -> swept to ~0 -> the pass-through tell
_SUPPRESSED = {"status": "suppressed", "matchedPatternId": "sig:x"}


def _served(confidence=_BORDERLINE, *, suppression=_SUPPRESSED, txns=None, recommendation="dismiss",
            verifier="agreed", debate=None, screening=None):
    return {"alertId": "X", "transactions": _BENIGN_TXNS if txns is None else txns,
            "triage": {"recommendation": recommendation, "confidence": confidence,
                       "verifier": {"status": verifier}, "suppression": suppression,
                       "debate": debate, "screening": screening}}


def test_suppression_auto_clears_a_borderline_dismiss():
    # ADR-0021: a matched suppression expands the frontier to a borderline dismiss the plain policy
    # would leave for a human.
    assert auto_clear_policy("dismiss", _BORDERLINE, "agreed", AUTO_CLEAR_THRESHOLD,
                             suppressed=True, review_threshold=REVIEW_THRESHOLD) == "autoCleared"
    assert auto_clear_policy("dismiss", _BORDERLINE, "agreed", AUTO_CLEAR_THRESHOLD,
                             suppressed=False, review_threshold=REVIEW_THRESHOLD) == "needsReview"


def test_suppression_requires_an_explicit_review_threshold():
    # Historical adapter behavior: callers must opt in to the suppression floor explicitly.
    assert auto_clear_policy("dismiss", _BORDERLINE, "agreed", AUTO_CLEAR_THRESHOLD,
                             suppressed=True) == "needsReview"


def test_suppression_never_clears_below_the_review_threshold():
    # The firewall floor: a suppression never clears a dismiss below the human review threshold.
    assert auto_clear_policy("dismiss", REVIEW_THRESHOLD - 0.05, "agreed", AUTO_CLEAR_THRESHOLD,
                             suppressed=True, review_threshold=REVIEW_THRESHOLD) == "needsReview"


def test_suppression_never_clears_an_escalate_flag_debate_or_screening_hit():
    # A suppression only ever auto-DISMISSES a verifier-agreed dismiss — never past the firewall.
    common = dict(suppressed=True, review_threshold=REVIEW_THRESHOLD)
    assert auto_clear_policy("escalate", _BORDERLINE, "agreed", AUTO_CLEAR_THRESHOLD, **common) == "needsReview"
    assert auto_clear_policy("dismiss", _BORDERLINE, "flagged", AUTO_CLEAR_THRESHOLD, **common) == "needsReview"
    assert auto_clear_policy("dismiss", _BORDERLINE, "agreed", AUTO_CLEAR_THRESHOLD,
                             debated=True, **common) == "needsReview"
    assert auto_clear_policy("dismiss", _BORDERLINE, "agreed", AUTO_CLEAR_THRESHOLD,
                             screening_blocked=True, **common) == "needsReview"


def test_route_served_clears_a_suppressed_borderline_dismiss_with_benign_envelope():
    assert route_served_alert(_served(), AUTO_CLEAR_THRESHOLD, REVIEW_THRESHOLD) == "autoCleared"


def test_route_served_denies_the_clear_when_the_envelope_shows_a_drain_tell():
    # Gate 2: a matched pattern is not enough — a drain/pass-through look-alike routes to a human,
    # so a cleared corridor cannot be reused without changing the structure that cleared it.
    assert route_served_alert(_served(txns=_DRAIN_TXNS), AUTO_CLEAR_THRESHOLD, REVIEW_THRESHOLD) == "needsReview"


def test_route_served_matches_plain_routing_without_a_suppression():
    # Suppression-blind parity: no suppression -> same result as route_triage.
    alert = _served(suppression=None)
    assert route_served_alert(alert, AUTO_CLEAR_THRESHOLD, REVIEW_THRESHOLD) == "needsReview"
    assert route_served_alert(alert, AUTO_CLEAR_THRESHOLD, REVIEW_THRESHOLD) == route_triage(
        alert["triage"], AUTO_CLEAR_THRESHOLD)

# Two stamped alerts reused across the seed/briefing tests: one auto-cleared, one for review.
_CLEARED = {"alertId": "A", "routing": "autoCleared",
            "triage": {"recommendation": "dismiss", "confidence": 0.95,
                       "verifier": {"status": "agreed"}}}
_REVIEW = {"alertId": "B", "routing": "needsReview",
           "triage": {"recommendation": "escalate", "confidence": 0.4,
                      "verifier": {"status": "flagged"}}}


def test_build_audit_seed_emits_one_autoclear_entry_per_cleared_alert():
    at = datetime(2026, 6, 23, 6, 0, 0)
    seed = build_audit_seed([_CLEARED, _REVIEW], at=at)
    assert len(seed) == 1  # only the auto-cleared alert
    e = AuditEntry.model_validate(seed[0])  # conforms to the audit-trail contract
    assert e.event == "autoClear"
    assert e.alert_id == "A"
    assert e.ai_recommendation == "dismiss"
    assert e.confidence == 0.95
    assert e.verifier_status == "agreed"


def test_build_debate_audit_seed_records_each_debated_alert():
    # ADR-0011: every alert that entered an adversarial debate writes a debateResolved entry, so the
    # accountability trail captures the contested calls (post-debate recommendation, final verdict).
    at = datetime(2026, 6, 23, 6, 0, 0)
    debated = {"alertId": "C", "triage": {
        "recommendation": "escalate", "confidence": 0.5, "verifier": {"status": "agreed"},
        "debate": {"reverdict": {"outcome": "conceded", "dispositionChanged": True,
                                 "note": "Triage conceded; disposition changed to escalate."}}}}
    plain = {"alertId": "A", "triage": {"recommendation": "dismiss", "confidence": 0.95,
                                        "verifier": {"status": "agreed"}}}
    seed = build_debate_audit_seed([debated, plain], at=at)
    assert len(seed) == 1  # only the debated alert
    e = AuditEntry.model_validate(seed[0])
    assert e.event == "debateResolved"
    assert e.alert_id == "C"
    assert e.ai_recommendation == "escalate"  # the post-debate recommendation
    assert e.verifier_status == "agreed"
    assert "conceded" in e.note


def test_narrate_briefing_returns_llm_summary_grounded_in_counts(make_client):
    # #8: the LLM rewrites the summary from the deterministic counts (no tokens — fake client).
    fake = make_client([json.dumps({"summary": "We processed 16 alerts overnight and cleared 3."})])
    briefing = {"processed": 16, "autoCleared": 3, "needsReview": 13, "escalations": 13, "flagged": 5}
    out = narrate_briefing(briefing, client=fake)
    assert out == "We processed 16 alerts overnight and cleared 3."
    assert "16" in json.dumps(fake.calls[0])  # the counts were actually sent to the model


def test_build_shift_briefing_counts_the_routed_queue():
    at = datetime(2026, 6, 23, 6, 0, 0)
    b = build_shift_briefing([_CLEARED, _REVIEW], at=at)
    sb = ShiftBriefing.model_validate(b)  # conforms to the wire contract
    assert sb.processed == 2
    assert sb.auto_cleared == 1
    assert sb.needs_review == 1
    assert sb.escalations == 1  # _REVIEW is an escalate
    assert sb.flagged == 1  # _REVIEW is verifier-flagged
    assert [r.code for r in sb.blocked_reasons] == ["escalation"]
    assert sb.blocked_reasons[0].count == 1
    assert sb.next_actions[0].label == "Sign escalation-ready cases"
    assert sb.next_actions[0].lane == "needsReview"
    assert sb.next_actions[-1].label == "Spot-check cleared lane"
    assert "2" in sb.summary  # the narrative mentions the counts


def test_blocked_reason_breakdown_is_disjoint_and_explains_refused_autonomy():
    alerts = [
        _CLEARED,
        _REVIEW,  # escalation and verifier-flagged; primary reason is escalation
        {"alertId": "C", "routing": "needsReview",
         "triage": {"recommendation": "dismiss", "confidence": 0.95,
                    "verifier": {"status": "agreed"},
                    "screening": {"blocked": True}}},
        {"alertId": "D", "routing": "needsReview",
         "triage": {"recommendation": "dismiss", "confidence": 0.95,
                    "verifier": {"status": "agreed"},
                    "debate": {"reverdict": {"outcome": "holds"}}}},
        {"alertId": "E", "routing": "needsReview",
         "triage": {"recommendation": "dismiss", "confidence": 0.95,
                    "verifier": {"status": "flagged"}}},
        {"alertId": "F", "routing": "needsReview",
         "triage": {"recommendation": "dismiss", "confidence": 0.8,
                    "verifier": {"status": "agreed"},
                    "suppression": {"status": "revoked"}}},
        {"alertId": "G", "routing": "needsReview",
         "triage": {"recommendation": "dismiss", "confidence": 0.5,
                    "verifier": {"status": "agreed"}}},
    ]

    breakdown = blocked_reason_breakdown(alerts)
    counts = {r["code"]: r["count"] for r in breakdown}
    assert sum(counts.values()) == 6  # every needsReview alert has exactly one primary reason
    assert counts == {
        "escalation": 1,
        "screeningHit": 1,
        "adversarialDebate": 1,
        "verifierFlagged": 1,
        "revokedSuppression": 1,
        "lowConfidenceDismiss": 1,
    }


def test_stamp_routing_sets_routing_on_each_alert_without_mutating_input():
    alerts = [
        {"alertId": "A", "triage": {"recommendation": "dismiss", "confidence": 0.95,
                                     "verifier": {"status": "agreed"}}},
        {"alertId": "B", "triage": {"recommendation": "escalate", "confidence": 0.95,
                                    "verifier": {"status": "agreed"}}},
    ]
    out = stamp_routing(alerts, threshold=0.85)
    assert [a["routing"] for a in out] == ["autoCleared", "needsReview"]
    assert "routing" not in alerts[0]  # pure: original list untouched


def test_route_triage_reads_the_stored_triage_dict():
    # extracts recommendation/confidence/verifier.status from the camelCase triage dict
    cleared = {"recommendation": "dismiss", "confidence": 0.9, "verifier": {"status": "agreed"}}
    review = {"recommendation": "escalate", "confidence": 0.9, "verifier": {"status": "agreed"}}
    assert route_triage(cleared, threshold=0.85) == "autoCleared"
    assert route_triage(review, threshold=0.85) == "needsReview"


def test_route_triage_firewalls_a_debated_alert():
    # ADR-0011: a stored triage carrying a `debate` was contested, so it never auto-clears even
    # when its FINAL verdict is a confident, verifier-agreed dismiss. Same verdict without a debate
    # still clears — the firewall is the only difference.
    debated = {"recommendation": "dismiss", "confidence": 0.95, "verifier": {"status": "agreed"},
               "debate": {"reverdict": {"outcome": "convinced", "dispositionChanged": False}}}
    undebated = {"recommendation": "dismiss", "confidence": 0.95, "verifier": {"status": "agreed"}}
    assert route_triage(debated, threshold=0.85) == "needsReview"
    assert route_triage(undebated, threshold=0.85) == "autoCleared"


def test_auto_clear_bar_sits_above_the_review_threshold():
    # ADR-0010 safety invariant: a verifier-flagged alert is capped just below
    # REVIEW_THRESHOLD, so the auto-clear bar must sit strictly above it — a flagged
    # or borderline dismiss can then never auto-clear on confidence alone.
    assert AUTO_CLEAR_THRESHOLD > REVIEW_THRESHOLD


def test_confident_agreed_dismiss_is_auto_cleared():
    assert auto_clear_policy("dismiss", 0.92, "agreed", threshold=0.85) == "autoCleared"


def test_escalate_is_never_auto_cleared():
    # even at high confidence with the verifier agreeing, an escalate must reach a human
    assert auto_clear_policy("escalate", 0.99, "agreed", threshold=0.85) == "needsReview"


def test_verifier_flag_is_never_auto_cleared():
    # the verifier challenged the call — a human adjudicates even a high-confidence dismiss
    assert auto_clear_policy("dismiss", 0.95, "flagged", threshold=0.85) == "needsReview"


def test_debated_alert_is_never_auto_cleared():
    # ADR-0011 firewall: an alert that entered an adversarial debate routes to a human even when
    # the debate resolved to a confident, verifier-agreed dismiss — we never auto-clear a contested
    # call, so autoClearPrecision is untouched by the debate.
    assert auto_clear_policy("dismiss", 0.95, "agreed", threshold=0.85, debated=True) == "needsReview"


def test_screening_hit_is_never_auto_cleared():
    # Slice B fail-safe: a sanctions/PEP watchlist hit routes to a human even on an otherwise
    # confident, verifier-agreed dismiss — a screened counterparty is never auto-cleared.
    assert auto_clear_policy(
        "dismiss", 0.95, "agreed", threshold=0.85, screening_blocked=True) == "needsReview"


def test_route_triage_firewalls_a_screening_hit():
    # the disqualifier reads the persisted screening.blocked off the stored triage dict, so routing
    # and the panel read the same value; a clean screen still clears on the usual conditions.
    hit = {"recommendation": "dismiss", "confidence": 0.95, "verifier": {"status": "agreed"},
           "screening": {"blocked": True}}
    clean = {"recommendation": "dismiss", "confidence": 0.95, "verifier": {"status": "agreed"},
             "screening": {"blocked": False}}
    no_screening = {"recommendation": "dismiss", "confidence": 0.95, "verifier": {"status": "agreed"}}
    assert route_triage(hit, threshold=0.85) == "needsReview"
    assert route_triage(clean, threshold=0.85) == "autoCleared"
    assert route_triage(no_screening, threshold=0.85) == "autoCleared"  # backward compatible


def test_low_confidence_dismiss_needs_review():
    # an uncertain dismiss below the auto-clear bar reaches a human even if the verifier agrees
    assert auto_clear_policy("dismiss", 0.70, "agreed", threshold=0.85) == "needsReview"


def test_confidence_exactly_at_threshold_is_inclusive():
    # the bar is >= : a dismiss landing exactly on the threshold still clears
    assert auto_clear_policy("dismiss", 0.85, "agreed", threshold=0.85) == "autoCleared"
