"""triage tests use a fake client — no DeepSeek calls, no tokens."""

import json

from agents.knowledge_base import get_card
from agents.triage import triage


def test_triage_prompt_withholds_benign_lookalike_and_distinguishing_test(make_client):
    # Triage matches on indicators ONLY; the benign look-alike + distinguishing test
    # are withheld and given to the verifier alone, so the two agents don't run the
    # same discrimination (ADR-0001). Triage seeing them made it do the verifier's job
    # and dismiss the crafted benign look-alikes, flip-flopping the hero cases.
    card = get_card("PT-01")
    fake = make_client([json.dumps({
        "matchedTypologyCode": "PT-01", "firedIndicators": [], "citedTransactionIds": [],
        "recommendation": "dismiss", "explanation": "x",
    })])
    triage("evidence block", [card], client=fake)

    system_msg = fake.calls[0]["messages"][0]["content"]
    user_msg = fake.calls[0]["messages"][1]["content"]
    assert str(card.indicators) in system_msg  # indicators ARE shown (in the cached prefix)
    whole = system_msg + user_msg
    assert card.benign_lookalike not in whole
    assert card.distinguishing_test not in whole


def test_triage_retries_on_unknown_typology_code(make_client):
    # A hallucinated code must fail validation and retry, not KeyError downstream.
    bad = json.dumps({"matchedTypologyCode": "ZZ-99", "firedIndicators": [],
                      "citedTransactionIds": [], "recommendation": "escalate", "explanation": "x"})
    good = json.dumps({"matchedTypologyCode": "PT-01", "firedIndicators": [],
                       "citedTransactionIds": [], "recommendation": "escalate", "explanation": "x"})
    fake = make_client([bad, good])
    out = triage("evidence block", [get_card("PT-01")], client=fake)

    assert out.matched_typology.code == "PT-01"
    assert len(fake.calls) == 2  # retried after the unknown code


def test_triage_no_match_sentinel_is_one_call_dismiss(make_client):
    # "NONE" means no typology fit — a reasoned dismiss in ONE call (no retry).
    fake = make_client([json.dumps({
        "matchedTypologyCode": "NONE", "firedIndicators": [], "citedTransactionIds": [],
        "recommendation": "dismiss", "explanation": "nothing matched",
    })])
    out = triage("evidence block", [get_card("PT-01")], client=fake)

    assert out.recommendation == "dismiss"
    assert out.matched_typology.code == "NONE"
    assert out.fired_indicators == []
    assert len(fake.calls) == 1  # did NOT retry


def test_triage_empty_code_normalises_to_no_match_without_retry(make_client):
    # An empty/missing code is the model saying "nothing matched" — not a failure
    # to retry. (A *hallucinated* code still retries — see the test above.)
    fake = make_client([json.dumps({
        "matchedTypologyCode": "", "citedTransactionIds": [],
        "recommendation": "escalate", "explanation": "x",
    })])
    out = triage("evidence block", [get_card("PT-01")], client=fake)

    assert out.matched_typology.code == "NONE"
    assert out.recommendation == "dismiss"  # forced: nothing to escalate without a typology
    assert len(fake.calls) == 1


def test_triage_resolves_card_and_clamps_indicators(make_client):
    card = get_card("PT-01")
    real_indicator = card.indicators[0]
    model_out = json.dumps(
        {
            "matchedTypologyCode": "PT-01",
            "firedIndicators": [real_indicator, "a hallucinated indicator"],
            "citedTransactionIds": ["T-1001"],
            "recommendation": "escalate",
            "explanation": "Funds in then out within hours.",
        }
    )
    out = triage("evidence block", [card], client=make_client([model_out]))

    assert out.recommendation == "escalate"
    assert out.matched_typology.model_dump() == {"code": "PT-01", "name": card.name, "source": card.source}
    assert out.fired_indicators == [real_indicator]  # hallucinated one dropped
    assert out.cited_transaction_ids == ["T-1001"]
    assert out.explanation
