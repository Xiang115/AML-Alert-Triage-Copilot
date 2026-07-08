"""Slice B — deterministic sanctions/PEP screening.

Two kinds of test:
  * logic tests inject a small FIXED list (monkeypatching `_load_list`) so the
    exact/alias/fuzzy/clear behaviour is deterministic and independent of whatever
    real data is bundled;
  * real-list tests load the actual OFAC SDN file (ingested by ingest_ofac.py) to
    prove the bundled list genuinely screens — a real designation blocks, and a
    benign counterparty is the honest "screened N, no matches" result.
"""

from __future__ import annotations

from datetime import datetime

import pytest

import agents.screening as screening_mod
from agents.screening import screen
from schemas import AlertInput, Screening, Transaction

# A controlled list the logic tests match against — NOT the real bundled data.
_FIXED_LIST = (
    {"name": "GLOBAL HORIZON TRADING LLC", "list": "OFAC SDN", "program": "SDGT",
     "aliases": ["GLOBAL HORIZON TRADING", "GLOBAL HORIZON TRADING CO"]},
    {"name": "IVANOV DMITRY", "list": "OFAC SDN", "program": "RUSSIA-EO14024",
     "aliases": ["DMITRY IVANOV", "D. IVANOV"]},
)


@pytest.fixture
def fixed_list(monkeypatch):
    """Screen against `_FIXED_LIST` regardless of the bundled file. Clears the index cache so
    it rebuilds over the fixed list (and again after, so real-list tests see the real list)."""
    monkeypatch.setattr(screening_mod, "_load_list", lambda: _FIXED_LIST)
    screening_mod._index.cache_clear()
    yield
    screening_mod._index.cache_clear()


def _txn(counterparty_name: str, account: str | None = "CP-1") -> Transaction:
    return Transaction(
        transaction_id="T1", timestamp=datetime(2026, 6, 1, 9, 0), amount=1000.0,
        currency="MYR", direction="inbound", counterparty_name=counterparty_name,
        counterparty_account=account, channel="transfer", running_balance=1000.0,
    )


def _alert(*txns: Transaction) -> AlertInput:
    return AlertInput(
        alert_id="A1", status="pending", created_at=datetime(2026, 6, 1, 8, 0),
        risk_score=50, trigger="test", transaction_ids=[t.transaction_id for t in txns],
        account={"accountId": "ACC-1", "holderName": "Test", "accountType": "personal",
                 "openedAt": datetime(2020, 1, 1)},
        transactions=list(txns),
    )


# --- matching logic (against the injected fixed list) ------------------------

def test_exact_match_is_a_blocked_hit(fixed_list):
    result = screen(_alert(_txn("GLOBAL HORIZON TRADING LLC")))
    assert result.status == "hit"
    assert result.blocked is True
    assert len(result.matches) == 1
    m = result.matches[0]
    assert m.match_type == "exact"
    assert m.score == 1.0
    assert m.list_name == "OFAC SDN"
    assert m.program == "SDGT"


def test_alias_match_counts_as_exact(fixed_list):
    result = screen(_alert(_txn("DMITRY IVANOV")))  # alias of IVANOV DMITRY
    assert result.status == "hit"
    assert result.blocked is True
    assert result.matches[0].match_type == "exact"
    assert result.matches[0].matched_name == "IVANOV DMITRY"


def test_case_and_whitespace_insensitive(fixed_list):
    result = screen(_alert(_txn("  global   horizon  trading llc ")))
    assert result.status == "hit"
    assert result.matches[0].match_type == "exact"


def test_fuzzy_above_threshold_is_potential_not_hit(fixed_list):
    # shares "global horizon trading" (3 of 5 union tokens = 0.6) but is not exact
    result = screen(_alert(_txn("GLOBAL HORIZON TRADING GROUP")))
    assert result.status == "potential"
    assert result.blocked is True  # any match blocks
    assert result.matches[0].match_type == "fuzzy"
    assert 0.6 <= result.matches[0].score < 1.0


def test_below_threshold_does_not_match(fixed_list):
    result = screen(_alert(_txn("ACME PAYROLL SERVICES BERHAD")))
    assert result.status == "clear"
    assert result.blocked is False
    assert result.matches == []
    assert result.screened_counterparties == 1


def test_unique_counterparties_deduped_by_account(fixed_list):
    a = _alert(_txn("GLOBAL HORIZON TRADING LLC", "CP-X"),
               _txn("GLOBAL HORIZON TRADING LLC", "CP-X"))
    result = screen(a)
    assert result.screened_counterparties == 1
    assert len(result.matches) == 1


def test_no_transactions_is_clear_zero(fixed_list):
    result = screen(_alert())
    assert result.status == "clear"
    assert result.blocked is False
    assert result.screened_counterparties == 0


def test_screen_is_pure_and_deterministic(fixed_list):
    alert = _alert(_txn("GLOBAL HORIZON TRADING LLC"))
    assert screen(alert) == screen(alert)


def test_returns_a_valid_screening_model(fixed_list):
    result = screen(_alert(_txn("GLOBAL HORIZON TRADING LLC")))
    assert isinstance(result, Screening)
    dumped = result.model_dump(by_alias=True)  # camelCase wire round-trip
    assert dumped["blocked"] is True
    assert dumped["screenedCounterparties"] == 1
    assert dumped["matches"][0]["matchType"] == "exact"


def test_missing_list_file_degrades_to_clear(monkeypatch, tmp_path):
    # nonexistent path + cleared caches => clear result, never raises
    screening_mod._load_list.cache_clear()
    screening_mod._index.cache_clear()
    monkeypatch.setattr(screening_mod, "_LIST_FILE", tmp_path / "nope.json")
    try:
        result = screen(_alert(_txn("GLOBAL HORIZON TRADING LLC")))
        assert result.status == "clear"
        assert result.blocked is False
        assert result.matches == []
        assert result.citation is None
    finally:
        screening_mod._load_list.cache_clear()
        screening_mod._index.cache_clear()


# --- against the REAL bundled OFAC SDN list (ingest_ofac.py) ------------------

def test_real_ofac_list_is_bundled_and_substantial():
    entries = screening_mod._load_list()
    assert len(entries) > 5000  # the real SDN list, not a hand-written sample
    first = entries[0]
    assert set(first) >= {"name", "list", "aliases"}
    assert first["list"] == "OFAC SDN"


def test_a_real_sdn_name_blocks():
    # a genuine OFAC designation, taken from the bundled list itself, must block
    entries = screening_mod._load_list()
    real_name = entries[0]["name"]
    result = screen(_alert(_txn(real_name)))
    assert result.status == "hit"
    assert result.blocked is True
    assert result.matches[0].match_type == "exact"


def test_benign_counterparty_against_real_list_is_no_match():
    # the honest "screened N, no matches" path against the REAL 17k-entry list:
    # a numeric SAML-D-style id and an ordinary local business name, neither designated
    result = screen(_alert(_txn("1002938475", "CP-num"),
                           _txn("KEDAI RUNCIT AMAN ENTERPRISE", "CP-biz")))
    assert result.status == "clear"
    assert result.blocked is False
    assert result.screened_counterparties == 2
    assert result.citation is not None  # the real list was loaded
