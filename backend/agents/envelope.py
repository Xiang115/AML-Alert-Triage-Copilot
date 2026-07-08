"""Shared behavioral-envelope signature (ADR-0021, fork B).

The SINGLE structural feature definition used by BOTH the live suppression (`agents.memory`) and the
offline leakage measurement (`eval.evaluate_suppression`), so the mechanism the app ships is literally
the mechanism the frontier measures. Chosen over a counterparty-identity signature because identity
recurs on ~0% of held-out SAML-D alerts while this behavioral envelope recurs on ~97% (CONTEXT.md:
Behavioral Envelope). Pure/deterministic — reuses `compute_activity_profile` for the ledger tells, so
the app and the eval can never drift on what the envelope is.
"""
from __future__ import annotations

from activity_profile import compute_activity_profile

# The pre-registered operating point's feature set (evaluate_suppression._OPERATING_POINT): the
# tightest envelope. The live signature keys on all of these so a live auto-clear matches the same
# bucket definition the measured frontier reports 0/80 leakage over.
OPERATING_POINT_FEATURES = ["typ", "amt", "dir", "drain", "conc", "xb", "cash", "ntxn"]

_AMT_EDGES = [1e3, 5e3, 1e4, 5e4, 1e5, 5e5]


def amt_band(x: float) -> int:
    for i, edge in enumerate(_AMT_EDGES):
        if x <= edge:
            return i
    return 6


def band3(share: float) -> int:
    return 0 if share == 0 else (2 if share >= 0.999 else 1)


def dir_shape(in_count: int, out_count: int) -> str:
    return "in" if out_count == 0 else ("out" if in_count == 0 else "mix")


def conc_band(top_share: float) -> int:
    return 0 if top_share < 0.5 else (1 if top_share < 0.8 else 2)


def envelope_features(
    *, typology: str | None, total_amount: float, in_count: int, out_count: int,
    transactions: list[dict],
) -> dict:
    """The structural, label-free behavioral envelope. One definition, called by the app and the eval.

    `typology` is the caller's typology key: the live app passes the model's matched-typology code
    (verifier-checked); the eval passes the dataset's ground-truth typology for a label-blind
    measurement. The remaining seven features are pure ledger structure via `compute_activity_profile`.
    """
    prof = compute_activity_profile(transactions)
    return {
        "typ": typology or "NONE",
        "amt": amt_band(float(total_amount)),
        "dir": dir_shape(in_count, out_count),
        "drain": bool(prof["balanceSwept"]["sweptToNearZero"]),
        "xb": band3(prof["crossBorder"]["share"]),
        "cash": band3(prof["cash"]["share"]),
        "conc": conc_band(prof["concentration"]["topShare"]),
        "ntxn": min(len(transactions), 5),
    }


def signature_key(env: dict, features: list[str] = OPERATING_POINT_FEATURES) -> str:
    """A stable, human-readable string key over the selected features (order-preserving)."""
    return "|".join(f"{f}={env[f]}" for f in features)


def signature_from_transactions(typology: str | None, transactions: list[dict]) -> str | None:
    """Convenience for the live app: derive the operating-point signature straight from an alert's
    raw ledger. None when the typology is unknown or the ledger is empty (nothing to key on)."""
    if not typology or not transactions:
        return None
    in_count = sum(1 for t in transactions if t.get("direction") == "inbound")
    out_count = sum(1 for t in transactions if t.get("direction") == "outbound")
    total_amount = sum(float(t.get("amount", 0.0)) for t in transactions)
    env = envelope_features(
        typology=typology, total_amount=total_amount,
        in_count=in_count, out_count=out_count, transactions=transactions,
    )
    return signature_key(env)
