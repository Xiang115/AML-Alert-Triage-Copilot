from schemas import EvidenceIntegrity, TracedClaim, TriageResult, Verifier


def test_triageresult_defaults_claims_and_integrity():
    v = Verifier(status="agreed", agrees_with_recommendation=True)  # note now optional
    t = TriageResult(
        alert_id="A-1", recommendation="dismiss", confidence=0.9,
        matched_typology={"code": "NONE", "name": "No typology matched", "source": "—"},
        cited_transaction_ids=[], indicator_coverage={"indicators": [], "fired": []},
        verifier=v, str_draft=None, model="m", generated_at="2026-07-07T00:00:00",
    )
    assert t.claims == []
    assert t.evidence_integrity.total_count == 0
    assert v.claims == []


def test_verifier_and_triage_accept_claims():
    claim = TracedClaim(text="x", anchored=True, evidence={"transactionIds": ["T-1"]})
    v = Verifier(status="flagged", agrees_with_recommendation=False, claims=[claim])
    assert v.claims[0].evidence.transaction_ids == ["T-1"]
