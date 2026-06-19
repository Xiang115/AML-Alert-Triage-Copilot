"""Offline precompute (build tool, NOT an endpoint) — see CLAUDE.md > Architecture.

Runs the full agent pipeline over the hand-crafted demo queue + hero cases and
writes `results.json`, which FastAPI loads on startup and serves from memory.
Run manually:  python -m data.precompute   (from backend/, venv active)

The demo/hero alerts are the entire on-screen bucket (ADR-0005): real SynthAML
powers the held-out accuracy metric only. Each input alert is account +
transactions (no triage); the pipeline fills in the triage/verifier/STR.
"""

from __future__ import annotations

import json
from pathlib import Path

from agents.pipeline import run_triage
from schemas import Alert, AlertInput, TriageResult

_DATA = Path(__file__).resolve().parent
_SOURCES = ["demo_queue.json", "hero_cases.json"]
_OUT = _DATA / "results.json"


def _run_with_retry(alert: AlertInput, client, attempts: int = 3) -> TriageResult:
    """DeepSeek V4 occasionally returns an empty body (reasoning-token starvation);
    one llm-level retry already runs inside complete_json — add a small outer retry
    so a single flaky response doesn't abort a multi-alert batch."""
    last = None
    for _ in range(attempts):
        try:
            return run_triage(alert, client=client)
        except Exception as e:  # noqa: BLE001 — surface only after exhausting retries
            last = e
    raise RuntimeError(f"run_triage failed for {alert.alert_id} after {attempts} attempts: {last}")


def build_results(alerts: list[dict], *, client=None) -> list[dict]:
    """Run the pipeline over each input alert and assemble validated Alert dicts.

    Pure of file I/O so it can be tested with a fake LLM client (no tokens).
    """
    results = []
    for raw in alerts:
        alert = AlertInput.model_validate(raw)  # input has no triage yet
        triage = _run_with_retry(alert, client)
        # Alert is AlertInput + triage; build it and re-dump camelCase as canonical.
        assembled = Alert(**alert.model_dump(), triage=triage)
        results.append(assembled.model_dump(by_alias=True, mode="json"))
    return results


def _load_inputs() -> list[dict]:
    alerts: list[dict] = []
    for name in _SOURCES:
        alerts.extend(json.loads((_DATA / name).read_text(encoding="utf-8")))
    return alerts


def main() -> None:
    alerts = _load_inputs()
    print(f"Precomputing triage for {len(alerts)} alerts (live DeepSeek calls)...")
    results = build_results(alerts)
    _OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    for r in results:
        t = r["triage"]
        print(f"  {r['alertId']}: {t['recommendation']:8} verifier={t['verifier']['status']:7} conf={t['confidence']}")
    print(f"Wrote {len(results)} results -> {_OUT}")


if __name__ == "__main__":
    main()
