# Pipeline and agents are fully typed; the FastAPI store stays dict, parsed at the seam

The agent pipeline traffics in Pydantic models end-to-end, with `schemas.py` as the single
source of every shape. The three previously-conflated dict shapes are now named:

- **`AlertInput`** — an Alert *before* triage (the pipeline's input). **`Alert(AlertInput)`** adds
  the one field, `triage`, so a stored `Alert` is also a valid `AlertInput` and flows straight into
  `run_triage` without fighting `extra="forbid"`.
- **`TriageOutput`** — the internal Triage Agent output; it carries `fired_indicators` (consumed by
  confidence + STR drafting), which the wire `TriageResult` never exposes.
- **`TypologyCard`** — the curated Card (ADR-0002), previously a raw dict read with string keys in
  `triage.py`/`verifier.py`.

Every agent now constructs and reads models (`alert.account.holder_name`, `card.distinguishing_test`),
so the contract is checked at **construction**, not only at the boundary — a key typo fails
immediately instead of slipping to an edge `model_validate`. This also makes `schemas.py`'s stated
"internal fields snake_case" convention true (the agents previously read camelCase dicts, violating it).

**Deliberately NOT typed: the FastAPI in-memory store.** `main._ALERTS` stays `dict[str, dict]`, and
the live `/triage` endpoint parses to `Alert` only at the `run_triage` seam. The
`list`/`detail`/`decision`/`reset` paths keep their dict logic.

Why the asymmetry: the value of typing is highest where shapes are *constructed and composed* (the
pipeline) and lowest where they are *passed through and re-serialized* (the serving layer). Typing the
store would rewrite four working endpoints and their 13 passing API tests for little leverage, against
the 23 Jun golden-path lock. The seam-parse caps the blast radius to one endpoint while still handing
`run_triage` a typed input.

Recorded so a future architecture review does not re-suggest "type the in-memory store" without first
weighing it against this trade-off. Revisit if the serving layer grows logic beyond pass-through
(e.g. server-side filtering/derivation over alerts), at which point the dicts stop being a pass-through
and typing the store would start earning its keep.

Rejected: (a) one `Alert` type for both input and output — input alerts have no `triage`, and
`extra="forbid"` makes a single permissive type lossy. (b) Fully typing the store — see above.

## Addendum: the `decide` endpoint grew logic — resolved by extraction, not by typing the store

The forecast above arrived: `POST /decision` encodes a real domain invariant (the disposition→STR
rule) plus a `Decision` record, so it is no longer a pure pass-through. That did **not** force typing
the store. Instead we kept the third path this ADR's seam-parse philosophy implies: the
disposition→STR rule moved into a pure `decision.resolve_str_draft` (unit-tested off the store, like
`confidence.py`), and the endpoint constructs a typed `schemas.Decision` at the seam (killing the
drift where the previously-unused `Decision` model diverged from an inline `decidedAt` dict). The store
stays `dict[str, dict]`. So "serving grew logic" was answered by concentrating that logic behind a
small tested seam, which is cheaper than rewriting the store and its API tests — typing the *whole*
store still hasn't earned its keep.
