"""LLM semantic anchor — verified entirely with a fake client (no DeepSeek call, no tokens).

These lock the prompt/parse/apply contract so the eventual real MODEL_VERIFIER run is cheap and
correct rather than a debugging loop.
"""

import json

import config
from agents.knowledge_base import get_card
from agents.semantic_anchor import semantic_review
from agents.str_drafter import draft_str
from schemas import Alert, MatchedTypology, TriageOutput


def _alert():
    return Alert.model_validate(json.load(open("data/fixtures/alerts.json"))[0])


def _triage():
    return TriageOutput(
        recommendation="escalate",
        matched_typology=MatchedTypology(code="PT-01", name="Pass-through / Rapid Movement", source="FATF R.20"),
        fired_indicators=["Inbound credit followed by outbound debit"],
        cited_transaction_ids=["T-1001", "T-1002"],
    )


def _draft(mk):
    """A real STRDraft (3 traced claims: 'No economic purpose' [unanchored], 'Balance drained to
    zero' [anchored], policy line [anchored]) built with a fake narrative call."""
    card = get_card("PT-01")
    narrative = json.dumps(
        {"activitySummary": "Funds in then out.", "groundsForSuspicion": ["No economic purpose", "Balance drained to zero"]}
    )
    return draft_str(_alert(), _triage(), card, client=mk([narrative])), card


def test_semantic_review_applies_verdicts_by_index_in_one_verifier_call(make_client):
    draft, card = _draft(make_client)
    verdicts = json.dumps({"verdicts": [
        {"index": 0, "verdict": "unsupported", "reason": "No transaction speaks to economic purpose."},
        {"index": 1, "verdict": "supported", "reason": "Running balance falls to near zero."},
        {"index": 2, "verdict": "supported", "reason": "The cited policy applies to this pattern."},
    ]})
    fake = make_client([verdicts])
    out = semantic_review(draft, _triage(), card, client=fake)

    assert out.traced_claims[0].semantic_verdict == "unsupported"
    assert out.traced_claims[1].semantic_verdict == "supported"
    assert out.traced_claims[1].semantic_reason.startswith("Running balance")
    # exactly one batched call, on the cheap verifier model
    assert len(fake.calls) == 1
    assert fake.calls[0]["model"] == config.MODEL_VERIFIER
    # the prompt carried the claims to judge and the concrete evidence to judge them against
    user_msg = fake.calls[0]["messages"][1]["content"]
    assert "Balance drained to zero" in user_msg
    assert "T-1001" in user_msg


def test_semantic_review_is_a_noop_with_no_claims(make_client):
    draft, card = _draft(make_client)
    empty = draft.model_copy(update={"traced_claims": []})
    fake = make_client([])  # any call would IndexError-pop from empty
    out = semantic_review(empty, _triage(), card, client=fake)
    assert out is empty
    assert fake.calls == []  # no tokens spent when there is nothing to review


def test_verdict_normalisation_is_robust_to_model_phrasing(make_client):
    draft, card = _draft(make_client)
    verdicts = json.dumps({"verdicts": [
        {"index": 0, "verdict": "Not supported", "reason": "x"},
        {"index": 1, "verdict": "SUPPORTED", "reason": "y"},
        {"index": 2, "verdict": "unclear from the evidence", "reason": "z"},
    ]})
    out = semantic_review(draft, _triage(), card, client=make_client([verdicts]))
    assert [c.semantic_verdict for c in out.traced_claims] == ["unsupported", "supported", "unclear"]


def test_reason_is_coerced_when_the_model_returns_structure(make_client):
    draft, card = _draft(make_client)
    verdicts = json.dumps({"verdicts": [{"index": 1, "verdict": "supported", "reason": {"balance": "drains to zero"}}]})
    out = semantic_review(draft, _triage(), card, client=make_client([verdicts]))
    assert isinstance(out.traced_claims[1].semantic_reason, str)
    assert "drains to zero" in out.traced_claims[1].semantic_reason


def test_claims_without_a_returned_verdict_stay_none(make_client):
    draft, card = _draft(make_client)
    verdicts = json.dumps({"verdicts": [{"index": 1, "verdict": "supported", "reason": "y"}]})
    out = semantic_review(draft, _triage(), card, client=make_client([verdicts]))
    assert out.traced_claims[1].semantic_verdict == "supported"
    assert out.traced_claims[0].semantic_verdict is None
    assert out.traced_claims[2].semantic_verdict is None
