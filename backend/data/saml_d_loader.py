"""SAML-D loader: turn the public SAML-D set (Oztas et al., 2023) into real
account-centric Alerts the SAME pipeline reasons over as the demo/hero alerts.

Why this exists (ADR-0012): SynthAML's features are amount-less and counterparty-less,
so 3 of our 5 typologies can't fire on it (ADR-0004). SAML-D rows carry **amount +
counterparty + per-transaction typology label**, so we can (a) build *real* on-screen
alerts with transactions (no hand-written demo cases), and (b) MEASURE FI-01/ST-01/PT-01
for real. The two datasets are complementary: SynthAML measures DA-01, SAML-D measures
FI-01/ST-01/PT-01 — together 4 of 5 cards; KYC-01 stays an honest residual (no public set
carries customer profile).

Modeling choices (deliberate, recorded in ADR-0012):
- An **Alert = one account's windowed ledger** (its inbound + outbound transactions),
  because the typology patterns are only visible account-centrically (fan-in needs the
  *receiver's* many inbound legs; structuring needs the depositing account's many
  sub-threshold legs). Direction is inbound when the alert's account is the receiver.
- **runningBalance is synthesised** from the cumulative signed flow over the window
  (SAML-D carries no balance) — a reconstruction from real flows, flagged as derived.
- Account profile (holderName/accountType/openedAt) is unknown in SAML-D; we set honest
  placeholders rather than invent a customer (which is exactly why KYC-01 can't be scored).
- **No label leakage:** Is_laundering / Laundering_type NEVER enter the evidence; flags are
  rule-derived (cross-border, cash) only. The label is used solely to score, never to decide.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

# SAML-D `Laundering_type` (the laundering rows; normal rows are prefixed "Normal_") mapped
# to our 5 curated cards. ONLY clear matches map; ambiguous patterns map to None and are the
# COVERAGE GAP, quantified honestly (the user's question made measurable). DA-01/KYC-01 have
# no SAML-D analogue — DA-01 is measured on SynthAML instead, KYC-01 nowhere (needs profile).
TYPOLOGY_MAP: dict[str, str | None] = {
    # FI-01 Fan-in / Fan-out (consolidation)
    "Fan_In": "FI-01",
    "Fan_Out": "FI-01",
    "Layered_Fan_In": "FI-01",
    "Layered_Fan_Out": "FI-01",
    "Gather-Scatter": "FI-01",
    "Scatter-Gather": "FI-01",
    "Bipartite": "FI-01",
    "Stacked Bipartite": "FI-01",
    # ST-01 Structuring / Smurfing
    "Structuring": "ST-01",
    "Smurfing": "ST-01",
    # PT-01 Pass-through / rapid movement
    "Deposit-Send": "PT-01",
    "Cycle": "PT-01",
    "Single_large": "PT-01",
    # Coverage gap — real laundering our 5-card KB does not describe (honest, counted):
    "Cash_Withdrawal": None,
    "Behavioural_Change_1": None,
    "Behavioural_Change_2": None,
    "Over-Invoicing": None,
}

# Typologies measurable on SAML-D (the mapped, non-None targets), for the per-typology recall.
SAMLD_MEASURED_TYPOLOGIES = ("PT-01", "FI-01", "ST-01")

_CASH_TYPES = {"Cash Deposit", "Cash Withdrawal"}


def map_typology(laundering_type: str) -> str | None:
    """SAML-D Laundering_type -> our card code, or None if no card covers it (coverage gap).
    A 'Normal_*' (benign) label has no mapping and returns None (it is not a laundering type)."""
    return TYPOLOGY_MAP.get(str(laundering_type).strip())


def alert_label(laundering_types: list[str]) -> tuple[str, str | None, bool]:
    """Outcome + typology for an alert, from the labels of its transactions (scoring only).

    Returns (outcome, mapped_card_code, is_coverage_gap):
      - outcome 'escalate' if the window contains any laundering txn, else 'dismiss'.
      - mapped_card_code: the dominant mapped card among the laundering txns (None if every
        laundering txn maps to no card — a pure coverage-gap Report).
      - is_coverage_gap: True when it is a Report but no laundering txn maps to a card.
    """
    laundering = [lt for lt in laundering_types if not str(lt).startswith("Normal_")]
    if not laundering:
        return "dismiss", None, False
    mapped = [c for c in (map_typology(lt) for lt in laundering) if c is not None]
    if not mapped:
        return "escalate", None, True  # real laundering, no card covers it
    # dominant mapped card
    dominant = max(set(mapped), key=mapped.count)
    return "escalate", dominant, False


def direction_for(account_id: int, sender: int, receiver: int) -> str:
    """inbound when the alert's account is the receiver of the leg; outbound when sender."""
    return "inbound" if int(account_id) == int(receiver) else "outbound"


def rule_flags(payment_type: str, sender_loc: str, receiver_loc: str) -> list[str]:
    """Flags a rules engine could derive WITHOUT the label — never from Is_laundering."""
    flags: list[str] = []
    if str(sender_loc).strip() != str(receiver_loc).strip():
        flags.append("cross-border")
    if str(payment_type).strip() in _CASH_TYPES:
        flags.append("cash")
    return flags


def synth_running_balance(signed_amounts: list[float], base: float = 5000.0) -> list[float]:
    """Reconstruct a per-transaction runningBalance from real flows (SAML-D has none).

    Starts at a base lifted enough to keep the balance non-negative across the window, then
    applies each signed flow (+inbound, -outbound). Lets the 'balance drains to ~0' mule tell
    surface for pass-through windows without inventing any transaction."""
    running = 0.0
    troughs = []
    cum = 0.0
    for a in signed_amounts:
        cum += a
        troughs.append(cum)
    lift = base + (-min(troughs) if troughs and min(troughs) < 0 else 0.0)
    out = []
    running = lift
    for a in signed_amounts:
        running += a
        out.append(round(running, 2))
    return out


def build_alert(
    alert_id: str,
    account_id: int,
    legs: list[dict],
    *,
    opened_at: datetime,
    base_balance: float = 5000.0,
) -> dict:
    """Assemble one account-centric Alert (AlertInput wire shape, camelCase) from its windowed
    legs. `legs` are dicts (already time-sorted) with: txn_id, timestamp(datetime), amount,
    currency, sender, receiver, payment_type, sender_loc, receiver_loc. Pure — no file/LLM."""
    signed = []
    for lg in legs:
        d = direction_for(account_id, lg["sender"], lg["receiver"])
        signed.append(lg["amount"] if d == "inbound" else -lg["amount"])
    balances = synth_running_balance(signed, base=base_balance)

    txns = []
    for lg, bal in zip(legs, balances):
        d = direction_for(account_id, lg["sender"], lg["receiver"])
        other = lg["sender"] if d == "inbound" else lg["receiver"]
        other_loc = lg["sender_loc"] if d == "inbound" else lg["receiver_loc"]
        txns.append({
            "transactionId": lg["txn_id"],
            "timestamp": lg["timestamp"].isoformat() if isinstance(lg["timestamp"], datetime) else str(lg["timestamp"]),
            "amount": round(float(lg["amount"]), 2),
            "currency": lg["currency"],
            "direction": d,
            "counterpartyName": f"Acct {other}",
            "counterpartyAccount": str(other),
            "counterpartyBank": str(other_loc),
            "channel": str(lg["payment_type"]).lower().replace(" ", "-"),
            "runningBalance": bal,
            "flags": rule_flags(lg["payment_type"], lg["sender_loc"], lg["receiver_loc"]),
        })

    n_in = sum(t["direction"] == "inbound" for t in txns)
    n_out = len(txns) - n_in
    last_ts = legs[-1]["timestamp"]
    created = last_ts.isoformat() if isinstance(last_ts, datetime) else str(last_ts)
    distinct_cp = len({t["counterpartyAccount"] for t in txns})
    risk = min(95, 25 + 4 * len(txns) + 3 * distinct_cp)
    return {
        "alertId": alert_id,
        "status": "pending",
        "createdAt": created,
        "riskScore": int(risk),
        "trigger": (
            f"{len(txns)} transactions ({n_in} in / {n_out} out) across {distinct_cp} "
            f"counterparties on this account flagged by transaction monitoring"
        ),
        "account": {
            "accountId": f"ACC-{account_id}",
            "holderName": f"SAML-D account {account_id}",
            "accountType": "unknown",
            "openedAt": opened_at.isoformat() if isinstance(opened_at, datetime) else str(opened_at),
        },
        "transactionIds": [t["transactionId"] for t in txns],
        "transactions": txns,
    }


# --- streaming build (I/O wrapper over the pure helpers above) ------------------------

_COLS = ["Time", "Date", "Sender_account", "Receiver_account", "Amount",
         "Payment_currency", "Payment_type", "Sender_bank_location",
         "Receiver_bank_location", "Is_laundering", "Laundering_type"]


def _window(legs: list[dict], laundering_flags: list[int], max_legs: int) -> tuple[list[dict], list[int]]:
    """Trim an account's time-sorted legs to a readable window. For a Report account, centre
    on the laundering cluster (a little context either side); otherwise take the first slice."""
    n = len(legs)
    if n <= max_legs:
        return legs, laundering_flags
    pos = [i for i, f in enumerate(laundering_flags) if f]
    if pos:
        start = max(0, pos[0] - 2)
        end = min(n, max(pos[-1] + 3, start + max_legs))
        start = max(0, min(start, end - max_legs))
    else:
        start, end = 0, max_legs
    end = min(end, start + max_legs)
    return legs[start:end], laundering_flags[start:end]


def _collect_legs(csv_path: Path, accounts: set[int], chunksize: int = 1_000_000) -> dict[int, list[dict]]:
    """Pass 2: stream the CSV and gather every leg (in or out) touching a selected account."""
    by_acct: dict[int, list[dict]] = {a: [] for a in accounts}
    for chunk in pd.read_csv(csv_path, usecols=_COLS, chunksize=chunksize):
        m = chunk["Sender_account"].isin(accounts) | chunk["Receiver_account"].isin(accounts)
        sub = chunk[m]
        for r in sub.itertuples(index=False):
            ts = datetime.fromisoformat(f"{r.Date}T{r.Time}")
            leg = {
                "timestamp": ts, "amount": float(r.Amount), "currency": r.Payment_currency,
                "sender": int(r.Sender_account), "receiver": int(r.Receiver_account),
                "payment_type": r.Payment_type, "sender_loc": r.Sender_bank_location,
                "receiver_loc": r.Receiver_bank_location,
                "_is_laundering": int(r.Is_laundering), "_ltype": r.Laundering_type,
            }
            for a in (leg["sender"], leg["receiver"]):
                if a in by_acct:
                    by_acct[a].append(leg)
    return by_acct


def build(csv_path: str | Path, out_dir: str | Path, *, seed: int = 42,
          n_holdout_report: int = 150, n_holdout_normal: int = 150,
          demo_per_typology: int = 4, demo_normal: int = 6, demo_lookalike: int = 4,
          max_legs: int = 12) -> dict:
    """One-time build tool: SAML-D.csv -> real account-centric alerts.

    Writes (disjoint pools, ADR-0005/0012):
      saml_d_demo_queue.json  — a curated real-alert queue for precompute/the demo (clear
                                patterns + benign-look-alikes to mine the verifier wow).
      saml_d_holdout.json     — a labelled held-out slice for the per-typology metric.
    """
    csv_path, out_dir = Path(csv_path), Path(out_dir)
    rng = np.random.RandomState(seed)

    # Pass 1: per-account laundering involvement (typology) + Normal_Fan_In look-alikes.
    launder: dict[int, Counter] = {}
    lookalike_recv: Counter = Counter()
    all_accts: set[int] = set()
    for chunk in pd.read_csv(csv_path, usecols=["Sender_account", "Receiver_account",
                             "Is_laundering", "Laundering_type"], chunksize=2_000_000):
        all_accts.update(chunk["Sender_account"].unique().tolist())
        all_accts.update(chunk["Receiver_account"].unique().tolist())
        lr = chunk[chunk.Is_laundering == 1]
        for r in lr.itertuples(index=False):
            for a in (int(r.Sender_account), int(r.Receiver_account)):
                launder.setdefault(a, Counter())[str(r.Laundering_type)] += 1
        # benign fan-in look-alikes: receivers of Normal_Fan_In (looks like consolidation)
        la = chunk[chunk.Laundering_type == "Normal_Fan_In"]
        lookalike_recv.update(la["Receiver_account"].astype(int).tolist())

    # account -> (dominant mapped typology, total laundering count)
    def dom_typ(c: Counter) -> tuple[str | None, int]:
        mapped = Counter()
        for lt, k in c.items():
            code = map_typology(lt)
            if code:
                mapped[code] += k
        total = sum(c.values())
        return (mapped.most_common(1)[0][0] if mapped else None, total)

    report_accts = {a: dom_typ(c) for a, c in launder.items()}
    normal_pool = [a for a in all_accts if a not in launder and lookalike_recv.get(a, 0) == 0]
    lookalikes = [a for a, k in lookalike_recv.most_common() if a not in launder and k >= 4]

    # --- select DEMO pool (clear hubs per measurable typology + look-alikes + plain normal) ---
    demo_sel: dict[int, dict] = {}
    for typ in SAMLD_MEASURED_TYPOLOGIES:
        hubs = sorted([a for a, (t, n) in report_accts.items() if t == typ],
                      key=lambda a: report_accts[a][1], reverse=True)
        for a in hubs[:demo_per_typology]:
            demo_sel[a] = {"pool": "demo", "kind": "report"}
    for a in lookalikes[:demo_lookalike]:
        demo_sel[a] = {"pool": "demo", "kind": "lookalike"}
    for a in rng.permutation(normal_pool)[:demo_normal].tolist():
        demo_sel[int(a)] = {"pool": "demo", "kind": "normal"}

    # --- select HELD-OUT pool (disjoint from demo) ---
    report_ids = [a for a in report_accts if a not in demo_sel]
    normal_ids = [a for a in normal_pool if a not in demo_sel]
    hold_report = rng.permutation(report_ids)[:n_holdout_report].tolist()
    hold_normal = rng.permutation(normal_ids)[:n_holdout_normal].tolist()
    hold_sel = {int(a): {"pool": "holdout", "kind": "report"} for a in hold_report}
    hold_sel.update({int(a): {"pool": "holdout", "kind": "normal"} for a in hold_normal})

    selected = set(demo_sel) | set(hold_sel)
    legs_by_acct = _collect_legs(csv_path, selected)

    def make(account: int, idx: int) -> tuple[dict, dict]:
        legs = sorted(legs_by_acct[account], key=lambda l: l["timestamp"])
        flags = [l["_is_laundering"] for l in legs]
        ltypes_all = [l["_ltype"] for l in legs]
        wlegs, wflags = _window(legs, flags, max_legs)
        # labels reflect only what is shown in the window
        start = legs.index(wlegs[0]) if wlegs else 0
        wltypes = ltypes_all[start:start + len(wlegs)]
        outcome, code, gap = alert_label(wltypes)
        opened = min(l["timestamp"] for l in legs)
        clean = [{k: v for k, v in l.items() if not k.startswith("_")} | {"txn_id": f"SDT-{idx}-{j}"}
                 for j, l in enumerate(wlegs)]
        alert = build_alert(f"SD-{idx:05d}", account, clean, opened_at=opened)
        meta = {"alertId": alert["alertId"], "outcome": outcome,
                "typology": code, "coverageGap": gap}
        return alert, meta

    demo_alerts, demo_meta = [], []
    for i, a in enumerate(demo_sel, 1):
        if not legs_by_acct.get(a):
            continue
        al, mt = make(a, i)
        mt["kind"] = demo_sel[a]["kind"]
        demo_alerts.append(al)
        demo_meta.append(mt)

    hold_alerts, hold_meta = [], []
    for i, a in enumerate(hold_sel, 10001):
        if not legs_by_acct.get(a):
            continue
        al, mt = make(a, i)
        hold_alerts.append(al)
        hold_meta.append(mt)

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "saml_d_demo_queue.json").write_text(
        json.dumps(demo_alerts, indent=2), encoding="utf-8")
    (out_dir / "saml_d_demo_meta.json").write_text(
        json.dumps(demo_meta, indent=2), encoding="utf-8")
    (out_dir / "saml_d_holdout.json").write_text(
        json.dumps({"alerts": hold_alerts, "meta": hold_meta}, indent=2), encoding="utf-8")

    summary = {
        "demo": len(demo_alerts), "demoReports": sum(m["outcome"] == "escalate" for m in demo_meta),
        "demoLookalikes": sum(m["kind"] == "lookalike" for m in demo_meta),
        "holdout": len(hold_alerts), "holdoutReports": sum(m["outcome"] == "escalate" for m in hold_meta),
        "holdoutCoverageGap": sum(m["coverageGap"] for m in hold_meta),
    }
    return summary


if __name__ == "__main__":
    _DATA = Path(__file__).resolve().parent
    s = build(_DATA / "SAML-D.csv", _DATA)
    print("SAML-D build:", json.dumps(s, indent=2))

