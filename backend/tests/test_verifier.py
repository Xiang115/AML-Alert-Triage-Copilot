"""verifier tests use a fake client — no DeepSeek calls, no tokens."""

import json

from agents.knowledge_base import get_card
from agents.verifier import challenge, re_verdict, verify
from schemas import Challenge, Rebuttal, Reverdict


def test_disagreement_flags_for_human_review(make_client):
    card = get_card("FI-01")
    ver, claims = verify(
        "evidence block", "escalate", card,
        client=make_client([json.dumps({
            "agreesWithRecommendation": False,
            "claims": [{"claim": "Could be a small business.", "citedTransactionIds": [],
                        "firedIndicators": []}],
        })]),
    )
    assert ver.status == "flagged"
    assert ver.agrees_with_recommendation is False
    assert claims and claims[0].text == "Could be a small business."


def test_agreement_passes_through(make_client):
    card = get_card("PT-01")
    ver, claims = verify(
        "evidence block", "escalate", card,
        client=make_client([json.dumps({
            "agreesWithRecommendation": True,
            "claims": [{"claim": "Evidence clearly meets the test.", "citedTransactionIds": [],
                        "firedIndicators": []}],
        })]),
    )
    assert ver.status == "agreed"
    assert ver.agrees_with_recommendation is True


# --- adversarial debate (ADR-0011) -------------------------------------------------

def test_challenge_articulates_the_counter_case(make_client):
    # On a flag, the verifier states its strongest counter-hypothesis (the benign look-alike)
    # and a point-by-point read against the distinguishing test — the un-anchored Challenge.
    card = get_card("PT-01")
    out = challenge(
        "evidence block",
        "escalate",
        card,
        client=make_client([json.dumps({
            "counterHypothesis": "Looks like a payroll sweep, not a pass-through.",
            "distinguishingTestAssessment": "Funds dwell over a day, unlike a same-day pass-through.",
        })]),
    )
    assert isinstance(out, Challenge)
    assert out.counter_hypothesis.startswith("Looks like")
    assert out.distinguishing_test_assessment


def test_challenge_coerces_structured_assessment_to_string(make_client):
    # DeepSeek-flash often returns distinguishingTestAssessment as an object/list rather than a
    # string; the challenge must coerce it to readable prose instead of failing validation and
    # burning retries (observed live on DQ-002/006/009).
    out = challenge(
        "evidence block", "escalate", get_card("PT-01"),
        client=make_client([json.dumps({
            "counterHypothesis": {"benign": "payroll sweep"},
            "distinguishingTestAssessment": {"Irregular timing": "Not present", "Rationale": "ops account"},
        })]),
    )
    assert isinstance(out.counter_hypothesis, str)
    assert isinstance(out.distinguishing_test_assessment, str)
    assert "Irregular timing" in out.distinguishing_test_assessment
    assert "Not present" in out.distinguishing_test_assessment


def test_re_verdict_holds_when_unconvinced(make_client):
    # Triage did not concede; the verifier re-judges and is unmoved → flag holds, no flip.
    out = re_verdict(
        "evidence block", "escalate", get_card("PT-01"),
        Challenge(counter_hypothesis="benign sweep", distinguishing_test_assessment="dwell > 1d"),
        Rebuttal(argument="Balance drains to zero each cycle.", conceded=False),
        client=make_client([json.dumps({"outcome": "holds", "note": "Dwell time does not clear it."})]),
    )
    assert isinstance(out, Reverdict)
    assert out.outcome == "holds"
    assert out.disposition_changed is False
    assert out.note


def test_re_verdict_can_be_convinced(make_client):
    # The rebuttal persuades the verifier → resolves to agreed, but the disposition is unchanged.
    out = re_verdict(
        "evidence block", "escalate", get_card("PT-01"),
        Challenge(counter_hypothesis="benign sweep", distinguishing_test_assessment="dwell > 1d"),
        Rebuttal(argument="Counterparties are unrelated shells.", conceded=False),
        client=make_client([json.dumps({"outcome": "convinced", "note": "Shell counterparties settle it."})]),
    )
    assert out.outcome == "convinced"
    assert out.disposition_changed is False
