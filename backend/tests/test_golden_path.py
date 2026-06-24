"""End-to-end smoke test: the 5-beat demo golden path, through the public API.

Walks the exact flow the filmed demo shows (CLAUDE.md > Demo golden path) against the
served precomputed data via the FastAPI TestClient — no tokens. If any beat's contract
breaks (a renamed field, a dropped STR, a broken goAML gate), the matching beat fails
with a labelled message, before it ever reaches the screen.

conftest._reset_state (autouse) isolates the in-memory mutations Beat 4 makes.
"""

from fastapi.testclient import TestClient
from lxml import etree

from main import app, get_llm_client
from schemas import Alert, Metrics

client = TestClient(app)

_HERO_FLAGGED = "HERO-001"   # verifier flags the call -> human review (the wow)
_HERO_CLEAN = "HERO-002"     # clean agreed escalate -> approve and file the STR


def test_beat1_queue_surfaces_the_worklist():
    """Beat 1 — the analyst opens a queue of alerts to triage (mostly noise)."""
    r = client.get("/alerts")
    assert r.status_code == 200
    queue = r.json()
    assert len(queue) > 0
    assert any(a["routing"] == "needsReview" for a in queue)  # the Queue Agent left a worklist
    for a in queue:
        assert a["transactions"] is None  # queue omits embedded txns (payload contract)
        Alert.model_validate(a)


def test_beat2_detail_gives_a_grounded_call():
    """Beat 2 — open an alert: recommendation + confidence + typology + cited txns,
    every citation grounded in the account's real ledger."""
    r = client.get(f"/alerts/{_HERO_CLEAN}")
    assert r.status_code == 200
    d = r.json()
    t = d["triage"]
    assert d["transactions"], "detail must embed the transactions the call cites"
    assert t["recommendation"] in {"escalate", "dismiss"}
    assert 0.0 <= t["confidence"] <= 1.0
    assert t["matchedTypology"]["code"]
    cited = set(t["citedTransactionIds"])
    ledger = {tx["transactionId"] for tx in d["transactions"]}
    assert cited and cited <= ledger, "every cited txn must exist in the ledger (citation grounding)"


def test_beat2_live_triage_is_resilient_on_camera(raising_client):
    """Beat 2 (Q&A) — the 'run it live' button never breaks the demo: a provider outage
    falls back to the precomputed call without mutating the demo source (ADR-0003)."""
    app.dependency_overrides[get_llm_client] = lambda: raising_client
    precomputed = client.get(f"/alerts/{_HERO_CLEAN}").json()["triage"]
    r = client.post(f"/alerts/{_HERO_CLEAN}/triage")
    assert r.status_code == 200
    assert r.json() == precomputed


def test_beat3_verifier_catches_the_wrong_call():
    """Beat 3 — the wow: the verifier flags HERO-001, capping confidence below the
    review threshold and opening an adversarial debate (ADR-0007/0011)."""
    t = client.get(f"/alerts/{_HERO_FLAGGED}").json()["triage"]
    assert t["verifier"]["status"] == "flagged"
    assert t["confidence"] < 0.6  # REVIEW_THRESHOLD — flag forces human review
    assert t["debate"] is not None  # challenge -> rebuttal -> re-verdict is recorded


def test_beat4_escalate_then_file_goaml():
    """Beat 4 — analyst approves the escalate; the approved STR exports as well-formed,
    XSD-validated goAML XML and files, returning an FIU acknowledgement. The filing gate
    is shut until sign-off."""
    assert client.get(f"/alerts/{_HERO_CLEAN}/str.xml").status_code == 409  # gate shut pre-signoff

    d = client.post(f"/alerts/{_HERO_CLEAN}/decision",
                    json={"action": "approve", "finalDisposition": "escalate"})
    assert d.status_code == 200 and d.json()["status"] == "approved"

    x = client.get(f"/alerts/{_HERO_CLEAN}/str.xml")
    assert x.status_code == 200
    etree.fromstring(x.content)  # parses -> well-formed XML (serializer also XSD-validated it)

    s = client.post(f"/alerts/{_HERO_CLEAN}/str/submit")
    assert s.status_code == 200 and s.json()["status"] == "accepted"

    trail = client.get("/audit").json()
    events = {e["event"] for e in trail if e["alertId"] == _HERO_CLEAN}
    assert {"decision", "submission"} <= events  # both actions are on the accountability trail


def test_beat5_metric_slide_is_served():
    """Beat 5 — the metric slide reads accuracy + workload numbers from /metrics."""
    r = client.get("/metrics")
    assert r.status_code == 200
    Metrics.model_validate(r.json())  # conforms to the contract
