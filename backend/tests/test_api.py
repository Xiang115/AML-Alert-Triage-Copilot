from fastapi.testclient import TestClient

from main import app
from schemas import Alert

client = TestClient(app)


def test_get_alerts_returns_camelcase_queue():
    r = client.get("/alerts")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 3
    first = data[0]
    assert "alertId" in first and "riskScore" in first
    assert "alert_id" not in first  # camelCase only on the wire
    # queue items carry no embedded transactions (detail does)
    assert first["transactions"] is None
    # every item is contract-valid
    for item in data:
        Alert.model_validate(item)


def test_get_alerts_filters_by_status():
    r = client.get("/alerts", params={"status": "pending"})
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    assert all(a["status"] == "pending" for a in data)


def test_get_alert_detail():
    r = client.get("/alerts/ALERT-001")
    assert r.status_code == 200
    data = r.json()
    assert data["alertId"] == "ALERT-001"
    assert "account" in data
    assert "transactions" in data
    assert len(data["transactions"]) == 2
    assert data["triage"]["alertId"] == "ALERT-001"


def test_get_alert_detail_not_found():
    r = client.get("/alerts/NONEXISTENT")
    assert r.status_code == 404


def test_post_decision_approve():
    payload = {
        "action": "approve",
        "finalDisposition": "escalate",
        "editedStrDraft": None
    }
    r = client.post("/alerts/ALERT-001/decision", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "approved"


def test_post_decision_override():
    payload = {
        "action": "override",
        "finalDisposition": "dismiss",
        "editedStrDraft": None
    }
    r = client.post("/alerts/ALERT-002/decision", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "overridden"
    assert data["triage"]["strDraft"] is None


def test_get_metrics():
    r = client.get("/metrics")
    assert r.status_code == 200
    data = r.json()
    assert "totalAlerts" in data
    assert "accuracyVsLabels" in data
    assert "falsePositiveReduction" in data


def test_post_reset():
    r = client.post("/reset")
    assert r.status_code == 200
    assert r.json()["status"] == "success"


def test_post_triage_fallback(monkeypatch):
    # Mock run_triage to fail to test fallback recovery
    def mock_run_triage(alert):
        raise RuntimeError("Simulated LLM pipeline failure")
    
    import main
    monkeypatch.setattr(main, "run_triage", mock_run_triage)
    
    r = client.post("/alerts/ALERT-001/triage")
    assert r.status_code == 200
    data = r.json()
    assert data["alertId"] == "ALERT-001"
    assert data["recommendation"] == "escalate"
    assert data["confidence"] == 0.86

