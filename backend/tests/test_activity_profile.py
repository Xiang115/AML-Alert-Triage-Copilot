"""Account Activity Profile tests — a ledger-derived summary of one account's window.

Every field is computed from transactions already in the payload (no fabricated KYC):
turnover per currency, the reconstructed balance sweep, cross-border and cash exposure,
and counterparty concentration. Pure function; serve-time in main.py.
"""

from __future__ import annotations

from activity_profile import compute_activity_profile


def _txn(
    *,
    amount: float,
    direction: str,
    currency: str = "USD",
    running_balance: float = 0.0,
    counterparty_account: str = "acct-x",
    counterparty_name: str = "Acct x",
    counterparty_bank: str = "USA",
    flags: list[str] | None = None,
) -> dict:
    return {
        "amount": amount,
        "direction": direction,
        "currency": currency,
        "runningBalance": running_balance,
        "counterpartyAccount": counterparty_account,
        "counterpartyName": counterparty_name,
        "counterpartyBank": counterparty_bank,
        "flags": flags or [],
    }


def test_turnover_is_grouped_by_currency_with_net_and_sorted_by_volume():
    profile = compute_activity_profile([
        _txn(amount=1000, direction="inbound", currency="USD"),
        _txn(amount=400, direction="outbound", currency="USD"),
        _txn(amount=500, direction="inbound", currency="EUR"),
    ])
    assert profile["turnover"] == [
        {"currency": "USD", "inbound": 1000.0, "outbound": 400.0, "net": 600.0},
        {"currency": "EUR", "inbound": 500.0, "outbound": 0.0, "net": 500.0},
    ]


def test_balance_sweep_flags_a_drain_to_near_zero():
    profile = compute_activity_profile([
        _txn(amount=5000, direction="inbound", running_balance=5000),
        _txn(amount=4000, direction="inbound", running_balance=9000),
        _txn(amount=8900, direction="outbound", running_balance=100),
    ])
    swept = profile["balanceSwept"]
    assert swept["opening"] == 0.0      # 5000 - 5000 (reconstructed pre-window balance)
    assert swept["peak"] == 9000.0
    assert swept["low"] == 100.0
    assert swept["closing"] == 100.0
    assert swept["sweptToNearZero"] is True


def test_balance_sweep_not_flagged_when_balance_stays_high():
    profile = compute_activity_profile([
        _txn(amount=5000, direction="inbound", running_balance=5000),
        _txn(amount=1000, direction="inbound", running_balance=6000),
        _txn(amount=500, direction="outbound", running_balance=5500),
    ])
    assert profile["balanceSwept"]["sweptToNearZero"] is False


def test_cross_border_exposure_counts_flagged_legs_and_distinct_jurisdictions():
    profile = compute_activity_profile([
        _txn(amount=100, direction="inbound", counterparty_bank="UK", flags=["cross-border"]),
        _txn(amount=100, direction="outbound", counterparty_bank="USA", flags=["cross-border"]),
        _txn(amount=100, direction="inbound", counterparty_bank="UK"),
    ])
    cb = profile["crossBorder"]
    assert cb["legs"] == 2
    assert cb["total"] == 3
    assert cb["share"] == 0.6667
    assert cb["jurisdictions"] == 2


def test_cash_intensity_share():
    profile = compute_activity_profile([
        _txn(amount=100, direction="inbound", flags=["cash"]),
        _txn(amount=100, direction="inbound"),
        _txn(amount=100, direction="outbound"),
    ])
    assert profile["cash"] == {"legs": 1, "total": 3, "share": 0.3333}


def test_counterparty_concentration_by_leg_share():
    profile = compute_activity_profile([
        _txn(amount=100, direction="inbound", counterparty_account="a", counterparty_name="Alice"),
        _txn(amount=100, direction="outbound", counterparty_account="a", counterparty_name="Alice"),
        _txn(amount=100, direction="inbound", counterparty_account="b", counterparty_name="Bob"),
    ])
    conc = profile["concentration"]
    assert conc["distinctCounterparties"] == 2
    assert conc["topCounterparty"] == "Alice"
    assert conc["topShare"] == 0.6667


def test_empty_ledger_yields_zeroed_profile():
    profile = compute_activity_profile([])
    assert profile["turnover"] == []
    assert profile["balanceSwept"] == {
        "opening": 0.0, "peak": 0.0, "low": 0.0, "closing": 0.0, "sweptToNearZero": False,
    }
    assert profile["crossBorder"] == {"legs": 0, "total": 0, "share": 0.0, "jurisdictions": 0}
    assert profile["cash"] == {"legs": 0, "total": 0, "share": 0.0}
    assert profile["concentration"] == {
        "distinctCounterparties": 0, "topCounterparty": None, "topShare": 0.0,
    }
