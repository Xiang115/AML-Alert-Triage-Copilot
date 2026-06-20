"""FastAPI serving layer (PIPELINE Phase 7).

Loads the precomputed `results.json` on startup and serves it from memory, so the
filmed demo never waits on an LLM (CLAUDE.md > Architecture). The single live
endpoint, POST /alerts/{id}/triage, re-runs the pipeline for Q&A only: it returns
a fresh result WITHOUT mutating the precomputed demo source, and falls back to the
precomputed triage if the provider hiccups (ADR-0003).

Run from /backend:  uvicorn main:app --reload
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from agents.pipeline import run_triage
from decision import resolve_str_draft
from schemas import Alert, CamelModel, Decision, Metrics, STRDraft

logger = logging.getLogger("api")

_DATA = Path(__file__).resolve().parent / "data"
_RESULTS = _DATA / "results.json"
_METRICS = _DATA / "metrics.json"


def _load_alerts() -> dict[str, dict]:
    """Load precomputed alerts (camelCase dicts), validating each against the contract."""
    out: dict[str, dict] = {}
    for a in json.loads(_RESULTS.read_text(encoding="utf-8")):
        Alert.model_validate(a)  # fail fast on a malformed results.json
        out[a["alertId"]] = a
    return out


_ALERTS: dict[str, dict] = _load_alerts()
_DECISIONS: dict[str, dict] = {}  # in-memory for the session (CLAUDE.md: leaning in-memory)


# --- error shape: { "error": { "code", "message" } } (CLAUDE.md > API contract) ---

class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message


def _require_alert(alert_id: str) -> dict:
    alert = _ALERTS.get(alert_id)
    if alert is None:
        raise ApiError(404, "ALERT_NOT_FOUND", f"No alert with id '{alert_id}'.")
    return alert


class DecisionRequest(CamelModel):
    action: Literal["approve", "override"]
    final_disposition: Literal["escalate", "dismiss"]
    edited_str_draft: STRDraft | None = None


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


@app.exception_handler(ApiError)
def _api_error_handler(_request, exc: ApiError):
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": exc.code, "message": exc.message}})


@app.get("/alerts")
def list_alerts(status: str | None = None):
    """Queue. Optional ?status= filter. Queue items omit embedded transactions."""
    items = [a for a in _ALERTS.values() if status is None or a["status"] == status]
    return [{**a, "transactions": None} for a in items]


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


@app.post("/alerts/{alert_id}/decision")
def decide(alert_id: str, body: DecisionRequest):
    """Analyst approve/override → updates status (+ STR per disposition), returns the Alert."""
    alert = _require_alert(alert_id)
    decision = Decision(
        alert_id=alert_id,
        action=body.action,
        final_disposition=body.final_disposition,
        edited_str_draft=body.edited_str_draft,
        decided_at=datetime.now(),
    )

    alert["status"] = "approved" if decision.action == "approve" else "overridden"
    # The disposition->STR invariant lives in decision.resolve_str_draft (reset restores it).
    alert["triage"]["strDraft"] = resolve_str_draft(
        alert["triage"]["strDraft"], decision.final_disposition, decision.edited_str_draft
    )

    _DECISIONS[alert_id] = decision.model_dump(by_alias=True, mode="json")
    return alert


@app.get("/metrics")
def get_metrics():
    """Serve metrics.json (Phase 8). 404s in contract shape until that artifact exists."""
    if not _METRICS.exists():
        raise ApiError(404, "METRICS_NOT_READY", "metrics.json has not been generated yet (Phase 8).")
    data = json.loads(_METRICS.read_text(encoding="utf-8"))
    return Metrics.model_validate(data).model_dump(by_alias=True, mode="json")


@app.post("/reset")
def reset():
    """Reload the in-memory alert state from results.json and clear session decisions.
    Not in the core contract — a demo convenience to clear edits between rehearsals."""
    _ALERTS.clear()
    _ALERTS.update(_load_alerts())
    _DECISIONS.clear()
    return {"status": "success", "message": "In-memory state reset from results.json."}
