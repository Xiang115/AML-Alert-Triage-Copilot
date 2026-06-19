"""triage tests use a fake client — no DeepSeek calls, no tokens."""

import json

from agents.knowledge_base import get_card
from agents.triage import triage


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
