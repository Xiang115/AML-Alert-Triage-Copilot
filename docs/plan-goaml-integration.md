# Plan — goAML STR Export (the integration seam)

**Goal:** Make the copilot visibly a *component inside a bank's compliance estate*, not a
standalone toy — by emitting the **regulator's actual wire format**. After a human signs off
on an escalation, one click produces a **schema-valid goAML STR XML** (the format BNM's FIU
ingests). This is the project's Market-Adoption (30) + Differentiation (30) anchor.

**One-line pitch:** *Most AML demos stop at a drafted report; we emit the regulator's real
wire format — schema-validated, gated behind human sign-off.*

Status: planned, not built. Target: land before prelim (26 Jun); build after current demo is solid.

---

## Locked decisions (from the grilling session)

| # | Decision | Rationale |
|---|---|---|
| 1 | Build a **thin real integration seam**, not just a slide. | Rubric rewards adoption path + compliance; a real seam beats a story. |
| 2 | **goAML STR export is the spine.** Inbound ingestion adapter is roadmap-only (dashed on diagram). | Depth over breadth; one deep real seam > two shallow ones. Export is deterministic → demo-safe. |
| 3 | Fidelity target **(B): faithful + XSD-validated, with a config seam that graduates to (A)**. | (A) full official-XSD conformance is a time bomb on a 6-day clock; (B) gets ~90% credibility, no external dependency, promotes to (A) via config. |
| 4 | **Transaction-based** report. Each `citedTransaction` → one `<transaction>`; from/to keyed by `direction` (subject = "my client"). | Strictly more faithful to our data; reuses the on-screen evidence (running-balance drain) → tight evidence→triage→STR→wire through-line. |
| 5 | `matchedTypology.code` → goAML `<report_indicators>` indicator, with a Q&A caveat that real indicator code lists are FIU-configurable. | Honest; keeps the typology visible on the wire. |
| 6 | Endpoint: **`GET /alerts/{alertId}/str.xml`**, `application/xml`. Serializes the **current (post-edit) `strDraft`**. | Human-in-the-loop edits flow all the way to the regulator artifact — the core product claim. |
| 7 | **Filing gate = `finalDisposition == escalate` on the decision record**, recomputed live every request. No decision → 409; dismissed → 409; escalate (approve *or* override-to-escalate) → emit. | The disposition, not the button label, is what legally triggers an STR. Override-to-escalate (the beat-3 hero path) **must** file. Live recompute → change-of-mind to dismiss instantly revokes export. |
| 8 | **Institution constants + reporting person live in one checked-in `goaml_config.json`** (the (B)→(A) swap seam). Reporting person = config default for the demo, with a "in prod this is the authenticated officer" caveat. | Mirrors the existing "constants → config, like the swappable LLM client" pattern. |
| 9 | **Validate at the endpoint** (refuse to emit a non-conforming doc) + CI test + **tightly-scoped derived XSD, every declared element populated**, header comment citing goAML schema version + UNODC/BNM reference. UI shows **"goAML 4.x · schema-valid ✓"** badge. | Credibility = provenance + honesty about the 2-3 stubbed config fields, not just a green check. A small fully-populated XSD reads as mastery; a half-empty one invites "why blank?". |
| 10 | **Not a 6th beat** — export is the closing flourish of **beat 4** (~20–30s). Inbound adapter shown **dashed/roadmap** on an explicit *integration-boundary* architecture diagram. | Protects the 7-min video budget + ADR-0003 determinism. The diagram scores both "architecture" and "adoption path." |

---

## Build plan

### Backend

1. **`backend/goaml.py`** (new) — pure serializer, no LLM, no I/O.
   - `to_goaml_str_xml(str_draft: STRDraft, decision: Decision, config: GoamlConfig) -> bytes`
   - Builds the transaction-based goAML report tree (`lxml.etree`):
     - report header: `rentity_id`, `submission_code=E`, `report_code=STR`, `entity_reference`,
       `submission_date`, `currency_code_local=MYR`, `reporting_person` (from config).
     - one `<transaction>` per `citedTransaction`; from/to assigned by `direction`
       (inbound → counterparty is `t_from`, subject is `t_to_my_client`; outbound → reversed).
     - `<reason>` ← `activitySummary` + `groundsForSuspicion[]`.
     - `<report_indicators>` ← `matchedTypology.code`.
   - Validates the built tree against the checked-in XSD **before returning**; raises on failure.
2. **`backend/data/goaml_config.json`** (new) — `{ rentityId, entityReference, submissionCode,
   reportCode, currencyCodeLocal, reportingPerson{...} }`. Loaded at startup like `results.json`.
3. **`backend/data/goaml_str.xsd`** (new) — tightly-scoped derived schema. Every element it
   declares is one we actually emit. Header comment cites goAML schema version + reference.
4. **`backend/main.py`** — add `GET /alerts/{alertId}/str.xml`:
   - `_require_alert`; look up `_DECISIONS[alertId]`.
   - gate: no decision → `409 STR_NOT_ADJUDICATED`; `finalDisposition == dismiss` →
     `409 STR_DISMISSED`; else serialize current `strDraft` via `goaml.to_goaml_str_xml`.
   - return `Response(content=..., media_type="application/xml")`.
   - load `goaml_config.json` at module load alongside `_RESULTS`/`_METRICS`.
5. **`backend/config.py`** — typed `GoamlConfig` loader (mirror existing config style).

### Frontend

6. **`frontend/src/api.ts`** — `strXmlUrl(alertId)` / a fetch helper for the XML download.
7. **STR editor / decision panel** (`StrEditor.tsx` / `DecisionPanel.tsx`) — **"Export goAML STR"**
   button, enabled **only when** the alert has an escalate decision (post-approval). Show the
   **"goAML 4.x · schema-valid ✓"** badge next to it. Clicking downloads / opens the XML.

### Tests

8. **`backend/tests/test_goaml.py`** — serialize a known `STRDraft`, assert it **validates against
   `goaml_str.xsd`** (lxml); assert from/to mapping per `direction`; assert typology→indicator.
9. **`backend/tests/test_api.py`** — gate matrix: no-decision→409, approve+dismiss→409,
   approve+escalate→200 XML, override+escalate→200 XML; change-to-dismiss revokes (→409).

### Docs / pitch

10. **Architecture diagram** — explicit integration boundary:
    `Bank TMS (Actimize/SAS) ⇢ [alert ingest adapter] → Copilot (retrieve→triage→verify→draft)
    → [decision + goAML export] → BNM goAML / case-management`. Inbound adapter **dashed = roadmap**.
11. **README pitch deck** — add the differentiation line (above) + the boundary diagram.

---

## Demo integration (beat 4 payoff — not a new beat)

> ...analyst edits the STR → **Approve** (finalDisposition = escalate) → the **Export goAML STR**
> button lights up → one click → a **schema-valid goAML STR**, the exact XML Malaysia's FIU
> ingests. "The system *cannot* file a malformed report, and *cannot* file without a human
> sign-off."

Deterministic (no LLM) → safe on the filmed critical path under ADR-0003.

## Honest caveats to keep ready for Q&A

- The XSD is **derived from the published goAML reference schema**, scoped to the STR
  transaction report — real element names/types/cardinalities. Per-FIU items (`rentity_id`,
  indicator code lists) are **config, not fiction**; swapping a real FIU's file promotes (B)→(A).
- Reporting person is a **config default** in the demo; in prod it's the authenticated officer
  who signed off (named on the wire — reinforces "no filing without sign-off").

## Roadmap (explicitly not built now)

- **Inbound alert-ingestion adapter** (`POST /alerts/ingest`): map a vendor TMS payload →
  `AlertInput`, run the pipeline live. Shown dashed on the diagram; build only if export lands
  clean and time remains.

## Sequencing

1. `goaml_str.xsd` + `goaml_config.json` (define the target shape first).
2. `goaml.py` serializer + `test_goaml.py` (red→green against the XSD).
3. `main.py` endpoint + gate + `test_api.py` gate matrix.
4. Frontend button/badge.
5. Diagram + README pitch line.
6. (Roadmap) inbound adapter — only if 1–5 are solid.
