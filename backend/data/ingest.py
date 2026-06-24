"""Ingest an alert catalog (alerts + their transactions) into the database — the
production "how alerts get in" path (build tool, not an endpoint).

Reads a results.json-shaped JSON file and bulk-loads it into the `alerts` + `transactions`
tables via the store. Idempotent (skips if the catalog is already loaded); pass --reset to
clear and reload. Run from backend/ (venv active):

    python -m data.ingest                       # ingest data/results.json into DATABASE_URL
    python -m data.ingest path/to/alerts.json   # ingest another catalog
    python -m data.ingest --reset               # clear + reload

The alert catalog is the input the pipeline reasons over; this is its relational,
queryable, scalable home (vs. the file-of-record results.json). A real deployment points
DATABASE_URL at Postgres/MySQL and feeds this from the bank's monitoring system.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import config
import store
from schemas import Alert

_DEFAULT = Path(__file__).resolve().parent / "results.json"


def ingest(path: Path, *, reset: bool = False) -> None:
    catalog = json.loads(path.read_text(encoding="utf-8"))
    for a in catalog:
        Alert.model_validate(a)  # fail fast on a malformed catalog before touching the DB
    store.init()
    if reset:
        store.clear_alerts()
    store.seed_alerts(catalog)
    print(
        f"ingested {store.count_alerts()} alerts / {store.count_transactions()} transactions "
        f"from {path.name} into {config.DATABASE_URL}"
    )


def main(argv: list[str]) -> None:
    reset = "--reset" in argv
    positional = [a for a in argv if not a.startswith("--")]
    path = Path(positional[0]) if positional else _DEFAULT
    ingest(path, reset=reset)


if __name__ == "__main__":
    main(sys.argv[1:])
