from datetime import datetime

import pytest
from pydantic import ValidationError

from schemas import Alert, Transaction


def _camel_triage(recommendation="escalate", with_str_draft=True):
    typ = {"code": "PT-01", "name": "Pass-through", "source": "FATF R.20"}
    str_draft = None
    if with_str_draft:
        str_draft = {
            "reportDate": "2026-06-01T09:00:00",
            "reportingInstitution": "Demo Bank",
            "subject": {
                "accountId": "AC1",
                "holderName": "Jane Tan",
                "accountType": "personal",
                "openedAt": "2025-01-01T00:00:00",
            },
            "typology": typ,
            "period": {"from": "2026-05-01T00:00:00", "to": "2026-06-01T00:00:00"},
            "activitySummary": "Funds in and out within hours.",
            "citedTransactions": [
                {
                    "transactionId": "T1",
                    "timestamp": "2026-06-01T09:30:00",
                    "amount": 1000.0,
                    "currency": "MYR",
                    "counterpartyName": "ACME Sdn Bhd",
                    "runningBalance": 0.0,
                }
            ],
            "groundsForSuspicion": ["No economic purpose", "Balance drained to zero"],
            "recommendedAction": "Escalate to FIED",
        }
    return {
        "alertId": "A1",
        "recommendation": recommendation,
        "confidence": 0.82,
        "explanation": "Classic pass-through.",
        "matchedTypology": typ,
        "citedTransactionIds": ["T1", "T2"],
        "verifier": {"status": "flagged", "agreesWithRecommendation": False, "note": "Could be a sweep."},
        "strDraft": str_draft,
        "model": "deepseek",
        "generatedAt": "2026-06-01T09:00:00",
    }


def _camel_alert(**over):
    base = {
        "alertId": "A1",
        "status": "pending",
        "createdAt": "2026-06-01T08:00:00",
        "riskScore": 82,
        "trigger": "rapid-movement",
        "account": {
            "accountId": "AC1",
            "holderName": "Jane Tan",
            "accountType": "personal",
            "openedAt": "2025-01-01T00:00:00",
        },
        "transactionIds": ["T1", "T2"],
        "triage": _camel_triage(),
    }
    base.update(over)
    return base


def _txn(**over):
    base = dict(
        transaction_id="T1",
        timestamp=datetime(2026, 6, 1, 9, 30),
        amount=1000.0,
        currency="MYR",
        direction="inbound",
        counterparty_name="ACME Sdn Bhd",
        channel="transfer",
        running_balance=1000.0,
        flags=[],
    )
    base.update(over)
    return base


def test_transaction_dumps_camelcase():
    dumped = Transaction(**_txn()).model_dump(by_alias=True)
    assert dumped["transactionId"] == "T1"
    assert dumped["runningBalance"] == 1000.0
    assert "transaction_id" not in dumped


def test_transaction_parses_camelcase_wire_payload():
    wire = {
        "transactionId": "T2",
        "timestamp": "2026-06-01T09:30:00",
        "amount": 500.0,
        "currency": "MYR",
        "direction": "outbound",
        "counterpartyName": "ACME Sdn Bhd",
        "channel": "transfer",
        "runningBalance": 0.0,
        "flags": ["rapid-movement"],
    }
    txn = Transaction.model_validate(wire)
    assert txn.transaction_id == "T2"
    assert txn.direction == "outbound"


def test_transaction_rejects_unknown_field():
    with pytest.raises(ValidationError):
        Transaction.model_validate({**_txn(transaction_id="T3"), "bogusField": 1})


def test_alert_parses_queue_payload_without_transactions():
    alert = Alert.model_validate(_camel_alert())
    assert alert.transactions is None  # queue items carry no embedded transactions
    assert alert.triage.verifier.agrees_with_recommendation is False
    assert alert.triage.str_draft is not None
    assert alert.triage.str_draft.period.from_.month == 5


def test_alert_detail_round_trips_with_embedded_transactions():
    payload = _camel_alert(
        transactions=[
            {
                "transactionId": "T1",
                "timestamp": "2026-06-01T09:30:00",
                "amount": 1000.0,
                "currency": "MYR",
                "direction": "inbound",
                "counterpartyName": "ACME Sdn Bhd",
                "channel": "transfer",
                "runningBalance": 1000.0,
                "flags": [],
            }
        ]
    )
    dumped = Alert.model_validate(payload).model_dump(by_alias=True)
    assert dumped["transactions"][0]["transactionId"] == "T1"
    assert dumped["triage"]["strDraft"]["period"]["from"] == datetime(2026, 5, 1)
    assert "str_draft" not in dumped["triage"]  # camelCase only


def test_dismiss_alert_has_null_str_draft():
    payload = _camel_alert(triage=_camel_triage(recommendation="dismiss", with_str_draft=False))
    alert = Alert.model_validate(payload)
    assert alert.triage.str_draft is None
    assert alert.model_dump(by_alias=True)["triage"]["strDraft"] is None
