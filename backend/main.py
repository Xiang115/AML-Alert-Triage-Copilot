"""FastAPI app for AML Alert-Triage Copilot.

Provides endpoints for listing alerts, showing alert details, running live
triage with a timeout/failure fallback, persistence of analyst decisions,
and serving evaluation metrics.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from agents.pipeline import run_triage
from schemas import Alert, CamelModel, Metrics, STRDraft, TriageResult

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")

# Paths
_DATA_DIR = Path(__file__).resolve().parent / "data"
_RESULTS_FILE = _DATA_DIR / "results.json"
_FIXTURE_FILE = _DATA_DIR / "fixtures" / "alerts.json"
_METRICS_FILE = _DATA_DIR / "fixtures" / "metrics.json"
_LIVE_METRICS_FILE = _DATA_DIR / "metrics.json"

# In-memory alerts database
_ALERTS_MAP: dict[str, Alert] = {}


def load_data() -> None:
    """Load alerts data from results.json (or fallback fixture) on startup/reset."""
    global _ALERTS_MAP
    _ALERTS_MAP.clear()

    # Detect if we are running in pytest
    is_testing = "pytest" in sys.modules or os.getenv("TESTING") == "true"
    
    # In tests, force fixture. In production/reload, prefer results.json
    path = _FIXTURE_FILE if is_testing else (_RESULTS_FILE if _RESULTS_FILE.exists() else _FIXTURE_FILE)

    if not path.exists():
        logger.error(f"Data file not found at: {path}")
        return

    try:
        raw_data = json.loads(path.read_text(encoding="utf-8"))
        for item in raw_data:
            alert_obj = Alert.model_validate(item)
            _ALERTS_MAP[alert_obj.alert_id] = alert_obj
        logger.info(f"Loaded {len(_ALERTS_MAP)} alerts from {path.name} (testing={is_testing})")
    except Exception as e:
        logger.exception(f"Error loading alerts data from {path}: {e}")


# Initialize state
load_data()

app = FastAPI(title="AML Alert-Triage Copilot")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class DecisionRequest(CamelModel):
    action: Literal["approve", "override"]
    final_disposition: Literal["escalate", "dismiss"]
    edited_str_draft: STRDraft | None = None


@app.get("/alerts")
def list_alerts(status: str | None = None):
    """List alerts. Optional ?status= filter. Transactions are omitted in the queue."""
    items = list(_ALERTS_MAP.values())
    if status is not None:
        items = [a for a in items if a.status == status]
    
    return [
        a.model_copy(update={"transactions": None}).model_dump(by_alias=True, mode="json")
        for a in items
    ]


@app.get("/alerts/{alert_id}")
def get_alert(alert_id: str):
    """Retrieve detailed alert including transactions and triage details."""
    alert = _ALERTS_MAP.get(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert.model_dump(by_alias=True, mode="json")


@app.post("/alerts/{alert_id}/triage", response_model=TriageResult)
async def post_triage(alert_id: str):
    """Run live agent triage. Fallback to precomputed result if it takes >3s or fails."""
    alert = _ALERTS_MAP.get(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert_dict = alert.model_dump(by_alias=True, mode="json")

    try:
        # Run the synchronous agent pipeline in an executor to avoid blocking the loop
        loop = asyncio.get_running_loop()
        triage_data = await asyncio.wait_for(
            loop.run_in_executor(None, run_triage, alert_dict),
            timeout=3.0
        )
        triage_result = TriageResult.model_validate(triage_data)
        
        # Cache the result in memory
        alert.triage = triage_result
        return triage_result.model_dump(by_alias=True, mode="json")
    except Exception as e:
        logger.warning(f"Live triage for {alert_id} failed or timed out: {e}. Using precomputed fallback.")
        
        fallback_triage = alert.triage
        if not fallback_triage:
            raise HTTPException(
                status_code=500,
                detail=f"Live triage failed, and no precomputed fallback was available: {e}"
            )
        return fallback_triage.model_dump(by_alias=True, mode="json")


@app.post("/alerts/{alert_id}/decision")
def post_decision(alert_id: str, req: DecisionRequest):
    """Persist analyst decisions in-memory and return the updated alert."""
    alert = _ALERTS_MAP.get(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    # Mutate the in-memory state
    alert.status = "approved" if req.action == "approve" else "overridden"
    
    # Handle STR draft updates based on final disposition
    if req.final_disposition == "escalate":
        if req.edited_str_draft is not None:
            alert.triage.str_draft = req.edited_str_draft
    else:
        alert.triage.str_draft = None

    return alert.model_dump(by_alias=True, mode="json")


@app.get("/metrics", response_model=Metrics)
def get_metrics():
    """Retrieve evaluation metrics from offline runs, falling back to fixtures."""
    path = _LIVE_METRICS_FILE if _LIVE_METRICS_FILE.exists() else _METRICS_FILE
    if not path.exists():
        raise HTTPException(status_code=404, detail="Metrics file not found")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Metrics.model_validate(data).model_dump(by_alias=True, mode="json")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load or parse metrics: {e}")


@app.post("/reset")
def reset_alerts():
    """Reset the in-memory alerts state back to the original source files."""
    load_data()
    return {"status": "success", "message": "In-memory alert state reset successfully."}
