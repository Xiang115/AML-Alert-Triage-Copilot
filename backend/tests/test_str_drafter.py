"""str_drafter tests use a fake client — no DeepSeek calls, no tokens."""

import json

from agents.knowledge_base import get_card
from agents.str_drafter import draft_str
from schemas import STRDraft


class _Resp:
    def __init__(self, content):
        self.choices = [type("C", (), {"message": type("M", (), {"content": content})})]


class FakeClient:
    def __init__(self, contents):
        self._contents = list(contents)
        self.calls = []
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _Resp(self._contents.pop(0))


def _alert():
    return json.load(open("data/fixtures/alerts.json"))[0]  # ALERT-001, has transactions


def _triage(recommendation="escalate"):
    return {
        "recommendation": recommendation,
        "matchedTypology": {"code": "PT-01", "name": "Pass-through / Rapid Movement", "source": "FATF R.20"},
        "firedIndicators": ["Inbound credit followed by outbound debit"],
        "citedTransactionIds": ["T-1001", "T-1002"],
        "explanation": "In then out within hours.",
    }


def test_no_str_draft_on_dismiss():
    fake = FakeClient([])
    out = draft_str(_alert(), _triage("dismiss"), get_card("PT-01"), client=fake)
    assert out is None
    assert fake.calls == []  # no LLM call when dismissing


def test_str_draft_structured_object_on_escalate():
    model_out = json.dumps(
        {
            "activitySummary": "Funds received and forwarded within hours.",
            "groundsForSuspicion": ["No economic purpose", "Balance drained to zero"],
        }
    )
    out = draft_str(_alert(), _triage("escalate"), get_card("PT-01"), client=FakeClient([model_out]))

    assert out["activitySummary"] == "Funds received and forwarded within hours."
    assert out["groundsForSuspicion"] == ["No economic purpose", "Balance drained to zero"]
    assert out["subject"]["accountId"] == "AC-1001"
    assert [t["transactionId"] for t in out["citedTransactions"]] == ["T-1001", "T-1002"]
    assert out["typology"]["code"] == "PT-01"
    assert out["recommendedAction"]
    STRDraft.model_validate(out)  # conforms to the contract
