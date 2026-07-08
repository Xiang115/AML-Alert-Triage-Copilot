"""Slice A learning-loop tests for cross-customer suppression memory."""

from __future__ import annotations

import importlib

import pytest

import store
from agents.triage import NO_MATCH_CODE


@pytest.fixture
def memory_store():
    """Point the global store at an isolated in-memory SQLite db for one test."""
    saved = (store._engine, store._seed, store._alert_seed)
    store._seed = []
    store._alert_seed = []
    store.init("sqlite://")
    store.reset()
    yield
    store._engine, store._seed, store._alert_seed = saved


def _memory_module():
    return importlib.import_module("agents.memory")


def _txn(
    txn_id: str,
    *,
    counterparty_name: str | None = None,
    counterparty_account: str | None = None,
    amount: float = 1000.0,
    direction: str = "outbound",
    balance: float = 5000.0,
    flags: list[str] | None = None,
) -> dict:
    return {
        "transactionId": txn_id,
        "counterpartyName": counterparty_name,
        "counterpartyAccount": counterparty_account,
        "amount": amount,
        "direction": direction,
        "currency": "MYR",
        "runningBalance": balance,
        "flags": flags or [],
    }


def _alert(
    *transactions: dict,
    alert_id: str = "ALERT-001",
    code: str = "FI-01",
    cited_ids: list[str] | None = None,
) -> dict:
    return {
        "alertId": alert_id,
        "transactions": list(transactions),
        "triage": {
            "matchedTypology": {"code": code},
            "citedTransactionIds": cited_ids or [],
        },
    }


def _ledger(*balances: float) -> list[dict]:
    """Transactions carrying just the fields the envelope gate reads (runningBalance drives sweep)."""
    return [{"amount": 1000.0, "direction": "outbound", "currency": "MYR", "runningBalance": b,
             "flags": [], "counterpartyAccount": "CP1"} for b in balances]


def test_envelope_benign_consistent_true_when_the_balance_never_drains():
    # No pass-through tell -> a matched suppression may auto-clear (ADR-0021 gate 2).
    assert _memory_module().envelope_benign_consistent(_ledger(11000, 8000, 6000)) is True


def test_envelope_benign_consistent_false_on_the_drain_to_zero_pass_through_tell():
    # Swept to ~0 (low <= 5% of peak) -> laundering-shaped -> auto-clear denied, routes to a human.
    assert _memory_module().envelope_benign_consistent(_ledger(10200, 5000, 200)) is False


def test_envelope_benign_consistent_denies_an_empty_ledger():
    # Not verifiable -> conservative deny.
    assert _memory_module().envelope_benign_consistent([]) is False


def test_signature_is_the_behavioral_envelope_of_a_matched_alert():
    # Fork B (ADR-0021): the signature is the STRUCTURAL behavioral envelope the leakage frontier is
    # measured over (agents.envelope) — typology + amount band + flow shape + ledger tells — NOT
    # counterparty identity (which recurs on ~0% of held-out SAML-D, so it could never auto-clear).
    alert = _alert(
        _txn("T-1", counterparty_account="acme-123", amount=1000.0, direction="inbound", balance=6000.0),
        _txn("T-2", counterparty_account="acme-123", amount=900.0, direction="outbound", balance=5100.0),
    )

    sig = _memory_module().signature(alert)

    assert sig is not None
    assert sig.startswith("typ=FI-01|")
    for feature in ("amt=", "dir=", "drain=", "conc=", "xb=", "cash=", "ntxn=2"):
        assert feature in sig
    # counterparty identity is deliberately NOT part of the key
    assert "acme-123" not in sig


def test_signature_returns_none_when_no_typology_matched():
    alert = _alert(
        _txn("T-1", counterparty_name="Acme Payroll"),
        code=NO_MATCH_CODE,
    )

    assert _memory_module().signature(alert) is None


def test_signature_returns_none_on_an_empty_ledger():
    # No transactions -> the structural envelope is not computable -> no signature (conservative).
    assert _memory_module().signature(_alert()) is None


def test_signature_is_shared_by_two_customers_with_the_same_structural_pattern():
    # The whole point of the behavioral envelope: different counterparties, same structural pattern ->
    # SAME signature, so one customer's clearance can surface another's look-alike.
    a = _alert(
        _txn("T-1", counterparty_account="acme-123", amount=1000.0, direction="inbound", balance=6000.0),
        _txn("T-2", counterparty_account="acme-123", amount=900.0, direction="outbound", balance=5100.0),
        alert_id="CUST-A",
    )
    b = _alert(
        _txn("T-1", counterparty_account="totally-different-999", amount=1000.0, direction="inbound", balance=6000.0),
        _txn("T-2", counterparty_account="totally-different-999", amount=900.0, direction="outbound", balance=5100.0),
        alert_id="CUST-B",
    )

    assert _memory_module().signature(a) == _memory_module().signature(b)


def test_dominant_counterparty_prefers_the_account_over_name_spelling():
    # The counterparty is no longer the signature key, but it still feeds Network Revocation, so its
    # extraction (account preferred, cited-first, normalized) stays covered.
    alert = _alert(
        _txn("T-1", counterparty_name="Acme Holdings", counterparty_account=" ACME-123 "),
        _txn("T-2", counterparty_name="Acme Payroll", counterparty_account="acme-123"),
        _txn("T-3", counterparty_name="Acme Payroll", counterparty_account=None),
    )

    assert _memory_module()._dominant_counterparty(alert) == "acme-123"


def test_dominant_counterparty_prefers_cited_transactions_over_a_noisier_population():
    alert = _alert(
        _txn("T-1", counterparty_account="noise-1"),
        _txn("T-2", counterparty_account="noise-1"),
        _txn("T-3", counterparty_account="noise-1"),
        _txn("T-4", counterparty_account="focus-42"),
        cited_ids=["T-4"],
    )

    assert _memory_module()._dominant_counterparty(alert) == "focus-42"


def test_suppress_returns_none_when_the_store_has_no_learned_match(memory_store):
    alert = _alert(
        _txn("T-1", counterparty_account="acme-123"),
        _txn("T-2", counterparty_account="acme-123"),
    )

    assert _memory_module().suppress(alert) is None


def test_revoked_by_network_flags_a_real_consolidation_hub():
    # ADR-0021 Network Revocation: an IBM AMLworld consolidation hub (real assembled structure) is
    # flagged; an ordinary counterparty is not. Case-insensitive.
    from agents.network_revocation import revoked_by_network

    hit = revoked_by_network("81A4AFE20")  # hub of IBM-MULE-01 (FI-01)
    assert hit is not None and hit["networkId"] == "IBM-MULE-01"
    assert revoked_by_network("81a4afe20")["networkId"] == "IBM-MULE-01"  # normalized
    assert revoked_by_network("acme-123") is None
    assert revoked_by_network(None) is None


def test_suppress_revokes_when_the_counterparty_is_a_consolidation_hub(memory_store):
    # The memory would clear this behavioral envelope (a pattern was learned) — but the Mule Network
    # walk flags the counterparty as a consolidation hub, so the suppression is REVOKED, not cleared.
    alert = _alert(
        _txn("T-1", counterparty_account="81A4AFE20"),
        _txn("T-2", counterparty_account="81A4AFE20"),
    )
    signature = _memory_module().signature(alert)
    assert signature is not None and signature.startswith("typ=FI-01|")
    store.record_clearance(
        signature=signature, typology="FI-01", source_decision_id="SD-00099",
        source_alert_id="SD-00099", cleared_at="2026-07-02T09:14:00+08:00",
    )

    out = _memory_module().suppress(alert)

    assert out is not None
    assert out["status"] == "revoked"  # not "suppressed" -> routing never auto-clears it
    assert out["revokedNetworkId"] == "IBM-MULE-01"
    assert "consolidation hub" in out["rationale"]


def test_suppress_returns_a_suppression_that_cites_the_source_decision(memory_store):
    alert = _alert(
        _txn("T-1", counterparty_account="acme-123"),
        _txn("T-2", counterparty_account="acme-123"),
    )
    signature = _memory_module().signature(alert)
    assert signature is not None and signature.startswith("typ=FI-01|")

    store.record_clearance(
        signature=signature,
        typology="FI-01",
        source_decision_id="SD-00021",
        source_alert_id="SD-00021",
        cleared_at="2026-07-02T09:14:00+08:00",
    )

    out = _memory_module().suppress(alert)

    assert out is not None
    assert out["status"] == "suppressed"
    assert out["matchedPatternId"] == signature
    assert out["sourceDecisionId"] == "SD-00021"
    assert out["signature"] == signature
    assert out["clearedCount"] == 1
