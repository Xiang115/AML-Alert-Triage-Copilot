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

import config
from agents.pipeline import run_triage
from agents.queue_agent import (
    build_audit_seed,
    build_debate_audit_seed,
    build_shift_briefing,
    narrate_briefing,
    stamp_routing,
)
from agents.knowledge_base import card_citation
from agents.screening import screen
from agents.str_drafter import policy_basis_line, recommended_action
from schemas import Alert, AlertInput, TriageResult
from timeutil import now_local

_DATA = Path(__file__).resolve().parent
# Real-data demo (ADR-0012): the served queue is now built from REAL SAML-D alerts
# (saml_d_demo_queue.json) — no hand-written cases — so the demo can't be dismissed as
# "works only on crafted cases". hero_cases.json is kept ONLY as a labelled fallback for
# the Beat-3 verifier wow if the mined real catch (SD-00013) is ever unavailable. The old
# hand-authored demo_queue*.json are retired from the demo (kept in git history).
_SOURCES = ["saml_d_demo_queue.json", "hero_cases.json"]
_OUT = _DATA / "results.json"
_AUDIT_SEED = _DATA / "audit_seed.json"
_BRIEFING = _DATA / "shift_briefing.json"


def _run_with_retry(alert: AlertInput, client, attempts: int = 4, *,
                    cost_sensitive: bool = False) -> TriageResult:
    """DeepSeek V4 occasionally returns an empty body (reasoning-token starvation) or a transient
    `Connection error` mid-batch; one llm-level retry already runs inside complete_model — add an
    outer retry with backoff so a single flaky response or brief network blip doesn't abort a long,
    expensive multi-alert batch (no per-alert checkpoint, so one failure wastes the whole run)."""
    import time

    last = None
    for attempt in range(attempts):
        try:
            return run_triage(alert, client=client, cost_sensitive=cost_sensitive)
        except Exception as e:  # noqa: BLE001 — surface only after exhausting retries
            last = e
            if attempt < attempts - 1:
                time.sleep(5 * (attempt + 1))  # 5s, 10s, 15s — ride out a brief API/network blip
    raise RuntimeError(f"run_triage failed for {alert.alert_id} after {attempts} attempts: {last}")


def _assemble_one(raw: dict, client, cost_sensitive: bool) -> tuple[dict, TriageResult, str]:
    """Run one alert through the pipeline and assemble its validated Alert dict.
    Independent per alert (no shared mutable state), so it is safe to fan out across threads."""
    alert = AlertInput.model_validate(raw)  # input has no triage yet
    triage = _run_with_retry(alert, client, cost_sensitive=cost_sensitive)
    # Alert is AlertInput + triage; build it and re-dump camelCase as canonical.
    assembled = Alert(**alert.model_dump(), triage=triage)
    return assembled.model_dump(by_alias=True, mode="json"), triage, alert.alert_id


def build_results(alerts: list[dict], *, client=None, cost_sensitive: bool = False,
                  progress: bool = False, workers: int = 1) -> list[dict]:
    """Run the pipeline over each input alert and assemble validated Alert dicts.

    Pure of file I/O so it can be tested with a fake LLM client (no tokens). The demo
    serves the cost-sensitive operating point so it matches the held-out eval metric.

    Each alert is an independent multi-call pipeline run (triage -> verify -> draft, ~2-4
    DeepSeek calls), so `workers > 1` fans them out across a thread pool (the OpenAI client
    is thread-safe) — for a 20+ alert real-data queue this cuts wall-time ~Nx with the same
    token count. `workers=1` (default) keeps the deterministic sequential path the fake-client
    tests rely on. Results are always returned in input order. `progress=True` prints a flushed
    line per completed alert so a long run isn't a black box.
    """
    import time
    from concurrent.futures import ThreadPoolExecutor, as_completed

    total = len(alerts)
    results: list[dict | None] = [None] * total

    if workers <= 1 or total <= 1:
        for i, raw in enumerate(alerts):
            if progress:
                print(f"  [{i + 1}/{total}] running (triage->verify->draft)...", flush=True)
            t0 = time.perf_counter()
            res, triage, aid = _assemble_one(raw, client, cost_sensitive)
            results[i] = res
            if progress:
                print(f"  [{i + 1}/{total}] {aid:9} {triage.recommendation:8} "
                      f"verifier={triage.verifier.status:7} conf={triage.confidence}  "
                      f"({time.perf_counter() - t0:.1f}s)", flush=True)
        return [r for r in results if r is not None]

    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_assemble_one, raw, client, cost_sensitive): i
                   for i, raw in enumerate(alerts)}
        for fut in as_completed(futures):
            i = futures[fut]
            res, triage, aid = fut.result()
            results[i] = res  # placed by index -> input order preserved
            done += 1
            if progress:
                print(f"  [{done}/{total}] {aid:9} {triage.recommendation:8} "
                      f"verifier={triage.verifier.status:7} conf={triage.confidence}", flush=True)
    return [r for r in results if r is not None]


def _load_inputs() -> list[dict]:
    alerts: list[dict] = []
    for name in _SOURCES:
        alerts.extend(json.loads((_DATA / name).read_text(encoding="utf-8")))
    return alerts


def _write_artifacts(results: list[dict], *, narrate: bool = False, client=None) -> None:
    """Stamp the Queue Agent routing onto each alert and write the three served artifacts
    (ADR-0010): results.json, the audit seed (autoClear events that open the trail), and
    the shift briefing. Routing + recommendedAction derive purely from each alert's stored
    triage (no LLM). When `narrate=True` the briefing summary is LLM-written (#8), falling
    back to the deterministic template if that call fails (drop-first, ADR-0010)."""
    at = now_local()
    # Slice B: deterministic sanctions/PEP screening, persisted on each triage so the served demo
    # carries it and the Queue Agent can honour a hit (screening.blocked disqualifies auto-clear).
    # Pure (no LLM): idempotent on a fresh precompute (re-screens to the same value) and backfills
    # a pre-screening results.json on --restamp. Runs before stamp_routing so routing sees the hit.
    for a in results:
        a["triage"]["screening"] = screen(Alert.model_validate(a)).model_dump(by_alias=True, mode="json")
    routed = stamp_routing(results, config.AUTO_CLEAR_THRESHOLD)
    # Re-derive the deterministic STR recommended action (#9) + append the card's policy-basis
    # citation to the grounds (Slice B) so a restamp of a frozen results.json picks up both
    # without an LLM re-run. Pure string logic; idempotent (the citation line is only appended
    # if absent, matched byte-for-byte via policy_basis_line).
    for a in routed:
        sd = a["triage"].get("strDraft")
        if sd is not None:
            code = a["triage"]["matchedTypology"]["code"]
            citation = card_citation(code)
            line = policy_basis_line(citation)
            if line and line not in sd["groundsForSuspicion"]:
                sd["groundsForSuspicion"].append(line)
            sd["recommendedAction"] = recommended_action(
                a["triage"]["verifier"]["status"], a["triage"]["matchedTypology"]["name"], citation
            )
    _OUT.write_text(json.dumps(routed, indent=2, ensure_ascii=False), encoding="utf-8")
    # The trail opens populated with the autonomous run (ADR-0010) AND every contested call
    # resolved by an adversarial debate (ADR-0011), so /audit replays exactly what the agents did.
    audit_seed = build_audit_seed(routed, at=at) + build_debate_audit_seed(routed, at=at)
    _AUDIT_SEED.write_text(json.dumps(audit_seed, indent=2), encoding="utf-8")
    briefing = build_shift_briefing(routed, at=at)
    if narrate:
        try:
            briefing["summary"] = narrate_briefing(briefing, client=client)
            print("  briefing: LLM-narrated (#8)", flush=True)
        except Exception as e:  # noqa: BLE001 — drop-first fallback (ADR-0010): keep the template
            print(f"  briefing narration failed ({e}); keeping deterministic summary", flush=True)
    _BRIEFING.write_text(json.dumps(briefing, indent=2, ensure_ascii=False), encoding="utf-8")
    n_cleared = sum(a["routing"] == "autoCleared" for a in routed)
    print(f"Wrote {len(routed)} results -> {_OUT.name}", flush=True)
    print(f"Queue Agent (ADR-0010): {n_cleared}/{len(routed)} auto-cleared "
          f"-> {_AUDIT_SEED.name} + {_BRIEFING.name}", flush=True)


def restamp(narrate: bool = False) -> None:
    """Re-derive the Queue Agent artifacts from the EXISTING results.json with no pipeline
    re-run. Routing + recommendedAction are pure (no LLM); add `--narrate` to also LLM-write
    the briefing summary (#8) — one cheap verifier call, not a full re-precompute:
        python -m data.precompute --restamp            # no LLM
        python -m data.precompute --restamp --narrate  # 1 LLM call (briefing only)"""
    if narrate:
        import llm
        llm.use_offline_timeout()
    _write_artifacts(json.loads(_OUT.read_text(encoding="utf-8")), narrate=narrate)


def main() -> None:
    import llm
    llm.use_offline_timeout()  # long timeout: don't abort+retry valid slow reasoning calls
    alerts = _load_inputs()
    print(f"Precomputing triage for {len(alerts)} alerts (live DeepSeek calls, cost-sensitive, parallel)...", flush=True)
    results = build_results(alerts, cost_sensitive=True, progress=True, workers=8)
    _write_artifacts(results, narrate=True)


if __name__ == "__main__":
    import sys
    if "--restamp" in sys.argv:
        restamp(narrate="--narrate" in sys.argv)
    else:
        main()
