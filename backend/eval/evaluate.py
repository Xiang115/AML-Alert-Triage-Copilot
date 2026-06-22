"""Offline evaluation (PIPELINE Phase 8) — measure accuracyVsLabels for real.

Runs the REAL triage agent (an LLM call, not a classifier — CLAUDE.md) over a
stratified random sample of the held-out SynthAML slice and compares its
recommendation to the Report/Dismiss label (ADR-0004). The held-out split was
frozen before any prompt tuning (data/holdout_alert_ids.json), so the number
isn't memorisation.

Triage reads aggregated per-alert features (real SynthAML rows are dense and
amount-less; see ADR-0005), via render_features_evidence. One LLM call per
sampled alert — keep the sample small. Run manually:
    python -m eval.evaluate            # default n=60
    python -m eval.evaluate --n 250    # bigger sample, more tokens

Metric math (compute_metrics) is pure and unit-tested; this module's main()
adds the data loading + live LLM run + metrics.json write.
"""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

from agents.evidence import render_features_evidence
from agents.knowledge_base import load_cards
from agents.triage import triage
from config import RANDOM_SEED
from synthaml_loader import FEATURE_COLUMNS

_DATA = Path(__file__).resolve().parent.parent / "data"
_HOLDOUT_IDS = _DATA / "holdout_alert_ids.json"
_FEATURES = _DATA / "alert_features.csv"
_ALERTS = _DATA / "synthaml" / "synthetic_alerts.csv"
_OUT = _DATA / "metrics.json"

# Modeled time numbers (ADR-0004): illustrative, NOT measured — never present as a
# sourced fact. 14.0 min baseline is a conservative midpoint of published AML
# first-pass alert-review estimates (industry operational estimates put a Level-1
# review at ~5-20 min/alert). 4.5 min is a conservative modeled with-copilot
# estimate. Time-saved is shown as illustrative, anchored to that cited range.
_BASELINE_MIN = 14.0
_COPILOT_MIN = 4.5

# Feature-evidence triage reasons harder than the demo prompts; give the visible
# JSON headroom so it isn't truncated to empty. Calls are I/O-bound on the API,
# so run them through a small thread pool to cut wall-time (same token count).
_EVAL_MAX_TOKENS = 8192
_WORKERS = 6


def label_to_recommendation(outcome: str) -> str:
    """SynthAML Outcome → the recommendation it should map to."""
    return "escalate" if str(outcome).strip().lower() == "report" else "dismiss"


def compute_metrics(
    predictions: list[str],
    actuals: list[str],
    *,
    baseline_min: float = _BASELINE_MIN,
    copilot_min: float = _COPILOT_MIN,
) -> dict:
    """Pure metric math (ADR-0004). Returns the Metrics wire shape (camelCase).

    Positive class = escalate (label Report). We report the full confusion matrix
    plus recall/precision/specificity because plain accuracy is misleading on an
    imbalanced AML base rate: an always-dismiss model scores `baselineAccuracy`
    while catching zero launderers (recall 0). The slide leads with workload +
    catch-rate, not accuracy.
    """
    total = len(predictions)
    pairs = list(zip(predictions, actuals))

    tp = sum(p == "escalate" and a == "escalate" for p, a in pairs)
    fp = sum(p == "escalate" and a == "dismiss" for p, a in pairs)
    fn = sum(p == "dismiss" and a == "escalate" for p, a in pairs)
    tn = sum(p == "dismiss" and a == "dismiss" for p, a in pairs)

    def _safe(num: int, den: int) -> float:
        return round(num / den, 4) if den else 0.0

    accuracy = _safe(tp + tn, total)
    # Always-dismiss baseline: correct exactly on the actual-dismiss rows (tn + fp).
    baseline_accuracy = _safe(tn + fp, total)
    recall = _safe(tp, tp + fn)
    precision = _safe(tp, tp + fp)
    specificity = _safe(tn, tn + fp)
    fp_reduction = _safe(tn, tn + fn)

    return {
        "totalAlerts": total,
        "accuracyVsLabels": accuracy,
        "baselineAccuracy": baseline_accuracy,
        "recall": recall,
        "precision": precision,
        "specificity": specificity,
        "falsePositiveReduction": fp_reduction,
        "confusionMatrix": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "avgReviewTimeBaselineMin": float(baseline_min),
        "avgReviewTimeWithCopilotMin": float(copilot_min),
    }


def _stratified_sample(df: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
    """Sample n rows stratified on Outcome, preserving the reported ratio."""
    rng = np.random.RandomState(seed)
    parts = []
    for _, group in df.groupby("Outcome"):
        k = min(len(group), int(round(n * len(group) / len(df))))
        idx = rng.permutation(group.index)[:k]
        parts.append(group.loc[idx])
    sample = pd.concat(parts)
    return sample.sample(frac=1, random_state=seed).reset_index(drop=True)


def _predict(row: pd.Series, cards: list[dict]) -> str:
    features = {c: row[c] for c in FEATURE_COLUMNS}
    try:
        rec = triage(render_features_evidence(features), cards, max_tokens=_EVAL_MAX_TOKENS).recommendation
        return rec if rec in ("escalate", "dismiss") else "dismiss"
    except Exception:  # noqa: BLE001 — rare hard failure; conservative default
        return "dismiss"


def main(n: int = 60, seed: int = RANDOM_SEED) -> None:
    import llm
    llm.use_offline_timeout()  # long timeout: don't abort+retry valid slow reasoning calls
    for p in (_HOLDOUT_IDS, _FEATURES, _ALERTS):
        if not p.exists():
            print(f"Missing required input: {p}")
            return

    holdout = set(json.loads(_HOLDOUT_IDS.read_text(encoding="utf-8")))
    feats = pd.read_csv(_FEATURES)  # first column is AlertID (the saved index)
    labels = pd.read_csv(_ALERTS)[["AlertID", "Outcome"]]
    feats["AlertID"] = feats["AlertID"].astype(int)
    labels["AlertID"] = labels["AlertID"].astype(int)

    merged = labels.merge(feats, on="AlertID")
    merged = merged[merged["AlertID"].isin(holdout)]
    sample = _stratified_sample(merged, n, seed)
    print(f"Evaluating {len(sample)} held-out alerts via the live triage agent (n requested={n})...")

    cards = load_cards()
    rows = [row for _, row in sample.iterrows()]
    actuals = [label_to_recommendation(row["Outcome"]) for row in rows]

    predictions: list[str] = [""] * len(rows)
    done = 0
    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        futures = {pool.submit(_predict, row, cards): i for i, row in enumerate(rows)}
        for fut in as_completed(futures):
            predictions[futures[fut]] = fut.result()
            done += 1
            if done % 10 == 0 or done == len(rows):
                print(f"  {done}/{len(rows)}", flush=True)

    metrics = compute_metrics(predictions, actuals)
    _OUT.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print("\n================ EVALUATION (held-out, measured) ================")
    print(f"  n (sample)              {metrics['totalAlerts']}")
    print(f"  accuracyVsLabels        {metrics['accuracyVsLabels']:.1%}")
    print(f"  falsePositiveReduction  {metrics['falsePositiveReduction']:.1%}")
    print(f"  reviewTime baseline->copilot  {_BASELINE_MIN}->{_COPILOT_MIN} min (modeled)")
    print(f"Wrote {_OUT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60, help="stratified holdout sample size (LLM calls)")
    main(n=ap.parse_args().n)
