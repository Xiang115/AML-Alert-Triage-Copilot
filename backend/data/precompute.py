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


def _run_with_retry(alert: AlertInput, client, attempts: int = 3, *,
                    cost_sensitive: bool = False) -> TriageResult:
    """DeepSeek V4 occasionally returns an empty body (reasoning-token starvation);
    one llm-level retry already runs inside complete_model — add a small outer retry
    so a single flaky response doesn't abort a multi-alert batch."""
    last = None
    for _ in range(attempts):
        try:
            return run_triage(alert, client=client, cost_sensitive=cost_sensitive)
        except Exception as e:  # noqa: BLE001 — surface only after exhausting retries
            last = e
    raise RuntimeError(f"run_triage failed for {alert.alert_id} after {attempts} attempts: {last}")


def build_results(alerts: list[dict], *, client=None, cost_sensitive: bool = False,
                  progress: bool = False) -> list[dict]:
    """Run the pipeline over each input alert and assemble validated Alert dicts.

    Pure of file I/O so it can be tested with a fake LLM client (no tokens). The demo
    serves the cost-sensitive operating point so it matches the held-out eval metric.
    `progress=True` prints a flushed line before and after each alert (which alert,
    outcome, and per-alert seconds) so a long sequential run isn't a black box.
    """
    import time

    results = []
    total = len(alerts)
    for i, raw in enumerate(alerts, 1):
        alert = AlertInput.model_validate(raw)  # input has no triage yet
        if progress:
            print(f"  [{i}/{total}] {alert.alert_id:9} running (triage->verify->draft)...", flush=True)
        t0 = time.perf_counter()
        triage = _run_with_retry(alert, client, cost_sensitive=cost_sensitive)
        # Alert is AlertInput + triage; build it and re-dump camelCase as canonical.
        assembled = Alert(**alert.model_dump(), triage=triage)
        results.append(assembled.model_dump(by_alias=True, mode="json"))
        if progress:
            print(f"  [{i}/{total}] {alert.alert_id:9} {triage.recommendation:8} "
                  f"verifier={triage.verifier.status:7} conf={triage.confidence}  "
                  f"({time.perf_counter() - t0:.1f}s)", flush=True)
    return results


def _load_inputs() -> list[dict]:
    alerts: list[dict] = []
    for name in _SOURCES:
        alerts.extend(json.loads((_DATA / name).read_text(encoding="utf-8")))
    return alerts


def main() -> None:
    import llm
    llm.use_offline_timeout()  # long timeout: don't abort+retry valid slow reasoning calls
    alerts = _load_inputs()
    print(f"Precomputing triage for {len(alerts)} alerts (live DeepSeek calls, cost-sensitive)...", flush=True)
    results = build_results(alerts, cost_sensitive=True, progress=True)
    _OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(results)} results -> {_OUT}", flush=True)


if __name__ == "__main__":
    main()
