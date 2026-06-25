"""Pipeline orchestrator — integration test with a fake client (no tokens).

The fake returns canned responses in pipeline order: triage, verify, then (on
escalate) the STR narrative.
"""

import json

from agents.knowledge_base import get_card
from agents.pipeline import resolve_concession, run_triage, run_triage_events
from schemas import Alert, TriageResult


def test_resolve_concession_gate():
    # ADR-0012: dismiss->escalate concession always honoured (recall-positive).
    assert resolve_concession("dismiss", 0, 2) == ("escalate", True)
    # A strong escalate (>= threshold fired) resists the drop -> holds as escalate.
    assert resolve_concession("escalate", 2, 2) == ("escalate", False)
    assert resolve_concession("escalate", 4, 2) == ("escalate", False)
    # A weak escalate (< threshold) is allowed to flip to dismiss.
    assert resolve_concession("escalate", 1, 2) == ("dismiss", True)
    assert resolve_concession("escalate", 0, 2) == ("dismiss", True)


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


def test_debate_holds_keeps_flag_and_caps_confidence(make_client):
    # ADR-0011: verifier flags an escalate, triage defends (no concede), the re-verdict HOLDS →
    # flag stands, confidence capped, disposition unchanged, and the debate is recorded.
    four = get_card("PT-01").indicators[:4]
    fake = make_client(
        [
            _triage_json(four),
            json.dumps({"agreesWithRecommendation": False, "note": "Could be a benign sweep."}),
            json.dumps({"counterHypothesis": "Payroll sweep.", "distinguishingTestAssessment": "Dwell > 1d."}),
            json.dumps({"argument": "Balance drains to zero each cycle.", "conceded": False}),
            json.dumps({"outcome": "holds", "note": "Dwell time does not clear it."}),
            json.dumps({"activitySummary": "x", "groundsForSuspicion": ["y"]}),
        ]
    )
    out = run_triage(_alert(), client=fake)
    assert out.recommendation == "escalate"  # unchanged — flag held, no flip
    assert out.verifier.status == "flagged"
    assert out.confidence == 0.59  # full coverage capped below the review threshold
    assert out.debate is not None
    assert out.debate.reverdict.outcome == "holds"
    assert out.debate.reverdict.disposition_changed is False
    assert out.str_draft is not None  # an escalate that held still drafts an STR


def test_debate_concede_flips_dismiss_to_escalate(make_client):
    # ADR-0011 deepest cut: verifier flags a DISMISS, triage concedes → disposition flips to escalate,
    # the verifier resolves to agreed, and an STR is now drafted for the saved alert.
    two = get_card("PT-01").indicators[:2]
    fake = make_client(
        [
            _triage_json(two, "dismiss"),
            json.dumps({"agreesWithRecommendation": False, "note": "This looks like a real pass-through."}),
            json.dumps({"counterHypothesis": "Active pass-through.", "distinguishingTestAssessment": "Same-day sweep."}),
            json.dumps({"argument": "On reflection the same-day sweep fits the typology.", "conceded": True}),
            json.dumps({"activitySummary": "Funds in then out.", "groundsForSuspicion": ["no purpose"]}),
        ]
    )
    out = run_triage(_alert(), client=fake)
    assert out.recommendation == "escalate"  # flipped from the first-pass dismiss
    assert out.verifier.status == "agreed"  # triage moved to the verifier's position
    assert out.debate.reverdict.outcome == "conceded"
    assert out.debate.reverdict.disposition_changed is True
    assert out.str_draft is not None  # the saved alert now gets an STR
    assert out.confidence == 0.5  # 2 of 4 coverage as an escalate, not capped (agreed)


def test_debate_resists_conceding_away_a_strong_escalation(make_client):
    # ADR-0012 recall fix: triage CONCEDES an escalate with a strong match (2 of 4 fired), but the
    # cost-sensitive gate resists — the call is NOT dropped to dismiss; it holds as escalate and
    # routes to a human (flagged -> needsReview). This is the fix for the debate dropping true reports.
    two = get_card("PT-01").indicators[:2]
    fake = make_client(
        [
            _triage_json(two, "escalate"),
            json.dumps({"agreesWithRecommendation": False, "note": "Could be a benign merchant."}),
            json.dumps({"counterHypothesis": "Legit merchant.", "distinguishingTestAssessment": "Retains balance."}),
            json.dumps({"argument": "On reflection it might be a merchant.", "conceded": True}),
            json.dumps({"activitySummary": "x", "groundsForSuspicion": ["y"]}),  # STR still drafted (escalate)
        ]
    )
    out = run_triage(_alert(), client=fake)
    assert out.recommendation == "escalate"  # NOT dropped despite the concession
    assert out.verifier.status == "flagged"  # holds -> flagged -> needsReview (human decides)
    assert out.debate.reverdict.outcome == "holds"
    assert out.debate.reverdict.disposition_changed is False
    assert out.str_draft is not None


def test_debate_honours_concession_on_a_weak_escalation(make_client):
    # The gate only protects STRONG matches: a thin escalate (1 of 4 fired) that triage concedes is
    # still allowed to flip to dismiss (no STR drafted).
    one = get_card("PT-01").indicators[:1]
    fake = make_client(
        [
            _triage_json(one, "escalate"),
            json.dumps({"agreesWithRecommendation": False, "note": "Likely benign."}),
            json.dumps({"counterHypothesis": "Benign.", "distinguishingTestAssessment": "Evidence is thin."}),
            json.dumps({"argument": "Agreed, the match is too thin.", "conceded": True}),
        ]
    )
    out = run_triage(_alert(), client=fake)
    assert out.recommendation == "dismiss"  # weak match: concession honoured, flips
    assert out.debate.reverdict.outcome == "conceded"
    assert out.debate.reverdict.disposition_changed is True
    assert out.str_draft is None


def test_debate_convinced_resolves_flag_without_flipping(make_client):
    # Triage does not concede but the re-verdict is CONVINCED → flag resolves to agreed, the
    # disposition is unchanged, and confidence is no longer capped.
    two = get_card("PT-01").indicators[:2]
    fake = make_client(
        [
            _triage_json(two, "escalate"),
            json.dumps({"agreesWithRecommendation": False, "note": "Could be benign."}),
            json.dumps({"counterHypothesis": "Benign retailer.", "distinguishingTestAssessment": "Maybe high turnover."}),
            json.dumps({"argument": "Counterparties are unrelated shells.", "conceded": False}),
            json.dumps({"outcome": "convinced", "note": "Shell counterparties settle it."}),
            json.dumps({"activitySummary": "x", "groundsForSuspicion": ["y"]}),
        ]
    )
    out = run_triage(_alert(), client=fake)
    assert out.recommendation == "escalate"  # unchanged
    assert out.verifier.status == "agreed"  # flag resolved by the rebuttal
    assert out.debate.reverdict.outcome == "convinced"
    assert out.debate.reverdict.disposition_changed is False
    assert out.confidence == 0.5  # 2 of 4 coverage, NOT capped


def test_run_triage_events_includes_the_debate_turns(make_client):
    # On a flagged first pass the timeline gains three turns between verifier and confidence.
    four = get_card("PT-01").indicators[:4]
    fake = make_client(
        [
            _triage_json(four),
            json.dumps({"agreesWithRecommendation": False, "note": "Could be a benign sweep."}),
            json.dumps({"counterHypothesis": "Payroll sweep.", "distinguishingTestAssessment": "Dwell > 1d."}),
            json.dumps({"argument": "Balance drains to zero.", "conceded": False}),
            json.dumps({"outcome": "holds", "note": "Does not clear it."}),
            json.dumps({"activitySummary": "x", "groundsForSuspicion": ["y"]}),
        ]
    )
    ids = [e["id"] for e in run_triage_events(_alert(), client=fake) if e["type"] == "stage"]
    assert ids == ["retrieve", "triage", "grounding", "verifier", "challenge", "rebuttal", "reverdict", "confidence", "draft"]


def test_retrieve_stage_shows_the_candidate_ranking(make_client):
    # The retrieve step now ranks candidates by signal overlap (display only — all cards still
    # go to triage). For ALERT-001 (pass-through evidence) PT-01 should lead the ranking.
    two = get_card("PT-01").indicators[:2]
    fake = make_client(
        [
            _triage_json(two),
            json.dumps({"agreesWithRecommendation": True, "note": "meets test"}),
            json.dumps({"activitySummary": "x", "groundsForSuspicion": ["y"]}),
        ]
    )
    retrieve = next(
        e for e in run_triage_events(_alert(), client=fake)
        if e["type"] == "stage" and e["id"] == "retrieve"
    )
    assert "Ranked" in retrieve["detail"]
    assert "PT-01" in retrieve["detail"]  # the strongest candidate is surfaced
    assert "passed to triage" in retrieve["detail"].lower()


def test_citations_are_grounded_to_the_ledger(make_client):
    # Citation Grounding: the model cites an id that isn't in the alert's ledger; the pipeline
    # clamps it out (provenance, not correctness) and the grounding stage reports the drop honestly.
    two = get_card("PT-01").indicators[:2]
    fake = make_client(
        [
            json.dumps(
                {
                    "matchedTypologyCode": "PT-01",
                    "firedIndicators": two,
                    "citedTransactionIds": ["T-1001", "T-9999"],  # T-9999 is not in the ledger
                    "recommendation": "escalate",
                    "explanation": "In then out within hours.",
                }
            ),
            json.dumps({"agreesWithRecommendation": True, "note": "meets test"}),
            json.dumps({"activitySummary": "x", "groundsForSuspicion": ["y"]}),
        ]
    )
    events = list(run_triage_events(_alert(), client=fake))
    result = events[-1]["triage"]
    # the hallucinated id is dropped — only the real ledger entry survives downstream
    assert result.cited_transaction_ids == ["T-1001"]
    assert result.str_draft is not None
    assert [c.transaction_id for c in result.str_draft.cited_transactions] == ["T-1001"]
    # the grounding stage reports it honestly
    grounding = next(e for e in events if e["type"] == "stage" and e["id"] == "grounding")
    assert "1 of 2" in grounding["detail"]
    assert "1 invalid" in grounding["detail"]
    assert "ledger" in grounding["detail"].lower()


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
        "retrieve", "triage", "grounding", "verifier", "confidence", "draft",
    ]
    inds = [e for e in events if e["type"] == "indicator"]
    assert len(inds) == len(get_card("PT-01").indicators)
    assert sum(1 for e in inds if e["fired"]) == 2
    # the grounding step reports the two cited ids as verified against the ledger, no drops
    grounding = next(e for e in events if e["type"] == "stage" and e["id"] == "grounding")
    assert "2 cited transactions verified against the account ledger" in grounding["detail"]

    result = events[-1]
    assert result["type"] == "result"
    assert isinstance(result["triage"], TriageResult)
    assert result["triage"].recommendation == "escalate"
    assert result["triage"].confidence == 0.5
