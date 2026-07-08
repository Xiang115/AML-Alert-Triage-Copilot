"""Network Revocation (ADR-0021): the Mule Network polices the learned suppression.

The exploitation defense for closed-loop suppression. A cleared counterparty that the Label-Blind
Walk finds sitting as a **Consolidation Account** (the `hub` role of an assembled Mule Network) can no
longer be trusted to auto-clear look-alikes — so its suppression is **revoked** and the alert routes
to a human. You cannot route laundering volume through a cleared corridor without forming the very
consolidation star that revokes the clearance.

Deterministic and token-free. **Illustrative on the frozen IBM AMLworld networks (ADR-0015)** — the
hubs are real assembled structure, but no aggregate metric is claimed; SAML-D is too edge-sparse for a
measured revocation rate (same honesty split as the Mule Network itself)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_NETWORKS = Path(__file__).resolve().parent.parent / "data" / "networks.json"


@lru_cache(maxsize=1)
def _hub_index() -> dict[str, dict]:
    """Map each Consolidation Account (hub `accountId`, normalized) -> its network's seed id +
    holder name. Built once from networks.json; a missing file yields an empty index (no revocation)."""
    if not _NETWORKS.exists():
        return {}
    nets = json.loads(_NETWORKS.read_text(encoding="utf-8"))
    networks = nets.values() if isinstance(nets, dict) else nets
    index: dict[str, dict] = {}
    for net in networks:
        for node in net.get("nodes", []):
            if node.get("role") == "hub" and node.get("accountId"):
                index[str(node["accountId"]).strip().lower()] = {
                    "networkId": net.get("seedAlertId"),
                    "hubHolder": node.get("holderName"),
                }
    return index


def revoked_by_network(counterparty_account: str | None) -> dict | None:
    """The network a cleared counterparty is a Consolidation Account of, else None. Returns
    `{"networkId", "hubHolder"}` — enough to name the network in the revocation rationale."""
    if not counterparty_account:
        return None
    return _hub_index().get(counterparty_account.strip().lower())
