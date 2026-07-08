"""str_drafter tests use a fake client — no DeepSeek calls, no tokens."""

import json

from agents.knowledge_base import get_card
from agents.str_drafter import draft_str, policy_basis_line, recommended_action
from schemas import Alert, MatchedTypology, STRDraft, TriageOutput


def test_recommended_action_varies_by_typology_when_verifier_agreed():
    a = recommended_action("agreed", "Pass-through / Rapid Movement")
    b = recommended_action("agreed", "Structuring / Smurfing")
    assert "Pass-through / Rapid Movement" in a
    assert "FIED" in a
    assert a != b  # reflects the matched typology — not a hardcoded constant


def test_recommended_action_holds_for_confirmation_when_verifier_flagged():
    out = recommended_action("flagged", "Pass-through / Rapid Movement")
    assert "Hold" in out  # a flagged call must not be filed without human confirmation
    assert "Pass-through / Rapid Movement" in out


def _alert():
    # ALERT-001 (has transactions). Stored fixture carries triage, so parse as Alert.
    return Alert.model_validate(json.load(open("data/fixtures/alerts.json"))[0])


def _triage(recommendation="escalate"):
    return TriageOutput(
        recommendation=recommendation,
        matched_typology=MatchedTypology(code="PT-01", name="Pass-through / Rapid Movement", source="FATF R.20"),
        fired_indicators=["Inbound credit followed by outbound debit"],
        cited_transaction_ids=["T-1001", "T-1002"],
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
    card = get_card("PT-01")
    out = draft_str(_alert(), _triage("escalate"), card, client=make_client([model_out]))

    assert out.activity_summary == "Funds received and forwarded within hours."
    # grounds_for_suspicion is now the ANCHORED-only filed list (ADR-0013): "Balance drained to
    # zero" anchors to the cited transactions and the policy line to its citation, while the pure
    # inference "No economic purpose" (no ledger anchor) is pulled from the filed draft.
    assert out.grounds_for_suspicion == ["Balance drained to zero", policy_basis_line(card.citation)]
    assert out.unanchored_claims == ["No economic purpose"]
    assert out.subject.account_id == "AC-1001"
    assert [t.transaction_id for t in out.cited_transactions] == ["T-1001", "T-1002"]
    assert out.typology.code == "PT-01"
    assert out.recommended_action
    assert isinstance(out, STRDraft)  # conforms to the contract


def test_citation_appended_to_grounds_and_recommended_action(make_client):
    # Slice B: the matched card's verified citation is surfaced on the STR deterministically.
    model_out = json.dumps({"activitySummary": "x", "groundsForSuspicion": ["No economic purpose"]})
    card = get_card("PT-01")
    assert card.citation and "FATF Recommendation 20" in card.citation
    out = draft_str(_alert(), _triage("escalate"), card, client=make_client([model_out]))
    assert f"Policy basis: {card.citation}." in out.grounds_for_suspicion
    assert card.citation in out.recommended_action


def test_no_citation_means_no_policy_line(make_client):
    # a card without a citation must not leak a "Policy basis: None" line (backward compatible)
    model_out = json.dumps({"activitySummary": "x", "groundsForSuspicion": ["No economic purpose"]})
    card = get_card("PT-01").model_copy(update={"citation": None})
    out = draft_str(_alert(), _triage("escalate"), card, client=make_client([model_out]))
    assert out.grounds_for_suspicion == ["No economic purpose"]
    assert "Policy basis" not in out.recommended_action


def test_draft_str_does_not_duplicate_the_policy_line(make_client):
    # idempotent: the guard means the citation line is never appended twice
    model_out = json.dumps({"activitySummary": "x", "groundsForSuspicion": ["a", "b"]})
    card = get_card("PT-01")
    out = draft_str(_alert(), _triage("escalate"), card, client=make_client([model_out]))
    line = policy_basis_line(card.citation)
    assert out.grounds_for_suspicion.count(line) == 1


# --- Evidence-Anchored STR (ADR-0013): Anchoring / self-review ---------------------------------


def _draft_with_grounds(make_client, grounds, triage=None, card=None):
    model_out = json.dumps({"activitySummary": "x", "groundsForSuspicion": grounds})
    return draft_str(
        _alert(), triage or _triage("escalate"), card or get_card("PT-01"),
        client=make_client([model_out]),
    )


def test_ground_naming_a_cited_txn_id_is_anchored_to_it(make_client):
    out = _draft_with_grounds(make_client, ["Transfer T-1001 had no economic rationale"])
    claim = next(c for c in out.traced_claims if c.text.startswith("Transfer T-1001"))
    assert claim.anchored
    assert "T-1001" in claim.evidence.transaction_ids
    assert "Transfer T-1001 had no economic rationale" in out.grounds_for_suspicion


def test_ground_quoting_a_cited_amount_or_counterparty_anchors_to_the_cited_txns(make_client):
    alert = _alert()
    tx = next(t for t in alert.transactions if t.transaction_id == "T-1001")
    ground = f"Funds were forwarded to {tx.counterparty_name} totalling {tx.amount:g}"
    model_out = json.dumps({"activitySummary": "x", "groundsForSuspicion": [ground]})
    out = draft_str(alert, _triage("escalate"), get_card("PT-01"), client=make_client([model_out]))
    claim = next(c for c in out.traced_claims if c.text == ground)
    assert claim.anchored
    assert set(claim.evidence.transaction_ids) == {"T-1001", "T-1002"}


def test_ground_describing_running_balance_behaviour_is_anchored(make_client):
    # The signature mule tell (balance draining to ~0) anchors to the cited transactions even though
    # the sentence names no id / amount / counterparty (ADR-0013 widened anchors).
    out = _draft_with_grounds(make_client, ["The running balance was swept to near-zero within a day"])
    claim = out.traced_claims[0]
    assert claim.anchored
    assert claim.evidence.transaction_ids  # points at the cited transactions


def test_ground_restating_a_fired_indicator_anchors_via_indicators(make_client):
    triage = TriageOutput(
        recommendation="escalate",
        matched_typology=MatchedTypology(code="PT-01", name="Pass-through / Rapid Movement", source="FATF R.20"),
        fired_indicators=["Inbound credit followed by outbound debit"],
        cited_transaction_ids=[],  # no cited txns, so only the indicator can anchor this ground
    )
    out = _draft_with_grounds(make_client, ["An inbound credit was followed by an outbound debit"], triage=triage)
    claim = out.traced_claims[0]
    assert claim.anchored
    assert claim.evidence.fired_indicators == ["Inbound credit followed by outbound debit"]


def test_generic_ground_with_no_anchor_is_unanchored_and_not_filed(make_client):
    out = _draft_with_grounds(
        make_client, ["The customer seemed suspicious overall", "Balance drained to zero"])
    assert "The customer seemed suspicious overall" in out.unanchored_claims
    assert "The customer seemed suspicious overall" not in out.grounds_for_suspicion
    generic = next(c for c in out.traced_claims if c.text.startswith("The customer"))
    assert not generic.anchored


def test_policy_basis_line_is_anchored_to_the_citation(make_client):
    card = get_card("PT-01")
    out = _draft_with_grounds(make_client, ["Balance drained to zero"], card=card)
    line = policy_basis_line(card.citation)
    claim = next(c for c in out.traced_claims if c.text == line)
    assert claim.anchored
    assert claim.evidence.citation == card.citation


def test_all_unanchored_guard_keeps_a_nonempty_grounds_list(make_client):
    # Every ground is a pure inference with no anchor, and the card carries no policy line — the
    # guard must still ship a non-empty grounds list rather than an empty report.
    card = get_card("PT-01").model_copy(update={"citation": None})
    out = _draft_with_grounds(make_client, ["Very suspicious", "Looks like laundering"], card=card)
    assert out.grounds_for_suspicion == ["Very suspicious", "Looks like laundering"]
    assert out.unanchored_claims == []
    assert all(not c.anchored for c in out.traced_claims)


def test_kw_overlap_is_deterministic_and_case_insensitive():
    from agents.anchoring import _kw_overlap

    assert _kw_overlap("Rapid movement of funds", "rapid movement observed") is True
    assert _kw_overlap("RAPID MOVEMENT of funds", "rapid movement observed") is True
    assert _kw_overlap("Rapid movement of funds", "an unrelated sentence") is False


# --- Narrative figure check (ADR-0013 deepening) -----------------------------------------------


def _fig_alert():
    from types import SimpleNamespace

    txns = [
        SimpleNamespace(transaction_id="T1", amount=5000.0, running_balance=5000.0, direction="inbound"),
        SimpleNamespace(transaction_id="T2", amount=3000.0, running_balance=8000.0, direction="inbound"),
        SimpleNamespace(transaction_id="T3", amount=8000.0, running_balance=0.0, direction="outbound"),
    ]
    alert = SimpleNamespace(transactions=txns)
    triage = SimpleNamespace(cited_transaction_ids=["T1", "T2", "T3"])
    return alert, triage


def test_narrative_amount_is_pinned_to_the_matching_transaction():
    from agents.str_drafter import _check_narrative_figures

    alert, triage = _fig_alert()
    figs = {f.text: f for f in _check_narrative_figures(
        alert, triage, "An inbound credit of 5,000 was received.")}
    assert figs["5,000"].kind == "transaction"
    assert "T1" in figs["5,000"].transaction_ids


def test_narrative_figure_matching_nothing_is_flagged_unmatched():
    # A number in the narrative that equals no txn, sum, or balance is surfaced (neutrally) for the
    # analyst to check — not silently accepted.
    from agents.str_drafter import _check_narrative_figures

    alert, triage = _fig_alert()
    figs = {f.text: f for f in _check_narrative_figures(
        alert, triage, "A suspicious 9,999 also appeared.")}
    assert figs["9,999"].kind == "unmatched"
    assert figs["9,999"].transaction_ids == []


def test_legitimate_total_is_not_false_flagged_even_when_approximate():
    # 'over £110k' equals the SUM of the cited amounts (not any single txn) -> verified as total,
    # never flagged. This is the guard against embarrassing false positives on real totals.
    from types import SimpleNamespace

    from agents.str_drafter import _check_narrative_figures

    txns = [SimpleNamespace(transaction_id=f"T{i}", amount=10000.0 + i, running_balance=0.0,
                            direction="inbound") for i in range(11)]  # sum == 110055
    alert = SimpleNamespace(transactions=txns)
    triage = SimpleNamespace(cited_transaction_ids=[f"T{i}" for i in range(11)])
    figs = _check_narrative_figures(alert, triage, "In total, over £110k flowed in.")
    total = next(f for f in figs if "110" in f.text)
    assert total.kind == "total"


def test_opening_balance_matches_the_pre_transaction_balance():
    # 'initial balance of 5,000' equals the balance just before T1 (5000 in - lands at 5000),
    # so it verifies against the ledger rather than being flagged.
    from agents.str_drafter import _check_narrative_figures

    alert, triage = _fig_alert()
    figs = {f.text: f for f in _check_narrative_figures(
        alert, triage, "Starting from an initial balance of 5,000, funds moved through.")}
    assert figs["5,000"].kind in ("transaction", "balance")  # a real ledger value, not unverified


def test_bare_integers_counts_and_years_are_not_treated_as_amounts():
    from agents.str_drafter import _check_narrative_figures

    alert, triage = _fig_alert()
    figs = _check_narrative_figures(
        alert, triage, "On 8 October 2022 the account received 11 inbound payments.")
    # '8', '2022', '11' carry no currency / separator / decimal / magnitude -> not amounts, not flagged
    assert figs == []


def test_activity_summary_prose_is_never_pruned(make_client):
    summary = "The account received inbound funds. This looks suspicious."
    model_out = json.dumps({"activitySummary": summary, "groundsForSuspicion": ["Balance drained to zero"]})
    out = draft_str(_alert(), _triage("escalate"), get_card("PT-01"), client=make_client([model_out]))
    assert out.activity_summary == summary  # narrative is kept verbatim
