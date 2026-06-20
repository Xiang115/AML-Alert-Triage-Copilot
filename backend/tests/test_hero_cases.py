"""Regression guard for the demo's hero cases (CLAUDE.md beat 3 — the wow).

Pins the outcomes in the *committed* results.json, which is what the demo serves.
A prompt/precompute change that flips a hero outcome fails here before it reaches
the screen. (This guards the committed artifact; it does not re-run the live model.)

The intended narrative: exactly HERO-001's verifier FLAGS the call (forcing human
review, confidence capped below the threshold per ADR-0007); HERO-002 and HERO-003
are clean agreed escalates that must not steal that moment.
"""

import json
from pathlib import Path

from config import REVIEW_THRESHOLD
from schemas import Alert

_RESULTS = Path(__file__).resolve().parent.parent / "data" / "results.json"


def _heroes() -> dict[str, dict]:
    data = json.loads(_RESULTS.read_text(encoding="utf-8"))
    return {a["alertId"]: a for a in data if a["alertId"].startswith("HERO")}


def test_all_three_hero_cases_present_and_valid():
    heroes = _heroes()
    assert set(heroes) == {"HERO-001", "HERO-002", "HERO-003"}
    for a in heroes.values():
        Alert.model_validate(a)  # conforms to the wire contract
        assert a["triage"]["recommendation"] == "escalate"
        assert a["triage"]["strDraft"] is not None  # escalate drafts an STR (beat 4)


def test_hero_001_verifier_flags_and_forces_review():
    h = _heroes()["HERO-001"]["triage"]
    assert h["verifier"]["status"] == "flagged"
    assert h["confidence"] < REVIEW_THRESHOLD  # flag caps it below review (ADR-0007)


def test_hero_002_and_003_are_clean_agreed_escalates():
    heroes = _heroes()
    for hid in ("HERO-002", "HERO-003"):
        t = heroes[hid]["triage"]
        assert t["verifier"]["status"] == "agreed"
        assert t["confidence"] >= REVIEW_THRESHOLD
