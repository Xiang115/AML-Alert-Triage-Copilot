"""Ingest the real OFAC SDN watchlist into the screening list format.

A build tool (like precompute.py) — run it manually to refresh `sanctions.json`; the
backend never invokes it at request time. Pulls the authoritative public files from
the U.S. Treasury (public domain), so `agents/screening.py` matches counterparties
against the *actual* OFAC Specially Designated Nationals list, not a hand-written sample.

    cd backend && .venv/Scripts/python.exe data/watchlist/ingest_ofac.py

Sources (OFAC published CSVs):
  SDN.CSV  ent_num, name, sdn_type, program, title, ...   (primary designations)
  ALT.CSV  ent_num, alt_num, alt_type, alt_name, remarks  (aka/fka aliases)
"""

from __future__ import annotations

import csv
import io
import json
import urllib.request
from collections import defaultdict
from pathlib import Path

_SDN_URL = "https://www.treasury.gov/ofac/downloads/sdn.csv"
_ALT_URL = "https://www.treasury.gov/ofac/downloads/alt.csv"
_OUT = Path(__file__).parent / "sanctions.json"

# OFAC uses "-0- " as its empty-field sentinel.
_EMPTY = {"", "-0-"}
# Vessels/aircraft are on the SDN list but are never bank account counterparties, so we
# screen only individuals and entities (names a transaction could actually carry).
_SKIP_TYPES = {"vessel", "aircraft"}


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", errors="replace")


def _clean(value: str) -> str:
    v = value.strip()
    return "" if v in _EMPTY else v


def _program(raw: str) -> str | None:
    # OFAC packs multiple programs as "IRAN] [SDGT"; make it a readable "IRAN; SDGT".
    p = _clean(raw).replace("] [", "; ").strip("[]")
    return p or None


def build() -> list[dict]:
    # Aliases first, grouped by entity number.
    aliases: dict[str, list[str]] = defaultdict(list)
    for row in csv.reader(io.StringIO(_fetch(_ALT_URL))):
        if len(row) < 4:
            continue
        ent, alt_name = row[0].strip(), _clean(row[3])
        if alt_name:
            aliases[ent].append(alt_name)

    entries: list[dict] = []
    for row in csv.reader(io.StringIO(_fetch(_SDN_URL))):
        if len(row) < 4:
            continue
        ent, name, sdn_type, program = row[0].strip(), _clean(row[1]), _clean(row[2]).lower(), row[3]
        if not name or sdn_type in _SKIP_TYPES:
            continue
        entries.append({
            "name": name,
            "list": "OFAC SDN",
            "program": _program(program),
            "aliases": sorted(set(aliases.get(ent, []))),
        })
    return entries


def main() -> None:
    entries = build()
    _OUT.write_text(json.dumps(entries, ensure_ascii=False, indent=0), encoding="utf-8")
    alias_total = sum(len(e["aliases"]) for e in entries)
    print(f"Wrote {len(entries):,} OFAC SDN entries ({alias_total:,} aliases) -> {_OUT}")


if __name__ == "__main__":
    main()
