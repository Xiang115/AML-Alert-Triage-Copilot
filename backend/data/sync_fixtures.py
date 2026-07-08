"""Sync the served precompute artifacts into the frontend's MOCK-mode fixtures.

The filmed demo runs in MOCK mode (frontend/src/api.ts: VITE_MOCK !== 'false'),
reading frontend/src/fixtures/* — NOT the backend. The live /triage Q&A reads the
backend's data/results.json. The two MUST stay equal, or the demo and the
"prove it's live" Q&A show different data. results.json / metrics.json are the
source of truth; this copies them into the fixtures. tests/test_fixture_sync.py
fails the build if they ever drift.

Run after every precompute (build tool, not an endpoint):
    python -m data.sync_fixtures          (from backend/)
"""

from __future__ import annotations

import shutil
from pathlib import Path

_DATA = Path(__file__).resolve().parent
_REPO = _DATA.parents[1]
_FIXTURES = _REPO / "frontend" / "src" / "fixtures"

# (source-of-truth backend artifact, frontend fixture it must equal).
_PAIRS = [
    (_DATA / "results.json", _FIXTURES / "alerts.json"),
    (_DATA / "metrics.json", _FIXTURES / "metrics.json"),
    # The curated typology cards are the single source; the coaching panel reads a synced copy.
    (_DATA / "typologies" / "typologies.json", _FIXTURES / "typologies.json"),
    # The held-out evaluation set (250 alerts + labels) shown on the dashboard.
    (_DATA / "evaluation.json", _FIXTURES / "evaluation.json"),
]


def sync() -> None:
    for src, dst in _PAIRS:
        shutil.copyfile(src, dst)
        print(f"synced {src.name} -> {dst.relative_to(_REPO)}")


if __name__ == "__main__":
    sync()
