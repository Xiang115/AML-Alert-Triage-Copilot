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
