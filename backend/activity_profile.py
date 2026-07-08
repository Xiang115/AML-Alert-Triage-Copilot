"""Account Activity Profile — a ledger-derived summary of one alert's account window.

SAML-D carries no customer identity (holderName/accountType/openedAt are honest
placeholders — see data/saml_d_loader.py), so a KYC-style "risk profile" would be
fabricated. This module instead summarises what the *real* ledger shows: turnover per
currency, the balance sweep, cross-border and cash exposure, and counterparty
concentration — every field derived from transactions already in the payload.

Design notes:
- Turnover is grouped **per currency** (never summed across currencies).
- `balanceSwept` reads the per-transaction runningBalance, which the SAML-D loader
  reconstructs from real signed flows (flagged 'reconstructed' in the UI).
- Concentration uses **leg share**, not amount share, so it is well-defined across a
  mixed-currency window.

Pure function: no I/O, no LLM. Computed serve-time in main.py, never persisted.
"""

from __future__ import annotations

_SWEEP_NEAR_ZERO_FRACTION = 0.05  # low <= 5% of peak reads as "drained to ~0"


def _signed(txn: dict) -> float:
    amount = float(txn.get("amount", 0.0))
    return amount if txn.get("direction") == "inbound" else -amount


def _turnover(transactions: list[dict]) -> list[dict]:
    by_ccy: dict[str, dict] = {}
    for t in transactions:
        ccy = t.get("currency", "")
        bucket = by_ccy.setdefault(ccy, {"currency": ccy, "inbound": 0.0, "outbound": 0.0})
        amount = float(t.get("amount", 0.0))
        if t.get("direction") == "inbound":
            bucket["inbound"] += amount
        else:
            bucket["outbound"] += amount
    rows = []
    for b in by_ccy.values():
        rows.append({
            "currency": b["currency"],
            "inbound": round(b["inbound"], 2),
            "outbound": round(b["outbound"], 2),
            "net": round(b["inbound"] - b["outbound"], 2),
        })
    rows.sort(key=lambda r: (-(r["inbound"] + r["outbound"]), r["currency"]))
    return rows


def _balance_swept(transactions: list[dict]) -> dict:
    if not transactions:
        return {"opening": 0.0, "peak": 0.0, "low": 0.0, "closing": 0.0, "sweptToNearZero": False}
    balances = [float(t.get("runningBalance", 0.0)) for t in transactions]
    opening = balances[0] - _signed(transactions[0])
    peak, low, closing = max(balances), min(balances), balances[-1]
    swept = peak > 0 and low <= _SWEEP_NEAR_ZERO_FRACTION * peak
    return {
        "opening": round(opening, 2),
        "peak": round(peak, 2),
        "low": round(low, 2),
        "closing": round(closing, 2),
        "sweptToNearZero": bool(swept),
    }


def _flag_share(transactions: list[dict], flag: str) -> tuple[int, int, float]:
    total = len(transactions)
    legs = sum(1 for t in transactions if flag in (t.get("flags") or []))
    share = round(legs / total, 4) if total else 0.0
    return legs, total, share


def _concentration(transactions: list[dict]) -> dict:
    if not transactions:
        return {"distinctCounterparties": 0, "topCounterparty": None, "topShare": 0.0}
    counts: dict[str, int] = {}
    display: dict[str, str] = {}
    for t in transactions:
        key = t.get("counterpartyAccount") or t.get("counterpartyName") or "unknown"
        counts[key] = counts.get(key, 0) + 1
        display.setdefault(key, t.get("counterpartyName") or key)
    top_key = max(counts, key=lambda k: counts[k])  # first-inserted wins ties (dict order)
    return {
        "distinctCounterparties": len(counts),
        "topCounterparty": display[top_key],
        "topShare": round(counts[top_key] / len(transactions), 4),
    }


def compute_activity_profile(transactions: list[dict]) -> dict:
    """Derive the Account Activity Profile (camelCase, serialised as-is) from an
    alert's embedded transactions."""
    cb_legs, cb_total, cb_share = _flag_share(transactions, "cross-border")
    cash_legs, cash_total, cash_share = _flag_share(transactions, "cash")
    jurisdictions = len({t.get("counterpartyBank") for t in transactions if t.get("counterpartyBank")})
    return {
        "turnover": _turnover(transactions),
        "balanceSwept": _balance_swept(transactions),
        "crossBorder": {"legs": cb_legs, "total": cb_total, "share": cb_share,
                        "jurisdictions": jurisdictions},
        "cash": {"legs": cash_legs, "total": cash_total, "share": cash_share},
        "concentration": _concentration(transactions),
    }
