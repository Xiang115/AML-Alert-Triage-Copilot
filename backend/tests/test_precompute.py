"""precompute.build_results — assembly integration test with a fake client (no tokens).

The fake returns canned pipeline responses per alert in order: triage, verify,
then (on escalate only) the STR narrative.
"""

import json

from data.precompute import build_results
from agents.knowledge_base import get_card
from schemas import Alert


class _Resp:
    def __init__(self, content):
        self.choices = [type("C", (), {"message": type("M", (), {"content": content})})]


class FakeClient:
    def __init__(self, contents):
        self._contents = list(contents)
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        return _Resp(self._contents.pop(0))


def _input_alert(alert_id="DQ-X", account_type="personal"):
    return {
        "alertId": alert_id,
        "status": "pending",
        "createdAt": "2026-06-15T08:00:00",
        "riskScore": 80,
        "trigger": "test trigger",
        "account": {"accountId": "AC-X", "holderName": "Test Holder", "accountType": account_type, "openedAt": "2025-01-01T00:00:00"},
        "transactionIds": ["TX-1", "TX-2"],
        "transactions": [
            {"transactionId": "TX-1", "timestamp": "2026-06-14T09:00:00", "amount": 50000.0, "currency": "MYR", "direction": "inbound", "counterpartyName": "Acme Ltd", "channel": "transfer", "runningBalance": 50100.0, "flags": []},
            {"transactionId": "TX-2", "timestamp": "2026-06-14T11:00:00", "amount": 49800.0, "currency": "MYR", "direction": "outbound", "counterpartyName": "Cash Co", "channel": "transfer", "runningBalance": 300.0, "flags": []},
        ],
    }


def _triage_json(recommendation, fired):
    return json.dumps({
        "matchedTypologyCode": "PT-01",
        "firedIndicators": fired,
        "citedTransactionIds": ["TX-1", "TX-2"],
        "recommendation": recommendation,
        "explanation": "in then out",
    })


def test_escalate_alert_assembles_valid_alert_with_str_draft():
    two = get_card("PT-01").indicators[:2]
    fake = FakeClient([
        _triage_json("escalate", two),
        json.dumps({"agreesWithRecommendation": True, "note": "meets test"}),
        json.dumps({"activitySummary": "Funds in then out.", "groundsForSuspicion": ["no purpose"]}),
    ])
    [result] = build_results([_input_alert("DQ-001")], client=fake)

    Alert.model_validate(result)  # conforms to the wire contract
    assert result["alertId"] == "DQ-001"
    assert result["triage"]["recommendation"] == "escalate"
    assert result["triage"]["strDraft"] is not None
    assert result["transactions"][0]["transactionId"] == "TX-1"  # detail embeds transactions


def test_dismiss_alert_has_null_str_draft_and_no_str_call():
    fake = FakeClient([
        _triage_json("dismiss", []),
        json.dumps({"agreesWithRecommendation": True, "note": "benign"}),
        # no third response: a dismiss must not trigger the STR drafter
    ])
    [result] = build_results([_input_alert("DQ-002", account_type="business")], client=fake)

    Alert.model_validate(result)
    assert result["triage"]["recommendation"] == "dismiss"
    assert result["triage"]["strDraft"] is None
