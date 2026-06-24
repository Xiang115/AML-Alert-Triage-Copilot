"""SQLAlchemy-backed persistence for the analyst's Decisions and the audit trail.

The accountability record a regulator can replay must survive a restart, be safe under
concurrent requests, and scale to a bank's alert volume — so it lives in a real SQL
database behind a single `DATABASE_URL` seam. The demo runs on SQLite (zero-ops); a
production deployment points the URL at Postgres or MySQL with **no code change** — the
same swap the LLM client (`llm.py`) makes for the model provider:

    sqlite:///.../data/app.db                  (demo default)
    postgresql+psycopg://user:pw@host/db       (production)

Four tables:
  alerts        one row per alert (metadata + embedded triage) — the input catalog.
  transactions  one row per ledger entry (indexed by alert_id) — the table that grows
                to a bank's volume.
  decisions     one row per alert: the CURRENT disposition (last write wins) — the source
                of truth for the STR filing gate.
  audit         append-only event log (autoClear / debateResolved seed + decision /
                submission events), ordered by an autoincrement key.

Built on SQLAlchemy Core (not the ORM) so the SQL stays explicit and the surface tiny;
the engine's connection pool makes concurrent requests safe and the schema is emitted
dialect-correctly per database. Payloads are the exact camelCase JSON dicts the API
emits, so a store round-trip is the identity — the wire contract stays the one shape.
"""

from __future__ import annotations

import json

from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    delete,
    func,
    insert,
    select,
    update,
)
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

import config

_metadata = MetaData()

decisions = Table(
    "decisions",
    _metadata,
    Column("alert_id", String(64), primary_key=True),
    Column("payload", Text, nullable=False),
)

audit = Table(
    "audit",
    _metadata,
    Column("seq", Integer, primary_key=True, autoincrement=True),  # SERIAL on PG, rowid on SQLite
    Column("payload", Text, nullable=False),
)

# Input data: the alert catalog. One row per alert (metadata + embedded triage) and one
# row per ledger transaction — the relational, queryable, scalable home for the alerts the
# pipeline reasons over (vs. the file-of-record results.json). status/routing are indexed
# columns so the queue filters are real WHERE clauses; the transactions table is the one
# that grows to a bank's volume, indexed by alert_id.
alerts = Table(
    "alerts",
    _metadata,
    Column("alert_id", String(64), primary_key=True),
    Column("status", String(16), nullable=False, index=True),
    Column("routing", String(16), nullable=True, index=True),
    Column("payload", Text, nullable=False),  # the Alert dict WITHOUT transactions
)

transactions = Table(
    "transactions",
    _metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),  # surrogate: txn ids need not be global
    Column("transaction_id", String(64), nullable=False, index=True),
    Column("alert_id", String(64), nullable=False, index=True),
    Column("seq", Integer, nullable=False),  # preserves ledger order
    Column("payload", Text, nullable=False),  # the Transaction dict
)

_engine: Engine | None = None
_seed: list[dict] = []  # remembered so reset() can restore the Queue Agent's audit trail
_alert_seed: list[dict] = []  # remembered so reset() can restore the alert catalog


def _is_memory_sqlite(url: str) -> bool:
    return url.startswith("sqlite") and (url == "sqlite://" or ":memory:" in url)


def init(url: str | None = None) -> None:
    """Open the engine for `url` (defaults to config.DATABASE_URL) and ensure the tables
    exist. Idempotent; safe to call at import and to call again to point at a new DB."""
    global _engine
    url = url or config.DATABASE_URL
    kwargs: dict = {}
    if _is_memory_sqlite(url):
        # Keep one connection so an in-memory SQLite db survives across the pool (tests).
        kwargs = {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}
    elif url.startswith("sqlite"):
        kwargs = {"connect_args": {"check_same_thread": False}}
    _engine = create_engine(url, **kwargs)
    _metadata.create_all(_engine)


def _require() -> Engine:
    if _engine is None:
        init()
    assert _engine is not None
    return _engine


def seed_audit(entries: list[dict]) -> None:
    """Seed the audit trail with the Queue Agent's precomputed events (ADR-0010/0011),
    but ONLY if it is empty — so a restart preserves the persisted runtime events instead
    of duplicating the seed. Remembers the seed so reset() can restore it."""
    global _seed
    _seed = list(entries)
    eng = _require()
    with eng.begin() as conn:
        count = conn.execute(select(func.count()).select_from(audit)).scalar_one()
        if count == 0 and _seed:
            conn.execute(insert(audit), [{"payload": json.dumps(e)} for e in _seed])


def record_decision(alert_id: str, payload: dict) -> None:
    """Upsert the current decision for an alert (the filing gate reads this). Portable
    delete-then-insert in one transaction — atomic, and dialect-agnostic."""
    eng = _require()
    with eng.begin() as conn:
        conn.execute(delete(decisions).where(decisions.c.alert_id == alert_id))
        conn.execute(insert(decisions), {"alert_id": alert_id, "payload": json.dumps(payload)})


def get_decision(alert_id: str) -> dict | None:
    eng = _require()
    with eng.connect() as conn:
        row = conn.execute(
            select(decisions.c.payload).where(decisions.c.alert_id == alert_id)
        ).first()
    return json.loads(row[0]) if row else None


def all_decisions() -> list[dict]:
    eng = _require()
    with eng.connect() as conn:
        rows = conn.execute(select(decisions.c.payload)).all()
    return [json.loads(r[0]) for r in rows]


def append_audit(entry: dict) -> None:
    eng = _require()
    with eng.begin() as conn:
        conn.execute(insert(audit), {"payload": json.dumps(entry)})


def all_audit() -> list[dict]:
    """Every audit event in insertion order (oldest first); the API reverses for display."""
    eng = _require()
    with eng.connect() as conn:
        rows = conn.execute(select(audit.c.payload).order_by(audit.c.seq)).all()
    return [json.loads(r[0]) for r in rows]


# --- alert catalog: input data (alerts + their transactions) ----------------------

def seed_alerts(alert_dicts: list[dict]) -> None:
    """Idempotent ingest of the alert catalog into the DB: split each alert into its
    metadata row + one transaction row per ledger entry. Only seeds an empty table, so a
    restart keeps decision-updated statuses. Remembers the catalog so reset() restores it."""
    global _alert_seed
    _alert_seed = list(alert_dicts)
    eng = _require()
    with eng.begin() as conn:
        count = conn.execute(select(func.count()).select_from(alerts)).scalar_one()
        if count == 0:
            for a in _alert_seed:
                _insert_alert(conn, a)


def _insert_alert(conn, a: dict) -> None:
    meta = {k: v for k, v in a.items() if k != "transactions"}
    conn.execute(
        insert(alerts),
        {"alert_id": a["alertId"], "status": a["status"],
         "routing": a.get("routing"), "payload": json.dumps(meta)},
    )
    txns = a.get("transactions") or []
    if txns:
        conn.execute(
            insert(transactions),
            [{"transaction_id": t["transactionId"], "alert_id": a["alertId"],
              "seq": i, "payload": json.dumps(t)} for i, t in enumerate(txns)],
        )


def clear_alerts() -> None:
    """Drop the alert catalog (transactions first, then alerts). Used by the ingest CLI's
    --reset; reset() re-seeds afterwards."""
    eng = _require()
    with eng.begin() as conn:
        conn.execute(delete(transactions))
        conn.execute(delete(alerts))


def list_alerts(status: str | None = None, routing: str | None = None) -> list[dict]:
    """The queue: alert metadata (no transactions), filtered on the indexed status/routing
    columns — the production query path. Each returned alert carries transactions=None."""
    eng = _require()
    stmt = select(alerts.c.payload)
    if status is not None:
        stmt = stmt.where(alerts.c.status == status)
    if routing is not None:
        stmt = stmt.where(alerts.c.routing == routing)
    with eng.connect() as conn:
        rows = conn.execute(stmt).all()
    out = []
    for (payload,) in rows:
        a = json.loads(payload)
        a["transactions"] = None  # queue omits embedded transactions
        out.append(a)
    return out


def get_alert(alert_id: str) -> dict | None:
    """Alert detail: metadata + its transactions in ledger order. None if absent."""
    eng = _require()
    with eng.connect() as conn:
        row = conn.execute(
            select(alerts.c.payload).where(alerts.c.alert_id == alert_id)
        ).first()
        if row is None:
            return None
        a = json.loads(row[0])
        txn_rows = conn.execute(
            select(transactions.c.payload)
            .where(transactions.c.alert_id == alert_id)
            .order_by(transactions.c.seq)
        ).all()
    a["transactions"] = [json.loads(t[0]) for t in txn_rows]
    return a


def set_alert_decision(alert_id: str, status: str, str_draft: dict | None) -> None:
    """Persist a decision's effect on the alert row: the new status + resolved STR draft, so
    a restart preserves them with no separate replay step."""
    eng = _require()
    with eng.begin() as conn:
        row = conn.execute(
            select(alerts.c.payload).where(alerts.c.alert_id == alert_id)
        ).first()
        if row is None:
            return
        a = json.loads(row[0])
        a["status"] = status
        a["triage"]["strDraft"] = str_draft
        conn.execute(
            update(alerts).where(alerts.c.alert_id == alert_id)
            .values(status=status, payload=json.dumps(a))
        )


def count_alerts() -> int:
    eng = _require()
    with eng.connect() as conn:
        return conn.execute(select(func.count()).select_from(alerts)).scalar_one()


def count_transactions() -> int:
    eng = _require()
    with eng.connect() as conn:
        return conn.execute(select(func.count()).select_from(transactions)).scalar_one()


def reset() -> None:
    """Wipe all session state and restore the seeds — the persistence-layer equivalent of
    the demo /reset and the per-test isolation hook. Decisions + audit events are dropped;
    the alert catalog and the Queue Agent's audit seed are restored."""
    eng = _require()
    with eng.begin() as conn:
        conn.execute(delete(decisions))
        conn.execute(delete(audit))
        conn.execute(delete(transactions))
        conn.execute(delete(alerts))
    seed_audit(_seed)         # re-insert the remembered audit seed
    seed_alerts(_alert_seed)  # re-insert the remembered alert catalog
