"""Guard: the frontend MOCK-mode fixtures must equal the backend's served artifacts.

The filmed demo runs in MOCK mode off frontend/src/fixtures/*; the live /triage
Q&A runs off backend/data/{results,metrics}.json. If they drift, the demo and the
"prove it's live" endpoint show different data — a silent landmine after a
re-precompute. Re-sync with:  python -m data.sync_fixtures
"""

import json
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1]
_DATA = _BACKEND / "data"
_FIXTURES = _BACKEND.parent / "frontend" / "src" / "fixtures"

# (backend artifact, frontend fixture that must equal it).
_PAIRS = [
    ("results.json", "alerts.json"),
    ("metrics.json", "metrics.json"),
]


@pytest.mark.parametrize("backend_name,fixture_name", _PAIRS)
def test_frontend_fixture_matches_backend_artifact(backend_name: str, fixture_name: str):
    fixture = _FIXTURES / fixture_name
    if not fixture.exists():
        pytest.skip(f"frontend fixture {fixture} not present (backend-only checkout)")
    backend_data = json.loads((_DATA / backend_name).read_text(encoding="utf-8"))
    fixture_data = json.loads(fixture.read_text(encoding="utf-8"))
    assert backend_data == fixture_data, (
        f"{fixture_name} has drifted from data/{backend_name} — the MOCK demo and the "
        f"live /triage Q&A would show different data. Re-run: python -m data.sync_fixtures"
    )
