"""Pipeline orchestrator — integration test with a fake client (no tokens).

The fake returns canned responses in pipeline order: triage, verify, then (on
escalate) the STR narrative.
"""

import json

from agents.knowledge_base import get_card
from agents.pipeline import run_triage, run_triage_events
from schemas import Alert, TriageResult


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


def test_run_triage_assembles_full_result_on_escalate_agreed(make_client):
    two = get_card("PT-01").indicators[:2]
    fake = make_client(
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
    # The coverage behind the score is serialized for the UI (ADR-0007).
    assert out.indicator_coverage.fired == two
    assert out.indicator_coverage.indicators == get_card("PT-01").indicators
    assert out.verifier.status == "agreed"
    assert out.str_draft is not None
    assert out.cited_transaction_ids == ["T-1001", "T-1002"]


def test_flag_caps_confidence_and_verifier_stays_pure(make_client):
    four = get_card("PT-01").indicators[:4]
    fake = make_client(
        [
            _triage_json(four),
            json.dumps({"agreesWithRecommendation": False, "note": "Could be a benign sweep."}),
            json.dumps({"activitySummary": "x", "groundsForSuspicion": ["y"]}),
        ]
    )
    out = run_triage(_alert(), client=fake)
    assert out.verifier.status == "flagged"
    assert out.confidence == 0.59  # full coverage capped below the review threshold


def test_run_triage_events_streams_stages_then_result(make_client):
    # The streamed path yields a stage per pipeline step (with indicators one-by-one),
    # ending in a result that matches the batch run_triage.
    two = get_card("PT-01").indicators[:2]
    fake = make_client(
        [
            _triage_json(two),
            json.dumps({"agreesWithRecommendation": True, "note": "Clearly meets the test."}),
            json.dumps({"activitySummary": "Funds in then out.", "groundsForSuspicion": ["no purpose"]}),
        ]
    )
    events = list(run_triage_events(_alert(), client=fake))

    assert [e["id"] for e in events if e["type"] == "stage"] == [
        "retrieve", "triage", "verifier", "confidence", "draft",
    ]
    inds = [e for e in events if e["type"] == "indicator"]
    assert len(inds) == len(get_card("PT-01").indicators)
    assert sum(1 for e in inds if e["fired"]) == 2

    result = events[-1]
    assert result["type"] == "result"
    assert isinstance(result["triage"], TriageResult)
    assert result["triage"].recommendation == "escalate"
    assert result["triage"].confidence == 0.5
