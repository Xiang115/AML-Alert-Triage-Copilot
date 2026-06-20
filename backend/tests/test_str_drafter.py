"""str_drafter tests use a fake client — no DeepSeek calls, no tokens."""

import json

from agents.knowledge_base import get_card
from agents.str_drafter import draft_str
from schemas import Alert, MatchedTypology, STRDraft, TriageOutput


def _alert():
    # ALERT-001 (has transactions). Stored fixture carries triage, so parse as Alert.
    return Alert.model_validate(json.load(open("data/fixtures/alerts.json"))[0])


def _triage(recommendation="escalate"):
    return TriageOutput(
        recommendation=recommendation,
        matched_typology=MatchedTypology(code="PT-01", name="Pass-through / Rapid Movement", source="FATF R.20"),
        fired_indicators=["Inbound credit followed by outbound debit"],
        cited_transaction_ids=["T-1001", "T-1002"],
        explanation="In then out within hours.",
    )


def test_no_str_draft_on_dismiss(make_client):
    fake = make_client([])
    out = draft_str(_alert(), _triage("dismiss"), get_card("PT-01"), client=fake)
    assert out is None
    assert fake.calls == []  # no LLM call when dismissing


def test_str_prompt_includes_cited_transactions_and_card_hints(make_client):
    # The narrative must be grounded in the real figures + the card's authored hints,
    # not just the indicator labels.
    fake = make_client([json.dumps({"activitySummary": "x", "groundsForSuspicion": ["y"]})])
    card = get_card("PT-01")
    draft_str(_alert(), _triage("escalate"), card, client=fake)

    user_msg = fake.calls[0]["messages"][1]["content"]
    assert "T-1001" in user_msg  # a cited transaction id, i.e. the real figures are present
    assert card.str_narrative_hints[0] in user_msg  # the card's authored narrative hints


def test_str_draft_structured_object_on_escalate(make_client):
    model_out = json.dumps(
        {
            "activitySummary": "Funds received and forwarded within hours.",
            "groundsForSuspicion": ["No economic purpose", "Balance drained to zero"],
        }
    )
    out = draft_str(_alert(), _triage("escalate"), get_card("PT-01"), client=make_client([model_out]))

    assert out.activity_summary == "Funds received and forwarded within hours."
    assert out.grounds_for_suspicion == ["No economic purpose", "Balance drained to zero"]
    assert out.subject.account_id == "AC-1001"
    assert [t.transaction_id for t in out.cited_transactions] == ["T-1001", "T-1002"]
    assert out.typology.code == "PT-01"
    assert out.recommended_action
    assert isinstance(out, STRDraft)  # conforms to the contract
