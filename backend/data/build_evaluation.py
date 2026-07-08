"""Materialize the held-out evaluation SET for the dashboard (token-free).

The accuracy in metrics.json is measured over the first N SAML-D held-out alerts (ADR-0012).
Those alerts + their ground-truth labels already live in saml_d_holdout.json — this surfaces
them (a compact per-alert summary, NOT the per-alert AI call, which would cost a re-run) so the
250-alert measurement is visible and inspectable in the dashboard instead of hidden behind a
single percentage. Pure/deterministic — reads existing files, runs no model.

    cd backend && .venv/Scripts/python.exe data/build_evaluation.py
"""

from __future__ import annotations

import json
from pathlib import Path

_DATA = Path(__file__).resolve().parent
_HOLDOUT = _DATA / "saml_d_holdout.json"
_METRICS = _DATA / "metrics.json"
_OUT = _DATA / "evaluation.json"
_N = 250  # must match eval.evaluate_samld's default n (the slice metrics.json is measured over)


def _summary(alert: dict, meta: dict) -> dict:
    txns = alert.get("transactions") or []
    return {
        "alertId": alert["alertId"],
        "riskScore": alert.get("riskScore"),
        "txnCount": len(txns),
        "inCount": sum(1 for t in txns if t.get("direction") == "inbound"),
        "outCount": sum(1 for t in txns if t.get("direction") == "outbound"),
        "totalAmount": round(sum(t.get("amount", 0) for t in txns), 2),
        "typology": meta.get("typology"),
        "coverageGap": bool(meta.get("coverageGap")),
        "label": meta["outcome"],  # ground-truth: escalate (Report) | dismiss
    }


def build() -> dict:
    blob = json.loads(_HOLDOUT.read_text(encoding="utf-8"))
    alerts, metas = blob["alerts"][:_N], blob["meta"][:_N]
    rows = [_summary(a, m) for a, m in zip(alerts, metas)]
    labels = {"escalate": sum(r["label"] == "escalate" for r in rows),
              "dismiss": sum(r["label"] == "dismiss" for r in rows)}
    metrics = json.loads(_METRICS.read_text(encoding="utf-8")) if _METRICS.exists() else {}
    out = {
        "n": len(rows),
        "accuracyVsLabels": metrics.get("accuracyVsLabels"),
        "recall": metrics.get("recall"),
        "precision": metrics.get("precision"),
        "labelDistribution": labels,
        # NOTE: no per-alert AI call yet — that is the (a) path (one eval re-run). This is (b):
        # the held-out set + ground-truth labels made visible, token-free.
        "alerts": rows,
    }
    _OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(rows)} held-out alerts -> {_OUT.name} "
          f"(labels: {labels['escalate']} report / {labels['dismiss']} dismiss)")
    return out


if __name__ == "__main__":
    build()
