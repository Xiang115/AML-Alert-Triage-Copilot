import json
from datetime import datetime

from agents.queue_agent import (
    auto_clear_policy,
    build_audit_seed,
    build_debate_audit_seed,
    build_shift_briefing,
    narrate_briefing,
    route_triage,
    stamp_routing,
)
from config import AUTO_CLEAR_THRESHOLD, REVIEW_THRESHOLD
from schemas import AuditEntry, ShiftBriefing

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
    assert "2" in sb.summary  # the narrative mentions the counts


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


def test_low_confidence_dismiss_needs_review():
    # an uncertain dismiss below the auto-clear bar reaches a human even if the verifier agrees
    assert auto_clear_policy("dismiss", 0.70, "agreed", threshold=0.85) == "needsReview"


def test_confidence_exactly_at_threshold_is_inclusive():
    # the bar is >= : a dismiss landing exactly on the threshold still clears
    assert auto_clear_policy("dismiss", 0.85, "agreed", threshold=0.85) == "autoCleared"
