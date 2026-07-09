"""FastAPI serving layer (Phase 7) — all contract endpoints, mocked (no tokens).

The live /triage endpoint injects a fake LLM client via the get_llm_client
dependency override, so the whole suite spends zero DeepSeek tokens.
"""

import copy
import json

import pytest
from fastapi.testclient import TestClient
from lxml import etree

import goaml
import main
from main import app, get_llm_client
from schemas import AccessControlPosture, Alert, BankIntegrationContract, CaseHandoff, CopilotRunLedger, CopilotRunList, DecisionTrace, DefenseCase, FinalsDemoScript, FinalsEvidenceBundle, FinalsQADefensePacket, GovernanceChangeRequestList, InnovationDifferentiation, OperationalImpact, PilotAdoptionPlan, ProductionTrustPlan, QAOutcome, QAOutcomeSummary, ReadinessSummary, TechnicalArchitecture, TriageResult, ValidationDossier

# State isolation (_reset_state) and the ':memory:' DB live in conftest.py — autouse.
client = TestClient(app)


def _decision_payload_for_final(alert_id: str, final_disposition: str, note: str | None = None) -> dict:
    recommendation = client.get(f"/alerts/{alert_id}").json()["triage"]["recommendation"]
    if recommendation == final_disposition:
        return {"action": "approve", "finalDisposition": final_disposition}
    return {
        "action": "override",
        "finalDisposition": final_disposition,
        "note": note or "Test analyst reason for overriding the stored AI recommendation.",
    }


def _signature_for(alert_id: str) -> str:
    from agents.memory import signature as memory_signature

    sig = memory_signature(main.store.get_alert(alert_id))
    assert sig is not None
    return sig


# --- Slice A: cross-customer self-learning suppression -----------------------------

@pytest.fixture
def slice_a_catalog():
    """Temporarily replace the alert catalog without leaking that seed to later tests."""
    saved_alert_seed = copy.deepcopy(main.store._alert_seed)
    main.store.clear_alerts()
    main.store.seed_alerts([_slice_a_alert("SLICEA-001"), _slice_a_alert("SLICEA-002")])
    yield
    main.store._alert_seed = saved_alert_seed
    main.store.reset()


def _slice_a_alert(alert_id: str) -> dict:
    """Clone one valid alert fixture into a tiny custom alert for suppression tests."""
    with open("data/results.json", encoding="utf-8") as f:
        template = next(a for a in json.load(f) if a["triage"]["matchedTypology"]["code"] != "NONE")

    alert = copy.deepcopy(template)
    alert["alertId"] = alert_id
    alert["status"] = "pending"
    alert["routing"] = "needsReview"
    alert["account"]["accountId"] = f"ACC-{alert_id}"
    alert["account"]["holderName"] = f"Slice A account {alert_id}"
    alert["transactionIds"] = [f"{alert_id}-T0", f"{alert_id}-T1", f"{alert_id}-T2"]
    alert["transactions"] = [
        {
            "transactionId": f"{alert_id}-T0", "timestamp": "2026-07-02T09:00:00", "amount": 1000.0,
            "currency": "MYR", "direction": "inbound", "counterpartyName": "ACME Payroll",
            "counterpartyAccount": "acme-123", "counterpartyBank": "Demo Bank", "channel": "ach",
            "runningBalance": 1000.0, "flags": [],
        },
        {
            "transactionId": f"{alert_id}-T1", "timestamp": "2026-07-02T10:00:00", "amount": 950.0,
            "currency": "MYR", "direction": "outbound", "counterpartyName": "ACME Payroll",
            "counterpartyAccount": "acme-123", "counterpartyBank": "Demo Bank", "channel": "ach",
            "runningBalance": 50.0, "flags": [],
        },
        {
            "transactionId": f"{alert_id}-T2", "timestamp": "2026-07-02T11:00:00", "amount": 25.0,
            "currency": "MYR", "direction": "outbound", "counterpartyName": "Utility Provider",
            "counterpartyAccount": "utility-999", "counterpartyBank": "Demo Bank", "channel": "bill-pay",
            "runningBalance": 25.0, "flags": [],
        },
    ]
    alert["triage"]["alertId"] = alert_id
    alert["triage"]["recommendation"] = "dismiss"  # a benign look-alike (the panel is dismiss-gated)
    alert["triage"]["citedTransactionIds"] = [f"{alert_id}-T0", f"{alert_id}-T1"]
    alert["triage"]["suppression"] = None
    return alert


def test_get_alert_detail_enriches_with_a_learned_suppression(slice_a_catalog):
    learned = client.post(
        "/alerts/SLICEA-001/decision",
        json=_decision_payload_for_final("SLICEA-001", "dismiss"),
    )
    assert learned.status_code == 200

    r = client.get("/alerts/SLICEA-002")
    assert r.status_code == 200
    suppression = r.json()["triage"]["suppression"]
    assert suppression["status"] == "suppressed"
    assert suppression["sourceDecisionId"] == "SLICEA-001"
    assert suppression["matchedPatternId"] == _signature_for("SLICEA-001")


def test_learned_patterns_returns_session_patterns(slice_a_catalog):
    client.post("/alerts/SLICEA-001/decision", json=_decision_payload_for_final("SLICEA-001", "dismiss"))

    r = client.get("/learned-patterns")
    assert r.status_code == 200
    # the session-learned pattern is present (alongside the demo seed) with the right shape
    sig = _signature_for("SLICEA-001")
    learned = next(p for p in r.json() if p["signature"] == sig)
    assert learned == {
        "signature": sig,
        "typology": "PT-01",
        "sourceAlertId": "SLICEA-001",
        "clearedCount": 1,
        "clearedAt": learned["clearedAt"],
    }
    assert learned["clearedAt"].endswith("+08:00")


def test_learned_patterns_open_with_the_demo_seed():
    # Slice A: /learned-patterns is populated with the seeded prior clearance in LIVE mode too
    # (parity with mock) — the tab isn't empty before any session dismiss. The seed is a real benign
    # dismiss (SD-00015), not the stale SD-00004 escalate the pre-refactor seed cited.
    sigs = [p["signature"] for p in client.get("/learned-patterns").json()]
    assert _signature_for("STANDCL-01") in sigs


def test_learning_loop_opportunities_enumerates_population_and_future_effects():
    r = client.get("/learning-loop/opportunities")
    assert r.status_code == 200
    body = r.json()

    assert body["scannedAlerts"] >= 31
    assert body["teachableSources"] >= 4
    assert body["reusableSources"] >= 1
    assert body["affectedFutureAlerts"] >= 2

    demo_source = next(c for c in body["candidates"] if c["sourceAlertId"] == "DEMO-CL-01")
    assert demo_source["canTeach"] is True
    assert demo_source["signature"] == _signature_for("DEMO-CL-01")
    assert {a["alertId"] for a in demo_source["affectedFutureAlerts"]} == {"DEMO-CL-02", "DEMO-CL-03"}

    blocked = next(c for c in body["candidates"] if c["sourceAlertId"] == "IBM-MULE-01")
    assert blocked["canTeach"] is False
    assert blocked["blockedReason"].startswith("No reusable signature")


def test_seeded_suppression_enriches_the_standing_look_alike():
    # The standing cluster ships STANDCL-01 as a prior clearance, so its look-alike STANDCL-02 (same
    # benign FI-01 envelope) shows a real auto-suppressed panel on a cold load and auto-clears.
    la = client.get("/alerts/STANDCL-02").json()
    s = la["triage"]["suppression"]
    assert s and s["status"] == "suppressed"
    assert s["sourceDecisionId"] == "STANDCL-01"
    assert s["matchedPatternId"] == _signature_for("STANDCL-02")
    assert la["routing"] == "autoCleared"  # no debate on the look-alike -> genuinely auto-suppressed

    # The teacher is NOT suppressed against the pattern it itself taught (no self-count).
    assert client.get("/alerts/STANDCL-01").json()["triage"]["suppression"] is None


def test_suppression_panel_never_shows_on_an_escalate():
    # suppress() matches on the behavioral envelope alone, so a learned clearance could otherwise
    # paint "matches a previously cleared pattern" onto a confident escalate. The served display is
    # gated on the recommendation: an escalate never surfaces a suppression panel.
    sig = _signature_for("SD-00006")  # a confident escalate
    assert client.get("/alerts/SD-00006").json()["triage"]["recommendation"] == "escalate"
    main.store.record_clearance(sig, "PT-01", "PRIOR-DEC", "PRIOR-ALERT", "2026-06-01T09:00:00+08:00")

    assert client.get("/alerts/SD-00006").json()["triage"]["suppression"] is None


def test_queue_list_reroutes_a_borderline_dismiss_after_a_clearance_is_learned():
    # ADR-0021 (beat-2 queue-shrink): the benign cluster starts on the needsReview worklist; dismissing
    # one sibling teaches the cross-customer pattern, and the others auto-clear off the list next fetch.
    before = {a["alertId"]: a["routing"] for a in client.get("/alerts").json()}
    assert before["DEMO-CL-02"] == "needsReview"
    assert before["DEMO-CL-03"] == "needsReview"

    dec = client.post("/alerts/DEMO-CL-01/decision", json=_decision_payload_for_final("DEMO-CL-01", "dismiss"))
    assert dec.status_code == 200

    after = {a["alertId"]: a["routing"] for a in client.get("/alerts").json()}
    assert after["DEMO-CL-02"] == "autoCleared"  # self-suppressed off the worklist
    assert after["DEMO-CL-03"] == "autoCleared"


def test_queue_routing_filter_uses_post_control_lane_after_suppression():
    # The filtered lane itself must shrink/grow with the serve-time suppression reroute, not just
    # the body field on an unfiltered list response.
    before_needs_review = {a["alertId"] for a in client.get("/alerts", params={"routing": "needsReview"}).json()}
    assert {"DEMO-CL-02", "DEMO-CL-03"} <= before_needs_review

    dec = client.post("/alerts/DEMO-CL-01/decision", json=_decision_payload_for_final("DEMO-CL-01", "dismiss"))
    assert dec.status_code == 200

    after_needs_review = {a["alertId"] for a in client.get("/alerts", params={"routing": "needsReview"}).json()}
    after_auto_cleared = {a["alertId"] for a in client.get("/alerts", params={"routing": "autoCleared"}).json()}
    assert "DEMO-CL-02" not in after_needs_review
    assert "DEMO-CL-03" not in after_needs_review
    assert {"DEMO-CL-02", "DEMO-CL-03"} <= after_auto_cleared


# --- serve-time insight: Account Activity Profile + STR filing SLA ---

def test_alert_detail_carries_the_account_activity_profile(slice_a_catalog):
    r = client.get("/alerts/SLICEA-001")
    assert r.status_code == 200
    body = r.json()
    Alert.model_validate(body)  # the serve-time fields conform to the contract
    profile = body["activityProfile"]
    assert profile["turnover"] == [
        {"currency": "MYR", "inbound": 1000.0, "outbound": 975.0, "net": 25.0}
    ]
    assert profile["balanceSwept"]["sweptToNearZero"] is True   # 1000 -> 50 -> 25
    assert profile["crossBorder"]["jurisdictions"] == 1
    assert profile["concentration"]["topCounterparty"] == "ACME Payroll"
    assert profile["concentration"]["topShare"] == 0.6667


def test_alert_defense_case_exposes_evidence_controls_and_audit():
    r = client.get("/alerts/HERO-002/defense-case")
    assert r.status_code == 200
    body = r.json()
    assert body["alertId"] == "HERO-002"
    DefenseCase.model_validate(body)
    assert body["decisionContext"]["aiRecommendation"] in {"escalate", "dismiss"}
    assert body["evidence"]["matchedTypology"]["code"]
    assert "fired" in body["evidence"]["indicatorCoverage"]
    assert "transactions" not in body  # packet cites evidence; it does not dump the full ledger

    auto_clear = body["controls"]["autoClearPolicy"]
    assert auto_clear["thresholds"]["autoClear"] == main.config.AUTO_CLEAR_THRESHOLD
    assert auto_clear["reasons"]
    assert body["controls"]["strFiling"]["requiresEscalateSignoff"] is True
    assert body["controls"]["strFiling"]["blocksUnanchoredGrounds"] is True
    assert isinstance(body["audit"], list)


def test_alert_defense_case_reflects_escalate_signoff_and_audit():
    client.post("/alerts/HERO-002/decision", json=_decision_payload_for_final("HERO-002", "escalate"))

    r = client.get("/alerts/HERO-002/defense-case")

    assert r.status_code == 200
    body = r.json()
    assert body["decisionContext"]["finalDisposition"] == "escalate"
    assert body["controls"]["strFiling"]["canFile"] is True
    assert any(e["event"] == "decision" for e in body["audit"])


def test_alert_defense_case_unknown_alert_returns_error_shaped_404():
    r = client.get("/alerts/NOPE/defense-case")

    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ALERT_NOT_FOUND"


def test_alert_defense_case_is_openapi_typed():
    spec = client.get("/openapi.json").json()
    schema = spec["paths"]["/alerts/{alert_id}/defense-case"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]

    assert schema["$ref"] == "#/components/schemas/DefenseCase"


def test_case_handoff_exposes_bank_writeback_packet():
    r = client.get("/alerts/HERO-002/case-handoff")
    assert r.status_code == 200
    body = r.json()
    CaseHandoff.model_validate(body)
    assert body["alertId"] == "HERO-002"
    assert body["caseStatusUpdate"] in {"needsReview", "autoCleared", "escalated", "dismissed", "filed"}
    assert "case-management" in body["caseNote"] or "AI recommended" in body["caseNote"]
    assert any("Actimize" in system for system in body["targetSystems"])
    endpoints = {artifact["endpoint"] for artifact in body["attachments"]}
    assert "/alerts/HERO-002/defense-case" in endpoints
    assert "/audit" in endpoints
    assert body["writeBack"]["requiresHumanDecision"] is True
    assert body["writeBack"]["productionGate"]
    assert any("does not mutate" in claim for claim in body["nonClaims"])


def test_case_handoff_unlocks_human_approved_writeback_after_decision():
    client.post("/alerts/HERO-002/decision", json=_decision_payload_for_final("HERO-002", "escalate"))

    body = client.get("/alerts/HERO-002/case-handoff").json()

    assert body["caseStatusUpdate"] == "escalated"
    assert body["decision"]["finalDisposition"] == "escalate"
    assert body["writeBack"]["mode"] == "humanApprovedWriteback"
    assert body["writeBack"]["allowed"] is True
    assert any(e["event"] == "decision" for e in body["auditEvents"])


def test_case_handoff_carries_submission_reference_after_filing():
    client.post("/alerts/HERO-002/decision", json=_decision_payload_for_final("HERO-002", "escalate"))
    filed = client.post("/alerts/HERO-002/str/submit")
    assert filed.status_code == 200

    body = client.get("/alerts/HERO-002/case-handoff").json()

    assert body["caseStatusUpdate"] == "filed"
    assert body["submissionRef"] == filed.json()["submissionRef"]
    assert any(e["event"] == "submission" for e in body["auditEvents"])


def test_case_handoff_is_openapi_typed():
    spec = client.get("/openapi.json").json()
    schema = spec["paths"]["/alerts/{alert_id}/case-handoff"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]

    assert schema["$ref"] == "#/components/schemas/CaseHandoff"


def test_decision_trace_exposes_observable_decision_path_not_llm_cot():
    r = client.get("/alerts/HERO-002/decision-trace")
    assert r.status_code == 200
    body = r.json()
    DecisionTrace.model_validate(body)
    assert body["alertId"] == "HERO-002"
    assert body["currentRecommendation"] in {"escalate", "dismiss"}
    assert body["routing"] in {"autoCleared", "needsReview"}
    assert "confidence" in body["formula"]
    step_kinds = {step["step"] for step in body["steps"]}
    assert "indicatorEvaluation" in step_kinds
    assert "confidenceComputation" in step_kinds
    assert "verifierGate" in step_kinds
    assert "routePolicy" in step_kinds
    assert "strFilingGate" in step_kinds
    assert "transactions" not in body
    non_claims = " ".join(body["nonClaims"]).lower()
    assert "not deepseek chain-of-thought" in non_claims
    assert "does not rerun" in non_claims


def test_decision_trace_reflects_human_decision_in_str_gate():
    before = client.get("/alerts/HERO-002/decision-trace").json()
    assert next(step for step in before["steps"] if step["step"] == "strFilingGate")["result"] == "locked"

    client.post("/alerts/HERO-002/decision", json=_decision_payload_for_final("HERO-002", "escalate"))
    after = client.get("/alerts/HERO-002/decision-trace").json()

    filing = next(step for step in after["steps"] if step["step"] == "strFilingGate")
    assert filing["inputs"]["finalDisposition"] == "escalate"
    assert filing["result"] == "canFile"


def test_decision_trace_is_openapi_typed():
    spec = client.get("/openapi.json").json()
    schema = spec["paths"]["/alerts/{alert_id}/decision-trace"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]

    assert schema["$ref"] == "#/components/schemas/DecisionTrace"


def test_copilot_runs_exposes_reconstructed_precomputed_ledger():
    runs = client.get("/alerts/HERO-002/copilot-runs")
    assert runs.status_code == 200
    run_list = runs.json()
    CopilotRunList.model_validate(run_list)
    assert run_list["alertId"] == "HERO-002"
    assert run_list["runs"][0]["runId"] == "precomputed-current"
    assert run_list["runs"][0]["status"] == "reconstructed"

    r = client.get("/alerts/HERO-002/copilot-runs/precomputed-current/ledger")
    assert r.status_code == 200
    body = r.json()
    CopilotRunLedger.model_validate(body)
    assert body["mode"] == "precomputed"
    assert body["provider"] == "precomputed-fixture"
    assert body["llmCalls"]
    assert body["llmCalls"][0]["stage"] == "triageAgent"
    assert body["llmCalls"][0]["messages"][0]["contentHash"].startswith("sha256:")
    assert body["llmCalls"][0]["schemaValid"] is True
    assert body["deterministicEvents"]
    assert "transactions" not in body
    non_claims = " ".join(body["nonClaims"]).lower()
    assert "not deepseek chain-of-thought" in non_claims
    assert "prompt/response envelope" in non_claims


def test_precomputed_ledger_reconstructs_claims():
    r = client.get("/alerts/HERO-002/copilot-runs/precomputed-current/ledger")
    body = r.json()
    triage_call = next(c for c in body["llmCalls"] if c["stage"] == "triageAgent")
    raw = json.loads(triage_call["rawResponse"])
    assert "claims" in raw
    assert "explanation" not in raw


def test_copilot_ledger_captures_live_llm_messages_after_triage(make_client):
    card_indicator = "Inbound credit followed by outbound debit of a similar amount within a short window (minutes to a few days)"
    fake = make_client([
        json.dumps({"matchedTypologyCode": "PT-01", "firedIndicators": [card_indicator],
                    "citedTransactionIds": ["DT-1001"], "recommendation": "escalate",
                    "claims": [{"claim": "LEDGER-MARKER", "citedTransactionIds": [], "firedIndicators": []}]}),
        json.dumps({"agreesWithRecommendation": True, "note": "meets test"}),
        json.dumps({"activitySummary": "ledger summary", "groundsForSuspicion": ["x"]}),
    ])
    app.dependency_overrides[get_llm_client] = lambda: fake

    triage = client.post("/alerts/HERO-002/triage")
    assert triage.status_code == 200

    run_list = client.get("/alerts/HERO-002/copilot-runs").json()
    live = next(run for run in run_list["runs"] if run["mode"] == "live")
    ledger = client.get(live["ledgerEndpoint"]).json()

    CopilotRunLedger.model_validate(ledger)
    assert ledger["status"] == "completed"
    assert [call["stage"] for call in ledger["llmCalls"]][:3] == ["triageAgent", "verifier", "strDrafter"]
    assert ledger["llmCalls"][0]["messages"][0]["role"] == "system"
    assert ledger["llmCalls"][0]["messages"][1]["role"] == "user"
    assert ledger["llmCalls"][0]["rawResponseHash"].startswith("sha256:")
    assert ledger["llmCalls"][0]["schemaValid"] is True
    assert "LEDGER-MARKER" in ledger["llmCalls"][0]["rawResponse"]
    assert ledger["finalOutput"]["claims"][0]["text"] == "LEDGER-MARKER"


def test_copilot_ledger_is_openapi_typed():
    spec = client.get("/openapi.json").json()
    runs_schema = spec["paths"]["/alerts/{alert_id}/copilot-runs"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    ledger_schema = spec["paths"]["/alerts/{alert_id}/copilot-runs/{run_id}/ledger"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]

    assert runs_schema["$ref"] == "#/components/schemas/CopilotRunList"
    assert ledger_schema["$ref"] == "#/components/schemas/CopilotRunLedger"


def test_filing_sla_activates_on_an_escalate_decision(slice_a_catalog):
    before = client.get("/alerts/SLICEA-001").json()["filingSla"]
    assert "next working day" in before["citation"]

    d = client.post(
        "/alerts/SLICEA-001/decision",
        json=_decision_payload_for_final("SLICEA-001", "escalate"),
    )
    assert d.status_code == 200

    sla = client.get("/alerts/SLICEA-001").json()["filingSla"]
    assert sla["applicable"] is True
    assert sla["state"] in {"active", "overdue"}
    assert sla["dueBy"] is not None
    assert sla["establishedAt"] is not None


def test_override_requires_an_analyst_reason(slice_a_catalog):
    alert = client.get("/alerts/SLICEA-001").json()
    expected_override = "dismiss" if alert["triage"]["recommendation"] == "escalate" else "escalate"

    r = client.post(
        "/alerts/SLICEA-001/decision",
        json={"action": "override", "finalDisposition": expected_override, "note": "   "},
    )

    assert r.status_code == 422
    assert r.json()["error"]["code"] == "OVERRIDE_REASON_REQUIRED"


def test_decision_rejects_client_disposition_drift(slice_a_catalog):
    alert = client.get("/alerts/SLICEA-001").json()
    illegal_disposition = "dismiss" if alert["triage"]["recommendation"] == "escalate" else "escalate"

    r = client.post(
        "/alerts/SLICEA-001/decision",
        json={"action": "approve", "finalDisposition": illegal_disposition},
    )

    assert r.status_code == 422
    assert r.json()["error"]["code"] == "DECISION_DISPOSITION_MISMATCH"


def test_override_reason_is_trimmed_into_audit(slice_a_catalog):
    alert = client.get("/alerts/SLICEA-001").json()
    expected_override = "dismiss" if alert["triage"]["recommendation"] == "escalate" else "escalate"

    r = client.post(
        "/alerts/SLICEA-001/decision",
        json={
            "action": "override",
            "finalDisposition": expected_override,
            "note": "  Known payroll corridor already cleared by compliance.  ",
        },
    )

    assert r.status_code == 200
    audit = client.get("/audit").json()
    decision = next(e for e in audit if e["alertId"] == "SLICEA-001" and e["event"] == "decision")
    assert decision["action"] == "override"
    assert decision["note"] == "Known payroll corridor already cleared by compliance."


# --- auto-clear assurance (ADR-0019) ---

def test_metrics_carries_auto_clear_leakage():
    m = client.get("/metrics").json()
    cm = m["confusionMatrix"]
    # Derived token-free from the served aggregates; assert internal consistency so a future eval
    # re-run (which shifts the numbers) doesn't break the test. The exact derivation is unit-tested
    # against fixed inputs in test_assurance.py.
    assert m["totalReports"] == cm["tp"] + cm["fn"]
    assert m["autoClearedReports"] >= 0
    assert m["autoClearLeakageRate"] == round(m["autoClearedReports"] / m["totalReports"], 4)


def test_alerts_flags_a_risk_weighted_qa_sample():
    import math

    import config as _cfg

    alerts = client.get("/alerts").json()
    cleared = [a for a in alerts if a.get("routing") == "autoCleared"]
    sampled = [a for a in alerts if a.get("qaSampled")]
    assert len(cleared) > 0
    assert len(sampled) == max(1, math.ceil(_cfg.QA_SAMPLE_RATE * len(cleared)))
    assert all(a["routing"] == "autoCleared" for a in sampled)


# --- model governance + borderline dismiss (ADR-0020) ---

def test_governance_snapshot():
    import config as _cfg

    g = client.get("/governance").json()
    assert g["model"]["workhorse"] == _cfg.MODEL_WORKHORSE
    assert g["thresholds"]["review"] == _cfg.REVIEW_THRESHOLD
    assert g["thresholds"]["autoClear"] == _cfg.AUTO_CLEAR_THRESHOLD
    assert g["thresholds"]["borderlineMargin"] == _cfg.BORDERLINE_MARGIN
    assert len(g["securityPosture"]) >= 1
    assert "decisions" in g["override"]


def test_access_control_posture_exposes_role_gated_write_contract():
    r = client.get("/security/access-control")
    assert r.status_code == 200
    body = r.json()
    AccessControlPosture.model_validate(body)
    assert body["mode"] == "actorRoleHeaders"
    rules = {rule["endpoint"]: rule for rule in body["rules"]}
    assert {"analyst", "compliance", "admin"} <= set(rules["/alerts/{alert_id}/decision"]["allowedRoles"])
    assert {"compliance", "admin"} <= set(rules["/alerts/{alert_id}/str/submit"]["allowedRoles"])
    assert rules["/reset"]["allowedRoles"] == ["admin"]
    assert any("OIDC" in claim for claim in body["nonClaims"])


def test_access_control_posture_is_openapi_typed():
    spec = client.get("/openapi.json").json()
    schema = spec["paths"]["/security/access-control"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]

    assert schema["$ref"] == "#/components/schemas/AccessControlPosture"


def test_decision_rejects_wrong_actor_role_and_audits_allowed_actor():
    denied = client.post(
        "/alerts/HERO-002/decision",
        json=_decision_payload_for_final("HERO-002", "escalate"),
        headers={"X-Actor-Id": "qa-1", "X-Actor-Role": "qa"},
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "ROLE_FORBIDDEN"

    allowed = client.post(
        "/alerts/HERO-002/decision",
        json=_decision_payload_for_final("HERO-002", "escalate"),
        headers={"X-Actor-Id": "analyst-7", "X-Actor-Role": "analyst"},
    )
    assert allowed.status_code == 200
    decision = next(e for e in client.get("/audit").json() if e["alertId"] == "HERO-002" and e["event"] == "decision")
    assert decision["actorId"] == "analyst-7"
    assert decision["actorRole"] == "analyst"


def test_str_submission_requires_compliance_actor_and_records_actor():
    client.post(
        "/alerts/HERO-002/decision",
        json=_decision_payload_for_final("HERO-002", "escalate"),
        headers={"X-Actor-Id": "analyst-7", "X-Actor-Role": "analyst"},
    )
    denied = client.post(
        "/alerts/HERO-002/str/submit",
        headers={"X-Actor-Id": "analyst-7", "X-Actor-Role": "analyst"},
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "ROLE_FORBIDDEN"

    filed = client.post(
        "/alerts/HERO-002/str/submit",
        headers={"X-Actor-Id": "mlro-1", "X-Actor-Role": "compliance"},
    )
    assert filed.status_code == 200
    ack = filed.json()
    assert ack["actorId"] == "mlro-1"
    assert ack["actorRole"] == "compliance"
    submission = next(e for e in client.get("/audit").json() if e["alertId"] == "HERO-002" and e["event"] == "submission")
    assert submission["actorId"] == "mlro-1"
    assert submission["actorRole"] == "compliance"


def test_reset_is_admin_only_when_actor_headers_are_present():
    denied = client.post("/reset", headers={"X-Actor-Id": "analyst-7", "X-Actor-Role": "analyst"})
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "ROLE_FORBIDDEN"

    allowed = client.post("/reset", headers={"X-Actor-Id": "ops-admin", "X-Actor-Role": "admin"})
    assert allowed.status_code == 200
    assert allowed.json()["actorRole"] == "admin"


def test_governance_change_requests_expose_model_risk_control_plane():
    r = client.get("/governance/change-requests")
    assert r.status_code == 200
    body = r.json()
    GovernanceChangeRequestList.model_validate(body)
    assert body["mode"] == "modelRiskChangeControl"
    assert body["pending"] >= 1
    assert "immutable" in body["blockedReason"]
    change = next(c for c in body["changes"] if c["changeId"] == "chg-threshold-auto-clear-hardening")
    assert change["status"] == "proposed"
    assert "modelRisk" in change["requiredApprovals"]
    assert "/qa/outcomes" in change["evidence"]
    assert any("does not mutate" in claim for claim in change["nonClaims"])


def test_governance_change_approval_requires_required_role_approvals():
    proposed = next(
        c for c in client.get("/governance/change-requests").json()["changes"]
        if c["changeId"] == "chg-threshold-auto-clear-hardening"
    )
    proposed["status"] = "approved"
    proposed["approvals"] = [
        {"role": "modelRisk", "approver": "mrm-1", "approvedAt": "2026-07-07T10:00:00+08:00"}
    ]
    denied = client.post(
        "/governance/change-requests",
        json=proposed,
        headers={"X-Actor-Id": "mrm-1", "X-Actor-Role": "modelRisk"},
    )
    assert denied.status_code == 422
    assert denied.json()["error"]["code"] == "APPROVAL_REQUIRED"

    proposed["approvals"].append(
        {"role": "compliance", "approver": "mlro-1", "approvedAt": "2026-07-07T10:05:00+08:00"}
    )
    accepted = client.post(
        "/governance/change-requests",
        json=proposed,
        headers={"X-Actor-Id": "mlro-1", "X-Actor-Role": "compliance"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "approved"


def test_governance_change_requests_are_openapi_typed():
    spec = client.get("/openapi.json").json()
    schema = spec["paths"]["/governance/change-requests"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]

    assert schema["$ref"] == "#/components/schemas/GovernanceChangeRequestList"


def test_qa_outcome_records_sample_review_and_audit():
    r = client.post(
        "/alerts/HERO-002/qa-outcome",
        json={"outcome": "confirmedClear", "reviewer": "qa-lead", "note": "Spot check confirmed the current disposition."},
        headers={"X-Actor-Id": "qa-lead", "X-Actor-Role": "qa"},
    )
    assert r.status_code == 200
    outcome = r.json()
    QAOutcome.model_validate(outcome)
    assert outcome["alertId"] == "HERO-002"
    assert outcome["reviewer"] == "qa-lead"
    assert outcome["actorId"] == "qa-lead"
    assert outcome["actorRole"] == "qa"
    assert "/alerts/HERO-002/decision-trace" in outcome["evidenceEndpoints"]

    summary = client.get("/qa/outcomes").json()
    QAOutcomeSummary.model_validate(summary)
    assert summary["reviewed"] == 1
    assert summary["confirmedClears"] == 1
    assert summary["missedSuspicion"] == 0
    assert summary["missRate"] == 0
    assert summary["outcomes"][0]["alertId"] == "HERO-002"
    qa_event = next(e for e in client.get("/audit").json() if e["event"] == "qaOutcome")
    assert qa_event["actorId"] == "qa-lead"
    assert qa_event["actorRole"] == "qa"


def test_qa_outcome_requires_reviewer_note():
    r = client.post(
        "/alerts/HERO-002/qa-outcome",
        json={"outcome": "missedSuspicion", "reviewer": "qa-lead", "note": "   "},
    )

    assert r.status_code == 422
    assert r.json()["error"]["code"] == "QA_NOTE_REQUIRED"


def test_qa_outcomes_are_openapi_typed():
    spec = client.get("/openapi.json").json()
    summary_schema = spec["paths"]["/qa/outcomes"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    outcome_schema = spec["paths"]["/alerts/{alert_id}/qa-outcome"]["post"]["responses"]["200"]["content"]["application/json"]["schema"]

    assert summary_schema["$ref"] == "#/components/schemas/QAOutcomeSummary"
    assert outcome_schema["$ref"] == "#/components/schemas/QAOutcome"


def test_integration_contract_names_data_access_outputs_and_gates():
    r = client.get("/integration/contract")
    assert r.status_code == 200
    body = r.json()
    BankIntegrationContract.model_validate(body)
    assert body["mode"] == "shadowFirst"
    assert any("Actimize" in s for s in body["inboundSystems"])
    assert any(f["name"] == "alertId" and f["required"] is True for f in body["minimumRequiredFields"])
    assert any("defense-case" in artifact for artifact in body["outboundArtifacts"])
    assert any("historical replay" in gate for gate in body["productionGates"])
    assert any("Does not auto-file STRs" in goal for goal in body["nonGoals"])


def test_integration_contract_is_openapi_typed():
    spec = client.get("/openapi.json").json()
    schema = spec["paths"]["/integration/contract"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]

    assert schema["$ref"] == "#/components/schemas/BankIntegrationContract"


def test_production_trust_plan_answers_bank_integration_validation_and_governance():
    r = client.get("/production/trust-plan")
    assert r.status_code == 200
    body = r.json()
    ProductionTrustPlan.model_validate(body)
    assert body["mode"] == "productionTrustPlan"
    systems = " ".join(body["targetSystems"])
    assert "Actimize" in systems
    assert "Mantas" in systems
    assert "goAML" in systems
    data = " ".join(body["minimumDataAccess"])
    assert "Transaction id" in data
    assert "running balance" in data
    assert "confirmed STR/no-STR outcome" in data
    controls = " ".join(body["governanceControls"])
    assert "verifier" in controls
    assert "QA-sampled" in controls
    assert "leakage" in controls
    gates = " ".join(body["validationGates"])
    assert "historical replay" in gates
    assert "shadow pilot" in gates
    assert any(item["area"] == "falsePositiveGovernance" for item in body["items"])
    assert "should not trust" in body["judgeResponse"]
    assert any("Synthetic held-out metrics" in claim for claim in body["nonClaims"])


def test_production_trust_plan_is_openapi_typed():
    spec = client.get("/openapi.json").json()
    schema = spec["paths"]["/production/trust-plan"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]

    assert schema["$ref"] == "#/components/schemas/ProductionTrustPlan"


def test_pilot_adoption_plan_is_conservative_about_bank_procurement():
    r = client.get("/pilot/adoption-plan")
    assert r.status_code == 200
    body = r.json()
    PilotAdoptionPlan.model_validate(body)
    assert body["mode"] == "bankPilot"
    assert any("Malaysia" in segment or "APAC" in segment for segment in body["targetSegments"])
    assert any("Model risk" in stakeholder for stakeholder in body["buyerStakeholders"])
    assert body["pilotEconomics"]["estimatedMonthlyHoursSaved"] > 0
    assert "not a production claim" in body["pilotEconomics"]["caveat"]
    assert len(body["sensitivityCases"]) >= 3
    assert any(case["monthlyAlerts"] == 20000 for case in body["sensitivityCases"])
    assert any("Paid shadow pilot" == tier["name"] for tier in body["commercialModel"])
    assert any("Production assist" == tier["name"] for tier in body["commercialModel"])
    assert any("overlay" in item for item in body["competitivePositioning"])
    assert any("Week 8" == step["week"] for step in body["pilotTimeline"])
    assert any("Shadow pilot" == phase["name"] for phase in body["phases"])
    assert any("leakage" in criterion for criterion in body["successCriteria"])
    evidence = " ".join(body["validationEvidence"])
    assert "Nasdaq 2024 Global Financial Crime Report" in evidence
    assert "Federal Reserve SR 11-7" in evidence
    assert "/operations/impact" in evidence
    assert any("months" in risk for risk in body["procurementRisks"])
    assert any("No claim of immediate annual contract" in claim for claim in body["nonClaims"])


def test_pilot_adoption_plan_is_openapi_typed():
    spec = client.get("/openapi.json").json()
    schema = spec["paths"]["/pilot/adoption-plan"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]

    assert schema["$ref"] == "#/components/schemas/PilotAdoptionPlan"


def test_innovation_differentiation_is_evidence_backed():
    r = client.get("/innovation/differentiation")
    assert r.status_code == 200
    body = r.json()
    InnovationDifferentiation.model_validate(body)
    assert body["mode"] == "evidenceBackedDifferentiation"
    names = " ".join(capability["name"] for capability in body["capabilities"])
    assert "Adversarial verifier" in names
    assert "Mule-network" in names
    assert "goAML" in names
    proof = {endpoint for capability in body["capabilities"] for endpoint in capability["proofEndpoints"]}
    assert "/alerts/HERO-002/defense-case" in proof
    assert "/governance/validation-dossier" in proof
    assert any("Not novelty by LLM usage alone" in claim for claim in body["nonClaims"])


def test_innovation_differentiation_is_openapi_typed():
    spec = client.get("/openapi.json").json()
    schema = spec["paths"]["/innovation/differentiation"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]

    assert schema["$ref"] == "#/components/schemas/InnovationDifferentiation"


def test_finals_qna_defense_maps_objections_to_evidence():
    r = client.get("/finals/qna-defense")
    assert r.status_code == 200
    body = r.json()
    FinalsQADefensePacket.model_validate(body)
    assert body["mode"] == "judgeDefense"
    objections = " ".join(answer["objection"] for answer in body["answers"])
    assert "Problem relevance" in objections
    assert "Auto-clear safety" in objections
    assert "Innovation" in objections
    assert "Procurement" in objections
    answers_text = " ".join(
        f"{answer['shortAnswer']} {answer['demoAction']}" for answer in body["answers"]
    )
    assert "pilot economics" in answers_text
    assert "not a production claim" in answers_text
    evidence = {endpoint for answer in body["answers"] for endpoint in answer["evidenceEndpoints"]}
    assert "/metrics" in evidence
    assert "/operations/impact" in evidence
    assert "/architecture/technical" in evidence
    assert "/production/trust-plan" in evidence
    assert "/innovation/differentiation" in evidence
    assert "/readiness/summary" in evidence
    assert all(answer["demoAction"] for answer in body["answers"])
    assert any("Do not" in answer["trapToAvoid"] for answer in body["answers"])


def test_finals_qna_defense_is_openapi_typed():
    spec = client.get("/openapi.json").json()
    schema = spec["paths"]["/finals/qna-defense"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]

    assert schema["$ref"] == "#/components/schemas/FinalsQADefensePacket"


def test_finals_demo_script_maps_presentation_path_to_evidence():
    r = client.get("/finals/demo-script")
    assert r.status_code == 200
    body = r.json()
    FinalsDemoScript.model_validate(body)
    assert body["mode"] == "finalsDemo"
    assert body["totalMinutes"] <= 8
    step_text = " ".join(step["title"] + " " + step["judgeTakeaway"] for step in body["steps"])
    assert "operational" in step_text.lower()
    assert "architecture" in step_text.lower()
    endpoints = {endpoint for step in body["steps"] for endpoint in step["evidenceEndpoints"]}
    assert "/operations/impact" in endpoints
    assert "/architecture/technical" in endpoints
    assert "/alerts/HERO-002/defense-case" in endpoints
    assert "/readiness/summary" in endpoints
    assert all(step["fallback"] for step in body["steps"])
    assert any("precomputed" in move.lower() for move in body["fallbackMoves"])
    assert any("autonomous STR" in claim for claim in body["nonClaims"])


def test_validation_dossier_packages_metrics_thresholds_and_release_gates():
    metrics = client.get("/metrics").json()
    r = client.get("/governance/validation-dossier")
    assert r.status_code == 200
    body = r.json()
    ValidationDossier.model_validate(body)
    assert body["dataset"] == "SAML-D held-out report-enriched slice"
    assert body["n"] == metrics["totalAlerts"]
    assert body["recall"] == metrics["recall"]
    assert body["autoClearLeakageRate"] == metrics["autoClearLeakageRate"]
    assert body["thresholds"]["autoClear"] == main.config.AUTO_CLEAR_THRESHOLD
    assert body["productionState"] == "shadowOnly"
    assert "catches zero reportable cases" in body["baselineExplanation"]
    assert any("Historical replay" in gate for gate in body["releaseGates"])
    assert any("No auto-filing" in action for action in body["prohibitedActions"])


def test_validation_dossier_is_openapi_typed():
    spec = client.get("/openapi.json").json()
    schema = spec["paths"]["/governance/validation-dossier"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]

    assert schema["$ref"] == "#/components/schemas/ValidationDossier"


def test_readiness_summary_validates_finals_contracts():
    r = client.get("/readiness/summary")
    assert r.status_code == 200
    body = r.json()
    ReadinessSummary.model_validate(body)
    assert body["status"] == "pass"
    endpoints = {check["endpoint"]: check for check in body["checks"]}
    for endpoint in (
        "/metrics",
        "/governance",
        "/security/access-control",
        "/governance/change-requests",
        "/qa/outcomes",
        "/queue/briefing",
        "/alerts/HERO-002/defense-case",
        "/alerts/HERO-002/case-handoff",
        "/operations/impact",
        "/architecture/technical",
        "/integration/contract",
        "/production/trust-plan",
        "/pilot/adoption-plan",
        "/innovation/differentiation",
        "/finals/demo-script",
        "/finals/qna-defense",
        "/governance/validation-dossier",
        "/finals/evidence-bundle",
    ):
        assert endpoints[endpoint]["ok"] is True
        assert endpoints[endpoint]["detail"] == "ok"


def test_operational_impact_quantifies_shift_workload():
    r = client.get("/operations/impact")
    assert r.status_code == 200
    body = r.json()
    OperationalImpact.model_validate(body)
    assert body["mode"] == "shiftImpact"
    assert body["processedAlerts"] == body["autoClearedAlerts"] + body["humanReviewAlerts"]
    assert body["minutesReturned"] > 0
    assert body["analystHoursReturned"] > 0
    assert 0 <= body["queueReductionRate"] <= 1
    assert "not a production ROI claim" in body["caveat"]


def test_technical_architecture_exposes_end_to_end_flow():
    r = client.get("/architecture/technical")
    assert r.status_code == 200
    body = r.json()
    TechnicalArchitecture.model_validate(body)
    assert body["mode"] == "technicalArchitecture"
    component_ids = {component["id"] for component in body["components"]}
    assert {"bank-monitoring", "api-store", "queue-agent", "triage-agents", "control-plane", "analyst-ui"} <= component_ids
    assert len(body["flows"]) >= 5
    assert any("/readiness/summary" in component["proofEndpoints"] for component in body["components"])
    assert any("schema" in flow["control"].lower() for flow in body["flows"])


def test_readiness_summary_is_openapi_typed():
    spec = client.get("/openapi.json").json()
    schema = spec["paths"]["/readiness/summary"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]

    assert schema["$ref"] == "#/components/schemas/ReadinessSummary"


def test_finals_evidence_bundle_packages_judge_contracts():
    r = client.get("/finals/evidence-bundle")
    assert r.status_code == 200
    body = r.json()
    FinalsEvidenceBundle.model_validate(body)
    assert body["readiness"]["status"] == "pass"
    assert body["metrics"]["totalAlerts"] == client.get("/metrics").json()["totalAlerts"]
    assert body["accessControl"]["mode"] == "actorRoleHeaders"
    assert body["governanceChangeControl"]["mode"] == "modelRiskChangeControl"
    assert body["qaOutcomeSummary"]["reviewed"] == 0
    assert body["operationalImpact"]["mode"] == "shiftImpact"
    assert body["technicalArchitecture"]["mode"] == "technicalArchitecture"
    assert body["validationDossier"]["productionState"] == "shadowOnly"
    assert body["productionTrustPlan"]["mode"] == "productionTrustPlan"
    assert body["integrationContract"]["mode"] == "shadowFirst"
    assert body["pilotAdoptionPlan"]["mode"] == "bankPilot"
    assert body["innovationDifferentiation"]["mode"] == "evidenceBackedDifferentiation"
    assert body["demoScript"]["mode"] == "finalsDemo"
    assert body["qnaDefense"]["mode"] == "judgeDefense"
    assert body["heroDefenseCase"]["alertId"] == "HERO-002"
    assert body["heroCaseHandoff"]["alertId"] == "HERO-002"
    assert body["heroDecisionTrace"]["alertId"] == "HERO-002"
    assert body["heroCopilotLedger"]["alertId"] == "HERO-002"
    backed = {endpoint for claim in body["claims"] for endpoint in claim["backedBy"]}
    assert "/metrics" in backed
    assert "/operations/impact" in backed
    assert "/architecture/technical" in backed
    assert "/production/trust-plan" in backed
    assert "/security/access-control" in backed
    assert "/governance/change-requests" in backed
    assert "/qa/outcomes" in backed
    assert "/readiness/summary" in backed
    assert "/pilot/adoption-plan" in backed
    assert "/innovation/differentiation" in backed
    assert "/finals/demo-script" in backed
    assert "/finals/qna-defense" in backed
    assert "/alerts/HERO-002/defense-case" in backed
    assert "/alerts/HERO-002/case-handoff" in backed
    assert "/alerts/HERO-002/decision-trace" in backed
    assert "/alerts/HERO-002/copilot-runs/precomputed-current/ledger" in backed
    claims_text = " ".join(f"{claim['claim']} {claim.get('caveat') or ''}" for claim in body["claims"])
    assert "Pilot economics" in claims_text
    assert "not a production claim" in claims_text


def test_finals_evidence_bundle_is_openapi_typed():
    spec = client.get("/openapi.json").json()
    schema = spec["paths"]["/finals/evidence-bundle"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]

    assert schema["$ref"] == "#/components/schemas/FinalsEvidenceBundle"


def test_borderline_dismiss_flag_on_alerts():
    d17 = client.get("/alerts/SD-00017").json()  # dismiss, conf 1.0, agreed — clear of the review line
    d9 = client.get("/alerts/SD-00009").json()   # dismiss, conf 0.75, near the review threshold (debated)
    assert d17["borderlineDismiss"] is False
    assert d9["borderlineDismiss"] is True


# --- GET /health ---

def test_health_reports_readiness():
    r = client.get("/health")
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "ok"
    assert d["alertsLoaded"] == main.store.count_alerts()
    assert d["transactionsLoaded"] == main.store.count_transactions()
    assert isinstance(d["llmKeyPresent"], bool)  # the pre-demo "is the live path wired" signal
    assert d["model"]
    assert d["provider"]  # active LLM provider label (Slice B on-prem swap): "... (cloud)" | "on-prem ..."


# --- GET /alerts ---

def test_get_alerts_returns_full_queue_camelcase_without_transactions():
    r = client.get("/alerts")
    assert r.status_code == 200
    data = r.json()
    assert len(data) > 0  # the precomputed queue is non-empty
    assert len(data) == main.store.count_alerts()  # returns the whole loaded queue, however many
    for item in data:
        assert "alertId" in item and "alert_id" not in item  # camelCase only
        assert item["transactions"] is None  # queue omits embedded transactions
        Alert.model_validate(item)


def test_get_alerts_filters_by_status():
    r = client.get("/alerts", params={"status": "pending"})
    assert r.status_code == 200
    assert all(a["status"] == "pending" for a in r.json())


def test_get_alerts_filters_by_routing():
    # the Queue Agent's lanes (ADR-0010): the needsReview inbox vs the auto-cleared surface
    r = client.get("/alerts", params={"routing": "autoCleared"})
    assert r.status_code == 200
    data = r.json()
    assert data and all(a["routing"] == "autoCleared" for a in data)


# --- GET /alerts/{id} ---

def test_get_alert_detail_embeds_transactions_and_triage():
    r = client.get("/alerts/HERO-002")
    assert r.status_code == 200
    d = r.json()
    assert d["alertId"] == "HERO-002"
    assert d["transactions"] and d["transactions"][0]["transactionId"]
    assert d["triage"]["recommendation"] in {"escalate", "dismiss"}
    Alert.model_validate(d)


def test_get_unknown_alert_returns_error_shaped_404():
    r = client.get("/alerts/NOPE")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ALERT_NOT_FOUND"
    assert "NOPE" in r.json()["error"]["message"]


# --- GET /typologies/{code}/handbook (live DeepSeek RAG) ---

def test_typology_handbook_generates_kb_cited_checks(make_client):
    # retrieval is real (BM25 over the KB chunks); the model is faked -> no tokens
    fake = make_client([json.dumps({"whatToCheck": [
        {"check": "Confirm the cash deposits cluster just below RM25,000.", "source": 1},
    ]})])
    app.dependency_overrides[get_llm_client] = lambda: fake
    r = client.get("/typologies/ST-01/handbook")
    assert r.status_code == 200
    body = r.json()
    assert body["typologyCode"] == "ST-01"
    assert body["whatToCheck"][0]["check"].startswith("Confirm")
    assert body["whatToCheck"][0]["source"]  # cited to a real KB source + page


def test_typology_handbook_falls_back_to_curated_checks_on_failure(raising_client):
    app.dependency_overrides[get_llm_client] = lambda: raising_client
    r = client.get("/typologies/PT-01/handbook")
    assert r.status_code == 200  # never 500 on camera — falls back to the card's curated checks
    assert r.json()["typologyCode"] == "PT-01"
    assert r.json()["whatToCheck"]  # the curated whatToCheck bullets


def test_typology_handbook_unknown_code_returns_error_shaped_404():
    r = client.get("/typologies/ZZ-99/handbook")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "TYPOLOGY_NOT_FOUND"


# --- POST /alerts/{id}/decision ---

def test_decision_approve_sets_status_approved():
    r = client.post("/alerts/HERO-002/decision", json={"action": "approve", "finalDisposition": "escalate"})
    assert r.status_code == 200
    assert r.json()["status"] == "approved"
    assert client.get("/alerts/HERO-002").json()["status"] == "approved"  # persists in session


def test_decision_override_to_dismiss_nulls_str_draft():
    r = client.post(
        "/alerts/HERO-003/decision",
        json={"action": "override", "finalDisposition": "dismiss", "note": "Analyst ruled out suspicion."},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "overridden"
    assert body["triage"]["strDraft"] is None  # overriding an escalate to dismiss drops the STR


def test_decision_on_unknown_alert_returns_error_shaped_404():
    r = client.post("/alerts/NOPE/decision", json={"action": "approve", "finalDisposition": "dismiss"})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ALERT_NOT_FOUND"


def test_invalid_request_body_returns_error_shaped_422():
    # Bad enum value: the error contract must hold for validation failures too,
    # not leak FastAPI's default {"detail": [...]} shape.
    r = client.post("/alerts/HERO-002/decision", json={"action": "nope", "finalDisposition": "escalate"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
    assert r.json()["error"]["message"]


# --- POST /alerts/{id}/triage (live) ---

def test_live_triage_returns_fresh_result_without_persisting(make_client):
    card_indicator = "Inbound credit followed by outbound debit of a similar amount within a short window (minutes to a few days)"
    fake = make_client([
        json.dumps({"matchedTypologyCode": "PT-01", "firedIndicators": [card_indicator],
                    "citedTransactionIds": ["DT-1001"], "recommendation": "escalate",
                    "claims": [{"claim": "LIVE-RUN-MARKER", "citedTransactionIds": [], "firedIndicators": []}]}),
        json.dumps({"agreesWithRecommendation": True, "note": "meets test"}),
        json.dumps({"activitySummary": "live summary", "groundsForSuspicion": ["x"]}),
    ])
    app.dependency_overrides[get_llm_client] = lambda: fake

    before = client.get("/alerts/HERO-002").json()["triage"]
    r = client.post("/alerts/HERO-002/triage")
    assert r.status_code == 200
    fresh = r.json()
    TriageResult.model_validate(fresh)
    assert fresh["claims"][0]["text"] == "LIVE-RUN-MARKER"
    # the stored/precomputed triage is untouched (demo stays deterministic, ADR-0003)
    assert client.get("/alerts/HERO-002").json()["triage"] == before


def test_live_triage_falls_back_to_precomputed_on_provider_failure(raising_client):
    app.dependency_overrides[get_llm_client] = lambda: raising_client
    precomputed = client.get("/alerts/HERO-002").json()["triage"]
    r = client.post("/alerts/HERO-002/triage")
    assert r.status_code == 200  # demo resilience (ADR-0003): never 500 on camera
    assert r.json() == precomputed


def test_live_triage_unknown_alert_returns_error_shaped_404():
    r = client.post("/alerts/NOPE/triage")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ALERT_NOT_FOUND"


# --- GET /alerts/{id}/triage/stream (live SSE 'thinking' view) ---

def test_live_triage_stream_emits_stage_events_then_result(make_client):
    card_indicator = "Inbound credit followed by outbound debit of a similar amount within a short window (minutes to a few days)"
    fake = make_client([
        json.dumps({"matchedTypologyCode": "PT-01", "firedIndicators": [card_indicator],
                    "citedTransactionIds": ["DT-1001"], "recommendation": "escalate",
                    "claims": [{"claim": "STREAM-MARKER", "citedTransactionIds": [], "firedIndicators": []}]}),
        json.dumps({"agreesWithRecommendation": True, "note": "meets test"}),
        json.dumps({"activitySummary": "s", "groundsForSuspicion": ["x"]}),
    ])
    app.dependency_overrides[get_llm_client] = lambda: fake

    before = client.get("/alerts/HERO-002").json()["triage"]
    r = client.get("/alerts/HERO-002/triage/stream")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")

    body = r.text
    # an SSE frame per pipeline stage, in order, plus indicators and the final result
    for stage in ("retrieve", "triage", "verifier", "confidence", "draft"):
        assert f'"id": "{stage}"' in body
    assert '"type": "indicator"' in body
    assert '"type": "result"' in body
    assert "STREAM-MARKER" in body
    # the precomputed demo source is untouched (ADR-0003)
    assert client.get("/alerts/HERO-002").json()["triage"] == before


# --- GET /alerts/{id}/str.xml (goAML export) ---

def _decide(alert_id, action, disposition):
    payload = {"action": action, "finalDisposition": disposition}
    if action == "override":
        payload["note"] = "Test analyst reason for overriding the stored AI recommendation."
    return client.post(f"/alerts/{alert_id}/decision", json=payload)


def test_export_blocked_until_adjudicated():
    # No decision yet: nothing can be filed (no sign-off).
    r = client.get("/alerts/HERO-002/str.xml")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "STR_NOT_ADJUDICATED"


def test_export_after_approve_escalate_returns_schema_valid_goaml():
    _decide("HERO-002", "approve", "escalate")
    r = client.get("/alerts/HERO-002/str.xml")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/xml")
    root = etree.fromstring(r.content)
    assert root.tag == "report" and root.findtext("report_code") == "STR"
    assert goaml._schema().validate(root)  # the wire bytes really validate


def test_escalate_signoff_can_file():
    # Any legal human sign-off to escalate opens the filing gate.
    client.post("/alerts/HERO-002/decision", json=_decision_payload_for_final("HERO-002", "escalate"))
    r = client.get("/alerts/HERO-002/str.xml")
    assert r.status_code == 200
    assert etree.fromstring(r.content).findtext("report_code") == "STR"


def test_export_blocked_when_dismissed():
    client.post("/alerts/HERO-002/decision", json=_decision_payload_for_final("HERO-002", "dismiss"))
    r = client.get("/alerts/HERO-002/str.xml")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "STR_DISMISSED"


def test_change_of_mind_to_dismiss_revokes_export():
    # Gate is recomputed live from the current decision, never cached.
    client.post("/alerts/HERO-002/decision", json=_decision_payload_for_final("HERO-002", "escalate"))
    assert client.get("/alerts/HERO-002/str.xml").status_code == 200
    client.post("/alerts/HERO-002/decision", json=_decision_payload_for_final("HERO-002", "dismiss"))
    r = client.get("/alerts/HERO-002/str.xml")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "STR_DISMISSED"


def test_export_unknown_alert_returns_error_shaped_404():
    r = client.get("/alerts/NOPE/str.xml")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ALERT_NOT_FOUND"


# --- POST /alerts/{id}/str/submit (goAML filing acknowledgement) ---

def test_submit_files_an_escalated_str_and_returns_an_accepted_ack():
    client.post("/alerts/HERO-002/decision", json=_decision_payload_for_final("HERO-002", "escalate"))
    r = client.post("/alerts/HERO-002/str/submit")
    assert r.status_code == 200
    ack = r.json()
    assert ack["status"] == "accepted"
    assert ack["alertId"] == "HERO-002"
    assert ack["submissionRef"].startswith("MYFIU-2026-")


def test_submit_is_gated_like_export():
    assert client.post("/alerts/HERO-002/str/submit").json()["error"]["code"] == "STR_NOT_ADJUDICATED"
    client.post("/alerts/HERO-002/decision", json=_decision_payload_for_final("HERO-002", "dismiss"))
    assert client.post("/alerts/HERO-002/str/submit").json()["error"]["code"] == "STR_DISMISSED"


def test_submission_appends_a_submission_event_to_the_audit_trail():
    client.post("/alerts/HERO-002/decision", json=_decision_payload_for_final("HERO-002", "escalate"))
    ack = client.post("/alerts/HERO-002/str/submit").json()
    entry = next(e for e in client.get("/audit").json() if e["event"] == "submission")
    assert entry["alertId"] == "HERO-002"
    assert entry["submissionRef"] == ack["submissionRef"]


# --- GET /audit (decision + submission audit trail) ---

def test_audit_trail_opens_seeded_with_autoclear_events():
    # the Queue Agent's overnight run populates /audit BEFORE any human acts (ADR-0010),
    # so the trail isn't empty on a cold demo open.
    autoclears = [e for e in client.get("/audit").json() if e["event"] == "autoClear"]
    assert autoclears  # seeded, not empty
    assert all(e["aiRecommendation"] == "dismiss" and e["verifierStatus"] == "agreed"
               for e in autoclears)

def test_decision_appends_audit_entry_pairing_ai_call_with_human_disposition():
    # The audit trail's whole point: record what the AI recommended next to what
    # the human decided, so an override is accountable after the fact.
    triage = client.get("/alerts/HERO-002").json()["triage"]
    client.post("/alerts/HERO-002/decision", json=_decision_payload_for_final("HERO-002", "escalate"))

    log = client.get("/audit").json()
    entry = next(e for e in log if e["alertId"] == "HERO-002" and e["event"] == "decision")
    assert entry["aiRecommendation"] == triage["recommendation"]
    assert entry["finalDisposition"] == "escalate"
    assert entry["confidence"] == triage["confidence"]
    assert entry["verifierStatus"] == triage["verifier"]["status"]
    assert entry["action"] == "approve"


def test_override_records_the_analyst_note_in_the_audit_trail():
    client.post("/alerts/HERO-002/decision",
                json={"action": "override", "finalDisposition": "dismiss", "note": "Confirmed legitimate salary run with HR."})
    entry = next(e for e in client.get("/audit").json() if e["alertId"] == "HERO-002")
    assert entry["action"] == "override"
    assert entry["note"] == "Confirmed legitimate salary run with HR."


def test_approve_without_a_note_leaves_note_null():
    client.post("/alerts/HERO-002/decision", json=_decision_payload_for_final("HERO-002", "escalate"))
    entry = next(e for e in client.get("/audit").json() if e["alertId"] == "HERO-002")
    assert entry["note"] is None


def test_audit_trail_is_append_only_across_a_change_of_mind():
    # A reversed decision must not erase the first: both are kept, newest first.
    client.post("/alerts/HERO-002/decision", json=_decision_payload_for_final("HERO-002", "escalate"))
    client.post("/alerts/HERO-002/decision", json=_decision_payload_for_final("HERO-002", "dismiss"))
    entries = [e for e in client.get("/audit").json() if e["alertId"] == "HERO-002" and e["event"] == "decision"]
    assert len(entries) == 2
    assert entries[0]["finalDisposition"] == "dismiss"   # newest first
    assert entries[1]["finalDisposition"] == "escalate"


def test_reset_restores_the_audit_trail_to_the_autoclear_seed():
    # reset drops session decisions/submissions but restores the Queue Agent's seed (autoClear
    # events, ADR-0010, plus debateResolved events, ADR-0011), so the trail returns to its
    # cold-open state, not empty.
    client.post("/alerts/HERO-002/decision", json=_decision_payload_for_final("HERO-002", "escalate"))
    assert any(e["event"] == "decision" for e in client.get("/audit").json())
    client.post("/reset")
    log = client.get("/audit").json()
    # only the seed remains — no session decision/submission events
    assert log and all(e["event"] in ("autoClear", "debateResolved") for e in log)


# --- GET /audit/summary (AI–analyst agreement, session, decision-scoped) ---

def test_audit_summary_starts_with_no_decisions_and_null_agreement():
    # the seed has autoClear/debateResolved events but no human decisions yet —
    # agreementRate must be null, never a misleading 100%.
    s = client.get("/audit/summary").json()
    assert s == {"decisions": 0, "approvals": 0, "overrides": 0, "agreementRate": None}


def test_audit_summary_counts_approvals_and_overrides():
    client.post("/alerts/HERO-002/decision", json=_decision_payload_for_final("HERO-002", "escalate"))
    client.post("/alerts/HERO-003/decision", json=_decision_payload_for_final("HERO-003", "dismiss"))
    client.post("/alerts/HERO-001/decision", json=_decision_payload_for_final("HERO-001", "escalate"))
    s = client.get("/audit/summary").json()
    assert s["decisions"] == 3
    assert s["approvals"] == 2
    assert s["overrides"] == 1
    assert s["agreementRate"] == round(2 / 3, 4)


def test_audit_summary_ignores_autoclear_and_submission_events():
    # only human approve/override decisions count toward agreement — the seeded autoClear /
    # debateResolved events and a goAML submission must not inflate the denominator.
    client.post("/alerts/HERO-002/decision", json=_decision_payload_for_final("HERO-002", "escalate"))
    client.post("/alerts/HERO-002/str/submit")  # appends a submission event
    s = client.get("/audit/summary").json()
    assert s["decisions"] == 1
    assert s["approvals"] == 1
    assert s["agreementRate"] == 1.0


# --- POST /reset ---

def test_reset_restores_status_and_clears_decisions():
    client.post("/alerts/HERO-002/decision", json=_decision_payload_for_final("HERO-002", "escalate"))
    r = client.post("/reset")
    assert r.status_code == 200 and r.json()["status"] == "success"
    assert client.get("/alerts/HERO-002").json()["status"] == "pending"  # back to source state


# --- GET /queue/briefing (Queue Agent shift briefing) ---

def test_queue_briefing_served_in_contract_shape():
    r = client.get("/queue/briefing")
    assert r.status_code == 200
    b = r.json()
    assert {"processed", "autoCleared", "needsReview", "escalations", "flagged", "blockedReasons", "nextActions", "summary"} <= b.keys()
    # The overnight briefing covers the triaged demo queue (results.json), a subset of the served
    # store — which also carries the mule-network hero seed alerts (ADR-0009/0015). So `processed` is
    # internally consistent and does not exceed the full store count, rather than equalling it.
    assert b["processed"] == b["autoCleared"] + b["needsReview"]
    assert 0 < b["processed"] <= main.store.count_alerts()
    assert sum(reason["count"] for reason in b["blockedReasons"]) == b["needsReview"]
    assert b["nextActions"]
    assert b["nextActions"][0]["lane"] in {"needsReview", "qaSample", "autoCleared"}


def test_queue_briefing_404_error_shaped_when_absent(monkeypatch):
    monkeypatch.setattr(main, "_BRIEFING", main._DATA / "definitely_absent_briefing.json")
    r = client.get("/queue/briefing")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "BRIEFING_NOT_READY"


# --- GET /metrics ---

def test_metrics_served_in_contract_shape_when_present():
    r = client.get("/metrics")
    assert r.status_code == 200
    body = r.json()
    assert {"totalAlerts", "accuracyVsLabels", "falsePositiveReduction"} <= body.keys()


def test_metrics_404_error_shaped_when_absent(monkeypatch):
    monkeypatch.setattr(main, "_METRICS", main._DATA / "definitely_absent_metrics.json")
    r = client.get("/metrics")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "METRICS_NOT_READY"


# --- GET /evaluation (held-out set behind the accuracy number) ---

def test_evaluation_serves_the_held_out_set_with_labels():
    r = client.get("/evaluation")
    assert r.status_code == 200
    body = r.json()
    assert body["n"] == len(body["alerts"])
    a = body["alerts"][0]
    assert {"alertId", "label", "typology", "txnCount"} <= a.keys()
    assert a["label"] in ("escalate", "dismiss")  # ground-truth, not an AI call (that is path (a))


# --- unexpected errors keep the contract shape (500) ---

def test_unexpected_error_returns_error_shaped_500(monkeypatch):
    # Force an unhandled error inside an endpoint; the catch-all must still emit
    # {"error": {"code", "message"}}, not FastAPI's default 500 page.
    def boom(*a, **k):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(main.Metrics, "model_validate", boom)
    safe = TestClient(app, raise_server_exceptions=False)
    r = safe.get("/metrics")
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "INTERNAL_ERROR"
