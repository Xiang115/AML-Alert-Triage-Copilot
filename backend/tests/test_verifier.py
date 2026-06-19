"""verifier tests use a fake client — no DeepSeek calls, no tokens."""

import json

from agents.knowledge_base import get_card
from agents.verifier import verify


def test_disagreement_flags_for_human_review(make_client):
    card = get_card("FI-01")
    out = verify(
        "evidence block",
        "escalate",
        card,
        client=make_client([json.dumps({"agreesWithRecommendation": False, "note": "Could be a small business."})]),
    )
    assert out.status == "flagged"
    assert out.agrees_with_recommendation is False
    assert out.note


def test_agreement_passes_through(make_client):
    card = get_card("PT-01")
    out = verify(
        "evidence block",
        "escalate",
        card,
        client=make_client([json.dumps({"agreesWithRecommendation": True, "note": "Evidence clearly meets the test."})]),
    )
    assert out.status == "agreed"
    assert out.agrees_with_recommendation is True
