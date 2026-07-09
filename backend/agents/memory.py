"""Slice A — cross-customer self-learning suppression."""

from __future__ import annotations

from collections import Counter

import store
from agents.envelope import signature_from_transactions
from agents.triage import NO_MATCH_CODE


def _dominant_counterparty(alert: dict) -> str | None:
    """Prefer counterparties in cited transactions; fall back to the whole ledger."""
    txns = alert.get("transactions") or []
    cited = set(alert["triage"].get("citedTransactionIds") or [])
    pool = [txn for txn in txns if txn["transactionId"] in cited] or txns
    keys = [
        ((txn.get("counterpartyAccount") or txn.get("counterpartyName") or "").strip().lower())
        for txn in pool
    ]
    keys = [key for key in keys if key]
    if not keys:
        return None
    return Counter(keys).most_common(1)[0][0]


def envelope_benign_consistent(transactions: list[dict]) -> bool:
    """ADR-0021 gate 2 (serve-time envelope safety): a learned suppression may auto-clear an alert
    only if the alert's OWN ledger envelope carries no laundering structural tell — primarily the
    drain-to-~0 pass-through signature. So a launderer cannot reuse a cleared corridor without
    changing the very structure that got it cleared: a drain/pass-through look-alike is denied the
    auto-clear and routes to a human. Empty ledger -> not verifiable -> deny (conservative). Reuses
    the production `compute_activity_profile`, so the app and the eval harness cannot diverge on what
    the envelope is."""
    if not transactions:
        return False
    from activity_profile import compute_activity_profile

    profile = compute_activity_profile(transactions)
    return not profile["balanceSwept"]["sweptToNearZero"]


def signature(alert: dict) -> str | None:
    """Stable cross-customer BEHAVIORAL-ENVELOPE signature (ADR-0021, fork B): the SAME structural
    feature bucket the leakage frontier is measured over (agents.envelope), NOT counterparty identity
    (which recurs on ~0% of held-out SAML-D, so it could never auto-clear a real alert). The typology
    key is the model's matched-typology code; the other seven features are pure ledger structure.
    None on a NO_MATCH triage or an empty ledger."""
    code = alert["triage"]["matchedTypology"]["code"]
    if code == NO_MATCH_CODE:
        return None
    return signature_from_transactions(code, alert.get("transactions") or [])


def suppress(alert: dict) -> dict | None:
    """Return a suppression citing the original human clearance, or None when unmatched."""
    sig = signature(alert)
    if not sig:
        return None
    pattern = store.find_cleared_pattern(sig)
    if not pattern:
        return None

    # An alert is never auto-suppressed by the clearance it ITSELF taught: the source is the teacher,
    # not a future look-alike. This keeps the learned-patterns view from double-counting the teacher
    # as an alert its own pattern removed, and matches the full-population learning scan (which
    # already excludes the source when it counts affected future alerts).
    if pattern.get("sourceAlertId") and alert.get("alertId") == pattern["sourceAlertId"]:
        return None

    # The match key is the behavioral envelope; the counterparty is needed only for Network Revocation
    # (does the cleared corridor's counterparty look like a consolidation hub).
    counterparty = _dominant_counterparty(alert)
    code = alert["triage"]["matchedTypology"]["code"]
    base = {
        "matchedPatternId": sig,
        "sourceDecisionId": pattern["sourceDecisionId"],
        "sourceAlertId": pattern["sourceAlertId"],
        "signature": sig,
        "clearedCount": pattern["clearedCount"],
        "clearedAt": pattern["clearedAt"],
    }

    # Network Revocation (ADR-0021): the Mule Network polices the memory. If the cleared counterparty
    # is a Consolidation Account (hub) of an assembled network, the clearance can be exploited — so it
    # is REVOKED (never auto-clears; routing keeps it for a human). The network catches what the memory
    # would wrongly clear.
    from agents.network_revocation import revoked_by_network

    revocation = revoked_by_network(counterparty) if counterparty else None
    if revocation:
        return {
            **base,
            "status": "revoked",
            "revokedNetworkId": revocation["networkId"],
            "rationale": (
                f"Counterparty {counterparty} was cleared as benign on {pattern['clearedCount']} prior "
                f"alert(s), but the mule-network walk flags it as a consolidation hub "
                f"({revocation['hubHolder']}) in network {revocation['networkId']}. Suppression REVOKED "
                f"— routed to human review."
            ),
        }

    return {
        **base,
        "status": "suppressed",
        "rationale": (
            f"A benign look-alike with the same behavioral envelope (typology {code}, matching "
            f"amount band, flow direction, and ledger structure) was cleared on "
            f"{pattern['clearedCount']} prior alert(s). Suppression cites decision "
            f"{pattern['sourceDecisionId']}."
        ),
    }
