"""Pure SAML-D loader helpers — no CSV, no LLM (no tokens). Covers the typology mapping,
the scoring label, account-centric assembly, the synthesised running balance, and the
critical no-label-leakage guarantee (ADR-0012)."""

from __future__ import annotations

import json
from datetime import datetime

from data.saml_d_loader import (
    TYPOLOGY_MAP,
    alert_label,
    build_alert,
    direction_for,
    map_typology,
    rule_flags,
    synth_running_balance,
)
from schemas import AlertInput


def test_typology_map_clear_matches():
    assert map_typology("Fan_In") == "FI-01"
    assert map_typology("Layered_Fan_Out") == "FI-01"
    assert map_typology("Structuring") == "ST-01"
    assert map_typology("Smurfing") == "ST-01"
    assert map_typology("Deposit-Send") == "PT-01"


def test_typology_map_coverage_gap_and_normal_are_none():
    # Real laundering our 5-card KB does not cover -> None (counted as coverage gap).
    assert map_typology("Over-Invoicing") is None
    assert map_typology("Cash_Withdrawal") is None
    assert map_typology("Behavioural_Change_1") is None
    # A benign 'Normal_*' label is not a laundering type -> None.
    assert map_typology("Normal_Fan_In") is None


def test_alert_label_dismiss_when_all_normal():
    outcome, code, gap = alert_label(["Normal_Fan_In", "Normal_Cash_Deposits"])
    assert outcome == "dismiss"
    assert code is None and gap is False


def test_alert_label_escalate_with_dominant_card():
    outcome, code, gap = alert_label(["Normal_Fan_In", "Fan_In", "Fan_In", "Structuring"])
    assert outcome == "escalate"
    assert code == "FI-01"  # dominant mapped card
    assert gap is False


def test_alert_label_coverage_gap_report():
    # Real laundering that maps to no card is still a Report, flagged as a coverage gap.
    outcome, code, gap = alert_label(["Over-Invoicing", "Over-Invoicing"])
    assert outcome == "escalate"
    assert code is None
    assert gap is True


def test_direction_inbound_when_account_is_receiver():
    assert direction_for(100, sender=200, receiver=100) == "inbound"
    assert direction_for(100, sender=100, receiver=200) == "outbound"


def test_rule_flags_are_label_free():
    # cross-border + cash derivable without the label; never a 'laundering' flag.
    assert rule_flags("Cash Deposit", "UK", "UAE") == ["cross-border", "cash"]
    assert rule_flags("ACH", "UK", "UK") == []


def test_synth_running_balance_stays_nonnegative_and_tracks_flow():
    # +1000 in, -900 out -> rises then drains toward the floor (pass-through tell).
    bals = synth_running_balance([1000.0, -900.0], base=500.0)
    assert all(b >= 0 for b in bals)
    assert bals[0] > bals[1]  # drained after the outbound


def _legs():
    return [
        {"txn_id": "SDT-1", "timestamp": datetime(2022, 10, 7, 10, 0), "amount": 5000.0,
         "currency": "UK pounds", "sender": 200, "receiver": 100, "payment_type": "ACH",
         "sender_loc": "UK", "receiver_loc": "UK"},
        {"txn_id": "SDT-2", "timestamp": datetime(2022, 10, 7, 12, 0), "amount": 4800.0,
         "currency": "UK pounds", "sender": 100, "receiver": 300, "payment_type": "Cross-border",
         "sender_loc": "UK", "receiver_loc": "UAE"},
    ]


def test_build_alert_is_valid_alertinput_and_account_centric():
    alert = build_alert("SD-0001", 100, _legs(), opened_at=datetime(2021, 1, 1))
    AlertInput.model_validate(alert)  # conforms to the wire contract
    dirs = [t["direction"] for t in alert["transactions"]]
    assert dirs == ["inbound", "outbound"]  # account 100 receives then sends
    assert alert["transactions"][0]["counterpartyAccount"] == "200"
    assert alert["transactions"][1]["counterpartyAccount"] == "300"


def test_build_alert_does_not_leak_the_label():
    # The evidence the model will see must contain no laundering label anywhere.
    blob = json.dumps(build_alert("SD-0001", 100, _legs(), opened_at=datetime(2021, 1, 1))).lower()
    assert "laundering" not in blob
    assert "is_laundering" not in blob
    for lt in TYPOLOGY_MAP:  # no raw SAML-D typology string leaks in
        assert lt.lower() not in blob
