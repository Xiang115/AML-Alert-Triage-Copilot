"""Evidence rendering tests — the prompt text every triage call reasons over.

These guard the on-screen `runningBalance` mule tell (CLAUDE.md): a bug here
silently degrades every LLM prompt and no other test would catch it.
"""

from agents.evidence import render_alert_evidence, render_features_evidence
from schemas import AlertInput


def _alert(transactions):
    return AlertInput.model_validate(
        {
            "alertId": "DQ-X",
            "status": "pending",
            "createdAt": "2026-06-15T08:00:00",
            "riskScore": 80,
            "trigger": "rapid in-out movement",
            "account": {
                "accountId": "AC-X",
                "holderName": "Test Holder",
                "accountType": "personal",
                "openedAt": "2025-01-01T00:00:00",
            },
            "transactionIds": [t["transactionId"] for t in transactions],
            "transactions": transactions,
        }
    )


def _txn(tid, amount, direction, running_balance, ts):
    return {
        "transactionId": tid,
        "timestamp": ts,
        "amount": amount,
        "currency": "MYR",
        "direction": direction,
        "counterpartyName": "Acme Ltd",
        "channel": "transfer",
        "runningBalance": running_balance,
        "flags": [],
    }


def test_alert_evidence_shows_running_balance_draining_in_order():
    alert = _alert(
        [
            _txn("TX-1", 50000.0, "inbound", 50100.0, "2026-06-14T09:00:00"),
            _txn("TX-2", 49800.0, "outbound", 300.0, "2026-06-14T11:00:00"),
        ]
    )
    out = render_alert_evidence(alert)

    # The mule tell: runningBalance column present, draining 50100 -> 300, in order.
    assert "runningBalance" in out
    assert "50100.0" in out and "300.0" in out
    assert out.index("TX-1") < out.index("TX-2")
    assert out.index("50100.0") < out.index("300.0")
    # Each transaction renders one line carrying id, direction, and balance.
    tx2_line = next(line for line in out.splitlines() if "TX-2" in line)
    assert "outbound" in tx2_line and "300.0" in tx2_line


def test_alert_evidence_includes_account_and_trigger_header():
    out = render_alert_evidence(_alert([]))
    assert "Test Holder" in out
    assert "personal" in out
    assert "rapid in-out movement" in out


def test_alert_evidence_handles_no_transactions():
    # None and [] must both render the header block without raising.
    alert = _alert([])
    alert.transactions = None
    out = render_alert_evidence(alert)
    assert "Transactions" in out
    assert out.strip().endswith("runningBalance):")  # header present, no rows


def test_features_evidence_renders_every_feature():
    features = {"txnCount": 829, "creditCount": 400, "netFlow": -1200.5}
    out = render_features_evidence(features)
    assert out.startswith("Aggregated alert features:")
    for key, value in features.items():
        assert key in out
        assert str(value) in out
