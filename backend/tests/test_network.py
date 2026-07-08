"""Mule Network endpoint (ADR-0009/0015) — GET /alerts/{id}/network.

Serves the frozen, qualitative IBM AMLworld hero from networks.json. No LLM, no tokens.
"""

import pytest
from fastapi.testclient import TestClient

import main
from main import app
from schemas import MuleNetwork

client = TestClient(app)

SEED = "IBM-MULE-01"
_has_hero = SEED in main._NETWORKS_DATA
requires_hero = pytest.mark.skipif(not _has_hero, reason="networks.json not built (run data.ibm_network)")


def test_network_missing_alert_404_in_contract_shape():
    """Most alerts have no network — a miss exits in the { error: { code, message } } envelope."""
    r = client.get("/alerts/NO-SUCH-ALERT/network")
    assert r.status_code == 404
    body = r.json()
    assert body["error"]["code"] == "NETWORK_NOT_FOUND"
    assert "NO-SUCH-ALERT" in body["error"]["message"]


@requires_hero
def test_network_hero_serves_valid_camelcase_mule_network():
    r = client.get(f"/alerts/{SEED}/network")
    assert r.status_code == 200
    body = r.json()
    # Round-trips the wire contract (camelCase, no extra fields).
    net = MuleNetwork.model_validate(body)
    assert net.seed_alert_id == SEED
    assert net.typology.code == "FI-01"
    assert "fromAccountId" in body["edges"][0]  # camelCase on the wire


@requires_hero
def test_network_hero_has_the_story_roles():
    """The demo hero must carry exactly one hidden mule (the seed) and a cleared benign payer —
    the recall reveal + the discrimination, not guilt-by-association."""
    net = MuleNetwork.model_validate(client.get(f"/alerts/{SEED}/network").json())
    roles = [n.role for n in net.nodes]
    assert roles.count("hub") == 1
    hidden = [n for n in net.nodes if n.role == "hidden_mule"]
    assert len(hidden) == 1 and hidden[0].is_seed
    assert any(n.role == "benign_cleared" for n in net.nodes)
    # The hidden mule looks dismissible alone: laundering is a small fraction of its activity.
    hm = hidden[0]
    assert hm.total_legs and hm.laundering_legs is not None
    assert hm.laundering_legs / hm.total_legs < 0.2


@requires_hero
def test_network_carries_the_honesty_caption():
    """ADR-0015: the 'illustrative, measured numbers are SAML-D' caption rides on the payload so
    the UI cannot silently drop it."""
    net = MuleNetwork.model_validate(client.get(f"/alerts/{SEED}/network").json())
    assert "illustrative" in net.source.lower()
    assert "saml-d" in net.source.lower()
