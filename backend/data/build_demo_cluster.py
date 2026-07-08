"""Build tool (Slice A demo, beat 3): a 3-alert suppression CLUSTER that all share one benign
behavioral envelope (routine remittance through a licensed MSB). None starts suppressed; dismissing
the first teaches the cross-customer pattern (agents/memory.signature = typology + structural ledger
envelope), so opening the other two shows the
'auto-suppressed — matches a previously cleared pattern' panel — self-learning, live on stage.

Writes demo_cluster_alerts.json (loaded additively by main.py). Run: python -m data.build_demo_cluster
"""
from __future__ import annotations

import json
from pathlib import Path

from agents.anchoring import anchor_claims, evidence_integrity
from schemas import Alert, ClaimCitation, Transaction
from timeutil import now_local

_DATA = Path(__file__).resolve().parent
OUT = _DATA / "demo_cluster_alerts.json"

# The shared benign counterparty — a licensed money-services business. Fresh (not in
# cleared_patterns_seed), so the cluster starts UN-suppressed until the analyst clears one.
CP_ACCT = "9911223344"
CP_NAME = "QuickCash Remittance Bhd"
CP_BANK = "QuickCash MSB"

# Three unrelated small businesses that all remit through the same MSB — a benign look-alike for
# pass-through (PT-01): rapid outbound movement to one counterparty, but routine remittance.
BUSINESSES = [
    ("DEMO-CL-01", "Kedai Runcit Aman", "ACC-CL-01", 8420.0, 5200.0, 2900.0),
    ("DEMO-CL-02", "Warung Selera Ibu", "ACC-CL-02", 7650.0, 4800.0, 2500.0),
    ("DEMO-CL-03", "Bengkel Motor Jaya", "ACC-CL-03", 9310.0, 6100.0, 2950.0),
]


def _alert(aid: str, holder: str, acct: str, inflow: float, out1: float, out2: float) -> dict:
    ts = ["2026-07-02T09:12:00+08:00", "2026-07-02T11:40:00+08:00", "2026-07-02T15:05:00+08:00"]
    ids = [f"{aid}-T0", f"{aid}-T1", f"{aid}-T2"]
    bal0 = round(3000.0 + inflow, 2)
    txns = [
        {"transactionId": ids[0], "timestamp": ts[0], "amount": inflow, "currency": "MYR",
         "direction": "inbound", "counterpartyName": "Daily takings (POS settlement)",
         "counterpartyAccount": f"POS-{acct}", "counterpartyBank": "Demo Bank", "channel": "ift",
         "runningBalance": bal0, "flags": []},
        {"transactionId": ids[1], "timestamp": ts[1], "amount": out1, "currency": "MYR",
         "direction": "outbound", "counterpartyName": CP_NAME, "counterpartyAccount": CP_ACCT,
         "counterpartyBank": CP_BANK, "channel": "ift", "runningBalance": round(bal0 - out1, 2),
         "flags": ["rapid-movement"]},
        {"transactionId": ids[2], "timestamp": ts[2], "amount": out2, "currency": "MYR",
         "direction": "outbound", "counterpartyName": CP_NAME, "counterpartyAccount": CP_ACCT,
         "counterpartyBank": CP_BANK, "channel": "ift", "runningBalance": round(bal0 - out1 - out2, 2),
         "flags": ["rapid-movement"]},
    ]
    typology_name = "Pass-through / rapid movement"
    cited = [ids[1], ids[2]]  # the two MSB remittances -> dominant counterparty
    txn_objs = [Transaction.model_validate(tx) for tx in txns]

    triage_text = (
        "Same-day outbound movement to a single counterparty resembles pass-through, but the "
        f"counterparty is {CP_NAME}, a licensed money-services business, and the amounts match "
        "routine remittance for a small retailer. No pass-through indicator fires once the MSB "
        "relationship is recognised."
    )
    verifier_text = "Agrees: a licensed remittance provider is the counterparty; the pattern is expected."
    # ADR-0022: claims replace prose, run through the same shared anchoring engine the live
    # pipeline uses — real anchoring, not hand-waved, even for this hand-authored demo cluster.
    triage_claims, _ = anchor_claims(
        [ClaimCitation(text=triage_text, cited_transaction_ids=cited, fired_indicators=[])],
        citable_transactions=txn_objs, fired_indicators=[], matched_typology_name=typology_name,
    )
    verifier_claims, _ = anchor_claims(
        [ClaimCitation(text=verifier_text, cited_transaction_ids=cited, fired_indicators=[])],
        citable_transactions=txn_objs, fired_indicators=[], matched_typology_name=typology_name,
    )

    triage = {
        "alertId": aid, "recommendation": "dismiss", "confidence": 0.61,
        "claims": [c.model_dump(by_alias=True, mode="json") for c in triage_claims],
        "evidenceIntegrity": evidence_integrity(triage_claims).model_dump(by_alias=True, mode="json"),
        "matchedTypology": {"code": "PT-01", "name": typology_name, "source": "FATF/BNM typology"},
        "citedTransactionIds": cited,
        "indicatorCoverage": {
            "indicators": ["rapid in-out movement", "funds forwarded within hours", "high pass-through ratio"],
            "fired": [],
        },
        "verifier": {"status": "agreed", "agreesWithRecommendation": True,
                     "claims": [c.model_dump(by_alias=True, mode="json") for c in verifier_claims]},
        "debate": None, "screening": None, "suppression": None, "strDraft": None,
        "model": "precomputed", "generatedAt": now_local().isoformat(),
    }
    return {
        "alertId": aid, "status": "pending", "createdAt": ts[2], "riskScore": 57,
        "trigger": f"3 transactions (1 in / 2 out) to {CP_NAME} flagged by transaction monitoring",
        "account": {"accountId": acct, "holderName": holder, "accountType": "SME current account",
                    "openedAt": "2023-02-14T09:00:00+08:00"},
        "transactionIds": ids, "transactions": txns, "triage": triage, "routing": "needsReview",
    }


def main() -> int:
    alerts = [_alert(*b) for b in BUSINESSES]
    for a in alerts:
        Alert.model_validate(a)  # fail fast on a malformed cluster alert
    OUT.write_text(json.dumps(alerts, indent=2), encoding="utf-8")
    print(f"wrote {OUT.name}: {len(alerts)} alerts sharing one benign PT-01 behavioral envelope "
          "(dismiss one, the other two self-suppress).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
