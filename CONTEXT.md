# AML Alert-Triage Copilot

The shared domain language for the NexHack Track 2 copilot that helps a bank AML analyst
triage suspicious-transaction alerts. Terms here are the canonical vocabulary for prompts,
API fields, and the deck — keep them consistent everywhere.

## Language

**Alert**:
A flagged item in the analyst's queue representing one account's suspicious activity to be reviewed.
_Avoid_: case, flag (as a noun for the whole item)

**Triage**:
The act of deciding **Escalate** or **Dismiss** for an Alert, with confidence and a grounded explanation.
_Avoid_: analyze, analysis, classify (the architecture draft said "analyze" — resolved to **Triage**)

**Triage Agent**:
The first-pass LLM that produces the Triage decision.

**Verifier (Agent)**:
An independent **adversarial QA** second pass that assumes the Triage call may be wrong and tries to
break it against the typology's distinguishing test. Emits `agreed` or `flagged`.
_Avoid_: reviewer, checker, second opinion (it is adversarial, not a polite re-check)

**Typology**:
A named money-laundering pattern (e.g. structuring, pass-through). Encoded as a **Typology Card**.

**Typology Card**:
The curated, hand-authored knowledge unit for one Typology (`backend/data/typologies/typologies.json`):
indicators, data signals, benign look-alike, and a distinguishing test. The retrieval unit — there is no PDF RAG.

**Distinguishing Test**:
The check that separates a Typology from its **Benign Look-alike**. The Verifier's core weapon.

**Benign Look-alike**:
An innocent pattern that superficially resembles a Typology (high-turnover business, salary/rent),
crafted into the dataset so Triage and Verifier must discriminate.

**Disposition**:
The outcome of an Alert: `escalate` or `dismiss`. The analyst's **final disposition** may differ from
the AI recommendation when they **override**.

**STR (Suspicious Transaction Report)**:
The regulator-facing report drafted by the AI when the recommendation is **escalate**; the analyst
edits and approves it. Drafted only on escalate.
_Avoid_: SAR (US term) — this is Malaysia-first; use **STR**.

**Decision**:
The analyst's action on an Alert — `approve` or `override` — producing the final disposition.

## Relationships

- An **Alert** is triaged by the **Triage Agent**, producing one Triage decision (Escalate/Dismiss).
- The **Verifier** independently challenges that decision against the matched **Typology Card**'s **Distinguishing Test**.
- A Triage decision references one **Typology** (`matchedTypology`) and cites supporting transactions.
- An **STR** is drafted only when the disposition is `escalate`.
- The analyst's **Decision** sets the **final disposition**, which may **override** the AI.

## Example dialogue

> **Dev:** "If the **Verifier** flags the call, does the **STR** still get drafted?"
> **Analyst:** "Draft it anyway if Triage said escalate — the flag just means the human must review
> before approving. The **Verifier** challenges the **Disposition**, it doesn't block the **STR** draft."

## Flagged ambiguities

- "analyze" / "analysis" (architecture draft, `/analyze` endpoint) was used for what we now call
  **Triage** — resolved: the canonical term is **Triage**, and the live endpoint is `/triage`.
- "verifier" was initially a polite double-check; resolved to an **adversarial QA** role
  (see `docs/adr/0001`).
