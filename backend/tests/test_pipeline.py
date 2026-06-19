"""Pipeline orchestrator — integration test with a fake client (no tokens).

The fake returns canned responses in pipeline order: triage, verify, then (on
escalate) the STR narrative.
"""

import json

from agents.knowledge_base import get_card
from agents.pipeline import run_triage
from schemas import Alert, TriageResult


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


def _alert():
    # ALERT-001. Stored fixture carries triage, so parse as Alert (an AlertInput).
    return Alert.model_validate(json.load(open("data/fixtures/alerts.json"))[0])


def _triage_json(fired, recommendation="escalate"):
    return json.dumps(
        {
            "matchedTypologyCode": "PT-01",
            "firedIndicators": fired,
            "citedTransactionIds": ["T-1001", "T-1002"],
            "recommendation": recommendation,
            "explanation": "In then out within hours.",
        }
    )


def test_run_triage_assembles_full_result_on_escalate_agreed():
    two = get_card("PT-01").indicators[:2]
    fake = FakeClient(
        [
            _triage_json(two),
            json.dumps({"agreesWithRecommendation": True, "note": "Clearly meets the test."}),
            json.dumps({"activitySummary": "Funds in then out.", "groundsForSuspicion": ["no purpose"]}),
        ]
    )
    out = run_triage(_alert(), client=fake)

    assert isinstance(out, TriageResult)  # conforms to the contract
    assert out.recommendation == "escalate"
    assert out.matched_typology.code == "PT-01"
    assert out.confidence == 0.5  # 2 of 4 indicators, escalate, not flagged
    assert out.verifier.status == "agreed"
    assert out.str_draft is not None
    assert out.cited_transaction_ids == ["T-1001", "T-1002"]


def test_flag_caps_confidence_and_verifier_stays_pure():
    four = get_card("PT-01").indicators[:4]
    fake = FakeClient(
        [
            _triage_json(four),
            json.dumps({"agreesWithRecommendation": False, "note": "Could be a benign sweep."}),
            json.dumps({"activitySummary": "x", "groundsForSuspicion": ["y"]}),
        ]
    )
    out = run_triage(_alert(), client=fake)
    assert out.verifier.status == "flagged"
    assert out.confidence == 0.59  # full coverage capped below the review threshold
