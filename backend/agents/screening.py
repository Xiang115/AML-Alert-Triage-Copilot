"""Deterministic sanctions/PEP screening (Slice B).

`screen(alert)` matches every counterparty on an alert against a bundled watchlist
(`data/watchlist/sanctions.json`, the real OFAC SDN list via ingest_ofac.py) and returns
a `Screening` result. Pure and deterministic — no LLM, no network. It runs once inside the
pipeline, so the result is persisted on the TriageResult and read (never recomputed) by the
Auto-Clear Policy and the UI. A hit sets `blocked=True`, the fail-safe the Queue Agent honours
by never auto-clearing a screened counterparty.

Matching is indexed (built once, cached): an exact/alias map gives O(1) exact matches, and a
token inverted-index restricts fuzzy scoring to entries that share a token with the counterparty
— so a numeric SAML-D counterparty (which shares no token with a 17k-entry list) is near-instant
instead of a full scan. Degrade, never crash: a missing/empty list yields a clear result.
"""

from __future__ import annotations

import json
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from schemas import AlertInput, Screening, ScreeningMatch

_LIST_FILE = Path(__file__).parent.parent / "data" / "watchlist" / "sanctions.json"
_CITATION = "OFAC SDN — U.S. Treasury full list (bundled snapshot)"
_FUZZY_THRESHOLD = 0.6


@lru_cache(maxsize=1)
def _load_list() -> tuple[dict, ...]:
    """The bundled watchlist, cached (static file). Missing file => empty list (degrade)."""
    if not _LIST_FILE.exists():
        return ()
    return tuple(json.loads(_LIST_FILE.read_text(encoding="utf-8")))


@lru_cache(maxsize=1)
def _index() -> tuple[tuple[dict, ...], dict[str, dict], dict[str, set[int]]]:
    """Build lookup structures over the watchlist once (cached): an exact/alias map for O(1)
    exact matches, and a token -> entry-indices inverted index so fuzzy matching only scores
    entries that share a token with the counterparty. Rebuilt when the list cache is cleared."""
    entries = _load_list()
    exact: dict[str, dict] = {}
    token_to_entries: dict[str, set[int]] = defaultdict(set)
    for i, entry in enumerate(entries):
        for cand in (entry["name"], *entry.get("aliases", [])):
            n = _norm(cand)
            if not n:
                continue
            exact.setdefault(n, entry)  # first list-order entry wins (deterministic)
            for tok in n.split():
                token_to_entries[tok].add(i)
    return entries, exact, token_to_entries


def _norm(s: str) -> str:
    return " ".join(s.lower().split())


def _match(name: str, entry: dict) -> tuple[str, float] | None:
    """Exact (incl. aliases) -> ("exact", 1.0); else Jaccard token overlap >= threshold ->
    ("fuzzy", score); else None. Deterministic and order-independent."""
    n = _norm(name)
    if not n:
        return None
    cands = [entry["name"], *entry.get("aliases", [])]
    if any(n == _norm(c) for c in cands):
        return "exact", 1.0
    nt = set(n.split())
    best = 0.0
    for c in cands:
        ct = set(_norm(c).split())
        if ct:
            best = max(best, len(nt & ct) / len(nt | ct))
    return ("fuzzy", round(best, 2)) if best >= _FUZZY_THRESHOLD else None


def screen(alert: AlertInput) -> Screening:
    """Screen every unique counterparty on the alert against the bundled watchlist.

    Always returns a Screening (clear/potential/hit). `blocked` is True on any match =>
    fail-safe: the Auto-Clear Policy will not clear this alert. Pure/deterministic — same
    alert in, same Screening out. Exact/alias matches are preferred over fuzzy (a stronger,
    unambiguous match); fuzzy is only scored over entries sharing a token (the index)."""
    entries, exact, token_to_entries = _index()

    # Unique counterparties, keyed by account (falling back to name), first occurrence wins.
    seen: dict[str, str] = {}
    for t in alert.transactions or []:
        cid = t.counterparty_account or t.counterparty_name
        if cid and cid not in seen:
            seen[cid] = t.counterparty_name or ""

    matches: list[ScreeningMatch] = []
    for cid, name in seen.items():
        n = _norm(name)
        if not n:
            continue
        hit_entry: dict | None = None
        match_type = "exact"
        score = 1.0
        if n in exact:  # O(1) exact / alias
            hit_entry = exact[n]
        else:  # fuzzy only over entries sharing a token; first list-order match wins
            candidates: set[int] = set()
            for tok in set(n.split()):
                candidates |= token_to_entries.get(tok, set())
            for i in sorted(candidates):
                m = _match(name, entries[i])
                if m:
                    match_type, score = m
                    hit_entry = entries[i]
                    break
        if hit_entry is not None:
            matches.append(ScreeningMatch(
                counterparty_id=str(cid),
                list_name=hit_entry["list"],
                matched_name=hit_entry["name"],
                match_type=match_type,
                score=score,
                program=hit_entry.get("program"),
            ))

    status = "hit" if any(m.match_type == "exact" for m in matches) else (
        "potential" if matches else "clear")
    return Screening(
        status=status,
        blocked=bool(matches),
        screened_counterparties=len(seen),
        matches=matches,
        citation=_CITATION if entries else None,
    )
