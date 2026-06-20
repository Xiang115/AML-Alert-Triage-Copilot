"""goAML STR export serializer (docs/plan-goaml-integration.md).

The serializer validates against the XSD internally, so a successful call already
proves conformance; these tests pin the from/to-by-direction mapping, the typology
indicator, and that a malformed draft is rejected rather than emitted."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest
from lxml import etree

from goaml import GoamlConfig, submission_reference, to_goaml_str_xml
from schemas import (
    Account,
    CitedTransaction,
    MatchedTypology,
    Period,
    STRDraft,
    Transaction,
)

_CONFIG = GoamlConfig.model_validate(
    json.loads((Path(__file__).resolve().parents[1] / "data" / "goaml_config.json").read_text())
)


def _txn(tid: str, direction: str, amount: float, cp: str) -> Transaction:
    return Transaction(
        transaction_id=tid,
        timestamp=datetime(2026, 6, 14, 9, 40),
        amount=amount,
        currency="MYR",
        direction=direction,
        counterparty_name=cp,
        counterparty_account="CP-1",
        counterparty_bank="Other Bank",
        channel="transfer",
        running_balance=amount,
    )


def _cited(tid: str, amount: float, cp: str) -> CitedTransaction:
    return CitedTransaction(
        transaction_id=tid,
        timestamp=datetime(2026, 6, 14, 9, 40),
        amount=amount,
        currency="MYR",
        counterparty_name=cp,
        running_balance=amount,
    )


def _draft(cited: list[CitedTransaction]) -> STRDraft:
    return STRDraft(
        report_date=datetime(2026, 6, 20, 12, 0),
        reporting_institution="Demo Bank Berhad",
        subject=Account(
            account_id="AC-4101",
            holder_name="Tan Wei Ming",
            account_type="personal",
            opened_at=datetime(2026, 4, 20),
        ),
        typology=MatchedTypology(code="PT-01", name="Pass-through / Rapid Movement", source="FATF R.10"),
        period=Period(**{"from": datetime(2026, 6, 14, 9, 40), "to": datetime(2026, 6, 14, 11, 55)}),
        activity_summary="Rapid in-and-out movement through a personal account.",
        cited_transactions=cited,
        grounds_for_suspicion=["Inbound 52k then outbound 51.5k within 2 hours."],
        recommended_action="Escalate to FIED.",
    )


def _serialize(draft: STRDraft, txns: list[Transaction]) -> etree._Element:
    xml = to_goaml_str_xml(draft, txns, _CONFIG, submission_date=datetime(2026, 6, 20, 12, 0))
    return etree.fromstring(xml)


def test_emits_schema_valid_report_with_header_from_config():
    cited = [_cited("DT-1001", 52000.0, "Evergreen Logistics Ltd")]
    root = _serialize(_draft(cited), [_txn("DT-1001", "inbound", 52000.0, "Evergreen Logistics Ltd")])

    assert root.tag == "report"
    assert root.findtext("report_code") == "STR"
    assert root.findtext("rentity_id") == str(_CONFIG.rentity_id)
    assert root.findtext("reporting_person/first_name") == _CONFIG.reporting_person.first_name


def test_inbound_puts_subject_on_the_to_my_client_side():
    cited = [_cited("DT-1001", 52000.0, "Evergreen Logistics Ltd")]
    root = _serialize(_draft(cited), [_txn("DT-1001", "inbound", 52000.0, "Evergreen Logistics Ltd")])

    txn = root.find("transaction")
    # Counterparty originates; our customer (subject) receives.
    assert txn.find("t_from") is not None and txn.find("t_from_my_client") is None
    assert txn.find("t_to_my_client") is not None and txn.find("t_to") is None
    assert txn.findtext("t_to_my_client/to_account/account") == "AC-4101"
    assert txn.findtext("t_from/from_account/account_name") == "Evergreen Logistics Ltd"


def test_outbound_puts_subject_on_the_from_my_client_side():
    cited = [_cited("DT-1002", 51500.0, "MaxCash Money Changer")]
    root = _serialize(_draft(cited), [_txn("DT-1002", "outbound", 51500.0, "MaxCash Money Changer")])

    txn = root.find("transaction")
    assert txn.find("t_from_my_client") is not None and txn.find("t_from") is None
    assert txn.find("t_to") is not None and txn.find("t_to_my_client") is None
    assert txn.findtext("t_from_my_client/from_account/account") == "AC-4101"
    assert txn.findtext("t_to/to_account/account_name") == "MaxCash Money Changer"


def test_typology_code_becomes_an_indicator():
    cited = [_cited("DT-1001", 52000.0, "Evergreen Logistics Ltd")]
    root = _serialize(_draft(cited), [_txn("DT-1001", "inbound", 52000.0, "Evergreen Logistics Ltd")])
    assert root.findtext("report_indicators/indicator") == "PT-01"


def test_grounds_fold_into_the_reason_narrative():
    cited = [_cited("DT-1001", 52000.0, "Evergreen Logistics Ltd")]
    root = _serialize(_draft(cited), [_txn("DT-1001", "inbound", 52000.0, "Evergreen Logistics Ltd")])
    reason = root.findtext("reason")
    assert "Rapid in-and-out" in reason
    assert "Grounds for suspicion" in reason


def test_missing_full_transaction_defaults_to_inbound_without_crashing():
    # A cited id with no matching full transaction still produces a valid report.
    cited = [_cited("DT-9999", 100.0, "Unknown Co")]
    root = _serialize(_draft(cited), [])
    txn = root.find("transaction")
    assert txn.find("t_from") is not None  # inbound default
    assert txn.findtext("t_from/from_account/account") == "UNKNOWN"


def test_rejects_a_draft_with_no_cited_transactions():
    # The XSD requires >= 1 <transaction>; an empty draft must raise, not emit.
    with pytest.raises(ValueError, match="XSD validation"):
        to_goaml_str_xml(_draft([]), [], _CONFIG, submission_date=datetime(2026, 6, 20, 12, 0))


def test_submission_reference_is_deterministic_and_fiu_formatted():
    # Demo-stable (ADR-0003): the same alert always files under the same FIU ref.
    ref = submission_reference("DQ-001")
    assert ref == submission_reference("DQ-001")
    assert ref != submission_reference("DQ-002")
    assert ref.startswith("MYFIU-2026-")
