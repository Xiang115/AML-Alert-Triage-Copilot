"""goAML STR export serializer (docs/plan-goaml-integration.md).

The serializer validates against the XSD internally, so a successful call already
proves conformance; these tests pin the from/to-by-direction mapping, the typology
indicator, and that a malformed draft is rejected rather than emitted."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from lxml import etree

from goaml import GoamlConfig, _schema, submission_reference, to_goaml_str_xml
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
_TYPOLOGY_CARDS = json.loads(
    (Path(__file__).resolve().parents[1] / "data" / "typologies" / "typologies.json").read_text()
)["typologies"]


def _txn(
    tid: str,
    direction: str,
    amount: float,
    cp: str,
    *,
    cp_account: str | None = "CP-1",
    cp_bank: str | None = "Other Bank",
) -> Transaction:
    return Transaction(
        transaction_id=tid,
        timestamp=datetime(2026, 6, 14, 9, 40),
        amount=amount,
        currency="MYR",
        direction=direction,
        counterparty_name=cp,
        counterparty_account=cp_account,
        counterparty_bank=cp_bank,
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


def _serialize_bytes(draft: STRDraft, txns: list[Transaction]) -> bytes:
    return to_goaml_str_xml(draft, txns, _CONFIG, submission_date=datetime(2026, 6, 20, 12, 0))


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


def test_mixed_direction_citations_keep_each_transaction_side_correct():
    cited = [
        _cited("DT-1001", 52000.0, "Evergreen Logistics Ltd"),
        _cited("DT-1002", 51500.0, "MaxCash Money Changer"),
    ]
    root = _serialize(
        _draft(cited),
        [
            _txn("DT-1001", "inbound", 52000.0, "Evergreen Logistics Ltd"),
            _txn("DT-1002", "outbound", 51500.0, "MaxCash Money Changer"),
        ],
    )

    inbound, outbound = root.findall("transaction")
    assert inbound.find("t_from") is not None
    assert inbound.find("t_to_my_client") is not None
    assert outbound.find("t_from_my_client") is not None
    assert outbound.find("t_to") is not None


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


def test_empty_grounds_leave_reason_as_activity_summary_only():
    cited = [_cited("DT-1001", 52000.0, "Evergreen Logistics Ltd")]
    draft = _draft(cited).model_copy(update={"grounds_for_suspicion": []})
    root = _serialize(draft, [_txn("DT-1001", "inbound", 52000.0, "Evergreen Logistics Ltd")])

    reason = root.findtext("reason")
    assert reason == "Rapid in-and-out movement through a personal account."
    assert "Grounds for suspicion" not in reason


def test_goaml_xml_carries_the_reporting_period():
    # ADR-0017: the filed report also carries the activity window from the draft.
    cited = [_cited("DT-1001", 52000.0, "Evergreen Logistics Ltd")]
    draft = _draft(cited)
    root = _serialize(draft, [_txn("DT-1001", "inbound", 52000.0, "Evergreen Logistics Ltd")])

    period = root.find("reporting_period")
    assert period is not None
    assert period.findtext("from_date") == draft.period.from_.isoformat()
    assert period.findtext("to_date") == draft.period.to.isoformat()


def test_reporting_period_precedes_reporting_person_and_still_validates():
    # A return (no raised ValueError) means the report passed XSD validation with the new
    # element in place; assert its position in the ordered sequence too.
    cited = [_cited("DT-1001", 52000.0, "Evergreen Logistics Ltd")]
    root = _serialize(_draft(cited), [_txn("DT-1001", "inbound", 52000.0, "Evergreen Logistics Ltd")])
    tags = [el.tag for el in root]
    assert tags.index("reporting_period") < tags.index("reporting_person")


def test_missing_full_transaction_defaults_to_inbound_without_crashing():
    # A cited id with no matching full transaction still produces a valid report.
    cited = [_cited("DT-9999", 100.0, "Unknown Co")]
    root = _serialize(_draft(cited), [])
    txn = root.find("transaction")
    assert txn.find("t_from") is not None  # inbound default
    assert txn.findtext("t_from/from_account/account") == "UNKNOWN"


def test_missing_counterparty_account_and_bank_use_unknown_fallbacks():
    cited = [_cited("DT-1001", 52000.0, "Evergreen Logistics Ltd")]
    root = _serialize(
        _draft(cited),
        [_txn("DT-1001", "inbound", 52000.0, "Evergreen Logistics Ltd", cp_account=None, cp_bank=None)],
    )

    assert root.findtext("transaction/t_from/from_account/institution_name") == "UNKNOWN"
    assert root.findtext("transaction/t_from/from_account/account") == "UNKNOWN"
    assert root.findtext("transaction/t_from/from_account/account_name") == "Evergreen Logistics Ltd"


def test_xml_10_invalid_control_characters_are_stripped_from_text_and_report_stays_valid():
    cited = [_cited("DT-\x001001", 52000.0, "Ever\x07green Logistics Ltd")]
    draft = _draft(cited).model_copy(
        update={
            "reporting_institution": "Demo\x1f Bank Berhad",
            "subject": Account(
                account_id="AC-\x084101",
                holder_name="Tan\x0c Wei Ming",
                account_type="personal",
                opened_at=datetime(2026, 4, 20),
            ),
            "activity_summary": "Rapid\x00 in-and-out\x0b movement.",
            "grounds_for_suspicion": ["Inbound\x0e 52k then outbound\x1f 51.5k."],
        }
    )

    xml = _serialize_bytes(
        draft,
        [
            _txn(
                "DT-\x001001",
                "inbound",
                52000.0,
                "Ever\x07green Logistics Ltd",
                cp_account="CP-\x001",
                cp_bank="Other\x0e Bank",
            )
        ],
    )
    root = etree.fromstring(xml)

    assert _schema().validate(root)
    assert root.findtext("reason") == (
        "Rapid in-and-out movement.\n\nGrounds for suspicion:\n"
        "- Inbound 52k then outbound 51.5k."
    )
    assert root.findtext("transaction/transactionnumber") == "DT-1001"
    assert root.findtext("transaction/t_from/from_account/institution_name") == "Other Bank"
    assert root.findtext("transaction/t_from/from_account/account") == "CP-1"
    assert root.findtext("transaction/t_from/from_account/account_name") == "Evergreen Logistics Ltd"


def test_rejects_a_draft_with_no_cited_transactions():
    # The XSD requires >= 1 <transaction>; an empty draft must raise, not emit.
    with pytest.raises(ValueError, match="at least one cited transaction"):
        to_goaml_str_xml(_draft([]), [], _CONFIG, submission_date=datetime(2026, 6, 20, 12, 0))


def test_rejects_a_draft_with_unanchored_grounds():
    cited = [_cited("DT-1001", 52000.0, "Evergreen Logistics Ltd")]
    unanchored = "Customer is linked to unexplained offshore activity."
    draft = _draft(cited).model_copy(
        update={
            "grounds_for_suspicion": [unanchored],
            "unanchored_claims": [unanchored],
        }
    )

    with pytest.raises(ValueError, match="1 unanchored ground"):
        to_goaml_str_xml(
            draft,
            [_txn("DT-1001", "inbound", 52000.0, "Evergreen Logistics Ltd")],
            _CONFIG,
            submission_date=datetime(2026, 6, 20, 12, 0),
        )


def test_allows_pulled_unanchored_claims_that_are_no_longer_in_the_filing():
    cited = [_cited("DT-1001", 52000.0, "Evergreen Logistics Ltd")]
    draft = _draft(cited).model_copy(update={"unanchored_claims": ["Pulled unsupported claim."]})

    root = _serialize(draft, [_txn("DT-1001", "inbound", 52000.0, "Evergreen Logistics Ltd")])

    assert root.findtext("report_code") == "STR"


def test_goaml_xml_is_deterministic_for_the_same_filing_inputs():
    cited = [_cited("DT-1001", 52000.0, "Evergreen Logistics Ltd")]
    draft = _draft(cited)
    txns = [_txn("DT-1001", "inbound", 52000.0, "Evergreen Logistics Ltd")]

    assert _serialize_bytes(draft, txns) == _serialize_bytes(draft, txns)


@pytest.mark.parametrize("card", _TYPOLOGY_CARDS, ids=lambda card: card["code"])
def test_every_configured_typology_code_round_trips_as_a_valid_indicator(card):
    cited = [_cited("DT-1001", 52000.0, "Evergreen Logistics Ltd")]
    draft = _draft(cited).model_copy(
        update={
            "typology": MatchedTypology(
                code=card["code"],
                name=card["name"],
                source=card["source"],
            )
        }
    )
    root = _serialize(draft, [_txn("DT-1001", "inbound", 52000.0, "Evergreen Logistics Ltd")])

    assert _schema().validate(root)
    assert root.findtext("report_indicators/indicator") == card["code"]


def test_export_endpoint_maps_goaml_value_error_to_error_envelope(monkeypatch):
    import main

    def fail_export(*_args, **_kwargs):
        raise ValueError("goAML STR export requires at least one cited transaction.")

    client = TestClient(main.app, raise_server_exceptions=False)
    client.post("/alerts/HERO-002/decision", json={"action": "approve", "finalDisposition": "escalate"})
    monkeypatch.setattr(main, "to_goaml_str_xml", fail_export)

    r = client.get("/alerts/HERO-002/str.xml")

    assert r.status_code == 422
    assert r.json() == {
        "error": {
            "code": "GOAML_EXPORT_FAILED",
            "message": "goAML STR export requires at least one cited transaction.",
        }
    }


def test_submit_endpoint_maps_goaml_value_error_to_error_envelope(monkeypatch):
    import main

    def fail_export(*_args, **_kwargs):
        raise ValueError("goAML report failed XSD validation: invalid report")

    client = TestClient(main.app, raise_server_exceptions=False)
    client.post("/alerts/HERO-002/decision", json={"action": "approve", "finalDisposition": "escalate"})
    monkeypatch.setattr(main, "to_goaml_str_xml", fail_export)

    r = client.post("/alerts/HERO-002/str/submit")

    assert r.status_code == 422
    assert r.json() == {
        "error": {
            "code": "GOAML_EXPORT_FAILED",
            "message": "goAML report failed XSD validation: invalid report",
        }
    }


def test_submission_reference_is_deterministic_and_fiu_formatted():
    # Demo-stable (ADR-0003): the same alert always files under the same FIU ref.
    ref = submission_reference("DQ-001")
    assert ref == submission_reference("DQ-001")
    assert ref != submission_reference("DQ-002")
    assert ref.startswith("MYFIU-2026-")
