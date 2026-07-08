"""Build tool (ADR-0009/0015): assemble UP TO 4 real IBM AMLworld fan-in clusters into the frozen
`networks.json` the API serves, plus each hidden mule's own account as a benign-looking queue alert
(`ibm_seed_alerts.json`). Build tools, never called at request time (mirrors precompute.py).

Each hero is a QUALITATIVE, hand-selected REAL cluster (ADR-0015) — NO metric is claimed. Selection
is automatic but honest: a hub qualifies only if its pattern legs are actually present in the graph
(aligned), it has >=2 laundering spokes, a benign spoke to clear, AND a hidden mule (an active,
mostly-normal account that single-account triage would dismiss). Run once, freeze; raw inputs gitignored.

Run from /backend:  python -m data.ibm_network
"""
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from agents.anchoring import anchor_claims, evidence_integrity
from schemas import ClaimCitation, Transaction
from timeutil import now_local

_DATA = Path(__file__).resolve().parent
PATTERNS = _DATA / "HI-Medium_Patterns.txt"
TRANS = _DATA / "HI-Medium_Trans.csv"
ACCOUNTS = _DATA / "HI-Medium_accounts.csv"
OUT_NET = _DATA / "networks.json"
OUT_SEED = _DATA / "ibm_seed_alerts.json"

FIRST_HUB = "81A4AFE20"   # the verified hero — pinned to IBM-MULE-01 so it never regresses
N_HEROES = 4
CANDIDATE_POOL = 60       # top fan-in hubs (by pattern degree) to evaluate
MIN_SPOKES = 4
MAX_MULES = 5
WINDOW = 12
_CASH = {"Cash", "Cash Deposit", "Cash Withdrawal"}


def _iso(ts: str) -> str:
    return datetime.strptime(ts, "%Y/%m/%d %H:%M").isoformat()


def _fanin_hubs() -> dict[str, int]:
    """Every fan-in hub -> its pattern spoke count (from Patterns.txt), for candidate ranking."""
    hubs: dict[str, int] = {}
    ptype, cur = None, []
    for line in PATTERNS.open(encoding="utf-8", errors="replace"):
        line = line.strip()
        if line.startswith("BEGIN LAUNDERING ATTEMPT"):
            ptype = line.split("-", 1)[1].split(":")[0].strip() if "-" in line else "?"
            cur = []
        elif line.startswith("END LAUNDERING ATTEMPT"):
            if ptype and "FAN-IN" in ptype.upper() and cur:
                tc = defaultdict(set)
                for fr, to in cur:
                    tc[to].add(fr)
                hub = max(tc, key=lambda h: len(tc[h]))
                hubs[hub] = max(hubs.get(hub, 0), len(tc[hub]))
            ptype, cur = None, []
        elif line and ptype is not None:
            p = line.split(",")
            if len(p) >= 11:
                cur.append((p[2], p[4]))
    return hubs


def _scan(cand_hubs: set[str]) -> tuple[dict, dict]:
    """Pass 1: inbound edges to every candidate hub. Pass 2: full leg records for those hubs and all
    their senders (so we can profile a hidden mule and window its ledger). Two passes, bounded memory."""
    edges: dict[str, dict] = defaultdict(lambda: defaultdict(
        lambda: {"amount": 0.0, "count": 0, "launder": 0, "currency": ""}))
    with TRANS.open(encoding="utf-8", errors="replace", newline="") as f:
        r = csv.reader(f); next(r)
        for row in r:
            if row[4] in cand_hubs and row[2] != row[4]:
                e = edges[row[4]][row[2]]
                e["amount"] += float(row[7]); e["count"] += 1
                e["launder"] += 1 if row[10] == "1" else 0
                e["currency"] = row[8]
    targets = set(cand_hubs)
    for hub in edges:
        targets |= set(edges[hub])
    legs: dict[str, list] = defaultdict(list)
    with TRANS.open(encoding="utf-8", errors="replace", newline="") as f:
        r = csv.reader(f); next(r)
        for row in r:
            if row[2] == row[4]:
                continue
            touched = [a for a in (row[2], row[4]) if a in targets]
            if not touched:
                continue
            leg = {"ts": row[0], "from": row[2], "to": row[4], "amount": float(row[7]),
                   "currency": row[8], "launder": row[10] == "1", "format": row[9],
                   "fromBank": row[1], "toBank": row[3]}
            for a in touched:
                legs[a].append(leg)
    return edges, legs


def _holder_names(accounts: set[str]) -> dict[str, str]:
    names: dict[str, str] = {}
    with ACCOUNTS.open(encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            if row["Account Number"] in accounts:
                names[row["Account Number"]] = row["Entity Name"]
    return names


def _synth_balance(signed: list[float], base: float = 8000.0) -> list[float]:
    cum, troughs = 0.0, []
    for a in signed:
        cum += a; troughs.append(cum)
    r = base + (-min(troughs) if troughs and min(troughs) < 0 else 0.0)
    out = []
    for a in signed:
        r += a; out.append(round(r, 2))
    return out


def _frac(stats: dict, a: str) -> float:
    t = stats[a]["total"]
    return stats[a]["launder"] / t if t else 0.0


def _pick_roles(hub_edges: dict, stats: dict) -> dict | None:
    """Assign roles for a hub, or None if it doesn't make a clean hero (aligned + hidden mule + benign)."""
    if len(hub_edges) < MIN_SPOKES:
        return None
    launder = [s for s in hub_edges if hub_edges[s]["launder"] > 0]
    benign = [s for s in hub_edges if hub_edges[s]["launder"] == 0]
    if len(launder) < 2 or not benign:
        return None
    active = [s for s in launder if stats[s]["total"] >= 20]
    if not active:
        return None
    hidden = min(active, key=lambda s: _frac(stats, s))
    if _frac(stats, hidden) > 0.15:  # a hidden mule must genuinely look mostly-normal alone
        return None
    mules = sorted((s for s in launder if s != hidden), key=lambda s: -hub_edges[s]["amount"])[:MAX_MULES]
    if not mules:
        return None
    return {"hidden": hidden, "mules": mules, "benign": max(benign, key=lambda s: hub_edges[s]["amount"])}


def _build_network(hub: str, seed_id: str, roles: dict, hub_edges: dict, stats: dict, names: dict) -> dict:
    hidden, mules, benign = roles["hidden"], roles["mules"], roles["benign"]
    spoke_order = mules + [hidden, benign]
    n = len(spoke_order)
    nodes = [{
        "accountId": hub, "holderName": names.get(hub, f"Account {hub}"),
        "role": "hub", "isSeed": False, "x": 620.0, "y": 260.0,
        "totalLegs": stats[hub]["total"], "launderingLegs": stats[hub]["launder"],
        "note": "Consolidation account — receives the fan-in and forwards it on.",
    }]
    for i, s in enumerate(spoke_order):
        y = 60.0 + (400.0 * i / max(1, n - 1))
        if s == hidden:
            role = "hidden_mule"
            note = (f"{stats[s]['total']} transactions, only {stats[s]['launder']} laundering "
                    f"({_frac(stats, s)*100:.0f}%) — reads as an ordinary business alone; the network exposes it.")
        elif s == benign:
            role, note = "benign_cleared", "Legitimate payer to the same account — cleared, not flagged."
        else:
            role, note = "mule", f"{hub_edges[s]['count']} transfer(s) into the hub."
        nodes.append({
            "accountId": s, "holderName": names.get(s, f"Account {s}"), "role": role,
            "isSeed": s == hidden, "x": 180.0, "y": round(y, 1),
            "totalLegs": stats[s]["total"], "launderingLegs": stats[s]["launder"], "note": note,
        })
    edge_list = [{
        "fromAccountId": s, "toAccountId": hub, "amount": round(hub_edges[s]["amount"], 2),
        "currency": hub_edges[s]["currency"] or "US Dollar", "transferCount": hub_edges[s]["count"],
        "laundering": hub_edges[s]["launder"] > 0,
    } for s in spoke_order]
    narrative = (
        f"{len(spoke_order)} accounts funnel into {names.get(hub, hub)} — a fan-in consolidation "
        f"pattern. Account-level triage cleared {names.get(hidden, hidden)}: on its own it looks like an "
        f"ordinary business ({stats[hidden]['total']} transactions, {_frac(stats, hidden)*100:.0f}% "
        f"laundering). The network re-surfaces it as a mule feeding the hub, while clearing a legitimate "
        f"payer to the same account — discrimination, not guilt by association."
    )
    return {
        "seedAlertId": seed_id,
        "typology": {"code": "FI-01", "name": "Fan-in consolidation", "source": "FATF/BNM typology"},
        "nodes": nodes, "edges": edge_list, "narrative": narrative,
        "source": "Real IBM AMLworld HI-Medium cluster — illustrative; the measured numbers are the SAML-D triage metrics (ADR-0015).",
        "generatedAt": now_local().isoformat(),
    }


def _build_seed(hidden: str, seed_id: str, legs: dict, names: dict, stats: dict) -> dict:
    srt = sorted(legs[hidden], key=lambda l: l["ts"])
    if len(srt) <= WINDOW:
        window = srt
    else:
        # Most ordinary contiguous window (min largest single amount) — dodges IBM's extreme outliers.
        best = min(range(len(srt) - WINDOW + 1), key=lambda i: max(l["amount"] for l in srt[i:i + WINDOW]))
        window = srt[best:best + WINDOW]
    signed = [(l["amount"] if l["to"] == hidden else -l["amount"]) for l in window]
    balances = _synth_balance(signed)
    txns, ids = [], []
    for i, (l, bal) in enumerate(zip(window, balances)):
        inbound = l["to"] == hidden
        cp = l["from"] if inbound else l["to"]
        flags = ["cross-border"] if l["fromBank"] != l["toBank"] else []
        if l["format"] in _CASH:
            flags.append("cash")
        tid = f"{seed_id}-T{i}"
        ids.append(tid)
        txns.append({
            "transactionId": tid, "timestamp": _iso(l["ts"]), "amount": round(l["amount"], 2),
            "currency": l["currency"], "direction": "inbound" if inbound else "outbound",
            "counterpartyName": names.get(cp, f"Account {cp}"), "counterpartyAccount": cp,
            "counterpartyBank": l["fromBank"] if inbound else l["toBank"],
            "channel": l["format"], "runningBalance": bal, "flags": flags,
        })
    n_in = sum(1 for t in txns if t["direction"] == "inbound")

    triage_text = (
        "Windowed activity is consistent with an ordinary active business: recurring, established "
        "counterparties and modest transfers in both directions, with no single large movement and "
        "no rapid full-forwarding of incoming funds. No money-laundering typology fires on the "
        "account viewed alone."
    )
    verifier_text = "Agrees the single-account evidence is unremarkable; no typology to challenge."
    # ADR-0022: claims replace prose, run through the same shared anchoring engine the live
    # pipeline uses — real anchoring, not hand-waved, even for this hand-authored seed alert.
    txn_objs = [Transaction.model_validate(t) for t in txns]
    triage_claims, _ = anchor_claims(
        [ClaimCitation(text=triage_text, cited_transaction_ids=[], fired_indicators=[])],
        citable_transactions=txn_objs, fired_indicators=[], matched_typology_name="No typology matched",
    )
    verifier_claims, _ = anchor_claims(
        [ClaimCitation(text=verifier_text, cited_transaction_ids=[], fired_indicators=[])],
        citable_transactions=txn_objs, fired_indicators=[], matched_typology_name="No typology matched",
    )

    triage = {
        "alertId": seed_id, "recommendation": "dismiss", "confidence": 0.58,
        "claims": [c.model_dump(by_alias=True, mode="json") for c in triage_claims],
        "evidenceIntegrity": evidence_integrity(triage_claims).model_dump(by_alias=True, mode="json"),
        "matchedTypology": {"code": "NONE", "name": "No typology matched", "source": "n/a"},
        "citedTransactionIds": [], "indicatorCoverage": {"indicators": [], "fired": []},
        "verifier": {"status": "agreed", "agreesWithRecommendation": True,
                     "claims": [c.model_dump(by_alias=True, mode="json") for c in verifier_claims]},
        "debate": None, "screening": None, "suppression": None, "strDraft": None,
        "model": "precomputed", "generatedAt": now_local().isoformat(),
    }
    return {
        "alertId": seed_id, "status": "pending", "createdAt": _iso(window[-1]["ts"]), "riskScore": 41,
        "trigger": f"{len(txns)} transactions ({n_in} in / {len(txns) - n_in} out) on an active account "
                   f"flagged by transaction monitoring",
        "account": {"accountId": f"ACC-{hidden}", "holderName": names.get(hidden, f"Account {hidden}"),
                    "accountType": "Sole Proprietorship", "openedAt": _iso(srt[0]["ts"])},
        "transactionIds": ids, "transactions": txns, "triage": triage, "routing": "needsReview",
    }


def build() -> tuple[dict, list]:
    hubs = _fanin_hubs()
    ranked = sorted((h for h in hubs if h != FIRST_HUB), key=lambda h: -hubs[h])[:CANDIDATE_POOL]
    candidates = ([FIRST_HUB] if FIRST_HUB in hubs else []) + ranked
    edges, legs = _scan(set(candidates))
    stats = {a: {"total": len(v), "launder": sum(1 for l in v if l["launder"])} for a, v in legs.items()}

    heroes = []  # (hub, roles)
    for hub in candidates:
        roles = _pick_roles(edges.get(hub, {}), stats)
        if roles:
            heroes.append((hub, roles))
        if len(heroes) >= N_HEROES:
            break

    # names for every hero node + every hidden-mule window counterparty
    need = set()
    for hub, roles in heroes:
        need |= {hub, roles["hidden"], roles["benign"], *roles["mules"]}
        need |= {(l["from"] if l["to"] == roles["hidden"] else l["to"]) for l in legs.get(roles["hidden"], [])}
    names = _holder_names(need)

    networks, seeds = {}, []
    for i, (hub, roles) in enumerate(heroes, 1):
        seed_id = f"IBM-MULE-{i:02d}"
        networks[seed_id] = _build_network(hub, seed_id, roles, edges[hub], stats, names)
        seeds.append(_build_seed(roles["hidden"], seed_id, legs, names, stats))
    return networks, seeds


def main() -> int:
    for p in (PATTERNS, TRANS, ACCOUNTS):
        if not p.exists():
            print(f"Missing {p.name} — place the IBM HI-Medium files in backend/data/ (gitignored).")
            return 1
    print("assembling fan-in hero networks (scans the 3 GB Trans.csv twice — ~3 min)...", flush=True)
    networks, seeds = build()
    from schemas import Alert, MuleNetwork
    for net in networks.values():
        MuleNetwork.model_validate(net)
    for s in seeds:
        Alert.model_validate(s)
    OUT_NET.write_text(json.dumps(networks, indent=2), encoding="utf-8")
    OUT_SEED.write_text(json.dumps(seeds, indent=2), encoding="utf-8")
    print(f"wrote {OUT_NET.name}: {len(networks)} hero network(s) -> {list(networks)}")
    for s in seeds:
        print(f"  {s['alertId']}: {s['account']['holderName']} ({len(s['transactions'])} txns, "
              f"triage={s['triage']['recommendation']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
