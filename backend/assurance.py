"""Auto-clear assurance (ADR-0019) — measuring and controlling the failure mode of autonomy.

An autonomous triage agent that auto-clears alerts (ADR-0010) lives or dies on one question a
model-risk committee or a regulator asks first: *how do you know you are not auto-clearing real
laundering?* This module answers it two ways, both grounded in real data, no fabrication:

- `auto_clear_leakage` — the FALSE-NEGATIVE LEAKAGE on the held-out slice, derived **token-free**
  from the already-locked aggregates (`autoClearedShare`, `autoClearPrecision`, `confusionMatrix`
  in metrics.json). It reports P(auto-cleared | true Report) — the share of true reports the agent
  would silently clear. That rate is **mix-independent** (like recall), so it is the honest headline;
  auto-clear *precision* moves with the base rate. Deriving it respects the ADR-0012 lock (re-running
  the eval drifts the numbers — DeepSeek is non-deterministic even at temp 0).

- `select_qa_sample` — the operational CONTROL: a risk-weighted sample of auto-cleared alerts routed
  for human QA spot-check. Ranked by **marginal confidence** (closest to the auto-clear threshold
  first) — the least-sure clears, where leakage hides. Deterministic (demo-stable, ADR-0003).

Pure module: no I/O, no LLM.
"""

from __future__ import annotations

import math


def auto_clear_leakage(metrics: dict) -> dict:
    """Derive the auto-clear false-negative leakage from the locked held-out aggregates.

    auto-cleared reports = auto-cleared count - benign auto-cleared (the docstring of
    `eval.evaluate.auto_clear_metrics` names this residual the 'catastrophic misses').
    `autoClearLeakageRate` = auto-cleared reports / all true reports = P(auto-cleared | Report),
    mix-independent."""
    cm = metrics["confusionMatrix"]
    n = cm["tp"] + cm["fp"] + cm["fn"] + cm["tn"]
    auto_cleared = round(metrics["autoClearedShare"] * n)
    benign = round(metrics["autoClearPrecision"] * auto_cleared)
    leaked = max(0, auto_cleared - benign)
    total_reports = cm["tp"] + cm["fn"]
    rate = round(leaked / total_reports, 4) if total_reports else 0.0
    return {
        "autoClearedReports": leaked,
        "totalReports": total_reports,
        "autoClearLeakageRate": rate,
    }


def is_borderline_dismiss(triage: dict, review_threshold: float, margin: float) -> bool:
    """Whether a dismiss is 'borderline' (ADR-0020) — the dismisses most at risk of a wrong clear:
    barely above the review floor (confidence <= review_threshold + margin) OR contested (the
    verifier flagged it, or it went to an adversarial debate). A confident, uncontested dismiss
    (e.g. a clean 1.0 no-match) is NOT borderline. Escalations are never borderline."""
    if triage.get("recommendation") != "dismiss":
        return False
    if triage.get("confidence", 1.0) <= review_threshold + margin:
        return True
    if (triage.get("verifier") or {}).get("status") == "flagged":
        return True
    return bool(triage.get("debate"))


def select_qa_sample(alerts: list[dict], rate: float) -> set[str]:
    """The risk-weighted QA sample among auto-cleared alerts (camelCase alert dicts).

    Ranks auto-cleared alerts by marginal confidence (ascending — closest to the auto-clear
    threshold first), tie-breaking on higher riskScore then alertId for determinism, and takes
    the top `ceil(rate * n)` (at least 1 when any are auto-cleared). Pure and deterministic."""
    cleared = [a for a in alerts if a.get("routing") == "autoCleared"]
    if not cleared:
        return set()
    ranked = sorted(
        cleared,
        key=lambda a: (a["triage"]["confidence"], -a.get("riskScore", 0), a["alertId"]),
    )
    k = max(1, math.ceil(rate * len(cleared)))
    return {a["alertId"] for a in ranked[:k]}
