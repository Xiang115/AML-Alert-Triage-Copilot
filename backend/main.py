"""FastAPI app. Phase 0: serves the canonical fixture queue (camelCase).

Later phases replace the fixture load with results.json (precompute) and add the
detail / triage / decision / metrics endpoints (see docs/PIPELINE.md Phase 7).
Run from /backend:  uvicorn main:app --reload
"""

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from schemas import Alert

_FIXTURE = Path(__file__).parent / "data" / "fixtures" / "alerts.json"
_ALERTS: list[Alert] = [Alert.model_validate(a) for a in json.loads(_FIXTURE.read_text(encoding="utf-8"))]

app = FastAPI(title="AML Alert-Triage Copilot")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/alerts")
def list_alerts(status: str | None = None):
    """Queue. Optional ?status= filter. Queue items omit embedded transactions."""
    items = _ALERTS if status is None else [a for a in _ALERTS if a.status == status]
    return [
        a.model_copy(update={"transactions": None}).model_dump(by_alias=True, mode="json")
        for a in items
    ]
