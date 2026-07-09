"""Build tool (Slice A, standing demo): a 2-alert benign FI-01 consolidation cluster that shares one
behavioral envelope — a registered rotating-savings committee (kootu / ROSCA): fixed monthly member
contributions fan in, then a single scheduled payout. A benign look-alike for scam-victim
consolidation (FI-01).

Unlike the beat-3 DEMO-CL cluster (which starts un-suppressed and teaches LIVE on stage), THIS cluster
ships with STANDCL-01 already seeded into cleared_patterns_seed.json as a prior clearance. So on a cold
load STANDCL-02 shows a real 'auto-suppressed — matches a previously cleared pattern' panel and the
Learning-loop card reads a truthful '1 future alert affected' — without pre-empting the DEMO-CL beat.
STANDCL-01 is the teacher (the pattern's source), so it is not suppressed against its own clearance.

Writes standing_cluster_alerts.json (loaded additively by main.py). After running, set
cleared_patterns_seed.json's signature to the value this prints. Run: python -m data.build_standing_cluster
"""
from __future__ import annotations

import json
from pathlib import Path

from agents.anchoring import anchor_claims, evidence_integrity
from agents.memory import signature as envelope_signature
from schemas import Alert, ClaimCitation, Transaction
from timeutil import now_local

_DATA = Path(__file__).resolve().parent
OUT = _DATA / "standing_cluster_alerts.json"

TYPOLOGY_NAME = "Fan-in / Fan-out (Consolidation)"
TYPOLOGY_SOURCE = "FATF Recommendations (2012), R.20; BNM AML/CFT Policy Document; scam-mule guidance"

# Two registered rotating-savings committees run by different customers — same benign structure, so
# they share one behavioral envelope (agents.memory.signature = typology + structural ledger shape).
COMMITTEES = [
    ("STANDCL-01", "Taman Sri Aman Committee Fund", "ACC-SC-01"),
    ("STANDCL-02", "Kampung Melati Kootu Fund", "ACC-SC-02"),
]

# Four fixed monthly contributions fan in, then one scheduled payout leaves the balance well above zero
# (no drain-to-~0 pass-through tell -> envelope stays benign-consistent).
CONTRIBUTIONS = [2600.0, 2550.0, 2700.0, 2500.0]
PAYOUT = 9000.0
OPENING = 3000.0


def _alert(aid: str, holder: str, acct: str) -> dict:
    ts = [
        "2026-07-03T09:05:00+08:00", "2026-07-03T09:40:00+08:00", "2026-07-03T10:15:00+08:00",
        "2026-07-03T10:55:00+08:00", "2026-07-03T14:30:00+08:00",
    ]
    ids = [f"{aid}-T{i}" for i in range(5)]
    txns: list[dict] = []
    bal = OPENING
    for i, amt in enumerate(CONTRIBUTIONS):
        bal = round(bal + amt, 2)
        txns.append({
            "transactionId": ids[i], "timestamp": ts[i], "amount": amt, "currency": "MYR",
            "direction": "inbound", "counterpartyName": f"Member contribution {i + 1}",
            "counterpartyAccount": f"MBR-{acct}-{i + 1}", "counterpartyBank": "Demo Bank",
            "channel": "ift", "runningBalance": bal, "flags": [],
        })
    bal = round(bal - PAYOUT, 2)
    txns.append({
        "transactionId": ids[4], "timestamp": ts[4], "amount": PAYOUT, "currency": "MYR",
        "direction": "outbound", "counterpartyName": "Scheduled payout (member of the month)",
        "counterpartyAccount": f"PAYEE-{acct}", "counterpartyBank": "Demo Bank", "channel": "ift",
        "runningBalance": bal, "flags": [],
    })

    cited = ids[:4]  # the fan-in contributions
    txn_objs = [Transaction.model_validate(tx) for tx in txns]

    triage_text = (
        "Multiple inbound contributions consolidating into one account before a single payout resembles "
        "fan-in consolidation, but the account is a registered rotating-savings committee (kootu / ROSCA): "
        "fixed, equal monthly contributions from known members and one scheduled payout. No scam-victim "
        "consolidation indicator fires once the committee relationship is recognised."
    )
    verifier_text = (
        "Agrees: contributions are fixed and periodic and the payout is scheduled — a benign rotating-"
        "savings pattern, not scam-victim consolidation."
    )
    triage_claims, _ = anchor_claims(
        [ClaimCitation(text=triage_text, cited_transaction_ids=cited, fired_indicators=[])],
        citable_transactions=txn_objs, fired_indicators=[], matched_typology_name=TYPOLOGY_NAME,
    )
    verifier_claims, _ = anchor_claims(
        [ClaimCitation(text=verifier_text, cited_transaction_ids=cited, fired_indicators=[])],
        citable_transactions=txn_objs, fired_indicators=[], matched_typology_name=TYPOLOGY_NAME,
    )

    triage = {
        "alertId": aid, "recommendation": "dismiss", "confidence": 0.7,
        "claims": [c.model_dump(by_alias=True, mode="json") for c in triage_claims],
        "evidenceIntegrity": evidence_integrity(triage_claims).model_dump(by_alias=True, mode="json"),
        "matchedTypology": {"code": "FI-01", "name": TYPOLOGY_NAME, "source": TYPOLOGY_SOURCE},
        "citedTransactionIds": cited,
        "indicatorCoverage": {
            "indicators": ["many inbound sources", "consolidation into one account", "onward forwarding"],
            "fired": [],
        },
        "verifier": {"status": "agreed", "agreesWithRecommendation": True,
                     "claims": [c.model_dump(by_alias=True, mode="json") for c in verifier_claims]},
        "debate": None, "screening": None, "suppression": None, "strDraft": None,
        "model": "precomputed", "generatedAt": now_local().isoformat(),
    }
    return {
        "alertId": aid, "status": "pending", "createdAt": ts[4], "riskScore": 44,
        "trigger": "5 transactions (4 in / 1 out) consolidating into one account flagged by monitoring",
        "account": {"accountId": acct, "holderName": holder, "accountType": "Committee/association account",
                    "openedAt": "2021-08-10T09:00:00+08:00"},
        "transactionIds": ids, "transactions": txns, "triage": triage, "routing": "needsReview",
    }


def main() -> int:
    alerts = [_alert(*c) for c in COMMITTEES]
    for a in alerts:
        Alert.model_validate(a)  # fail fast on a malformed cluster alert
    OUT.write_text(json.dumps(alerts, indent=2), encoding="utf-8")

    sigs = {envelope_signature(a) for a in alerts}
    assert len(sigs) == 1, f"cluster members must share one envelope, got {sigs}"
    print(f"wrote {OUT.name}: {len(alerts)} alerts sharing one benign FI-01 envelope.")
    print(f"seed signature (source STANDCL-01): {sigs.pop()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
