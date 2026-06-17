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
]

_DAY = 86400.0


def _features_for_alert(g: pd.DataFrame) -> dict:
    ts = pd.to_datetime(g["Timestamp"]).sort_values()
    n = len(g)
    credit = (g["Entry"] == "Credit").sum()
    debit = n - credit
    types = g["Type"].value_counts()
    signed = g["Size"].where(g["Entry"] == "Credit", -g["Size"])
    gaps = ts.diff().dropna().dt.total_seconds() / _DAY
    per_day = ts.dt.floor("D").value_counts()
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

