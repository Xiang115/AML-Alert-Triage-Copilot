"""Closed-loop suppression measurement (ADR-0021) — the leakage/coverage frontier.

Answers: if the analyst's benign clearances auto-clear future look-alikes off the worklist,
how much true laundering does that loop wrongly suppress (**false-suppression / leakage**), and
how much of the queue does it clear (**coverage**)?

Honest protocol (mirrors the label-blind, no-sweep discipline of ADR-0012/0014):
- Join the 250-alert labelled held-out slice (`evaluation.json`, ground-truth `label`) to its rich
  transactions (`saml_d_holdout.json`) by `alertId`.
- Build a STRUCTURAL behavioural envelope per alert from transactions ONLY — reusing the production
  primitive `activity_profile.compute_activity_profile` for the ledger tells (drain-to-~0, cross-border
  / cash share, counterparty concentration). **No label is ever read to decide a suppression.**
- **Leave-one-out:** alert i is auto-suppressed iff its envelope bucket has >= MIN_BENIGN benign
  precedents among the OTHER alerts (and, if the config requires it, zero laundering precedents). i's
  own label is read ONLY at scoring. Seeding from ground-truth-benign isolates the loop's own
  propagation leakage assuming the human seeds correctly.
- No per-alert timestamp exists, so this is leave-one-out CROSS-VALIDATION, not a temporal replay.

Why token-free: unlike `evaluate_samld` (which runs the triage agent), this is a pure structural +
label computation — deterministic, reproducible, costs nothing, and cannot drift.

**The operating point is PRE-REGISTERED a priori** (declared below, NOT chosen by scanning the test
set): the tightest envelope (all structural features) requiring a pure-benign precedent bucket. We
report that fixed config's cross-validated leakage + coverage with a confidence interval, PLUS a
split-validation robustness check (pick on validation, report on test) to show we did not tune on the
test set, PLUS the full exploratory frontier for context. Per ADR-0021 decision A, **the frontier +
the data-volume caveat is the headline, not a bare <=1%** — at N~100 benign, <=1% is not certifiable.

Run from backend/ (venv active):  python -m eval.evaluate_suppression
"""
from __future__ import annotations

import collections
import json
import math
from pathlib import Path

from agents.envelope import envelope_features

_DATA = Path(__file__).resolve().parent.parent / "data"
_EVAL = _DATA / "evaluation.json"
_HOLDOUT = _DATA / "saml_d_holdout.json"
_OUT = _DATA / "suppression_metrics.json"

# Feature-set ladder: coarse -> fine. amt+dir+typ is the base; each step adds a ledger tell.
_FEATURE_SETS = [
    ["typ", "amt", "dir"],
    ["typ", "amt", "dir", "drain"],
    ["typ", "amt", "dir", "drain", "conc"],
    ["typ", "amt", "dir", "drain", "conc", "xb"],
    ["typ", "amt", "dir", "drain", "conc", "xb", "cash"],
    ["typ", "amt", "dir", "drain", "conc", "xb", "cash", "ntxn"],
]
# The pre-registered operating point, fixed a priori by PRINCIPLE (tightest envelope + pure precedent).
_OPERATING_POINT = {"features": _FEATURE_SETS[-1], "min_benign": 1, "require_pure": True}
# The naive strawman we improve on (coarse envelope, any cleared bucket) — the ~15% talking point.
_NAIVE = {"features": _FEATURE_SETS[0], "min_benign": 1, "require_pure": False}


def envelope(eval_alert: dict, txns: list[dict]) -> dict:
    """Structural, label-free behavioural envelope — the SAME definition the live app keys on
    (`agents.envelope.envelope_features`), so the mechanism we ship is the mechanism we measure here.
    The eval passes the dataset's ground-truth typology for a label-blind measurement; the live app
    passes the model's verifier-checked matched-typology code."""
    return envelope_features(
        typology=eval_alert.get("typology"),
        total_amount=float(eval_alert.get("totalAmount", 0.0)),
        in_count=eval_alert.get("inCount", 0),
        out_count=eval_alert.get("outCount", 0),
        transactions=txns,
    )


def _sig(env: dict, feats: list[str]) -> tuple:
    return tuple(env[f] for f in feats)


def _wilson_upper(k: int, n: int) -> float:
    """95% upper bound on a proportion. Rule of three when k==0 (Wilson degenerates there)."""
    if n == 0:
        return float("nan")
    if k == 0:
        return 3.0 / n
    z = 1.96
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (centre + half) / denom


def _loo(env_labels: list[tuple[dict, str]], feats: list[str], min_benign: int, pure: bool) -> dict:
    """Leave-one-out: suppress alert i on OTHER alerts' benign precedents; score on i's own label."""
    buckets: dict[tuple, list[str]] = collections.defaultdict(list)
    for env, lab in env_labels:
        buckets[_sig(env, feats)].append(lab)
    suppressed = leaked = 0
    for env, lab in env_labels:
        members = buckets[_sig(env, feats)]
        # counts excluding self (remove one instance of this alert's own label)
        benign = members.count("dismiss") - (1 if lab == "dismiss" else 0)
        launder = members.count("escalate") - (1 if lab == "escalate" else 0)
        if benign >= min_benign and (not pure or launder == 0):
            suppressed += 1
            leaked += lab == "escalate"
    n = len(env_labels)
    leak = leaked / suppressed if suppressed else 0.0
    return {
        "features": feats, "minBenign": min_benign, "requirePure": pure,
        "suppressed": suppressed, "leaked": leaked,
        "coverage": round(suppressed / n, 4),
        "leakage": round(leak, 4),
        "leakage95Upper": round(_wilson_upper(leaked, suppressed), 4),
    }


def _split_check(env_labels: list[tuple[dict, str]], cfg: dict) -> dict:
    """Robustness: train buckets on one deterministic half, report the pre-registered config on the
    other (both directions). Demonstrates the operating point is not tuned on the reported data."""
    a, b = env_labels[0::2], env_labels[1::2]

    def report(train, test) -> dict:
        buckets: dict[tuple, list[str]] = collections.defaultdict(list)
        for env, lab in train:
            buckets[_sig(env, cfg["features"])].append(lab)
        suppressed = leaked = 0
        for env, lab in test:
            members = buckets.get(_sig(env, cfg["features"]), [])
            benign, launder = members.count("dismiss"), members.count("escalate")
            if benign >= cfg["min_benign"] and (not cfg["require_pure"] or launder == 0):
                suppressed += 1
                leaked += lab == "escalate"
        leak = leaked / suppressed if suppressed else 0.0
        return {"suppressed": suppressed, "leaked": leaked,
                "coverage": round(suppressed / len(test), 4), "leakage": round(leak, 4),
                "leakage95Upper": round(_wilson_upper(leaked, suppressed), 4)}

    return {"trainA_reportB": report(a, b), "trainB_reportA": report(b, a)}


def main() -> int:
    ev = {a["alertId"]: a for a in json.loads(_EVAL.read_text(encoding="utf-8"))["alerts"]}
    ho = {a["alertId"]: a for a in json.loads(_HOLDOUT.read_text(encoding="utf-8"))["alerts"]}
    ids = sorted(i for i in ev if i in ho)
    env_labels = [(envelope(ev[i], ho[i]["transactions"]), ev[i]["label"]) for i in ids]
    n_launder = sum(1 for _, l in env_labels if l == "escalate")
    print(f"joined labelled+txn alerts: {len(ids)}  ({n_launder} escalate / {len(ids)-n_launder} dismiss)")

    frontier = [
        _loo(env_labels, feats, mb, pure)
        for feats in _FEATURE_SETS for mb in (1, 2, 3) for pure in (False, True)
    ]
    naive = _loo(env_labels, _NAIVE["features"], _NAIVE["min_benign"], _NAIVE["require_pure"])
    op = _loo(env_labels, _OPERATING_POINT["features"], _OPERATING_POINT["min_benign"],
              _OPERATING_POINT["require_pure"])
    split = _split_check(env_labels, _OPERATING_POINT)

    headline = (
        f"Naive coarse-envelope self-suppression leaks {naive['leakage']:.0%} of laundering "
        f"({naive['leaked']}/{naive['suppressed']}). The pre-registered firewall envelope collapses that "
        f"to {op['leakage']:.1%} ({op['leaked']}/{op['suppressed']}) at {op['coverage']:.0%} coverage - "
        f"but at N~{len(ids)-n_launder} benign the 95% upper bound is {op['leakage95Upper']:.0%}, so we "
        f"report the frontier and state plainly that certifying <=1% is a labelled-data-volume problem, "
        f"solved by the confirmed-SAR feedback loop, not a design gap."
    )
    out = {
        "n": len(ids), "nBenign": len(ids) - n_launder, "nLaundering": n_launder,
        "method": ("leave-one-out cross-validation, label-blind (label read only at scoring); "
                   "envelope from compute_activity_profile; token-free/deterministic (ADR-0021)"),
        "naiveBaseline": naive,
        "operatingPoint": {**op, "preRegistered": True,
                           "rationale": "tightest envelope + pure-benign precedent, fixed a priori"},
        "splitValidation": split,
        "frontier": frontier,
        "headline": headline,
        "caveat": ("<=1% is aspirational, not certified: ~100 benign held-out alerts cap the CI; the "
                   "leaked laundering overlaps the triage model's own false negatives, so the "
                   "dismiss+agreed gate does not clearly purify further. Frontier is the honest artifact."),
    }
    _OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")

    print(f"\nNAIVE  {naive['features']}: leakage {naive['leakage']:.1%} "
          f"({naive['leaked']}/{naive['suppressed']}), coverage {naive['coverage']:.0%}")
    print(f"OP*    {op['features']}\n       pre-registered: leakage {op['leakage']:.1%} "
          f"({op['leaked']}/{op['suppressed']}), coverage {op['coverage']:.0%}, "
          f"95%-upper {op['leakage95Upper']:.0%}")
    print(f"SPLIT  A->B leakage {split['trainA_reportB']['leakage']:.1%} "
          f"({split['trainA_reportB']['leaked']}/{split['trainA_reportB']['suppressed']}) | "
          f"B->A leakage {split['trainB_reportA']['leakage']:.1%} "
          f"({split['trainB_reportA']['leaked']}/{split['trainB_reportA']['suppressed']})")
    print(f"\nwrote {_OUT.name}\nHEADLINE: {headline}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
