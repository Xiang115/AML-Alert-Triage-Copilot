"""triage tests use a fake client — no DeepSeek calls, no tokens."""

import json

from agents.knowledge_base import get_card
from agents.triage import triage


def test_triage_prompt_includes_benign_lookalike(make_client):
    # Triage must see each card's benign look-alike so it can rule it out on the
    # first pass, not lean entirely on the verifier (the crafted benign cases).
    card = get_card("PT-01")
    fake = make_client([json.dumps({
        "matchedTypologyCode": "PT-01", "firedIndicators": [], "citedTransactionIds": [],
        "recommendation": "dismiss", "explanation": "x",
    })])
    triage("evidence block", [card], client=fake)

    user_msg = fake.calls[0]["messages"][1]["content"]
    assert card.benign_lookalike in user_msg


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
