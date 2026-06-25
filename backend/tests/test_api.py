"""FastAPI serving layer (Phase 7) — all contract endpoints, mocked (no tokens).

The live /triage endpoint injects a fake LLM client via the get_llm_client
dependency override, so the whole suite spends zero DeepSeek tokens.
"""

import json

from fastapi.testclient import TestClient
from lxml import etree

import goaml
import main
from main import app, get_llm_client
from schemas import Alert, TriageResult

# State isolation (_reset_state) and the ':memory:' DB live in conftest.py — autouse.
client = TestClient(app)


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


# --- POST /alerts/{id}/decision ---

def test_decision_approve_sets_status_approved():
    r = client.post("/alerts/HERO-002/decision", json={"action": "approve", "finalDisposition": "escalate"})
    assert r.status_code == 200
    assert r.json()["status"] == "approved"
    assert client.get("/alerts/HERO-002").json()["status"] == "approved"  # persists in session


def test_decision_override_to_dismiss_nulls_str_draft():
    r = client.post("/alerts/HERO-003/decision", json={"action": "override", "finalDisposition": "dismiss"})
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
                    "citedTransactionIds": ["DT-1001"], "recommendation": "escalate", "explanation": "LIVE-RUN-MARKER"}),
        json.dumps({"agreesWithRecommendation": True, "note": "meets test"}),
        json.dumps({"activitySummary": "live summary", "groundsForSuspicion": ["x"]}),
    ])
    app.dependency_overrides[get_llm_client] = lambda: fake

    before = client.get("/alerts/HERO-002").json()["triage"]
    r = client.post("/alerts/HERO-002/triage")
    assert r.status_code == 200
    fresh = r.json()
    TriageResult.model_validate(fresh)
    assert fresh["explanation"] == "LIVE-RUN-MARKER"
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
                    "citedTransactionIds": ["DT-1001"], "recommendation": "escalate", "explanation": "STREAM-MARKER"}),
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
    return client.post(f"/alerts/{alert_id}/decision", json={"action": action, "finalDisposition": disposition})


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


def test_override_to_escalate_can_file():
    # The beat-3 hero path: analyst overrides a call up to escalate -> must file.
    _decide("HERO-002", "override", "escalate")
    r = client.get("/alerts/HERO-002/str.xml")
    assert r.status_code == 200
    assert etree.fromstring(r.content).findtext("report_code") == "STR"


def test_export_blocked_when_dismissed():
    _decide("HERO-002", "approve", "dismiss")
    r = client.get("/alerts/HERO-002/str.xml")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "STR_DISMISSED"


def test_change_of_mind_to_dismiss_revokes_export():
    # Gate is recomputed live from the current decision, never cached.
    _decide("HERO-002", "approve", "escalate")
    assert client.get("/alerts/HERO-002/str.xml").status_code == 200
    _decide("HERO-002", "override", "dismiss")
    r = client.get("/alerts/HERO-002/str.xml")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "STR_DISMISSED"


def test_export_unknown_alert_returns_error_shaped_404():
    r = client.get("/alerts/NOPE/str.xml")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ALERT_NOT_FOUND"


# --- POST /alerts/{id}/str/submit (goAML filing acknowledgement) ---

def test_submit_files_an_escalated_str_and_returns_an_accepted_ack():
    _decide("HERO-002", "approve", "escalate")
    r = client.post("/alerts/HERO-002/str/submit")
    assert r.status_code == 200
    ack = r.json()
    assert ack["status"] == "accepted"
    assert ack["alertId"] == "HERO-002"
    assert ack["submissionRef"].startswith("MYFIU-2026-")


def test_submit_is_gated_like_export():
    assert client.post("/alerts/HERO-002/str/submit").json()["error"]["code"] == "STR_NOT_ADJUDICATED"
    _decide("HERO-002", "approve", "dismiss")
    assert client.post("/alerts/HERO-002/str/submit").json()["error"]["code"] == "STR_DISMISSED"


def test_submission_appends_a_submission_event_to_the_audit_trail():
    _decide("HERO-002", "approve", "escalate")
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
    _decide("HERO-002", "approve", "escalate")

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
    _decide("HERO-002", "approve", "escalate")
    entry = next(e for e in client.get("/audit").json() if e["alertId"] == "HERO-002")
    assert entry["note"] is None


def test_audit_trail_is_append_only_across_a_change_of_mind():
    # A reversed decision must not erase the first: both are kept, newest first.
    _decide("HERO-002", "approve", "escalate")
    _decide("HERO-002", "override", "dismiss")
    entries = [e for e in client.get("/audit").json() if e["alertId"] == "HERO-002" and e["event"] == "decision"]
    assert len(entries) == 2
    assert entries[0]["finalDisposition"] == "dismiss"   # newest first
    assert entries[1]["finalDisposition"] == "escalate"


def test_reset_restores_the_audit_trail_to_the_autoclear_seed():
    # reset drops session decisions/submissions but restores the Queue Agent's seed (autoClear
    # events, ADR-0010, plus debateResolved events, ADR-0011), so the trail returns to its
    # cold-open state, not empty.
    _decide("HERO-002", "approve", "escalate")
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
    _decide("HERO-002", "approve", "escalate")   # agree with the AI
    _decide("HERO-003", "override", "dismiss")    # disagree
    _decide("HERO-001", "approve", "escalate")   # agree
    s = client.get("/audit/summary").json()
    assert s["decisions"] == 3
    assert s["approvals"] == 2
    assert s["overrides"] == 1
    assert s["agreementRate"] == round(2 / 3, 4)


def test_audit_summary_ignores_autoclear_and_submission_events():
    # only human approve/override decisions count toward agreement — the seeded autoClear /
    # debateResolved events and a goAML submission must not inflate the denominator.
    _decide("HERO-002", "approve", "escalate")
    client.post("/alerts/HERO-002/str/submit")  # appends a submission event
    s = client.get("/audit/summary").json()
    assert s["decisions"] == 1
    assert s["approvals"] == 1
    assert s["agreementRate"] == 1.0


# --- POST /reset ---

def test_reset_restores_status_and_clears_decisions():
    client.post("/alerts/HERO-002/decision", json={"action": "approve", "finalDisposition": "escalate"})
    r = client.post("/reset")
    assert r.status_code == 200 and r.json()["status"] == "success"
    assert client.get("/alerts/HERO-002").json()["status"] == "pending"  # back to source state


# --- GET /queue/briefing (Queue Agent shift briefing) ---

def test_queue_briefing_served_in_contract_shape():
    r = client.get("/queue/briefing")
    assert r.status_code == 200
    b = r.json()
    assert {"processed", "autoCleared", "needsReview", "escalations", "flagged", "summary"} <= b.keys()
    assert b["processed"] == main.store.count_alerts()


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
