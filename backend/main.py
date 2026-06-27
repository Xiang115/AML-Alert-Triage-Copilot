"""FastAPI serving layer (PIPELINE Phase 7).

Loads the precomputed `results.json` on startup and serves it from memory, so the
filmed demo never waits on an LLM (CLAUDE.md > Architecture). The single live
endpoint, POST /alerts/{id}/triage, re-runs the pipeline for Q&A only: it returns
a fresh result WITHOUT mutating the precomputed demo source, and falls back to the
precomputed triage if the provider hiccups (ADR-0003).

Run from /backend:  python -m uvicorn main:app --reload
(use `python -m uvicorn`, not bare `uvicorn` — Windows Application Control blocks the
unsigned uvicorn.exe shim in .venv\\Scripts\\.)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse

import config
import store
from agents.pipeline import run_triage, run_triage_events
from timeutil import now_local
from decision import resolve_str_draft
from goaml import GoamlConfig, submission_reference, to_goaml_str_xml
from schemas import (
    Alert,
    AuditEntry,
    CamelModel,
    Decision,
    DecisionSummary,
    Metrics,
    ShiftBriefing,
    STRDraft,
    SubmissionAck,
)

# Configure logging once at import so the api/llm loggers actually emit (a bare
# getLogger has no handler). Idempotent — a no-op if a host (uvicorn) already set up
# root handlers, so it never double-logs.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")

_DATA = Path(__file__).resolve().parent / "data"
_RESULTS = _DATA / "results.json"
_METRICS = _DATA / "metrics.json"
_AUDIT_SEED = _DATA / "audit_seed.json"  # Queue Agent autoClear events (ADR-0010)
_BRIEFING = _DATA / "shift_briefing.json"
_GOAML_CONFIG = GoamlConfig.model_validate(
    json.loads((_DATA / "goaml_config.json").read_text(encoding="utf-8"))
)


def _load_alert_catalog() -> list[dict]:
    """Load the precomputed alert catalog (camelCase dicts), validating each against the
    contract. The seed source for the alert tables and the file-of-record (ADR-0003)."""
    catalog = json.loads(_RESULTS.read_text(encoding="utf-8"))
    for a in catalog:
        Alert.model_validate(a)  # fail fast on a malformed results.json
    return catalog


def _load_audit_seed() -> list[dict]:
    """The Queue Agent's autoClear events (ADR-0010), so /audit opens populated with the
    autonomous overnight run instead of empty until a human acts. Missing file
    (precompute not yet run) -> empty trail."""
    if not _AUDIT_SEED.exists():
        return []
    return json.loads(_AUDIT_SEED.read_text(encoding="utf-8"))


# The DB (store.py, behind the DATABASE_URL seam) is the source of truth for the alert
# catalog (alerts + their transactions), the analyst's decisions, and the audit trail —
# all survive a restart and are safe under concurrent requests. The catalog is seeded
# from results.json (the file-of-record, ADR-0003) and the trail from the Queue Agent's
# autonomous run (ADR-0010); each seed only takes when its table is empty, so a restart
# keeps decision-updated alert statuses and real runtime events.
store.init()
store.seed_alerts(_load_alert_catalog())
store.seed_audit(_load_audit_seed())


# --- error shape: { "error": { "code", "message" } } (CLAUDE.md > API contract) ---

class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message


def _require_alert(alert_id: str) -> dict:
    alert = store.get_alert(alert_id)
    if alert is None:
        raise ApiError(404, "ALERT_NOT_FOUND", f"No alert with id '{alert_id}'.")
    return alert


class DecisionRequest(CamelModel):
    action: Literal["approve", "override"]
    final_disposition: Literal["escalate", "dismiss"]
    edited_str_draft: STRDraft | None = None
    note: str | None = None


def get_llm_client():
    """Injectable LLM client. None in prod → agents lazily build the real DeepSeek
    client; tests override this dependency with a fake so /triage spends no tokens."""
    return None


app = FastAPI(title="AML Alert-Triage Copilot")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    """The single error envelope (CLAUDE.md > API contract): every error exits here."""
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message}})


@app.exception_handler(ApiError)
def _api_error_handler(_request, exc: ApiError):
    return _error_response(exc.status_code, exc.code, exc.message)


@app.exception_handler(RequestValidationError)
def _validation_error_handler(_request, exc: RequestValidationError):
    """Malformed request body/params — keep the contract shape instead of FastAPI's default."""
    detail = "; ".join(
        f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()
    )
    return _error_response(422, "VALIDATION_ERROR", detail or "Request validation failed.")


@app.exception_handler(Exception)
def _unexpected_error_handler(_request, exc: Exception):
    """Last-resort catch-all so an unexpected failure still exits in the contract
    shape. The message is generic — internals aren't leaked to the client."""
    logger.exception("Unhandled error serving request")
    return _error_response(500, "INTERNAL_ERROR", "An unexpected error occurred.")


@app.get("/health")
def health():
    """Liveness + readiness for the live path. `llmKeyPresent` confirms the live
    /triage run is actually wired BEFORE you're on camera — a missing key otherwise
    only surfaces as a logged warning mid-Q&A, then falls back to precomputed
    (ADR-0003). Cheap to hit during a pre-demo check."""
    return {
        "status": "ok",
        "alertsLoaded": store.count_alerts(),
        "transactionsLoaded": store.count_transactions(),
        "llmKeyPresent": bool(config.DEEPSEEK_API_KEY),
        "model": config.MODEL_WORKHORSE,
    }


@app.get("/alerts")
def list_alerts(status: str | None = None, routing: str | None = None):
    """Queue. Optional ?status= and ?routing= filters (the Queue Agent lanes, ADR-0010),
    applied as indexed WHERE clauses in the DB. Queue items omit embedded transactions."""
    return store.list_alerts(status, routing)


@app.get("/alerts/{alert_id}")
def get_alert(alert_id: str):
    """Detail: account + embedded transactions + embedded triage."""
    return _require_alert(alert_id)


@app.post("/alerts/{alert_id}/triage")
def live_triage(alert_id: str, client=Depends(get_llm_client)):
    """LIVE pipeline run (Q&A only). Returns a fresh TriageResult; never persists it.
    Falls back to the precomputed triage if the provider fails (ADR-0003)."""
    alert = _require_alert(alert_id)
    try:
        # Stored record has triage; parse as Alert (an AlertInput) at this seam.
        result = run_triage(Alert.model_validate(alert), client=client)
        return result.model_dump(by_alias=True, mode="json")
    except Exception as e:  # noqa: BLE001 — demo resilience: replay precomputed on any failure
        logger.warning("Live triage for %s failed (%s); serving precomputed fallback.", alert_id, e)
        return alert["triage"]


@app.get("/alerts/{alert_id}/triage/stream")
def live_triage_stream(alert_id: str, client=Depends(get_llm_client)):
    """LIVE pipeline run, streamed as Server-Sent Events so the UI can show the agent's
    reasoning step-by-step as each stage actually completes (Q&A 'thinking' view). Never
    persists. On any provider failure it emits an error event then the precomputed result,
    so the demo still resolves (ADR-0003). Cost-sensitive, to match the served demo data."""
    alert = _require_alert(alert_id)

    def gen():
        try:
            for ev in run_triage_events(Alert.model_validate(alert), client=client, cost_sensitive=True):
                if ev["type"] == "result":
                    payload = {"type": "result", "triage": ev["triage"].model_dump(by_alias=True, mode="json")}
                else:
                    payload = ev
                yield f"data: {json.dumps(payload)}\n\n"
        except Exception as e:  # noqa: BLE001 — demo resilience: fall back to precomputed
            logger.warning("Live triage stream for %s failed (%s); serving precomputed fallback.", alert_id, e)
            yield f"data: {json.dumps({'type': 'error', 'message': 'Live run failed; showing the precomputed result.'})}\n\n"
            yield f"data: {json.dumps({'type': 'result', 'triage': alert['triage']})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.post("/alerts/{alert_id}/decision")
def decide(alert_id: str, body: DecisionRequest):
    """Analyst approve/override → updates status (+ STR per disposition), returns the Alert."""
    alert = _require_alert(alert_id)
    decision = Decision(
        alert_id=alert_id,
        action=body.action,
        final_disposition=body.final_disposition,
        edited_str_draft=body.edited_str_draft,
        note=body.note,
        decided_at=now_local(),
    )

    new_status = "approved" if decision.action == "approve" else "overridden"
    # The disposition->STR invariant lives in decision.resolve_str_draft (reset restores it).
    new_str_draft = resolve_str_draft(
        alert["triage"]["strDraft"], decision.final_disposition, decision.edited_str_draft
    )
    # Persist the decision's effect on the alert row (survives restart), the decision
    # record (the filing gate), and the audit event — all in the DB.
    store.set_alert_decision(alert_id, new_status, new_str_draft)
    store.record_decision(alert_id, decision.model_dump(by_alias=True, mode="json"))
    alert["status"] = new_status
    alert["triage"]["strDraft"] = new_str_draft
    triage = alert["triage"]
    store.append_audit(AuditEntry(
        alert_id=alert_id,
        event="decision",
        at=decision.decided_at,
        action=decision.action,
        ai_recommendation=triage["recommendation"],
        final_disposition=decision.final_disposition,
        confidence=triage["confidence"],
        verifier_status=triage["verifier"]["status"],
        note=decision.note,
    ).model_dump(by_alias=True, mode="json"))
    return alert


def _require_escalate_signoff(alert_id: str) -> tuple[Alert, dict]:
    """The STR filing gate, recomputed live from the current decision: an STR exists
    only after an analyst signs off on an escalation. Raises 409 (no decision /
    dismissed) so a later change-of-mind revokes both export and submission. Returns
    the validated Alert plus its decision record."""
    alert_dict = _require_alert(alert_id)
    decision = store.get_decision(alert_id)
    if decision is None:
        raise ApiError(
            409, "STR_NOT_ADJUDICATED",
            "Alert has not been adjudicated; an STR cannot be filed until an analyst signs off.",
        )
    if decision["finalDisposition"] != "escalate":
        raise ApiError(409, "STR_DISMISSED", "Alert was dismissed; there is no STR to file.")
    alert = Alert.model_validate(alert_dict)
    if alert.triage.str_draft is None:  # invariant: an escalate decision keeps the draft
        raise ApiError(409, "STR_DISMISSED", "No STR draft is present for this alert.")
    return alert, decision


@app.get("/alerts/{alert_id}/str.xml")
def export_goaml_str(alert_id: str):
    """Export the approved STR as a schema-valid goAML STR report (the integration seam)."""
    alert, decision = _require_escalate_signoff(alert_id)
    xml = to_goaml_str_xml(
        alert.triage.str_draft,
        alert.transactions or [],
        _GOAML_CONFIG,
        submission_date=datetime.fromisoformat(decision["decidedAt"]),
    )
    return Response(content=xml, media_type="application/xml")


@app.post("/alerts/{alert_id}/str/submit")
def submit_goaml_str(alert_id: str):
    """File the approved STR and return the FIU acknowledgement. Generates+validates
    the goAML report (so an unfileable report can't be acked), records the filing in
    the audit trail, and returns a demo-stable submission reference."""
    alert, decision = _require_escalate_signoff(alert_id)
    to_goaml_str_xml(  # validate the report is well-formed before acknowledging it
        alert.triage.str_draft, alert.transactions or [], _GOAML_CONFIG,
        submission_date=datetime.fromisoformat(decision["decidedAt"]),
    )
    ack = SubmissionAck(
        alert_id=alert_id,
        submission_ref=submission_reference(alert_id),
        status="accepted",
        submitted_at=now_local(),
    )
    store.append_audit(AuditEntry(
        alert_id=alert_id, event="submission", at=ack.submitted_at, submission_ref=ack.submission_ref,
    ).model_dump(by_alias=True, mode="json"))
    return ack.model_dump(by_alias=True, mode="json")


@app.get("/audit")
def get_audit():
    """The append-only accountability trail, newest first (decisions + submissions)."""
    return list(reversed(store.all_audit()))


@app.get("/audit/summary")
def get_audit_summary():
    """Session AI–analyst agreement, computed from the audit log's `decision` events — the
    authoritative record, so every client agrees (vs. a per-client tally that would drift).
    Decision-scoped: autoClear / debateResolved / submission events never count. `agreementRate`
    is null until a decision is made. A session-activity signal, NOT held-out performance
    (that is /metrics) — surfaced on the audit trail, never the performance dashboard."""
    decisions = [e for e in store.all_audit() if e["event"] == "decision"]
    approvals = sum(1 for e in decisions if e.get("action") == "approve")
    n = len(decisions)
    return DecisionSummary(
        decisions=n,
        approvals=approvals,
        overrides=n - approvals,
        agreement_rate=round(approvals / n, 4) if n else None,
    ).model_dump(by_alias=True, mode="json")


@app.get("/queue/briefing")
def get_briefing():
    """The Queue Agent's Shift Briefing (ADR-0010) — the precomputed overnight-run summary
    the analyst sees on arrival. 404s in contract shape until precompute has written it."""
    if not _BRIEFING.exists():
        raise ApiError(404, "BRIEFING_NOT_READY", "shift_briefing.json has not been generated yet.")
    data = json.loads(_BRIEFING.read_text(encoding="utf-8"))
    return ShiftBriefing.model_validate(data).model_dump(by_alias=True, mode="json")


@app.get("/metrics")
def get_metrics():
    """Serve metrics.json (Phase 8). 404s in contract shape until that artifact exists."""
    if not _METRICS.exists():
        raise ApiError(404, "METRICS_NOT_READY", "metrics.json has not been generated yet (Phase 8).")
    data = json.loads(_METRICS.read_text(encoding="utf-8"))
    return Metrics.model_validate(data).model_dump(by_alias=True, mode="json")


@app.post("/reset")
def reset():
    """Reset the persisted store: re-seed the alert catalog, drop session decisions + audit
    events, and restore the Queue Agent's autonomous seed. Not in the core contract — a
    demo convenience to clear edits between rehearsals."""
    store.reset()
    return {"status": "success", "message": "State reset from the seeded catalog."}
