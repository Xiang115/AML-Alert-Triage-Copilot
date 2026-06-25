"""Held-out evaluation on SAML-D (ADR-0012) — the REAL-data measurement.

Unlike SynthAML (amount-less feature aggregates, ADR-0004/0005), SAML-D alerts carry
amount + counterparty, so the pipeline runs on the rich `render_alert_evidence` path and
FI-01/ST-01/PT-01 can actually fire. Reports overall metrics PLUS per-typology recall and
the quantified coverage gap (typologies our 5-card KB doesn't describe).

Reuses the pure, unit-tested metric math from `eval.evaluate`. Runs the live triage agent
+ verifier (NOT the adversarial debate — same operating point as eval.evaluate, so the two
datasets are comparable; the debate further lowers matched-card recall, see ADR-0012).

Run from backend/ (venv active):
    python -m eval.evaluate_samld            # n=250, 24 workers
    python -m eval.evaluate_samld --n 120 --workers 16
"""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import config
import llm
from agents.confidence import compute_confidence
from agents.evidence import render_alert_evidence
from agents.knowledge_base import get_card, load_cards
from agents.queue_agent import auto_clear_policy
from agents.triage import NO_MATCH_CODE, triage
from agents.verifier import verify
from eval.evaluate import auto_clear_metrics, compute_metrics, drop_error_predictions
from schemas import AlertInput

_DATA = Path(__file__).resolve().parent.parent / "data"
_HOLDOUT = _DATA / "saml_d_holdout.json"
_OUT = _DATA / "saml_d_metrics.json"
_EVAL_MAX_TOKENS = 8192
_MAX_ATTEMPTS = 2


def _predict(alert_dict: dict, cards) -> tuple[str, str]:
    """Run one SAML-D alert through triage -> verifier -> confidence -> Auto-Clear Policy,
    on the rich evidence path. Returns (recommendation, routing); ("error","error") on a
    persistent failure so the row is EXCLUDED rather than scored as a dismiss (ADR-0004)."""
    alert = AlertInput.model_validate(alert_dict)
    evidence = render_alert_evidence(alert)
    for attempt in range(_MAX_ATTEMPTS):
        try:
            tri = triage(evidence, cards, max_tokens=_EVAL_MAX_TOKENS, cost_sensitive=True)
            rec = tri.recommendation if tri.recommendation in ("escalate", "dismiss") else "dismiss"
            if tri.matched_typology.code == NO_MATCH_CODE:
                conf = compute_confidence(0, 0, "dismiss", verifier_flagged=False)
                vstatus = "agreed"
            else:
                card = get_card(tri.matched_typology.code)
                vstatus = verify(evidence, rec, card).status
                conf = compute_confidence(len(tri.fired_indicators), len(card.indicators), rec,
                                          verifier_flagged=vstatus == "flagged")
            return rec, auto_clear_policy(rec, conf, vstatus, config.AUTO_CLEAR_THRESHOLD)
        except Exception:  # noqa: BLE001 — retry transient API/JSON-truncation errors, then exclude
            if attempt + 1 >= _MAX_ATTEMPTS:
                return "error", "error"
    return "error", "error"


def per_typology_recall(meta: list[dict], predictions: list[str]) -> dict:
    """Recall within each true typology (Reports only): caught / total. Coverage-gap Reports
    (no card maps) are bucketed separately — their low recall quantifies the KB-coverage limit.
    Pure: testable without tokens."""
    buckets: dict[str, dict] = {}
    for m, rec in zip(meta, predictions):
        if m["outcome"] != "escalate" or rec == "error":
            continue
        key = m["typology"] or ("COVERAGE_GAP" if m.get("coverageGap") else "UNMAPPED")
        b = buckets.setdefault(key, {"caught": 0, "total": 0})
        b["total"] += 1
        b["caught"] += rec == "escalate"
    return {k: {"recall": round(v["caught"] / v["total"], 4) if v["total"] else None,
                "caught": v["caught"], "total": v["total"]} for k, v in buckets.items()}


def main(n: int = 250, workers: int = 24) -> None:
    llm.use_offline_timeout()
    if not _HOLDOUT.exists():
        print(f"Missing {_HOLDOUT} — run `python -m data.saml_d_loader` first.")
        return
    blob = json.loads(_HOLDOUT.read_text(encoding="utf-8"))
    alerts, meta = blob["alerts"], blob["meta"]
    if n and n < len(alerts):
        alerts, meta = alerts[:n], meta[:n]
    cards = load_cards()
    actuals = [m["outcome"] for m in meta]
    print(f"Evaluating {len(alerts)} SAML-D held-out alerts (rich evidence, {workers} workers)...", flush=True)

    results: list[tuple[str, str]] = [("error", "error")] * len(alerts)
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(_predict, a, cards): i for i, a in enumerate(alerts)}
        for fut in as_completed(futs):
            results[futs[fut]] = fut.result()
            done += 1
            if done % 25 == 0 or done == len(alerts):
                print(f"  {done}/{len(alerts)}", flush=True)

    preds = [r for r, _ in results]
    routings = [rt for _, rt in results]
    p, a, n_excl = drop_error_predictions(preds, actuals)
    _, kept_routings, _ = drop_error_predictions(preds, routings)
    metrics = compute_metrics(p, a)
    metrics.update(auto_clear_metrics(kept_routings, a))
    metrics["perTypologyRecall"] = per_typology_recall(meta, preds)
    metrics["nExcludedErrors"] = n_excl
    _OUT.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print("\n==== SAML-D HELD-OUT (measured, rich evidence) ====")
    for k in ("totalAlerts", "accuracyVsLabels", "baselineAccuracy", "recall", "precision",
              "falsePositiveReduction", "autoClearedShare", "autoClearPrecision"):
        print(f"  {k:24} {metrics[k]}")
    print(f"  confusion                {metrics['confusionMatrix']}  (excluded {n_excl})")
    print("  per-typology recall (Reports):")
    for k, v in sorted(metrics["perTypologyRecall"].items()):
        print(f"    {k:14} {v['recall']}  ({v['caught']}/{v['total']})")
    print(f"Wrote {_OUT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=250, help="cap alerts (0=all)")
    ap.add_argument("--workers", type=int, default=24)
    args = ap.parse_args()
    main(args.n, args.workers)
