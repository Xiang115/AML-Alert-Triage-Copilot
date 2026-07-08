from config import AUTO_CLEAR_THRESHOLD, BORDERLINE_MARGIN, QA_SAMPLE_RATE, REVIEW_THRESHOLD
from decision_control import DecisionControlPlane


_BORDERLINE = REVIEW_THRESHOLD + (BORDERLINE_MARGIN / 2)
_SUPPRESSED = {"status": "suppressed", "matchedPatternId": "sig:x"}
_BENIGN_TXNS = [
    {
        "amount": 8000,
        "direction": "inbound",
        "currency": "MYR",
        "runningBalance": 11000,
        "flags": [],
        "counterpartyAccount": "CP1",
    },
    {
        "amount": 3000,
        "direction": "outbound",
        "currency": "MYR",
        "runningBalance": 8000,
        "flags": [],
        "counterpartyAccount": "CP1",
    },
]
_DRAIN_TXNS = [
    {
        "amount": 10000,
        "direction": "inbound",
        "currency": "MYR",
        "runningBalance": 10200,
        "flags": [],
        "counterpartyAccount": "CP1",
    },
    {
        "amount": 10000,
        "direction": "outbound",
        "currency": "MYR",
        "runningBalance": 200,
        "flags": [],
        "counterpartyAccount": "CP1",
    },
]


def _plane() -> DecisionControlPlane:
    return DecisionControlPlane(
        auto_clear_threshold=AUTO_CLEAR_THRESHOLD,
        review_threshold=REVIEW_THRESHOLD,
        qa_sample_rate=QA_SAMPLE_RATE,
        borderline_margin=BORDERLINE_MARGIN,
    )


def _alert(*, confidence=_BORDERLINE, txns=None, suppression=_SUPPRESSED) -> dict:
    return {
        "alertId": "X",
        "transactions": _BENIGN_TXNS if txns is None else txns,
        "triage": {
            "recommendation": "dismiss",
            "confidence": confidence,
            "verifier": {"status": "agreed"},
            "suppression": suppression,
            "debate": None,
            "screening": None,
        },
    }


def test_control_plane_returns_full_decision_for_suppressed_borderline_clear():
    decision = _plane().evaluate_alert(_alert(), qa_sample_ids={"X"})

    assert decision.routing == "autoCleared"
    assert decision.eligible is True
    assert decision.qa_sampled is True
    assert decision.borderline_dismiss is True
    assert decision.blocked_reason is None
    assert decision.suppression_applied is True
    assert decision.suppression_envelope_consistent is True
    assert "Final control-plane routing is autoCleared." in decision.reasons


def test_control_plane_blocks_suppression_when_ledger_envelope_changes():
    decision = _plane().evaluate_alert(_alert(txns=_DRAIN_TXNS), qa_sample_ids={"X"})

    assert decision.routing == "needsReview"
    assert decision.eligible is False
    assert decision.blocked_reason == "lowConfidenceDismiss"
    assert decision.suppression_applied is False
    assert decision.suppression_envelope_consistent is False
    assert "Blocked: learned suppression matched, but the ledger envelope changed or is unavailable." in decision.reasons


def test_queue_item_uses_hydrated_alert_only_when_suppression_needs_ledger():
    full_alert = _alert()
    queue_item = {k: v for k, v in full_alert.items() if k != "transactions"}
    queue_item["routing"] = "needsReview"

    without_ledger = _plane().evaluate_queue_item(queue_item, qa_sample_ids={"X"})
    with_ledger = _plane().evaluate_queue_item(queue_item, full_alert=full_alert, qa_sample_ids={"X"})

    assert without_ledger.routing == "needsReview"
    assert without_ledger.suppression_applied is False
    assert with_ledger.routing == "autoCleared"
    assert with_ledger.suppression_applied is True
