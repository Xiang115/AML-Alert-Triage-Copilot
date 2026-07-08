"""triage tests use a fake client — no DeepSeek calls, no tokens."""

import json

from agents.knowledge_base import get_card
from agents.triage import _cost_sensitive_escalate, rebut, triage
from schemas import Challenge


def test_triage_prompt_withholds_benign_lookalike_and_distinguishing_test(make_client):
    # Triage matches on indicators ONLY; the benign look-alike + distinguishing test
    # are withheld and given to the verifier alone, so the two agents don't run the
    # same discrimination (ADR-0001). Triage seeing them made it do the verifier's job
    # and dismiss the crafted benign look-alikes, flip-flopping the hero cases.
    card = get_card("PT-01")
    fake = make_client([json.dumps({
        "matchedTypologyCode": "PT-01", "firedIndicators": [],
        "recommendation": "dismiss", "claims": [],
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
                      "recommendation": "escalate", "claims": []})
    good = json.dumps({"matchedTypologyCode": "PT-01", "firedIndicators": [],
                       "recommendation": "escalate", "claims": []})
    fake = make_client([bad, good])
    out = triage("evidence block", [get_card("PT-01")], client=fake)

    assert out.matched_typology.code == "PT-01"
    assert len(fake.calls) == 2  # retried after the unknown code


def test_triage_no_match_sentinel_is_one_call_dismiss(make_client):
    # "NONE" means no typology fit — a reasoned dismiss in ONE call (no retry).
    fake = make_client([json.dumps({
        "matchedTypologyCode": "NONE", "firedIndicators": [],
        "recommendation": "dismiss", "claims": [],
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
        "matchedTypologyCode": "",
        "recommendation": "escalate", "claims": [],
    })])
    out = triage("evidence block", [get_card("PT-01")], client=fake)

    assert out.matched_typology.code == "NONE"
    assert out.recommendation == "dismiss"  # forced: nothing to escalate without a typology
    assert len(fake.calls) == 1


def test_triage_resolves_card_and_clamps_indicators(make_client):
    card = get_card("PT-01")
    real_indicator = card.indicators[0]
    model_out = json.dumps({
        "matchedTypologyCode": "PT-01",
        "firedIndicators": [real_indicator, "a hallucinated indicator"],
        "recommendation": "escalate",
        "claims": [
            {"claim": "Funds in then out within hours.",
             "citedTransactionIds": ["T-1001"], "firedIndicators": [real_indicator]},
        ],
    })
    out = triage("evidence block", [card], client=make_client([model_out]))

    assert out.recommendation == "escalate"
    assert out.matched_typology.model_dump() == {"code": "PT-01", "name": card.name, "source": card.source}
    assert out.fired_indicators == [real_indicator]           # hallucinated one dropped
    assert out.cited_transaction_ids == ["T-1001"]            # derived from the claim citation
    assert out.claims and out.claims[0].text.startswith("Funds in then out")


# --- adversarial debate rebuttal (ADR-0011) ---------------------------------------

def _challenge():
    return Challenge(
        counter_hypothesis="High-turnover retailer, not a pass-through.",
        distinguishing_test_assessment="Funds dwell over a day, unlike a same-day sweep.",
    )


def test_rebut_defends_the_call(make_client):
    out = rebut(
        "evidence block", get_card("PT-01"), _challenge(),
        client=make_client([json.dumps({
            "argument": "Balance still drains to zero each cycle.", "conceded": False})]),
    )
    assert out.conceded is False
    assert out.argument


def test_rebut_can_concede(make_client):
    out = rebut(
        "evidence block", get_card("PT-01"), _challenge(),
        client=make_client([json.dumps({
            "argument": "On reflection the dwell time fits a benign sweep.", "conceded": True})]),
    )
    assert out.conceded is True


# --- cost-sensitive operating point (recall-oriented escalation) -------------------

def test_cost_sensitive_escalate_pure():
    # A timid dismiss on a card that fired an indicator becomes an escalate.
    assert _cost_sensitive_escalate("dismiss", ["i1"], 1) == "escalate"
    # No fired indicators → no fabricated escalate.
    assert _cost_sensitive_escalate("dismiss", [], 1) == "dismiss"
    # An already-escalate call is untouched.
    assert _cost_sensitive_escalate("escalate", [], 1) == "escalate"
    # Threshold respected: one fired indicator under a min of 2 stays dismiss.
    assert _cost_sensitive_escalate("dismiss", ["i1"], 2) == "dismiss"


def test_cost_sensitive_flips_timid_dismiss_to_escalate(make_client):
    # Matched card + a real fired indicator + model said dismiss → cost-sensitive escalates.
    card = get_card("PT-01")
    real_indicator = card.indicators[0]
    out = triage("evidence block", [card], cost_sensitive=True, client=make_client([json.dumps({
        "matchedTypologyCode": "PT-01", "firedIndicators": [real_indicator],
        "recommendation": "dismiss", "claims": [],
    })]))
    assert out.recommendation == "escalate"
    assert out.fired_indicators == [real_indicator]


def test_cost_sensitive_does_not_escalate_when_nothing_fired(make_client):
    card = get_card("PT-01")
    out = triage("evidence block", [card], cost_sensitive=True, client=make_client([json.dumps({
        "matchedTypologyCode": "PT-01", "firedIndicators": [],
        "recommendation": "dismiss", "claims": [],
    })]))
    assert out.recommendation == "dismiss"  # no fired indicators → not forced


def test_cost_sensitive_never_escalates_no_match(make_client):
    # NO_MATCH is always a reasoned dismiss; cost-sensitive must not fabricate a match.
    out = triage("evidence block", [get_card("PT-01")], cost_sensitive=True,
                 client=make_client([json.dumps({
                     "matchedTypologyCode": "NONE", "firedIndicators": [],
                     "recommendation": "dismiss", "claims": [],
                 })]))
    assert out.recommendation == "dismiss"
    assert out.matched_typology.code == "NONE"


def test_default_is_not_cost_sensitive(make_client):
    # Without the flag, a matched dismiss stays dismiss even with a fired indicator.
    card = get_card("PT-01")
    out = triage("evidence block", [card], client=make_client([json.dumps({
        "matchedTypologyCode": "PT-01", "firedIndicators": [card.indicators[0]],
        "recommendation": "dismiss", "claims": [],
    })]))
    assert out.recommendation == "dismiss"


def test_cost_sensitive_note_only_in_prompt_when_enabled(make_client):
    card = get_card("PT-01")
    resp = json.dumps({"matchedTypologyCode": "PT-01", "firedIndicators": [],
                       "recommendation": "dismiss", "claims": []})
    on = make_client([resp]); triage("ev", [card], cost_sensitive=True, client=on)
    off = make_client([resp]); triage("ev", [card], client=off)
    assert "COST-SENSITIVE MODE" in on.calls[0]["messages"][0]["content"]
    assert "COST-SENSITIVE MODE" not in off.calls[0]["messages"][0]["content"]
