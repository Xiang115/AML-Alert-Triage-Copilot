"""FastAPI serving layer (Phase 7) — all contract endpoints, mocked (no tokens).

The live /triage endpoint injects a fake LLM client via the get_llm_client
dependency override, so the whole suite spends zero DeepSeek tokens.
"""

import copy
import json

import pytest
from fastapi.testclient import TestClient

import main
from main import app, get_llm_client
from schemas import Alert, TriageResult

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_state():
    """Endpoints mutate in-memory state (decisions flip status); isolate each test."""
    alerts = copy.deepcopy(main._ALERTS)
    decisions = copy.deepcopy(main._DECISIONS)
    yield
    main._ALERTS.clear()
    main._ALERTS.update(alerts)
    main._DECISIONS.clear()
    main._DECISIONS.update(decisions)
    app.dependency_overrides.clear()


# --- GET /alerts ---

def test_get_alerts_returns_full_queue_camelcase_without_transactions():
    r = client.get("/alerts")
    assert r.status_code == 200
    data = r.json()
    assert len(data) > 0  # the precomputed queue is non-empty
    assert len(data) == len(main._ALERTS)  # returns the whole loaded queue, however many
    for item in data:
        assert "alertId" in item and "alert_id" not in item  # camelCase only
        assert item["transactions"] is None  # queue omits embedded transactions
        Alert.model_validate(item)


def test_get_alerts_filters_by_status():
    r = client.get("/alerts", params={"status": "pending"})
    assert r.status_code == 200
    assert all(a["status"] == "pending" for a in r.json())


# --- GET /alerts/{id} ---

def test_get_alert_detail_embeds_transactions_and_triage():
    r = client.get("/alerts/DQ-001")
    assert r.status_code == 200
    d = r.json()
    assert d["alertId"] == "DQ-001"
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
    r = client.post("/alerts/DQ-001/decision", json={"action": "approve", "finalDisposition": "escalate"})
    assert r.status_code == 200
    assert r.json()["status"] == "approved"
    assert client.get("/alerts/DQ-001").json()["status"] == "approved"  # persists in session


def test_decision_override_to_dismiss_nulls_str_draft():
    r = client.post("/alerts/DQ-003/decision", json={"action": "override", "finalDisposition": "dismiss"})
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
    r = client.post("/alerts/DQ-001/decision", json={"action": "nope", "finalDisposition": "escalate"})
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

    before = client.get("/alerts/DQ-001").json()["triage"]
    r = client.post("/alerts/DQ-001/triage")
    assert r.status_code == 200
    fresh = r.json()
    TriageResult.model_validate(fresh)
    assert fresh["explanation"] == "LIVE-RUN-MARKER"
    # the stored/precomputed triage is untouched (demo stays deterministic, ADR-0003)
    assert client.get("/alerts/DQ-001").json()["triage"] == before


def test_live_triage_falls_back_to_precomputed_on_provider_failure(raising_client):
    app.dependency_overrides[get_llm_client] = lambda: raising_client
    precomputed = client.get("/alerts/DQ-001").json()["triage"]
    r = client.post("/alerts/DQ-001/triage")
    assert r.status_code == 200  # demo resilience (ADR-0003): never 500 on camera
    assert r.json() == precomputed


def test_live_triage_unknown_alert_returns_error_shaped_404():
    r = client.post("/alerts/NOPE/triage")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ALERT_NOT_FOUND"


# --- POST /reset ---

def test_reset_restores_status_and_clears_decisions():
    client.post("/alerts/DQ-001/decision", json={"action": "approve", "finalDisposition": "escalate"})
    r = client.post("/reset")
    assert r.status_code == 200 and r.json()["status"] == "success"
    assert client.get("/alerts/DQ-001").json()["status"] == "pending"  # back to source state


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
