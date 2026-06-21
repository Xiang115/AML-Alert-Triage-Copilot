"""SynthAML loader: reduce the dense, normalized transaction history to a small
per-alert feature record, and carve the frozen held-out split.

Real SynthAML alerts have ~829 transactions each, normalized `Size` (not currency),
and no counterparty/customer — so they drive the accuracy metric, not the on-screen
demo (see docs/adr/0005). `build()` streams the 935 MB file once and writes
`alert_features.csv` + `holdout_alert_ids.json`.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from config import RANDOM_SEED

# Feature columns produced per alert (order is the file/contract order).
FEATURE_COLUMNS = [
    "txnCount",
    "creditCount",
    "debitCount",
    "creditDebitRatio",
    "cardFrac",
    "wireFrac",
    "cashFrac",
    "intlFrac",
    "spanDays",
    "maxDormancyGapDays",
    "burstFrac",
    "sizeMean",
    "sizeStd",
    "sizeMax",
    "netFlow",
    # Timestamp-based pattern features (the only typology signals real SynthAML can
    # express — no counterparty, no currency amounts). They map the aggregate row back
    # to the two detectable typologies so triage has something to fire on (ADR-0005).
    "medianCreditToDebitHours",  # PT-01 pass-through: in then straight back out
    "postDormancyBurstFrac",     # DA-01 dormant-then-active: woke up and burst
]

_DAY = 86400.0


def _median_credit_to_debit_hours(ts: np.ndarray, entry: np.ndarray, default: float) -> float:
    """Pass-through signal (PT-01): FIFO-pair each credit with the next debit and take
    the median hours between. Small => funds move in and straight back out. `default`
    (the full span) stands in when nothing pairs, i.e. no rapid turnover."""
    from collections import deque

    pending: deque = deque()
    gaps: list[float] = []
    for t, e in zip(ts, entry):
        if e == "Credit":
            pending.append(t)
        elif pending:
            c = pending.popleft()
            gaps.append((t - c) / np.timedelta64(1, "h"))
    return float(np.median(gaps)) if gaps else float(default)


def _post_dormancy_burst_frac(ts: np.ndarray, n: int) -> float:
    """Dormant-then-active signal (DA-01): fraction of transactions within 7 days after
    the single largest inactivity gap. High (paired with a large maxDormancyGapDays) =>
    a long-quiet account suddenly bursting back to life."""
    if n < 2:
        return 0.0
    diffs = np.diff(ts) / np.timedelta64(1, "D")
    reactivation = ts[int(np.argmax(diffs)) + 1]
    window_end = reactivation + np.timedelta64(7, "D")
    post = int(((ts >= reactivation) & (ts <= window_end)).sum())
    return post / n


def _features_for_alert(g: pd.DataFrame) -> dict:
    ts = pd.to_datetime(g["Timestamp"]).sort_values()
    n = len(g)
    credit = (g["Entry"] == "Credit").sum()
    debit = n - credit
    types = g["Type"].value_counts()
    signed = g["Size"].where(g["Entry"] == "Credit", -g["Size"])
    gaps = ts.diff().dropna().dt.total_seconds() / _DAY
    per_day = ts.dt.floor("D").value_counts()
    # Timestamp-ordered view so credit/debit timing lines up (the aggregate stats above
    # are order-independent; the pattern features below are not).
    gs = g.sort_values("Timestamp")
    order_ts = pd.to_datetime(gs["Timestamp"]).to_numpy()
    span_hours = (ts.iloc[-1] - ts.iloc[0]).total_seconds() / 3600 if n > 1 else 0.0
    return {
        "txnCount": n,
        "creditCount": int(credit),
        "debitCount": int(debit),
        "creditDebitRatio": credit / debit if debit else float(credit),
        "cardFrac": types.get("Card", 0) / n,
        "wireFrac": types.get("Wire", 0) / n,
        "cashFrac": types.get("Cash", 0) / n,
        "intlFrac": types.get("International", 0) / n,
        "spanDays": (ts.iloc[-1] - ts.iloc[0]).total_seconds() / _DAY,
        "maxDormancyGapDays": float(gaps.max()) if len(gaps) else 0.0,
        "burstFrac": int(per_day.max()) / n,
        "sizeMean": g["Size"].mean(),
        "sizeStd": g["Size"].std(ddof=0),
        "sizeMax": g["Size"].max(),
        "netFlow": signed.sum(),
        "medianCreditToDebitHours": _median_credit_to_debit_hours(
            order_ts, gs["Entry"].to_numpy(), span_hours
        ),
        "postDormancyBurstFrac": _post_dormancy_burst_frac(order_ts, n),
    }


def aggregate_features(txns: pd.DataFrame) -> pd.DataFrame:
    """One feature row per AlertID (indexed by AlertID)."""
    rows = {aid: _features_for_alert(g) for aid, g in txns.groupby("AlertID")}
    return pd.DataFrame.from_dict(rows, orient="index")[FEATURE_COLUMNS]


def stratified_split(labels: pd.DataFrame, holdout_frac: float, seed: int):
    """Split AlertIDs into (working_ids, holdout_ids), stratified on Outcome so
    both sets preserve the reported ratio. Deterministic for a given seed.
    """
    rng = np.random.RandomState(seed)
    holdout: list = []
    for _, group in labels.groupby("Outcome"):
        ids = group["AlertID"].to_numpy()
        ids = rng.permutation(ids)
        n_holdout = round(len(ids) * holdout_frac)
        holdout.extend(ids[:n_holdout].tolist())
    holdout_set = set(holdout)
    working = [a for a in labels["AlertID"].tolist() if a not in holdout_set]
    return working, holdout


def build(synthaml_dir: str | Path, out_dir: str | Path, holdout_frac: float = 0.8,
          seed: int = RANDOM_SEED) -> pd.DataFrame:
    """One-time build: stream the raw CSVs, write alert_features.csv +
    holdout_alert_ids.json. I/O wrapper over the tested pure functions.
    """
    synthaml_dir, out_dir = Path(synthaml_dir), Path(out_dir)
    txns = pd.read_csv(
        synthaml_dir / "synthetic_transactions.csv",
        dtype={"AlertID": "int32", "Entry": "category", "Type": "category", "Size": "float32"},
        parse_dates=["Timestamp"],
    )
    feats = aggregate_features(txns)
    feats.index.name = "AlertID"
    feats.to_csv(out_dir / "alert_features.csv")

    alerts = pd.read_csv(synthaml_dir / "synthetic_alerts.csv")
    _, holdout = stratified_split(alerts[["AlertID", "Outcome"]], holdout_frac, seed)
    (out_dir / "holdout_alert_ids.json").write_text(json.dumps(sorted(int(x) for x in holdout)))
    return feats


if __name__ == "__main__":
    build("data/synthaml", "data")
    print("built data/alert_features.csv and data/holdout_alert_ids.json")

