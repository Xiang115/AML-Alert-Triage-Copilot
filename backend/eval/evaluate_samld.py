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
from agents.pipeline import run_triage
from agents.queue_agent import auto_clear_policy
from agents.triage import NO_MATCH_CODE, triage
from agents.verifier import verify
from eval.evaluate import auto_clear_metrics, compute_metrics, drop_error_predictions
from schemas import AlertInput

_DATA = Path(__file__).resolve().parent.parent / "data"
_HOLDOUT = _DATA / "saml_d_holdout.json"
_OUT = _DATA / "saml_d_metrics.json"
_SERVED = _DATA / "metrics.json"  # what GET /metrics serves (ADR-0012: the SAML-D result)
_EVAL_MAX_TOKENS = 8192
_MAX_ATTEMPTS = 2

# Combined typology coverage across BOTH real public sets (ADR-0012): SAML-D carries amount +
# counterparty, so PT-01/FI-01/ST-01 are measured here; DA-01 is measured on SynthAML (timing
# features). KYC-01 stays the honest residual — no public set carries the declared customer
# profile it needs. measured XOR roadmap, and together they partition the 5-card KB.
SAMLD_MEASURED_TYPOLOGIES = ("PT-01", "FI-01", "ST-01", "DA-01")
SAMLD_ROADMAP_TYPOLOGIES = ("KYC-01",)
SAMLD_COVERAGE_NOTE = (
    "Measured on real held-out SAML-D alerts (Oztas et al., 2023), which carry transaction "
    "amount + counterparty — so FI-01 (fan-in) and ST-01 (structuring), structurally "
    "unmeasurable on SynthAML's amount-less features, are measured for real here and are the "
    "strongest detectors. Across SAML-D + SynthAML, 4 of 5 curated FATF/BNM cards are now "
    "measured (PT-01/FI-01/ST-01 on SAML-D, DA-01 on SynthAML); KYC-01 is the honest residual "
    "— no public dataset carries the declared customer profile it needs. Reports whose pattern "
    "matches no card (the coverage gap) score far lower recall, confirming patterns outside the "
    "5-card KB are correctly not caught. The held-out slice is report-enriched (~60% positive) "
    "for measurement power, so accuracy and precision reflect that mix, not the real ~0.1% base "
    "rate — recall and per-typology recall are the mix-independent truths; lead with those."
)


def served_metrics_from_samld(samld: dict) -> dict:
    """Transform the raw SAML-D eval (`saml_d_metrics.json`) into the served `metrics.json`
    wire shape (ADR-0012). Pure, token-free, deterministic — locks the recorded numbers
    instead of re-running (DeepSeek is non-deterministic even at temp 0, ADR-0012/0003).

    Keeps every Metrics wire field + `perTypologyRecall`, drops the eval-only `nExcludedErrors`,
    and merges the combined SAML-D+SynthAML coverage disclosure. Validates against the `Metrics`
    contract (`extra="forbid"`) before returning, so a stray key fails fast here."""
    from schemas import Metrics

    served = {k: v for k, v in samld.items() if k != "nExcludedErrors"}
    served["measuredTypologies"] = list(SAMLD_MEASURED_TYPOLOGIES)
    served["roadmapTypologies"] = list(SAMLD_ROADMAP_TYPOLOGIES)
    served["coverageNote"] = SAMLD_COVERAGE_NOTE
    Metrics.model_validate(served)  # fail fast if the raw file gained a field the contract forbids
    return served


def write_served_metrics() -> None:
    """Regenerate the served `data/metrics.json` from the locked `saml_d_metrics.json`. No LLM
    run — run standalone with `python -m eval.evaluate_samld --served-only` after a measurement."""
    if not _OUT.exists():
        print(f"Missing {_OUT} — run `python -m eval.evaluate_samld` first.")
        return
    samld = json.loads(_OUT.read_text(encoding="utf-8"))
    _SERVED.write_text(json.dumps(served_metrics_from_samld(samld), indent=2), encoding="utf-8")
    print(f"Wrote {_SERVED} (served SAML-D metrics) from {_OUT.name}")


def _predict(alert_dict: dict, cards, debate: bool = False) -> tuple[str, str]:
    """Run one SAML-D alert and return (recommendation, routing); ("error","error") on a
    persistent failure so the row is EXCLUDED rather than scored as a dismiss (ADR-0004).

    Default = triage -> verifier -> confidence -> Auto-Clear (same operating point as
    eval.evaluate, so SynthAML/SAML-D are comparable). `debate=True` runs the FULL production
    pipeline incl. the adversarial debate + concession gate (ADR-0011/0012) — use it to measure
    the production-path recall and confirm the gate stops the debate dropping true reports."""
    alert = AlertInput.model_validate(alert_dict)
    for attempt in range(_MAX_ATTEMPTS):
        try:
            if debate:
                res = run_triage(alert, cost_sensitive=True)
                return res.recommendation, auto_clear_policy(
                    res.recommendation, res.confidence, res.verifier.status, config.AUTO_CLEAR_THRESHOLD)
            evidence = render_alert_evidence(alert)
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


def main(n: int = 250, workers: int = 24, debate: bool = False) -> None:
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
    mode = "full pipeline incl. debate+gate" if debate else "triage+verifier"
    print(f"Evaluating {len(alerts)} SAML-D held-out alerts ({mode}, {workers} workers)...", flush=True)

    results: list[tuple[str, str]] = [("error", "error")] * len(alerts)
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(_predict, a, cards, debate): i for i, a in enumerate(alerts)}
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
    # Keep the canonical no-debate metric separate from the production-path (with-debate) number.
    out = _DATA / ("saml_d_metrics_debate.json" if debate else "saml_d_metrics.json")
    out.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    # The no-debate run is the served held-out result (ADR-0012); refresh metrics.json from it.
    if not debate:
        write_served_metrics()

    print("\n==== SAML-D HELD-OUT (measured, rich evidence) ====")
    for k in ("totalAlerts", "accuracyVsLabels", "baselineAccuracy", "recall", "precision",
              "falsePositiveReduction", "autoClearedShare", "autoClearPrecision"):
        print(f"  {k:24} {metrics[k]}")
    print(f"  confusion                {metrics['confusionMatrix']}  (excluded {n_excl})")
    print("  per-typology recall (Reports):")
    for k, v in sorted(metrics["perTypologyRecall"].items()):
        print(f"    {k:14} {v['recall']}  ({v['caught']}/{v['total']})")
    print(f"Wrote {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=250, help="cap alerts (0=all)")
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--debate", action="store_true",
                    help="run the FULL pipeline incl. adversarial debate + concession gate (ADR-0012)")
    ap.add_argument("--served-only", action="store_true",
                    help="no LLM run: just rebuild the served metrics.json from the locked "
                         "saml_d_metrics.json (ADR-0012 numbers stay locked)")
    args = ap.parse_args()
    if args.served_only:
        write_served_metrics()
    else:
        main(args.n, args.workers, debate=args.debate)
