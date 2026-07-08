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


def _triage_json(fired, recommendation="escalate", cited=("T-1001", "T-1002"),
                  claim="In then out within hours."):
    return json.dumps(
        {
            "matchedTypologyCode": "PT-01",
            "firedIndicators": fired,
            "citedTransactionIds": list(cited),
            "recommendation": recommendation,
            "claims": [
                {"claim": claim, "citedTransactionIds": list(cited), "firedIndicators": fired},
            ],
        }
    )


def _verifier_json(agrees, note="Clearly meets the test."):
    # `note` here is just the claim text (ADR-0022: the verifier's rationale now travels
    # as claims, not a free-text note).
    return json.dumps(
        {
            "agreesWithRecommendation": agrees,
            "claims": [{"claim": note, "citedTransactionIds": [], "firedIndicators": []}],
        }
    )


def test_run_triage_assembles_full_result_on_escalate_agreed(make_client):
    two = get_card("PT-01").indicators[:2]
    fake = make_client(
        [
            _triage_json(two),
            _verifier_json(True, "Clearly meets the test."),
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


def test_pipeline_attaches_evidence_integrity(make_client):
    # ADR-0022: the pipeline anchors the triage claims and computes EvidenceIntegrity over them,
    # attaching both to the final TriageResult. One claim cites a real ledger transaction (anchors);
    # the other is a generic, unanchored inference.
    two = get_card("PT-01").indicators[:2]
    triage_json = json.dumps(
        {
            "matchedTypologyCode": "PT-01",
            "firedIndicators": two,
            "citedTransactionIds": ["T-1001", "T-1002"],
            "recommendation": "escalate",
            "claims": [
                {"claim": "Transfer T-1001 was forwarded within hours with no economic purpose.",
                 "citedTransactionIds": ["T-1001"], "firedIndicators": []},
                {"claim": "The customer seemed suspicious overall.",
                 "citedTransactionIds": [], "firedIndicators": []},
            ],
        }
    )
    fake = make_client(
        [
            triage_json,
            _verifier_json(True, "Clearly meets the test."),
            json.dumps({"activitySummary": "Funds in then out.", "groundsForSuspicion": ["no purpose"]}),
        ]
    )
    result = run_triage(_alert(), client=fake)

    assert result.evidence_integrity.total_count == len(result.claims) == 2
    assert result.evidence_integrity.anchored_count == sum(c.anchored for c in result.claims)
    assert result.evidence_integrity.anchored_count == 1  # the T-1001 claim anchors, the generic one doesn't
    assert result.evidence_integrity.unanchored_count == 1


def test_live_pipeline_passes_learned_memory_to_verifier(make_client):
    import main
    import store

    from agents.memory import signature as memory_signature

    # DEMO-CL-01 and DEMO-CL-02 share the behavioral envelope (fork B), so a clearance learned from
    # -01 surfaces on -02. Compute the signature instead of hardcoding a format the fork changed.
    sig = memory_signature(main.store.get_alert("DEMO-CL-01"))
    store.record_clearance(
        signature=sig,
        typology="PT-01",
        source_decision_id="DEMO-CL-01",
        source_alert_id="DEMO-CL-01",
        cleared_at="2026-07-08T10:00:00+08:00",
    )
    alert = Alert.model_validate(main.store.get_alert("DEMO-CL-02"))
    fake = make_client([
        _triage_json(
            [],
            recommendation="dismiss",
            cited=("DEMO-CL-02-T1", "DEMO-CL-02-T2"),
            claim="Licensed MSB remittance pattern.",
        ),
        _verifier_json(True, "Prior clearance and ledger envelope support benign remittance."),
    ])

    out = run_triage(alert, client=fake)

    assert out.suppression is not None
    assert out.suppression.status == "suppressed"
    assert out.suppression.source_decision_id == "DEMO-CL-01"
    verifier_prompt = fake.calls[1]["messages"][1]["content"]
    assert "Learned clearance precedent" in verifier_prompt
    assert "DEMO-CL-01" in verifier_prompt
    assert sig in verifier_prompt


def test_semantic_off_by_default_and_reviews_when_enabled(make_client):
    # Off by default: the 3-response fake below would IndexError if a 4th (semantic) call fired.
    two = get_card("PT-01").indicators[:2]
    base = [
        _triage_json(two),
        _verifier_json(True, "Clearly meets the test."),
        json.dumps({"activitySummary": "Funds in then out.", "groundsForSuspicion": ["no purpose"]}),
    ]
    off = make_client(list(base))
    out_off = run_triage(_alert(), client=off)
    assert len(off.calls) == 3  # no semantic call on the default path (precompute stays token-clean)
    assert all(c.semantic_verdict is None for c in out_off.str_draft.traced_claims)

    # Enabled: one extra MODEL_VERIFIER call annotates the claims (grounds = ['no purpose', policy line]).
    on = make_client(base + [json.dumps({"verdicts": [
        {"index": 0, "verdict": "unsupported", "reason": "no evidence of purpose"},
        {"index": 1, "verdict": "supported", "reason": "policy applies"},
    ]})])
    out_on = run_triage(_alert(), client=on, semantic=True)
    assert len(on.calls) == 4
    assert out_on.str_draft.traced_claims[0].semantic_verdict == "unsupported"
    assert out_on.str_draft.traced_claims[1].semantic_verdict == "supported"


def test_semantic_failure_does_not_discard_the_live_triage(make_client):
    # The semantic anchor is an advisory extra: if the flash call fails, the fresh live triage must
    # still stand (unannotated), not fall back. Two invalid replies exhaust complete_model's retry.
    two = get_card("PT-01").indicators[:2]
    fake = make_client([
        _triage_json(two),
        _verifier_json(True, "Meets the test."),
        json.dumps({"activitySummary": "Funds in then out.", "groundsForSuspicion": ["no purpose"]}),
        "not json",        # semantic attempt 1 -> invalid
        "still not json",  # semantic retry -> invalid -> ValueError, caught as best-effort
    ])
    out = run_triage(_alert(), client=fake, semantic=True)

    assert out.recommendation == "escalate"   # the live result survives the semantic failure
    assert out.str_draft is not None
    assert all(c.semantic_verdict is None for c in out.str_draft.traced_claims)  # just unannotated
    assert len(fake.calls) == 5  # triage, verify, draft, then semantic tried twice (retry) before giving up


def test_debate_holds_keeps_flag(make_client):
    # ADR-0011: verifier flags an escalate, triage defends (no concede), the re-verdict HOLDS →
    # flag stands, disposition unchanged, and the debate is recorded. The escalate keeps its
    # true coverage confidence (ADR-0007: only a flagged dismiss is capped).
    four = get_card("PT-01").indicators[:4]
    fake = make_client(
        [
            _triage_json(four),
            _verifier_json(False, "Could be a benign sweep."),
            json.dumps({"counterHypothesis": "Payroll sweep.", "distinguishingTestAssessment": "Dwell > 1d."}),
            json.dumps({"argument": "Balance drains to zero each cycle.", "conceded": False}),
            json.dumps({"outcome": "holds", "note": "Dwell time does not clear it."}),
            json.dumps({"activitySummary": "x", "groundsForSuspicion": ["y"]}),
        ]
    )
    out = run_triage(_alert(), client=fake)
    assert out.recommendation == "escalate"  # unchanged — flag held, no flip
    assert out.verifier.status == "flagged"
    assert out.confidence == 1.0  # full coverage (4/4), NOT capped — an escalate never auto-clears
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
            _verifier_json(False, "This looks like a real pass-through."),
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
            _verifier_json(False, "Could be a benign merchant."),
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
            _verifier_json(False, "Likely benign."),
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
            _verifier_json(False, "Could be benign."),
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
            _verifier_json(False, "Could be a benign sweep."),
            json.dumps({"counterHypothesis": "Payroll sweep.", "distinguishingTestAssessment": "Dwell > 1d."}),
            json.dumps({"argument": "Balance drains to zero.", "conceded": False}),
            json.dumps({"outcome": "holds", "note": "Does not clear it."}),
            json.dumps({"activitySummary": "x", "groundsForSuspicion": ["y"]}),
        ]
    )
    ids = [e["id"] for e in run_triage_events(_alert(), client=fake) if e["type"] == "stage"]
    assert ids == ["retrieve", "screening", "triage", "grounding", "verifier", "challenge", "rebuttal", "reverdict", "confidence", "draft"]


def test_retrieve_stage_shows_the_candidate_ranking(make_client):
    # The retrieve step now ranks candidates by signal overlap (display only — all cards still
    # go to triage). For ALERT-001 (pass-through evidence) PT-01 should lead the ranking.
    two = get_card("PT-01").indicators[:2]
    fake = make_client(
        [
            _triage_json(two),
            _verifier_json(True, "meets test"),
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
            _triage_json(two, cited=("T-1001", "T-9999")),  # T-9999 is not in the ledger
            _verifier_json(True, "meets test"),
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
            _verifier_json(True, "Clearly meets the test."),
            json.dumps({"activitySummary": "Funds in then out.", "groundsForSuspicion": ["no purpose"]}),
        ]
    )
    events = list(run_triage_events(_alert(), client=fake))

    assert [e["id"] for e in events if e["type"] == "stage"] == [
        "retrieve", "screening", "triage", "grounding", "verifier", "confidence", "draft",
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
